# -*- coding: utf-8 -*-
"""
Tests for the two xlsx-pipeline robustness fixes:

  1. utils.sheet_providers._serialize_cell handles datetime.time and
     Excel-time-of-day (datetime with year <= 1900) as 'HH:MM' instead of
     '01.01.1900'.

  2. utils.extensions._is_valid_uhrzeit / _normalize_uhrzeit drop rows
     where the Uhrzeit column is empty, NaN, '01.01.1900' garbage, or
     anything else that doesn't look like HH:MM.

  3. utils.extensions.data_prep skips phantom rows (VL set but no time)
     with a warning, instead of crashing.
"""

from __future__ import annotations

import datetime as dt
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from utils.sheet_providers import _serialize_cell  # noqa: E402
from utils.extensions import (  # noqa: E402
    _is_valid_uhrzeit,
    _normalize_uhrzeit,
    data_prep,
)


# ----------------------------------------------------------------------
# _serialize_cell
# ----------------------------------------------------------------------

class TestSerializeCell(unittest.TestCase):

    def test_none_becomes_empty(self):
        self.assertEqual(_serialize_cell(None), "")

    def test_pure_time_becomes_hhmm(self):
        self.assertEqual(_serialize_cell(dt.time(10, 0)), "10:00")
        self.assertEqual(_serialize_cell(dt.time(9, 5)), "09:05")
        self.assertEqual(_serialize_cell(dt.time(15, 30, 45)), "15:30")

    def test_excel_time_of_day_1900_becomes_hhmm(self):
        # Excel stores time-of-day as datetime with 1900-01-01 or 1899-12-30.
        self.assertEqual(
            _serialize_cell(dt.datetime(1900, 1, 1, 10, 0)), "10:00"
        )
        self.assertEqual(
            _serialize_cell(dt.datetime(1899, 12, 30, 9, 30)), "09:30"
        )

    def test_real_date_becomes_ddmmyyyy(self):
        self.assertEqual(_serialize_cell(dt.date(2026, 6, 1)), "01.06.2026")

    def test_real_datetime_with_zero_time_becomes_ddmmyyyy(self):
        # Common in xlsx 'Datum' columns
        self.assertEqual(
            _serialize_cell(dt.datetime(2026, 6, 1, 0, 0)), "01.06.2026"
        )

    def test_real_datetime_with_time_keeps_both(self):
        self.assertEqual(
            _serialize_cell(dt.datetime(2026, 6, 1, 10, 30)),
            "01.06.2026 10:30",
        )

    def test_str_passes_through(self):
        self.assertEqual(_serialize_cell("TST1"), "TST1")
        self.assertEqual(_serialize_cell(""), "")

    def test_int_stringified(self):
        self.assertEqual(_serialize_cell(42), "42")


# ----------------------------------------------------------------------
# _is_valid_uhrzeit / _normalize_uhrzeit
# ----------------------------------------------------------------------

class TestUhrzeitValidation(unittest.TestCase):

    def test_valid_hh_mm(self):
        self.assertTrue(_is_valid_uhrzeit("10:00"))
        self.assertTrue(_is_valid_uhrzeit("09:30"))
        self.assertTrue(_is_valid_uhrzeit("23:59"))

    def test_valid_hh_mm_ss_truncates(self):
        # Collabora often writes 10:00:00 — should still be accepted, and
        # the normaliser should hand back 'HH:MM'.
        self.assertTrue(_is_valid_uhrzeit("10:00:00"))
        self.assertEqual(_normalize_uhrzeit("10:00:00"), "10:00")

    def test_excel_garbage_1900_rejected(self):
        # The 'classic' openpyxl time-of-day artifact
        self.assertFalse(_is_valid_uhrzeit("01.01.1900"))
        self.assertFalse(_is_valid_uhrzeit("1900-01-01 10:00:00"))
        self.assertFalse(_is_valid_uhrzeit("30.12.1899"))

    def test_empty_or_nan_rejected(self):
        self.assertFalse(_is_valid_uhrzeit(None))
        self.assertFalse(_is_valid_uhrzeit(""))
        self.assertFalse(_is_valid_uhrzeit("   "))
        self.assertFalse(_is_valid_uhrzeit(float("nan")))
        self.assertFalse(_is_valid_uhrzeit("nan"))
        self.assertFalse(_is_valid_uhrzeit("NaT"))

    def test_garbage_strings_rejected(self):
        self.assertFalse(_is_valid_uhrzeit("foo"))
        self.assertFalse(_is_valid_uhrzeit("25:99"))
        self.assertFalse(_is_valid_uhrzeit("ten o clock"))

    def test_normalize_invalid_returns_NA(self):
        # downstream code uses pd.isna(...) on this value
        self.assertTrue(pd.isna(_normalize_uhrzeit("")))
        self.assertTrue(pd.isna(_normalize_uhrzeit("01.01.1900")))


# ----------------------------------------------------------------------
# data_prep: end-to-end with a CSV that contains the problematic rows
# ----------------------------------------------------------------------

class _CsvFixture:
    """Build a temporary ./data with the two CSV files data_prep reads."""

    def __init__(self, main_csv: str, info_csv: str = None):
        self.main = main_csv
        self.info = info_csv or "VL,name,email\nTST1,Tester One,t1@x\nTST2,Tester Two,t2@x\n"
        self.tmp = None
        self.old_cwd = None

    def __enter__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="termino-dp-fix-"))
        (self.tmp / "data").mkdir()
        (self.tmp / "data" / "google_spreadsheet.csv").write_text(
            self.main, encoding="utf-8"
        )
        (self.tmp / "data" / "google_spreadsheet_information.csv").write_text(
            self.info, encoding="utf-8"
        )
        self.old_cwd = os.getcwd()
        os.chdir(self.tmp)
        return self

    def __exit__(self, *a):
        os.chdir(self.old_cwd)


def _termino_df(rows):
    df = pd.DataFrame(rows, columns=["Short ID", "Place", "Time", "Date"])
    df["Date"] = pd.to_datetime(df["Date"], format="%d.%m.%Y", errors="coerce")
    return df


class TestDataPrepWithBadXlsxRows(unittest.TestCase):

    def test_phantom_row_with_garbage_uhrzeit_is_skipped(self):
        """
        Reproduces the bug the user hit: row 6 has Uhrzeit '01.01.1900'
        (openpyxl wrote it that way from a time-only cell). Before the fix
        this crashed; after the fix the row is skipped, no exception.
        """
        main_csv = (
            "Datum,Uhrzeit,VL1,VL2,VL3,VL4,Anmerkung VL\n"
            "29.05.2026,01.01.1900,TST1,TST2,,,\n"   # phantom row
            "29.05.2026,10:00,TST1,,,,\n"            # valid row
        )
        df_termino = _termino_df([])
        with _CsvFixture(main_csv):
            differenz, zukuenftig = data_prep("28.05.2026", df_termino)
        # The valid row survives; the garbage one is dropped.
        self.assertEqual(len(zukuenftig), 1)
        self.assertEqual(zukuenftig.iloc[0]["Uhrzeit"], "10:00")

    def test_phantom_row_with_empty_uhrzeit_but_vl_is_skipped(self):
        """
        User typed TST2 in a row that has no Uhrzeit. The row should NOT
        crash data_prep and should NOT appear in zukuenftig.
        """
        main_csv = (
            "Datum,Uhrzeit,VL1,VL2,VL3,VL4,Anmerkung VL\n"
            "29.05.2026,10:00,TST1,,,,\n"            # ok
            ",,, TST2 ,,,\n"                         # phantom: VL set, no time
        )
        df_termino = _termino_df([])
        with _CsvFixture(main_csv):
            differenz, zukuenftig = data_prep("28.05.2026", df_termino)
        self.assertEqual(len(zukuenftig), 1)
        self.assertEqual(zukuenftig.iloc[0]["VL1"], "TST1")

    def test_all_valid_rows_pass_through_unchanged(self):
        main_csv = (
            "Datum,Uhrzeit,VL1,VL2,VL3,VL4,Anmerkung VL\n"
            "29.05.2026,10:00,TST1,,,,\n"
            "29.05.2026,11:00,TST2,,,,\n"
        )
        df_termino = _termino_df([])
        with _CsvFixture(main_csv):
            differenz, zukuenftig = data_prep("28.05.2026", df_termino)
        self.assertEqual(len(zukuenftig), 2)
        self.assertEqual(set(zukuenftig["Uhrzeit"]), {"10:00", "11:00"})

    def test_10_00_00_collabora_format_is_accepted(self):
        """
        If openpyxl ever does manage to write '10:00:00' through (newer
        versions) — that should also be accepted, normalised to '10:00'.
        """
        main_csv = (
            "Datum,Uhrzeit,VL1,VL2,VL3,VL4,Anmerkung VL\n"
            "29.05.2026,10:00:00,TST1,,,,\n"
        )
        df_termino = _termino_df([])
        with _CsvFixture(main_csv):
            differenz, zukuenftig = data_prep("28.05.2026", df_termino)
        self.assertEqual(len(zukuenftig), 1)
        self.assertEqual(zukuenftig.iloc[0]["Uhrzeit"], "10:00")


if __name__ == "__main__":
    unittest.main(verbosity=2)
