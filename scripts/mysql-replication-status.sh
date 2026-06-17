#!/bin/bash
# Status replikacji MySQL (uruchamiaj na terminal1 lub terminal3).

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/mes-parafina-app}"

if [[ ! -f "${APP_DIR}/.env" ]]; then
    echo "Brak pliku ${APP_DIR}/.env"
    exit 1
fi

set -a
# shellcheck disable=SC1091
source "${APP_DIR}/.env"
set +a

cd "${APP_DIR}"

# Wykryj host: terminal1 = replica, terminal3 = primary
HOSTNAME_SHORT="$(hostname | tr '[:upper:]' '[:lower:]')"
if [[ "${HOSTNAME_SHORT}" == *"terminal1"* ]]; then
    export COMPOSE_FILE="${APP_DIR}/docker-compose.yml:${APP_DIR}/docker-compose.standby.yml"
    MODE="REPLICA"
elif [[ "${HOSTNAME_SHORT}" == *"terminal3"* ]]; then
    export COMPOSE_FILE="${APP_DIR}/docker-compose.yml:${APP_DIR}/docker-compose.primary.yml"
    MODE="PRIMARY"
else
    MODE="DEFAULT"
fi

if ! docker compose ps --status running db 2>/dev/null | grep -q db; then
    echo "Kontener db nie działa."
    exit 1
fi

echo "=== MySQL ${MODE} — $(date) ==="

if [[ "${MODE}" == "PRIMARY" ]]; then
    docker compose exec -T db mysql -u root -p"${MYSQL_ROOT_PASSWORD}" -e "SHOW MASTER STATUS\G"
else
    docker compose exec -T db mysql -u root -p"${MYSQL_ROOT_PASSWORD}" -e "SHOW REPLICA STATUS\G" | \
        grep -E "Replica_IO_Running|Replica_SQL_Running|Seconds_Behind_Source|Source_Host|Last_Error|Last_SQL_Error"
fi
