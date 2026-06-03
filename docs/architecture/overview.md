# Architecture overview

The script is built around three independent provider slots. `main.py` resolves each slot at startup from `config.json` and then orchestrates the daily workflow using only the abstract interfaces:

```
main.py
  ├── _resolve_mail_provider(config.json)   ->  MailSender (Yahoo SMTP | Uni-Graz EWS)
  ├── make_sheet_provider(config.json)      ->  SheetProvider (Google | uniCLOUD WebDAV)
  └── make_calendar_sink(config.json)       ->  CalendarSink (NoOp | CalDAV | EWS)
```

Each provider is an abstract base class with a small interface (`.send()` for mail, `.fetch()` for sheets, `.upsert_event()` for calendar). New backends are added by writing one subclass and one factory branch; the rest of the code never needs to know which backend is active.

## Key modules

| Module | Responsibility |
| --- | --- |
| `main.py` | Daily workflow orchestration, idempotent task runner, run-report mailer |
| `utils/secrets.py` | Wrapper around `keyring` + CLI (`python -m utils.secrets set/get/delete/list`) |
| `utils/mail_senders.py` | `YahooSmtpSender`, `UniGrazEwsSender` |
| `utils/mailing.py` | First-booking / reminder / VL-notification / supervisor-missing alert |
| `utils/sheet_providers.py` | `GoogleSheetProvider`, `UniCloudSheetProvider` |
| `utils/calendar_sinks.py` | `NoOpCalendarSink`, `UniCloudCalDAVSink`, `ExchangeEWSSink`, iMIP invite builder |
| `utils/web_interaction.py` | Selenium driver for Termino (Drupal AJAX form handling) |
| `utils/extensions.py` | Spreadsheet-to-Termino diff logic |
| `utils/unicloud.py` | Lightweight WebDAV client (PROPFIND / PUT with If-Match) |
| `utils/preperation.py` | Config loading, data loading, `tomorrow_today_data` |
| `utils/run_report.py` | Structured per-day report (HTML mail + console summary) |
| `status.py` / `status.json` | Per-day task state (gitignored) |
| `session.json` | Termino session cache (gitignored) |

For the full docstring-level API reference see {doc}`../reference/api/index`.
