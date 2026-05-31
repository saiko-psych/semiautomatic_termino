# Server-VPN-Setup-Guide für `semiautomatic_termino` auf headless Linux

> **Was das ist:** Komplette, aus realer Deployment-Erfahrung abgeleitete Anleitung wie man Uni-Graz-VPN (`univpn.uni-graz.at`) **automatisiert + headless** in einem Linux-Container für das Termino-Skript aufsetzt. Geeignet als Repo-Doku (`docs/SERVER_VPN_SETUP.md`) oder als Grundlage für ein optionales Python-Modul (`utils/auto_vpn.py`).
>
> **Zielplattform:** Debian 12 (bookworm) unprivileged LXC. Lässt sich 1:1 auf Ubuntu 22.04/24.04 oder Docker übertragen — nur die Paketnamen können leicht abweichen.
>
> **Nicht zielführend:** Klassisches `openconnect` ohne `-sso`. Bei Uni Graz scheitert das, weil der Cisco-Server die Authentifizierung an Keycloak (`login.uni-graz.at`) via SAML delegiert. Klassisches Form-Login wird zwar angezeigt, aber jedes Login-PW wird konsistent abgelehnt.

---

## Inhalt

1. [Architektur: warum dieser Stack](#architektur-warum-dieser-stack)
2. [System-Voraussetzungen](#system-voraussetzungen)
3. [Schritt-für-Schritt-Setup](#schritt-für-schritt-setup)
4. [Wrapper-Scripts (ready to use)](#wrapper-scripts-ready-to-use)
5. [systemd-Service (ready to use)](#systemd-service-ready-to-use)
6. [Optional: Auto-VPN-Modul fürs Skript selbst](#optional-auto-vpn-modul-fürs-skript-selbst)
7. [Sicherheits-Überlegungen](#sicherheits-überlegungen)
8. [Troubleshooting](#troubleshooting)
9. [Pfade auf einen Blick](#pfade-auf-einen-blick)

---

## Architektur: warum dieser Stack

```
┌─────────────────────────────────────────────────────────────────┐
│ openconnect-sso (Python wrapper, v0.8.1)                        │
│   ├── Qt6-WebEngine (headless Chromium-basierter Browser)       │
│   └── lädt SAML-Login-Page von login.uni-graz.at                │
│        ├── auto-füllt Username + Password aus Keyring           │
│        ├── auto-füllt TOTP-Code (generiert aus Base32-Seed)     │
│        ├── klickt durch Keycloak-MFA-Auswahl + Consent          │
│        └── extrahiert AnyConnect-Session-Cookie                 │
│                                                                  │
│   gibt aus: COOKIE, HOST, FINGERPRINT  →  beendet sich          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ openconnect (klassisches CLI, v9.x)                             │
│   --cookie <COOKIE> --servercert <FP> --background --no-dtls    │
│        └── baut tun0 auf, läuft im Hintergrund (daemon)         │
│        └── pid in /home/<user>/.local/run/oc.pid                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                       Tunnel zu Uni-Netz (143.50.0.0/16)
                              │
                              ▼
            EWS-Mailversand, Uni-interne Services, etc.
```

### Warum 2-stufig (Auth + Tunnel getrennt)?

- **`openconnect-sso --authenticate`** liefert nur Cookie + Host + Fingerprint und beendet sich — kein Tunnel-Aufbau, kein Block der Shell.
- **`openconnect --background`** baut dann mit dem Cookie den Tunnel auf und daemonized.
- So ist der Aufruf **non-blocking** (für systemd-Pre-Hooks gut), Skript-tauglich und sauber recovery-bar.

Versucht man stattdessen `openconnect-sso` ohne `--authenticate`, blockiert es solange der Tunnel läuft (es ist Wrapper um openconnect). Im systemd-`ExecStartPre`-Kontext führt das zu Race-Conditions oder „hängenden" Service-Starts.

### Warum xvfb-run?

openconnect-sso braucht einen X-Display um den Qt-Browser zu rendern. Auf einem headless Server gibt's das nicht → `xvfb-run` erstellt einen virtuellen Display (`Xvfb`) für die Dauer des Befehls. Der Browser läuft in diesem virtuellen Display, niemand „sieht" ihn, aber er funktioniert vollständig (DOM, JavaScript, Form-Auto-Fill).

### Warum klassisches `openconnect` für den Tunnel statt openconnect-sso selbst?

openconnect-sso ohne `--authenticate` startet automatisch openconnect intern (mit dem Cookie). Aber: dieser interne openconnect läuft als Child-Process von openconnect-sso, der wiederum als Child-Process von xvfb-run läuft — eine Kette die schwer sauber zu daemonizen ist. Direkt-Aufruf von `openconnect --background` als sudo gibt uns volle Kontrolle über PID-File, Tunnel-Lifecycle und Cleanup.

---

## System-Voraussetzungen

### Header-Pakete (`apt install` als root)

```bash
# Basis
apt install -y \
    python3 python3-venv python3-pip \
    git curl ca-certificates \
    openconnect \
    xvfb \
    sudo

# Qt6-Runtime für openconnect-sso v0.8.1
apt install -y \
    libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
    libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xkb1 \
    libxkbcommon-x11-0 libnss3 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxrandr2 libgbm1

# Wenn auch Selenium+Chromium laufen soll (für Termino-Antibot):
apt install -y chromium chromium-driver \
                fonts-liberation fonts-noto-color-emoji
```

### Container-Konfiguration (LXC) am Host

Falls in **unprivileged LXC** (Proxmox/incus), Host-seitig zwei Dinge:

1. **udev-Rule** damit `/dev/net/tun` Container-zugänglich bleibt:
   ```bash
   # Auf dem Host als root
   echo tun > /etc/modules-load.d/tun.conf
   modprobe tun
   cat > /etc/udev/rules.d/90-tun-lxc.rules << 'EOF'
   KERNEL=="tun", MODE="0666"
   EOF
   udevadm control --reload-rules
   udevadm trigger /dev/net/tun
   ```

2. **LXC-Config ergänzen** (`/etc/pve/lxc/<CTID>.conf` bei Proxmox):
   ```
   lxc.cgroup2.devices.allow: c 10:200 rwm
   lxc.mount.entry: /dev/net/tun dev/net/tun none bind,create=file
   ```

3. **Capabilities NICHT droppen:** `sys_admin` UND `net_admin` MÜSSEN drinbleiben (openconnect braucht beide für TUN-Setup). Wenn Hardening andere Caps droppt, diese explizit ausnehmen.

### Docker (alternative Zielplattform)

```dockerfile
# Im Container-Run
docker run \
  --cap-add=NET_ADMIN \
  --cap-add=SYS_ADMIN \
  --device=/dev/net/tun \
  ...
```

### Python-Tooling

```bash
# uv (Astral) — schneller, lock-file-basierter Package Manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# openconnect-sso ALS ISOLIERTES TOOL installieren
# WICHTIG: --with-Pins sind aus realer Live-Erfahrung
uv tool install \
    --with "setuptools<70" \
    --with "keyrings.alt" \
    --with "pycryptodome" \
    openconnect-sso
```

**Warum die Pins?**
- `setuptools<70`: openconnect-sso v0.8.1 importiert `pkg_resources`, das in setuptools 70+ entfernt wurde. Pinning auf < 70 hält das Modul verfügbar.
- `keyrings.alt`: für `PlaintextKeyring` (siehe nächster Abschnitt).
- `pycryptodome`: Crypto-Dependency die keyrings.alt für seine encrypted-Variante braucht und sonst zur Laufzeit beim Backend-Detect crash't.

### Verifikation der Installation

```bash
openconnect --version          # >= 9.x
openconnect-sso --version      # 0.8.1
xvfb-run --help | head -1      # zeigt Usage
```

---

## Schritt-für-Schritt-Setup

### Schritt 1 — User anlegen

```bash
# Als root
adduser --disabled-password --gecos "Termino daily run" termino
```

Begründung: Service-User ohne PW-Login (kein SSH, kein sudo direkt). Tunnel-Aufbau geht via Sudoers-NOPASSWD-Regel (siehe Schritt 5).

### Schritt 2 — openconnect-sso config.toml für Uni-Graz-Keycloak

Die config.toml beinhaltet die **DOM-Selektoren** für die Keycloak-Login-Seite — ohne die kann openconnect-sso das Formular nicht ausfüllen.

```bash
# Als termino-User
mkdir -p ~/.config/openconnect-sso

cat > ~/.config/openconnect-sso/config.toml << 'EOF'
on_disconnect = ""

[default_profile]
address = "univpn.uni-graz.at"
user_group = ""
name = "Studierende"

[auto_fill_rules]

# Username
[[auto_fill_rules."https://login.uni-graz.at/*"]]
selector = "input#username"
fill = "username"

# Password
[[auto_fill_rules."https://login.uni-graz.at/*"]]
selector = "input#password"
fill = "password"

# Login-Button klicken (Stufe 1)
[[auto_fill_rules."https://login.uni-graz.at/*"]]
selector = "input#kc-login"
action = "click"

# MFA-Auswahl: TOTP wählen (UUID ist stabile Keycloak-ID für „Authenticator-App")
[[auto_fill_rules."https://login.uni-graz.at/*"]]
selector = "label[for='31d086a8-3054-4551-b80c-35a07358d88d']"
action = "click"

# TOTP-Code eingeben
[[auto_fill_rules."https://login.uni-graz.at/*"]]
selector = "input[name=otp]"
fill = "totp"

# Login-Button klicken (Stufe 2 nach TOTP)
[[auto_fill_rules."https://login.uni-graz.at/*"]]
selector = "input#kc-login"
action = "click"

# Eventueller Consent-Bildschirm akzeptieren
[[auto_fill_rules."https://login.uni-graz.at/*"]]
selector = "input#kc-accept"
action = "click"

# Stop-Indicator: wenn Error-Span auftaucht → abbrechen
[[auto_fill_rules."https://login.uni-graz.at/*"]]
selector = "span#input-error"
action = "stop"
EOF
chmod 600 ~/.config/openconnect-sso/config.toml
```

**Hinweis zu Authgroup `Studierende`:** Uni Graz hat drei Authgroups (`Bedienstete | Studierende | Universitaetsbibliothek`). Studierende ist `name = "Studierende"`. Das URL-Fragment `/ub` (wie in `univpn.uni-graz.at/ub`) ist eine URL-Pfad-Variante für UB-Quick-Access — **nicht** der interne Group-Name. Cisco-Server gibt die Group-Liste bei `?`-Trial preis.

**Wenn die Selektoren brechen:** Keycloak-Theme der Uni Graz hat sich geändert. Den eigenen Linux-PC (auf dem openconnect-sso interaktiv funktioniert) als Referenz nehmen — dort liegt eine funktionierende config.toml unter `~/.config/openconnect-sso/config.toml`. Selektoren von dort 1:1 übernehmen.

### Schritt 3 — Keyring-Backend (CRITICAL für Cron)

**Wichtigste Erkenntnis aus der Live-Session:** Beide encrypted-File-Backends — `keyrings.cryptfile.file.EncryptedKeyring` UND `keyrings.alt.file.EncryptedKeyring` — ignorieren die `KEYRING_CRYPTFILE_PASSWORD` ENV-Var. Beim ersten und jedem Folge-Aufruf kommt ein interaktiver Master-PW-Prompt → blockt jeden Cron-Run.

**Funktionierende Lösung: `keyrings.alt.file.PlaintextKeyring`.**

```bash
# In allen Shells die den Keyring nutzen (am Besten in /etc/termino/env):
export PYTHON_KEYRING_BACKEND=keyrings.alt.file.PlaintextKeyring
```

Sicherheits-Schutz: 0600-Permissions auf das File.

```bash
chmod 700 ~/.local/share/python_keyring/
chmod 600 ~/.local/share/python_keyring/keyring_pass.cfg
```

**Threat-Modell-Argument:** Mit cryptfile + Master-PW-in-File hätten wir effektiv dieselbe Sicherheit (Master-PW liegt 0600 auf der Platte). PlaintextKeyring ist ehrlicher, weniger fragil, headless-tauglich. Wer Filesystem-Access (Root im Container) hat, hat in beiden Fällen alle Secrets.

### Schritt 4 — Erste interaktive Auth (legt Credentials ins Keyring)

Dieser eine Run wird gemacht **bevor** Cron läuft. User tippt Passwort + TOTP-Seed interaktiv ein, beides landet im Keyring. Folge-Runs lesen ohne Prompt.

```bash
# Als termino
export PYTHON_KEYRING_BACKEND=keyrings.alt.file.PlaintextKeyring

xvfb-run --auto-servernum --server-args="-screen 0 1024x768x24" \
  openconnect-sso \
    -u <DEINE-MAIL>@edu.uni-graz.at \
    --browser-display-mode shown \
    -l INFO \
    --authenticate
```

Prompts:
- `Password (...)` → UGO-Login-Passwort (= dein normales Uni-Login-PW, nicht das Mail-PW)
- `TOTP secret (...)` → **Base32-Seed** deiner MFA-App (nicht der 6-stellige Code). Bei Authenticator-Apps: Export-Funktion oder Token im Uni-IT-Portal neu generieren und beim QR-Scan den Manual-Entry-String mit kopieren.

Output: `HOST=...`, `COOKIE=...`, `FINGERPRINT=...` (Cookie ist kurzlebig, kann ignoriert werden — der Setup-Effekt ist dass die Credentials jetzt im Keyring liegen).

### Schritt 5 — Sudoers-Regel für openconnect

`/etc/sudoers.d/openconnect-termino`:

```
termino ALL=(root) NOPASSWD: /usr/sbin/openconnect, /usr/bin/killall openconnect, /usr/bin/pkill openconnect, /bin/kill
```

```bash
chmod 0440 /etc/sudoers.d/openconnect-termino
visudo -cf /etc/sudoers.d/openconnect-termino    # MUSS "OK" sagen
```

Notwendig weil openconnect für TUN-Setup root-Rechte braucht, der Wrapper aber als termino läuft.

---

## Wrapper-Scripts (ready to use)

Beide nach `/opt/termino/scripts/` ablegen, `chown termino:termino`, `chmod +x`.

### `vpn_up.sh`

```bash
#!/bin/bash
# Auth + Tunnel-Aufbau für Uni-Graz-VPN.
# Phase 1: openconnect-sso macht headless SAML-Auth, gibt Cookie/Host/FP aus
# Phase 2: openconnect (CLI) baut Tunnel im Hintergrund mit dem Cookie
set -euo pipefail

# Anpassen: dein UGO-Email
USER_EMAIL="${UNI_GRAZ_EMAIL:-your-mail@edu.uni-graz.at}"

export PYTHON_KEYRING_BACKEND=keyrings.alt.file.PlaintextKeyring
export HOME=/home/termino
export XDG_CONFIG_HOME=/home/termino/.config

PID_FILE=/home/termino/.local/run/oc.pid
LOG_FILE=/home/termino/.local/run/vpn-up.log
mkdir -p /home/termino/.local/run

# Idempotenz: schon ein Tunnel da?
if pgrep -f "openconnect.*univpn.uni-graz.at" > /dev/null; then
    echo "[vpn_up] VPN-Tunnel läuft bereits"
    exit 0
fi

# Phase 1: Auth
echo "[vpn_up] Authenticating..." >&2
AUTH_OUTPUT=$(xvfb-run --auto-servernum --server-args="-screen 0 1024x768x24" \
  /home/termino/.local/bin/openconnect-sso \
    -u "$USER_EMAIL" \
    --browser-display-mode shown \
    -l ERROR \
    --authenticate 2>>"$LOG_FILE")

HOST=$(echo "$AUTH_OUTPUT" | grep '^HOST=' | cut -d= -f2-)
COOKIE=$(echo "$AUTH_OUTPUT" | grep '^COOKIE=' | cut -d= -f2-)
FINGERPRINT=$(echo "$AUTH_OUTPUT" | grep '^FINGERPRINT=' | cut -d= -f2-)

if [ -z "$HOST" ] || [ -z "$COOKIE" ] || [ -z "$FINGERPRINT" ]; then
    echo "[vpn_up] AUTH FAILED — Output war nicht parsebar." >&2
    echo "Log: $LOG_FILE" >&2
    exit 1
fi

# Phase 2: Tunnel im Hintergrund
echo "[vpn_up] Auth ok, starting tunnel..." >&2
sudo /usr/sbin/openconnect \
    --servercert "$FINGERPRINT" \
    --cookie "$COOKIE" \
    --background \
    --pid-file "$PID_FILE" \
    --no-dtls \
    "$HOST" >>"$LOG_FILE" 2>&1

# Cleanup ENV - Cookie nicht im Shell-State lassen
unset HOST COOKIE FINGERPRINT AUTH_OUTPUT

# Wait for tun0
for i in {1..10}; do
    if ip link show tun0 >/dev/null 2>&1; then
        echo "[vpn_up] tun0 ist up nach ${i}s"
        exit 0
    fi
    sleep 1
done

echo "[vpn_up] FEHLER: tun0 nicht da nach 10s. Log: $LOG_FILE" >&2
exit 2
```

### `vpn_down.sh`

```bash
#!/bin/bash
# Schließt den Uni-Graz-VPN-Tunnel sauber.
# PID via pgrep — das PID-File gehört root (von sudo openconnect), termino kann es nicht lesen.
set -uo pipefail

# Alle openconnect-PIDs zu unserem Server finden
PIDS=$(pgrep -f "openconnect.*univpn.uni-graz.at" || true)

if [ -n "$PIDS" ]; then
    echo "[vpn_down] Killing openconnect: $PIDS"
    for PID in $PIDS; do
        sudo /bin/kill "$PID" || true
    done

    # Auf clean shutdown warten
    for i in {1..10}; do
        if ! pgrep -f "openconnect.*univpn.uni-graz.at" > /dev/null; then
            break
        fi
        sleep 1
    done

    # Failsafe: pkill (in sudoers erlaubt)
    if pgrep -f "openconnect.*univpn.uni-graz.at" > /dev/null; then
        echo "[vpn_down] Failsafe pkill"
        sudo /usr/bin/pkill openconnect || true
        sleep 2
    fi
fi

# Final-Check
if pgrep -f "openconnect.*univpn.uni-graz.at" > /dev/null; then
    echo "[vpn_down] WARNUNG: openconnect läuft noch"
    exit 1
fi
echo "[vpn_down] Tunnel down"
```

### Verifikation der Wrapper-Scripts

```bash
# Als termino
/opt/termino/scripts/vpn_up.sh
sleep 3
ip addr show tun0 | head -3      # 143.50.x.x sichtbar
curl -sI --max-time 10 https://webmail.uni-graz.at/ews/exchange.asmx | head -1
# Erwartung: HTTP/1.1 401 Unauthorized (= EWS via Tunnel erreichbar)
/opt/termino/scripts/vpn_down.sh
ip addr show tun0 2>&1 | tail -1  # Device "tun0" does not exist.
```

---

## systemd-Service (ready to use)

Empfohlenes Pattern: VPN als **Pre-/Post-Hook** des eigentlichen Termino-Service, nicht als permanent laufender Tunnel.

`/etc/systemd/system/termino.service`:

```ini
[Unit]
Description=Daily Termino reminder run
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
User=termino
Group=termino
WorkingDirectory=/opt/termino
Environment="HOME=/home/termino"
Environment="PYTHON_KEYRING_BACKEND=keyrings.alt.file.PlaintextKeyring"
Environment="UNI_GRAZ_EMAIL=your-mail@edu.uni-graz.at"

# VPN hochfahren als Pre-Hook (idempotent — wenn schon up, kein Problem)
ExecStartPre=/opt/termino/scripts/vpn_up.sh

# Eigentlicher Lauf
ExecStart=/home/termino/.local/bin/uv run --project /opt/termino python /opt/termino/main.py

# VPN runter als Post-Hook (läuft auch bei Fehler im Hauptlauf)
ExecStopPost=/opt/termino/scripts/vpn_down.sh

StandardOutput=journal
StandardError=journal
TimeoutStartSec=600
```

`/etc/systemd/system/termino.timer`:

```ini
[Unit]
Description=Run Termino daily at 06:00

[Timer]
OnCalendar=*-*-* 06:00:00 Europe/Vienna
Persistent=true
RandomizedDelaySec=120

[Install]
WantedBy=timers.target
```

```bash
systemctl daemon-reload
systemctl enable --now termino.timer
systemctl list-timers termino.timer
```

**Warum Pre/Post statt persistenter Tunnel?**
- 80-Sekunden-Window pro Tag wo der Container VPN-Credentials „on the wire" hat — minimale Angriffsfläche
- Kein Reconnect-Logic-Aufwand
- Wenn Lauf failed (ExecStart) → ExecStopPost feuert trotzdem → Tunnel-Cleanup garantiert
- Kein „dauerhaft offener Uni-Tunnel" der ggf. nach 24h vom Server-Side terminated wird

---

## Optional: Auto-VPN-Modul fürs Skript selbst

Wenn du das ganz **ins Skript einbauen** willst (statt externe Bash-Wrapper), hier ein Vorschlag für ein Python-Modul `utils/auto_vpn.py`. Triggered durch eine Config-Option in `config.json`.

### Config-Schema-Erweiterung

```json
{
    ...
    "auto_vpn": {
        "enabled": true,
        "type": "openconnect-sso",
        "server": "univpn.uni-graz.at",
        "authgroup": "Studierende",
        "user_email": "your.account@edu.uni-graz.at",
        "openconnect_path": "/usr/sbin/openconnect",
        "openconnect_sso_path": "/home/termino/.local/bin/openconnect-sso",
        "pid_file": "/tmp/oc-termino.pid",
        "use_xvfb": true,
        "down_on_exit": true
    }
}
```

Wenn `auto_vpn.enabled == false` oder Section fehlt: kein Auto-Aufbau. Das ist wichtig damit Windows-Dev/Test-Läufe das nicht versehentlich triggern.

### Modul-Skelett `utils/auto_vpn.py`

```python
"""
utils.auto_vpn — Optional VPN-Setup via openconnect-sso für headless Linux.

Aktiviert über config_data['auto_vpn']['enabled'] = True.
Übersprungen wenn Config-Section fehlt oder False.

Cross-platform: auf Windows / macOS schlägt der Aufruf bewusst fehl und
gibt klare Fehlermeldung — der User soll dort den nativen VPN-Client
(Cisco AnyConnect) verwenden.
"""

import os
import re
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from typing import Optional


class VPNError(Exception):
    """Raised when VPN setup fails. Caller decides whether to abort."""


def is_vpn_up(server_hint: str = "univpn") -> bool:
    """Cheap check: gibt es schon ein openconnect zum gewünschten Server?"""
    try:
        out = subprocess.run(
            ["pgrep", "-f", f"openconnect.*{server_hint}"],
            capture_output=True, text=True, timeout=5,
        )
        return out.returncode == 0
    except FileNotFoundError:
        # pgrep nicht da → wir sind nicht auf Linux
        return False


def _authenticate_via_sso(cfg: dict) -> tuple[str, str, str]:
    """Ruft openconnect-sso --authenticate auf und parst HOST/COOKIE/FINGERPRINT."""
    sso_path = cfg.get("openconnect_sso_path", "openconnect-sso")
    if not shutil.which(sso_path):
        raise VPNError(
            f"openconnect-sso not found at {sso_path!r}. "
            "Install with: uv tool install --with 'setuptools<70' --with 'keyrings.alt' --with 'pycryptodome' openconnect-sso"
        )
    cmd = [sso_path,
           "-u", cfg["user_email"],
           "--browser-display-mode", "shown",
           "-l", "ERROR",
           "--authenticate"]
    if cfg.get("use_xvfb", True):
        if not shutil.which("xvfb-run"):
            raise VPNError("xvfb-run not found — sudo apt install xvfb")
        cmd = ["xvfb-run", "--auto-servernum",
               "--server-args=-screen 0 1024x768x24"] + cmd

    print("[auto_vpn] Authenticating via openconnect-sso...", file=sys.stderr)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise VPNError(f"openconnect-sso failed: {result.stderr[:500]}")

    host = cookie = fingerprint = None
    for line in result.stdout.splitlines():
        if line.startswith("HOST="):
            host = line.split("=", 1)[1]
        elif line.startswith("COOKIE="):
            cookie = line.split("=", 1)[1]
        elif line.startswith("FINGERPRINT="):
            fingerprint = line.split("=", 1)[1]
    if not all([host, cookie, fingerprint]):
        raise VPNError(
            "openconnect-sso lieferte keine vollständigen Auth-Daten. "
            "Output: " + result.stdout[:500]
        )
    return host, cookie, fingerprint


def _start_tunnel(host: str, cookie: str, fingerprint: str, cfg: dict) -> None:
    """Startet openconnect mit Cookie im Hintergrund."""
    oc_path = cfg.get("openconnect_path", "/usr/sbin/openconnect")
    pid_file = cfg.get("pid_file", "/tmp/oc.pid")

    cmd = ["sudo", "-n", oc_path,
           "--servercert", fingerprint,
           "--cookie", cookie,
           "--background",
           "--pid-file", pid_file,
           "--no-dtls",
           host]

    print("[auto_vpn] Starting tunnel...", file=sys.stderr)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise VPNError(f"openconnect failed: {result.stderr[:500]}")

    # Wait for tun0
    for _ in range(10):
        time.sleep(1)
        check = subprocess.run(["ip", "link", "show", "tun0"],
                               capture_output=True)
        if check.returncode == 0:
            print("[auto_vpn] tun0 is up", file=sys.stderr)
            return
    raise VPNError("tun0 nicht hochgekommen nach 10s")


def _stop_tunnel(server_hint: str = "univpn") -> None:
    """Killt openconnect-Prozesse zum Server."""
    subprocess.run(["sudo", "-n", "/usr/bin/pkill",
                    "-f", f"openconnect.*{server_hint}"],
                   capture_output=True)


@contextmanager
def auto_vpn_session(config_data: dict):
    """
    Context-Manager: VPN up vor main(), VPN down nach Exit (auch bei Fehler).

    Use case:
        with auto_vpn_session(config_data):
            run_main_workflow()

    Wenn config_data['auto_vpn']['enabled'] != True, wird nichts gemacht.
    """
    cfg = config_data.get("auto_vpn", {})
    if not cfg.get("enabled"):
        # Nichts zu tun — yield ohne Setup
        yield None
        return

    if sys.platform not in ("linux",):
        raise VPNError(
            f"auto_vpn ist nur auf Linux supported, nicht auf {sys.platform}. "
            "Auf Windows/macOS Cisco AnyConnect manuell starten."
        )

    server_hint = cfg.get("server", "univpn.uni-graz.at").split(".")[0]
    was_already_up = is_vpn_up(server_hint)

    if not was_already_up:
        host, cookie, fingerprint = _authenticate_via_sso(cfg)
        _start_tunnel(host, cookie, fingerprint, cfg)
        # Sensitive vars sofort vergessen
        del cookie

    try:
        yield True
    finally:
        if cfg.get("down_on_exit", True) and not was_already_up:
            print("[auto_vpn] Closing tunnel", file=sys.stderr)
            _stop_tunnel(server_hint)
```

### Integration in `main.py`

```python
from utils.auto_vpn import auto_vpn_session, VPNError

def main():
    config_data = load_config()
    try:
        with auto_vpn_session(config_data):
            _run_daily_workflow(config_data)
    except VPNError as e:
        print(f"VPN-Setup failed: {e}", file=sys.stderr)
        sys.exit(2)
```

### Vorteile dieser Modul-Variante

- **Cross-platform-tauglich:** Auf Windows/macOS überspringt das Modul den Setup mit klarer Fehlermeldung — kein Bash-Skript-Wrapper nötig
- **Config-driven:** `auto_vpn.enabled` zentral steuerbar
- **Context-Manager-Garantie:** Tunnel-Cleanup auch bei Skript-Crash
- **Testbar:** Mit Mocks für `subprocess.run` lässt sich der Modul-Pfad in Unit-Tests prüfen

### Nachteile

- **Mehr Repo-Code zum Warten** als externe Bash-Wrapper
- **Coupling Skript ↔ Server-Setup** — Bash-Wrapper trennen das sauberer
- **Sudoers-Regel ist trotzdem nötig** (das ändert sich nicht)

**Empfehlung:** Bash-Wrapper als Standard im Server-Setup-Doku-Path. Das Python-Modul als **opt-in für User, die ein Single-Process-Skript wollen** (z. B. wenn sie kein systemd haben, sondern nur einen cron-job). Dann ist es eine reine Convenience-Feature.

---

## Sicherheits-Überlegungen

### Was im Container liegt

- **UGO-Login-Passwort** (im PlaintextKeyring, 0600)
- **TOTP-Base32-Seed** (im PlaintextKeyring, 0600)
- Session-Cookie für openconnect-Verbindung (nur kurz im Memory während vpn_up.sh läuft)

### Threat-Modell

**Wer Root im Container hat → kann alles lesen.** Punkt. Kein Keyring-Encryption hilft hier, weil das Master-PW auch irgendwo im Klartext liegen muss damit Cron es nutzen kann.

Daraus folgt:
- **Container-Hardening ist Pflicht** wenn man UGO-Credentials drin lagert (siehe Phase 8 im Server-Mgmt-Workspace)
- **Backup muss verschlüsselt** sein ODER `keyring_pass.cfg` muss aus dem Backup excluded werden
- **Updates für openconnect-sso, Chromium, etc. aktuell halten** (unattended-upgrades)

### Backup-Empfehlung (vzdump-Pattern)

```bash
vzdump <CTID> \
  --mode snapshot \
  --compress zstd \
  --exclude-path /home/termino/.local/share/python_keyring \
  --exclude-path /home/termino/.local/run \
  --exclude-path /home/termino/.cache
```

Konsequenz: bei Restore muss man den Keyring manuell neu befüllen (1× interaktives openconnect-sso `--authenticate`-Run + `python -m utils.secrets set --termino`). 5 Min Arbeit. Trade-off für sichere Backups.

### Credential-Rotation

UGO-Passwörter laufen bei der Uni Graz ca. alle 6 Monate ab. Workflow:
1. Im Uni-IT-Portal neues PW setzen
2. Im Container: `xvfb-run openconnect-sso --authenticate` als termino → tippt neues PW + TOTP → landet im Keyring → fertig

TOTP-Seed bleibt stabil bis der MFA-Token im IT-Portal neu erstellt wird.

---

## Troubleshooting

### „Cannot open /dev/net/tun: Permission denied"

Host-seitige udev-Rule prüfen:
```bash
ls -la /dev/net/tun
# Soll: crw-rw-rw- 1 root root 10, 200
```
Falls anders: `udevadm trigger /dev/net/tun`. Wenn das auch nicht reicht: Host-Reboot UND udev-Rule wirklich da (`cat /etc/udev/rules.d/90-tun-lxc.rules`).

### „openconnect-sso: pkg_resources not found"

`setuptools` ist zu neu. Reinstall mit Pin:
```bash
uv tool install --reinstall --with "setuptools<70" openconnect-sso
```

### Browser/Qt startet nicht — fehlende Lib

Output enthält Zeile wie `qt.qpa.plugin: From 6.5.0, xcb-cursor0 or libxcb-cursor0 is needed`. Lib nachinstallieren:
```bash
apt install -y libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
                libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 \
                libxcb-shape0 libxcb-xkb1 libxkbcommon-x11-0
```

### „Please enter password for encrypted keyring" beim Auto-Run

Du nutzt `keyrings.alt.file.EncryptedKeyring` oder `keyrings.cryptfile.*`. Wechsel zu `PlaintextKeyring`:
```bash
export PYTHON_KEYRING_BACKEND=keyrings.alt.file.PlaintextKeyring
rm -rf ~/.local/share/python_keyring/    # reset, dann neu auth'en
```

### Auth läuft durch, aber `Login failed` im Loop

Keycloak hat sich verändert. Selektoren in `~/.config/openconnect-sso/config.toml` an die aktuelle Form anpassen. Falls Auto-Fill grundsätzlich nicht greift: `--browser-display-mode shown` + `xvfb-run` mit zugänglichem VNC-Display laufen lassen, manuell den Browser-Inhalt anschauen.

### EWS antwortet trotz Tunnel nicht (Timeout)

```bash
ip route get 143.50.129.84       # MUSS "dev tun0" enthalten
```
Wenn Route via `eth0` geht: Tunnel ist hochgekommen, aber Routing splittet nicht durch. openconnect ohne `--script` macht Standard-Route über tun → sollte automatisch passen. Bei custom Setups manuell prüfen.

### „Account locked" oder Login wiederholt abgelehnt

Cisco-Side Lockout nach mehreren Failed-Tries. Typisch 15–30 Min warten. **Vorbeugen:** Konfig nie ohne Diagnose iterativ verändern → Selektoren erst am Linux-PC verifizieren, dann 1× am Server testen.

---

## Pfade auf einen Blick

| Pfad | Inhalt |
|---|---|
| `~/.config/openconnect-sso/config.toml` | SAML-Profile + Auto-Fill-Selektoren |
| `~/.local/bin/openconnect-sso` | uv-tool wrapper-script |
| `~/.local/share/uv/tools/openconnect-sso/` | Tool-eigenes venv (PyQt6, etc.) |
| `~/.local/share/python_keyring/keyring_pass.cfg` | Secrets-Store (0600!) |
| `/etc/sudoers.d/openconnect-termino` | NOPASSWD-Regel für openconnect/kill |
| `/etc/systemd/system/termino.{service,timer}` | systemd-Cron |
| `/opt/termino/scripts/vpn_up.sh` | Auth + Tunnel-Start |
| `/opt/termino/scripts/vpn_down.sh` | Tunnel-Stop |
| `~/.local/run/oc.pid` | openconnect-PID (root-owned wegen sudo) |
| `~/.local/run/vpn-up.log` | Auth/Tunnel-Logs |
| Host: `/etc/udev/rules.d/90-tun-lxc.rules` | TUN-Permissions persistent |
| Host: `/etc/pve/lxc/<CTID>.conf` | LXC TUN-Passthrough |

---

## TL;DR-Checkliste für neue Deployments

- [ ] Host: tun-Modul-Persistenz + udev-Rule + LXC-TUN-Passthrough
- [ ] System: Python, xvfb, openconnect, Qt6-Libs, chromium-driver, fonts
- [ ] User: `termino` mit `--disabled-password`
- [ ] uv installiert, openconnect-sso via uv tool mit den 3 `--with`-Pins
- [ ] `~/.config/openconnect-sso/config.toml` mit Uni-Graz-Selektoren
- [ ] `PYTHON_KEYRING_BACKEND=keyrings.alt.file.PlaintextKeyring` ENV
- [ ] 1× interaktives `openconnect-sso --authenticate` → Keyring populated
- [ ] `chmod 700 ~/.local/share/python_keyring/ && chmod 600 ~/.local/share/python_keyring/keyring_pass.cfg`
- [ ] `/etc/sudoers.d/openconnect-termino` mit NOPASSWD-Regel
- [ ] `vpn_up.sh` + `vpn_down.sh` in `/opt/termino/scripts/` + chmod +x
- [ ] termino.service + termino.timer in `/etc/systemd/system/` + enable
- [ ] vzdump-Backup mit `--exclude-path` für Keyring-Verzeichnis
- [ ] Verifikation: `vpn_up.sh && curl -sI https://webmail.uni-graz.at/ews/exchange.asmx → 401` → success

---

_Source: live deployment on a Proxmox unprivileged LXC. Field-verified for a daily run cycle (~30 seconds with the VPN bring-up + workflow + tear-down). Originally written 2026, kept generic so any lab on the Uni-Graz network can reuse._
