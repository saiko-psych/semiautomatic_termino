# Installation

Install `uv`, sync the project, then run the setup wizard.

## Requirements

The script runs on Python 3.10 or newer (3.13 recommended on Windows; 3.10 is fine on Linux servers). You also need the `uv` package manager, a [Termino](https://www.termino.gv.at/) account with an active booking list, a mail account (either Uni-Graz Exchange/Outlook or Yahoo), and Chrome or Chromium installed on the machine that will run the script (`webdriver-manager` downloads the matching driver automatically).

| Requirement | Notes |
| --- | --- |
| Python >= 3.10 | 3.13 on Windows, 3.10+ on Linux |
| [`uv`](https://docs.astral.sh/uv/) | One-line install — see below |
| Termino account | Free at termino.gv.at |
| Mail account | Uni-Graz EWS (Outlook) or Yahoo SMTP |
| Chrome or Chromium | Selenium-based automation |

Optional but recommended:

| What | Why |
| --- | --- |
| Cisco AnyConnect / Secure Client VPN | Required to reach `webmail.uni-graz.at` for EWS mail |
| Nextcloud / cloud.uni-graz.at account | Host the supervisor spreadsheet (WebDAV) |
| Nextcloud calendar | Auto-create and share calendar entries per slot |

## Install uv

**Linux / macOS:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Clone and sync

```bash
git clone https://github.com/saiko-psych/semiautomatic_termino.git
cd semiautomatic_termino
uv sync
```

`uv sync` creates a local `.venv/` and installs everything pinned in `uv.lock`. The result is reproducible across Windows, Linux, and macOS.

## First-time setup

Run the interactive setup wizard:

```bash
uv run python setup.py
```

The wizard walks through each choice and writes `config.json`:

- Pick your mail provider (Uni-Graz EWS or Yahoo SMTP).
- Pick your sheet provider (uniCLOUD WebDAV or Google Sheets).
- Pick your calendar backend (none, unicloud-caldav, or uni-graz-ews).
- Initialise the OS keyring entries you will need.

After the wizard finishes, store your credentials (see {doc}`secrets` for details):

```bash
uv run python -m utils.secrets set --termino
uv run python -m utils.secrets set --email <your-mail-address>
```

No plaintext passwords are written to disk at any point — everything goes into the OS keyring (Windows Credential Manager, macOS Keychain, or Linux CryptFile-Keyring).
