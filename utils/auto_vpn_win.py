# -*- coding: utf-8 -*-
"""
utils.auto_vpn_win - Windows port of the headless VPN setup.

Mirrors utils.auto_vpn (Linux) function-for-function, with Windows
adjustments verified against the live CT-test on David's laptop on
2026-06-01:

  * openconnect-sso calls `sudo openconnect` internally - on Windows
    there is no sudo (Win11 has an optional one but it's off by default).
    So we split: openconnect-sso --authenticate ONLY (returns
    HOST/COOKIE/FINGERPRINT), then openconnect.exe directly (admin
    PowerShell already has the rights).
  * Qt-WebEngine "hidden" mode crashes with D3D errors on Windows with
    dedicated GPU. `shown` + saved Credentials + DOM-selectors in
    config.toml gives functionally-headless auto-fill (3 seconds).
  * Wintun adapter creation needs Administrator. We surface a clear
    error if the script isn't elevated.
  * Cisco Secure Client (csc_vpnagent) and Mullvad (MullvadVPN)
    services conflict with openconnect for routing. We stop them
    before tunnel-up and start them after tunnel-down (opt-in).

Activation (config.json)::

    {
        "auto_vpn": {
            "enabled": true,
            "user_email": "your-account@edu.uni-graz.at",
            "server": "univpn.uni-graz.at",
            "openconnect_path": "C:/Program Files/OpenConnect-GUI/openconnect.exe",
            "openconnect_sso_path": "C:/Users/<you>/.local/bin/openconnect-sso.exe",
            "stop_cisco_during_run": true,
            "stop_mullvad_during_run": true,
            "down_on_exit": true
        }
    }

If the section is missing or ``enabled`` is False, this module is a
no-op and main.py runs unchanged.

Verification
------------
Verified live on 2026-06-01:
  - openconnect.exe v9.12 from openconnect-gui-1.6.2-win64
  - openconnect-sso 0.8.1 (PyPI) installed via uv tool + setuptools<70 + PyQt6
  - config.toml with Uni-Graz Keycloak DOM selectors at
    ~/.config/openconnect-sso/config.toml (UTF-8 *without* BOM)
  - Tunnel up in ~3 seconds, webmail.uni-graz.at reachable via VPN-IP
  - Strg-C cleans up Wintun adapter sauber
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional, Tuple

# Reuse the same exception so callers can `except VPNError:` regardless
# of platform.
from utils.auto_vpn import VPNError


# --- platform + privilege guards ----------------------------------------

def _check_windows(operation: str) -> None:
    """Raise VPNError if not on Windows."""
    if sys.platform != "win32":
        raise VPNError(
            f"auto_vpn_win.{operation} is only supported on Windows "
            f"(detected: {sys.platform!r}). On Linux use utils.auto_vpn, "
            "on macOS start Cisco Secure Client manually."
        )


def _is_admin() -> bool:
    """Return True if the current process has Administrator rights.

    On non-Windows always returns False (caller should have guarded with
    _check_windows first anyway).
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _check_admin() -> None:
    """Raise VPNError with a clear message if not elevated."""
    if not _is_admin():
        raise VPNError(
            "Wintun adapter creation requires Administrator privileges. "
            "Right-click PowerShell -> 'Run as Administrator', then re-run. "
            "See docs/WINDOWS_SETUP.md - Administrator-Voraussetzung."
        )


# --- tool resolution + keyring pre-check --------------------------------

def _resolve_tool(name: str, override_path: str = "") -> str:
    """Return the path to a CLI tool, or raise VPNError with install hint."""
    if override_path:
        if os.path.exists(override_path) and os.access(override_path, os.X_OK):
            return override_path
        # Configured path didn't resolve - fall through to PATH lookup.
    resolved = shutil.which(name)
    if not resolved:
        raise VPNError(
            f"required tool {name!r} not found in PATH "
            "and no valid openconnect_path / openconnect_sso_path "
            "in config.json. See docs/WINDOWS_SETUP.md."
        )
    return resolved


def _check_keyring_credentials(cfg: dict) -> None:
    """Verify the keyring has VPN login PW + TOTP seed before spawning
    openconnect-sso. Otherwise the Qt-WebEngine browser pops up but
    auto-fill silently does nothing.

    Late import to keep the module importable in test contexts without
    a keyring backend.
    """
    from utils.secrets import get_uni_login_password, get_uni_totp_secret
    email = cfg["user_email"]
    if not get_uni_login_password(email):
        raise VPNError(
            f"No UGO login password in Windows Credential Manager for "
            f"{email!r} (under the openconnect-sso namespace). "
            f"Run setup-windows.ps1 or:\n"
            f"  python -m utils.secrets set --email {email} --vpn"
        )
    if not get_uni_totp_secret(email):
        raise VPNError(
            f"No TOTP base32 seed in Windows Credential Manager for "
            f"{email!r}. Run setup-windows.ps1 or:\n"
            f"  python -m utils.secrets set --email {email} --vpn"
        )


def is_vpn_up(server_hint: str = "univpn") -> bool:
    """Cheap check: is an openconnect process running?

    Windows-only. On non-Windows returns False so cross-platform
    callers don't need a guard.
    """
    if sys.platform != "win32":
        return False
    try:
        # tasklist /FI matches process names. openconnect.exe is the
        # process name regardless of which gateway it connects to,
        # so server_hint is unused on Windows (it's there to keep the
        # same signature as utils.auto_vpn.is_vpn_up).
        #
        # encoding="utf-8" + errors="replace" because Windows default
        # codepage is cp1252 and tasklist can emit bytes outside it,
        # which would otherwise crash subprocess._readerthread with
        # UnicodeDecodeError and leave result.stdout=None.
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq openconnect.exe", "/NH"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        # Defensive None-check + tasklist prints "INFO: No tasks..."
        # when nothing matches, and the process name otherwise.
        return bool(result.stdout) and "openconnect.exe" in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


# --- Cisco / Mullvad coexistence ----------------------------------------

def _service_status(name: str) -> Optional[str]:
    """Return the current Windows-service status, or None if unknown."""
    try:
        result = subprocess.run(
            ["sc", "query", name],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        out = result.stdout or ""
        if "RUNNING" in out:
            return "RUNNING"
        if "STOPPED" in out:
            return "STOPPED"
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _stop_conflicting_services(cfg: dict) -> List[str]:
    """Stop services that would compete with openconnect for routing.

    Returns the list of service names we *did* stop, so the caller can
    restart them on exit (only the ones we touched).
    """
    stopped = []
    targets = []
    if cfg.get("stop_cisco_during_run", True):
        targets.append("csc_vpnagent")
    if cfg.get("stop_mullvad_during_run", True):
        targets.append("MullvadVPN")
    for svc in targets:
        if _service_status(svc) == "RUNNING":
            print(f"[auto_vpn_win] Stopping {svc} for tunnel duration",
                  file=sys.stderr)
            try:
                subprocess.run(
                    ["net", "stop", svc],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=15,
                )
                stopped.append(svc)
            except subprocess.TimeoutExpired:
                print(f"[auto_vpn_win] WARN: stop {svc} timed out",
                      file=sys.stderr)
    return stopped


def _restart_services(services: List[str]) -> None:
    """Restart services we previously stopped."""
    for svc in services:
        print(f"[auto_vpn_win] Restarting {svc}", file=sys.stderr)
        try:
            subprocess.run(
                ["net", "start", svc],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
            )
        except subprocess.TimeoutExpired:
            print(f"[auto_vpn_win] WARN: start {svc} timed out",
                  file=sys.stderr)


# --- SAML auth + tunnel bring-up ---------------------------------------

def _authenticate(cfg: dict) -> Tuple[str, str, str]:
    """Run openconnect-sso --authenticate and parse HOST/COOKIE/FINGERPRINT.

    Identical contract to utils.auto_vpn._authenticate(). DOM selectors
    for the Uni-Graz Keycloak SAML flow live in
    %USERPROFILE%\\.config\\openconnect-sso\\config.toml - this file
    MUST be UTF-8 *without* BOM (PowerShell `Set-Content -Encoding UTF8`
    writes a BOM that the toml parser rejects with "invalid character"
    - lost an hour on this during the live test).
    """
    # Try `_win` override first (config.example.json uses this so Linux
    # and Windows users can share a config.json without stepping on
    # each other), fall back to the generic key, then to PATH.
    sso_override = cfg.get("openconnect_sso_path_win") or cfg.get("openconnect_sso_path", "")
    sso_path = _resolve_tool("openconnect-sso", sso_override)

    cmd = [
        sso_path,
        "-u", cfg["user_email"],
        # `shown` instead of `hidden` because Qt-WebEngine's hidden mode
        # crashes with D3D context errors on Windows. With Credentials
        # in the keyring + selectors in config.toml the browser fills
        # itself and closes in ~2 seconds, so it's functionally headless.
        "--browser-display-mode", "shown",
        "-l", "ERROR",
        "--authenticate",
    ]
    authgroup = cfg.get("authgroup", "")
    if authgroup:
        cmd.extend(["--authgroup", authgroup])

    print("[auto_vpn_win] Authenticating via openconnect-sso ...",
          file=sys.stderr)
    try:
        result = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        raise VPNError("openconnect-sso authentication timed out after 180s")

    stdout = result.stdout or ""
    stderr = result.stderr or ""
    if result.returncode != 0:
        raise VPNError(
            f"openconnect-sso failed (exit {result.returncode}). "
            f"stderr tail:\n{stderr[-500:].strip()}"
        )

    host = cookie = fingerprint = None
    for line in stdout.splitlines():
        if line.startswith("HOST="):
            host = line.split("=", 1)[1].strip()
        elif line.startswith("COOKIE="):
            cookie = line.split("=", 1)[1].strip()
        elif line.startswith("FINGERPRINT="):
            fingerprint = line.split("=", 1)[1].strip()

    if not all([host, cookie, fingerprint]):
        raise VPNError(
            "openconnect-sso did not return HOST/COOKIE/FINGERPRINT. "
            f"First 200 chars of stdout: {stdout[:200]!r}"
        )
    return host, cookie, fingerprint


def _start_tunnel(host: str, cookie: str, fingerprint: str,
                  cfg: dict) -> subprocess.Popen:
    """Spawn openconnect.exe in the background and return the Popen handle.

    On Linux we use `sudo openconnect --background --pid-file ...`. On
    Windows we run as Administrator already (Wintun requires it), so no
    sudo. openconnect.exe doesn't support --background cleanly on
    Windows in the same way, so we spawn it as a long-running child
    process and keep the handle for teardown.
    """
    _check_admin()
    oc_override = cfg.get("openconnect_path_win") or cfg.get("openconnect_path", "")
    oc_path = _resolve_tool("openconnect", oc_override)

    cmd = [
        oc_path,
        "--servercert", fingerprint,
        "--cookie", cookie,
        "--no-dtls",
        host,
    ]
    print("[auto_vpn_win] Starting openconnect.exe ...", file=sys.stderr)
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        # New process group so Ctrl-C in our process doesn't kill the
        # tunnel prematurely - we control teardown via terminate().
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )

    # Wait for vpnc-script-win.js to finish configuring DNS + routes.
    # The key marker is "Legacy IP route configuration done." - that's
    # printed AFTER openconnect has set up Wintun, configured the DNS
    # servers, and added the split-include routes. If we return earlier
    # (e.g. on the "Configured as ..." line) the workflow can race
    # against DNS being set up and the very first DNS lookup fails with
    # "Name or service not known", which is what happened during the
    # 2026-06-01 21:00 live test.
    #
    # If we never see the marker within 30s, give up. We also still
    # detect "Configured as" so we can warn that the route config is
    # taking longer than expected.
    deadline = time.time() + 30
    saw_configured = False
    while time.time() < deadline:
        if proc.poll() is not None:
            # Process exited - read whatever output it produced.
            try:
                tail = proc.stdout.read() if proc.stdout else ""
            except Exception:
                tail = ""
            raise VPNError(
                f"openconnect.exe exited prematurely (code {proc.returncode}). "
                f"tail:\n{tail[-500:]}"
            )
        line = ""
        try:
            if proc.stdout:
                line = proc.stdout.readline()
        except Exception:
            line = ""
        if line:
            print(f"[openconnect] {line.rstrip()}", file=sys.stderr)
            if "Configured as" in line or "Connected as" in line:
                saw_configured = True
            if "route configuration done" in line:
                # All DNS + routes set up. Now we need to keep draining
                # stdout in the background so the openconnect-process
                # doesn't block on a full pipe (DPD pings + keepalive
                # write to stdout continuously).
                _spawn_stdout_drainer(proc)
                return proc
            if "Access denied" in line:
                _terminate_proc(proc)
                raise VPNError(
                    "openconnect.exe got 'Access denied' creating the "
                    "Wintun adapter despite running as Administrator. "
                    "Reboot and retry, or check the Windows Event Log."
                )
        else:
            time.sleep(0.2)

    # Timeout. If we at least saw "Configured as" the tunnel is half-up.
    _terminate_proc(proc)
    if saw_configured:
        raise VPNError(
            "openconnect.exe set up the tunnel but vpnc-script-win.js "
            "never finished route configuration within 30s. DNS lookups "
            "would race against the workflow start - aborting."
        )
    raise VPNError(
        "openconnect.exe did not report 'Configured as ...' within 30s"
    )


def _spawn_stdout_drainer(proc: subprocess.Popen) -> None:
    """Drain openconnect.exe's stdout in a background daemon thread.

    openconnect prints DPD/keepalive activity periodically. If we leave
    stdout=PIPE unread, the OS pipe buffer fills (~64KB on Windows) and
    openconnect blocks on its next write, freezing the tunnel.
    """
    import threading

    def _drain() -> None:
        try:
            if not proc.stdout:
                return
            for line in iter(proc.stdout.readline, ""):
                if not line:
                    break
                # Quiet: only echo non-empty lines, prefixed.
                print(f"[openconnect] {line.rstrip()}", file=sys.stderr)
        except Exception:
            pass

    t = threading.Thread(target=_drain, daemon=True, name="openconnect-drain")
    t.start()


def _terminate_proc(proc: subprocess.Popen) -> None:
    """Best-effort tunnel teardown via Ctrl-C-style signal, then kill."""
    if proc.poll() is not None:
        return
    try:
        # On Windows, sending CTRL_BREAK_EVENT to the new process group
        # is the cleanest way to tell openconnect to disconnect.
        if sys.platform == "win32":
            CTRL_BREAK = getattr(__import__("signal"), "CTRL_BREAK_EVENT", None)
            if CTRL_BREAK is not None:
                proc.send_signal(CTRL_BREAK)
            else:
                proc.terminate()
        else:
            proc.terminate()
    except Exception:
        # Fall through to kill.
        pass

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def _stop_tunnel_by_proc(proc: Optional[subprocess.Popen]) -> None:
    """Stop the openconnect.exe instance we spawned."""
    if sys.platform != "win32":
        return
    if proc is not None:
        _terminate_proc(proc)
    # Belt-and-braces: kill any stray openconnect.exe that survived.
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "openconnect.exe"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


# --- public context manager ---------------------------------------------

@contextmanager
def auto_vpn_session_win(config_data: dict):
    """Context manager: open VPN tunnel around the wrapped block.

    Mirrors utils.auto_vpn.auto_vpn_session() so the cross-platform
    factory utils.vpn_provider.make_vpn_session() can pick either
    transparently.

    No-op when config_data['auto_vpn'].enabled is not True.
    """
    cfg = (config_data.get("auto_vpn") or {})
    if not cfg.get("enabled"):
        yield None
        return

    _check_windows("auto_vpn_session_win")

    if not cfg.get("user_email"):
        raise VPNError(
            "auto_vpn.user_email is required when auto_vpn.enabled is true"
        )

    server = cfg.get("server", "univpn.uni-graz.at")
    server_hint = server.split(".")[0]
    was_already_up = is_vpn_up(server_hint)

    proc: Optional[subprocess.Popen] = None
    stopped_services: List[str] = []

    if not was_already_up:
        _check_keyring_credentials(cfg)
        # Stop conflicting VPN services *before* we authenticate, in
        # case Mullvad's routing would have masked the SAML POST.
        stopped_services = _stop_conflicting_services(cfg)
        try:
            host, cookie, fingerprint = _authenticate(cfg)
            proc = _start_tunnel(host, cookie, fingerprint, cfg)
        except BaseException:
            # Symmetric with Linux: clean up if we crashed mid-setup.
            print("[auto_vpn_win] Setup failed - cleaning up partial tunnel",
                  file=sys.stderr)
            _stop_tunnel_by_proc(proc)
            _restart_services(stopped_services)
            raise
        # Sensitive: drop the cookie reference from this frame.
        del cookie

    try:
        yield True
    finally:
        if cfg.get("down_on_exit", True) and not was_already_up:
            print("[auto_vpn_win] Closing tunnel", file=sys.stderr)
            _stop_tunnel_by_proc(proc)
            _restart_services(stopped_services)


# --- standalone CLI -----------------------------------------------------
# Lets the user bring the VPN up/down from PowerShell without touching
# main.py. Useful for "I just need the tunnel" workflows the user
# explicitly asked for.

def _load_config(path: str = "config.json") -> dict:
    import json
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _cli_up(args) -> int:
    cfg = _load_config(args.config)
    cfg.setdefault("auto_vpn", {})
    cfg["auto_vpn"]["enabled"] = True
    print("[auto_vpn_win] CLI mode: bringing tunnel up", file=sys.stderr)
    try:
        with auto_vpn_session_win(cfg):
            print("[auto_vpn_win] Tunnel is up. Press Ctrl-C to disconnect.",
                  file=sys.stderr)
            try:
                while True:
                    time.sleep(60)
            except KeyboardInterrupt:
                print("\n[auto_vpn_win] Ctrl-C received, tearing down",
                      file=sys.stderr)
    except VPNError as exc:
        print(f"[auto_vpn_win] FAIL: {exc}", file=sys.stderr)
        return 2
    return 0


def _cli_status(args) -> int:
    if is_vpn_up():
        print("openconnect.exe is RUNNING")
        return 0
    print("openconnect.exe is NOT running")
    return 1


def _cli_down(args) -> int:
    print("[auto_vpn_win] CLI mode: tearing down any running tunnel",
          file=sys.stderr)
    _stop_tunnel_by_proc(None)
    _restart_services(["csc_vpnagent", "MullvadVPN"])
    return 0


def main_cli() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        prog="python -m utils.auto_vpn_win",
        description="Stand-alone Uni-Graz VPN connect/disconnect for Windows.",
    )
    parser.add_argument("--config", default="config.json",
                        help="Path to config.json (default: config.json in cwd)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("up", help="Bring tunnel up and block until Ctrl-C")
    sub.add_parser("down", help="Tear down a running tunnel + restart Cisco/Mullvad")
    sub.add_parser("status", help="Print whether openconnect.exe is running")
    args = parser.parse_args()

    dispatch = {"up": _cli_up, "down": _cli_down, "status": _cli_status}
    return dispatch[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main_cli())
