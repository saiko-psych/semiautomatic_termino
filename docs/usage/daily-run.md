# Daily run

## Running it

```bash
uv run python main.py
```

The script works through eight phases in order: download the Termino booking list, send confirmation mails to new bookings, send day-before reminders, read the supervisor sheet, send VL notifications, sync the Termino schedule, update the calendar, and finally send an HTML run-report mail back to the study coordinator. Each phase is logged to the console and summarised in the HTML report.

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
