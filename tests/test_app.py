from __future__ import annotations

import http.client
import json
import time
import unittest

from credential_compass.app import CredentialCompassServer
from credential_compass.config import AppConfig


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.token = "test-access-token-for-credential-compass"
        config = AppConfig(
            bind_host="127.0.0.1",
            port=0,
            access_token=cls.token,
            generated_access_token=False,
            allowed_hosts=frozenset({"127.0.0.1", "localhost"}),
            trusted_proxy_ips=frozenset(),
            cpa_url="demo://local",
            cpa_host="demo",
            cpa_addresses=frozenset(),
            cpa_key="",
            demo=True,
            live_probe=True,
            allow_status_changes=True,
            max_accounts=100,
            concurrency=4,
            request_timeout=5,
            allow_private_http=False,
        )
        cls.application = CredentialCompassServer(config)
        cls.server, cls.thread = cls.application.start_in_thread()
        cls.port = cls.server.server_port

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(2)

    def request(self, method, path, payload=None, *, token=True, host=None, origin=None, raw=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        host_value = host or f"127.0.0.1:{self.port}"
        headers = {"Host": host_value}
        if token:
            headers["Authorization"] = f"Bearer {self.token}"
        if origin is not None:
            headers["Origin"] = origin
        body = raw
        if payload is not None:
            body = json.dumps(payload)
            headers["Content-Type"] = "application/json"
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        data = response.read()
        result_headers = dict(response.getheaders())
        connection.close()
        return response.status, result_headers, data

    def test_static_page_has_security_headers(self) -> None:
        status, headers, body = self.request("GET", "/", token=False)
        self.assertEqual(status, 200)
        self.assertIn(b"Credential Compass", body)
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])

    def test_health_is_public_but_bootstrap_requires_token(self) -> None:
        self.assertEqual(self.request("GET", "/api/health", token=False)[0], 200)
        self.assertEqual(self.request("GET", "/api/bootstrap", token=False)[0], 401)
        self.assertEqual(self.request("GET", "/api/bootstrap")[0], 200)

    def test_invalid_host_is_rejected(self) -> None:
        self.assertEqual(self.request("GET", "/", token=False, host="evil.example")[0], 400)

    def test_cross_origin_write_is_rejected(self) -> None:
        status, _headers, _body = self.request(
            "POST", "/api/scan", {"concurrency": 1, "limit": 1}, origin="https://evil.example"
        )
        self.assertEqual(status, 403)

    def test_cross_port_write_is_rejected(self) -> None:
        status, _headers, _body = self.request(
            "POST",
            "/api/scan",
            {"concurrency": 1, "limit": 1},
            origin="http://127.0.0.1:65535",
        )
        self.assertEqual(status, 403)

    def test_scan_reaches_complete_state(self) -> None:
        origin = f"http://127.0.0.1:{self.port}"
        status, _headers, _body = self.request(
            "POST", "/api/scan", {"concurrency": 4, "limit": 0}, origin=origin
        )
        self.assertEqual(status, 202)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            status, _headers, raw = self.request("GET", "/api/state")
            state = json.loads(raw)
            if not state["running"]:
                break
            time.sleep(0.02)
        self.assertEqual(status, 200)
        self.assertEqual(state["phase"], "complete")
        self.assertEqual(state["percent"], 100.0)

    def test_reveal_is_explicit_and_authenticated(self) -> None:
        origin = f"http://127.0.0.1:{self.port}"
        self.request("POST", "/api/scan", {"concurrency": 4, "limit": 0}, origin=origin)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            _status, _headers, current = self.request("GET", "/api/state")
            if not json.loads(current)["running"]:
                break
            time.sleep(0.02)
        _status, _headers, masked = self.request("GET", "/api/state")
        _status, _headers, revealed = self.request("GET", "/api/state?reveal=1")
        self.assertNotIn(b"aurora@example.com", masked)
        self.assertIn(b"aurora@example.com", revealed)

    def test_status_change_requires_exact_confirmation(self) -> None:
        _status, _headers, raw = self.request("GET", "/api/state")
        handle = json.loads(raw)["items"][0]["handle"]
        origin = f"http://127.0.0.1:{self.port}"
        wrong = self.request(
            "POST",
            "/api/credentials/status",
            {"action": "disable", "handles": [handle], "confirmation": "yes"},
            origin=origin,
        )
        self.assertEqual(wrong[0], 400)
        correct = self.request(
            "POST",
            "/api/credentials/status",
            {"action": "disable", "handles": [handle], "confirmation": "DISABLE 1"},
            origin=origin,
        )
        self.assertEqual(correct[0], 200)

    def test_json_content_type_is_required(self) -> None:
        origin = f"http://127.0.0.1:{self.port}"
        status, _headers, _body = self.request("POST", "/api/scan", origin=origin, raw=b"{}")
        self.assertEqual(status, 415)


if __name__ == "__main__":
    unittest.main()
