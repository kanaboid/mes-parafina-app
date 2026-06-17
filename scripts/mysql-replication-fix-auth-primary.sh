#!/bin/bash
# Naprawa uwierzytelniania replikacji (caching_sha2_password wymaga SSL).
# Uruchom na terminal3 — ustawia mysql_native_password dla użytkownika repl.
#
# Błąd na replice:
#   Authentication requires secure connection

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/mes-parafina-app}"
PRIMARY_COMPOSE="${APP_DIR}/docker-compose.primary.yml"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

fail() {
    log "BŁĄD: $*"
    exit 1
}

source "${APP_DIR}/.env"

REPL_USER="${MYSQL_REPLICATION_USER:-repl}"
REPL_PASSWORD="${MYSQL_REPLICATION_PASSWORD:-}"

if [[ -z "${REPL_PASSWORD}" ]]; then
    fail "Ustaw MYSQL_REPLICATION_PASSWORD w .env"
fi

cd "${APP_DIR}"
export COMPOSE_FILE="${APP_DIR}/docker-compose.yml:${PRIMARY_COMPOSE}"

log "Ustawiam mysql_native_password dla ${REPL_USER}@'%'..."
docker compose exec -T db mysql -u root -p"${MYSQL_ROOT_PASSWORD}" <<EOF
ALTER USER '${REPL_USER}'@'%' IDENTIFIED WITH mysql_native_password BY '${REPL_PASSWORD}';
FLUSH PRIVILEGES;
EOF

log "Gotowe. Na terminal1 uruchom:"
log "  ./scripts/mysql-replication-fix-io.sh"
