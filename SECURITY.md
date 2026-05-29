# Security Policy

## Supported versions

Only the current `main` branch (v2.x) is supported. v1 (Yahoo-only legacy) is unmaintained.

## What this project handles

- **Termino account credentials** — used by Selenium to log in and edit booking lists.
- **Mail account credentials** — Uni-Graz EWS or Yahoo SMTP, used to send confirmation, reminder and supervisor mails.
- **Nextcloud / uniCLOUD app password** — used to read the supervisor xlsx and optionally write calendar events.
- **Participant names and email addresses** — read from the Termino booking list and used as mail recipients.

## How credentials are stored

All credentials live in the **OS keyring**:

- Windows: Credential Manager (`keyring` default backend)
- macOS: Keychain (`keyring` default backend)
- Linux: CryptFile-Keyring (`keyrings.cryptfile`), encrypted at rest

Credentials are **never written to `config.json`, `sensible.env`, log files, or any artefact in `.git/`.**
Re-validate periodically with `python -m utils.secrets list` to see which keys are present (values are not printed).

The `sensible.env` file (if it exists in your install) is a legacy fallback that may contain `google_spreadsheet_url` and other low-sensitivity strings. It is in `.gitignore` and never committed. After migration via `tools/migrate_env_to_keyring.py` you can delete it.

## Network reachability

- `webmail.uni-graz.at` (EWS) requires Cisco AnyConnect VPN. The script does not bring up the VPN — it expects the VPN to be up before `main.py` runs.
- `cloud.uni-graz.at` (WebDAV + CalDAV) is publicly reachable; no VPN required.
- `www.termino.gv.at` is publicly reachable; no VPN required.

## Reporting a vulnerability

If you find a credential leak, an exfiltration path, or any other issue that compromises participant data, please open a **private** security advisory on GitHub:

https://github.com/saiko-psych/semiautomatic_termino/security/advisories/new

For non-security bugs, please use [GitHub Issues](https://github.com/saiko-psych/semiautomatic_termino/issues) instead.

## Threat model

This script is designed for **single-user, per-lab installation**, not multi-tenant SaaS:

- One install handles one research group's booking lists.
- The script trusts the OS user account it runs as.
- The script does not authenticate participants — anyone who can put an entry on Termino is treated as a real booking.

Out of scope:

- Hardening against a malicious lab admin who has shell access to the install.
- Anti-bot or rate-limiting of the participant booking flow (that's Termino's responsibility).
- E2E encryption of mails.
