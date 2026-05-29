# -*- coding: utf-8 -*-
"""
Tests for the spreadsheet-vs-Termino diff logic in utils.extensions.

What these tests pin down:
  - data_prep() finds the right "spreadsheet entries that exist in
    Termino but have no valid VL"  (differenz_termino)
  - data_prep_2() finds the right "spreadsheet entries that DON'T
    exist in Termino yet"  (differenz_neu / new appointments)
  - get_ids_to_remove() correctly returns the IDs of bookings to be
    removed from Termino (past + tomorrow-but-not-in-current-bookings)
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from utils.extensions import data_prep, data_prep_2
from utils.preperation import get_ids_to_remove


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------

class _DataDirHelper:
    """Context manager: create a temporary ./data with the two CSVs."""

    def __init__(self, main_rows, info_rows):
        self.main = main_rows
        self.info = info_rows
        self.tmp = None
        self.old_cwd = None

    def __enter__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="termino-dp-"))
        (self.tmp / "data").mkdir()
        self.old_cwd = os.getcwd()
        os.chdir(self.tmp)
        # main schedule
        main_csv_lines = ["Datum,Uhrzeit,VL1,VL2,VL3,VL4,Anmerkung VL"]
        for row in self.main:
            main_csv_lines.append(",".join(str(c) for c in row))
        (self.tmp / "data" / "google_spreadsheet.csv").write_text(
            "\n".join(main_csv_lines), encoding="utf-8"
        )
        # info sheet
        info_csv_lines = ["VL,name,email"]
        for row in self.info:
            info_csv_lines.append(",".join(str(c) for c in row))
        (self.tmp / "data" / "google_spreadsheet_information.csv").write_text(
            "\n".join(info_csv_lines), encoding="utf-8"
        )
        return self

    def __exit__(self, *a):
        os.chdir(self.old_cwd)


def _termino_df(rows):
    """Build a df_termino DataFrame with columns Short ID, Place, Time, Date."""
    df = pd.DataFrame(rows, columns=["Short ID", "Place", "Time", "Date"])
    df["Date"] = pd.to_datetime(df["Date"], format="%d.%m.%Y", errors="coerce")
    return df


# --------------------------------------------------------------------
# data_prep
# --------------------------------------------------------------------

class TestDataPrep(unittest.TestCase):

    def test_diff_termino_when_spreadsheet_has_no_vl(self):
        """
        Termino has a slot 2026-06-15 10:00.
        Spreadsheet has the same slot but with empty VL columns -> the
        spreadsheet event is INVALID (no valid VL), so the Termino slot
        appears in differenz_termino (= "no supervisor assigned").
        """
        main = [
            # Tomorrow / future, no VL valid
            ["15.06.2026", "10:00", "", "", "", "", ""],
        ]
        info = [["LEN", "Lena", "len@uni.at"]]
        df_termino = _termino_df([
            ["edit-field-flagcollection-und-0", "0", "10:00", "15.06.2026"],
        ])

        with _DataDirHelper(main, info):
            differenz_termino, zukuenftige = data_prep("14.06.2026", df_termino)

        self.assertEqual(len(differenz_termino), 1)
        self.assertEqual(len(zukuenftige), 0)

    def test_no_diff_when_vl_is_valid_and_event_matches(self):
        main = [
            ["15.06.2026", "10:00", "LEN", "", "", "", ""],
        ]
        info = [["LEN", "Lena", "len@uni.at"]]
        df_termino = _termino_df([
            ["edit-field-flagcollection-und-0", "0", "10:00", "15.06.2026"],
        ])

        with _DataDirHelper(main, info):
            differenz_termino, zukuenftige = data_prep("14.06.2026", df_termino)

        # Slot matches between sheet and Termino, and a valid VL is assigned.
        self.assertEqual(len(differenz_termino), 0)
        # zukuenftige_ereignisse contains the future event with valid VL.
        self.assertEqual(len(zukuenftige), 1)

    def test_termino_event_without_corresponding_sheet_entry(self):
        """
        Termino slot exists, spreadsheet entry for the SAME datetime
        doesn't (sheet has a DIFFERENT date). -> Termino slot lands in
        differenz_termino (= 'orphaned in Termino').
        """
        main = [
            ["20.06.2026", "10:00", "LEN", "", "", "", ""],
        ]
        info = [["LEN", "Lena", "len@uni.at"]]
        df_termino = _termino_df([
            ["edit-field-flagcollection-und-0", "0", "10:00", "15.06.2026"],
        ])

        with _DataDirHelper(main, info):
            differenz_termino, zukuenftige = data_prep("14.06.2026", df_termino)

        self.assertEqual(len(differenz_termino), 1)
        # The 20.06. event is future, so it shows up in zukuenftige
        self.assertEqual(len(zukuenftige), 1)


# --------------------------------------------------------------------
# data_prep_2
# --------------------------------------------------------------------

class TestDataPrep2(unittest.TestCase):

    def test_new_event_inserted_when_sheet_has_one_not_in_termino(self):
        """
        Spreadsheet wants 20.06.2026 09:00, Termino doesn't know about it.
        data_prep_2 must mark exactly one row with Neuer_Termin=True.
        """
        # zukuenftige_ereignisse must look like what data_prep produced
        zuk = pd.DataFrame({
            "Datum":  pd.to_datetime(["20.06.2026"], format="%d.%m.%Y"),
            "Uhrzeit": ["09:00"],
            "VL1": ["LEN"], "VL2": [None], "VL3": [None], "VL4": [None],
            "datetime": pd.to_datetime(["2026-06-20 09:00"]),
        })
        df_termino = _termino_df([])
        df_termino["datetime"] = pd.Series(dtype="datetime64[ns]")

        out = data_prep_2(zuk, df_termino)
        new_rows = out[out["Neuer_Termin"] == True]
        self.assertEqual(len(new_rows), 1)
        self.assertEqual(new_rows.iloc[0]["Date"], "20.06.2026")
        self.assertEqual(new_rows.iloc[0]["Time"], "09:00")

    def test_no_new_event_when_termino_already_has_it(self):
        zuk = pd.DataFrame({
            "Datum":  pd.to_datetime(["20.06.2026"], format="%d.%m.%Y"),
            "Uhrzeit": ["09:00"],
            "VL1": ["LEN"], "VL2": [None], "VL3": [None], "VL4": [None],
            "datetime": pd.to_datetime(["2026-06-20 09:00"]),
        })
        df_termino = _termino_df([
            ["edit-field-flagcollection-und-5", "0", "09:00", "20.06.2026"],
        ])
        df_termino["datetime"] = pd.to_datetime(
            df_termino["Date"].dt.strftime("%d.%m.%Y") + " " + df_termino["Time"],
            format="%d.%m.%Y %H:%M",
        )

        out = data_prep_2(zuk, df_termino)
        new_rows = out[out["Neuer_Termin"] == True]
        self.assertEqual(len(new_rows), 0)


# --------------------------------------------------------------------
# get_ids_to_remove
# --------------------------------------------------------------------

class TestGetIdsToRemove(unittest.TestCase):

    def _today(self):
        return pd.to_datetime("15.06.2026", dayfirst=True)

    def _tomorrow(self):
        return pd.to_datetime("16.06.2026", dayfirst=True)

    def test_past_bookings_are_removed(self):
        df = _termino_df([
            ["edit-field-flagcollection-und-0", "0", "09:00", "10.06.2026"],
            ["edit-field-flagcollection-und-1", "0", "10:00", "12.06.2026"],
        ])
        ids = get_ids_to_remove(df, self._today(), self._tomorrow(), [])
        self.assertEqual(set(ids), {
            "edit-field-flagcollection-und-0-remove-button",
            "edit-field-flagcollection-und-1-remove-button",
        })

    def test_today_bookings_are_removed(self):
        df = _termino_df([
            ["edit-field-flagcollection-und-0", "0", "11:00", "15.06.2026"],
        ])
        ids = get_ids_to_remove(df, self._today(), self._tomorrow(), [])
        self.assertEqual(len(ids), 1)

    def test_tomorrow_booking_kept_if_in_tomorrow_time_list(self):
        df = _termino_df([
            ["edit-field-flagcollection-und-0", "0", "09:00", "16.06.2026"],
        ])
        ids = get_ids_to_remove(df, self._today(), self._tomorrow(), ["09:00"])
        self.assertEqual(ids, [])

    def test_tomorrow_booking_removed_if_not_in_tomorrow_time_list(self):
        df = _termino_df([
            ["edit-field-flagcollection-und-0", "0", "09:00", "16.06.2026"],
        ])
        # tomorrow_time list has 10:00, not 09:00 -> this booking should go
        ids = get_ids_to_remove(df, self._today(), self._tomorrow(), ["10:00"])
        self.assertEqual(ids, ["edit-field-flagcollection-und-0-remove-button"])

    def test_future_booking_beyond_tomorrow_is_kept(self):
        df = _termino_df([
            ["edit-field-flagcollection-und-0", "0", "10:00", "20.06.2026"],
        ])
        ids = get_ids_to_remove(df, self._today(), self._tomorrow(), [])
        self.assertEqual(ids, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
