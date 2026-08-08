from __future__ import annotations

import re
import unittest
from importlib.resources import files


class StaticContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = files("credential_compass").joinpath("static")
        cls.html = root.joinpath("index.html").read_text(encoding="utf-8")
        cls.js = root.joinpath("app.js").read_text(encoding="utf-8")
        cls.css = root.joinpath("app.css").read_text(encoding="utf-8")

    def test_csp_compatible_assets_have_no_inline_code(self) -> None:
        self.assertNotRegex(self.html, r"<script(?![^>]*\bsrc=)")
        self.assertNotRegex(self.html, r"<style\b")
        self.assertNotRegex(self.html, r"\son[a-z]+=\"")

    def test_four_global_themes_are_present(self) -> None:
        for theme in ("sky", "jade", "sunset", "graphite"):
            self.assertIn(f'data-theme-option="{theme}"', self.html)
            self.assertIn(f'[data-theme="{theme}"]', self.css)
        self.assertIn("--bg: #17191d", self.css)

    def test_favicon_formats_are_linked(self) -> None:
        self.assertIn("/favicon.svg", self.html)
        self.assertIn("/favicon.png", self.html)
        self.assertIn("/favicon.ico", self.html)

    def test_secrets_are_not_persisted_in_browser_storage(self) -> None:
        storage_calls = re.findall(r"(?:localStorage|sessionStorage)\.[a-zA-Z]+\(([^\n]+)", self.js)
        self.assertNotIn("sessionStorage", self.js)
        self.assertEqual(len(storage_calls), 2)
        self.assertTrue(all("THEME_KEY" in call for call in storage_calls))

    def test_no_external_runtime_assets(self) -> None:
        self.assertNotRegex(self.html, r"https?://")
        self.assertNotRegex(self.css, r"url\(\s*['\"]?https?://")

    def test_icon_only_mobile_controls_keep_accessible_names(self) -> None:
        self.assertIn('id="privacyToggle" type="button" aria-label=', self.html)
        self.assertIn('id="themeTrigger" type="button" aria-label=', self.html)
        self.assertIn("setAttribute('aria-label', revealAccounts", self.js)
        self.assertIn("选择主题，当前${meta.label}", self.js)


if __name__ == "__main__":
    unittest.main()
