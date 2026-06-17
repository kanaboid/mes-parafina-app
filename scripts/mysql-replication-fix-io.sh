#!/bin/bash
# Naprawa repliki gdy Slave_IO_Running: Connecting (zwykle zły MASTER_HOST w kontenerze).
# Uruchom na terminal1 — bez ponownego dumpa.

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

source "${APP_DIR}/.env"

PRIMARY_HOST="${PRIMARY_HOST:-terminal3}"
REPL_USER="${MYSQL_REPLICATION_USER:-repl}"
REPL_PASSWORD="${MYSQL_REPLICATION_PASSWORD:-}"

PRIMARY_IP="$(getent hosts "${PRIMARY_HOST}" | awk '{print $1}' | head -1)"
if [[ -z "${PRIMARY_IP}" ]]; then
    fail "Nie można rozwiązać ${PRIMARY_HOST}. Ustaw PRIMARY_HOST na IP w .env"
fi

cd "${APP_DIR}"
export COMPOSE_FILE="${APP_DIR}/docker-compose.yml:${STANDBY_COMPOSE}"

log "Ustawiam MASTER_HOST=${PRIMARY_IP} (${PRIMARY_HOST})..."

docker compose exec -T db env MYSQL_PWD="${MYSQL_ROOT_PASSWORD}" mysql -h 127.0.0.1 -u root <<EOF
STOP SLAVE;
CHANGE MASTER TO
  MASTER_HOST='${PRIMARY_IP}',
  MASTER_USER='${REPL_USER}',
  MASTER_PASSWORD='${REPL_PASSWORD}',
  MASTER_PORT=3306;
START SLAVE;
EOF

sleep 3
"${APP_DIR}/scripts/mysql-replication-status.sh"
