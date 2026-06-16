#!/bin/bash
# Prosty monitoring produkcji (terminal3) z hosta standby (terminal1).
# Uruchamiaj z crona co 5 minut.
#
# Przykład crona na terminal1:
#   */5 * * * * /home/terminal1/mes-parafina-app/scripts/monitor-primary.sh >> /home/terminal1/mes-monitor.log 2>&1

set -euo pipefail

PRIMARY_URL="${PRIMARY_URL:-http://terminal3/}"
LOG_FILE="${LOG_FILE:-$HOME/mes-monitor.log}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-10}"

TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"

if curl -sf --max-time "${TIMEOUT_SECONDS}" -o /dev/null "${PRIMARY_URL}"; then
    # Produkcja działa — opcjonalnie loguj tylko błędy (domyślnie cisza)
    :
else
    echo "${TIMESTAMP} AWARIA: brak odpowiedzi z ${PRIMARY_URL}" >> "${LOG_FILE}"
    exit 1
fi
