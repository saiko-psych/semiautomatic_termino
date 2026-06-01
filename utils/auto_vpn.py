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

import os
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
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
    """Spawn openconnect in the background with the given SAML cookie.

    Critical: openconnect --background daemonizes (fork, parent exits,
    daemon-child lives on). The daemon-child INHERITS any pipes opened
    by the parent subprocess. If we used capture_output=True here,
    subprocess.run would wait for EOF on those pipes - which never
    arrives because the daemon-child is still holding them open - and
    we would always hit the timeout even though the tunnel came up
    cleanly. See docs/AUTO-VPN-TEST-REPORT.md, Befund 2 in the test
    report on commit ae99621.

    The fix is three-fold:
    - stdin/stdout/stderr=DEVNULL so the daemon-child has no pipes to
      inherit; subprocess.run returns the moment the parent exits.
    - start_new_session=True so openconnect lives in its own process
      group, fully detached from Python.
    - Verify success by polling the PID-file rather than trusting the
      return code (which under --background does not reflect the daemon
      state anyway).
    """
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
        subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
            start_new_session=True,
            check=False,
        )
    except subprocess.TimeoutExpired:
        # Detached + DEVNULL should make this unreachable, but if a
        # sudoers misconfiguration makes sudo block on a password prompt
        # we still want a clean error.
        raise VPNError(
            "openconnect spawn timed out after 15s. "
            "Most likely the sudoers NOPASSWD rule is missing - sudo is "
            "prompting for a password and blocking. "
            "See docs/SERVER_VPN_SETUP.md - Sudoers-Regel."
        )

    # Active verification via PID-file. openconnect writes its daemon
    # PID here once it has forked. If the PID-file never appears the
    # spawn failed (typically auth-cookie expired or sudoers wrong).
    pid_path = Path(pid_file)
    for _ in range(10):
        if pid_path.exists():
            try:
                pid = int(pid_path.read_text().strip())
                if Path(f"/proc/{pid}").is_dir():
                    break
            except (ValueError, OSError):
                pass
        time.sleep(1)
    else:
        raise VPNError(
            f"openconnect did not register a running PID at {pid_file} "
            "within 10s. Check /var/log/auth.log or run the same "
            "openconnect command manually to diagnose."
        )

    # PID exists - now wait for tun0 to actually come up (kernel-side
    # interface creation lags the daemon spawn by a beat).
    for i in range(10):
        time.sleep(1)
        check = subprocess.run(
            ["ip", "link", "show", "tun0"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if check.returncode == 0:
            print(f"[auto_vpn] tun0 is up (after {i + 1}s)", file=sys.stderr)
            return
    raise VPNError("tun0 did not come up within 10s after openconnect spawn")


def _stop_tunnel(server_hint: str = "univpn") -> None:
    """Kill openconnect processes for the configured VPN server.

    Mirrors the production vpn_down.sh strategy because the deployed
    sudoers rule for the termino user is very tight:

        NOPASSWD: /usr/sbin/openconnect,
                  /usr/bin/killall openconnect,
                  /usr/bin/pkill openconnect,
                  /bin/kill

    sudo requires EXACT argument matches, so `sudo pkill -f <pattern>`
    is rejected by sudoers even though `sudo pkill openconnect` is
    allowed. The old implementation used the -f form and failed silently,
    leaving the tunnel running. See docs/AUTO-VPN-TEST-REPORT.md,
    Befund 4 (discovered during the 2026-06-01 CT-131 verify of the
    pipe-detach fix).

    Strategy now:
    1. pgrep (unprivileged) for openconnect PIDs matching the server hint
    2. `sudo /bin/kill <pid>` per PID (sudoers allows /bin/kill any args)
    3. Failsafe: `sudo /usr/bin/pkill openconnect` (exact sudoers match)
    """
    if sys.platform != "linux":
        return

    pattern = f"openconnect.*{server_hint}"

    # Step 1: find target PIDs. pgrep is unprivileged.
    pids = []
    try:
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
        pids = [p.strip() for p in result.stdout.splitlines() if p.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        # pgrep missing or hung - fall through to failsafe.
        pass

    # Step 2: kill per PID. sudoers allows /bin/kill with any args.
    for pid in pids:
        try:
            subprocess.run(
                ["sudo", "-n", "/bin/kill", pid],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        except subprocess.TimeoutExpired:
            print(f"[auto_vpn] WARN: sudo kill {pid} timed out",
                  file=sys.stderr)

    # Brief settle window so kernel can release tun0 + write pidfile delete.
    time.sleep(1)

    # Step 3: failsafe if anything survived the per-PID round. Uses the
    # exact `sudo /usr/bin/pkill openconnect` form the sudoers rule
    # allows; intentionally has no -f or pattern so the match works.
    try:
        still = subprocess.run(
            ["pgrep", "-f", pattern],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        if still.returncode == 0:
            print("[auto_vpn] WARN: stragglers detected - using failsafe pkill",
                  file=sys.stderr)
            subprocess.run(
                ["sudo", "-n", "/usr/bin/pkill", "openconnect"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


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
        try:
            host, cookie, fingerprint = _authenticate(cfg)
            _start_tunnel(host, cookie, fingerprint, cfg)
        except BaseException:
            # Critical: if _start_tunnel raises mid-flight, an
            # openconnect daemon may already be running. Without this
            # cleanup it would survive as a zombie and the next
            # vpn_up.sh pgrep idempotency check would treat it as
            # "already up", silently using an expired auth-cookie.
            # See docs/AUTO-VPN-TEST-REPORT.md, Befund 3.
            print("[auto_vpn] Setup failed - cleaning up partial tunnel",
                  file=sys.stderr)
            _stop_tunnel(server_hint)
            raise
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
