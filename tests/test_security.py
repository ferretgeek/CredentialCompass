from __future__ import annotations

import unittest

from credential_compass.security import (
    SlidingWindowLimiter,
    clean_text,
    client_peer_key,
    host_allowed,
    mask_email,
    opaque_handle,
    same_origin,
    token_matches,
)


class SecurityTests(unittest.TestCase):
    def test_clean_text_removes_control_characters_and_bounds_length(self) -> None:
        self.assertEqual(clean_text("hello\nworld\x00", 8), "hello wo")

    def test_mask_email_hides_local_and_domain(self) -> None:
        masked = mask_email("person@example.com")
        self.assertEqual(masked, "p•••@e•••.com")
        self.assertNotIn("person", masked)
        self.assertNotIn("example", masked)

    def test_mask_non_email_uses_generic_label(self) -> None:
        self.assertEqual(mask_email("private-identifier"), "account-••••")

    def test_opaque_handle_is_stable_without_revealing_identifier(self) -> None:
        salt = b"s" * 32
        first = opaque_handle(salt, "credential-private@example.com")
        self.assertEqual(first, opaque_handle(salt, "credential-private@example.com"))
        self.assertNotIn("private", first)
        self.assertNotEqual(first, opaque_handle(b"t" * 32, "credential-private@example.com"))

    def test_bearer_auth_is_exact(self) -> None:
        expected = "a" * 32
        self.assertTrue(token_matches(f"Bearer {expected}", expected))
        self.assertFalse(token_matches(expected, expected))
        self.assertFalse(token_matches(f"Bearer {expected}x", expected))

    def test_host_allowlist_ignores_port_but_not_subdomains(self) -> None:
        allowed = frozenset({"localhost", "compass.example.com"})
        self.assertTrue(host_allowed("localhost:8788", allowed))
        self.assertTrue(host_allowed("compass.example.com", allowed))
        self.assertFalse(host_allowed("evil.compass.example.com", allowed))
        self.assertFalse(host_allowed("user@compass.example.com", allowed))

    def test_same_origin_matches_hostname_and_port(self) -> None:
        self.assertTrue(same_origin("https://compass.example.com", "compass.example.com"))
        self.assertTrue(same_origin("http://localhost:8788", "localhost:8788"))
        self.assertTrue(same_origin("https://compass.example.com", "compass.example.com:443"))
        self.assertFalse(same_origin("https://evil.example", "compass.example.com"))
        self.assertFalse(same_origin("http://localhost:9000", "localhost:8788"))
        self.assertFalse(same_origin("https://compass.example.com:8443", "compass.example.com"))
        self.assertFalse(same_origin("file:///tmp/page", "localhost:8788"))

    def test_missing_origin_is_allowed_for_non_browser_clients(self) -> None:
        self.assertTrue(same_origin(None, "localhost:8788"))

    def test_sliding_window_enforces_limit(self) -> None:
        limiter = SlidingWindowLimiter(2, 60)
        self.assertTrue(limiter.allow("client"))
        self.assertTrue(limiter.allow("client"))
        self.assertFalse(limiter.allow("client"))
        self.assertTrue(limiter.allow("other"))

    def test_forwarded_client_is_used_only_behind_a_trusted_proxy(self) -> None:
        trusted = frozenset({"127.0.0.1", "192.0.2.10"})
        self.assertEqual(client_peer_key("127.0.0.1", "198.51.100.7", trusted), "198.51.100.7")
        self.assertEqual(
            client_peer_key("127.0.0.1", "198.51.100.7, 192.0.2.10", trusted),
            "198.51.100.7",
        )
        self.assertEqual(client_peer_key("198.51.100.8", "198.51.100.7", trusted), "198.51.100.8")
        self.assertEqual(client_peer_key("127.0.0.1", "not-an-ip", trusted), "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
