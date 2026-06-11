# -*- coding: utf-8 -*-
"""
tests.test_data_prep_strict_string
==================================

Regression guard for the pandas 2.2+ future-string-dtype mode.

In pandas 2.3+ with ``pd.options.future.infer_string = True`` (which is
how uv-managed venvs sometimes end up), string columns get a strict
``str`` dtype. ``df.loc[i, 'Place'] = i`` (int assignment to a str
column) raises ``TypeError`` instead of silently up-casting.

This test re-runs the data_prep / data_prep_2 path under the strict
flag so we catch this regression at unit-test time instead of when a
fresh uv-venv hits production.
"""

import unittest
import importlib
import sys

import pandas as pd


class TestDataPrepUnderStrictStringDtype(unittest.TestCase):
    """Run a representative slice of the data_prep tests with strict dtype."""

    def setUp(self):
        # Flip the strict flag for the duration of the test, then restore.
        self._prev = pd.options.future.infer_string
        pd.options.future.infer_string = True

        # On pandas <2.3, the strict string mode requires pyarrow.
        # If pyarrow isn't installed (common on Windows / fresh clones
        # without 'uv sync'), skip rather than crash with ImportError.
        try:
            _ = pd.DataFrame({"x": ["probe"]})
        except ImportError as exc:
            pd.options.future.infer_string = self._prev
            self.skipTest(
                f"strict-string-dtype mode requires pyarrow on this pandas: {exc}"
            )

        # Reload utils.extensions so it picks up the new option *if* it
        # cached anything (it doesn't, but safer).
        if "utils.extensions" in sys.modules:
            importlib.reload(sys.modules["utils.extensions"])

    def tearDown(self):
        pd.options.future.infer_string = self._prev
        if "utils.extensions" in sys.modules:
            importlib.reload(sys.modules["utils.extensions"])

    def test_data_prep_2_with_str_dtype_termino(self):
        """data_prep_2 must not crash when df_termino has str-dtype columns."""
        from utils.extensions import data_prep_2

        zuk = pd.DataFrame({
            "Datum":  pd.to_datetime(["20.06.2026"], format="%d.%m.%Y"),
            "Uhrzeit": ["09:00"],
            "VL1": ["LEN"], "VL2": [None], "VL3": [None], "VL4": [None],
            "datetime": pd.to_datetime(["2026-06-20 09:00"]),
        })
        df_termino = pd.DataFrame(
            [["edit-field-flagcollection-und-5", "0", "09:00", "20.06.2026"]],
            columns=["Short ID", "Place", "Time", "Date"],
        )
        df_termino["Date"] = pd.to_datetime(
            df_termino["Date"], format="%d.%m.%Y", errors="coerce",
        )
        df_termino["datetime"] = pd.to_datetime(
            df_termino["Date"].dt.strftime("%d.%m.%Y") + " " + df_termino["Time"],
            format="%d.%m.%Y %H:%M",
        )

        # Sanity: confirm the strict dtype IS in effect. The repr differs by
        # pandas version - 2.2.x with pyarrow reports "string", 2.3+ reports
        # "str" - but both are the strict string mode this test guards.
        self.assertIn(str(df_termino["Place"].dtype), ("str", "string"),
                      "future.infer_string did not kick in")

        # The point: this used to raise TypeError.
        out = data_prep_2(zuk, df_termino)

        # Termino already had the slot - no new event should be flagged.
        new_rows = out[out["Neuer_Termin"] == True]
        self.assertEqual(len(new_rows), 0)

        # And Place should now be a clean int column (not str).
        self.assertTrue(
            pd.api.types.is_integer_dtype(out["Place"]),
            f"Place should be int after data_prep_2, got {out['Place'].dtype}",
        )

    def test_data_prep_2_appends_new_event_under_strict(self):
        """The 'new event needs Short ID' branch also works under strict dtype."""
        from utils.extensions import data_prep_2

        zuk = pd.DataFrame({
            "Datum":  pd.to_datetime(["20.06.2026"], format="%d.%m.%Y"),
            "Uhrzeit": ["09:00"],
            "VL1": ["LEN"], "VL2": [None], "VL3": [None], "VL4": [None],
            "datetime": pd.to_datetime(["2026-06-20 09:00"]),
        })
        # Termino has a DIFFERENT slot - so zuk's slot is new.
        df_termino = pd.DataFrame(
            [["edit-field-flagcollection-und-2", "0", "10:00", "15.06.2026"]],
            columns=["Short ID", "Place", "Time", "Date"],
        )
        df_termino["Date"] = pd.to_datetime(
            df_termino["Date"], format="%d.%m.%Y", errors="coerce",
        )
        df_termino["datetime"] = pd.to_datetime(
            df_termino["Date"].dt.strftime("%d.%m.%Y") + " " + df_termino["Time"],
            format="%d.%m.%Y %H:%M",
        )

        out = data_prep_2(zuk, df_termino)
        new_rows = out[out["Neuer_Termin"] == True]
        self.assertEqual(len(new_rows), 1)
        # The new row should have a freshly-generated Short ID.
        self.assertTrue(
            new_rows.iloc[0]["Short ID"].startswith("edit-field-flagcollection-und-"),
            f"Bad Short ID: {new_rows.iloc[0]['Short ID']!r}",
        )


if __name__ == "__main__":
    unittest.main()
