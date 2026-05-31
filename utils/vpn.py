# -*- coding: utf-8 -*-
"""
utils.vpn - Pre-flight VPN reachability check for Uni-Graz EWS.

Why this module exists
----------------------
The EWS mail backend (`mail_provider.type: "uni-graz-ews"`) talks to
``webmail.uni-graz.at``, which is only reachable from inside the
Uni-Graz network or via the Cisco AnyConnect / Secure Client VPN. If
you run the script without the VPN active, the workflow looks fine
until the very end - then the Daily-Report mail times out with a
120-second connect error.

This module provides a fast pre-flight probe (~3s) so the user knows
RIGHT AT START whether the mail step will fail. It does not attempt to
bring the VPN up - that's deliberately out of scope for Phase A. See
SERVER_DEPLOY_PLAN.md for the Linux/Mac openconnect-with-TOTP-seed path
that Phase B will integrate.

Cross-platform
--------------
Pure stdlib ``socket`` - works identically on Linux, macOS, Windows.
No external CLI tools, no network drivers, no admin privileges.
"""

from __future__ import annotations

import logging
import socket

log = logging.getLogger(__name__)

# The EWS endpoint that the mail backend talks to. Hardcoded here because
# the same value lives in utils.mail_senders.UniGrazEwsSender and the two
# must stay in sync. If you ever swap to a different Exchange host, change
# both places.
EWS_HOST = "webmail.uni-graz.at"
EWS_PORT = 443


def is_vpn_connected(host: str = EWS_HOST,
                     port: int = EWS_PORT,
                     timeout: float = 3.0) -> bool:
    """Quick TCP-connect check to the Uni-Graz EWS endpoint.

    Returns True if a TCP handshake to ``host:port`` succeeds within
    ``timeout`` seconds. Returns False on timeout, DNS failure, refused
    connection, or any other socket-level error.

    Note: this only proves the host is reachable from this machine.
    Strictly it does not prove the route is via the Cisco VPN - in
    practice ``webmail.uni-graz.at`` is internal-only, so reachability
    is a sufficient proxy.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, socket.gaierror, ConnectionError, OSError) as exc:
        log.debug("VPN check: cannot reach %s:%d (%s)", host, port, exc)
        return False


def warn_if_not_connected(mail_provider_type: str) -> bool:
    """Print a clear warning if EWS is configured but the host is unreachable.

    Returns True when everything looks fine (either VPN is up, or EWS isn't
    being used). Returns False when the user should know that the mail step
    will fail later.

    This is intentionally non-blocking - the workflow still runs to
    completion. We just want the user to see the diagnosis at the start
    of the run instead of after a 120-second timeout at the end.
    """
    if mail_provider_type != "uni-graz-ews":
        return True
    if is_vpn_connected():
        return True

    print()
    print("!" * 60)
    print("! VPN PRE-FLIGHT WARNING")
    print("!" * 60)
    print(f"  Could not reach {EWS_HOST}:{EWS_PORT} (3s TCP timeout).")
    print()
    print("  mail_provider.type is 'uni-graz-ews', which sends mail through")
    print(f"  {EWS_HOST}. That endpoint is only reachable from inside the")
    print("  Uni-Graz network or via the Cisco AnyConnect / Secure Client VPN.")
    print()
    print("  Likely cause: VPN not connected.")
    print("    - Windows / macOS: start Cisco Secure Client and authenticate.")
    print("    - Linux server:    ensure your openconnect tunnel is up.")
    print()
    print("  The workflow will still run, but the final daily-report mail")
    print("  will fail with a connect-timeout. Fix the VPN and re-run, or")
    print("  switch mail_provider.type to 'yahoo-smtp' if you don't need EWS.")
    print("!" * 60)
    print()
    return False
