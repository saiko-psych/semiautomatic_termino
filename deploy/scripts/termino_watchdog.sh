#!/bin/bash
# Termino watchdog - alerts via ntfy.sh if today's daily run did not succeed.
#
# Behaviour, install path and exit codes are VERIFIED against CT 131
# (2026-06-13), but the exact byte-for-byte body of the live script was not
# captured - treat this as a faithful reconstruction. The real script is
# installed root:root, mode 0755, at /usr/local/bin/termino_watchdog.sh
# (~1979 bytes). Diff before relying on it:
#     diff /usr/local/bin/termino_watchdog.sh deploy/scripts/termino_watchdog.sh
#
# Runs daily at 07:00 (one hour after the daily run) via termino-watchdog.timer.
# Exit codes: 0 = run succeeded today, 1 = alert sent, 2 = alert failed to send.
set -uo pipefail

# ntfy.sh topic to push to (half-secret: anyone who knows it can read/post).
NTFY_TOPIC="${NTFY_TOPIC:-<NTFY_TOPIC>}"

RESULT=$(systemctl show termino.service -p Result --value)
TODAY=$(date +%Y-%m-%d)
# Date of the last termino.service run (its main-process exit timestamp).
LAST_RUN_DATE=$(systemctl show termino.service -p ExecMainExitTimestamp --value | awk '{print $2}')

if [ "$RESULT" = "success" ] && [ "$LAST_RUN_DATE" = "$TODAY" ]; then
    echo "[watchdog] OK - termino.service succeeded today ($TODAY)"
    exit 0
fi

echo "[watchdog] ALERT - Result=$RESULT, last run=$LAST_RUN_DATE, today=$TODAY" >&2
JOURNAL=$(journalctl -u termino.service -n 20 --no-pager 2>/dev/null || true)
if curl -sf \
    -H "Title: Termino daily run FAILED on $(hostname)" \
    -H "Priority: high" \
    -H "Tags: warning,rotating_light" \
    -d "Result=${RESULT}, last run=${LAST_RUN_DATE} (today ${TODAY}).

Last journal lines:
${JOURNAL}" \
    "https://ntfy.sh/${NTFY_TOPIC}" > /dev/null; then
    echo "[watchdog] alert pushed to ntfy topic"
    exit 1
fi
echo "[watchdog] FAILED to push alert to ntfy" >&2
exit 2
