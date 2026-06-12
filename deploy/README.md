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
| `scripts/watchdog.sh` | `/opt/termino/scripts/watchdog.sh` | **reconstructed** - see caveat below |
| `systemd/termino.service` | `/etc/systemd/system/termino.service` | the daily run |
| `systemd/termino.timer` | `/etc/systemd/system/termino.timer` | 06:00 Europe/Vienna |
| `systemd/termino-watchdog.service` | `/etc/systemd/system/...` | **reconstructed** |
| `systemd/termino-watchdog.timer` | `/etc/systemd/system/...` | **reconstructed**, 07:00 |
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

## ⚠️ Reconstructed files

`scripts/watchdog.sh`, `systemd/termino-watchdog.service` and
`systemd/termino-watchdog.timer` were **rebuilt from the behaviour description**
in the server status report, not copied verbatim from the running box. Before
relying on them, compare with the live versions:

```bash
systemctl cat termino-watchdog.service termino-watchdog.timer
cat /opt/termino/scripts/watchdog.sh
```

and replace these files if they differ.

## VPN: two paths, on purpose

This server uses the **bash `vpn_up.sh` / `vpn_down.sh`** path wired into systemd
via `ExecStartPre` / `ExecStopPost`. That is the production-proven Linux path.

The repo *also* ships a Python context-manager path (`utils/auto_vpn.py` /
`utils/auto_vpn_win.py`, enabled via `config.json` `auto_vpn.enabled`). That one
is the **opt-in / cross-platform (esp. Windows)** path - it is not what this
systemd setup uses. Pick one per host; don't run both at once.
