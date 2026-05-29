# -*- coding: utf-8 -*-
"""
tools/migrate_env_to_keyring.py
===============================

One-shot migration for the single-user Termino setup.

What it does
------------
1. Reads ``sensible.env`` in the repo root.
2. For each secret key it knows about, stores the value in the OS keyring.
3. Rewrites ``sensible.env`` so it no longer contains the secrets — only
   the non-secret values (mail address, spreadsheet URL, etc.).
4. Backs the original up to ``sensible.env.pre-keyring.bak``.

What it does NOT do
-------------------
- Set the Uni-Graz login password or TOTP secret. Those never lived in
  ``sensible.env``. Use::

      python -m utils.secrets set --email your-mail@your-uni.at --vpn

- Edit ``config.json`` — the choice of mail provider (yahoo vs. uni-graz-ews)
  is a manual decision (default stays Yahoo if you don't change config.json).
- Touch ``data/``, ``templates/``, or ``session.json``.

Run it
------
::

    python tools/migrate_env_to_keyring.py            # do the migration
    python tools/migrate_env_to_keyring.py --dry-run  # show what would happen

Idempotent
----------
Running twice is safe: the second run sees that the secret keys are no
longer in ``sensible.env`` and stops with "nothing to migrate".
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.secrets import set_secret  # noqa: E402


# env-key  →  keyring-key under service "termino-uni"
SECRET_KEYS_TO_MIGRATE: dict[str, str] = {
    "app_password_mail": "yahoo-app-pw",
    "password_termino": "termino-pw",
    # password_mail is the legacy Yahoo account password. mail_senders.py
    # uses app_password_mail for auth, so we don't migrate password_mail —
    # we just warn and drop it.
}

NON_SECRET_KEYS: set[str] = {
    "mail",
    "username_termino",
    "google_spreadsheet_url",
}

NON_SECRET_PREFIXES: tuple[str, ...] = (
    "google_spreadsheet_url",   # also catches future _x suffix variants
    "unicloud_",                # future-proof
)


def parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out


def is_secret_key(key: str) -> bool:
    return key in SECRET_KEYS_TO_MIGRATE


def is_keep_key(key: str) -> bool:
    if key in NON_SECRET_KEYS:
        return True
    return any(key.startswith(p) for p in NON_SECRET_PREFIXES)


def migrate(env_file: Path, *, dry_run: bool) -> int:
    """Migrate one sensible.env. Returns the number of secrets moved."""
    if not env_file.exists():
        print(f"sensible.env not found at {env_file} — nothing to do")
        return 0

    print(f"Processing {env_file}")
    entries = parse_env_file(env_file)

    secrets_to_move: dict[str, str] = {}
    keep: dict[str, str] = {}
    unknown: dict[str, str] = {}
    for k, v in entries.items():
        if is_secret_key(k):
            if v:
                secrets_to_move[k] = v
            else:
                print(f"  - {k}: empty, skipping")
        elif is_keep_key(k):
            keep[k] = v
        elif k == "password_mail":
            # Legacy Yahoo account password — known, intentionally dropped.
            print(f"  ! password_mail: legacy field (mail_senders uses "
                  f"app_password_mail only) — NOT migrated, will be removed")
        else:
            unknown[k] = v

    if not secrets_to_move:
        print(f"  no secrets to migrate (already done?)")
    else:
        for env_key, value in secrets_to_move.items():
            keyring_key = SECRET_KEYS_TO_MIGRATE[env_key]
            if dry_run:
                print(f"  would store: keyring['termino-uni/{keyring_key}'] "
                      f"= <{len(value)} chars from {env_key}>")
            else:
                set_secret(keyring_key, value)
                print(f"  ✓ stored: keyring['termino-uni/{keyring_key}'] "
                      f"(from {env_key})")

    if unknown:
        print(f"  unknown keys preserved as-is in sensible.env:")
        for k in unknown:
            print(f"    - {k}")

    # Rewrite env file (keep + unknown). Drop password_mail and the migrated
    # secrets — they are now in the keyring (or intentionally gone).
    keep.update(unknown)
    new_lines = [
        "# sensible.env — non-secret values only.",
        "# Secrets live in the OS keyring; see utils/secrets.py.",
        "# Run `python -m utils.secrets list` to see which keys are set.",
        "",
    ]
    for k, v in keep.items():
        new_lines.append(f"{k}={v}")
    new_content = "\n".join(new_lines) + "\n"

    if dry_run:
        print(f"  would rewrite {env_file} ({len(keep)} non-secret entries)")
        print(f"  preview:")
        for line in new_lines[:15]:
            print(f"    {line}")
        return len(secrets_to_move)

    backup = env_file.with_suffix(".env.pre-keyring.bak")
    if backup.exists():
        print(f"  ! backup already exists at {backup} — leaving it alone")
    else:
        env_file.rename(backup)
        print(f"  ✓ backed up old env to {backup}")

    env_file.write_text(new_content, encoding="utf-8")
    print(f"  ✓ rewrote {env_file} ({len(keep)} entries, secrets gone)")

    return len(secrets_to_move)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Migrate sensible.env passwords into the OS keyring."
    )
    parser.add_argument(
        "--env-file",
        default="sensible.env",
        help="Path to sensible.env (default: ./sensible.env)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen, don't write anything.",
    )
    args = parser.parse_args(argv)

    env_file = Path(args.env_file).resolve()
    print(f"sensible.env: {env_file}")
    if args.dry_run:
        print("DRY RUN — nothing will be written.")
    print()

    moved = migrate(env_file, dry_run=args.dry_run)

    print()
    if args.dry_run:
        print(f"DRY RUN: would have moved {moved} secrets.")
        print("Re-run without --dry-run to actually do it.")
    else:
        print(f"DONE: moved {moved} secrets into keyring.")
        print("Next: `python -m utils.secrets list` to verify.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
