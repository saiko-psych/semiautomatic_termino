# -*- coding: utf-8 -*-
"""
Integration test for main._push_slots_to_calendar.

Verifies that the calendar hook in main.py:
  - Builds exactly one event per (date, time) slot — not per VL
  - Lists all VLs of that slot as attendees
  - Includes participant info in the description
  - Calls upsert_event with stable UIDs (idempotency)
  - Tolerates malformed slot times (logs warning, skips)
  - Survives sink errors (mail flow has already succeeded)
"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.calendar_sinks import (  # noqa: E402
    NoOpCalendarSink, CalendarEvent, push_slots_to_calendar
)


class TestPushSlotsToCalendar(unittest.TestCase):

    def test_one_event_per_slot_with_multiple_vls(self):
        """Two VLs share the 10:00 slot -> one event with both as attendees."""
        sink = NoOpCalendarSink()
        push_slots_to_calendar(
            calendar_sink=sink,
            config_data={"study_name": "Music", "study_location": "Glacis 27"},
            tomorrow="28.05.2026",
            name_vl=["Lena", "Bob"],
            email_vl=["lena@uni.at", "bob@uni.at"],
            time_vl=["10:00", "10:00"],
            tomorrow_time=["10:00"],
            tomorrow_name=["Anna"],
            tomorrow_email=["anna@x.at"],
        )
        self.assertEqual(len(sink.events), 1)
        ev = sink.events[0]
        # Slot summary mentions study + time
        self.assertIn("Music", ev.summary)
        self.assertIn("10:00", ev.summary)
        # Both VLs as attendees
        self.assertEqual(set(ev.attendees), {"lena@uni.at", "bob@uni.at"})
        # Description lists the participant
        self.assertIn("Anna", ev.description)
        self.assertIn("anna@x.at", ev.description)
        # Location is the configured study location
        self.assertEqual(ev.location, "Glacis 27")
        # Start datetime corresponds to tomorrow 10:00
        self.assertEqual(ev.start, datetime(2026, 5, 28, 10, 0))

    def test_distinct_slots_yield_distinct_events(self):
        sink = NoOpCalendarSink()
        push_slots_to_calendar(
            calendar_sink=sink,
            config_data={"study_name": "Music"},
            tomorrow="28.05.2026",
            name_vl=["Lena", "Bob"],
            email_vl=["lena@uni.at", "bob@uni.at"],
            time_vl=["10:00", "15:00"],
            tomorrow_time=["10:00", "15:00"],
            tomorrow_name=["A", "B"],
            tomorrow_email=["a@x", "b@x"],
        )
        self.assertEqual(len(sink.events), 2)
        starts = sorted(e.start for e in sink.events)
        self.assertEqual(starts, [datetime(2026, 5, 28, 10, 0),
                                  datetime(2026, 5, 28, 15, 0)])

    def test_empty_slot_still_creates_event_with_zero_participants(self):
        """VL is on duty but nobody booked -> event exists, body says '0'."""
        sink = NoOpCalendarSink()
        push_slots_to_calendar(
            calendar_sink=sink,
            config_data={"study_name": "Music"},
            tomorrow="28.05.2026",
            name_vl=["Lena"],
            email_vl=["lena@uni.at"],
            time_vl=["10:00"],
            tomorrow_time=[],
            tomorrow_name=[],
            tomorrow_email=[],
        )
        self.assertEqual(len(sink.events), 1)
        self.assertIn("(0)", sink.events[0].description)
        self.assertIn("keine angemeldet", sink.events[0].description)

    def test_idempotent_double_run(self):
        """Running the hook twice with same data must produce 1 event, not 2."""
        sink = NoOpCalendarSink()
        for _ in range(2):
            push_slots_to_calendar(
                calendar_sink=sink,
                config_data={"study_name": "Music"},
                tomorrow="28.05.2026",
                name_vl=["Lena"],
                email_vl=["lena@uni.at"],
                time_vl=["10:00"],
                tomorrow_time=["10:00"],
                tomorrow_name=["A"],
                tomorrow_email=["a@x"],
            )
        # NoOp dedupes by uid
        self.assertEqual(len(sink.events), 1)

    def test_malformed_slot_time_is_skipped_not_raised(self):
        sink = NoOpCalendarSink()
        push_slots_to_calendar(
            calendar_sink=sink,
            config_data={"study_name": "Music"},
            tomorrow="28.05.2026",
            name_vl=["Lena", "Bob"],
            email_vl=["lena@uni.at", "bob@uni.at"],
            time_vl=["10:00", "NOPE"],     # second slot has garbage time
            tomorrow_time=["10:00"],
            tomorrow_name=["A"],
            tomorrow_email=["a@x"],
        )
        # Only the valid slot lands in the calendar
        self.assertEqual(len(sink.events), 1)
        self.assertEqual(sink.events[0].start, datetime(2026, 5, 28, 10, 0))

    def test_sink_error_does_not_abort_remaining_slots(self):
        """First slot's sink raises -> second slot still gets through."""
        class FlakySink(NoOpCalendarSink):
            def __init__(self):
                super().__init__()
                self.attempts = 0
            def upsert_event(self, event):
                self.attempts += 1
                if self.attempts == 1:
                    raise RuntimeError("first slot blew up")
                super().upsert_event(event)

        sink = FlakySink()
        push_slots_to_calendar(
            calendar_sink=sink,
            config_data={"study_name": "Music"},
            tomorrow="28.05.2026",
            name_vl=["Lena", "Bob"],
            email_vl=["lena@uni.at", "bob@uni.at"],
            time_vl=["10:00", "15:00"],
            tomorrow_time=[],
            tomorrow_name=[],
            tomorrow_email=[],
        )
        # Both upserts were attempted, second one succeeded
        self.assertEqual(sink.attempts, 2)
        self.assertEqual(len(sink.events), 1)
        self.assertEqual(sink.events[0].start, datetime(2026, 5, 28, 15, 0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
