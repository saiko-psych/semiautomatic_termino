# `deploy/` - Linux server deployment artifacts

These are the **production-proven** files behind the unattended daily run of
`semiautomatic_termino` on a Proxmox LXC (Debian 12). They are committed here as
**redacted templates** so the setup is reproducible. The full step-by-step guide
lives in the docs: [Server / cron deployment](../docs/deployment/server-cron.md).

> All real values (email, ntfy topic, container id, IP, study details) have been
> replaced with placeholders. Fill them in on the server, **not** in the repo.

## What's here

| Path | Goes to (on the server) | Notes |
|---|---|---|
| `scripts/vpn_up.sh` | `/opt/termino/scripts/vpn_up.sh` | SAML auth + tunnel up (ExecStartPre) |
| `scripts/vpn_down.sh` | `/opt/termino/scripts/vpn_down.sh` | tunnel down (ExecStopPost) |
| `scripts/termino_watchdog.sh` | `/usr/local/bin/termino_watchdog.sh` (root:root, 0755) | reconstructed body - see caveat below |
| `systemd/termino.service` | `/etc/systemd/system/termino.service` | the daily run |
| `systemd/termino.timer` | `/etc/systemd/system/termino.timer` | 06:00 Europe/Vienna |
| `systemd/termino-watchdog.service` | `/etc/systemd/system/...` | reconstructed (unit not captured) |
| `systemd/termino-watchdog.timer` | `/etc/systemd/system/...` | verified 2026-06-13, 07:00 |
| `sudoers.d/openconnect-termino` | `/etc/sudoers.d/openconnect-termino` | NOPASSWD for openconnect, mode 0440 |
| `openconnect-sso/config.toml.example` | `~termino/.config/openconnect-sso/config.toml` | Keycloak selectors, no secrets |
| `lxc/ct.conf.snippet` | `/etc/pve/lxc/<CT_ID>.conf` (Proxmox host) | TUN passthrough |
| `lxc/90-tun-lxc.rules` | `/etc/udev/rules.d/90-tun-lxc.rules` (host) | make /dev/net/tun usable |

## Placeholders to fill

| Placeholder | Where | Meaning |
|---|---|---|
| `your.account@edu.uni-graz.at` | `vpn_up.sh`, `termino.service` | your UGO email (VPN/EWS login) |
| `<NTFY_TOPIC>` | `watchdog.sh`, `termino-watchdog.service` | your ntfy.sh topic (keep it secret-ish) |
| `<CT_ID>` | `lxc/ct.conf.snippet` filename + path | your LXC container id |
| `termino` (user) / `/opt/termino` / `/home/termino` | throughout | service user + paths; change only if you deviate from the guide |

Credentials (UGO password, TOTP seed, uniCLOUD/Termino app-passwords) are **never**
in these files - they live in the OS keyring and are set once, interactively. See
[Storing secrets](../docs/getting-started/secrets.md).

## ⚠️ Reconstructed watchdog files

The watchdog was reconciled against CT 131 on 2026-06-13:

- `termino-watchdog.timer` - **verified** (07:00 Europe/Vienna, `Persistent`, `RandomizedDelaySec=120`).
- `scripts/termino_watchdog.sh` - path, behaviour and exit codes (0=ok, 1=alert-sent, 2=alert-failed) verified, but the **exact body was not captured** - this is a faithful reconstruction.
- `termino-watchdog.service` - the live `.service` unit was **not captured**; `User=`/`ExecStart` unverified (the script path `/usr/local/bin/termino_watchdog.sh` is confirmed).

Before relying on the two reconstructed files, compare with the live versions and replace if they differ:

```bash
systemctl cat termino-watchdog.service
diff /usr/local/bin/termino_watchdog.sh deploy/scripts/termino_watchdog.sh
```

## VPN: two paths, on purpose

This server uses the **bash `vpn_up.sh` / `vpn_down.sh`** path wired into systemd
via `ExecStartPre` / `ExecStopPost`. That is the production-proven Linux path.

The repo *also* ships a Python context-manager path (`utils/auto_vpn.py` /
`utils/auto_vpn_win.py`, enabled via `config.json` `auto_vpn.enabled`). That one
is the **opt-in / cross-platform (esp. Windows)** path - it is not what this
systemd setup uses. Pick one per host; don't run both at once.
