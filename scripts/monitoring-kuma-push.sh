#!/bin/bash
# Wysyła ping sukcesu do monitora Push w Uptime Kuma.
# Brak pingów w zadanym interwale = alert w Kuma.
#
# Użycie:
#   ./scripts/monitoring-kuma-push.sh "http://oczyszczalnia-aio:3001/api/push/TOKEN?status=up&msg=ok&ping="
#   UPTIME_KUMA_PUSH_URL='http://...' ./scripts/monitoring-kuma-push.sh
#
# Zmienne:
#   UPTIME_KUMA_PUSH_URL — pełny URL Push (z tokenem z panelu Kuma)
#   UPTIME_KUMA_PUSH_MSG   — opcjonalny komunikat (domyślnie: ok)

set -euo pipefail

PUSH_URL="${1:-${UPTIME_KUMA_PUSH_URL:-}}"
PUSH_MSG="${UPTIME_KUMA_PUSH_MSG:-ok}"

if [[ -z "${PUSH_URL}" ]]; then
    exit 0
fi

# Nie przerywaj głównego zadania (backup, cron), gdy Kuma chwilowo niedostępna.
curl -fsS -m 15 -G "${PUSH_URL}" \
    --data-urlencode "status=up" \
    --data-urlencode "msg=${PUSH_MSG}" \
    --data-urlencode "ping=" \
    >/dev/null 2>&1 || true
