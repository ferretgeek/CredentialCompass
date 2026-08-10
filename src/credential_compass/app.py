from __future__ import annotations

import json
import mimetypes
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from typing import Any
from urllib.parse import parse_qs, urlsplit

from . import __version__
from .config import AppConfig
from .cpa_client import ClientSettings, CPAClient, DemoCPAClient
from .security import (
    SECURITY_HEADERS,
    SlidingWindowLimiter,
    client_peer_key,
    host_allowed,
    same_origin,
    token_matches,
)
from .state import CompassState

MAX_REQUEST_BYTES = 32 * 1024
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/assets/app.css": ("app.css", "text/css; charset=utf-8"),
    "/assets/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/favicon.svg": ("favicon.svg", "image/svg+xml"),
    "/favicon.png": ("favicon.png", "image/png"),
    "/favicon.ico": ("favicon.ico", "image/x-icon"),
}


class CredentialCompassServer:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        client = (
            DemoCPAClient()
            if config.demo
            else CPAClient(
                ClientSettings(
                    base_url=config.cpa_url,
                    management_key=config.cpa_key,
                    timeout=config.request_timeout,
                    max_accounts=config.max_accounts,
                    approved_addresses=config.cpa_addresses,
                )
            )
        )
        self.state = CompassState(client, live_probe=config.live_probe, concurrency=config.concurrency)
        self.client = client
        self.general_limiter = SlidingWindowLimiter(240, 60)
        self.action_limiter = SlidingWindowLimiter(20, 60)
        self.static_root = files("credential_compass").joinpath("static")

    def handler_class(self) -> type[BaseHTTPRequestHandler]:
        application = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "CredentialCompass"
            sys_version = ""

            def log_message(self, _format: str, *args: object) -> None:
                del args

            def _headers(self, *, content_type: str, length: int, cache: str = "no-store") -> None:
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(length))
                for name, value in SECURITY_HEADERS.items():
                    self.send_header(name, cache if name == "Cache-Control" else value)

            def _send(self, status: int, body: bytes, content_type: str, *, cache: str = "no-store") -> None:
                self.send_response(status)
                self._headers(content_type=content_type, length=len(body), cache=cache)
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(body)

            def _json(self, status: int, payload: dict[str, Any]) -> None:
                body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                self._send(status, body, "application/json; charset=utf-8")

            def _error(self, status: int, code: str, message: str) -> None:
                self._json(status, {"error": {"code": code, "message": message}})

            def _request_allowed(self, *, action: bool = False) -> bool:
                host = self.headers.get("Host")
                if not host_allowed(host, application.config.allowed_hosts):
                    self._error(HTTPStatus.BAD_REQUEST, "invalid_host", "The request host is not allowed")
                    return False
                fetch_site = (self.headers.get("Sec-Fetch-Site") or "").lower()
                if fetch_site == "cross-site" or not same_origin(self.headers.get("Origin"), host):
                    self._error(HTTPStatus.FORBIDDEN, "cross_origin", "Cross-origin requests are blocked")
                    return False
                remote = client_peer_key(
                    self.client_address[0],
                    self.headers.get("X-Forwarded-For"),
                    application.config.trusted_proxy_ips,
                )
                limiter = application.action_limiter if action else application.general_limiter
                if not limiter.allow(remote):
                    self._error(
                        HTTPStatus.TOO_MANY_REQUESTS, "rate_limited", "Please wait before trying again"
                    )
                    return False
                return True

            def _authenticated(self) -> bool:
                if token_matches(self.headers.get("Authorization"), application.config.access_token):
                    return True
                self._error(HTTPStatus.UNAUTHORIZED, "unauthorized", "Enter the local access token")
                return False

            def _body(self) -> dict[str, Any] | None:
                content_type = (self.headers.get("Content-Type") or "").split(";", 1)[0].lower()
                if content_type != "application/json":
                    self._error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "content_type", "JSON is required")
                    return None
                try:
                    length = int(self.headers.get("Content-Length") or "0")
                except ValueError:
                    self._error(HTTPStatus.BAD_REQUEST, "content_length", "Invalid request length")
                    return None
                if length <= 0 or length > MAX_REQUEST_BYTES:
                    self._error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "body_size", "Request body is too large")
                    return None
                raw = self.rfile.read(length)
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self._error(HTTPStatus.BAD_REQUEST, "invalid_json", "Request body is not valid JSON")
                    return None
                if not isinstance(payload, dict):
                    self._error(HTTPStatus.BAD_REQUEST, "invalid_json", "A JSON object is required")
                    return None
                return payload

            def _static(self, path: str) -> bool:
                entry = STATIC_FILES.get(path)
                if not entry:
                    return False
                filename, content_type = entry
                resource = application.static_root.joinpath(filename)
                try:
                    body = resource.read_bytes()
                except FileNotFoundError:
                    self._error(HTTPStatus.NOT_FOUND, "not_found", "Asset not found")
                    return True
                cache = "public, max-age=0, must-revalidate" if path.startswith("/assets/") else "no-store"
                self._send(
                    HTTPStatus.OK,
                    body,
                    content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream",
                    cache=cache,
                )
                return True

            def do_HEAD(self) -> None:  # noqa: N802
                self.do_GET()

            def do_GET(self) -> None:  # noqa: N802
                path = urlsplit(self.path).path
                if not self._request_allowed():
                    return
                if self._static(path):
                    return
                if path == "/api/health":
                    self._json(HTTPStatus.OK, {"status": "ok", "version": __version__})
                    return
                if not path.startswith("/api/"):
                    self._error(HTTPStatus.NOT_FOUND, "not_found", "Page not found")
                    return
                if not self._authenticated():
                    return
                if path == "/api/bootstrap":
                    self._json(
                        HTTPStatus.OK,
                        {
                            "version": __version__,
                            "demo": application.config.demo,
                            "live_probe": application.config.live_probe,
                            "status_changes": application.config.allow_status_changes,
                            "max_accounts": application.config.max_accounts,
                            "default_concurrency": application.config.concurrency,
                        },
                    )
                    return
                if path == "/api/state":
                    query = parse_qs(urlsplit(self.path).query)
                    reveal = query.get("reveal", ["0"])[0] == "1"
                    self._json(HTTPStatus.OK, application.state.snapshot(reveal=reveal))
                    return
                if path == "/api/connection":
                    try:
                        ok = application.client.test_connection()
                    except Exception:
                        ok = False
                    self._json(HTTPStatus.OK, {"connected": ok})
                    return
                self._error(HTTPStatus.NOT_FOUND, "not_found", "API route not found")

            def do_POST(self) -> None:  # noqa: N802
                path = urlsplit(self.path).path
                if not self._request_allowed(action=True) or not self._authenticated():
                    return
                payload = self._body()
                if payload is None:
                    return
                if path == "/api/scan":
                    try:
                        concurrency = int(payload.get("concurrency", application.config.concurrency))
                        limit = int(payload.get("limit", 0))
                    except (TypeError, ValueError):
                        self._error(HTTPStatus.BAD_REQUEST, "scan_options", "Scan options must be integers")
                        return
                    if not 1 <= concurrency <= 8 or not 0 <= limit <= application.config.max_accounts:
                        self._error(
                            HTTPStatus.BAD_REQUEST, "scan_options", "Scan options are outside safe limits"
                        )
                        return
                    if not application.state.start_scan(concurrency=concurrency, limit=limit):
                        self._error(HTTPStatus.CONFLICT, "scan_running", "A scan is already running")
                        return
                    self._json(HTTPStatus.ACCEPTED, {"status": "started"})
                    return
                if path == "/api/scan/cancel":
                    if not application.state.cancel():
                        self._error(HTTPStatus.CONFLICT, "scan_idle", "No scan is running")
                        return
                    self._json(HTTPStatus.ACCEPTED, {"status": "cancelling"})
                    return
                if path == "/api/credentials/status":
                    if not application.config.allow_status_changes:
                        self._error(
                            HTTPStatus.FORBIDDEN, "read_only", "Status changes are disabled by the operator"
                        )
                        return
                    action = str(payload.get("action") or "")
                    handles = payload.get("handles")
                    if action not in {"disable", "enable"} or not isinstance(handles, list):
                        self._error(
                            HTTPStatus.BAD_REQUEST,
                            "status_request",
                            "A supported action and handle list are required",
                        )
                        return
                    clean_handles = [str(item) for item in handles if isinstance(item, str)][:51]
                    if not clean_handles or len(clean_handles) > 50:
                        self._error(
                            HTTPStatus.BAD_REQUEST, "status_request", "Choose between 1 and 50 credentials"
                        )
                        return
                    expected = f"{action.upper()} {len(dict.fromkeys(clean_handles))}"
                    if payload.get("confirmation") != expected:
                        self._error(HTTPStatus.BAD_REQUEST, "confirmation", f"Type {expected} to continue")
                        return
                    try:
                        result = application.state.change_status(clean_handles, disabled=action == "disable")
                    except RuntimeError:
                        self._error(
                            HTTPStatus.CONFLICT, "scan_running", "Wait for the current scan to finish"
                        )
                        return
                    self._json(HTTPStatus.OK, result)
                    return
                self._error(HTTPStatus.NOT_FOUND, "not_found", "API route not found")

            def do_OPTIONS(self) -> None:  # noqa: N802
                self._error(HTTPStatus.METHOD_NOT_ALLOWED, "method", "CORS is not enabled")

        return Handler

    def serve_forever(self) -> None:
        server = ThreadingHTTPServer((self.config.bind_host, self.config.port), self.handler_class())
        server.daemon_threads = True
        server.request_queue_size = 64
        try:
            server.serve_forever(poll_interval=0.25)
        finally:
            server.server_close()

    def start_in_thread(self) -> tuple[ThreadingHTTPServer, threading.Thread]:
        server = ThreadingHTTPServer((self.config.bind_host, self.config.port), self.handler_class())
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread
