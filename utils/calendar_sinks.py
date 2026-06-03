# -*- coding: utf-8 -*-
"""
utils.calendar_sinks
====================

Provider-agnostic calendar writing for the Termino script.

Why this module exists
----------------------
After the mail-flow refactor (utils.mail_senders), the next stage is to
also drop a calendar entry whenever VLs are notified for tomorrow.  Two
backends are supported:

UniCloudCalDAVSink
    Nextcloud calendar at cloud.uni-graz.at via CalDAV.  Uses the
    'caldav' library and the Nextcloud app password from the keyring
    (key 'unicloud-app-pw').  Idempotent because CalDAV PUT on a fixed
    UID replaces the prior version of the event.

ExchangeEWSSink
    Uni-Graz Outlook calendar via Exchange Web Services.  Reuses the
    same Basic-Auth creds we already use for mail-sending.  Idempotent
    via a custom 'ICalUID'-style property: before saving we search the
    user's calendar for items whose body contains the X-TERMINO-ID
    marker, delete them, then save the new item.

NoOpCalendarSink
    Default sink.  Records events in memory only.  Used both as the
    fallback (no calendar configured) and in unit tests.

Idempotency contract
--------------------
Every CalendarEvent carries a stable 'uid' derived from the Termino
Short ID + slot datetime.  ``upsert_event`` must be safe to call
repeatedly for the same uid: the second call MUST NOT produce a
duplicate event in the user's calendar.  In CalDAV this is free (PUT
on the same URL replaces).  In EWS we have to do find-and-delete first.

Construction
------------
``make_calendar_sink(config_data, secret_getter=get_secret)`` is the
factory.  Reads ``config_data['calendar_provider']``.  If absent or
``{"type": "none"}`` it returns a NoOp sink.  Tests inject a fake
``secret_getter`` to avoid touching the keyring.
"""

from __future__ import annotations

import abc
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, List, Optional

from utils.secrets import get_secret, get_uni_login_password

log = logging.getLogger(__name__)


# --- common event data type ---------------------------------------------

@dataclass
class CalendarEvent:
    """
    Provider-neutral representation of a calendar event.

    ``uid`` is the stable idempotency key.  Two upserts with the same
    uid MUST result in a single event in the user's calendar (the
    second updates the first in place).

    Termino Short IDs look like ``edit-field-flagcollection-und-0``.
    We hash them + datetime to keep the UID short and RFC-5545-safe.
    """
    uid: str
    summary: str
    description: str
    start: datetime
    end: datetime
    location: str = ""
    attendees: List[str] = field(default_factory=list)

    @classmethod
    def from_termino_slot(
        cls,
        short_id: str,
        slot_dt: datetime,
        end_dt: datetime,
        summary: str,
        description: str = "",
        location: str = "",
        attendees: Optional[List[str]] = None,
    ) -> "CalendarEvent":
        """Build a CalendarEvent with a stable UID derived from short_id+date."""
        raw = f"{short_id}|{slot_dt.isoformat()}"
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
        uid = f"termino-{digest}@uni-graz.at"
        return cls(
            uid=uid,
            summary=summary,
            description=description,
            start=slot_dt,
            end=end_dt,
            location=location,
            attendees=list(attendees or []),
        )


# --- abstract base ------------------------------------------------------

class CalendarSink(abc.ABC):
    """Interface every concrete calendar sink must implement."""

    @abc.abstractmethod
    def upsert_event(self, event: CalendarEvent) -> None:
        """Insert or update the event identified by event.uid."""

    @abc.abstractmethod
    def close(self) -> None:
        """Release the underlying connection."""

    def __enter__(self) -> "CalendarSink":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


# --- No-op sink ---------------------------------------------------------

class NoOpCalendarSink(CalendarSink):
    """Sink that doesn't actually write anywhere - records calls in memory.

    Used when the user hasn't configured a calendar provider, and used by
    unit tests to inspect what would have been written.
    """

    def __init__(self) -> None:
        self.events: List[CalendarEvent] = []

    def upsert_event(self, event: CalendarEvent) -> None:
        # Replace any prior entry with the same uid -> mirror real upsert.
        self.events = [e for e in self.events if e.uid != event.uid]
        self.events.append(event)
        log.debug("noop calendar: would upsert %s (%s)", event.summary, event.uid)

    def close(self) -> None:
        pass


# --- UniCloud CalDAV sink -----------------------------------------------

class UniCloudCalDAVSink(CalendarSink):
    """
    Nextcloud (uniCLOUD) calendar via CalDAV.

    The Nextcloud principal URL is
        https://cloud.uni-graz.at/remote.php/dav/principals/users/<user>/
    and the user's calendars hang off
        https://cloud.uni-graz.at/remote.php/dav/calendars/<user>/<cal>/

    We auto-pick or create the calendar named ``calendar_name``.  Events
    are PUT with their stable UID, which means re-runs replace in place.
    """

    DEFAULT_URL = "https://cloud.uni-graz.at/remote.php/dav"

    def __init__(
        self,
        username: str,
        password: str,
        calendar_name: str = "Termino",
        url: str = DEFAULT_URL,
        share_with: Optional[List[str]] = None,
    ) -> None:
        # Lazy import so the NoOp / Exchange path doesn't need caldav installed.
        from caldav import DAVClient
        self._DAVClient = DAVClient

        self.username = username
        self._password = password
        self.calendar_name = calendar_name
        self.url = url
        # Nextcloud principals to auto-share with on calendar creation.
        # Each entry is a Nextcloud username (e.g. "your-username_edu"),
        # NOT an email address.
        self.share_with_principals = list(share_with or [])
        self._client = None
        self._calendar = None
        self._already_shared = False  # track to avoid re-sharing every run

    def _ensure_calendar(self):
        if self._calendar is not None:
            return self._calendar
        log.debug("opening CalDAV connection to %s as %s", self.url, self.username)
        self._client = self._DAVClient(
            url=self.url,
            username=self.username,
            password=self._password,
        )
        principal = self._client.principal()

        # Find the named calendar; create if missing.
        for cal in principal.calendars():
            if cal.name == self.calendar_name:
                self._calendar = cal
                # Existing calendar: re-share once per run if VL-list set.
                # Nextcloud accepts re-shares idempotently.
                if self.share_with_principals and not self._already_shared:
                    self.share_with(self.share_with_principals)
                    self._already_shared = True
                return cal
        log.info("CalDAV: calendar %r not found, creating", self.calendar_name)
        self._calendar = principal.make_calendar(name=self.calendar_name)
        # New calendar -> share immediately so VLs can see it from day 1.
        if self.share_with_principals:
            self.share_with(self.share_with_principals)
            self._already_shared = True
        return self._calendar

    def share_with(self, principals, read_only: bool = False) -> dict:
        """Share the calendar with a list of Nextcloud principals.

        ``principals`` is a list of Nextcloud usernames (NOT email addresses).
        For Uni-Graz Nextcloud, that's the prefix of the @uni-graz.at mail
        (e.g. "your-username_edu" for your-mail@your-uni.at).

        Uses the Nextcloud-specific oc:share WebDAV extension (Sabre/DAV).
        Returns a dict {principal: success_bool, ...}.

        This is best-effort: if Nextcloud refuses the share (wrong principal
        name, calendar not shareable, ...), we log the error but don't
        raise — the calendar still works for the owner.
        """
        cal_obj = self._ensure_calendar()
        cal_url = str(cal_obj.url)
        results = {}
        for p in principals:
            # Nextcloud expects the sharee as principal:principals/users/<user>
            sharee = f"principal:principals/users/{p}"
            access = "<oc:read/>" if read_only else "<oc:read-write/>"
            xml = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<oc:share xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">'
                '<oc:set>'
                f'<d:href>{sharee}</d:href>'
                f'{access}'
                '</oc:set>'
                '</oc:share>'
            )
            try:
                resp = self._client.post(
                    cal_url,
                    body=xml,
                    headers={"Content-Type": "application/xml; charset=utf-8"},
                )
                ok = getattr(resp, "status", 0) in (200, 201, 204, 207)
                results[p] = ok
                if ok:
                    log.info("caldav: shared %s with %s", self.calendar_name, p)
                    print(f"  -> Kalender mit {p} geteilt")
                else:
                    status = getattr(resp, "status", "?")
                    log.warning("caldav: share to %s failed: HTTP %s", p, status)
                    print(f"  ! Sharing mit {p} fehlgeschlagen (HTTP {status})")
            except Exception as e:
                results[p] = False
                log.warning("caldav: share to %s raised: %s", p, e)
                print(f"  ! Sharing mit {p} fehlgeschlagen: {e}")
        return results

    def upsert_event(self, event: CalendarEvent) -> None:
        from icalendar import Calendar as ICal, Event as IEvent

        cal_obj = self._ensure_calendar()

        # Build the iCalendar payload.
        ical = ICal()
        ical.add("prodid", "-//Termino-Sync//uni-graz.at//")
        ical.add("version", "2.0")
        ev = IEvent()
        ev.add("uid", event.uid)
        ev.add("summary", event.summary)
        ev.add("description", event.description)
        ev.add("dtstart", event.start)
        ev.add("dtend", event.end)
        if event.location:
            ev.add("location", event.location)
        for addr in event.attendees:
            ev.add("attendee", f"mailto:{addr}")
        ical.add_component(ev)

        ical_str = ical.to_ical().decode("utf-8")

        # If an event with this UID already exists, update it in place;
        # otherwise save_event() creates a new one.
        try:
            existing = cal_obj.event_by_uid(event.uid)
            existing.data = ical_str
            existing.save()
            log.info("caldav: updated event uid=%s subj=%r", event.uid, event.summary)
        except Exception:
            # event_by_uid raises NotFoundError if no match; create new.
            cal_obj.save_event(ical_str)
            log.info("caldav: created event uid=%s subj=%r", event.uid, event.summary)

    def close(self) -> None:
        # caldav.DAVClient holds a requests.Session; let GC handle it.
        self._client = None
        self._calendar = None


# --- Exchange EWS sink --------------------------------------------------

# Marker string we embed in the event body so we can find+delete prior
# copies when re-upserting.  EWS doesn't expose iCalendar UID for filter
# queries by default, so this body-marker approach is the most portable
# way to be idempotent.
_EWS_UID_MARKER = "X-TERMINO-ID:"


class ExchangeEWSSink(CalendarSink):
    """
    Uni-Graz Outlook calendar via Exchange Web Services.

    Re-uses the same Basic-Auth credentials as the mail sender.  To be
    idempotent, every event body contains a hidden ``X-TERMINO-ID: <uid>``
    line that we search for and delete before saving the new copy.

    Requires VPN to reach webmail.uni-graz.at.
    """

    DEFAULT_EWS_URL = "https://webmail.uni-graz.at/ews/exchange.asmx"

    def __init__(
        self,
        username: str,
        login_password: str,
        ews_url: str = DEFAULT_EWS_URL,
    ) -> None:
        from exchangelib import Account, Credentials, Configuration, DELEGATE
        self._Account = Account
        self._Credentials = Credentials
        self._Configuration = Configuration
        self._DELEGATE = DELEGATE

        self.username = username
        self._password = login_password
        self.ews_url = ews_url
        self._account = None

    def _ensure_account(self):
        if self._account is not None:
            return self._account
        log.debug("opening EWS calendar connection as %s", self.username)
        creds = self._Credentials(username=self.username, password=self._password)
        config = self._Configuration(service_endpoint=self.ews_url, credentials=creds)
        self._account = self._Account(
            primary_smtp_address=self.username,
            config=config,
            autodiscover=False,
            access_type=self._DELEGATE,
        )
        return self._account

    def _find_existing(self, account, uid: str):
        """Yield existing CalendarItems whose body carries our X-TERMINO-ID."""
        marker = f"{_EWS_UID_MARKER} {uid}"
        # body__contains is supported by exchangelib's QuerySet API.
        return account.calendar.filter(body__contains=marker)

    def upsert_event(self, event: CalendarEvent) -> None:
        from exchangelib import CalendarItem, EWSDateTime, EWSTimeZone, Mailbox

        account = self._ensure_account()

        # 1) Delete any prior event with the same UID (idempotency).
        try:
            for prior in self._find_existing(account, event.uid):
                prior.delete()
                log.info("ews-cal: deleted prior copy of uid=%s", event.uid)
        except Exception as e:
            log.warning("ews-cal: idempotency search failed for uid=%s: %s",
                        event.uid, e)

        # 2) Embed the UID marker in the body so the next run can find it.
        body = f"{event.description}\n\n{_EWS_UID_MARKER} {event.uid}\n"

        # 3) Resolve a timezone for the start/end.  Default to Europe/Vienna,
        # which matches the Termino slots.
        tz = EWSTimeZone("Europe/Vienna")

        # Convert naive datetimes to EWSDateTime in the chosen tz.
        def _to_ews(dt):
            return EWSDateTime(
                dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, tzinfo=tz
            )

        item = CalendarItem(
            account=account,
            folder=account.calendar,
            subject=event.summary,
            body=body,
            start=_to_ews(event.start),
            end=_to_ews(event.end),
            location=event.location or None,
            required_attendees=[
                Mailbox(email_address=addr) for addr in event.attendees
            ] or None,
        )
        # save() with no args adds to the calendar; does NOT send invites
        # unless we use send_meeting_invitations.  We keep it silent.
        item.save()
        log.info("ews-cal: saved event uid=%s subj=%r", event.uid, event.summary)

    def close(self) -> None:
        if self._account is not None:
            try:
                self._account.protocol.close()
            except Exception:
                pass
            self._account = None


# --- factory ------------------------------------------------------------

CalendarConfig = dict
SecretGetter = Callable[[str], Optional[str]]


def make_calendar_sink(
    config_data: dict,
    secret_getter: SecretGetter = get_secret,
) -> CalendarSink:
    """
    Build a CalendarSink from config_data['calendar_provider'].

    Expected shapes::

        # No calendar (default)
        {"calendar_provider": {"type": "none"}}

        # uniCLOUD CalDAV
        {"calendar_provider": {
            "type": "unicloud-caldav",
            "username": "your-username_edu",
            "calendar_name": "Termino"
        }}

        # Uni-Graz Outlook (EWS)
        {"calendar_provider": {
            "type": "uni-graz-ews",
            "username": "your-mail@your-uni.at"
        }}

    Returns a NoOpCalendarSink if no provider is configured.  Tests
    inject a fake ``secret_getter`` to avoid the real keyring.
    """
    cfg = config_data.get("calendar_provider") or {"type": "none"}
    ptype = cfg.get("type", "none")

    if ptype == "none":
        return NoOpCalendarSink()

    username = cfg.get("username")
    if not username:
        raise ValueError("calendar_provider.username is required")

    if ptype == "unicloud-caldav":
        pw = secret_getter("unicloud-app-pw")
        if not pw:
            raise ValueError(
                "unicloud-caldav configured but no 'unicloud-app-pw' in keyring. "
                "Run: python -m utils.secrets set unicloud-app-pw"
            )
        return UniCloudCalDAVSink(
            username=username,
            password=pw,
            calendar_name=cfg.get("calendar_name", "Termino"),
            url=cfg.get("url", UniCloudCalDAVSink.DEFAULT_URL),
            share_with=cfg.get("share_with") or [],
        )

    if ptype == "uni-graz-ews":
        pw = get_uni_login_password(username)
        if not pw:
            raise ValueError(
                f"uni-graz-ews calendar configured but no login password in keyring "
                f"for {username!r}. Run: python -m utils.secrets set --email {username} --vpn"
            )
        return ExchangeEWSSink(
            username=username,
            login_password=pw,
            ews_url=cfg.get("ews_url", ExchangeEWSSink.DEFAULT_EWS_URL),
        )

    raise ValueError(
        f"Unknown calendar provider type: {ptype!r}. "
        f"Supported: 'none', 'unicloud-caldav', 'uni-graz-ews'."
    )


# --- workflow integration helper ----------------------------------------

def push_slots_to_calendar(
    *,
    calendar_sink: CalendarSink,
    config_data: dict,
    tomorrow: str,
    name_vl,
    email_vl,
    time_vl,
    tomorrow_time,
    tomorrow_name,
    tomorrow_email,
) -> None:
    """
    Build one CalendarEvent per distinct slot tomorrow and push to ``sink``.

    A 'slot' is one (date, time) pair tomorrow. Multiple VLs may share a
    slot; all of them become attendees on the same event. Participants
    booked into that slot are listed in the description.

    Calendar errors are caught and logged - they never break the daily run.
    Lives here (not in main.py) so it can be unit-tested without booting
    the full Termino workflow.
    """
    from datetime import datetime, timedelta

    study_name = config_data.get("study_name", "Studie")

    # Auto-share the calendar with all VLs (if sink supports it).
    # The sink itself short-circuits if share_with is already set, so this is
    # idempotent across calendar_sink_create + share_with from config.json.
    if hasattr(calendar_sink, "share_with") and email_vl:
        unique_emails = list(dict.fromkeys(email_vl))  # preserve order, dedupe
        principals = [email_to_nextcloud_user(e) for e in unique_emails]
        principals = [p for p in principals if p]
        if principals:
            try:
                calendar_sink.share_with(principals)
            except Exception as e:
                log.warning("calendar: auto-share failed: %s", e)
                print(f"  ! Kalender-Share fehlgeschlagen: {e}")

    # Group VLs by their slot time tomorrow.
    by_slot: dict = {}
    for n, e, t in zip(name_vl, email_vl, time_vl):
        by_slot.setdefault(t, {"vl_names": [], "vl_emails": []})
        by_slot[t]["vl_names"].append(n)
        by_slot[t]["vl_emails"].append(e)

    for slot_time, vl in by_slot.items():
        try:
            start_dt = datetime.strptime(
                f"{tomorrow} {slot_time}", "%d.%m.%Y %H:%M"
            )
        except Exception as e:
            log.warning(
                "calendar: could not parse slot '%s %s': %s",
                tomorrow, slot_time, e,
            )
            continue
        end_dt = start_dt + timedelta(hours=1)

        participants = [
            f"  - {n} <{e}>"
            for n, e, t in zip(tomorrow_name, tomorrow_email, tomorrow_time)
            if t == slot_time
        ]
        description = (
            f"{study_name} - Termin am {tomorrow} um {slot_time}.\n\n"
            f"Versuchsleitung: {', '.join(vl['vl_names'])}\n\n"
            f"Teilnehmer:innen ({len(participants)}):\n"
            + ("\n".join(participants) if participants else "  (keine angemeldet)")
        )

        ev = CalendarEvent.from_termino_slot(
            short_id=f"{study_name}|{slot_time}",
            slot_dt=start_dt,
            end_dt=end_dt,
            summary=f"{study_name} - {slot_time}",
            description=description,
            location=config_data.get("study_location", ""),
            attendees=vl["vl_emails"],
        )
        try:
            calendar_sink.upsert_event(ev)
            log.info(
                "Kalender-Event gesetzt fuer %s (%d VL, %d TN)",
                slot_time, len(vl["vl_emails"]), len(participants),
            )
        except Exception as e:
            log.warning(
                "calendar: upsert failed for slot %s: %s", slot_time, e
            )
            print(f"  ! Kalender-Event fuer {slot_time} fehlgeschlagen: {e}")


# --- wor

def email_to_nextcloud_user(email: str) -> str:
    """Heuristic mapping email -> Nextcloud username for the Uni-Graz setup.

    your-mail@your-uni.at -> your-username_edu
    your-mail@your-uni.at     -> your-username
    foo@example.com                 -> foo  (fallback: local-part)

    The user can override this via an explicit 'nextcloud_user' column
    in the information sheet (handled by callers, not here).
    """
    if not email or "@" not in email:
        return email or ""
    local, _, domain = email.partition("@")
    if domain.endswith("edu.uni-graz.at"):
        return f"{local}_edu"
    if domain.endswith("uni-graz.at"):
        return local
    return local


# --- iMIP invite builder (used for VL mail attachments) -----------------

def build_ics_invite(
    event: CalendarEvent,
    organizer_email: str,
    organizer_name: str = "",
    method: str = "REQUEST",
) -> bytes:
    """Build an RFC-5545 iCalendar VEVENT with METHOD=REQUEST.

    This is the on-the-wire format mail clients (Outlook, Apple Mail,
    Thunderbird, K-9, etc.) understand as a calendar invite.  When the
    recipient opens the mail, the client shows "Accept / Decline" and
    can drop the event straight into the user's own calendar.

    Returns the ICS as UTF-8 bytes ready to attach as
    ``text/calendar; method=REQUEST; charset=UTF-8``.
    """
    from icalendar import Calendar as ICal, Event as IEvent, vCalAddress, vText

    cal = ICal()
    cal.add("prodid", "-//Termino-Sync//uni-graz.at//")
    cal.add("version", "2.0")
    cal.add("method", method)

    ev = IEvent()
    ev.add("uid", event.uid)
    ev.add("summary", event.summary)
    ev.add("description", event.description)
    ev.add("dtstamp", datetime.utcnow())
    ev.add("dtstart", event.start)
    ev.add("dtend", event.end)
    if event.location:
        ev.add("location", event.location)
    ev.add("status", "CONFIRMED")
    ev.add("sequence", 0)

    # Organizer
    org = vCalAddress(f"MAILTO:{organizer_email}")
    if organizer_name:
        org.params["cn"] = vText(organizer_name)
    org.params["role"] = vText("CHAIR")
    ev["organizer"] = org

    # Attendees
    for addr in event.attendees:
        att = vCalAddress(f"MAILTO:{addr}")
        att.params["cutype"] = vText("INDIVIDUAL")
        att.params["role"] = vText("REQ-PARTICIPANT")
        att.params["partstat"] = vText("NEEDS-ACTION")
        att.params["rsvp"] = vText("TRUE")
        att.params["cn"] = vText(addr)
        ev.add("attendee", att, encode=0)

    cal.add_component(ev)
    return cal.to_ical()

