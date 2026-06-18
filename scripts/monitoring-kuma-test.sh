#!/bin/bash
# Test połączenia Push → Uptime Kuma (terminal3 lub terminal1).
#
# Użycie:
#   ./scripts/monitoring-kuma-test.sh backup      # terminal3 — czyta UPTIME_KUMA_BACKUP_PUSH_URL
#   ./scripts/monitoring-kuma-test.sh replication # terminal1 — UPTIME_KUMA_REPLICATION_PUSH_URL
#
# Albo z pełnym URL:
#   ./scripts/monitoring-kuma-test.sh 'http://oczyszczalnia-aio:3001/api/push/TOKEN'

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/mes-parafina-app}"
MODE="${1:-}"

usage() {
    echo "Użycie: $0 backup|replication|PEŁNY_URL_PUSH"
    exit 1
}

[[ -n "${MODE}" ]] || usage

if [[ "${MODE}" == http* ]]; then
    PUSH_URL="${MODE}"
elif [[ -f "${APP_DIR}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${APP_DIR}/.env"
    set +a
    if [[ "${MODE}" == "backup" ]]; then
        PUSH_URL="${UPTIME_KUMA_BACKUP_PUSH_URL:-}"
    elif [[ "${MODE}" == "replication" ]]; then
        PUSH_URL="${UPTIME_KUMA_REPLICATION_PUSH_URL:-}"
    else
        usage
    fi
else
    echo "Brak ${APP_DIR}/.env"
    exit 1
fi

if [[ -z "${PUSH_URL}" ]]; then
    echo "BŁĄD: brak URL Push w .env (sprawdź nazwę zmiennej i cudzysłowy wokół URL)."
    exit 1
fi

# Wyciągnij host Kuma do testu sieci
KUMA_HOST="$(echo "${PUSH_URL}" | sed -n 's|^[a-z]*://\([^/:]*\).*|\1|p')"
KUMA_PORT="$(echo "${PUSH_URL}" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')"
KUMA_PORT="${KUMA_PORT:-3001}"

echo "=== Test Push Uptime Kuma ==="
echo "URL (skrócony): ${PUSH_URL%%\?*}..."
echo "Host Kuma: ${KUMA_HOST}:${KUMA_PORT}"
echo ""

echo "1) Ping / port TCP..."
if command -v nc >/dev/null 2>&1; then
    if nc -z -w 5 "${KUMA_HOST}" "${KUMA_PORT}" 2>/dev/null; then
        echo "   OK — port ${KUMA_PORT} otwarty"
    else
        echo "   BŁĄD — brak połączenia z ${KUMA_HOST}:${KUMA_PORT}"
        echo "   Na oczyszczalnia-aio: sudo ufw allow from IP_TERMINAL3 to any port 3001"
        echo "   Na oczyszczalnia-aio: sudo ufw allow from IP_TERMINAL1 to any port 3001"
        exit 1
    fi
else
    echo "   (pominięto — brak nc)"
fi

echo ""
echo "2) Wysyłam testowy push..."
HTTP_CODE="$(curl -sS -m 15 -o /tmp/kuma-push-test.out -w '%{http_code}' -G "${PUSH_URL}" \
    --data-urlencode "status=up" \
    --data-urlencode "msg=test-$(hostname)-$(date +%H%M%S)" \
    --data-urlencode "ping=" || echo "000")"

echo "   HTTP: ${HTTP_CODE}"
if [[ -f /tmp/kuma-push-test.out ]]; then
    echo "   Odpowiedź: $(cat /tmp/kuma-push-test.out)"
fi

if [[ "${HTTP_CODE}" == "200" ]]; then
    echo ""
    echo "OK — sprawdź w Kuma, czy monitor Push pokazał heartbeat."
    exit 0
fi

echo ""
echo "BŁĄD push. Typowe przyczyny:"
echo "  - URL w .env BEZ cudzysłowów (znak & ucina wartość) — patrz docs/monitoring.md"
echo "  - zły token w URL (skopiuj ponownie z Kuma → Edit → Push URL)"
echo "  - firewall na oczyszczalnia-aio blokuje terminal3/terminal1"
exit 1
