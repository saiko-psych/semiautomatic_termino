# -*- coding: utf-8 -*-
"""
Unit tests for utils.mail_senders.

These tests run entirely offline — SMTP and EWS are mocked. The point is to
verify the wiring (config → sender → outgoing message), not whether the
remote servers actually accept the mails. End-to-end testing happens on
David's laptop with VPN, and later on the server.
"""

from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# Make sure we can import from the package even when pytest's cwd is the tests dir.
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.mail_senders import (
    OutgoingMail,
    YahooSmtpSender,
    UniGrazEwsSender,
    make_sender,
)


# --------------------- OutgoingMail dataclass ---------------------------

class TestOutgoingMail(unittest.TestCase):
    def test_defaults(self):
        m = OutgoingMail(to="a@b", subject="s", body="hi")
        self.assertEqual(m.to, "a@b")
        self.assertFalse(m.body_is_html)
        self.assertIsNone(m.from_address)

    def test_equality(self):
        # Equality matters because tests compare expected vs actual messages.
        a = OutgoingMail(to="x@y", subject="s", body="b")
        b = OutgoingMail(to="x@y", subject="s", body="b")
        self.assertEqual(a, b)


# --------------------- YahooSmtpSender ----------------------------------

class TestYahooSmtpSender(unittest.TestCase):

    @patch("utils.mail_senders.smtplib.SMTP_SSL")
    def test_connects_once_and_reuses(self, mock_smtp_class):
        """Sending two mails must not open two SMTP sessions."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        sender = YahooSmtpSender("me@yahoo.com", "app-pw-123")
        sender.send(OutgoingMail(to="a@b", subject="s1", body="hi"))
        sender.send(OutgoingMail(to="c@d", subject="s2", body="hello"))

        # One SMTP_SSL construction, one login, two send_message calls.
        self.assertEqual(mock_smtp_class.call_count, 1)
        mock_smtp_class.assert_called_with("smtp.mail.yahoo.com", 465)
        mock_smtp.login.assert_called_once_with("me@yahoo.com", "app-pw-123")
        self.assertEqual(mock_smtp.send_message.call_count, 2)

    @patch("utils.mail_senders.smtplib.SMTP_SSL")
    def test_message_headers_filled(self, mock_smtp_class):
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        with YahooSmtpSender("me@yahoo.com", "pw") as sender:
            sender.send(OutgoingMail(to="x@y", subject="hello", body="body"))

        # Inspect the MIME message that was passed to send_message
        sent_msg = mock_smtp.send_message.call_args.args[0]
        self.assertEqual(sent_msg["From"], "me@yahoo.com")
        self.assertEqual(sent_msg["To"], "x@y")
        self.assertEqual(sent_msg["Subject"], "hello")

    @patch("utils.mail_senders.smtplib.SMTP_SSL")
    def test_explicit_from_address_overrides(self, mock_smtp_class):
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        s = YahooSmtpSender("me@yahoo.com", "pw")
        s.send(OutgoingMail(to="x@y", subject="s", body="b",
                            from_address="display-name@yahoo.com"))
        sent_msg = mock_smtp.send_message.call_args.args[0]
        self.assertEqual(sent_msg["From"], "display-name@yahoo.com")

    @patch("utils.mail_senders.smtplib.SMTP_SSL")
    def test_close_quits_smtp(self, mock_smtp_class):
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        s = YahooSmtpSender("me@yahoo.com", "pw")
        s.send(OutgoingMail(to="x@y", subject="s", body="b"))
        s.close()
        mock_smtp.quit.assert_called_once()

    @patch("utils.mail_senders.smtplib.SMTP_SSL")
    def test_close_without_send_is_safe(self, mock_smtp_class):
        # If no mail was ever sent, close() should be a no-op (no SMTP connection
        # was ever opened, so there's nothing to close).
        s = YahooSmtpSender("me@yahoo.com", "pw")
        s.close()  # should not raise
        mock_smtp_class.assert_not_called()


# --------------------- UniGrazEwsSender ---------------------------------

class TestUniGrazEwsSender(unittest.TestCase):

    def _fake_exchangelib(self):
        """
        Build a stand-in 'exchangelib' module just rich enough for
        UniGrazEwsSender to instantiate Account/Credentials/Configuration
        and call .send_and_save() without doing real network I/O.
        """
        fake = types.ModuleType("exchangelib")

        class FakeProtocol:
            close = MagicMock()

        class FakeAccount:
            def __init__(self, **kw):
                self.init_kwargs = kw
                self.protocol = FakeProtocol()

        class FakeCredentials:
            def __init__(self, **kw):
                self.kw = kw

        class FakeConfiguration:
            def __init__(self, **kw):
                self.kw = kw

        class FakeMessage:
            sent_messages: list = []

            def __init__(self, **kw):
                self.kw = kw

            def send_and_save(self):
                FakeMessage.sent_messages.append(self.kw)

        class FakeMailbox:
            def __init__(self, email_address):
                self.email_address = email_address

        def fake_html_body(s):
            return ("HTMLBODY:" + s)

        fake.Account = FakeAccount
        fake.Credentials = FakeCredentials
        fake.Configuration = FakeConfiguration
        fake.Message = FakeMessage
        fake.Mailbox = FakeMailbox
        fake.HTMLBody = fake_html_body
        fake.DELEGATE = "DELEGATE"
        return fake

    def test_connects_lazily_and_sends_plain_text(self):
        fake_exchangelib = self._fake_exchangelib()
        with patch.dict(sys.modules, {"exchangelib": fake_exchangelib}):
            s = UniGrazEwsSender("me@uni.at", "uni-pw")
            # No connection until first send
            self.assertIsNone(s._account)

            s.send(OutgoingMail(to="x@y", subject="hi", body="plain body"))
            self.assertIsNotNone(s._account)

            # One message was sent
            self.assertEqual(len(fake_exchangelib.Message.sent_messages), 1)
            sent = fake_exchangelib.Message.sent_messages[0]
            self.assertEqual(sent["subject"], "hi")
            self.assertEqual(sent["body"], "plain body")  # NOT wrapped in HTMLBody
            self.assertEqual(sent["to_recipients"][0].email_address, "x@y")

            # Cleanup so the class-level list doesn't leak into the next test
            fake_exchangelib.Message.sent_messages.clear()

    def test_html_body_is_wrapped(self):
        fake_exchangelib = self._fake_exchangelib()
        with patch.dict(sys.modules, {"exchangelib": fake_exchangelib}):
            s = UniGrazEwsSender("me@uni.at", "uni-pw")
            s.send(OutgoingMail(to="x@y", subject="hi",
                                body="<p>hi</p>", body_is_html=True))
            sent = fake_exchangelib.Message.sent_messages[0]
            self.assertEqual(sent["body"], "HTMLBODY:<p>hi</p>")
            fake_exchangelib.Message.sent_messages.clear()

    def test_connection_reused_across_sends(self):
        fake_exchangelib = self._fake_exchangelib()
        with patch.dict(sys.modules, {"exchangelib": fake_exchangelib}):
            s = UniGrazEwsSender("me@uni.at", "uni-pw")
            s.send(OutgoingMail(to="a@b", subject="1", body="x"))
            first_account = s._account
            s.send(OutgoingMail(to="c@d", subject="2", body="y"))
            self.assertIs(s._account, first_account)
            fake_exchangelib.Message.sent_messages.clear()

    def test_close_invokes_protocol_close(self):
        fake_exchangelib = self._fake_exchangelib()
        with patch.dict(sys.modules, {"exchangelib": fake_exchangelib}):
            s = UniGrazEwsSender("me@uni.at", "uni-pw")
            s.send(OutgoingMail(to="x@y", subject="s", body="b"))
            account = s._account
            s.close()
            account.protocol.close.assert_called_once()
            self.assertIsNone(s._account)
            fake_exchangelib.Message.sent_messages.clear()


# --------------------- make_sender factory ------------------------------

class TestMakeSender(unittest.TestCase):

    def test_yahoo_config_returns_yahoo_sender(self):
        config = {"type": "yahoo-smtp", "username": "x@yahoo.com"}
        s = make_sender(config, secret_getter=lambda k: "fake-pw" if k == "yahoo-app-pw" else None)
        self.assertIsInstance(s, YahooSmtpSender)
        self.assertEqual(s.username, "x@yahoo.com")
        self.assertEqual(s.host, "smtp.mail.yahoo.com")
        self.assertEqual(s.port, 465)

    def test_yahoo_missing_secret_raises(self):
        config = {"type": "yahoo-smtp", "username": "x@yahoo.com"}
        with self.assertRaises(ValueError) as ctx:
            make_sender(config, secret_getter=lambda k: None)
        self.assertIn("yahoo-app-pw", str(ctx.exception))

    def test_yahoo_custom_host_port(self):
        config = {"type": "yahoo-smtp", "username": "x@yahoo.com",
                  "smtp_host": "alt.yahoo.com", "smtp_port": 587}
        s = make_sender(config, secret_getter=lambda k: "pw")
        self.assertEqual(s.host, "alt.yahoo.com")
        self.assertEqual(s.port, 587)

    def test_ews_config(self):
        # We don't actually instantiate the Account (lazy), so the factory
        # should construct UniGrazEwsSender without touching network.
        # Patch get_uni_login_password (imported into mail_senders namespace)
        # to return a fake password.
        with patch("utils.mail_senders.get_uni_login_password", return_value="uni-pw"):
            config = {"type": "uni-graz-ews",
                      "username": "your-mail@your-uni.at"}
            s = make_sender(config)
            self.assertIsInstance(s, UniGrazEwsSender)
            self.assertEqual(s.username, "your-mail@your-uni.at")
            self.assertEqual(s.ews_url, "https://webmail.uni-graz.at/ews/exchange.asmx")

    def test_ews_missing_password(self):
        with patch("utils.mail_senders.get_uni_login_password", return_value=None):
            config = {"type": "uni-graz-ews", "username": "x@uni.at"}
            with self.assertRaises(ValueError) as ctx:
                make_sender(config)
            self.assertIn("login password", str(ctx.exception))

    def test_unknown_provider_type(self):
        with self.assertRaises(ValueError) as ctx:
            make_sender({"type": "carrier-pigeon", "username": "x"},
                        secret_getter=lambda k: None)
        self.assertIn("carrier-pigeon", str(ctx.exception))

    def test_missing_username(self):
        with self.assertRaises(ValueError):
            make_sender({"type": "yahoo-smtp"}, secret_getter=lambda k: "x")


if __name__ == "__main__":
    unittest.main(verbosity=2)
