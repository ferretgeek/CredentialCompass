from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from credential_compass.config import AppConfig, ConfigError, _normalized_base_url


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()

    def tearDown(self) -> None:
        self.environment.stop()

    def test_demo_generates_ephemeral_loopback_token(self) -> None:
        config = AppConfig.from_env(demo_override=True)
        self.assertTrue(config.generated_access_token)
        self.assertGreaterEqual(len(config.access_token), 32)
        self.assertIn("127.0.0.1", config.allowed_hosts)

    def test_short_access_token_is_rejected(self) -> None:
        os.environ["COMPASS_ACCESS_TOKEN"] = "short"
        with self.assertRaisesRegex(ConfigError, "32"):
            AppConfig.from_env(demo_override=True)

    def test_non_loopback_requires_access_token(self) -> None:
        os.environ["COMPASS_BIND_HOST"] = "0.0.0.0"
        os.environ["COMPASS_ALLOWED_HOSTS"] = "compass.example.com"
        with self.assertRaisesRegex(ConfigError, "ACCESS_TOKEN"):
            AppConfig.from_env(demo_override=True)

    def test_non_loopback_requires_exact_allowed_host(self) -> None:
        os.environ.update(
            {
                "COMPASS_BIND_HOST": "0.0.0.0",
                "COMPASS_ACCESS_TOKEN": "x" * 32,
                "COMPASS_ALLOWED_HOSTS": "*",
            }
        )
        with self.assertRaisesRegex(ConfigError, "exact"):
            AppConfig.from_env(demo_override=True)

    def test_real_mode_requires_management_key(self) -> None:
        os.environ.update({"COMPASS_ACCESS_TOKEN": "x" * 32, "COMPASS_CPA_URL": "https://cpa.example.com"})
        with (
            patch(
                "credential_compass.config._resolved_addresses",
                return_value={__import__("ipaddress").ip_address("203.0.113.4")},
            ),
            self.assertRaisesRegex(ConfigError, "CPA_KEY"),
        ):
            AppConfig.from_env(demo_override=False)

    def test_url_rejects_embedded_credentials_and_paths(self) -> None:
        userinfo_fixture = ":".join(("name", "synthetic-credential"))
        with self.assertRaises(ConfigError):
            _normalized_base_url(f"https://{userinfo_fixture}@example.com", False)
        with self.assertRaises(ConfigError):
            _normalized_base_url("https://example.com/private/path", False)

    def test_plain_http_requires_loopback_by_default(self) -> None:
        address = __import__("ipaddress").ip_address("192.0.2.8")
        with (
            patch("credential_compass.config._resolved_addresses", return_value={address}),
            self.assertRaisesRegex(ConfigError, "Plain HTTP"),
        ):
            _normalized_base_url("http://cpa.example.com", False)

    def test_https_normalizes_host_and_default_port(self) -> None:
        address = __import__("ipaddress").ip_address("203.0.113.8")
        with patch("credential_compass.config._resolved_addresses", return_value={address}):
            url, host, addresses = _normalized_base_url("https://CPA.Example.com/", False)
        self.assertEqual(url, "https://cpa.example.com")
        self.assertEqual(host, "cpa.example.com")
        self.assertEqual(addresses, frozenset({"203.0.113.8"}))

    def test_demo_allows_reversible_status_controls(self) -> None:
        os.environ["COMPASS_ACCESS_TOKEN"] = "x" * 32
        config = AppConfig.from_env(demo_override=True)
        self.assertTrue(config.allow_status_changes)
        self.assertTrue(config.live_probe)

    def test_trusted_proxies_must_be_ip_literals(self) -> None:
        os.environ["COMPASS_TRUSTED_PROXY_IPS"] = "proxy.example.com"
        with self.assertRaisesRegex(ConfigError, "IP literals"):
            AppConfig.from_env(demo_override=True)


if __name__ == "__main__":
    unittest.main()
