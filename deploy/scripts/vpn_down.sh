#!/bin/bash
# Schliesst den Uni-Graz-VPN-Tunnel sauber.
# PID via pgrep - das PID-File gehoert root (von sudo openconnect), der
# termino-User kann es nicht lesen. Wird vom systemd-Service als ExecStopPost
# aufgerufen (laeuft also auch, wenn der Hauptlauf gecrasht ist).
set -uo pipefail

# Alle openconnect-PIDs zu unserem Server finden.
PIDS=$(pgrep -f "openconnect.*univpn.uni-graz.at" || true)

if [ -n "$PIDS" ]; then
    echo "[vpn_down] Killing openconnect: $PIDS"
    for PID in $PIDS; do
        sudo /bin/kill "$PID" || true
    done

    # Auf clean shutdown warten.
    for i in {1..10}; do
        if ! pgrep -f "openconnect.*univpn.uni-graz.at" > /dev/null; then
            break
        fi
        sleep 1
    done

    # Failsafe: exakt die in sudoers erlaubte pkill-Form (ohne -f/Pattern).
    if pgrep -f "openconnect.*univpn.uni-graz.at" > /dev/null; then
        echo "[vpn_down] Failsafe pkill"
        sudo /usr/bin/pkill openconnect || true
        sleep 2
    fi
fi

# Final-Check.
if pgrep -f "openconnect.*univpn.uni-graz.at" > /dev/null; then
    echo "[vpn_down] WARNUNG: openconnect laeuft noch"
    exit 1
fi
echo "[vpn_down] Tunnel down"
