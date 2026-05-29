# -*- coding: utf-8 -*-
"""
utils.mailing - refactored (sender-based)

The four send-* functions (first_message, reminder, vl_mail, termin_missing)
take a MailSender as the first argument. The choice between Yahoo SMTP and
Uni-Graz EWS happens once in main.py via make_sender(). Templates are loaded
relative to the current working directory.

Defensive against bad spreadsheet input: every loop validates Termin /
mail / name and skips with a warning instead of raising, so one bad row
in the xlsx cannot kill the whole daily cron.
"""

from __future__ import annotations

import logging
import random
import sys
import time
from string import Template
from typing import Sequence

import pandas as pd

from utils.mail_senders import MailSender, OutgoingMail

log = logging.getLogger(__name__)


def loading_animation(duration: float) -> None:
    """Console spinner. Kept verbatim from the legacy code."""
    end_time = time.time() + duration
    while time.time() < end_time:
        for char in ("|", "/", "-", "\\"):
            sys.stdout.write(f"\rLade{char}... ")
            sys.stdout.flush()
            time.sleep(0.2)
    sys.stdout.write("\rFertig!     \n")


def readTemplate(filename: str) -> Template:
    """Load a string.Template from disk (cwd-relative)."""
    with open(filename, "r", encoding="utf-8") as f:
        return Template(f.read())


def _human_pause(min_sec: float, max_sec: float, *, animate: bool = False) -> None:
    """Randomised sleep so we don't trigger recipient spam filters.

    Default-silent: no spinner, no console line. Set animate=True for an
    interactive run if you really want the old loading bar back.
    """
    sleep_time = random.uniform(min_sec, max_sec)
    log.debug("human pause: sleeping %.2fs", sleep_time)
    if animate:
        loading_animation(sleep_time)
    else:
        time.sleep(sleep_time)


def _split_termin(termin):
    """Defensive split of 'DD.MM.YYYY - HH:MM'. Returns None on NaN/garbage."""
    if pd.isna(termin):
        return None
    s = str(termin).strip()
    if " - " not in s:
        return None
    parts = s.split(" - ", 1)
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        return None
    return parts[0].strip(), parts[1].strip()


def _safe_title(value) -> str:
    """NaN-safe .title()."""
    if pd.isna(value):
        return ""
    return str(value).title()


def _contact_mail(config_data: dict, env_data: dict) -> str:
    """Public-facing contact address shown to participants.

    Prefers config_data['contact_mail'] (an optional field labs can set
    in config.json), falls back to env_data['mail'] (the sender's own
    address) so existing single-user setups keep working without an
    extra config field.
    """
    return str(
        config_data.get("contact_mail")
        or env_data.get("mail", "")
    )


def _template_vars(config_data: dict, env_data: dict) -> dict:
    """Shared template substitution variables for participant mails.

    Centralised so that adding a new variable requires only one change.
    All template files (templates/first_email.txt, templates/reminder.txt)
    can reference any of these via $NAME.
    """
    return {
        "STUDYNAME": _safe_title(config_data.get("study_name", "")),
        "MAIL": _contact_mail(config_data, env_data),
        "LOCATION": str(config_data.get("study_location", "")),
        "BOOKING_URL": str(config_data.get("booking_url", "")),
    }


def first_message(
    sender: MailSender,
    env_data: dict,
    config_data: dict,
    to_send_name: Sequence[str],
    to_send_mail: Sequence[str],
    to_send_date: Sequence[str],
) -> None:
    """Send the initial confirmation mail to every new booking."""
    tmpl = readTemplate("templates/first_email.txt")

    for name1, mail1, termin1 in zip(to_send_name, to_send_mail, to_send_date):
        split = _split_termin(termin1)
        if split is None:
            log.warning("first_message: skipping %r - Termin %r invalid",
                        name1, termin1)
            print(f"  ! Bestaetigungsmail an {name1!r} uebersprungen "
                  f"(Termin ungueltig: {termin1!r})")
            continue
        date1, time1 = split
        if pd.isna(mail1) or not str(mail1).strip():
            log.warning("first_message: skipping %r - no mail address", name1)
            print(f"  ! Bestaetigungsmail an {name1!r} uebersprungen "
                  f"(keine Mail-Adresse)")
            continue
        body = tmpl.substitute(
            NAME=_safe_title(name1),
            DATE=_safe_title(date1),
            TIME=_safe_title(time1),
            **_template_vars(config_data, env_data),
        )
        subject = (
            f"Teilnahmebestaetigung {config_data['study_name']} am {date1} "
            f"um {time1} Uhr fuer {name1}"
        )

        sender.send(OutgoingMail(
            to=mail1,
            subject=subject,
            body=body,
            from_address=env_data["mail"],
        ))
        log.info("first_message sent to %s for %s %s", mail1, date1, time1)

        _human_pause(2, 10)

    log.info("first_message: %d confirmation mails sent", len(to_send_mail))


def reminder(
    sender: MailSender,
    env_data: dict,
    config_data: dict,
    tomorrow_name: Sequence[str],
    tomorrow_email: Sequence[str],
    tomorrow_date: Sequence[str],
) -> None:
    """Send tomorrow-reminder mails to scheduled participants."""
    tmpl = readTemplate("templates/reminder.txt")

    for name1, mail1, termin1 in zip(tomorrow_name, tomorrow_email, tomorrow_date):
        split = _split_termin(termin1)
        if split is None:
            log.warning("reminder: skipping %r - Termin %r invalid",
                        name1, termin1)
            print(f"  ! Erinnerungsmail an {name1!r} uebersprungen "
                  f"(Termin ungueltig: {termin1!r})")
            continue
        date1, time1 = split
        if pd.isna(mail1) or not str(mail1).strip():
            log.warning("reminder: skipping %r - no mail address", name1)
            print(f"  ! Erinnerungsmail an {name1!r} uebersprungen "
                  f"(keine Mail-Adresse)")
            continue
        body = tmpl.substitute(
            NAME=_safe_title(name1),
            DATE=_safe_title(date1),
            TIME=_safe_title(time1),
            **_template_vars(config_data, env_data),
        )
        subject = (
            f"Terminerinnerung {config_data['study_name']} "
            f"fuer Morgen {date1} um {time1} Uhr"
        )
        log.info("reminder: sending to %s for %s", mail1, time1)

        sender.send(OutgoingMail(
            to=mail1,
            subject=subject,
            body=body,
            from_address=env_data["mail"],
        ))
        _human_pause(8, 15)

    log.info("reminder: %d reminder mails sent for tomorrow",
             len(tomorrow_email))


def vl_mail(
    sender: MailSender,
    env_data: dict,
    config_data: dict,
    name_vl: Sequence[str],
    email_vl: Sequence[str],
    time_vl: Sequence[str],
    tomorrow_time: Sequence[str],
    tomorrow_name: Sequence[str],
    tomorrow_email: Sequence[str],
    tomorrow: str,
) -> None:
    """Inform each Versuchsleiter:in about their slot tomorrow."""
    for name1, mail1, time1 in zip(name_vl, email_vl, time_vl):
        # NaN-Guards: time1 / mail1 / name1 koennen aus einem kaputten Sheet
        # NaN sein. In dem Fall ueberspringen wir den VL mit einer Warning,
        # statt mit einem ValueError den ganzen Daily-Run zu sprengen.
        if pd.isna(time1) or not str(time1).strip():
            log.warning("vl_mail: skipping %r - no slot time", name1)
            print(f"  ! VL-Mail an {name1!r} uebersprungen (Uhrzeit fehlt)")
            continue
        if pd.isna(mail1) or not str(mail1).strip():
            log.warning("vl_mail: skipping %r - no mail address", name1)
            print(f"  ! VL-Mail an {name1!r} uebersprungen (Mail-Adresse fehlt)")
            continue
        name1 = "" if pd.isna(name1) else str(name1)

        anzahl_personen = sum(1 for t1 in tomorrow_time if t1 == time1)
        personen_info = [
            (n1, e1)
            for n1, e1, t1 in zip(tomorrow_name, tomorrow_email, tomorrow_time)
            if t1 == time1
        ]
        personen_details = "\n".join(
            f"    - Name: {name} | E-Mail: {email}"
            for name, email in personen_info
        )

        if anzahl_personen == 0:
            body = (
                f"Hallo {name1},\n\n"
                f"du bist fuer morgen ({tomorrow}) um {time1} fuer eine "
                f"Testung eingetragen!\n\n"
                f"Es sind fuer diesen Termin keine Personen angemeldet.\n\n"
                f"Du musst morgen nicht kommen!\n"
            )
            subject = f"Studientestung morgen {tomorrow} um {time1} Uhr faellt aus!"
        else:
            body = (
                f"Hallo {name1},\n\n"
                f"du bist fuer morgen ({tomorrow}) um {time1} fuer eine "
                f"Testung eingetragen!\n\n"
                f"Es sind fuer diesen Termin {anzahl_personen} Personen "
                f"angemeldet.\n\n"
                f"Infos zu den Personen:\n{personen_details}\n"
            )
            subject = f"Studientestung morgen {tomorrow} um {time1} Uhr"

        # Build a per-slot iMIP invite so the VL gets an Outlook/Apple-Mail
        # "Accept / Decline" prompt and can drop the event into their own
        # calendar. The Termino-Test calendar in uniCLOUD is private to
        # the organizer; the ICS-attachment is the portable per-VL channel.
        ics_bytes = None
        try:
            from utils.calendar_sinks import CalendarEvent, build_ics_invite
            from datetime import datetime as _dt, timedelta as _td
            start_dt = _dt.strptime(f"{tomorrow} {time1}", "%d.%m.%Y %H:%M")
            end_dt = start_dt + _td(hours=1)
            study = config_data.get("study_name", "Studie")
            location = config_data.get("study_location", "")
            ev = CalendarEvent.from_termino_slot(
                short_id=f"{study}|{time1}",
                slot_dt=start_dt,
                end_dt=end_dt,
                summary=f"{study} - {time1}",
                description=body,
                location=location,
                attendees=[mail1],  # only this VL on his/her own invite
            )
            organizer = env_data.get("mail", "")
            ics_bytes = build_ics_invite(
                ev, organizer_email=organizer, organizer_name=study
            )
        except Exception as e:
            log.warning("vl_mail: ICS-invite build failed for %s: %s", name1, e)

        log.debug("vl_mail body for %s:\n%s", name1, body)
        try:
            sender.send(OutgoingMail(
                to=mail1, subject=subject, body=body,
                from_address=env_data["mail"],
                ics_attachment=ics_bytes,
            ))
            log.info("vl_mail sent to %s (%s, %d Probanden)",
                     mail1, time1, anzahl_personen)
        except Exception as e:
            log.error("failed to send VL mail to %s: %s", mail1, e)
            # Errors stay on stdout so the user notices in PowerShell.
            print(f"  ! Fehler beim Senden der VL-Mail an {mail1}: {e}")

        _human_pause(5, 10)

    log.info("vl_mail: %d VL mails sent", len(email_vl))



def termin_missing(
    sender: MailSender,
    env_data: dict,
    config_data: dict,
    differenz_termino: pd.DataFrame,
) -> None:
    """Alert the coordinator about Termino slots without a supervisor."""
    google_url = env_data.get("google_spreadsheet_url", "N/A")
    body = (
        f"Hallo Studienleitung,\n\n"
        f"es wurden Termine in Termino gefunden fuer welche sich im "
        f"Spreadsheet ( {google_url} ) noch keine Versuchsleitung "
        f"eingetragen hat\n\n"
        f"Bitte so schnell es geht dieses Problem beheben!\n\n"
        f"Bei diesen Terminen gibt es noch keine Versuchsleitung:\n"
        f"{differenz_termino['datetime']}\n"
    )

    # Single warning on stdout - full body goes into the alert mail itself.
    print(f"  ! {len(differenz_termino)} Termin(e) in Termino ohne VL - "
          f"Studienleitung wird informiert.")
    log.debug("termin_missing body:\n%s", body)

    sender.send(OutgoingMail(
        to=env_data["mail"],
        subject="ACHTUNG BEI TERMINO GIBT ES TERMINE OHNE VERSUCHSLEITUNG",
        body=body,
        from_address=env_data["mail"],
    ))
    log.info("termin_missing: alerted self about %d slot(s) without VL",
             len(differenz_termino))
