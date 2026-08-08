from __future__ import annotations

import json
import unittest

from credential_compass.cpa_client import (
    MAX_RESPONSE_BYTES,
    PROBE_TARGET,
    ClientError,
    ClientSettings,
    CPAClient,
)


class FakeResponse:
    def __init__(self, status: int, payload: bytes) -> None:
        self.status = status
        self.payload = payload

    def read(self, amount: int) -> bytes:
        return self.payload[:amount]


class FakeConnection:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.request_data = None
        self.closed = False

    def request(self, method, path, body=None, headers=None) -> None:
        self.request_data = {"method": method, "path": path, "body": body, "headers": headers}

    def getresponse(self) -> FakeResponse:
        return self.response

    def close(self) -> None:
        self.closed = True


class ClientTests(unittest.TestCase):
    def client(
        self, payload: object, status: int = 200, max_accounts: int = 20
    ) -> tuple[CPAClient, FakeConnection]:
        raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        connection = FakeConnection(FakeResponse(status, raw))
        client = CPAClient(ClientSettings("https://cpa.example.com", "management-secret", 5, max_accounts))
        client._connection = lambda: connection  # type: ignore[method-assign]
        return client, connection

    def test_auth_file_request_keeps_key_in_headers(self) -> None:
        client, connection = self.client({"files": []})
        self.assertEqual(client.get_auth_files(), [])
        self.assertEqual(connection.request_data["path"], "/v0/management/auth-files")
        self.assertEqual(connection.request_data["headers"]["X-Management-Key"], "management-secret")
        self.assertNotIn("management-secret", str(connection.request_data["body"]))
        self.assertTrue(connection.closed)

    def test_pool_limit_is_enforced(self) -> None:
        client, _connection = self.client({"files": [{}, {}]}, max_accounts=1)
        with self.assertRaisesRegex(ClientError, "exceeds"):
            client.get_auth_files()

    def test_redirects_are_not_followed(self) -> None:
        client, _connection = self.client({}, status=302)
        with self.assertRaisesRegex(ClientError, "redirect"):
            client.get_auth_files()

    def test_invalid_json_is_rejected(self) -> None:
        client, _connection = self.client(b"not-json")
        with self.assertRaisesRegex(ClientError, "invalid JSON"):
            client.get_auth_files()

    def test_oversized_response_is_rejected(self) -> None:
        client, _connection = self.client(b"x" * (MAX_RESPONSE_BYTES + 1))
        with self.assertRaisesRegex(ClientError, "oversized"):
            client.get_auth_files()

    def test_probe_target_is_fixed_and_never_user_supplied(self) -> None:
        client, connection = self.client({"status_code": 200, "body": {"rate_limit": {}}})
        code, _body = client.probe({"auth_index": 7, "id_token": {"chatgpt_account_id": "demo-account"}})
        payload = json.loads(connection.request_data["body"])
        self.assertEqual(code, 200)
        self.assertEqual(payload["url"], PROBE_TARGET)
        self.assertEqual(payload["header"]["Authorization"], "Bearer $TOKEN$")

    def test_missing_auth_index_is_rejected_locally(self) -> None:
        client, connection = self.client({})
        with self.assertRaisesRegex(ClientError, "auth index"):
            client.probe({})
        self.assertIsNone(connection.request_data)

    def test_status_change_sends_only_identifier_and_boolean(self) -> None:
        client, connection = self.client({"status": "ok"})
        self.assertTrue(client.set_disabled("opaque-on-server.json", True))
        payload = json.loads(connection.request_data["body"])
        self.assertEqual(payload, {"name": "opaque-on-server.json", "disabled": True})


if __name__ == "__main__":
    unittest.main()
