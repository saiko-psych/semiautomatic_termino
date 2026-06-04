# Daily run

## Running it

```bash
uv run python main.py
```

The script works through eight phases in order: download the Termino booking list, send confirmation mails to new bookings, send day-before reminders, read the supervisor sheet, send VL notifications, sync the Termino schedule, update the calendar, and finally send an HTML run-report mail back to the study coordinator. Each phase is logged to the console and summarised in the HTML report.

A participant books a slot through the Termino link, and phase 1 then reads
those bookings:

```{figure} ../_static/screenshots/termino-booking-dialog.png
:alt: A participant booking a Termino slot (e-mail blurred)
:width: 90%

Booking a slot from the participant's side — name, e-mail, and an optional note.
(E-mail blurred; demo booking on a test list.)
```

```{figure} ../_static/screenshots/termino-bookings.png
:alt: The Termino bookings table the script reads each day (e-mail column blurred)
:width: 100%

Phase 1 reads these bookings; the script then mails each new booking and reminds
tomorrow's slots. (E-mail column blurred; test list.)
```

The script is **idempotent at the day level**: each phase records its result in `status.json`. Re-running on the same day skips every phase that already succeeded. `session.json` caches the Termino login so repeated runs within a day do not re-authenticate.

To force a full re-run on the same day, delete `status.json` first:

```powershell
# Windows
Remove-Item status.json
```

```bash
# Linux / macOS
rm status.json
```

## Email templates

Participant-facing mails are built from plain-text templates in `templates/`. Two templates exist:

| File | When sent | Available variables |
| --- | --- | --- |
| `templates/first_email.txt` | First booking confirmation | `$NAME`, `$DATE`, `$TIME`, `$STUDYNAME`, `$MAIL`, `$LOCATION`, `$BOOKING_URL` |
| `templates/reminder.txt` | Day-before reminder | same |

Variables are substituted with Python's [`string.Template`](https://docs.python.org/3/library/string.html#template-strings). `$MAIL` uses `config.contact_mail` and falls back to `mail_provider.username` if that field is not set.

Templates are **gitignored** so each lab can customise them without merge conflicts. Versioned starting points are provided as `templates/*.example.txt`. Copy and edit them once:

```bash
cp templates/first_email.example.txt templates/first_email.txt
cp templates/reminder.example.txt    templates/reminder.txt
```
