from __future__ import annotations

import unittest

from credential_compass.classifier import classify, quota_summary


class ClassifierTests(unittest.TestCase):
    def test_healthy_quota_is_reduced_to_safe_fields(self) -> None:
        body = {
            "plan_type": "plus",
            "private_field": "must-not-escape",
            "rate_limit": {
                "allowed": True,
                "limit_reached": False,
                "primary_window": {"used_percent": 37.56, "resets_at": "2026-08-14T08:00:00Z"},
            },
        }
        result = classify(200, body)
        self.assertEqual(result["key"], "healthy")
        self.assertEqual(result["quota"]["used_percent"], 37.6)
        self.assertEqual(result["quota"]["plan"], "plus")
        self.assertNotIn("private_field", str(result))

    def test_limited_quota_is_warning(self) -> None:
        body = {"rate_limit": {"allowed": False, "limit_reached": True}}
        result = classify(200, body)
        self.assertEqual(result["key"], "quota_limited")
        self.assertEqual(result["tone"], "warn")

    def test_quota_can_calculate_used_ratio(self) -> None:
        summary = quota_summary(
            {"rate_limit": {"allowed": True, "limit_reached": False, "used": 3, "limit": 4}}
        )
        self.assertEqual(summary["used_percent"], 75.0)

    def test_unknown_plan_is_not_reflected(self) -> None:
        summary = quota_summary({"plan_type": "private-enterprise-name", "rate_limit": {}})
        self.assertEqual(summary["plan"], "")

    def test_timestamp_is_normalized(self) -> None:
        summary = quota_summary({"rate_limit": {"reset_at": 1_800_000_000}})
        self.assertTrue(summary["resets_at"].endswith("Z"))

    def test_401_rules_do_not_return_raw_body(self) -> None:
        result = classify(401, {"error": "token expired", "secret": "private-value"})
        self.assertEqual(result["key"], "expired")
        self.assertNotIn("private-value", str(result))

    def test_generic_401_is_safe(self) -> None:
        result = classify(401, "account john@example.com failed")
        self.assertEqual(result["key"], "unauthorized")
        self.assertNotIn("john", str(result))

    def test_rate_limit_and_network_categories(self) -> None:
        self.assertEqual(classify(429, {})["key"], "rate_limited")
        self.assertEqual(classify(-1, {})["key"], "network")

    def test_invalid_json_returns_unknown_quota(self) -> None:
        self.assertEqual(quota_summary("not-json")["state"], "unknown")


if __name__ == "__main__":
    unittest.main()
