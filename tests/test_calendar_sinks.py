# -*- coding: utf-8 -*-
"""
Tests for utils.calendar_sinks.

We mock out caldav.DAVClient and exchangelib.Account so the tests are
offline.  What we want to pin down:

  * CalendarEvent.from_termino_slot produces a stable, reproducible UID
  * NoOpCalendarSink.upsert_event is idempotent (same uid twice -> 1 entry)
  * make_calendar_sink('none')   -> NoOp
  * make_calendar_sink('unicloud-caldav') reads the keyring via the
    injected secret_getter
  * make_calendar_sink with no username -> ValueError
  * UniCloudCalDAVSink first-time path calls save_event(); re-upsert
    path calls existing.save()
  * ExchangeEWSSink upsert deletes prior matches before save()
"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.calendar_sinks import (  # noqa: E402
    CalendarEvent,
    NoOpCalendarSink,
    UniCloudCalDAVSink,
    ExchangeEWSSink,
    make_calendar_sink,
)


# --------------------------------------------------------------------
# CalendarEvent
# --------------------------------------------------------------------

class TestCalendarEvent(unittest.TestCase):

    def test_from_termino_slot_yields_stable_uid(self):
        slot = datetime(2026, 6, 1, 10, 0)
        a = CalendarEvent.from_termino_slot(
            "edit-field-flagcollection-und-0", slot, slot, "x", "y"
        )
        b = CalendarEvent.from_termino_slot(
            "edit-field-flagcollection-und-0", slot, slot, "x", "y"
        )
        self.assertEqual(a.uid, b.uid)
        self.assertTrue(a.uid.startswith("termino-"))
        self.assertTrue(a.uid.endswith("@uni-graz.at"))

    def test_different_slots_yield_different_uids(self):
        slot1 = datetime(2026, 6, 1, 10, 0)
        slot2 = datetime(2026, 6, 1, 11, 0)
        a = CalendarEvent.from_termino_slot("X", slot1, slot1, "s", "d")
        b = CalendarEvent.from_termino_slot("X", slot2, slot2, "s", "d")
        self.assertNotEqual(a.uid, b.uid)

    def test_attendees_default_to_empty_list(self):
        slot = datetime(2026, 6, 1, 10, 0)
        ev = CalendarEvent.from_termino_slot("X", slot, slot, "s", "d")
        self.assertEqual(ev.attendees, [])
        # Adding to one event must not bleed into the next (no shared list).
        ev.attendees.append("a@x")
        ev2 = CalendarEvent.from_termino_slot("X", slot, slot, "s", "d")
        self.assertEqual(ev2.attendees, [])


# --------------------------------------------------------------------
# NoOpCalendarSink
# --------------------------------------------------------------------

class TestNoOpSink(unittest.TestCase):

    def _ev(self, uid: str = "u1") -> CalendarEvent:
        return CalendarEvent(
            uid=uid, summary="s", description="d",
            start=datetime(2026, 6, 1, 10, 0),
            end=datetime(2026, 6, 1, 11, 0),
        )

    def test_upsert_records_event(self):
        sink = NoOpCalendarSink()
        sink.upsert_event(self._ev("u1"))
        self.assertEqual(len(sink.events), 1)
        self.assertEqual(sink.events[0].uid, "u1")

    def test_upsert_same_uid_is_idempotent(self):
        sink = NoOpCalendarSink()
        sink.upsert_event(self._ev("u1"))
        sink.upsert_event(self._ev("u1"))
        sink.upsert_event(self._ev("u1"))
        self.assertEqual(len(sink.events), 1)

    def test_upsert_different_uids_accumulate(self):
        sink = NoOpCalendarSink()
        sink.upsert_event(self._ev("u1"))
        sink.upsert_event(self._ev("u2"))
        self.assertEqual({e.uid for e in sink.events}, {"u1", "u2"})

    def test_context_manager(self):
        with NoOpCalendarSink() as sink:
            sink.upsert_event(self._ev("u1"))
        self.assertEqual(len(sink.events), 1)


# --------------------------------------------------------------------
# make_calendar_sink (factory)
# --------------------------------------------------------------------

class TestMakeCalendarSink(unittest.TestCase):

    def test_none_returns_noop(self):
        sink = make_calendar_sink({"calendar_provider": {"type": "none"}})
        self.assertIsInstance(sink, NoOpCalendarSink)

    def test_missing_provider_block_returns_noop(self):
        # No 'calendar_provider' key at all -> NoOp (backward compat)
        sink = make_calendar_sink({})
        self.assertIsInstance(sink, NoOpCalendarSink)

    def test_unknown_type_raises(self):
        with self.assertRaises(ValueError):
            make_calendar_sink(
                {"calendar_provider": {"type": "google-calendar",
                                       "username": "x"}},
                secret_getter=lambda k: "pw",
            )

    def test_caldav_requires_username(self):
        with self.assertRaises(ValueError):
            make_calendar_sink(
                {"calendar_provider": {"type": "unicloud-caldav"}},
                secret_getter=lambda k: "pw",
            )

    def test_caldav_requires_keyring_password(self):
        with self.assertRaises(ValueError):
            make_calendar_sink(
                {"calendar_provider": {"type": "unicloud-caldav",
                                       "username": "u"}},
                secret_getter=lambda k: None,   # nothing in keyring
            )

    def test_caldav_factory_returns_caldav_sink(self):
        sink = make_calendar_sink(
            {"calendar_provider": {"type": "unicloud-caldav",
                                   "username": "u",
                                   "calendar_name": "MyCal"}},
            secret_getter=lambda k: "secret-pw" if k == "unicloud-app-pw" else None,
        )
        self.assertIsInstance(sink, UniCloudCalDAVSink)
        self.assertEqual(sink.username, "u")
        self.assertEqual(sink.calendar_name, "MyCal")

    def test_ews_factory_returns_ews_sink(self):
        # Patch get_uni_login_password where make_calendar_sink looks it up.
        with mock.patch(
            "utils.calendar_sinks.get_uni_login_password",
            return_value="login-pw",
        ):
            sink = make_calendar_sink(
                {"calendar_provider": {"type": "uni-graz-ews",
                                       "username": "me@uni.at"}},
            )
        self.assertIsInstance(sink, ExchangeEWSSink)
        self.assertEqual(sink.username, "me@uni.at")


# --------------------------------------------------------------------
# UniCloudCalDAVSink (with mocked caldav)
# --------------------------------------------------------------------

class TestCalDAVSink(unittest.TestCase):
    """Verify the CalDAV sink talks to caldav correctly without hitting net."""

    def _make_sink_with_mocked_client(self, mock_calendar):
        """Build a sink, then swap in a fake DAVClient returning mock_calendar."""
        # Build a stub DAVClient class: DAVClient(...).principal().calendars()
        # returns [mock_calendar] iff its .name matches.
        mock_principal = mock.MagicMock()
        mock_principal.calendars.return_value = [mock_calendar]
        mock_principal.make_calendar.return_value = mock_calendar
        mock_client_instance = mock.MagicMock()
        mock_client_instance.principal.return_value = mock_principal
        FakeDAV = mock.MagicMock(return_value=mock_client_instance)

        sink = UniCloudCalDAVSink(
            username="u", password="p", calendar_name="Termino"
        )
        # Replace the lazily-imported class with our fake.
        sink._DAVClient = FakeDAV
        return sink, FakeDAV, mock_principal

    def _ev(self, uid: str = "u1") -> CalendarEvent:
        return CalendarEvent(
            uid=uid, summary="Test", description="hi",
            start=datetime(2026, 6, 1, 10, 0),
            end=datetime(2026, 6, 1, 11, 0),
            attendees=["v@uni.at"],
        )

    def test_first_upsert_creates_event_via_save_event(self):
        mock_calendar = mock.MagicMock()
        mock_calendar.name = "Termino"
        # event_by_uid raises -> branch: create.
        mock_calendar.event_by_uid.side_effect = Exception("not found")

        sink, FakeDAV, _ = self._make_sink_with_mocked_client(mock_calendar)
        sink.upsert_event(self._ev("u1"))

        # DAVClient was instantiated with our credentials
        FakeDAV.assert_called_once()
        kwargs = FakeDAV.call_args.kwargs
        self.assertEqual(kwargs["username"], "u")
        self.assertEqual(kwargs["password"], "p")

        # save_event was called once with iCalendar payload
        mock_calendar.save_event.assert_called_once()
        ical_text = mock_calendar.save_event.call_args.args[0]
        self.assertIn("BEGIN:VEVENT", ical_text)
        self.assertIn("UID:u1", ical_text)
        self.assertIn("SUMMARY:Test", ical_text)
        self.assertIn("mailto:v@uni.at", ical_text)

    def test_reupsert_updates_existing_event(self):
        mock_calendar = mock.MagicMock()
        mock_calendar.name = "Termino"
        existing_event = mock.MagicMock()
        mock_calendar.event_by_uid.return_value = existing_event

        sink, _, _ = self._make_sink_with_mocked_client(mock_calendar)
        sink.upsert_event(self._ev("u1"))

        # Existing event's data was overwritten and saved
        existing_event.save.assert_called_once()
        # save_event was NOT called (we updated in place)
        mock_calendar.save_event.assert_not_called()

    def test_calendar_creates_missing(self):
        """If the requested calendar doesn't exist, make_calendar is called."""
        other_cal = mock.MagicMock()
        other_cal.name = "SomeOther"

        # principal.calendars() returns no Termino calendar -> create it
        mock_principal = mock.MagicMock()
        mock_principal.calendars.return_value = [other_cal]
        made = mock.MagicMock()
        made.event_by_uid.side_effect = Exception("not found")
        mock_principal.make_calendar.return_value = made

        mock_client_instance = mock.MagicMock()
        mock_client_instance.principal.return_value = mock_principal
        FakeDAV = mock.MagicMock(return_value=mock_client_instance)

        sink = UniCloudCalDAVSink(
            username="u", password="p", calendar_name="Termino"
        )
        sink._DAVClient = FakeDAV

        sink.upsert_event(self._ev("u1"))
        mock_principal.make_calendar.assert_called_once_with(name="Termino")
        made.save_event.assert_called_once()


# --------------------------------------------------------------------
# ExchangeEWSSink (with mocked exchangelib)
# --------------------------------------------------------------------

class TestEWSSink(unittest.TestCase):

    def _make_sink_with_mocked_account(self):
        """Construct an ExchangeEWSSink with all exchangelib classes mocked."""
        sink = ExchangeEWSSink(username="me@uni.at", login_password="pw")

        fake_account = mock.MagicMock()
        # Stub _ensure_account to return our mock without doing a real connect.
        sink._ensure_account = mock.MagicMock(return_value=fake_account)
        return sink, fake_account

    def _ev(self, uid: str = "u1") -> CalendarEvent:
        return CalendarEvent(
            uid=uid, summary="Test", description="hi",
            start=datetime(2026, 6, 1, 10, 0),
            end=datetime(2026, 6, 1, 11, 0),
            attendees=[],
        )

    def test_upsert_first_run_only_saves(self):
        sink, account = self._make_sink_with_mocked_account()

        # No prior matches in the calendar.
        account.calendar.filter.return_value = []

        # Patch the symbols imported inside upsert_event so we don't need
        # the real exchangelib types.
        with mock.patch.multiple(
            "exchangelib",
            CalendarItem=mock.DEFAULT,
            EWSDateTime=mock.DEFAULT,
            EWSTimeZone=mock.DEFAULT,
            Mailbox=mock.DEFAULT,
        ) as patches:
            saved_item = mock.MagicMock()
            patches["CalendarItem"].return_value = saved_item
            sink.upsert_event(self._ev("u1"))

        # filter() ran with our X-TERMINO-ID marker
        called_kwargs = account.calendar.filter.call_args.kwargs
        self.assertIn("body__contains", called_kwargs)
        self.assertIn("u1", called_kwargs["body__contains"])
        # No prior items -> nothing deleted
        # And save() was called on the new CalendarItem
        saved_item.save.assert_called_once()

    def test_reupsert_deletes_prior_then_saves(self):
        sink, account = self._make_sink_with_mocked_account()

        # Two prior copies should be deleted before save().
        prior_a = mock.MagicMock()
        prior_b = mock.MagicMock()
        account.calendar.filter.return_value = [prior_a, prior_b]

        with mock.patch.multiple(
            "exchangelib",
            CalendarItem=mock.DEFAULT,
            EWSDateTime=mock.DEFAULT,
            EWSTimeZone=mock.DEFAULT,
            Mailbox=mock.DEFAULT,
        ) as patches:
            saved_item = mock.MagicMock()
            patches["CalendarItem"].return_value = saved_item
            sink.upsert_event(self._ev("u1"))

        prior_a.delete.assert_called_once()
        prior_b.delete.assert_called_once()
        saved_item.save.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
