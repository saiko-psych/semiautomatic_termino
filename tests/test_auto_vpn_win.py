# -*- coding: utf-8 -*-
"""
Tests for utils.auto_vpn_win.

All subprocess and ctypes calls are mocked - these tests run cleanly
on Linux CI and never spawn openconnect-sso, openconnect.exe, or talk
to univpn.uni-graz.at. They verify the orchestration logic, platform
guards, and the no-op-when-disabled contract.
"""

import sys
import subprocess
import unittest
from unittest import mock

# We import the module under test from a Linux CI environment. The
# top-level import path is fine because the module's platform-specific
# behavior is gated behind sys.platform checks inside each function -
# no Windows-only modules are imported at module load time.
from utils.auto_vpn_win import (
    auto_vpn_session_win,
    is_vpn_up,
)
from utils.auto_vpn import VPNError


# --- no-op when disabled -------------------------------------------------

class TestDisabledIsNoOp(unittest.TestCase):
    """When auto_vpn is not enabled, the context manager does nothing."""

    def test_no_op_when_section_missing(self):
        with auto_vpn_session_win({}) as token:
            self.assertIsNone(token)

    def test_no_op_when_enabled_false(self):
        cfg = {"auto_vpn": {"enabled": False}}
        with auto_vpn_session_win(cfg) as token:
            self.assertIsNone(token)

    def test_no_op_when_section_is_none(self):
        with auto_vpn_session_win({"auto_vpn": None}) as token:
            self.assertIsNone(token)

    def test_no_subprocess_calls_when_disabled(self):
        with mock.patch("subprocess.run") as run:
            with auto_vpn_session_win({"auto_vpn": {"enabled": False}}):
                pass
            run.assert_not_called()


# --- platform guard ------------------------------------------------------

class TestPlatformGuard(unittest.TestCase):
    """auto_vpn_win refuses to act on non-Windows."""

    def test_raises_on_linux(self):
        with mock.patch.object(sys, "platform", "linux"):
            cfg = {"auto_vpn": {"enabled": True,
                                "user_email": "x@example.org"}}
            with self.assertRaises(VPNError) as cm:
                with auto_vpn_session_win(cfg):
                    self.fail("body should never run on linux")
            self.assertIn("only supported on Windows", str(cm.exception))

    def test_raises_on_darwin(self):
        with mock.patch.object(sys, "platform", "darwin"):
            cfg = {"auto_vpn": {"enabled": True,
                                "user_email": "x@example.org"}}
            with self.assertRaises(VPNError):
                with auto_vpn_session_win(cfg):
                    self.fail("body should never run on darwin")


# --- config validation --------------------------------------------------

class TestConfigValidation(unittest.TestCase):
    """Required fields are validated before any subprocess is spawned."""

    def test_raises_without_user_email(self):
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch("subprocess.run") as run:
            cfg = {"auto_vpn": {"enabled": True}}
            with self.assertRaises(VPNError) as cm:
                with auto_vpn_session_win(cfg):
                    self.fail("body should never run without user_email")
            self.assertIn("user_email is required", str(cm.exception))
            run.assert_not_called()


# --- is_vpn_up probe ----------------------------------------------------

class TestIsVpnUp(unittest.TestCase):
    """tasklist-based detection, cross-platform safe."""

    def test_false_on_non_windows(self):
        with mock.patch.object(sys, "platform", "linux"):
            self.assertFalse(is_vpn_up())

    def test_true_when_tasklist_finds_match(self):
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch("utils.auto_vpn_win.subprocess.run") as run:
            run.return_value = mock.Mock(
                stdout="openconnect.exe    1234 Console  1  10,000 K",
            )
            self.assertTrue(is_vpn_up())

    def test_false_when_tasklist_no_match(self):
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch("utils.auto_vpn_win.subprocess.run") as run:
            run.return_value = mock.Mock(
                stdout="INFO: No tasks are running which match the criteria.",
            )
            self.assertFalse(is_vpn_up())

    def test_false_when_tasklist_missing(self):
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch("utils.auto_vpn_win.subprocess.run",
                        side_effect=FileNotFoundError()):
            self.assertFalse(is_vpn_up())


# --- keyring pre-check ---------------------------------------------------

class TestKeyringPreCheck(unittest.TestCase):
    """Keyring is probed before openconnect-sso is spawned."""

    def test_raises_when_login_pw_missing(self):
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch("utils.auto_vpn_win.subprocess.run") as run, \
             mock.patch("utils.auto_vpn_win.is_vpn_up", return_value=False), \
             mock.patch("utils.secrets.get_uni_login_password",
                        return_value=None), \
             mock.patch("utils.secrets.get_uni_totp_secret",
                        return_value="seed"):
            cfg = {"auto_vpn": {"enabled": True,
                                "user_email": "x@example.org"}}
            with self.assertRaises(VPNError) as cm:
                with auto_vpn_session_win(cfg):
                    self.fail("body should never run without keyring pw")
            self.assertIn("No UGO login password", str(cm.exception))
            self.assertIn("Windows Credential Manager", str(cm.exception))

    def test_raises_when_totp_seed_missing(self):
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch("utils.auto_vpn_win.subprocess.run") as run, \
             mock.patch("utils.auto_vpn_win.is_vpn_up", return_value=False), \
             mock.patch("utils.secrets.get_uni_login_password",
                        return_value="some-pw"), \
             mock.patch("utils.secrets.get_uni_totp_secret",
                        return_value=None):
            cfg = {"auto_vpn": {"enabled": True,
                                "user_email": "x@example.org"}}
            with self.assertRaises(VPNError) as cm:
                with auto_vpn_session_win(cfg):
                    self.fail("body should never run without TOTP seed")
            self.assertIn("No TOTP base32 seed", str(cm.exception))


# --- admin guard ---------------------------------------------------------

class TestAdminGuard(unittest.TestCase):
    """_start_tunnel refuses to run without Administrator privileges."""

    def test_raises_when_not_admin(self):
        from utils.auto_vpn_win import _start_tunnel
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch("utils.auto_vpn_win._is_admin", return_value=False), \
             mock.patch("utils.auto_vpn_win._resolve_tool",
                        return_value="C:/openconnect.exe"):
            with self.assertRaises(VPNError) as cm:
                _start_tunnel("host", "cookie", "fp",
                              {"openconnect_path": "C:/openconnect.exe"})
            self.assertIn("Administrator", str(cm.exception))


# --- cleanup on setup failure -------------------------------------------

class TestCleanupOnSetupFailure(unittest.TestCase):
    """If _start_tunnel raises mid-flight, conflicting services restart
    and any partial openconnect.exe gets killed."""

    def test_services_restart_when_authenticate_raises(self):
        cfg = {"auto_vpn": {"enabled": True,
                            "user_email": "x@example.org",
                            "stop_cisco_during_run": True,
                            "stop_mullvad_during_run": True}}
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch("utils.auto_vpn_win.is_vpn_up", return_value=False), \
             mock.patch("utils.auto_vpn_win._check_keyring_credentials"), \
             mock.patch("utils.auto_vpn_win._stop_conflicting_services",
                        return_value=["csc_vpnagent", "MullvadVPN"]), \
             mock.patch("utils.auto_vpn_win._restart_services") as restart, \
             mock.patch("utils.auto_vpn_win._stop_tunnel_by_proc") as stop_proc, \
             mock.patch("utils.auto_vpn_win._authenticate",
                        side_effect=VPNError("simulated auth failure")):

            with self.assertRaises(VPNError):
                with auto_vpn_session_win(cfg):
                    self.fail("body must never run when setup failed")

            # We had not yet spawned a tunnel proc - but stop_proc is
            # still called with None as a belt-and-braces sweep.
            stop_proc.assert_called_once_with(None)
            # And services we stopped must be restarted.
            restart.assert_called_once_with(["csc_vpnagent", "MullvadVPN"])

    def test_services_restart_when_tunnel_raises(self):
        cfg = {"auto_vpn": {"enabled": True,
                            "user_email": "x@example.org",
                            "stop_cisco_during_run": True}}
        fake_proc = mock.Mock()
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch("utils.auto_vpn_win.is_vpn_up", return_value=False), \
             mock.patch("utils.auto_vpn_win._check_keyring_credentials"), \
             mock.patch("utils.auto_vpn_win._stop_conflicting_services",
                        return_value=["csc_vpnagent"]), \
             mock.patch("utils.auto_vpn_win._restart_services") as restart, \
             mock.patch("utils.auto_vpn_win._stop_tunnel_by_proc") as stop_proc, \
             mock.patch("utils.auto_vpn_win._authenticate",
                        return_value=("host", "cookie", "fp")), \
             mock.patch("utils.auto_vpn_win._start_tunnel",
                        side_effect=VPNError("tunnel blew up")):

            with self.assertRaises(VPNError):
                with auto_vpn_session_win(cfg):
                    self.fail("body must never run")

            stop_proc.assert_called_once()
            restart.assert_called_once_with(["csc_vpnagent"])


# --- service coexistence helpers ----------------------------------------

class TestServiceCoexistence(unittest.TestCase):
    """_stop_conflicting_services only stops what's actually running and
    what config opts into."""

    def test_skips_services_already_stopped(self):
        from utils.auto_vpn_win import _stop_conflicting_services
        cfg = {"stop_cisco_during_run": True,
               "stop_mullvad_during_run": True}
        with mock.patch("utils.auto_vpn_win._service_status",
                        return_value="STOPPED"), \
             mock.patch("utils.auto_vpn_win.subprocess.run") as run:
            result = _stop_conflicting_services(cfg)
            # Nothing was running, so nothing is in our restart-list
            self.assertEqual(result, [])
            # And we never called `net stop`
            for call in run.call_args_list:
                self.assertNotIn("stop", call.args[0])

    def test_opt_out_via_config(self):
        from utils.auto_vpn_win import _stop_conflicting_services
        cfg = {"stop_cisco_during_run": False,
               "stop_mullvad_during_run": False}
        with mock.patch("utils.auto_vpn_win._service_status",
                        return_value="RUNNING"), \
             mock.patch("utils.auto_vpn_win.subprocess.run") as run:
            result = _stop_conflicting_services(cfg)
            self.assertEqual(result, [])
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
