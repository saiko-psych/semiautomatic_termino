# -*- coding: utf-8 -*-
"""
Tests for utils.auto_vpn.

All subprocess calls are mocked - the tests never spawn openconnect-sso
or talk to univpn.uni-graz.at. They verify the orchestration logic,
platform safety, and the no-op-when-disabled contract.
"""

import sys
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


if __name__ == "__main__":
    unittest.main()
