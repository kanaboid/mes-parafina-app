#!/bin/bash
# Konfiguracja MySQL PRIMARY na terminal3 (binlog + użytkownik replikacji).
#
# Uruchom JEDNOKROTNIE na terminal3:
#   ./scripts/mysql-replication-setup-primary.sh
#
# Wymaga w .env:
#   MYSQL_ROOT_PASSWORD
#   MYSQL_REPLICATION_USER (domyślnie: repl)
#   MYSQL_REPLICATION_PASSWORD

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

if [[ ! -f "${APP_DIR}/.env" ]]; then
    fail "Brak pliku ${APP_DIR}/.env"
fi

set -a
# shellcheck disable=SC1091
source "${APP_DIR}/.env"
set +a

REPL_USER="${MYSQL_REPLICATION_USER:-repl}"
REPL_PASSWORD="${MYSQL_REPLICATION_PASSWORD:-}"

if [[ -z "${MYSQL_ROOT_PASSWORD:-}" ]]; then
    fail "Ustaw MYSQL_ROOT_PASSWORD w .env"
fi

if [[ -z "${REPL_PASSWORD}" ]]; then
    fail "Ustaw MYSQL_REPLICATION_PASSWORD w .env (silne hasło tylko do replikacji)"
fi

if [[ ! -f "${PRIMARY_COMPOSE}" ]]; then
    fail "Brak pliku docker-compose.primary.yml"
fi

cd "${APP_DIR}"
export COMPOSE_FILE="${APP_DIR}/docker-compose.yml:${PRIMARY_COMPOSE}"

log "Restartuję MySQL z włączonym binlogiem (krótka przerwa w zapisach)..."
docker compose up -d db
sleep 10

log "Tworzę użytkownika replikacji: ${REPL_USER}..."
docker compose exec -T db mysql -u root -p"${MYSQL_ROOT_PASSWORD}" <<EOF
CREATE USER IF NOT EXISTS '${REPL_USER}'@'%' IDENTIFIED BY '${REPL_PASSWORD}';
GRANT REPLICATION SLAVE ON *.* TO '${REPL_USER}'@'%';

-- Zdalny dostęp root (wymagany do mysqldump z terminal1 przez sieć)
CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY '${MYSQL_ROOT_PASSWORD}';
ALTER USER 'root'@'%' IDENTIFIED BY '${MYSQL_ROOT_PASSWORD}';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;

FLUSH PRIVILEGES;
SHOW MASTER STATUS;
EOF

log ""
log "=== PRIMARY gotowy ==="
log "Na terminal3 otwórz port 3306 tylko dla terminal1 (przykład):"
log "  sudo ufw allow from IP_TERMINAL1 to any port 3306 proto tcp"
log ""
log "Następny krok na terminal1:"
log "  ./scripts/mysql-replication-setup-replica.sh"
