#!/bin/bash
# RECONSTRUCTED from the behaviour spec in the production status report
# (2026-06-01). The exact script on the running server was NOT captured
# verbatim - verify the live version and replace this if it differs.
#
# Checks whether today's termino.service run succeeded; if not, POSTs an alert
# to an ntfy.sh topic (push to phone). Runs as the `termino` user at 07:00 via
# termino-watchdog.timer.
set -uo pipefail

# ntfy.sh topic - set via the systemd Environment= (preferred) or here.
# Half-secret: anyone who knows the topic can read and post to it.
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
curl -s \
    -H "Title: Termino daily run FAILED on $(hostname)" \
    -H "Priority: high" \
    -H "Tags: warning,rotating_light" \
    -d "Result=${RESULT}, last run=${LAST_RUN_DATE} (today ${TODAY}).

Last journal lines:
${JOURNAL}" \
    "https://ntfy.sh/${NTFY_TOPIC}" > /dev/null
echo "[watchdog] alert pushed to ntfy topic"
