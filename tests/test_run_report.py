# -*- coding: utf-8 -*-
"""
Unit tests for utils.run_report - specifically the error_detail / traceback
path added so a crash mail pinpoints the source line instead of only showing
the exception type name.

Regression guard for "Bug 3" from the production status report: a non-
reproducible KeyError produced a [ERRORS] mail that said only the type, with
no stack, so it could not be diagnosed after the fact.
"""

from __future__ import annotations

import os
import sys
import unittest

# Make sure we can import from the package even when the cwd is the tests dir.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.run_report import RunReport


class TestErrorDetail(unittest.TestCase):
    def test_no_error_detail_renders_no_traceback_block(self):
        """Clean run: no <pre>/Traceback section (existing behaviour unchanged)."""
        r = RunReport()
        r.add_phase("Phase 1", status="ok", details="fine")
        out = r.to_html()
        self.assertNotIn("<pre", out)
        self.assertNotIn("Traceback", out)

    def test_error_detail_renders_pre_block(self):
        """With a traceback set, the HTML gains a <pre> Traceback section."""
        r = RunReport()
        r.set_error_detail("Traceback (most recent call last):\n  ...\nKeyError: 'x'")
        out = r.to_html()
        self.assertIn("<pre", out)
        self.assertIn("<h3>Traceback</h3>", out)
        self.assertIn("KeyError", out)

    def test_traceback_is_html_escaped(self):
        """HTML-special chars in the traceback must be escaped, not injected."""
        r = RunReport()
        r.set_error_detail("File \"<module>\", line 1, in <lambda> & more")
        out = r.to_html()
        self.assertIn("&lt;module&gt;", out)
        self.assertIn("&lt;lambda&gt;", out)
        self.assertIn("&amp;", out)
        # The raw, unescaped form must NOT appear.
        self.assertNotIn("<module>", out)

    def test_set_error_detail_none_is_safe(self):
        """set_error_detail(None) normalises to empty, no crash, no <pre>."""
        r = RunReport()
        r.set_error_detail(None)
        self.assertEqual(r.error_detail, "")
        self.assertNotIn("<pre", r.to_html())

    def test_console_summary_shows_cause_line(self):
        """Console summary surfaces the last traceback line as 'Cause'."""
        r = RunReport()
        r.add_error("unerwarteter Fehler: KeyError")
        r.set_error_detail("Traceback (most recent call last):\n"
                           "  File 'main.py', line 42, in run\n"
                           "KeyError: 'buchungsliste_nummer'")
        summary = r.to_console_summary()
        self.assertIn("Cause", summary)
        self.assertIn("KeyError: 'buchungsliste_nummer'", summary)

    def test_console_summary_no_cause_without_detail(self):
        """No 'Cause' line when there is no traceback detail."""
        r = RunReport()
        r.add_error("some error")
        self.assertNotIn("Cause", r.to_console_summary())


if __name__ == "__main__":
    unittest.main()
