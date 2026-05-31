# -*- coding: utf-8 -*-
"""
utils.mail_senders
==================

Provider-agnostic mail sending for the Termino script.

Why this module exists
----------------------
The old ``mailing.py`` hard-coded Yahoo's SMTP server and the
``env_data['app_password_mail']`` lookup in every function. This module
turns that into a strategy pattern: each function in the refactored
``mailing.py`` is handed a ``MailSender`` and calls ``.send(...)`` on it.
The function doesn't know if mail goes via SMTP-to-Yahoo or EWS-to-Uni-Graz.

Two implementations are provided
--------------------------------
``YahooSmtpSender``
    The legacy path. ``smtplib.SMTP_SSL`` to smtp.mail.yahoo.com:465 with
    an app password. Kept because users can still be configured for Yahoo.

``UniGrazEwsSender``
    The new path. ``exchangelib`` against
    ``https://webmail.uni-graz.at/ews/exchange.asmx`` with Basic Auth.
    Requires that the host can reach webmail.uni-graz.at — which in
    practice means the LXC must be on the Uni VPN.

Connection re-use
-----------------
Both senders cache their connection for the lifetime of the sender object.
A single Termino run typically sends 10–30 mails, and we want one SMTP/EWS
session for the whole batch, not one per mail. Use the sender as a context
manager (``with make_sender(...) as s: ...``) to make sure the connection is
closed cleanly even on errors.

Construction
------------
``make_sender(provider_config, secrets_getter=get_secret)`` is the factory.
The ``provider_config`` dict is the per-user config (see PLAN.md, Phase 1).
``secrets_getter`` lets tests inject a fake secret lookup; in production it's
the keyring wrapper from ``utils.secrets``.

Credential source per provider
------------------------------
Both senders look up their password in the OS keyring via the
``secrets_getter`` callable. The two providers use DIFFERENT keyring
slots, by convention:

YahooSmtpSender
    Reads ``termino-uni/yahoo-app-pw``. Set via
    ``python -m utils.secrets set --termino``.

UniGrazEwsSender
    Reads the user's UGO login password from
    ``openconnect-sso/<username>`` - the SAME slot that openconnect-sso
    populates for the VPN login. This is intentional: EWS Basic Auth
    accepts the regular Uni-Graz login password, and we want one place
    to update it when the password rotates (UGO-PWs expire every ~6
    months). Set via ``python -m utils.secrets set --email <addr> --vpn``.

So the VPN setup automatically also sets up EWS. No separate Mail-PW
step needed (the ``termino-uni/uni-mail-pw`` slot is for the legacy
SMTP-via-mailproxy path only and is unused by the EWS sender).
"""

from __future__ import annotations

import abc
import logging
import smtplib
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Callable, Optional

from utils.secrets import get_secret, get_uni_login_password

log = logging.getLogger(__name__)


# --- common message data type -------------------------------------------

@dataclass
class OutgoingMail:
    """
    Provider-neutral representation of a mail to send.

    Callers in ``mailing.py`` build this; senders translate it into their
    backend's format. Keeping it a plain dataclass means tests can compare
    expected vs. actual messages with ``==``.

    ``ics_attachment`` (optional): raw iCalendar bytes for an iMIP invite.
    When set, senders MUST add it as a ``text/calendar; method=REQUEST``
    MIME part so the recipient's mail client (Outlook, Apple Mail, etc.)
    shows an "Accept / Decline" button and can import the event directly
    into the user's own calendar.
    """
    to: str
    subject: str
    body: str
    body_is_html: bool = False
    from_address: Optional[str] = None  # senders that need it can fall back
    ics_attachment: Optional[bytes] = None
    ics_filename: str = "invite.ics" 


# --- abstract base ------------------------------------------------------

class MailSender(abc.ABC):
    """Interface every concrete sender must implement."""

    @abc.abstractmethod
    def send(self, mail: OutgoingMail) -> None:
        """Send a single mail. Should raise on failure, not silently swallow."""

    @abc.abstractmethod
    def close(self) -> None:
        """Release the underlying connection."""

    # Context-manager helpers — concrete classes inherit these as-is.
    def __enter__(self) -> "MailSender":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


# --- Yahoo SMTP sender (legacy) ----------------------------------------

class YahooSmtpSender(MailSender):
    """
    Send via SMTP over SSL to smtp.mail.yahoo.com.

    Behaviour copied from the old ``mailing.py`` so existing Yahoo users
    keep working without re-configuration. Differences:
    - Connection is opened once and reused for the whole batch.
    - App password comes from the keyring, not from env_data dict.
    """

    DEFAULT_HOST = "smtp.mail.yahoo.com"
    DEFAULT_PORT = 465

    def __init__(self, username: str, app_password: str,
                 host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.username = username
        self._password = app_password
        self.host = host
        self.port = port
        self._smtp: Optional[smtplib.SMTP_SSL] = None

    def _ensure_connected(self) -> smtplib.SMTP_SSL:
        if self._smtp is not None:
            return self._smtp
        log.debug("opening SMTP_SSL %s:%d as %s", self.host, self.port, self.username)
        s = smtplib.SMTP_SSL(self.host, self.port)
        s.login(self.username, self._password)
        self._smtp = s
        return s

    def send(self, mail: OutgoingMail) -> None:
        smtp = self._ensure_connected()
        msg = MIMEMultipart("mixed")
        msg["From"] = mail.from_address or self.username
        msg["To"] = mail.to
        msg["Subject"] = mail.subject
        mime_subtype = "html" if mail.body_is_html else "plain"
        msg.attach(MIMEText(mail.body, mime_subtype, _charset="utf-8"))
        if mail.ics_attachment:
            # text/calendar with METHOD=REQUEST -> mail clients show
            # the accept/decline buttons. The filename helps Outlook
            # identify it as an invite.
            from email.mime.base import MIMEBase
            from email import encoders
            ics_part = MIMEBase("text", "calendar",
                                method="REQUEST", charset="UTF-8")
            ics_part.set_payload(mail.ics_attachment)
            encoders.encode_base64(ics_part)
            ics_part.add_header("Content-Disposition",
                                f'attachment; filename="{mail.ics_filename}"')
            msg.attach(ics_part)
        smtp.send_message(msg)
        log.info("yahoo: sent mail to %s subj=%r", mail.to, mail.subject)

    def close(self) -> None:
        if self._smtp is not None:
            try:
                self._smtp.quit()
            except Exception:
                pass
            self._smtp = None


# --- Uni Graz EWS sender (new) -----------------------------------------

class UniGrazEwsSender(MailSender):
    """
    Send via Exchange Web Services to webmail.uni-graz.at.

    Uses Basic Auth with the user's normal Uni-Graz login password
    (not the Keycloak Mail Password — that one is rejected by EWS).
    Mailbox is on-prem, so this works only when the host can reach
    webmail.uni-graz.at — i.e. when the Uni VPN is up.

    A copy of every sent mail is saved to the user's Sent Items
    folder, matching what Outlook Desktop does.
    """

    DEFAULT_EWS_URL = "https://webmail.uni-graz.at/ews/exchange.asmx"

    def __init__(self, username: str, login_password: str,
                 ews_url: str = DEFAULT_EWS_URL):
        # Import exchangelib lazily so the Yahoo path doesn't pull it in.
        from exchangelib import Account, Credentials, Configuration, DELEGATE
        self._Account = Account
        self._Credentials = Credentials
        self._Configuration = Configuration
        self._DELEGATE = DELEGATE

        self.username = username
        self._password = login_password
        self.ews_url = ews_url
        self._account = None  # type: Optional[object]

    def _ensure_connected(self):
        if self._account is not None:
            return self._account
        log.debug("opening EWS connection to %s as %s", self.ews_url, self.username)
        creds = self._Credentials(username=self.username, password=self._password)
        config = self._Configuration(service_endpoint=self.ews_url, credentials=creds)
        self._account = self._Account(
            primary_smtp_address=self.username,
            config=config,
            autodiscover=False,
            access_type=self._DELEGATE,
        )
        return self._account

    def send(self, mail: OutgoingMail) -> None:
        from exchangelib import Message, Mailbox, HTMLBody

        account = self._ensure_connected()
        body = HTMLBody(mail.body) if mail.body_is_html else mail.body

        msg = Message(
            account=account,
            subject=mail.subject,
            body=body,
            to_recipients=[Mailbox(email_address=mail.to)],
        )
        if mail.ics_attachment:
            # Attach the iMIP invite. Lazy-import FileAttachment so unit-tests
            # that mock 'exchangelib' with a minimal stub don't fail.
            try:
                from exchangelib import FileAttachment
                msg.attach(FileAttachment(
                    name=mail.ics_filename,
                    content=mail.ics_attachment,
                    content_type="text/calendar; method=REQUEST; charset=UTF-8",
                ))
            except (ImportError, AttributeError) as e:
                log.warning("ews: could not attach iMIP invite: %s", e)
        msg.send_and_save()
        log.info("ews: sent mail to %s subj=%r%s",
                 mail.to, mail.subject,
                 " (with iMIP invite)" if mail.ics_attachment else "")

    def close(self) -> None:
        # exchangelib's Account doesn't hold a persistent socket the way
        # SMTP_SSL does, but protocol pooling does. Tell it to shut down.
        if self._account is not None:
            try:
                self._account.protocol.close()
            except Exception:
                pass
            self._account = None


# --- factory ------------------------------------------------------------

ProviderConfig = dict  # alias for readability; comes from per-user config.json

SecretGetter = Callable[[str], Optional[str]]


def make_sender(provider_config: ProviderConfig,
                secret_getter: SecretGetter = get_secret) -> MailSender:
    """
    Build a MailSender from the user-level provider config.

    Expected shape of ``provider_config``::

        {
            "type": "uni-graz-ews",
            "username": "your-mail@your-uni.at",
            "ews_url": "https://webmail.uni-graz.at/ews/exchange.asmx"   # optional
        }

    or::

        {
            "type": "yahoo-smtp",
            "username": "studie@yahoo.com",
            "smtp_host": "smtp.mail.yahoo.com",       # optional
            "smtp_port": 465                          # optional
        }

    Passwords are never in the config — they come from the keyring via
    ``secret_getter``. Tests inject a dict-based fake here.

    Raises ValueError on unknown provider type or missing credentials.
    """
    ptype = provider_config.get("type")
    username = provider_config.get("username")
    if not username:
        raise ValueError("provider_config.username is required")

    if ptype == "yahoo-smtp":
        app_pw = secret_getter("yahoo-app-pw")
        if not app_pw:
            raise ValueError(
                "Yahoo provider configured but 'yahoo-app-pw' is not in keyring. "
                "Run: python -m utils.secrets set --termino"
            )
        return YahooSmtpSender(
            username=username,
            app_password=app_pw,
            host=provider_config.get("smtp_host", YahooSmtpSender.DEFAULT_HOST),
            port=provider_config.get("smtp_port", YahooSmtpSender.DEFAULT_PORT),
        )

    if ptype == "uni-graz-ews":
        # EWS uses the regular Uni login password; lives under the
        # openconnect-sso service so it's shared with the VPN setup.
        login_pw = get_uni_login_password(username)
        if not login_pw:
            raise ValueError(
                f"Uni-Graz EWS provider configured but no login password "
                f"in keyring for {username!r}. Run: "
                f"python -m utils.secrets set --email {username} --vpn"
            )
        return UniGrazEwsSender(
            username=username,
            login_password=login_pw,
            ews_url=provider_config.get("ews_url", UniGrazEwsSender.DEFAULT_EWS_URL),
        )

    raise ValueError(
        f"Unknown mail provider type: {ptype!r}. "
        f"Supported: 'yahoo-smtp', 'uni-graz-ews'."
    )
