#!/bin/bash
# Promocja repliki do PRIMARY przy failover (uruchom na terminal1 PRZED startem aplikacji).
#
#   ./scripts/mysql-replication-promote.sh
#   ./scripts/failover-start.sh --use-replication

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/mes-parafina-app}"
STANDBY_COMPOSE="${APP_DIR}/docker-compose.standby.yml"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

fail() {
    log "BŁĄD: $*"
    exit 1
}

if [[ ! -f "${APP_DIR}/.env" ]]; then
    fail "Brak pliku ${APP_DIR}/.env"
fi

set -a
# shellcheck disable=SC1091
source "${APP_DIR}/.env"
set +a

cd "${APP_DIR}"
export COMPOSE_FILE="${APP_DIR}/docker-compose.yml:${STANDBY_COMPOSE}:${APP_DIR}/docker-compose.failover.yml"

if ! docker compose ps --status running db | grep -q db; then
    fail "Kontener db nie działa — uruchom: ./scripts/mysql-replication-start-db.sh"
fi

log "Promuję replikę do PRIMARY (wyłączam replikację, zdejmuję read_only)..."
docker compose exec -T db mysql -u root -p"${MYSQL_ROOT_PASSWORD}" <<'EOF'
STOP REPLICA;
RESET REPLICA ALL;
SET GLOBAL read_only=OFF;
SET GLOBAL super_read_only=OFF;
EOF

log "Replika została promowana — można uruchomić aplikację:"
log "  ./scripts/failover-start.sh --no-restore"
