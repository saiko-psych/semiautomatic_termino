# Server / cron deployment

This is the runbook for the **unattended daily run** on a Debian 12 Proxmox LXC —
the setup that has been running `semiautomatic_termino` in production since
2026-05-31 (daily at 06:00 Europe/Vienna: VPN up → mails → uniCLOUD sync →
calendar → daily-report mail → VPN down).

The ready-to-use, redacted artifacts referenced below live in the repo under
[`deploy/`](https://github.com/saiko-psych/semiautomatic_termino/tree/main/deploy)
(see `deploy/README.md` for the file-to-path mapping). Fill the placeholders on
the server, never in the repo.

## 1. System packages (Debian 12 / Ubuntu 22.04+)

```bash
sudo apt install -y \
    python3 python3-venv python3-pip \
    git curl ca-certificates \
    openconnect \
    xvfb \
    sudo

# Qt6 runtime that openconnect-sso's headless browser needs
sudo apt install -y \
    libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
    libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xkb1 \
    libxkbcommon-x11-0 libnss3 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxrandr2 libgbm1

# Selenium + Chromium for the Termino scraping phases
sudo apt install -y chromium chromium-driver \
                    fonts-liberation fonts-noto-color-emoji
```

`chromium-driver` (system package) is deliberately used instead of
`webdriver-manager`'s download, so the driver version always matches the
installed Chromium. The script's `_resolve_chromedriver_path()` picks up
`/usr/bin/chromedriver` automatically and falls back to `ChromeDriverManager`
elsewhere (e.g. Windows).

## 2. `uv` + `openconnect-sso`

Install [`uv`](https://docs.astral.sh/uv/), then install `openconnect-sso` as an
isolated `uv tool` with these pins (each is from hard live experience):

```bash
uv tool install \
    --with "setuptools<70" \
    --with "keyrings.alt" \
    --with "pycryptodome" \
    openconnect-sso
```

- `setuptools<70` — openconnect-sso v0.8.1 imports `pkg_resources`, removed in setuptools 70+.
- `keyrings.alt` — provides the `PlaintextKeyring` backend used headless (below).
- `pycryptodome` — `keyrings.alt` needs it at runtime during backend detection.

## 3. Proxmox host: /dev/net/tun for the unprivileged LXC

An unprivileged container can't open `/dev/net/tun` without help. On the **host**:

```bash
echo tun > /etc/modules-load.d/tun.conf
install -m 0644 deploy/lxc/90-tun-lxc.rules /etc/udev/rules.d/90-tun-lxc.rules
udevadm control --reload-rules && udevadm trigger /dev/net/tun
```

Then append the lines from `deploy/lxc/ct.conf.snippet` to
`/etc/pve/lxc/<CT_ID>.conf` and restart the container. Keep both `sys_admin` and
`net_admin` — openconnect needs them for tun setup.

## 4. Service user + code

```bash
sudo adduser --disabled-password --gecos "Termino daily run" termino
sudo git clone https://github.com/saiko-psych/semiautomatic_termino.git /opt/termino
sudo chown -R termino:termino /opt/termino
sudo -u termino bash -c 'cd /opt/termino && uv sync'

# VPN wrapper scripts into place (executable)
sudo install -m 0755 /opt/termino/deploy/scripts/vpn_up.sh   /opt/termino/scripts/vpn_up.sh
sudo install -m 0755 /opt/termino/deploy/scripts/vpn_down.sh /opt/termino/scripts/vpn_down.sh
```

The `termino` user has no password (`--disabled-password`), so it can never log
in interactively — only systemd runs it.

## 5. Secrets (keyring)

Credentials live in the OS keyring, never in files. On a headless server the
backend is set via the systemd `Environment=` line (already in the unit):

```
PYTHON_KEYRING_BACKEND=keyrings.alt.file.PlaintextKeyring
```

`PlaintextKeyring` + `chmod 0600` is used because the encrypted file backends
ignore `KEYRING_CRYPTFILE_PASSWORD` and prompt interactively, which would block
cron. The security model is identical to "encrypted with the master password
stored next to it". Set the secrets once (interactively) as described in
{doc}`../getting-started/secrets`; the VPN login PW + TOTP seed go in under the
openconnect-sso namespace.

Copy the openconnect-sso browser-automation config (no secrets in it):

```bash
sudo -u termino mkdir -p /home/termino/.config/openconnect-sso
sudo -u termino install -m 0600 /opt/termino/deploy/openconnect-sso/config.toml.example \
     /home/termino/.config/openconnect-sso/config.toml
```

## 6. sudoers for openconnect

```bash
sudo install -m 0440 /opt/termino/deploy/sudoers.d/openconnect-termino \
     /etc/sudoers.d/openconnect-termino
sudo visudo -cf /etc/sudoers.d/openconnect-termino   # validate
```

This grants the `termino` user password-less openconnect up/down only. See
{doc}`vpn-setup` for why the exact argument forms matter.

## 7. systemd timer

Install the units from `deploy/systemd/`, fill the `UNI_GRAZ_EMAIL` placeholder
in `termino.service`, then enable:

```bash
sudo install -m 0644 /opt/termino/deploy/systemd/termino.service /etc/systemd/system/
sudo install -m 0644 /opt/termino/deploy/systemd/termino.timer   /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now termino.timer
```

The service is `Type=oneshot` with `ExecStartPre=vpn_up.sh`, the run, and
`ExecStopPost=vpn_down.sh` (the latter runs even if the main run fails, so the
tunnel always comes back down). The timer fires daily 06:00 Europe/Vienna with a
120 s randomized delay and `Persistent=true` (catch-up after downtime).

### Optional watchdog

`deploy/systemd/termino-watchdog.{service,timer}` + `deploy/scripts/termino_watchdog.sh`
(installed to `/usr/local/bin/termino_watchdog.sh`) check at 07:00 whether the run
succeeded and push an [ntfy.sh](https://ntfy.sh) alert to your phone if not. The
timer is verified against the production box; the watchdog script body and the
`.service` unit are reconstructed (verify them — see `deploy/README.md`).

## 8. Verify a run

```bash
# Trigger once by hand (idempotent: re-running the same day is a no-op)
sudo systemctl start termino.service

journalctl -u termino.service -n 50   # last run output
systemctl list-timers                 # schedule + next/last trigger
```

A clean run takes ~28 s and ends with the daily-report mail in your inbox. To
force a full re-run the same day, delete `status.json` first:

```bash
sudo -u termino rm /opt/termino/status.json
```

## 9. Updating an existing deployment

If the container was set up earlier with local out-of-tree patches (the
ChromeOptions / system-chromedriver / `keyrings.alt` edits), those are now
upstream in `main` — you can drop them and pull:

```bash
sudo -u termino git -C /opt/termino rev-parse HEAD   # what's deployed?
sudo -u termino git -C /opt/termino status           # any local edits?

# If the only local changes are the chromedriver/keyring patches (now upstream):
sudo -u termino git -C /opt/termino stash            # or: checkout -- <files>
sudo -u termino git -C /opt/termino pull origin main
sudo -u termino bash -c 'cd /opt/termino && uv sync'
sudo systemctl daemon-reload
```

Keep anything genuinely local (e.g. an untracked `scripts/` you placed by hand)
and re-check `git status` is clean afterwards.
