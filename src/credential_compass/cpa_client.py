from __future__ import annotations

import http.client
import ipaddress
import json
import socket
import ssl
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

MAX_RESPONSE_BYTES = 512 * 1024
PROBE_TARGET = "https://chatgpt.com/backend-api/wham/usage"


class ClientError(RuntimeError):
    """A deliberately non-sensitive upstream failure."""


@dataclass(frozen=True, slots=True)
class ClientSettings:
    base_url: str
    management_key: str
    timeout: int
    max_accounts: int
    approved_addresses: frozenset[str]


class CPAClient:
    def __init__(self, settings: ClientSettings) -> None:
        self.settings = settings
        self._parsed = urlsplit(settings.base_url)
        self._tls = ssl.create_default_context()
        self._tls.minimum_version = ssl.TLSVersion.TLSv1_2

    def _connection(self) -> http.client.HTTPConnection:
        host = self._parsed.hostname or ""
        if not self.settings.approved_addresses:
            raise ClientError("CLIProxyAPI has no approved connection address")
        approved = min(
            self.settings.approved_addresses,
            key=lambda value: (ipaddress.ip_address(value).version, int(ipaddress.ip_address(value))),
        )
        port = self._parsed.port or (443 if self._parsed.scheme == "https" else 80)
        if self._parsed.scheme == "https":
            connection: http.client.HTTPConnection = http.client.HTTPSConnection(
                host, port, timeout=self.settings.timeout, context=self._tls
            )
        else:
            connection = http.client.HTTPConnection(host, port, timeout=self.settings.timeout)

        def create_pinned_connection(
            _address: tuple[str, int],
            timeout: float | object = socket._GLOBAL_DEFAULT_TIMEOUT,
            source_address: tuple[str, int] | None = None,
        ) -> socket.socket:
            return socket.create_connection((approved, port), timeout, source_address)

        connection._create_connection = create_pinned_connection  # type: ignore[method-assign]
        return connection

    def _connect_and_verify(self, connection: http.client.HTTPConnection) -> None:
        connection.connect()
        if connection.sock is None:
            raise ClientError("CLIProxyAPI connection was not established")
        peer = str(ipaddress.ip_address(connection.sock.getpeername()[0].split("%", 1)[0]))
        if peer not in self.settings.approved_addresses:
            raise ClientError("CLIProxyAPI connected to an unapproved address")

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.settings.management_key}",
            "X-Management-Key": self.settings.management_key,
            "User-Agent": "CredentialCompass/1.0",
            "Connection": "close",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        connection = self._connection()
        try:
            self._connect_and_verify(connection)
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        except (OSError, TimeoutError, http.client.HTTPException) as exc:
            raise ClientError("CLIProxyAPI is unavailable") from exc
        finally:
            connection.close()
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ClientError("CLIProxyAPI returned an oversized response")
        if response.status in {301, 302, 303, 307, 308}:
            raise ClientError("CLIProxyAPI redirects are not followed")
        if not 200 <= response.status < 300:
            raise ClientError(f"CLIProxyAPI returned HTTP {response.status}")
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ClientError("CLIProxyAPI returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise ClientError("CLIProxyAPI returned an unexpected response")
        return data

    def get_auth_files(self) -> list[dict[str, Any]]:
        data = self._request("GET", "/v0/management/auth-files")
        files = data.get("files")
        if not isinstance(files, list):
            raise ClientError("CLIProxyAPI did not return a credential list")
        if len(files) > self.settings.max_accounts:
            raise ClientError("The credential pool exceeds COMPASS_MAX_ACCOUNTS")
        return [item for item in files if isinstance(item, dict)]

    def probe(self, file_info: dict[str, Any]) -> tuple[int, Any]:
        auth_index = file_info.get("auth_index")
        if auth_index is None or isinstance(auth_index, (dict, list)):
            raise ClientError("A credential is missing its auth index")
        account_id = str((file_info.get("id_token") or {}).get("chatgpt_account_id") or "")[:160]
        payload = {
            "authIndex": auth_index,
            "method": "GET",
            "url": PROBE_TARGET,
            "header": {
                "Authorization": "Bearer $TOKEN$",
                "Content-Type": "application/json",
                "Chatgpt-Account-Id": account_id,
            },
        }
        data = self._request("POST", "/v0/management/api-call", payload)
        try:
            status_code = int(data.get("status_code", -1))
        except (TypeError, ValueError):
            status_code = -1
        return status_code, data.get("body")

    def set_disabled(self, raw_id: str, disabled: bool) -> bool:
        data = self._request(
            "PATCH",
            "/v0/management/auth-files/status",
            {"name": raw_id, "disabled": bool(disabled)},
        )
        return data.get("status") == "ok"

    def test_connection(self) -> bool:
        self.get_auth_files()
        return True


class DemoCPAClient:
    _FILES = (
        ("demo-aurora.json", "aurora@example.com", False, 200, 38.0, "plus"),
        ("demo-river.json", "river@example.net", False, 200, 72.0, "team"),
        ("demo-moss.json", "moss@example.org", False, 401, None, ""),
        ("demo-comet.json", "comet@example.com", False, 429, None, ""),
        ("demo-linen.json", "linen@example.net", True, -1, None, ""),
        ("demo-cove.json", "cove@example.org", False, 200, 96.0, "free"),
    )

    def get_auth_files(self) -> list[dict[str, Any]]:
        return [
            {
                "id": raw_id,
                "email": email,
                "provider": "codex",
                "disabled": disabled,
                "auth_index": index,
                "id_token": {"chatgpt_account_id": f"demo-{index}"},
            }
            for index, (raw_id, email, disabled, _status, _used, _plan) in enumerate(self._FILES)
        ]

    def probe(self, file_info: dict[str, Any]) -> tuple[int, Any]:
        time.sleep(0.03)
        index = int(file_info.get("auth_index", 0))
        _raw_id, _email, _disabled, status, used, plan = self._FILES[index]
        if status == 200:
            return (
                status,
                {
                    "plan_type": plan,
                    "rate_limit": {
                        "allowed": used is not None and used < 100,
                        "limit_reached": used is not None and used >= 100,
                        "primary_window": {
                            "used_percent": used,
                            "resets_at": "2026-08-14T08:00:00Z",
                        },
                    },
                },
            )
        if status == 401:
            return status, {"error": {"message": "token expired"}}
        return status, {}

    def set_disabled(self, raw_id: str, disabled: bool) -> bool:
        del raw_id, disabled
        return True

    def test_connection(self) -> bool:
        return True
