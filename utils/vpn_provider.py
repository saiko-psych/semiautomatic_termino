# -*- coding: utf-8 -*-
"""
utils.vpn_provider - Cross-platform factory for the VPN context manager.

This lets main.py do::

    from utils.vpn_provider import make_vpn_session
    with make_vpn_session(config_data), make_sender(...) as sender, ...:
        _run_workflow(...)

and get the right implementation per OS:

  * Linux  -> utils.auto_vpn.auto_vpn_session (openconnect-sso + xvfb-run)
  * Windows -> utils.auto_vpn_win.auto_vpn_session_win (openconnect.exe, no sudo)
  * macOS / unknown -> noop context manager that yields None

If the user explicitly disables auto_vpn in config.json (or omits it),
all backends honor the no-op contract regardless of OS.

This module intentionally does the import lazily so that importing
``utils.vpn_provider`` on a stripped-down system without keyring or
PyQt6 still succeeds; the platform-specific dependency only loads
when the platform-specific session is actually requested.
"""

from __future__ import annotations

import sys
from contextlib import contextmanager


@contextmanager
def _noop_session():
    """Used on macOS and unknown platforms - the script runs unchanged."""
    yield None


def make_vpn_session(config_data: dict):
    """Return a context manager that opens the VPN around the wrapped block.

    Inspects ``config_data['auto_vpn']`` to decide what to do. Even when
    auto_vpn is disabled, this returns a context manager (no-op) so
    callers can always use it inside a ``with`` statement.
    """
    if sys.platform == "linux":
        from utils.auto_vpn import auto_vpn_session
        return auto_vpn_session(config_data)
    if sys.platform == "win32":
        from utils.auto_vpn_win import auto_vpn_session_win
        return auto_vpn_session_win(config_data)
    # macOS or unknown - silently skip. The pre-flight warning in
    # utils.vpn still surfaces if EWS is unreachable.
    return _noop_session()
