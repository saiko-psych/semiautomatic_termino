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

## Headless

The headless path uses [`openconnect-sso`](https://github.com/vlaci/openconnect-sso), a Python wrapper that drives a Qt-WebEngine browser through the Uni-Graz Keycloak SAML flow and hands off to plain `openconnect` for the tunnel. Plain `openconnect` alone does not work because Uni-Graz rejects its login form submissions.

There are **two ways** to bring this VPN up around the daily run; pick one per host, don't run both:

1. **bash wrappers + systemd (the production Linux path).** `deploy/scripts/vpn_up.sh` runs `openconnect-sso --authenticate` (via `xvfb-run`) and then `sudo openconnect --background`; `vpn_down.sh` tears it down. systemd calls them as `ExecStartPre` / `ExecStopPost`. This is what the production LXC uses — full setup in {doc}`server-cron`, ready-to-use files in `deploy/`.

2. **The `auto_vpn` config block (opt-in / cross-platform).** The script can bring the VPN up itself via `utils/auto_vpn.py` (Linux) / `utils/auto_vpn_win.py` (Windows) when `config.json` has `auto_vpn.enabled: true`. This is the path for Windows hosts and for runs without systemd. It uses the same `openconnect-sso` tool and keyring credentials.

Either way, install `openconnect-sso` as a `uv tool` with the pins shown in {doc}`server-cron`, and provide the Keycloak DOM selectors via `~/.config/openconnect-sso/config.toml` (template: `deploy/openconnect-sso/config.toml.example`).

A separate sister project, [`automatic-openconnect`](https://automatic-openconnect.readthedocs.io/), packages this same headless VPN logic as a standalone, cross-platform library + tray app. Termino does **not** depend on it — the two share the approach, not the code.
