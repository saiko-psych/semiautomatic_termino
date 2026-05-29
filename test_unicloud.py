# -*- coding: utf-8 -*-
"""
test_unicloud.py - end-to-end check for the uniCLOUD WebDAV layer.

Run from the project root:
    python test_unicloud.py

This script does NOT need VPN — cloud.uni-graz.at is publicly reachable.
It does need the keyring entry ``unicloud-app-pw`` to be set
(generate the app password in cloud.uni-graz.at -> Settings -> Security,
then run ``python -m utils.secrets set --termino`` and enter it for
``unicloud-app-pw``).

What it does
------------
1) List the user's root directory.
2) Print the first 20 entries (no file contents).
3) Upload a tiny test file ``/.termino-test.txt`` with the current timestamp.
4) Download it back into ./test_unicloud_download.txt.
5) Verify content matches.
6) Delete the test file from uniCLOUD.

If all six steps succeed, you can trust the WebDAV layer for Excel I/O.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from utils.unicloud import (
    UniCloudClient,
    UniCloudAuthError,
    UniCloudNotFound,
    UniCloudError,
)

TEST_REMOTE = "/.termino-test.txt"
LOCAL_DOWNLOAD = Path("test_unicloud_download.txt")


def _username_from_config() -> str | None:
    """Read sheet_provider.username from config.json if present."""
    try:
        cfg = json.loads(Path("config.json").read_text(encoding="utf-8"))
        return cfg.get("sheet_provider", {}).get("username")
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--username",
        default=_username_from_config(),
        help="Nextcloud account name (NOT the email). For "
             "@edu.uni-graz.at addresses this is usually "
             "firstname.lastname_edu. Defaults to "
             "config.json -> sheet_provider.username.",
    )
    args = parser.parse_args()

    if not args.username:
        print("ERROR: no Nextcloud username given and config.json has no "
              "sheet_provider.username. Use --username <name>.", file=sys.stderr)
        return 2

    nextcloud_username = args.username
    print(f"uniCLOUD verification for user: {nextcloud_username}")
    print()

    try:
        client = UniCloudClient(username=nextcloud_username)
    except UniCloudAuthError as e:
        print(f"AUTH SETUP: {e}")
        return 1

    # 1) list root
    print("1) Listing root '/'...")
    try:
        entries = client.list("/")
    except UniCloudAuthError as e:
        print(f"   FAIL  authentication rejected: {e}")
        print("   Hint: is the Nextcloud username correct? Is the app password set?")
        return 1
    except UniCloudError as e:
        print(f"   FAIL  {e}")
        return 1
    print(f"   OK    got {len(entries)} entries (incl. the directory itself)")

    # 2) show contents
    print("\n2) First 20 entries:")
    for e in entries[:20]:
        kind = "DIR " if e.is_dir else "FILE"
        size = f"{e.size:>10}B"
        print(f"     {kind}  {size}  {e.path}")
    if len(entries) > 20:
        print(f"     ... ({len(entries) - 20} more not shown)")

    # 3) upload a tiny test file
    print(f"\n3) Uploading {TEST_REMOTE}...")
    payload = (
        f"termino-test\n"
        f"timestamp: {datetime.now().isoformat()}\n"
        f"if you can read this remotely, WebDAV PUT works.\n"
    )
    local_upload = Path("test_unicloud_upload.txt")
    local_upload.write_text(payload, encoding="utf-8")
    try:
        etag = client.upload(local_upload, TEST_REMOTE)
    except UniCloudError as e:
        print(f"   FAIL  {e}")
        return 1
    print(f"   OK    uploaded ({len(payload)} bytes, etag={etag!r})")

    # 4) download it back
    print(f"\n4) Downloading {TEST_REMOTE} -> {LOCAL_DOWNLOAD}...")
    try:
        client.download(TEST_REMOTE, LOCAL_DOWNLOAD)
    except UniCloudError as e:
        print(f"   FAIL  {e}")
        return 1
    print(f"   OK    downloaded ({LOCAL_DOWNLOAD.stat().st_size} bytes)")

    # 5) verify content
    print("\n5) Comparing content...")
    downloaded = LOCAL_DOWNLOAD.read_text(encoding="utf-8")
    if downloaded == payload:
        print("   OK    bytes match exactly")
    else:
        print(f"   sent    : {payload!r}")
        print(f"   received: {downloaded!r}")
        return 1

    # 6) clean up
    print(f"\n6) Deleting {TEST_REMOTE}...")
    try:
        client.delete(TEST_REMOTE)
    except UniCloudError as e:
        print(f"   WARN  could not delete: {e} (please remove manually)")
    else:
        print("   OK    deleted")

    # local cleanup
    local_upload.unlink(missing_ok=True)
    LOCAL_DOWNLOAD.unlink(missing_ok=True)

    print()
    print("SUCCESS - uniCLOUD WebDAV layer is functional.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
