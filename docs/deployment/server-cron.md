# Server / cron deployment

The script is designed to run unattended on a Proxmox LXC container or any small Debian/Ubuntu box. Two pieces need attention beyond a normal install.

## Headless Chrome

Selenium needs a real Chrome or Chromium binary. On Debian:

```bash
sudo apt install chromium chromium-driver
```

`webdriver-manager` will locate the installed binary automatically.

## VPN

If you use the `uni-graz-ews` mail backend the script must reach `webmail.uni-graz.at`, which is only accessible through the Uni-Graz VPN. The Yahoo SMTP backend has no such requirement. See {doc}`vpn-setup` for the headless `openconnect-sso` path.

## systemd timer

A typical pair of unit files:

```ini
# /etc/systemd/system/termino.service
[Unit]
Description=Daily Termino reminder run
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
User=termino
WorkingDirectory=/opt/termino
ExecStart=/opt/termino/.venv/bin/python /opt/termino/main.py
```

```ini
# /etc/systemd/system/termino.timer
[Unit]
Description=Run Termino daily at 06:00

[Timer]
OnCalendar=*-*-* 06:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now termino.timer
```

Check status:

```bash
# Last run output
journalctl -u termino.service

# Timer schedule and last/next trigger times
systemctl list-timers
```
