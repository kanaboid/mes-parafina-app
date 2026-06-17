#!/bin/bash
# Uruchom tylko kontener MySQL-replica na terminal1 (bez aplikacji web).
# Dodaj do crona @reboot na terminal1.

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/mes-parafina-app}"
STANDBY_COMPOSE="${APP_DIR}/docker-compose.standby.yml"

cd "${APP_DIR}"
export COMPOSE_FILE="${APP_DIR}/docker-compose.yml:${STANDBY_COMPOSE}"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Uruchamiam MySQL replica..."
docker compose up -d db
sleep 10

if [[ -f "${APP_DIR}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${APP_DIR}/.env"
    set +a
    # read_only tylko gdy replikacja już skonfigurowana (standby)
    docker compose exec -T db mysql -u root -p"${MYSQL_ROOT_PASSWORD}" -e \
        "SET GLOBAL read_only=ON; SET GLOBAL super_read_only=ON;" 2>/dev/null || true
fi

"${APP_DIR}/scripts/mysql-replication-status.sh"
