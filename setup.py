# setup.py - initial setup for the Termino script.
#
# After cloning: run once to install dependencies, create folders, ask
# which mail provider to use, write config.json + sensible.env (no
# passwords!), and store credentials in the OS keyring.
#
# Re-run later to update credentials:
#   python -m utils.secrets set --termino
#   python -m utils.secrets set --email <addr> --vpn
#
# If you already had a sensible.env with plaintext passwords:
#   python tools/migrate_env_to_keyring.py

import json
import os
import subprocess
import sys
from pathlib import Path


def install_requirements() -> None:
    print("Installing requirements...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
    )


def create_data_folder() -> Path:
    folder = Path("data")
    folder.mkdir(exist_ok=True)
    print("  data/      ok")
    return folder


def create_templates_folder() -> Path:
    folder = Path("templates")
    folder.mkdir(exist_ok=True)
    print("  templates/ ok")
    return folder


def create_tools_folder() -> Path:
    folder = Path("tools")
    folder.mkdir(exist_ok=True)
    print("  tools/     ok")
    return folder


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]: " if default else ": "
    val = input(prompt + suffix).strip()
    return val or default


def _ask_choice(prompt: str, options: list, default_idx: int = 0) -> str:
    print(prompt)
    for i, (val, descr) in enumerate(options, start=1):
        marker = " (default)" if i - 1 == default_idx else ""
        print(f"  {i}) {val} - {descr}{marker}")
    while True:
        raw = input(f"  choose 1-{len(options)} [{default_idx + 1}]: ").strip()
        if not raw:
            return options[default_idx][0]
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return options[idx][0]
        except ValueError:
            pass
        print("  invalid input, try again.")


def collect_user_inputs() -> tuple:
    """Returns (env_dict, config_dict, mail_provider_type)."""
    print()
    print("=" * 60)
    print("TERMINO SETUP - user input")
    print("=" * 60)
    print()

    username_termino = _ask("Termino username")
    mail = _ask("E-Mail address (used as From / Reply-To)")
    booking_list = _ask("Termino booking list name")
    study_name = _ask("Study name (Studienname)")

    print()
    provider = _ask_choice(
        "Which mail provider do you want to use?",
        options=[
            ("uni-graz-ews", "Uni Graz Exchange via EWS (requires VPN on server)"),
            ("yahoo-smtp",   "Yahoo SMTP (legacy)"),
        ],
        default_idx=0,
    )

    print()
    google_input = _ask(
        "Enable Google Sheets integration for supervisor notifications? (yes/no)",
        default="yes",
    ).lower()
    implement_google = 1 if google_input in ("yes", "y", "ja", "j") else 2
    if implement_google == 1:
        google_url = _ask("Google Spreadsheet URL")
        information = _ask("Spreadsheet sheet name with supervisor info",
                           default="information")
    else:
        google_url = ""
        information = ""

    env_data = {
        "username_termino": username_termino,
        "mail": mail,
    }
    if google_url:
        env_data["google_spreadsheet_url"] = google_url

    config_data = {
        "booking_list": booking_list,
        "study_name": study_name,
        "actual_list_printing": 2,
        "fist_mail_recieved_printing": 2,
        "to_send_first_mail": 2,
        "implement_google": implement_google,
        "information": information,
        "mail_provider": {
            "type": provider,
            "username": mail,
        },
    }
    return env_data, config_data, provider


def write_env_file(env_data: dict, path: str = "sensible.env") -> None:
    lines = [
        "# sensible.env - non-secret values only.",
        "# Passwords live in the OS keyring; see utils/secrets.py.",
        "# Run `python -m utils.secrets list` to see which keys are set.",
        "",
    ]
    for k, v in env_data.items():
        lines.append(f"{k}={v}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  {path}  written (no passwords)")


def write_config_json(config_data: dict, path: str = "config.json") -> None:
    Path(path).write_text(
        json.dumps(config_data, indent=4, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"  {path}  written")


def store_secrets_interactively(provider: str, mail: str) -> None:
    """Ask for passwords + store in keyring. Empty input skips."""
    import getpass
    from utils.secrets import (
        set_secret, set_uni_login_password,
        get_secret, get_uni_login_password,
    )

    print()
    print("=" * 60)
    print("CREDENTIALS - keyring")
    print("=" * 60)
    print("Stored in your OS keyring (KDE Wallet / Keychain / Credential")
    print("Manager). Press Enter to skip a field and set it later via")
    print("`python -m utils.secrets set`.")
    print()

    if get_secret("termino-pw"):
        print("  termino-pw      already set (keep existing)")
    else:
        pw = getpass.getpass("  Termino password (hidden): ")
        if pw:
            set_secret("termino-pw", pw)
            print("  termino-pw      stored")

    if provider == "yahoo-smtp":
        if get_secret("yahoo-app-pw"):
            print("  yahoo-app-pw    already set")
        else:
            pw = getpass.getpass("  Yahoo app password (hidden): ")
            if pw:
                set_secret("yahoo-app-pw", pw)
                print("  yahoo-app-pw    stored")

    if provider == "uni-graz-ews":
        if get_uni_login_password(mail):
            print(f"  uni-login-pw    already set for {mail}")
        else:
            pw = getpass.getpass(f"  Uni-Graz login password for {mail} (hidden): ")
            if pw:
                set_uni_login_password(mail, pw)
                print("  uni-login-pw    stored")


def create_first_email_template() -> None:
    p = Path("templates") / "first_email.txt"
    if p.exists():
        print("  templates/first_email.txt   exists")
        return
    p.write_text(
        "Hallo $NAME,\n\n"
        "vielen Dank fuer deine Anmeldung zur Studie $STUDYNAME!\n"
        "Hiermit bestaetigen wir deinen Termin am $DATE um $TIME Uhr.\n\n"
        "Bei Fragen wende dich an $MAIL.\n\n"
        "Viele Gruesse,\n"
        "Dein Studienteam\n",
        encoding="utf-8",
    )
    print("  templates/first_email.txt   created")


def create_reminder_template() -> None:
    p = Path("templates") / "reminder.txt"
    if p.exists():
        print("  templates/reminder.txt      exists")
        return
    p.write_text(
        "Hallo $NAME,\n\n"
        "dies ist eine Erinnerung an deinen Termin zur Studie $STUDYNAME "
        "morgen am $DATE um $TIME Uhr.\n\n"
        "Bitte sei puenktlich. Bei Fragen melde dich gerne unter $MAIL.\n\n"
        "Viele Gruesse,\n"
        "Dein Studienteam\n",
        encoding="utf-8",
    )
    print("  templates/reminder.txt      created")


def create_csv_file(data_folder: Path) -> None:
    csv_file = data_folder / "first_mail_sended_booking_list.csv"
    if csv_file.exists():
        print("  data/first_mail_sended_booking_list.csv  exists")
        return
    csv_file.write_text(",Name,Date,E-Mail\n", encoding="utf-8")
    print("  data/first_mail_sended_booking_list.csv  created")


def main() -> None:
    os.chdir(Path(__file__).parent)
    print("\nTermino setup\n=============")

    if Path("requirements.txt").exists():
        install_requirements()
    else:
        print("WARN: requirements.txt missing - skipping pip install")

    print("\nFolders:")
    data_folder = create_data_folder()
    create_templates_folder()
    create_tools_folder()

    env_data, config_data, provider = collect_user_inputs()

    print("\nWriting files:")
    write_env_file(env_data)
    write_config_json(config_data)
    create_csv_file(data_folder)
    create_first_email_template()
    create_reminder_template()

    try:
        store_secrets_interactively(provider, env_data["mail"])
    except Exception as e:
        print(f"\nWARN: keyring access failed ({e}).")
        print("      Set credentials later via:  python -m utils.secrets set")

    print("\nSetup complete. Next steps:")
    print("  1. Verify keyring:    python -m utils.secrets list")
    print("  2. If using EWS:      make sure your VPN is reachable")
    print("  3. Run the script:    python main.py")


if __name__ == "__main__":
    main()
