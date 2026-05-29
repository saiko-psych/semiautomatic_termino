# -*- coding: utf-8 -*-
"""
Unit tests for utils.mailing (single-user, sender-based).

Verifies:
- Right OutgoingMail objects are passed to the sender
- Templates loaded from ./templates/
- Empty input lists don't crash
- vl_mail handles 0-participant slots with cancellation subject
- termin_missing builds correct alert body
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from utils.mail_senders import OutgoingMail
from utils import mailing


class _SenderSpy:
    def __init__(self):
        self.sent: list[OutgoingMail] = []
    def send(self, mail: OutgoingMail) -> None:
        self.sent.append(mail)
    def close(self) -> None: pass


class _Chdir:
    """Context manager: chdir into a dir, restore on exit."""
    def __init__(self, path): self.path, self.old = path, None
    def __enter__(self):
        self.old = os.getcwd(); os.chdir(self.path); return self.path
    def __exit__(self, *a):
        os.chdir(self.old)


def _make_template_dir(first_tmpl: str, reminder_tmpl: str) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="termino-test-"))
    (tmp / "templates").mkdir()
    (tmp / "templates" / "first_email.txt").write_text(first_tmpl, encoding="utf-8")
    (tmp / "templates" / "reminder.txt").write_text(reminder_tmpl, encoding="utf-8")
    return tmp


@patch("utils.mailing._human_pause", lambda *a, **kw: None)
class TestFirstMessage(unittest.TestCase):

    def test_one_participant(self):
        sender = _SenderSpy()
        d = _make_template_dir(
            "Hi $NAME, $DATE $TIME $STUDYNAME $MAIL",
            "(unused)",
        )
        with _Chdir(d):
            mailing.first_message(
                sender,
                env_data={"mail": "coord@uni.at"},
                config_data={"study_name": "music"},
                to_send_name=["anna"],
                to_send_mail=["anna@x.at"],
                to_send_date=["10.05.2026 - 14:00"],
            )
        self.assertEqual(len(sender.sent), 1)
        m = sender.sent[0]
        self.assertEqual(m.to, "anna@x.at")
        self.assertEqual(m.from_address, "coord@uni.at")
        self.assertIn("Hi Anna", m.body)
        self.assertIn("10.05.2026", m.body)
        self.assertIn("14:00", m.body)
        self.assertIn("Music", m.body)
        self.assertIn("Teilnahmebestaetigung", m.subject)

    def test_empty_lists_send_nothing(self):
        sender = _SenderSpy()
        d = _make_template_dir("hi $NAME", "x")
        with _Chdir(d):
            mailing.first_message(
                sender, {"mail": "x@y"}, {"study_name": "s"},
                [], [], [],
            )
        self.assertEqual(sender.sent, [])

    def test_multiple_participants_keep_order(self):
        sender = _SenderSpy()
        d = _make_template_dir("hi $NAME $DATE $TIME $STUDYNAME $MAIL", "x")
        with _Chdir(d):
            mailing.first_message(
                sender, {"mail": "c@u"}, {"study_name": "s"},
                ["a", "b", "c"],
                ["a@x", "b@x", "c@x"],
                ["01.01.2026 - 09:00", "01.01.2026 - 10:00", "01.01.2026 - 11:00"],
            )
        self.assertEqual([m.to for m in sender.sent], ["a@x", "b@x", "c@x"])


@patch("utils.mailing._human_pause", lambda *a, **kw: None)
class TestReminder(unittest.TestCase):
    def test_subject_is_german(self):
        sender = _SenderSpy()
        d = _make_template_dir("x", "Hi $NAME $DATE $TIME $STUDYNAME $MAIL")
        with _Chdir(d):
            mailing.reminder(
                sender, {"mail": "c@u"}, {"study_name": "music-study"},
                ["anna"], ["anna@x"], ["10.05.2026 - 14:00"],
            )
        m = sender.sent[0]
        self.assertIn("Terminerinnerung", m.subject)
        self.assertIn("music-study", m.subject.lower())
        self.assertIn("14:00", m.subject)


@patch("utils.mailing._human_pause", lambda *a, **kw: None)
class TestVlMail(unittest.TestCase):
    def test_slot_with_no_participants_uses_cancellation_subject(self):
        sender = _SenderSpy()
        mailing.vl_mail(
            sender, {"mail": "c@u"}, {},
            name_vl=["maria"], email_vl=["maria@vl.at"], time_vl=["14:00"],
            tomorrow_time=["10:00"],
            tomorrow_name=["anna"], tomorrow_email=["anna@x"],
            tomorrow="11.05.2026",
        )
        self.assertEqual(len(sender.sent), 1)
        m = sender.sent[0]
        self.assertIn("faellt aus", m.subject)
        self.assertIn("Du musst morgen nicht kommen", m.body)

    def test_slot_with_participants_lists_them(self):
        sender = _SenderSpy()
        mailing.vl_mail(
            sender, {"mail": "c@u"}, {},
            ["maria"], ["maria@vl.at"], ["14:00"],
            tomorrow_time=["14:00", "14:00", "10:00"],
            tomorrow_name=["anna", "bob", "carl"],
            tomorrow_email=["anna@x", "bob@x", "carl@x"],
            tomorrow="11.05.2026",
        )
        m = sender.sent[0]
        self.assertIn("2 Personen", m.body)
        self.assertIn("anna@x", m.body)
        self.assertIn("bob@x", m.body)
        self.assertNotIn("carl@x", m.body)
        self.assertNotIn("faellt aus", m.subject)

    def test_send_failure_does_not_abort_batch(self):
        class FlakySender:
            def __init__(self): self.calls = 0; self.sent = []
            def send(self, mail):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("simulated network error")
                self.sent.append(mail)
            def close(self): pass

        sender = FlakySender()
        mailing.vl_mail(
            sender, {"mail": "c@u"}, {},
            ["maria", "tom"], ["maria@x", "tom@x"], ["14:00", "10:00"],
            tomorrow_time=["14:00"], tomorrow_name=["anna"],
            tomorrow_email=["anna@x"], tomorrow="11.05.2026",
        )
        self.assertEqual(sender.calls, 2)
        self.assertEqual(len(sender.sent), 1)
        self.assertEqual(sender.sent[0].to, "tom@x")


class TestTerminMissing(unittest.TestCase):
    def test_alert_contains_spreadsheet_url_and_appointments(self):
        sender = _SenderSpy()
        df = pd.DataFrame({
            "datetime": ["2026-05-10 14:00", "2026-05-10 15:00"],
            "Place": [1, 2],
        })
        env_data = {"mail": "coord@uni.at",
                    "google_spreadsheet_url": "https://sheets/abc"}
        mailing.termin_missing(sender, env_data, {}, df)

        self.assertEqual(len(sender.sent), 1)
        m = sender.sent[0]
        self.assertEqual(m.to, "coord@uni.at")
        self.assertEqual(m.from_address, "coord@uni.at")
        self.assertIn("ACHTUNG", m.subject)
        self.assertIn("https://sheets/abc", m.body)
        self.assertIn("2026-05-10 14:00", m.body)

    def test_url_falls_back_when_missing(self):
        sender = _SenderSpy()
        df = pd.DataFrame({"datetime": ["x"], "Place": [1]})
        mailing.termin_missing(sender, {"mail": "c@u"}, {}, df)
        self.assertIn("N/A", sender.sent[0].body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
