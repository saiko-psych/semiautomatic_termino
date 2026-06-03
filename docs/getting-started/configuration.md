# Configuration

`config.json` is per-installation and gitignored, so it never lands in version control. Use `config.example.json` as a starting point:

```bash
cp config.example.json config.json
```

Then either edit the file directly or use the interactive wizard (see {ref}`config-wizard` below).

## Top-level fields

| Field | Purpose |
| --- | --- |
| `booking_list` | Name of the Termino booking list (must match exactly) |
| `study_name` | Shown in mail subjects and templates |
| `study_location` | Substituted into mail templates as `$LOCATION` |
| `contact_mail` | Address shown to participants as the reply-to contact (`$MAIL`) |
| `booking_url` | Direct Termino booking link, substituted as `$BOOKING_URL` |
| `mail_provider` | Which backend sends outgoing mail |
| `sheet_provider` | Where the supervisor assignment spreadsheet lives |
| `calendar_provider` | Optional: where to write calendar entries |

## Providers

### mail_provider

Pick one of the two supported backends:

```json
{ "type": "uni-graz-ews", "username": "your.account@edu.uni-graz.at" }
```

```json
{ "type": "yahoo-smtp", "username": "your-mail@yahoo.com" }
```

EWS requires the Uni-Graz VPN to reach `webmail.uni-graz.at`. Yahoo requires a [Yahoo App Password](https://help.yahoo.com/kb/SLN15241.html). See {doc}`secrets` for how to store credentials, and {doc}`../deployment/vpn-setup` for VPN notes.

### sheet_provider

Pick one of the two supported backends:

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
{ "type": "google" }
```

For the Google backend, set `google_spreadsheet_url` in `sensible.env`.

### calendar_provider

Pick one of the three options:

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

`share_with` is optional; when present the calendar is automatically shared with those Nextcloud usernames on first run.

(config-wizard)=
## Interactive wizard

A friendlier alternative to hand-editing `config.json` is the interactive PowerShell wizard:

```powershell
.\config.ps1
```

This is the intended path for most users. The wizard validates each entry before writing, and it will be extended in future releases to cover keyring management as well.
