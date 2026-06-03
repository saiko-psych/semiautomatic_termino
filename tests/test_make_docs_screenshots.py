# -*- coding: utf-8 -*-
"""Unit tests for tools/make_docs_screenshots.py.

Browser-free: we drive `capture` with a fake page object and assert the
fail-safe PII guard behaves correctly. Playwright is never imported here.
"""
from __future__ import annotations

import os
import sys
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


if __name__ == "__main__":
    unittest.main()
