from __future__ import annotations

import hashlib
import hmac
import ipaddress
import re
import threading
import time
from collections import defaultdict, deque
from urllib.parse import urlsplit

_CONTROL = re.compile(r"[\x00-\x1f\x7f]+")


def clean_text(value: object, maximum: int = 120) -> str:
    text = _CONTROL.sub(" ", str(value or ""))
    text = " ".join(text.split())
    return text[:maximum]


def mask_email(value: object) -> str:
    email = clean_text(value, 160)
    if "@" not in email:
        return "account-••••"
    local, domain = email.rsplit("@", 1)
    first = local[:1] or "•"
    domain_parts = domain.split(".")
    domain_head = domain_parts[0][:1] if domain_parts and domain_parts[0] else "•"
    suffix = f".{domain_parts[-1]}" if len(domain_parts) > 1 else ""
    return f"{first}•••@{domain_head}•••{suffix}"


def opaque_handle(salt: bytes, raw_identifier: str) -> str:
    digest = hmac.new(salt, raw_identifier.encode("utf-8", "replace"), hashlib.sha256).hexdigest()
    return f"cc_{digest[:18]}"


def token_matches(header_value: str | None, expected: str) -> bool:
    if not header_value or not header_value.startswith("Bearer "):
        return False
    supplied = header_value[7:]
    return hmac.compare_digest(supplied, expected)


def normalize_host(value: str) -> str | None:
    try:
        parsed = urlsplit(f"//{value}")
        if parsed.username or parsed.password or not parsed.hostname:
            return None
        return parsed.hostname.lower().rstrip(".")
    except ValueError:
        return None


def _host_port(value: str) -> int | None:
    try:
        parsed = urlsplit(f"//{value}")
        if parsed.username or parsed.password or not parsed.hostname:
            return None
        return parsed.port
    except ValueError:
        return None


def host_allowed(host_header: str | None, allowed_hosts: frozenset[str]) -> bool:
    if not host_header:
        return False
    normalized = normalize_host(host_header)
    return normalized in allowed_hosts if normalized else False


def same_origin(origin: str | None, host_header: str | None) -> bool:
    if not origin:
        return True
    try:
        parsed = urlsplit(origin)
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not host_header:
        return False
    origin_host = normalize_host(parsed.netloc)
    request_host = normalize_host(host_header)
    if not origin_host or origin_host != request_host:
        return False
    try:
        origin_explicit_port = parsed.port
    except ValueError:
        return False
    request_port = _host_port(host_header)
    if request_port is None:
        return origin_explicit_port is None
    origin_port = origin_explicit_port or (443 if parsed.scheme == "https" else 80)
    return origin_port == request_port


def peer_key(address: str) -> str:
    try:
        return str(ipaddress.ip_address(address.split("%", 1)[0]))
    except ValueError:
        return "unknown"


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window
        with self._lock:
            events = self._events[key]
            while events and events[0] < cutoff:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            if len(self._events) > 2048:
                stale = [item for item, values in self._events.items() if not values or values[-1] < cutoff]
                for item in stale[:512]:
                    self._events.pop(item, None)
            return True


SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": (
        "default-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'; "
        "img-src 'self' data:; connect-src 'self'; font-src 'self'; object-src 'none'; "
        "script-src 'self'; style-src 'self'"
    ),
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}
