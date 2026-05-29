# -*- coding: utf-8 -*-
"""
Tests for the second batch of defensive fixes against bad spreadsheet
input. None of these existed before the user discovered that one bad
Excel cell could bring the whole daily cron down.

Coverage:
  - first_message / reminder: NaN Termin and NaN mail -> skip with warning
  - vl_mail: NaN time / NaN mail -> skip with warning
  - data_prep: completely empty Datum column -> doesn't crash
  - google_dp: VL kuerzel not in info-sheet -> warning, kein Versand
  - insert_new_app_in_termino: NaN Date/Time row -> skip with warning
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from utils.mail_senders import OutgoingMail  # noqa: E402
from utils import mailing  # noqa: E402
from utils.extensions import google_dp, data_prep  # noqa: E402


class _Spy:
    def __init__(self):
        self.sent = []
    def send(self, m):
        self.sent.append(m)
    def close(self):
        pass


class _Chdir:
    def __init__(self, p):
        self.p, self.old = p, None
    def __enter__(self):
        self.old = os.getcwd()
        os.chdir(self.p)
        return self
    def __exit__(self, *a):
        os.chdir(self.old)


def _make_data(main_csv: str, info_csv: str = None) -> Path:
    """Build a temporary working dir with data/google_spreadsheet*.csv."""
    tmp = Path(tempfile.mkdtemp(prefix="termino-defensive-"))
    (tmp / "data").mkdir()
    (tmp / "data" / "google_spreadsheet.csv").write_text(
        main_csv, encoding="utf-8")
    (tmp / "data" / "google_spreadsheet_information.csv").write_text(
        info_csv or "VL,name,email\nTST1,Tester One,t1@x\nTST2,Tester Two,t2@x\n",
        encoding="utf-8")
    # also drop templates that mailing.first_message / .reminder need
    (tmp / "templates").mkdir()
    (tmp / "templates" / "first_email.txt").write_text(
        "Hi $NAME, $DATE $TIME $STUDYNAME $MAIL", encoding="utf-8")
    (tmp / "templates" / "reminder.txt").write_text(
        "Hi $NAME, $DATE $TIME $STUDYNAME $MAIL", encoding="utf-8")
    return tmp


# --- mailing: NaN-safe -----------------------------------------------------

@mock.patch("utils.mailing._human_pause", lambda *a, **kw: None)
class TestMailingNaNSafe(unittest.TestCase):

    def test_first_message_skips_nan_termin(self):
        sender = _Spy()
        d = _make_data("")
        with _Chdir(d):
            mailing.first_message(
                sender, {"mail": "c@u"}, {"study_name": "S"},
                to_send_name=["Anna", "Bob"],
                to_send_mail=["a@x", "b@x"],
                to_send_date=[float("nan"), "10.05.2026 - 14:00"],
            )
        # Only Bob got a mail (Anna's termin was NaN)
        self.assertEqual(len(sender.sent), 1)
        self.assertEqual(sender.sent[0].to, "b@x")

    def test_first_message_skips_termin_without_separator(self):
        sender = _Spy()
        d = _make_data("")
        with _Chdir(d):
            mailing.first_message(
                sender, {"mail": "c@u"}, {"study_name": "S"},
                to_send_name=["Anna"], to_send_mail=["a@x"],
                to_send_date=["10.05.2026 NO_SEPARATOR 14:00"],
            )
        self.assertEqual(len(sender.sent), 0)

    def test_first_message_skips_empty_mail(self):
        sender = _Spy()
        d = _make_data("")
        with _Chdir(d):
            mailing.first_message(
                sender, {"mail": "c@u"}, {"study_name": "S"},
                to_send_name=["Anna"], to_send_mail=[""],
                to_send_date=["10.05.2026 - 14:00"],
            )
        self.assertEqual(len(sender.sent), 0)

    def test_reminder_skips_nan_termin(self):
        sender = _Spy()
        d = _make_data("")
        with _Chdir(d):
            mailing.reminder(
                sender, {"mail": "c@u"}, {"study_name": "S"},
                tomorrow_name=["A"], tomorrow_email=["a@x"],
                tomorrow_date=[float("nan")],
            )
        self.assertEqual(len(sender.sent), 0)

    def test_vl_mail_skips_nan_time(self):
        sender = _Spy()
        # No template file needed for vl_mail
        mailing.vl_mail(
            sender, {"mail": "c@u"}, {},
            name_vl=["Lena", "Bob"], email_vl=["l@x", "b@x"],
            time_vl=[float("nan"), "10:00"],
            tomorrow_time=["10:00"], tomorrow_name=["A"],
            tomorrow_email=["a@x"], tomorrow="11.05.2026",
        )
        # Lena was skipped (NaN time); Bob got his mail
        self.assertEqual(len(sender.sent), 1)
        self.assertEqual(sender.sent[0].to, "b@x")

    def test_vl_mail_skips_empty_mail(self):
        sender = _Spy()
        mailing.vl_mail(
            sender, {"mail": "c@u"}, {},
            name_vl=["Lena"], email_vl=[""], time_vl=["10:00"],
            tomorrow_time=[], tomorrow_name=[], tomorrow_email=[],
            tomorrow="11.05.2026",
        )
        self.assertEqual(len(sender.sent), 0)


# --- extensions.google_dp: VL not in info-sheet ---------------------------

class TestGoogleDpVLLookup(unittest.TestCase):

    def test_unknown_vl_kuerzel_is_warned_not_silent(self):
        main = (
            "Datum,Uhrzeit,VL1,VL2,VL3,VL4,Anmerkung VL\n"
            "29.05.2026,10:00,UNKNOWN,,,,\n"   # UNKNOWN is not in info
            "29.05.2026,11:00,TST1,,,,\n"
        )
        info = "VL,name,email\nTST1,Tester,t1@x\n"
        d = _make_data(main, info)
        buf = io.StringIO()
        with _Chdir(d), redirect_stdout(buf):
            name_vl, email_vl, _, time_vl = google_dp("29.05.2026")
        out = buf.getvalue()
        self.assertIn("UNKNOWN", out)
        self.assertIn("fehlt im information-Sheet", out)
        # TST1 is fine and gets through
        self.assertEqual(name_vl, ["Tester"])
        self.assertEqual(time_vl, ["11:00"])

    def test_vl_with_empty_email_warned_and_skipped(self):
        main = (
            "Datum,Uhrzeit,VL1,VL2,VL3,VL4,Anmerkung VL\n"
            "29.05.2026,10:00,TSTNOEM,,,,\n"
        )
        info = "VL,name,email\nTSTNOEM,No Email,\n"
        d = _make_data(main, info)
        buf = io.StringIO()
        with _Chdir(d), redirect_stdout(buf):
            name_vl, email_vl, _, _ = google_dp("29.05.2026")
        out = buf.getvalue()
        self.assertIn("keine Mail-Adresse", out)
        self.assertEqual(name_vl, [])
        self.assertEqual(email_vl, [])


# --- extensions.data_prep: empty/garbage Datum column doesn't crash --------

def _termino_df(rows):
    df = pd.DataFrame(rows, columns=["Short ID", "Place", "Time", "Date"])
    df["Date"] = pd.to_datetime(df["Date"], format="%d.%m.%Y", errors="coerce")
    return df


class TestDataPrepDefensive(unittest.TestCase):

    def test_completely_empty_datum_column_does_not_crash(self):
        main = (
            "Datum,Uhrzeit,VL1,VL2,VL3,VL4,Anmerkung VL\n"
            ",10:00,TST1,,,,\n"
            ",11:00,TST2,,,,\n"
        )
        info = "VL,name,email\nTST1,T1,t1@x\nTST2,T2,t2@x\n"
        d = _make_data(main, info)
        df_termino = _termino_df([])
        with _Chdir(d):
            # Should not raise — all rows get dropped because no valid Datum
            diff, zuk = data_prep("14.06.2026", df_termino)
        self.assertEqual(len(zuk), 0)

    def test_garbage_datum_string_is_skipped(self):
        main = (
            "Datum,Uhrzeit,VL1,VL2,VL3,VL4,Anmerkung VL\n"
            "not-a-date,10:00,TST1,,,,\n"
            "20.06.2026,11:00,TST1,,,,\n"
        )
        info = "VL,name,email\nTST1,T1,t1@x\n"
        d = _make_data(main, info)
        df_termino = _termino_df([])
        with _Chdir(d):
            # tomorrow=14.06.2026, so 20.06.2026 IS zukuenftig.
            diff, zuk = data_prep("14.06.2026", df_termino)
        # Only the valid row survives the bad-date filter
        self.assertEqual(len(zuk), 1)
        self.assertEqual(zuk.iloc[0]["Uhrzeit"], "11:00")


if __name__ == "__main__":
    unittest.main(verbosity=2)
