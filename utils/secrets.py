# -*- coding: utf-8 -*-
"""
utils.secrets
=============

Centralised secret access for the Termino script.

Why this module exists
----------------------
- Stop scattering passwords across ``sensible.env``. That file ends up
  in backups, screenshots, and git diffs more often than we'd like.
- Give one place to switch the backend: KDE Wallet on the Linux laptop,
  EncryptedKeyring on the headless Proxmox LXC. Callers don't care.

Backend selection
-----------------
The choice is driven by the environment variable ``PYTHON_KEYRING_BACKEND``,
following the python-keyring convention:

- On David's Linux laptop, nothing is set -> falls back to the OS default
  (SecretService / KDE Wallet).
- On the Proxmox LXC, set::

      PYTHON_KEYRING_BACKEND=keyrings.cryptfile.cryptfile.CryptFileKeyring
      KEYRING_CRYPTFILE_PASSWORD=<master-password>

  in the systemd EnvironmentFile.

  IMPORTANT: do NOT use ``keyrings.alt.file.EncryptedKeyring`` on the
  server - that one prompts interactively via getpass and has no
  non-interactive mode. ``keyrings.cryptfile`` was designed exactly for
  the headless case and reads the master password from the env var
  ``KEYRING_CRYPTFILE_PASSWORD``.

  pip dependencies for the server: ``keyrings.cryptfile`` and
  ``pycryptodome`` (transitive).

This module never picks the backend itself - that would couple the code to
deployment, which is exactly what we want to avoid.

Key naming convention
---------------------
Two service names are used. The split keeps Termino-specific secrets out of
the namespace that ``openconnect-sso`` and Davids existing VPN tooling use:

- ``termino-uni``     -> script-specific secrets (Termino password, uniCLOUD
                         app password, optional Yahoo app password, etc.).
- ``openconnect-sso`` -> VPN/login credentials, with the *same* key layout that
                         David's laptop scripts already use. So if you later
                         run ``openconnect-sso`` on the server too, it picks
                         up the same entries - no duplication.

The VPN keys use the email address as the keyring "username", matching the
``--user`` flag passed to ``openconnect-sso``. The TOTP entry is the same
username with a ``totp/`` prefix.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from typing import Optional

import keyring
import keyring.errors


# --- service names ------------------------------------------------------

SERVICE_TERMINO = "termino-uni"
SERVICE_VPN = "openconnect-sso"  # match Davids existing convention


# --- known keys (documented in one place so we never typo them) ---------

# Script secrets - short-lived, scope-limited, easy to revoke
TERMINO_KEYS: dict[str, str] = {
    "unicloud-app-pw": "Nextcloud app password for uniCLOUD WebDAV/CalDAV "
                       "(generate in cloud.uni-graz.at -> Settings -> Security).",
    "termino-pw": "Password for the www.termino.gv.at account.",
    "yahoo-app-pw": "Yahoo app password (only needed if a user is configured "
                    "to send via Yahoo).",
    "uni-mail-pw": "Keycloak 'Mail Password' (works ONLY for SMTP to "
                   "mailproxy.uni-graz.at - not for EWS). Kept for completeness "
                   "but not used in the current EWS-based flow.",
}

# VPN secrets - high-impact, only stored because EWS Basic Auth needs them.
# Username = email; keyed exactly like openconnect-sso expects.
VPN_KEY_PATTERN: dict[str, str] = {
    "<email>": "The user's normal Uni-Graz login password. Used by both "
               "openconnect-sso (VPN login) and exchangelib (EWS Basic Auth).",
    "totp/<email>": "TOTP shared secret in base32 (the seed, not the 6-digit "
                    "code). openconnect-sso generates the rotating code from it.",
}


# --- low-level API ------------------------------------------------------

def get_secret(key: str, service: str = SERVICE_TERMINO) -> Optional[str]:
    """Return the secret stored under ``service``/``key`` or None if missing."""
    return keyring.get_password(service, key)


def set_secret(key: str, value: str, service: str = SERVICE_TERMINO) -> None:
    """Store a secret. Overwrites any existing value silently."""
    keyring.set_password(service, key, value)


def delete_secret(key: str, service: str = SERVICE_TERMINO) -> None:
    """Remove a secret. Raises keyring.errors.PasswordDeleteError if not present."""
    keyring.delete_password(service, key)


# --- VPN-credential helpers (convenience wrappers) ----------------------

def get_uni_login_password(email: str) -> Optional[str]:
    """Fetch the Uni-Graz login password from the openconnect-sso namespace."""
    return get_secret(email, service=SERVICE_VPN)


def get_uni_totp_secret(email: str) -> Optional[str]:
    """Fetch the TOTP base32 seed from the openconnect-sso namespace."""
    return get_secret(f"totp/{email}", service=SERVICE_VPN)


def set_uni_login_password(email: str, password: str) -> None:
    set_secret(email, password, service=SERVICE_VPN)


def set_uni_totp_secret(email: str, base32_seed: str) -> None:
    set_secret(f"totp/{email}", base32_seed, service=SERVICE_VPN)


# --- diagnostics --------------------------------------------------------

def backend_info() -> dict[str, str]:
    """Return information about the active keyring backend for debugging."""
    kr = keyring.get_keyring()
    return {
        "name": kr.name,
        "class": f"{type(kr).__module__}.{type(kr).__name__}",
    }


def all_known_keys_status() -> dict[str, dict[str, str]]:
    """
    Return which known keys are set and which are missing.

    The actual secret values are NEVER returned - only presence/absence.
    Useful for ``python -m utils.secrets list``.
    """
    out: dict[str, dict[str, str]] = {}
    for key in TERMINO_KEYS:
        out[f"{SERVICE_TERMINO}/{key}"] = {
            "present": str(get_secret(key) is not None),
            "description": TERMINO_KEYS[key],
        }
    return out


# --- CLI ----------------------------------------------------------------

def _cli_set(args: argparse.Namespace) -> int:
    """Interactive setter: prompts for each requested key without echoing."""
    if args.email and not args.vpn and not args.termino:
        # If only --email is given, set the VPN credentials
        args.vpn = True

    if not (args.vpn or args.termino):
        # Default: do both
        args.vpn = bool(args.email)
        args.termino = True

    if args.termino:
        print("Setting Termino-script secrets:")
        print("(Type the value at each prompt, or just press Enter to keep the current one.)")
        for key, descr in TERMINO_KEYS.items():
            current = "already set" if get_secret(key) else "not set"
            print(f"\n  {key}  [{current}]")
            print(f"    {descr}")
            value = getpass.getpass(f"    new value (Enter to keep): ")
            if value:
                set_secret(key, value)
                print(f"    OK {key} stored.")
            else:
                print(f"    (kept)")

    if args.vpn:
        if not args.email:
            print("ERROR: --email required when setting VPN credentials.", file=sys.stderr)
            return 2
        print(f"\nSetting VPN credentials for {args.email}:")
        print("(Type the value at each prompt, or just press Enter to keep the current one.)")

        current_pw = "already set" if get_uni_login_password(args.email) else "not set"
        print(f"\n  Uni login password  [{current_pw}]")
        pw = getpass.getpass(f"    new value (Enter to keep): ")
        if pw:
            set_uni_login_password(args.email, pw)
            print(f"    OK login password stored.")
        else:
            print(f"    (kept)")

        current_totp = "already set" if get_uni_totp_secret(args.email) else "not set"
        print(f"\n  TOTP secret base32  [{current_totp}]")
        totp = getpass.getpass(f"    new value (Enter to keep): ")
        if totp:
            set_uni_totp_secret(args.email, totp.replace(" ", ""))
            print(f"    OK TOTP secret stored.")
        else:
            print(f"    (kept)")

    return 0


def _cli_get(args: argparse.Namespace) -> int:
    """Print a single secret value to stdout. Use for scripting only."""
    value = get_secret(args.key, service=args.service)
    if value is None:
        print(f"NOT SET: {args.service}/{args.key}", file=sys.stderr)
        return 1
    print(value)
    return 0


def _cli_list(_args: argparse.Namespace) -> int:
    """Show backend + which known keys are set, without revealing values."""
    info = backend_info()
    print(f"keyring backend: {info['name']}")
    print(f"keyring class:   {info['class']}")
    print()
    print("Termino-script keys:")
    for entry, status in all_known_keys_status().items():
        marker = "OK" if status["present"] == "True" else "X"
        print(f"  {marker} {entry}")
    return 0


def _cli_delete(args: argparse.Namespace) -> int:
    try:
        delete_secret(args.key, service=args.service)
        print(f"deleted: {args.service}/{args.key}")
        return 0
    except keyring.errors.PasswordDeleteError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m utils.secrets",
        description="Manage credentials in the OS keyring for the Termino script.",
    )
    sub = parser.add_subparsers(dest="action", required=True)

    set_p = sub.add_parser("set", help="Interactively set secrets.")
    set_p.add_argument("--email", default=None,
                       help="Email address used as the key for VPN credentials.")
    set_p.add_argument("--vpn", action="store_true",
                       help="Set the VPN/login credentials (uni-login-pw + TOTP).")
    set_p.add_argument("--termino", action="store_true",
                       help="Set the Termino-script secrets (defaults if neither flag given).")
    set_p.set_defaults(func=_cli_set)

    get_p = sub.add_parser("get", help="Fetch a single secret (for scripting).")
    get_p.add_argument("key")
    get_p.add_argument("--service", default=SERVICE_TERMINO,
                       help=f"Service name (default: {SERVICE_TERMINO}).")
    get_p.set_defaults(func=_cli_get)

    del_p = sub.add_parser("delete", help="Remove a secret.")
    del_p.add_argument("key")
    del_p.add_argument("--service", default=SERVICE_TERMINO)
    del_p.set_defaults(func=_cli_delete)

    list_p = sub.add_parser("list", help="Show backend + which keys are set.")
    list_p.set_defaults(func=_cli_list)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
