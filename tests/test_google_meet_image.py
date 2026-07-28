from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class GoogleMeetImageContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
        cls.config = (REPO_ROOT / "config.yaml").read_text(encoding="utf-8")
        cls.readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    def test_google_meet_plugin_is_enabled(self) -> None:
        self.assertIn("    - google_meet", self.config)

    def test_python_playwright_is_pinned_in_the_hermes_venv(self) -> None:
        self.assertIn(
            '/opt/hermes/.venv/bin/python -m pip install --no-cache-dir "playwright==1.61.0"',
            self.dockerfile,
        )

    def test_matching_chromium_is_installed_at_build_time(self) -> None:
        self.assertIn(
            "/opt/hermes/.venv/bin/python -m playwright install chromium",
            self.dockerfile,
        )

    def test_safe_initial_meet_behavior_is_documented(self) -> None:
        for expected in (
            "explicit `https://meet.google.com/...` URL",
            "listen-only transcription mode",
            "Do not scan calendars",
            "Do not enable realtime speaking mode",
            "Confirm participant consent",
            "Never commit",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, self.readme)


if __name__ == "__main__":
    unittest.main()
