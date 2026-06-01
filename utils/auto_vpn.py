# -*- coding: utf-8 -*-
"""
utils.auto_vpn - Optional headless VPN setup via openconnect-sso.

Why this exists
---------------
The Uni-Graz EWS mail backend (webmail.uni-graz.at) is only reachable
from the Uni-Graz network. When the script runs unattended on a Linux
server, something has to bring the VPN tunnel up before main.py and
tear it down after.

Two valid approaches exist:

1. RECOMMENDED FOR PRODUCTION: external bash wrappers (vpn_up.sh,
   vpn_down.sh) called from systemd as ExecStartPre / ExecStopPost.
   See ``docs/SERVER_VPN_SETUP.md`` for the full guide.

2. OPT-IN (this module): the script handles VPN setup itself via a
   Python context manager. Useful when you don't have systemd (Docker
   container, plain cron without unit files, manual interactive runs
   on a Linux box that needs VPN).

Both call the same underlying tools (openconnect-sso for SAML auth,
then openconnect to build the tunnel). The choice is purely about
where the orchestration lives.

Cross-platform safety
---------------------
On Windows / macOS this module refuses to act. Those platforms have
the Cisco Secure Client GUI with native MFA. utils.vpn (Phase A) still
covers them with a connectivity pre-flight warning.

Activation
----------
Add to config.json (Linux only)::

    {
        ...
        "auto_vpn": {
            "enabled": true,
            "user_email": "your-account@edu.uni-graz.at",
            "server": "univpn.uni-graz.at",
            "use_xvfb": true,
            "down_on_exit": true,
            "openconnect_path": "/usr/sbin/openconnect",
            "openconnect_sso_path": "/home/<user>/.local/bin/openconnect-sso",
            "pid_file": "/tmp/oc-termino.pid"
        }
    }

If the section is missing or ``enabled`` is False, this module is a
no-op and main.py runs as before.

Threat model
------------
sudo NOPASSWD for ``/usr/sbin/openconnect`` is required so the tunnel
bring-up can elevate. The script itself runs as a non-root user; only
the openconnect subprocess sees root. See ``docs/SERVER_VPN_SETUP.md``
for the sudoers fragment.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from typing import Optional, Tuple


class VPNError(RuntimeError):
    """auto_vpn could not bring the VPN up. Caller decides whether to abort."""


# --- platform + tool guards ---------------------------------------------

def _check_linux(operation: str) -> None:
    """Raise VPNError if we're not on Linux."""
    if sys.platform != "linux":
        raise VPNError(
            f"auto_vpn.{operation} is only supported on Linux "
            f"(detected: {sys.platform!r}). On Windows / macOS, start "
            "Cisco Secure Client manually before running the script. "
            "See README.md - VPN setup."
        )


def _check_keyring_credentials(cfg: dict) -> None:
    """Verify the keyring has VPN login PW + TOTP seed BEFORE we spawn
    openconnect-sso. Otherwise the user gets a cryptic browser-interaction
    failure instead of a clear 'run set --vpn first' message.

    Late import of utils.secrets so this module stays importable in test
    contexts where the keyring backend may not be installed.
    """
    from utils.secrets import get_uni_login_password, get_uni_totp_secret
    email = cfg["user_email"]
    if not get_uni_login_password(email):
        raise VPNError(
            f"No UGO login password in keyring for {email!r} (under the "
            "openconnect-sso namespace). Populate it first:\n"
            f"  python -m utils.secrets set --email {email} --vpn\n"
            "See README.md - Storing secrets."
        )
    if not get_uni_totp_secret(email):
        raise VPNError(
            f"No TOTP base32 seed in keyring for {email!r}. The same "
            "command sets both:\n"
            f"  python -m utils.secrets set --email {email} --vpn\n"
            "It prompts for the login PW and the TOTP seed in turn."
        )


def _resolve_tool(name: str, override_path: str = "") -> str:
    """Return the path to a CLI tool, or raise VPNError with install hint."""
    if override_path:
        if shutil.which(override_path):
            return override_path
        # configured path didn't resolve - fall through to PATH lookup
    resolved = shutil.which(name)
    if not resolved:
        raise VPNError(
            f"required tool {name!r} not found in PATH. "
            "See docs/SERVER_VPN_SETUP.md - System-Voraussetzungen."
        )
    return resolved


def is_vpn_up(server_hint: str = "univpn") -> bool:
    """Cheap check: is an openconnect process talking to the server?

    Uses pgrep, which is Linux-only. On other platforms returns False.

    For a cross-platform connectivity probe, use
    ``utils.vpn.is_vpn_connected()`` instead - that one is a TCP test
    to webmail.uni-graz.at:443 and works on every OS.
    """
    if sys.platform != "linux":
        return False
    try:
        result = subprocess.run(
            ["pgrep", "-f", f"openconnect.*{server_hint}"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# --- the two-stage VPN bring-up -----------------------------------------

def _authenticate(cfg: dict) -> Tuple[str, str, str]:
    """Run openconnect-sso --authenticate and parse HOST/COOKIE/FINGERPRINT.

    openconnect-sso uses a Qt-WebEngine browser to walk through the
    Uni-Graz Keycloak SAML flow (username + password + TOTP pick + OTP
    + consent). Credentials come from the OS keyring. The DOM selectors
    that drive the auto-fill live in ~/.config/openconnect-sso/config.toml.

    Returns the host, session cookie, and certificate fingerprint that
    the second stage (classic openconnect) needs.
    """
    sso_path = _resolve_tool(
        "openconnect-sso", cfg.get("openconnect_sso_path", "")
    )

    cmd = [
        sso_path,
        "-u", cfg["user_email"],
        "--browser-display-mode", "shown",
        "-l", "ERROR",
        "--authenticate",
    ]
    if cfg.get("use_xvfb", True):
        xvfb_path = _resolve_tool("xvfb-run")
        cmd = [
            xvfb_path,
            "--auto-servernum",
            "--server-args=-screen 0 1024x768x24",
        ] + cmd

    print("[auto_vpn] Authenticating via openconnect-sso ...", file=sys.stderr)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=180
        )
    except subprocess.TimeoutExpired:
        raise VPNError("openconnect-sso authentication timed out after 180s")

    if result.returncode != 0:
        raise VPNError(
            f"openconnect-sso failed (exit {result.returncode}). "
            f"stderr tail:\n{result.stderr[-500:].strip()}"
        )

    host = cookie = fingerprint = None
    for line in result.stdout.splitlines():
        if line.startswith("HOST="):
            host = line.split("=", 1)[1].strip()
        elif line.startswith("COOKIE="):
            cookie = line.split("=", 1)[1].strip()
        elif line.startswith("FINGERPRINT="):
            fingerprint = line.split("=", 1)[1].strip()

    if not all([host, cookie, fingerprint]):
        raise VPNError(
            "openconnect-sso did not return HOST/COOKIE/FINGERPRINT. "
            f"First 200 chars of stdout: {result.stdout[:200]!r}"
        )
    return host, cookie, fingerprint


def _start_tunnel(host: str, cookie: str, fingerprint: str, cfg: dict) -> None:
    """Spawn openconnect in the background with the given SAML cookie."""
    oc_path = _resolve_tool("openconnect", cfg.get("openconnect_path", ""))
    pid_file = cfg.get("pid_file", "/tmp/oc-termino.pid")

    cmd = [
        "sudo", "-n", oc_path,
        "--servercert", fingerprint,
        "--cookie", cookie,
        "--background",
        "--pid-file", pid_file,
        "--no-dtls",
        host,
    ]
    print("[auto_vpn] Starting tunnel ...", file=sys.stderr)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )
    except subprocess.TimeoutExpired:
        raise VPNError("openconnect tunnel-start timed out after 30s")

    if result.returncode != 0:
        raise VPNError(
            f"openconnect failed (exit {result.returncode}). "
            f"stderr tail:\n{result.stderr[-500:].strip()}\n\n"
            "Hint: is the sudoers NOPASSWD rule for openconnect in place? "
            "See docs/SERVER_VPN_SETUP.md - Sudoers-Regel."
        )

    for i in range(10):
        time.sleep(1)
        check = subprocess.run(
            ["ip", "link", "show", "tun0"], capture_output=True
        )
        if check.returncode == 0:
            print(f"[auto_vpn] tun0 is up (after {i + 1}s)", file=sys.stderr)
            return
    raise VPNError("tun0 did not come up within 10s after openconnect spawn")


def _stop_tunnel(server_hint: str = "univpn") -> None:
    """Kill openconnect processes for the configured server. Best effort."""
    if sys.platform != "linux":
        return
    try:
        subprocess.run(
            ["sudo", "-n", "/usr/bin/pkill",
             "-f", f"openconnect.*{server_hint}"],
            capture_output=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        # We tried, log and move on. The tunnel will time out eventually.
        print("[auto_vpn] WARN: pkill openconnect timed out", file=sys.stderr)


# --- public context manager ---------------------------------------------

@contextmanager
def auto_vpn_session(config_data: dict):
    """Context manager that brings the VPN up around the wrapped block.

    No-op when ``config_data['auto_vpn'].enabled`` is not True. In that
    case the with-block runs unchanged and the caller doesn't need any
    new dependencies.

    Usage in main.py::

        from utils.auto_vpn import auto_vpn_session, VPNError
        ...
        try:
            with auto_vpn_session(config_data):
                with make_sender(provider_cfg) as sender:
                    _run_workflow(...)
        except VPNError as exc:
            print(f"VPN setup failed: {exc}", file=sys.stderr)
            sys.exit(2)

    Cleanup is guaranteed on normal exit AND on exception thrown from
    inside the with-block - but only if WE brought the tunnel up. If
    the tunnel was already running when we entered (someone else
    started it), we leave it alone on exit.
    """
    cfg = (config_data.get("auto_vpn") or {})
    if not cfg.get("enabled"):
        yield None
        return

    _check_linux("auto_vpn_session")

    if not cfg.get("user_email"):
        raise VPNError(
            "auto_vpn.user_email is required when auto_vpn.enabled is true"
        )

    server = cfg.get("server", "univpn.uni-graz.at")
    server_hint = server.split(".")[0]
    was_already_up = is_vpn_up(server_hint)

    if not was_already_up:
        # Pre-check keyring BEFORE we burn 30+ seconds spawning Qt-WebEngine
        # only to fail with a confusing browser error.
        _check_keyring_credentials(cfg)
        host, cookie, fingerprint = _authenticate(cfg)
        _start_tunnel(host, cookie, fingerprint, cfg)
        # Sensitive: drop the cookie reference from this frame. The
        # subprocess argv had it (visible in /proc/<pid>/cmdline) but
        # that process has already exited; we just don't want it in
        # this frame's locals any longer than necessary.
        del cookie

    try:
        yield True
    finally:
        if cfg.get("down_on_exit", True) and not was_already_up:
            print("[auto_vpn] Closing tunnel", file=sys.stderr)
            _stop_tunnel(server_hint)
