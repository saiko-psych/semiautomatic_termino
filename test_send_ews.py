# -*- coding: utf-8 -*-
"""
test_send_ews.py - send one test mail to yourself via UniGrazEwsSender.

Run from the project root with the Uni VPN active:

    # Uses the mail_provider.username from config.json by default:
    python test_send_ews.py

    # Or pass the address explicitly:
    python test_send_ews.py --email your-mail@your-uni.at

Uses the same code path that main.py uses for reminders. If this works,
the EWS sender is fully functional.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from utils.mail_senders import make_sender, OutgoingMail


def _email_from_config() -> str | None:
    """Read mail_provider.username from config.json if present."""
    try:
        cfg = json.loads(Path("config.json").read_text(encoding="utf-8"))
        return cfg.get("mail_provider", {}).get("username")
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--email",
        default=_email_from_config(),
        help="EWS address to send from/to. Defaults to "
             "config.json -> mail_provider.username.",
    )
    args = parser.parse_args()

    if not args.email:
        print("ERROR: no email given and config.json has no "
              "mail_provider.username. Use --email <addr>.", file=sys.stderr)
        return 2

    email = args.email
    provider = {"type": "uni-graz-ews", "username": email}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"Building EWS sender for {email} ...")
    with make_sender(provider) as sender:
        print(f"Connected. Sending test mail at {now} ...")
        sender.send(OutgoingMail(
            to=email,
            subject=f"Termino EWS sender test - {now}",
            body=(
                "If you can read this, UniGrazEwsSender works end-to-end:\n"
                f"  * provider: uni-graz-ews\n"
                f"  * from   : {email}\n"
                f"  * to     : {email}\n"
                f"  * via    : webmail.uni-graz.at EWS\n"
                f"  * time   : {now}\n"
            ),
            from_address=email,
        ))
        print("Sent. Check your Posteingang AND your Gesendete-Objekte folder.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
