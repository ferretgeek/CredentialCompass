from __future__ import annotations

import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Protocol

from .classifier import classify
from .security import clean_text, mask_email, opaque_handle


class CredentialClient(Protocol):
    def get_auth_files(self) -> list[dict[str, Any]]: ...

    def probe(self, file_info: dict[str, Any]) -> tuple[int, Any]: ...

    def set_disabled(self, raw_id: str, disabled: bool) -> bool: ...

    def test_connection(self) -> bool: ...


@dataclass(slots=True)
class StoredCredential:
    handle: str
    raw_id: str
    email: str
    disabled: bool
    status_code: int | None
    category: dict[str, Any]

    def public(self, reveal: bool) -> dict[str, Any]:
        quota = dict(self.category.get("quota") or {})
        return {
            "handle": self.handle,
            "account": self.email if reveal else mask_email(self.email),
            "revealed": reveal,
            "disabled": self.disabled,
            "status_code": self.status_code,
            "category": self.category.get("key", "unknown"),
            "label": self.category.get("label", "状态待确认"),
            "tone": self.category.get("tone", "neutral"),
            "quota": quota,
        }


class CompassState:
    def __init__(self, client: CredentialClient, *, live_probe: bool, concurrency: int) -> None:
        self.client = client
        self.live_probe = live_probe
        self.default_concurrency = concurrency
        self._salt = secrets.token_bytes(32)
        self._lock = threading.RLock()
        self._cancel = threading.Event()
        self._running = False
        self._phase = "idle"
        self._started_at = 0.0
        self._completed = 0
        self._total = 0
        self._items: list[StoredCredential] = []
        self._by_handle: dict[str, StoredCredential] = {}
        self._events: list[dict[str, str]] = []
        self._error = ""

    def _event(self, message: str, tone: str = "neutral") -> None:
        with self._lock:
            self._events.append({"time": time.strftime("%H:%M:%S"), "message": message, "tone": tone})
            self._events = self._events[-40:]

    def start_scan(self, *, concurrency: int, limit: int) -> bool:
        with self._lock:
            if self._running:
                return False
            self._running = True
            self._phase = "inventory"
            self._started_at = time.monotonic()
            self._completed = 0
            self._total = 0
            self._error = ""
            self._items = []
            self._by_handle = {}
            self._cancel.clear()
        worker = threading.Thread(target=self._run_scan, args=(concurrency, limit), daemon=True)
        worker.start()
        return True

    def _identity(self, file_info: dict[str, Any], index: int) -> tuple[str, str]:
        raw_id = clean_text(file_info.get("id"), 240) or f"credential-{index}"
        email = (
            clean_text(file_info.get("email") or file_info.get("account") or file_info.get("label"), 160)
            or f"account-{index + 1}"
        )
        return raw_id, email

    def _run_scan(self, concurrency: int, limit: int) -> None:
        try:
            files = [item for item in self.client.get_auth_files() if item.get("provider") == "codex"]
            if limit > 0:
                files = files[:limit]
            with self._lock:
                self._total = len(files)
                self._phase = "probing" if self.live_probe else "inventory"
            stored: list[StoredCredential] = []
            for index, file_info in enumerate(files):
                raw_id, email = self._identity(file_info, index)
                disabled = file_info.get("disabled") is True
                category = {
                    "key": "disabled" if disabled else "inventory",
                    "label": "已停用" if disabled else "等待探测" if self.live_probe else "已收录",
                    "tone": "neutral",
                    "quota": {"state": "unknown", "plan": "", "used_percent": None, "resets_at": ""},
                }
                stored.append(
                    StoredCredential(
                        handle=opaque_handle(self._salt, raw_id),
                        raw_id=raw_id,
                        email=email,
                        disabled=disabled,
                        status_code=None,
                        category=category,
                    )
                )
            with self._lock:
                self._items = stored
                self._by_handle = {item.handle: item for item in stored}

            active = [
                (item, file_info) for item, file_info in zip(stored, files, strict=False) if not item.disabled
            ]
            if self.live_probe and active and not self._cancel.is_set():
                workers = max(1, min(concurrency, self.default_concurrency, 8, len(active)))
                with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="compass-probe") as pool:
                    futures = {pool.submit(self.client.probe, file_info): item for item, file_info in active}
                    for future in as_completed(futures):
                        if self._cancel.is_set():
                            for pending in futures:
                                pending.cancel()
                            break
                        item = futures[future]
                        try:
                            status_code, body = future.result()
                            category = classify(status_code, body)
                        except Exception:
                            status_code = -1
                            category = classify(-1, None)
                        with self._lock:
                            item.status_code = status_code
                            item.category = category
                            self._completed += 1
            else:
                with self._lock:
                    self._completed = len(stored)
            with self._lock:
                self._phase = "cancelled" if self._cancel.is_set() else "complete"
                if not self._cancel.is_set():
                    self._completed = len(stored)
            self._event("扫描已取消" if self._cancel.is_set() else f"完成 {len(stored)} 枚凭证的健康盘点")
        except Exception:
            with self._lock:
                self._phase = "error"
                self._error = "无法完成盘点，请检查服务端配置与管理接口"
            self._event("盘点未完成，服务端配置需要检查", "bad")
        finally:
            with self._lock:
                self._running = False

    def cancel(self) -> bool:
        with self._lock:
            if not self._running:
                return False
            self._cancel.set()
            self._phase = "cancelling"
            return True

    def change_status(self, handles: list[str], *, disabled: bool) -> dict[str, int]:
        with self._lock:
            if self._running:
                raise RuntimeError("A scan is still running")
            targets = [self._by_handle[item] for item in dict.fromkeys(handles) if item in self._by_handle]
        changed = 0
        failed = 0
        for item in targets:
            try:
                ok = self.client.set_disabled(item.raw_id, disabled)
            except Exception:
                ok = False
            if ok:
                with self._lock:
                    item.disabled = disabled
                    item.category = {
                        "key": "disabled" if disabled else "inventory",
                        "label": "已停用" if disabled else "等待重新探测",
                        "tone": "neutral",
                        "quota": {"state": "unknown", "plan": "", "used_percent": None, "resets_at": ""},
                    }
                    item.status_code = None
                changed += 1
            else:
                failed += 1
        action = "停用" if disabled else "恢复"
        self._event(f"{action}完成：成功 {changed}，失败 {failed}", "good" if not failed else "warn")
        return {"matched": len(targets), "changed": changed, "failed": failed}

    def snapshot(self, *, reveal: bool = False) -> dict[str, Any]:
        with self._lock:
            items = [item.public(reveal) for item in self._items]
            running = self._running
            phase = self._phase
            completed = self._completed
            total = self._total
            error = self._error
            events = list(self._events)
            elapsed = time.monotonic() - self._started_at if self._started_at else 0.0
        healthy = sum(1 for item in items if item["category"] == "healthy")
        attention = sum(1 for item in items if item["tone"] in {"bad", "warn"})
        disabled = sum(1 for item in items if item["disabled"])
        quota_values = [
            item["quota"].get("used_percent")
            for item in items
            if isinstance(item["quota"].get("used_percent"), (int, float))
        ]
        return {
            "running": running,
            "phase": phase,
            "completed": completed,
            "total": total,
            "percent": round(completed / total * 100, 1) if total else 0,
            "elapsed_seconds": round(elapsed, 1),
            "error": error,
            "summary": {
                "total": len(items),
                "healthy": healthy,
                "attention": attention,
                "disabled": disabled,
                "average_used_percent": round(sum(quota_values) / len(quota_values), 1)
                if quota_values
                else None,
            },
            "items": items,
            "events": events,
        }
