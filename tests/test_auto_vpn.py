# -*- coding: utf-8 -*-
"""
Tests for utils.auto_vpn.

All subprocess calls are mocked - the tests never spawn openconnect-sso
or talk to univpn.uni-graz.at. They verify the orchestration logic,
platform safety, and the no-op-when-disabled contract.
"""

import sys
import subprocess
import unittest
from unittest import mock

from utils.auto_vpn import (
    VPNError,
    auto_vpn_session,
    is_vpn_up,
)


# --- no-op when disabled -------------------------------------------------

class TestDisabledIsNoOp(unittest.TestCase):
    """When auto_vpn is not enabled, the context manager does nothing."""

    def test_no_op_when_section_missing(self):
        with auto_vpn_session({}) as token:
            self.assertIsNone(token)

    def test_no_op_when_enabled_false(self):
        cfg = {"auto_vpn": {"enabled": False}}
        with auto_vpn_session(cfg) as token:
            self.assertIsNone(token)

    def test_no_op_when_section_is_none(self):
        # Some config writers might persist {"auto_vpn": null}; treat as off.
        with auto_vpn_session({"auto_vpn": None}) as token:
            self.assertIsNone(token)

    def test_no_subprocess_calls_when_disabled(self):
        with mock.patch("subprocess.run") as run:
            with auto_vpn_session({"auto_vpn": {"enabled": False}}):
                pass
            run.assert_not_called()


# --- platform guard ------------------------------------------------------

class TestPlatformGuard(unittest.TestCase):
    """auto_vpn refuses to act on non-Linux when explicitly enabled."""

    def test_raises_on_windows(self):
        with mock.patch.object(sys, "platform", "win32"):
            cfg = {"auto_vpn": {"enabled": True,
                                "user_email": "x@example.org"}}
            with self.assertRaises(VPNError) as cm:
                with auto_vpn_session(cfg):
                    self.fail("body should never run on win32")
            self.assertIn("only supported on Linux", str(cm.exception))

    def test_raises_on_darwin(self):
        with mock.patch.object(sys, "platform", "darwin"):
            cfg = {"auto_vpn": {"enabled": True,
                                "user_email": "x@example.org"}}
            with self.assertRaises(VPNError):
                with auto_vpn_session(cfg):
                    self.fail("body should never run on darwin")


# --- config validation ---------------------------------------------------

class TestConfigValidation(unittest.TestCase):
    """Required fields are validated before any subprocess is spawned."""

    def test_raises_without_user_email(self):
        with mock.patch.object(sys, "platform", "linux"), \
             mock.patch("subprocess.run") as run:
            cfg = {"auto_vpn": {"enabled": True}}
            with self.assertRaises(VPNError) as cm:
                with auto_vpn_session(cfg):
                    self.fail("body should never run without user_email")
            self.assertIn("user_email is required", str(cm.exception))
            # Specifically: we must NOT have spawned anything before
            # discovering the config problem.
            run.assert_not_called()


# --- is_vpn_up probe ----------------------------------------------------

class TestIsVpnUp(unittest.TestCase):
    """pgrep-based detection, cross-platform safe."""

    def test_false_on_non_linux(self):
        with mock.patch.object(sys, "platform", "win32"):
            self.assertFalse(is_vpn_up())

    def test_true_when_pgrep_finds_match(self):
        with mock.patch.object(sys, "platform", "linux"), \
             mock.patch("subprocess.run") as run:
            run.return_value = mock.Mock(returncode=0)
            self.assertTrue(is_vpn_up("univpn"))

    def test_false_when_pgrep_returns_nonzero(self):
        with mock.patch.object(sys, "platform", "linux"), \
             mock.patch("subprocess.run") as run:
            run.return_value = mock.Mock(returncode=1)
            self.assertFalse(is_vpn_up("univpn"))

    def test_false_when_pgrep_missing(self):
        with mock.patch.object(sys, "platform", "linux"), \
             mock.patch("subprocess.run", side_effect=FileNotFoundError()):
            self.assertFalse(is_vpn_up())


# --- linux-enabled happy path with full mocking --------------------------

class TestEnabledLinuxFlow(unittest.TestCase):
    """When everything is mocked-OK, the context manager runs to completion."""

    def test_already_up_skips_auth_and_skips_teardown(self):
        """If a tunnel is already running, we don't auth, don't tunnel,
        and don't tear down on exit (we didn't bring it up)."""
        cfg = {"auto_vpn": {
            "enabled": True,
            "user_email": "x@example.org",
            "down_on_exit": True,
        }}
        # Make is_vpn_up() report "already up" via pgrep returncode 0.
        with mock.patch.object(sys, "platform", "linux"), \
             mock.patch("subprocess.run") as run:
            run.return_value = mock.Mock(returncode=0)
            with auto_vpn_session(cfg) as token:
                self.assertTrue(token)
            # We must NOT have called sudo/openconnect-sso/openconnect
            # in any of the calls so far.
            for call in run.call_args_list:
                args = call.args[0] if call.args else []
                joined = " ".join(args)
                self.assertNotIn("openconnect-sso", joined)
                self.assertNotIn("sudo", joined)


class TestKeyringPreCheck(unittest.TestCase):
    """The keyring is probed before openconnect-sso is spawned."""

    def test_raises_when_login_pw_missing(self):
        with mock.patch.object(sys, "platform", "linux"), \
             mock.patch("subprocess.run") as run, \
             mock.patch("utils.secrets.get_uni_login_password",
                        return_value=None), \
             mock.patch("utils.secrets.get_uni_totp_secret",
                        return_value="seed"):
            run.return_value = mock.Mock(returncode=1)  # is_vpn_up -> False
            cfg = {"auto_vpn": {"enabled": True,
                                "user_email": "x@example.org"}}
            with self.assertRaises(VPNError) as cm:
                with auto_vpn_session(cfg):
                    self.fail("body should never run without keyring pw")
            self.assertIn("No UGO login password in keyring", str(cm.exception))

    def test_raises_when_totp_seed_missing(self):
        with mock.patch.object(sys, "platform", "linux"), \
             mock.patch("subprocess.run") as run, \
             mock.patch("utils.secrets.get_uni_login_password",
                        return_value="some-pw"), \
             mock.patch("utils.secrets.get_uni_totp_secret",
                        return_value=None):
            run.return_value = mock.Mock(returncode=1)
            cfg = {"auto_vpn": {"enabled": True,
                                "user_email": "x@example.org"}}
            with self.assertRaises(VPNError) as cm:
                with auto_vpn_session(cfg):
                    self.fail("body should never run without TOTP seed")
            self.assertIn("No TOTP base32 seed", str(cm.exception))


# --- subprocess pipe-detach + cleanup-on-setup-failure --------------------
# Regression tests for the bug discovered during CT-131 side-by-side test
# on 2026-06-01 (see docs/AUTO-VPN-TEST-REPORT.md).

class TestStartTunnelPipeDetach(unittest.TestCase):
    """_start_tunnel must spawn openconnect detached from Python's pipes.

    openconnect --background daemonizes, the daemon-child inherits any
    pipes opened by the parent subprocess.run, and capture_output=True
    used to deadlock the parent waiting for EOF that would never come.
    The fix: stdin/stdout/stderr=DEVNULL + start_new_session=True.
    """

    def test_uses_devnull_and_new_session(self):
        from utils.auto_vpn import _start_tunnel

        with mock.patch("utils.auto_vpn._resolve_tool", return_value="/usr/sbin/openconnect"), \
             mock.patch("utils.auto_vpn.subprocess.run") as run, \
             mock.patch("utils.auto_vpn.Path") as PathMock, \
             mock.patch("utils.auto_vpn.time.sleep"):
            # subprocess.run reports immediate success.
            run.return_value = mock.Mock(returncode=0)
            # PID-file appears immediately, /proc/<pid> exists.
            pid_path = mock.Mock()
            pid_path.exists.return_value = True
            pid_path.read_text.return_value = "12345"
            proc_path = mock.Mock()
            proc_path.is_dir.return_value = True
            PathMock.side_effect = lambda p: pid_path if "tmp" in str(p) or "oc" in str(p) else proc_path

            _start_tunnel("host", "cookie", "fp", {"pid_file": "/tmp/oc-test.pid"})

            # The FIRST subprocess.run call must be the openconnect spawn.
            self.assertGreaterEqual(run.call_count, 1)
            first = run.call_args_list[0]
            kwargs = first.kwargs
            # No pipes - daemon-child must not inherit anything.
            self.assertEqual(kwargs.get("stdin"), subprocess.DEVNULL)
            self.assertEqual(kwargs.get("stdout"), subprocess.DEVNULL)
            self.assertEqual(kwargs.get("stderr"), subprocess.DEVNULL)
            # New session so openconnect is fully detached.
            self.assertTrue(kwargs.get("start_new_session"))
            # capture_output must NOT be set (it would re-open pipes).
            self.assertFalse(kwargs.get("capture_output"))

    def test_raises_when_pid_file_never_appears(self):
        """If openconnect spawn returns but never writes a PID-file
        (cookie expired, sudoers wrong), we surface a clear error."""
        from utils.auto_vpn import _start_tunnel

        with mock.patch("utils.auto_vpn._resolve_tool", return_value="/usr/sbin/openconnect"), \
             mock.patch("utils.auto_vpn.subprocess.run") as run, \
             mock.patch("utils.auto_vpn.Path") as PathMock, \
             mock.patch("utils.auto_vpn.time.sleep"):
            run.return_value = mock.Mock(returncode=0)
            never_exists = mock.Mock()
            never_exists.exists.return_value = False
            PathMock.return_value = never_exists

            with self.assertRaises(VPNError) as cm:
                _start_tunnel("host", "cookie", "fp", {"pid_file": "/tmp/oc-test.pid"})
            self.assertIn("did not register a running PID", str(cm.exception))


class TestCleanupOnSetupFailure(unittest.TestCase):
    """If _start_tunnel raises mid-flight, a daemon may already be running.
    auto_vpn_session must call _stop_tunnel before re-raising, so the
    zombie does not fool the next vpn_up.sh pgrep check.
    """

    def test_stop_tunnel_called_when_start_tunnel_raises(self):
        cfg = {"auto_vpn": {"enabled": True,
                            "user_email": "x@example.org"}}
        with mock.patch.object(sys, "platform", "linux"), \
             mock.patch("utils.auto_vpn.is_vpn_up", return_value=False), \
             mock.patch("utils.auto_vpn._check_keyring_credentials"), \
             mock.patch("utils.auto_vpn._authenticate",
                        return_value=("host", "cookie", "fp")), \
             mock.patch("utils.auto_vpn._start_tunnel",
                        side_effect=VPNError("simulated tunnel failure")), \
             mock.patch("utils.auto_vpn._stop_tunnel") as stop:

            with self.assertRaises(VPNError):
                with auto_vpn_session(cfg):
                    self.fail("body must never run when setup failed")

            stop.assert_called_once()
            args = stop.call_args.args
            self.assertEqual(args[0], "univpn")



class TestStopTunnelSudoersCompat(unittest.TestCase):
    """_stop_tunnel must use commands that match the deployed sudoers
    rule exactly. Regression test for Befund 4 (CT-131, 2026-06-01):
    `sudo pkill -f <pattern>` is rejected by sudoers because the rule
    is `sudo /usr/bin/pkill openconnect` (no -f). The fix uses pgrep
    to enumerate PIDs and `sudo /bin/kill <pid>` per PID, with
    `sudo /usr/bin/pkill openconnect` as failsafe.
    """

    def test_kills_each_pid_via_kill_not_pkill_dash_f(self):
        from utils.auto_vpn import _stop_tunnel
        with mock.patch.object(sys, "platform", "linux"), \
             mock.patch("utils.auto_vpn.subprocess.run") as run, \
             mock.patch("utils.auto_vpn.time.sleep"):
            run.side_effect = [
                mock.Mock(returncode=0, stdout="12345\n67890\n"),
                mock.Mock(returncode=0),
                mock.Mock(returncode=0),
                mock.Mock(returncode=1),
            ]
            _stop_tunnel("univpn")

            invocations = [call.args[0] for call in run.call_args_list]
            self.assertIn(["sudo", "-n", "/bin/kill", "12345"], invocations)
            self.assertIn(["sudo", "-n", "/bin/kill", "67890"], invocations)
            for inv in invocations:
                joined = " ".join(inv)
                self.assertNotIn("pkill -f", joined,
                    "pkill -f is rejected by sudoers and must not be used")

    def test_failsafe_pkill_uses_exact_sudoers_form(self):
        from utils.auto_vpn import _stop_tunnel
        with mock.patch.object(sys, "platform", "linux"), \
             mock.patch("utils.auto_vpn.subprocess.run") as run, \
             mock.patch("utils.auto_vpn.time.sleep"):
            run.side_effect = [
                mock.Mock(returncode=0, stdout="42\n"),
                mock.Mock(returncode=0),
                mock.Mock(returncode=0),
                mock.Mock(returncode=0),
            ]
            _stop_tunnel("univpn")

            invocations = [call.args[0] for call in run.call_args_list]
            self.assertIn(
                ["sudo", "-n", "/usr/bin/pkill", "openconnect"],
                invocations,
            )


if __name__ == "__main__":
    unittest.main()
