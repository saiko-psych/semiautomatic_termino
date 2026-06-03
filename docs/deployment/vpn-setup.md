# VPN setup

The EWS mail backend (`mail_provider.type: "uni-graz-ews"`) needs to reach `webmail.uni-graz.at`, which is only accessible from inside the Uni-Graz network or through the Uni-Graz VPN. If you use Yahoo SMTP you do not need a VPN and can skip this page entirely.

## Interactive (laptop)

The standard path for daily laptop use is Cisco Secure Client:

1. Open Cisco Secure Client.
2. Connect to `univpn.uni-graz.at` and select the appropriate auth group (`Bedienstete`, `Studierende`, or `Universitaetsbibliothek`).
3. Authenticate with your Uni email address and password.
4. Confirm the MFA prompt (TOTP from the Uni-Graz Authenticator app).
5. Run the script once the "Connected" status appears.

There is no reliable headless CLI for Cisco Secure Client on Windows or macOS. For unattended laptop runs, either keep the VPN session alive in a long-lived desktop session, or switch to the Yahoo SMTP backend.

## Headless / one-click

The headless path uses [`openconnect-sso`](https://github.com/vlaci/openconnect-sso), a Python wrapper that drives a Qt-WebEngine browser through the Uni-Graz Keycloak SAML flow and hands off to plain `openconnect` for the tunnel. Plain `openconnect` alone does not work because Uni-Graz rejects its login form submissions.

The full installation and configuration guide — including the `config.toml` Keycloak DOM selectors, the systemd `ExecStartPre`/`ExecStopPost` wrapper pattern, and the Windows Scheduled-Task approach — is being migrated to the [`automatic-openconnect`](https://github.com/saiko-psych/automatic-openconnect) repository. Once that repo is published, `openconnect-sso` will be installable as a `uv tool` and the `auto_vpn` config block will work out of the box.

In the meantime, the current detailed notes for the Linux server setup live in `docs/SERVER_VPN_SETUP.md` in this repo.
