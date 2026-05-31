import os
import sys
import time
from pathlib import Path
from typing import Tuple, Optional

os.chdir(Path(__file__).parent)

from status import StatusManager
from utils.styles import TERMINO_SCRIPT_ASCI, EXTENSIONS
from utils.preperation import (
    load_config,
    load_env_data,
    config_text,
    load_session,
    session_json,
    booking_list_preperation,
    date_creation,
    tomorrow_today_data,
    get_ids_to_remove
)
from utils.web_interaction import (
    termino_antibot_key,
    session,
    termino_login,
    bookinglist_url,
    get_buchungsliste_nummer,
    termino_csv_download,
    termino_bookings,
    deleting_bookings,
    insert_new_app_in_termino
)
from utils.mailing import first_message, reminder, vl_mail, termin_missing
from utils.mail_senders import make_sender, MailSender
from utils.calendar_sinks import (
    make_calendar_sink,
    push_slots_to_calendar,
    CalendarSink,
    CalendarEvent,
    NoOpCalendarSink,
)
from utils.extensions import download_g_s, google_dp, data_prep, data_prep_2
from utils.run_report import RunReport
from utils.vpn import warn_if_not_connected


def _resolve_mail_provider(config_data: dict, env_data: dict) -> dict:
    """
    Build the provider_config dict for make_sender().

    Reads ``config_data['mail_provider']`` if present, otherwise falls back
    to the legacy Yahoo SMTP setup using ``env_data['mail']`` as the
    username. This keeps existing installations working without having to
    edit config.json on day one.
    """
    if "mail_provider" in config_data:
        cfg = dict(config_data["mail_provider"])
        # username can be the same as the From-address; allow shorthand
        cfg.setdefault("username", env_data.get("mail", ""))
        return cfg
    # Legacy default: Yahoo SMTP with the address in env_data['mail']
    return {
        "type": "yahoo-smtp",
        "username": env_data["mail"],
    }


class TerminoSession:
    """
    Manages the Termino session including login, antibot key, and cookies.
    """

    def __init__(self, env_data: dict, config_data: dict):
        self.env_data = env_data
        self.config_data = config_data
        self.session_id = None
        self.antibot_key = None
        self.cookies = None
        self.logged_url = None
        self.buchungsliste_nummer = None
        self.actual_booking_list_csv = None

    def initialize(self) -> None:
        """
        Initialize session and login to Termino.
        Attempts to load existing session first, creates new one if needed.
        """
        self.session_id = session()

        # Try to load existing session data
        try:
            (self.antibot_key,
             self.cookies,
             self.logged_url,
             self.buchungsliste_nummer,
             self.actual_booking_list_csv) = load_session()
        except Exception:
            self.antibot_key = None
            self.cookies = None
            self.logged_url = None
            self.buchungsliste_nummer = None
            self.actual_booking_list_csv = None

        # Attempt login with existing credentials
        self._perform_login()

    def _perform_login(self) -> None:
        """
        Perform login to Termino. If login fails, get new antibot key and retry.
        """
        if self.antibot_key:
            self.logged_url, self.cookies = termino_login(
                self.env_data,
                self.antibot_key,
                self.session_id
            )
        else:
            self.logged_url = "error"

        # If login failed, get new antibot key and retry
        if self.logged_url == "error":
            print("Login failed, fetching new antibot key...")
            self.session_id = session()
            self.antibot_key = termino_antibot_key()
            self.logged_url, self.cookies = termino_login(
                self.env_data,
                self.antibot_key,
                self.session_id
            )

        # Update booking list information
        self._update_booking_list()

        # Save session data
        self._save_session()

    def _update_booking_list(self) -> None:
        """
        Update booking list number and download current CSV.
        """
        booking_url = bookinglist_url(self.session_id, self.logged_url)
        self.buchungsliste_nummer = get_buchungsliste_nummer(
            self.session_id,
            booking_url,
            self.config_data
        )
        self.actual_booking_list_csv = termino_csv_download(
            self.session_id,
            self.config_data,
            self.buchungsliste_nummer
        )

    def _save_session(self) -> None:
        """
        Save current session data to session.json.
        """
        session_json(
            self.antibot_key,
            self.cookies,
            self.logged_url,
            self.buchungsliste_nummer,
            self.actual_booking_list_csv
        )


class TaskRunner:
    """
    Manages task execution with automatic status tracking.
    """

    def __init__(self, status_manager: StatusManager):
        self.status = status_manager

    def run_task(
        self,
        task_name: str,
        task_func: callable,
        *args,
        skip_message: str = None,
        **kwargs
    ) -> Optional[any]:
        """
        Run a task with automatic status tracking.

        Args:
            task_name: Unique identifier for the task
            task_func: Function to execute
            skip_message: Message to display if task is already done
            *args, **kwargs: Arguments to pass to task_func

        Returns:
            Result of task_func or None if already completed
        """
        if self.status.is_done_today(task_name):
            if skip_message:
                print(f"\nOK {skip_message}")
            return None

        try:
            result = task_func(*args, **kwargs)
            self.status.mark_done(task_name)
            return result
        except Exception as e:
            error_msg = str(e)
            print(f"\nX ERROR in {task_name}: {error_msg}")
            self.status.mark_failed(task_name, error_msg)
            raise


def send_emails_task(
    sender: MailSender,
    env_data: dict,
    config_data: dict,
    actual_booking_list_csv: str,
    tomorrow: str,
    today: str
) -> Tuple:
    """
    Task: Process booking list and send confirmation and reminder emails.

    The mail provider (Yahoo SMTP, Uni-Graz EWS, ...) is determined by the
    ``sender`` passed in - see ``_resolve_mail_provider`` and ``make_sender``.
    """
    (date_prob, name_prob, email_prob,
     date_first_mail_sended, name_first_mail_sended, email_first_mail_sended,
     to_send_name, to_send_mail, to_send_date) = booking_list_preperation(
         actual_booking_list_csv,
         config_data
     )

    if to_send_name:
        first_message(sender, env_data, config_data,
                      to_send_name, to_send_mail, to_send_date)

    (tomorrow_name, tomorrow_email, tomorrow_date,
     tomorrow_time, today_name, today_email, today_date) = tomorrow_today_data(
         date_prob, name_prob, email_prob, tomorrow, today
     )

    if tomorrow_name:
        reminder(sender, env_data, config_data,
                 tomorrow_name, tomorrow_email, tomorrow_date)

    return (date_prob, name_prob, email_prob, tomorrow_name, tomorrow_email,
            tomorrow_date, tomorrow_time)


def delete_old_bookings_task(
    session_id,
    cookies: dict,
    buchungsliste_nummer: str,
    today_as_datetime,
    tomorrow_as_datetime,
    tomorrow_time: list,
    today: str
):
    """Task: Delete expired bookings from Termino."""
    editing_url = f"https://www.termino.gv.at/meet/de/node/{buchungsliste_nummer}/edit"
    df_termino = termino_bookings(session_id, editing_url)

    to_remove_ids = get_ids_to_remove(
        df_termino,
        today_as_datetime,
        tomorrow_as_datetime,
        tomorrow_time
    )

    if to_remove_ids:
        actual_deleted = deleting_bookings(cookies, editing_url, to_remove_ids, today)
        # The print is now inside deleting_bookings (with the true count).
        if actual_deleted != len(to_remove_ids):
            print(f"  ! Expected {len(to_remove_ids)} deletions, got {actual_deleted}")
    else:
        print("  -> Keine Slots zum Loeschen (vergangen oder morgen-leer)")

    return df_termino


def notify_supervisors_task(
    sender: MailSender,
    calendar_sink: CalendarSink,
    env_data: dict,
    config_data: dict,
    tomorrow: str,
    tomorrow_time: list,
    tomorrow_name: list,
    tomorrow_email: list
) -> Tuple:
    """Task: Download Google Sheet and notify supervisors about tomorrow's sessions.

    Sends the daily reminder mails AND drops a calendar entry per slot
    into the configured calendar (NoOp by default, see calendar_sinks).
    Calendar upsert errors never break the mail flow - they only log a
    warning.
    """
    print(EXTENSIONS)
    time.sleep(0.5)

    download_g_s(env_data, config_data)
    name_vl, email_vl, date_vl, time_vl = google_dp(tomorrow)

    print(f"Tomorrow time: {tomorrow_time}")
    print(f"Supervisor names: {name_vl}")
    print(f"Supervisor emails: {email_vl}")
    print(f"Supervisor dates: {date_vl}")
    print(f"Supervisor times: {time_vl}")

    vl_mail(
        sender,
        env_data,
        config_data,
        name_vl,
        email_vl,
        time_vl,
        tomorrow_time,
        tomorrow_name,
        tomorrow_email,
        tomorrow
    )

    # Mirror VL notifications into the calendar sink - one event per
    # *slot* (not per VL), with all VLs as attendees and the participants
    # listed in the description. Idempotent via stable UIDs. The helper
    # lives in utils.calendar_sinks so it can be unit-tested directly.
    push_slots_to_calendar(
        calendar_sink=calendar_sink,
        config_data=config_data,
        tomorrow=tomorrow,
        name_vl=name_vl,
        email_vl=email_vl,
        time_vl=time_vl,
        tomorrow_time=tomorrow_time,
        tomorrow_name=tomorrow_name,
        tomorrow_email=tomorrow_email,
    )

    return name_vl, email_vl, date_vl, time_vl


def manage_appointments_task(
    sender: MailSender,
    env_data: dict,
    config_data: dict,
    cookies: dict,
    editing_url: str,
    tomorrow: str,
    df_termino
) -> None:
    """Task: Sync appointments between Google Sheet and Termino."""
    differenz_termino, zukuenftige_ereignisse = data_prep(tomorrow, df_termino)

    if len(differenz_termino["Place"]) > 0:
        print(f"\n!  Warning: {len(differenz_termino)} appointments in Termino have no supervisor assigned!")
        termin_missing(sender, env_data, config_data, differenz_termino)

    df_kombiniert = data_prep_2(zukuenftige_ereignisse, df_termino)

    # Always run insert_new_app_in_termino so the chronological-sort pass
    # also fires when nothing new is inserted. If df_kombiniert has zero
    # new rows, the function loops once, finds nothing, then sorts+saves.
    new_count = int(df_kombiniert["Neuer_Termin"].sum())
    if new_count > 0:
        print(f"\n-> Inserting {new_count} new appointments into Termino...")
    else:
        print("\n-> No new appointments to insert; running sort-only pass")
    insert_new_app_in_termino(cookies, editing_url, df_kombiniert)
    if new_count > 0:
        print(f"-> Successfully inserted {new_count} new appointment(s)")
    else:
        # We don't have the sort-pass return value up here, so say neutrally
        # what happened. The sort function itself logs sucess/failure.
        print("-> manage_appointments done (no inserts; sort attempted)")


def _run_workflow(
    *,
    sender: MailSender,
    calendar_sink: CalendarSink,
    env_data: dict,
    config_data: dict,
    runner: TaskRunner,
    status: StatusManager,
    today: str,
    tomorrow: str,
    today_as_datetime,
    tomorrow_as_datetime,
    report: RunReport,
) -> None:
    """
    The actual daily workflow. Extracted from main() so it can be wrapped
    cleanly in the sender context manager without massive indentation.
    """
    # Initialize Termino session
    print("\n" + "=" * 60)
    print("INITIALIZING TERMINO SESSION")
    print("=" * 60)

    termino_session = TerminoSession(env_data, config_data)

    # Task 1: Download Termino CSV (only once per day)
    runner.run_task(
        task_name="download_termino_csv",
        task_func=termino_session.initialize,
        skip_message="Termino CSV already downloaded today"
    )
    report.add_phase("Termino-Login + CSV", "ok",
                     details=f"Buchungsliste #{termino_session.buchungsliste_nummer}")

    # If the task was skipped (already done today), TerminoSession's fields
    # are still None - initialize() was never called. Restore them from
    # session.json so downstream tasks (which need the CSV path, cookies,
    # buchungsliste_nummer, ...) still work.
    if termino_session.actual_booking_list_csv is None:
        try:
            (termino_session.antibot_key,
             termino_session.cookies,
             termino_session.logged_url,
             termino_session.buchungsliste_nummer,
             termino_session.actual_booking_list_csv) = load_session()
            # Build a fresh requests.Session and inject the stored cookies
            # back into it, otherwise downstream calls like termino_bookings()
            # would hit Termino unauthenticated and get the login page.
            termino_session.session_id = session()
            for name, value in (termino_session.cookies or {}).items():
                termino_session.session_id.cookies.set(
                    name, value, domain=".termino.gv.at", path="/"
                )
            print("  (restored Termino session state from session.json)")
        except Exception as e:
            # session.json missing or unreadable - force a fresh init
            print(f"  WARN: could not restore session ({e}); re-initialising")
            termino_session.initialize()

    # Task 2: Send confirmation + reminder emails (only once per day)
    print("\n" + "=" * 60)
    print("PROCESSING EMAILS")
    print("=" * 60)

    email_data = runner.run_task(
        task_name="send_reminder_mail",
        task_func=send_emails_task,
        skip_message="Reminder emails already sent today",
        sender=sender,
        env_data=env_data,
        config_data=config_data,
        actual_booking_list_csv=termino_session.actual_booking_list_csv,
        tomorrow=tomorrow,
        today=today
    )
    if email_data:
        _, _, _, t_name, _, _, _ = email_data
        report.add_phase("Probandinnen-Mails", "ok",
                         details=f"{len(t_name)} morgen-Erinnerung(en)",
                         count=len(t_name))
    else:
        report.add_phase("Probandinnen-Mails", "skipped",
                         details="schon heute gelaufen")

    # Extract data (either from task or reload if skipped)
    if email_data:
        (date_prob, name_prob, email_prob, tomorrow_name, tomorrow_email,
         tomorrow_date, tomorrow_time) = email_data
    else:
        (date_prob, name_prob, email_prob,
         date_first_mail_sended, name_first_mail_sended, email_first_mail_sended,
         to_send_name, to_send_mail, to_send_date) = booking_list_preperation(
             termino_session.actual_booking_list_csv,
             config_data
         )
        (tomorrow_name, tomorrow_email, tomorrow_date,
         tomorrow_time, today_name, today_email, today_date) = tomorrow_today_data(
             date_prob, name_prob, email_prob, tomorrow, today
         )

    # Task 3 (moved): just load df_termino now; delete runs AFTER manage_appointments
    # so that morgen-Slots ohne Probandinnen, die manage_appointments frisch
    # eingefuegt hat, sofort wieder geloescht werden.
    editing_url = (
        f"https://www.termino.gv.at/meet/de/node/"
        f"{termino_session.buchungsliste_nummer}/edit"
    )
    df_termino = termino_bookings(termino_session.session_id, editing_url)

    # Optional: Google Sheets / uniCLOUD spreadsheet integration
    if config_data.get('implement_sheet_sync', config_data.get('implement_google')) == 1:

        # Task 4: Notify supervisors
        print("\n" + "=" * 60)
        print("SPREADSHEET INTEGRATION - NOTIFYING SUPERVISORS")
        print("=" * 60)

        runner.run_task(
            task_name="message_vl",
            task_func=notify_supervisors_task,
            skip_message="Supervisors already notified today",
            sender=sender,
            calendar_sink=calendar_sink,
            env_data=env_data,
            config_data=config_data,
            tomorrow=tomorrow,
            tomorrow_time=tomorrow_time,
            tomorrow_name=tomorrow_name,
            tomorrow_email=tomorrow_email,
        )
        # The actual VL count isn't easy to recover here without refactoring
        # notify_supervisors_task to return data. For now, just mark it ok.
        report.add_phase("VL-Mails + Kalender", "ok",
                         details=f"tomorrow={tomorrow}")

        # Task 5: Manage appointments (sync spreadsheet -> Termino)
        print("\n" + "=" * 60)
        print("SPREADSHEET INTEGRATION - SYNCING APPOINTMENTS")
        print("=" * 60)

        editing_url = (
            f"https://www.termino.gv.at/meet/de/node/"
            f"{termino_session.buchungsliste_nummer}/edit"
        )
        runner.run_task(
            task_name="manage_appointments",
            task_func=manage_appointments_task,
            skip_message="Appointments already managed today",
            sender=sender,
            env_data=env_data,
            config_data=config_data,
            cookies=termino_session.cookies,
            editing_url=editing_url,
            tomorrow=tomorrow,
            df_termino=df_termino,
        )
        report.add_phase("Termino-Sync + Sort", "ok",
                         details="insert + chronologische Sortierung")

        # POST-insert delete pass: re-load df_termino (frisch nach insert),
        # dann lösche vergangene Slots + morgen-Slots ohne Probandinnen.
        # WICHTIG: Diese Reihenfolge stellt sicher dass NEUE morgen-Slots,
        # die manage_appointments grad eingefuegt hat aber fuer die keine
        # Probandin gebucht hat, sofort wieder verschwinden.
        print("\n" + "=" * 60)
        print("DELETING EXPIRED + TOMORROW-EMPTY BOOKINGS (POST-INSERT)")
        print("=" * 60)
        df_termino_fresh = termino_bookings(termino_session.session_id, editing_url)
        runner.run_task(
            task_name="delete_bookings",
            task_func=delete_old_bookings_task,
            skip_message="Bookings already deleted today",
            session_id=termino_session.session_id,
            cookies=termino_session.cookies,
            buchungsliste_nummer=termino_session.buchungsliste_nummer,
            today_as_datetime=today_as_datetime,
            tomorrow_as_datetime=tomorrow_as_datetime,
            tomorrow_time=tomorrow_time,
            today=today
        )
        report.add_phase("Cleanup (vergangene + leere)", "ok",
                         details="post-insert delete pass")

    # ---- Status summary ----
    print("\n" + "=" * 60)
    print("DAILY WORKFLOW COMPLETE")
    print("=" * 60)

    completed = status.get_completed_tasks() if hasattr(status, "get_completed_tasks") else {}
    failed = status.get_failed_tasks() if hasattr(status, "get_failed_tasks") else {}

    if completed:
        print(f"\nOK Completed today: {list(completed)}")
    if failed:
        print("\n!  WARNING: The following tasks failed today:")
        for task, info in failed.items():
            print(f"  X {task}: {info.get('error', 'Unknown error')}")
    else:
        print("\nOK All tasks completed successfully!")


def main() -> None:
    """
    Main function that orchestrates the full Termino workflow.

    Steps:
        1. Initialize status manager and create dates
        2. Load config and env (no passwords - those live in the keyring)
        3. Build the mail sender from config_data['mail_provider']
        4. Build the calendar sink from config_data['calendar_provider']
        5. Run the daily workflow inside both context managers
    """
    # Display banner
    print(TERMINO_SCRIPT_ASCI)
    time.sleep(0.5)

    # Initialize status manager
    status = StatusManager("status.json", debug=True)
    runner = TaskRunner(status)

    # Create date objects
    today, tomorrow, today_as_datetime, tomorrow_as_datetime = date_creation()

    # Load configuration
    env_data = load_env_data()
    config_data = load_config()

    # Backward-compat: web_interaction.termino_login() still reads the
    # Termino password from env_data['password_termino']. After the keyring
    # migration the env file no longer holds it, so we inject it here from
    # the keyring at runtime.
    from utils.secrets import get_secret
    _termino_pw = get_secret("termino-pw")
    if _termino_pw:
        env_data["password_termino"] = _termino_pw
    else:
        print("\n!  Termino password not found in keyring. Run:")
        print("     python -m utils.secrets set --termino")

    config_text(config_data, env_data)

    # Run-Report sammelt strukturierte Daten ueber den Lauf.
    report = RunReport()

    # Build the mail sender once for the entire run.
    provider_cfg = _resolve_mail_provider(config_data, env_data)
    print(f"\nMail provider: {provider_cfg['type']} as {provider_cfg.get('username')}")

    # Pre-flight: warn early if EWS is configured but the host is unreachable.
    # Non-blocking - we still run the workflow (Termino-Sync, Calendar etc.
    # don't need VPN), but the user sees the diagnosis up front instead of
    # after a 120s timeout on the final mail step. See utils/vpn.py.
    warn_if_not_connected(provider_cfg["type"])

    # Build the calendar sink. Defaults to NoOp when calendar_provider
    # is absent from config.json - i.e. nothing is written anywhere.
    cal_cfg = config_data.get("calendar_provider", {"type": "none"})
    print(f"Calendar provider: {cal_cfg.get('type')} "
          f"as {cal_cfg.get('username', '(no username)')}")

    with make_sender(provider_cfg) as sender, \
         make_calendar_sink(config_data) as calendar_sink:
        workflow_crashed = False
        try:
            _run_workflow(
                sender=sender,
                calendar_sink=calendar_sink,
                env_data=env_data,
                config_data=config_data,
                runner=runner,
                status=status,
                today=today,
                tomorrow=tomorrow,
                today_as_datetime=today_as_datetime,
                tomorrow_as_datetime=tomorrow_as_datetime,
                report=report,
            )
        except Exception as e:
            # Classify the error so the report's status / console message
            # tells the user what to do (network vs. code vs. auth).
            msg = str(e)
            workflow_crashed = True
            if "NameResolutionError" in msg or "Name or service not known" in msg:
                hint = "DNS/Netzwerk-Problem - Internet pruefen (VPN ggf. trennen)"
            elif "ConnectionError" in msg or "Max retries exceeded" in msg:
                hint = "Netzwerk-Problem - termino.gv.at nicht erreichbar"
            elif "Auth" in msg or "401" in msg or "403" in msg:
                hint = "Auth-Problem - Termino-Passwort im Keyring pruefen"
            else:
                hint = f"unerwarteter Fehler: {type(e).__name__}"
            report.add_error(hint)
        finally:
            # Print short console summary + send the long mail report.
            report.finalize()
            print()
            print(report.to_console_summary())
            sent = report.send(sender, env_data, config_data)
            if sent:
                print(f"  -> Daily-Report per Mail an {report.sent_to} verschickt")
            else:
                print(f"  ! Mail-Bericht konnte nicht verschickt werden")
            if workflow_crashed:
                # Exit cleanly: report has been sent, traceback would only
                # be noise on top of the structured error already in the report.
                sys.exit(1)


if __name__ == "__main__":
    main()
