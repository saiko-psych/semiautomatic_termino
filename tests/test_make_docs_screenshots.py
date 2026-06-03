# -*- coding: utf-8 -*-
"""Unit tests for tools/make_docs_screenshots.py.

Browser-free: we drive `capture` with a fake page object and assert the
fail-safe PII guard behaves correctly. Playwright is never imported here.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

# tools/ is not a package; put it on sys.path and import the module directly.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "tools"))

import make_docs_screenshots as mds  # noqa: E402


class BuildBlurCssTests(unittest.TestCase):
    def test_includes_every_selector_and_blur(self):
        css = mds.build_blur_css([".name-col", ".email-col"])
        self.assertIn(".name-col", css)
        self.assertIn(".email-col", css)
        self.assertIn("blur(", css)

    def test_exact_css_shape(self):
        # An exact-shape assertion so malformed output (e.g. an empty selector
        # list producing a rule with no selector) cannot slip through.
        css = mds.build_blur_css([".name-col", ".email-col"])
        self.assertEqual(
            css, f".name-col, .email-col {{ filter: blur({mds.BLUR_RADIUS}) !important; }}"
        )


class CaptureGuardTests(unittest.TestCase):
    def _fake_page(self, count):
        page = MagicMock()
        page.locator.return_value.count.return_value = count
        return page

    def test_aborts_and_does_not_screenshot_when_selector_missing(self):
        spec = mds.ShotSpec(
            name="termino",
            url="https://example/x",
            blur_selectors=[".name-col"],
            out_filename="termino.png",
        )
        page = self._fake_page(0)  # selector matches nothing -> unsafe
        with self.assertRaises(mds.PIIGuardError):
            mds.capture(spec, page, out_dir="/tmp")
        page.screenshot.assert_not_called()

    def test_blurs_then_screenshots_when_selector_present(self):
        spec = mds.ShotSpec(
            name="termino",
            url="https://example/x",
            blur_selectors=[".name-col"],
            out_filename="termino.png",
        )
        page = self._fake_page(1)  # selector found -> safe to blur+shoot
        mds.capture(spec, page, out_dir="/tmp")
        page.add_style_tag.assert_called_once()
        page.screenshot.assert_called_once()

    def test_aborts_when_no_selectors_configured(self):
        # An empty selector list would blur nothing -> must refuse, never shoot.
        spec = mds.ShotSpec(
            name="termino",
            url="https://example/x",
            blur_selectors=[],
            out_filename="termino.png",
        )
        page = self._fake_page(1)
        with self.assertRaises(mds.PIIGuardError):
            mds.capture(spec, page, out_dir="/tmp")
        page.screenshot.assert_not_called()

    def test_aborts_when_one_of_several_selectors_missing(self):
        # Per-selector check: if any configured selector is gone, abort.
        spec = mds.ShotSpec(
            name="termino",
            url="https://example/x",
            blur_selectors=[".present", ".missing"],
            out_filename="termino.png",
        )
        page = MagicMock()

        def _locator(selector):
            loc = MagicMock()
            loc.count.return_value = 1 if selector == ".present" else 0
            return loc

        page.locator.side_effect = _locator
        with self.assertRaises(mds.PIIGuardError):
            mds.capture(spec, page, out_dir="/tmp")
        page.screenshot.assert_not_called()

    def test_returns_expected_out_path(self):
        spec = mds.ShotSpec(
            name="termino",
            url="https://example/x",
            blur_selectors=[".name-col"],
            out_filename="shot.png",
        )
        page = self._fake_page(1)
        out = mds.capture(spec, page, out_dir="/tmp")
        self.assertEqual(out, os.path.join("/tmp", "shot.png"))

    def test_requires_blur_false_captures_without_guard_or_blur(self):
        # Explicit per-shot opt-out for verified PII-free pages (public /
        # synthetic test data): no blur applied, guard skipped, still captured.
        spec = mds.ShotSpec(
            name="public",
            url="https://example/public",
            blur_selectors=[],
            out_filename="public.png",
            requires_blur=False,
        )
        page = self._fake_page(0)  # empty selectors would normally abort
        out = mds.capture(spec, page, out_dir="/tmp")
        page.add_style_tag.assert_not_called()
        page.screenshot.assert_called_once()
        self.assertEqual(out, os.path.join("/tmp", "public.png"))


class BuildShotsTests(unittest.TestCase):
    def test_builds_public_booking_shot_from_config(self):
        shots = mds.build_shots({"booking_url": "https://x/meet/de/b/abc-1"}, {})
        pub = {s.name: s for s in shots}.get("termino-public-booking")
        self.assertIsNotNone(pub)
        self.assertEqual(pub.url, "https://x/meet/de/b/abc-1")
        self.assertTrue(pub.requires_blur)  # blur the public contact email
        self.assertIn('a[href^="mailto:"]', pub.blur_selectors)
        self.assertFalse(pub.use_termino_auth)  # capture anonymously (participant view)

    def test_skips_public_shot_when_no_booking_url(self):
        shots = mds.build_shots({}, {})
        self.assertNotIn("termino-public-booking", [s.name for s in shots])


class TerminoCookieTests(unittest.TestCase):
    """The tool reuses the project's Termino login by translating session.json's
    flat ``kekse`` cookie dict into Playwright's add_cookies() format."""

    def test_translates_kekse_to_playwright_cookies(self):
        cookies = mds.termino_cookies_from_session({"kekse": {"SESSabc": "v1"}})
        self.assertEqual(len(cookies), 1)
        c = cookies[0]
        self.assertEqual(c["name"], "SESSabc")
        self.assertEqual(c["value"], "v1")
        self.assertEqual(c["domain"], ".termino.gv.at")
        self.assertEqual(c["path"], "/")
        self.assertTrue(c["secure"])
        self.assertTrue(c["httpOnly"])

    def test_multiple_cookies(self):
        cookies = mds.termino_cookies_from_session({"kekse": {"a": "1", "b": "2"}})
        self.assertEqual(len(cookies), 2)

    def test_empty_or_missing_kekse_returns_empty(self):
        self.assertEqual(mds.termino_cookies_from_session({"kekse": {}}), [])
        self.assertEqual(mds.termino_cookies_from_session({}), [])
        self.assertEqual(mds.termino_cookies_from_session(None), [])

    def test_load_reads_session_json(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "session.json"), "w", encoding="utf-8") as f:
                json.dump({"kekse": {"SESSxyz": "tok"}}, f)
            cookies = mds.load_termino_cookies(d)
            self.assertEqual(len(cookies), 1)
            self.assertEqual(cookies[0]["name"], "SESSxyz")

    def test_load_missing_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(mds.load_termino_cookies(d), [])


if __name__ == "__main__":
    unittest.main()
