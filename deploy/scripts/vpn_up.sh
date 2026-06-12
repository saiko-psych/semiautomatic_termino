#!/bin/bash
# Auth + Tunnel-Aufbau fuer Uni-Graz-VPN.
#   Phase 1: openconnect-sso macht headless SAML-Auth, gibt Cookie/Host/FP aus
#   Phase 2: openconnect (CLI) baut den Tunnel im Hintergrund mit dem Cookie
#
# Wird vom systemd-Service als ExecStartPre aufgerufen. Idempotent: laeuft schon
# ein Tunnel, passiert nichts. Credentials kommen aus dem OS-Keyring
# (openconnect-sso-Namespace) - NICHTS davon steht in diesem Script.
set -euo pipefail

# Anpassen: deine UGO-Email (oder via Environment= im systemd-Service setzen).
USER_EMAIL="${UNI_GRAZ_EMAIL:-your.account@edu.uni-graz.at}"

export PYTHON_KEYRING_BACKEND=keyrings.alt.file.PlaintextKeyring
export HOME=/home/termino
export XDG_CONFIG_HOME=/home/termino/.config

PID_FILE=/home/termino/.local/run/oc.pid
LOG_FILE=/home/termino/.local/run/vpn-up.log
mkdir -p /home/termino/.local/run

# Idempotenz: schon ein Tunnel da?
if pgrep -f "openconnect.*univpn.uni-graz.at" > /dev/null; then
    echo "[vpn_up] VPN-Tunnel laeuft bereits"
    exit 0
fi

# Phase 1: Auth (Qt-WebEngine headless via xvfb gegen Keycloak)
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
    echo "[vpn_up] AUTH FAILED - Output war nicht parsebar." >&2
    echo "Log: $LOG_FILE" >&2
    exit 1
fi

# Phase 2: Tunnel im Hintergrund. stdout/stderr ins Log, damit der daemonized
# openconnect keine Pipe ans systemd-Journal offen haelt (sonst haengt der Run).
echo "[vpn_up] Auth ok, starting tunnel..." >&2
sudo /usr/sbin/openconnect \
    --servercert "$FINGERPRINT" \
    --cookie "$COOKIE" \
    --background \
    --pid-file "$PID_FILE" \
    --no-dtls \
    "$HOST" >>"$LOG_FILE" 2>&1

# Cleanup ENV - Cookie nicht im Shell-State lassen.
unset HOST COOKIE FINGERPRINT AUTH_OUTPUT

# Auf tun0 warten (Kernel-Interface kommt einen Tick nach dem Daemon-Spawn).
for i in {1..10}; do
    if ip link show tun0 >/dev/null 2>&1; then
        echo "[vpn_up] tun0 ist up nach ${i}s"
        exit 0
    fi
    sleep 1
done

echo "[vpn_up] FEHLER: tun0 nicht da nach 10s. Log: $LOG_FILE" >&2
exit 2
