# semiautomatic_termino

Daily-cron automation around [termino.gv.at](https://www.termino.gv.at/), built for university research groups that need to manage many participants and supervisors without drowning in coordination email.

The script reads supervisor (Versuchsleiter:in, "VL") assignments from an Excel file in your group's cloud, syncs the schedule with Termino, sends confirmation and reminder mails to participants, alerts every VL about their slot the day before, and (optionally) drops every slot into a shared calendar.

This is **v2.0** — a full rewrite of the original Yahoo-only single-file script. The legacy v1 workflow is preserved as a fallback (Yahoo SMTP still works) but the recommended path is Uni-Graz EWS + uniCLOUD + Nextcloud Calendar.

---

## Table of Contents

- [What it does](#what-it-does)
- [Requirements](#requirements)
- [Quick install](#quick-install)
- [Configuration](#configuration)
- [Storing secrets](#storing-secrets)
- [VPN setup (only for EWS)](#vpn-setup-only-for-ews)
- [Daily run](#daily-run)
- [Server / cron deployment](#server--cron-deployment)
- [Email templates](#email-templates)
- [Architecture (Provider Pattern)](#architecture-provider-pattern)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## What it does

In one daily run, `main.py`:

1. Logs into Termino and downloads the booking list as CSV.
2. Sends a confirmation mail to every new booking (once per booking).
3. Sends a reminder mail to every participant whose appointment is tomorrow.
4. Reads the supervisor (VL) sheet from your group's cloud (uniCLOUD WebDAV or Google Sheets).
5. Notifies each VL about tomorrow's slot — how many participants, who they are, and (optional) an iMIP calendar invite they can accept in Outlook / Apple Mail / Thunderbird.
6. Syncs the spreadsheet schedule with Termino: inserts new appointments, sorts them chronologically, deletes expired slots, and removes any "morgen-leeren" slots (tomorrow's slots with zero participants).
7. (Optional) Drops every slot into a shared calendar (Nextcloud CalDAV or Exchange / Outlook).
8. Sends a structured HTML run-report mail back to the study coordinator: which phase succeeded, how many mails went out, how long each phase took, what errors occurred.

The script is **idempotent at the day-level**: re-running on the same day is a no-op for each task that already succeeded.

---

## Requirements

| What | Why | Notes |
| --- | --- | --- |
| Python **3.10 or newer** | Runtime | 3.13 recommended on Windows; 3.10 is fine on Linux servers. |
| [`uv`](https://docs.astral.sh/uv/) | Dependency management | One-line install. See [Quick install](#quick-install). |
| A Termino account + booking list | The script logs in as you | Free at termino.gv.at. |
| A mail account | To send mails | Either Uni-Graz EWS (Exchange Web Services / Outlook) or Yahoo SMTP. |
| Chrome or Chromium | Selenium driver | `webdriver-manager` downloads the right driver automatically. |

Optional, but strongly recommended:

| What | Why |
| --- | --- |
| **Cisco AnyConnect VPN** | Required to reach `webmail.uni-graz.at` for the EWS mail backend. Not required for the Termino selenium part. |
| **Nextcloud / cloud.uni-graz.at** account | Store the VL assignment spreadsheet there (WebDAV `xlsx`). Lets you skip Google Sheets entirely. |
| **Nextcloud calendar** | Auto-create and auto-share calendar entries per slot. |

Tested on Windows 11 (Python 3.13) and Debian 12 LXC (Python 3.11). macOS should work but is not exercised by the test suite.

### Quick recommendation

If you're at Uni-Graz and don't mind connecting the Cisco VPN before each
run / via systemd:

- `mail_provider: uni-graz-ews`
- `sheet_provider: unicloud`
- `calendar_provider: unicloud-caldav`

If you want zero VPN setup (Yahoo address as the sender, Google Drive
sheet, no calendar):

- `mail_provider: yahoo-smtp`
- `sheet_provider: google`
- `calendar_provider: none`

Mixing is fine - the providers are independent. The `setup.py` wizard
walks through each choice.

---

## Quick install

### 1. Install `uv`

**Linux / macOS:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Clone and sync

```bash
git clone https://github.com/saiko-psych/semiautomatic_termino.git
cd semiautomatic_termino
uv sync
```

`uv sync` creates a local `.venv/` and installs everything pinned in `uv.lock`. Reproducible across Windows, Linux, and macOS.

### 3. First-time setup

```bash
uv run python setup.py
```

This walks you through:

- Picking your mail provider (Uni-Graz EWS or Yahoo SMTP).
- Picking your sheet provider (uniCLOUD WebDAV or Google Sheets).
- Picking your calendar backend (none / unicloud-caldav / uni-graz-ews).
- Writing `config.json` from the choices above.
- Initialising the OS keyring entries you'll need.

After `setup.py` finishes, run:

```bash
uv run python -m utils.secrets set --termino
uv run python -m utils.secrets set --email <your-mail-address>
```

The script stores credentials in your OS keyring (Windows Credential Manager / macOS Keychain / Linux CryptFile-Keyring). **No plaintext passwords are written to disk at any point.**

### 4. Try a single live run

```bash
uv run python main.py
```

If anything goes wrong, see [Troubleshooting](#troubleshooting).

---

## Configuration

`config.json` is per-installation; it is in `.gitignore` so it never lands in git. Use `config.example.json` as a starting point:

```bash
cp config.example.json config.json
$EDITOR config.json
```

Top-level fields:

| Field | Purpose | Example |
| --- | --- | --- |
| `booking_list` | Name of the Termino booking list to read (must match exactly) | `"Studienteilnahme"` |
| `study_name` | Shown in mail subjects and templates | `"Musiktherapie"` |
| `study_location` | Substituted into mail templates as `$LOCATION` | `"Glacisstrasse 27, 8010 Graz"` |
| `contact_mail` | Address shown to participants as the contact (`$MAIL` in templates) | `"study-contact@example.org"` |
| `booking_url` | Direct Termino booking link, substituted into templates as `$BOOKING_URL` | `"https://www.termino.gv.at/meet/de/b/..."` |
| `mail_provider` | Which backend sends mails | see below |
| `sheet_provider` | Where the supervisor spreadsheet lives | see below |
| `calendar_provider` | Optional: where to drop calendar entries | see below |

### `mail_provider`

Pick **one**:

```json
{ "type": "uni-graz-ews", "username": "your.account@edu.uni-graz.at" }
```

```json
{ "type": "yahoo-smtp",   "username": "your-mail@yahoo.com" }
```

EWS requires VPN to reach `webmail.uni-graz.at`. Yahoo requires a [Yahoo App Password](https://help.yahoo.com/kb/SLN15241.html).

### `sheet_provider`

Pick **one**:

```json
{
    "type": "unicloud",
    "username": "your.account_edu",
    "xlsx_path": "/Termino/versuchsleiter.xlsx",
    "main_sheet": "Zeittabelle",
    "info_sheet": "information"
}
```

```json
{
    "type": "google"
}
```

For the Google flavour, set `env_data['google_spreadsheet_url']` in `sensible.env`.

### `calendar_provider`

Pick **one**:

```json
{ "type": "none" }
```

```json
{
    "type": "unicloud-caldav",
    "username": "your.account_edu",
    "calendar_name": "Termino",
    "share_with": ["colleague1_edu", "colleague2_edu"]
}
```

```json
{
    "type": "uni-graz-ews",
    "username": "your.account@edu.uni-graz.at",
    "calendar_name": "Termino"
}
```

`share_with` is optional. When present, the calendar is automatically shared with the listed Nextcloud usernames during the first run.

A friendlier alternative to hand-editing `config.json` is the interactive wizard:

```powershell
.\config.ps1
```

---

## Storing secrets

All credentials live in the OS keyring, never in `config.json` and never in `sensible.env`. Manage them with:

```bash
# Termino-script secrets (interactively prompts for each: Termino password,
# uniCLOUD app-password, Yahoo app-password, etc.)
uv run python -m utils.secrets set --termino

# VPN + EWS credentials: Uni-Graz login password + TOTP base32 seed,
# stored under the openconnect-sso namespace so it's shared with the
# VPN tooling. The EWS mail backend reads from this same slot.
uv run python -m utils.secrets set --email <your-mail@edu.uni-graz.at> --vpn

# Diagnostics
uv run python -m utils.secrets list                # show which keys are present
uv run python -m utils.secrets get <key>           # print one value (be careful)
```

Note: The `uni-mail-pw` slot under `termino-uni` is the legacy Keycloak
"Mail Password" used only for direct SMTP to `mailproxy.uni-graz.at`. It is
**NOT** used by the EWS flow - EWS uses the regular login password from
the `openconnect-sso` namespace above. You can safely skip `uni-mail-pw`
in `set --termino` unless you've explicitly switched to SMTP.

Migration from a legacy plaintext `sensible.env`:

```bash
uv run python tools/migrate_env_to_keyring.py
```

### EWS Credential Source (technical)

The Uni-Graz EWS mail backend (`mail_provider.type: "uni-graz-ews"`) reads
the user's UGO login password from the **openconnect-sso namespace**, not
from a separate Termino-Skript slot. This is by design - EWS Basic Auth
accepts the regular Uni login password (same as VPN login), and we want
**one** rotation point when the UGO-PW expires.

Practical consequence: running

```bash
python -m utils.secrets set --email <your-mail@edu.uni-graz.at> --vpn
```

sets up BOTH the VPN tunnel password AND the EWS auth in one go. No
separate step needed for EWS mail.

The `uni-mail-pw` slot in the `termino-uni` namespace is for the legacy
SMTP-via-mailproxy.uni-graz.at path only - leave it unset if you use EWS.

### Headless / Server setup (no interactive desktop)

If you run the script on a server without a desktop session (LXC, Docker,
cron-only VM), the default OS keyring will not work. Use the plaintext file
backend explicitly:

```bash
export PYTHON_KEYRING_BACKEND=keyrings.alt.file.PlaintextKeyring
```

Put this in your systemd `EnvironmentFile=` so the daily-cron service picks
it up. Then set restrictive permissions:

```bash
chmod 700 ~/.local/share/python_keyring/
chmod 600 ~/.local/share/python_keyring/keyring_pass.cfg
```

Plaintext + 0600 has the same security model as encrypted-with-master-
password-in-a-file (both require filesystem-access protection). It avoids
an interactive prompt that would block cron.

The encrypted-file backends (`keyrings.cryptfile`, `keyrings.alt`
EncryptedKeyring) ignore the `KEYRING_CRYPTFILE_PASSWORD` env var in
practice — they always prompt interactively, which kills cron. Use
PlaintextKeyring on the server.

---

## VPN setup (only for EWS)

If your `mail_provider.type` is `"uni-graz-ews"`, the script needs to
reach `webmail.uni-graz.at`, which is only accessible from inside the
Uni-Graz network or through the Cisco / openconnect-sso VPN. **Yahoo
SMTP needs no VPN; skip this section if you use Yahoo.**

The script auto-detects whether webmail is reachable and prints a clear
warning at the start of the run if not (see `utils/vpn.py`). If the VPN
is down, the final daily-report mail is skipped automatically so you
don't wait through a 120-second connect timeout (see `utils/auto_vpn.py`
for the optional headless integration).

### Laptop (Windows / macOS) - Cisco Secure Client

The interactive Uni-Graz setup. Cisco Secure Client (the modern
replacement for AnyConnect) has a GUI you launch manually:

1. Open Cisco Secure Client.
2. Connect to `univpn.uni-graz.at` and select the right authgroup
   (`Bedienstete`, `Studierende`, or `Universitaetsbibliothek`).
3. Authenticate with your Uni email + password.
4. Confirm the MFA prompt (TOTP from the Uni-Graz Authenticator app).
5. Wait until "Connected" appears.
6. Run the script: `uv run python main.py`.

There is no reliable headless CLI for Cisco Secure Client on Windows or
macOS. For unattended runs on those platforms, either keep the
connection alive in a long-lived session, or switch to the Yahoo SMTP
backend (no VPN required).

### Linux server - openconnect-sso (headless)

Uni-Graz delegates VPN authentication to Keycloak (SAML), which means
**plain `openconnect` does NOT work** out of the box - it gets login
form submissions rejected. The supported headless path uses
[`openconnect-sso`](https://github.com/vlaci/openconnect-sso), a Python
wrapper that drives a headless Qt-WebEngine browser through the SAML
flow, extracts the AnyConnect session cookie, then hands off to plain
`openconnect` for the actual tunnel.

The full setup - apt packages, sudoers rule for `/usr/sbin/openconnect`,
LXC host-side TUN passthrough, keyring credentials, the
`~/.config/openconnect-sso/config.toml` DOM selectors for Keycloak,
`vpn_up.sh` / `vpn_down.sh` wrappers, systemd Pre/Post hooks - is
documented step by step in **[`docs/SERVER_VPN_SETUP.md`](docs/SERVER_VPN_SETUP.md)**.
That doc is the canonical reference; this README only summarises.

Two ways to integrate the tunnel with the daily run:

1. **External bash wrappers + systemd** (recommended). `vpn_up.sh` runs
   as `ExecStartPre` on `termino.service`, `vpn_down.sh` as
   `ExecStopPost`. See the systemd block in `docs/SERVER_VPN_SETUP.md`.

2. **In-script** (`config.auto_vpn.enabled = true`). `utils/auto_vpn.py`
   wraps the workflow in a Python context manager that calls the same
   underlying tools. Useful when you don't have systemd. See
   `config.example.json` for the `auto_vpn` block and the docstring of
   `utils/auto_vpn.py` for the threat model.

Either way `openconnect-sso` itself must be installed as a uv tool
(its `keyring<24` pin conflicts with the script's `keyring>=25`, so it
can't be a regular project dep):

```bash
uv tool install --with 'setuptools<70' --with 'keyrings.alt' --with 'pycryptodome' openconnect-sso
```

---

## Daily run

```bash
uv run python main.py
```

The script prints a structured per-phase summary at the end and also sends an HTML run-report mail back to `mail_provider.username`. The mail is the source of truth — the console output is a convenience.

Idempotency lives in `status.json` (per-day) and `session.json` (Termino session cache). To force a re-run on the same day:

```bash
rm status.json
# (Windows) Remove-Item status.json
```

---

## Server / cron deployment

The script is designed to run unattended on a Proxmox LXC container or any small Debian box. Two pieces are non-trivial:

1. **Headless Chrome / Chromium** must be installed. On Debian:
   ```bash
   sudo apt install chromium chromium-driver
   ```

2. **VPN must be available** if you use the EWS mail backend. Headless `openconnect-sso` against `univpn.uni-graz.at` is the documented path - see [`docs/SERVER_VPN_SETUP.md`](docs/SERVER_VPN_SETUP.md). The Yahoo SMTP backend has no VPN requirement.

A typical systemd timer pair:

```ini
# /etc/systemd/system/termino.service
[Unit]
Description=Daily Termino reminder run
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
User=termino
WorkingDirectory=/opt/termino
ExecStart=/opt/termino/.venv/bin/python /opt/termino/main.py
```

```ini
# /etc/systemd/system/termino.timer
[Unit]
Description=Run Termino daily at 06:00

[Timer]
OnCalendar=*-*-* 06:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now termino.timer
```

Check status with `journalctl -u termino.service` and `systemctl list-timers`.

---

## Email templates

Templates live in `templates/` and are loaded relative to the project root. Two templates exist:

| File | When | Available variables |
| --- | --- | --- |
| `templates/first_email.txt` | First booking confirmation | `$NAME`, `$DATE`, `$TIME`, `$STUDYNAME`, `$MAIL`, `$LOCATION`, `$BOOKING_URL` |
| `templates/reminder.txt` | Day-before reminder | same |

Variables are substituted with [`string.Template`](https://docs.python.org/3/library/string.html#template-strings). `$MAIL` prefers `config.contact_mail` and falls back to `mail_provider.username` if not set.

Templates are **gitignored** so each lab can customize them without git conflicts on pull. Versioned starting points live next to them as `templates/*.example.txt`. First-time setup:

```bash
cp templates/first_email.example.txt templates/first_email.txt
cp templates/reminder.example.txt    templates/reminder.txt
$EDITOR templates/first_email.txt
$EDITOR templates/reminder.txt
```

---

## Architecture (Provider Pattern)

```
main.py
  ├── _resolve_mail_provider(config.json)   →  MailSender (Yahoo SMTP | Uni-Graz EWS)
  ├── make_sheet_provider(config.json)      →  SheetProvider (Google | uniCLOUD WebDAV)
  └── make_calendar_sink(config.json)       →  CalendarSink (NoOp | CalDAV | EWS)
```

Each provider is an abstract base class with a small interface (`.send()`, `.fetch()`, `.upsert_event()`). New providers are added by writing one subclass plus one factory branch. The rest of the code does not know which backend is active.

Key modules:

| Module | Responsibility |
| --- | --- |
| `main.py` | Daily workflow, idempotent task runner, RunReport mailer |
| `utils/secrets.py` | Wrapper around `keyring` + CLI (`python -m utils.secrets set/get/delete/list`) |
| `utils/mail_senders.py` | `YahooSmtpSender`, `UniGrazEwsSender` |
| `utils/mailing.py` | First-message / reminder / VL-mail / supervisor-missing alert |
| `utils/sheet_providers.py` | `GoogleSheetProvider`, `UniCloudSheetProvider` |
| `utils/calendar_sinks.py` | `NoOpCalendarSink`, `UniCloudCalDAVSink`, `ExchangeEWSSink`, iMIP invite builder |
| `utils/web_interaction.py` | Selenium driver for Termino (Drupal AJAX form handling) |
| `utils/extensions.py` | Spreadsheet ↔ Termino diffing |
| `utils/unicloud.py` | Lightweight WebDAV client (PROPFIND / PUT with If-Match) |
| `utils/preperation.py` | `load_env_data`, `load_config`, `config_text`, `tomorrow_today_data` |
| `utils/run_report.py` | Structured per-day report (HTML mail + console summary) |
| `status.py` / `status.json` | Per-day task state (gitignored) |
| `session.json` | Termino session cache (gitignored) |

---

## Troubleshooting

**`Login failed, fetching new antibot key...` loops forever**
Your Termino password may have changed. Refresh it:
`python -m utils.secrets set --termino`

**EWS sender raises `Could not resolve host`**
You're not on the VPN. EWS lives on `webmail.uni-graz.at` which is only reachable through Cisco AnyConnect.

**`No module named 'caldav'` after `git pull`**
A new dependency was added. Re-sync:
`uv sync`

**Selenium hangs on the "Mehr hinzufuegen" button**
Termino is Drupal-AJAX-based and occasionally drops slot containers from the DOM mid-render. The `Save-Reload-Sort-Save` pattern in `utils/web_interaction.py` is designed to bypass this. If it still hangs, run `tools/sort_termino.py --unsort` to reset and try again.

**Excel cell `01.01.1900` appearing in CSV output**
That's the openpyxl epoch glitch for time-only cells. The defensive filter in `_is_valid_uhrzeit` drops these — they show up as a console warning, not a crash.

**Tests fail with `ImportError: cannot import name 'TypeAlias'` on Python 3.9**
The codebase uses PEP 604 union syntax (`int | None`). Upgrade to Python 3.10 or newer.

For anything not covered here, check the journal of past bugs and gotchas in [`CLAUDE.md`](CLAUDE.md).

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the dev workflow and `CLAUDE.md` for project conventions and known gotchas. Pull requests welcome.

Unit tests:

```bash
uv run python -m unittest discover -s tests
```

There are currently 90 tests, all offline (no network or fixtures required).

---

## License

GPL-3.0-or-later. See [`LICENSE`](LICENSE).
