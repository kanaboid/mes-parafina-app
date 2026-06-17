#!/bin/bash
# Sprawdza replikację MySQL na terminal1; opcjonalny ping do Uptime Kuma.
# Uruchamiaj z crona co 5 minut na terminal1.
#
# Przykład crona:
#   */5 * * * * /home/terminal1/mes-parafina-app/scripts/mysql-replication-healthcheck.sh >> /home/terminal1/mes-replication-health.log 2>&1
#
# W .env na terminal1 (opcjonalnie):
#   UPTIME_KUMA_REPLICATION_PUSH_URL=http://oczyszczalnia-aio:3001/api/push/TOKEN?status=up&msg=ok&ping=

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/mes-parafina-app}"
MAX_LAG_SECONDS="${MAX_LAG_SECONDS:-300}"

if [[ ! -f "${APP_DIR}/.env" ]]; then
    echo "Brak pliku ${APP_DIR}/.env"
    exit 1
fi

set -a
# shellcheck disable=SC1091
source "${APP_DIR}/.env"
set +a

cd "${APP_DIR}"
export COMPOSE_FILE="${APP_DIR}/docker-compose.yml:${APP_DIR}/docker-compose.standby.yml"

if ! docker compose ps --status running db 2>/dev/null | grep -q db; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] BŁĄD: kontener db nie działa"
    exit 1
fi

STATUS_RAW="$(docker compose exec -T db env MYSQL_PWD="${MYSQL_ROOT_PASSWORD}" mysql -h 127.0.0.1 -u root \
    -N -e "SHOW SLAVE STATUS\G" 2>/dev/null || true)"

if [[ -z "${STATUS_RAW}" ]]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] BŁĄD: brak SHOW SLAVE STATUS (replika nie skonfigurowana?)"
    exit 1
fi

get_field() {
    echo "${STATUS_RAW}" | awk -F': ' -v key="$1" '$1 == key {gsub(/^[ \t]+/, "", $2); print $2; exit}'
}

IO_RUNNING="$(get_field "Slave_IO_Running")"
SQL_RUNNING="$(get_field "Slave_SQL_Running")"
LAG="$(get_field "Seconds_Behind_Master")"
IO_ERROR="$(get_field "Last_IO_Error")"

if [[ "${IO_RUNNING}" != "Yes" || "${SQL_RUNNING}" != "Yes" ]]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] BŁĄD replikacji: IO=${IO_RUNNING} SQL=${SQL_RUNNING} lag=${LAG:-?} err=${IO_ERROR:-brak}"
    exit 1
fi

if [[ -n "${LAG}" && "${LAG}" != "NULL" && "${LAG}" -gt "${MAX_LAG_SECONDS}" ]]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] BŁĄD: opóźnienie replikacji ${LAG}s (max ${MAX_LAG_SECONDS}s)"
    exit 1
fi

if [[ -n "${UPTIME_KUMA_REPLICATION_PUSH_URL:-}" ]]; then
    UPTIME_KUMA_PUSH_URL="${UPTIME_KUMA_REPLICATION_PUSH_URL}" \
        UPTIME_KUMA_PUSH_MSG="repl OK lag=${LAG:-0}s" \
        "${APP_DIR}/scripts/monitoring-kuma-push.sh"
fi

# Domyślnie cisza przy sukcesie (żeby nie zaśmiecać logu crona).
