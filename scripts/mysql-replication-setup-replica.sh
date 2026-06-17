#!/bin/bash
# Inicjalizacja repliki MySQL na terminal1 (pierwsza synchronizacja + START REPLICA).
#
# Uruchom na terminal1 (wymaga działającego PRIMARY na terminal3):
#   ./scripts/mysql-replication-setup-replica.sh
#
# W .env na terminal1 ustaw:
#   PRIMARY_HOST=terminal3
#   MYSQL_REPLICATION_USER=repl
#   MYSQL_REPLICATION_PASSWORD=...  (to samo co na terminal3)

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/mes-parafina-app}"
STANDBY_COMPOSE="${APP_DIR}/docker-compose.standby.yml"
TMP_DUMP="/tmp/mes_replica_init_$$.sql"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

fail() {
    log "BŁĄD: $*"
    rm -f "${TMP_DUMP}"
    exit 1
}

cleanup() {
    rm -f "${TMP_DUMP}"
}
trap cleanup EXIT

if [[ ! -f "${APP_DIR}/.env" ]]; then
    fail "Brak pliku ${APP_DIR}/.env"
fi

set -a
# shellcheck disable=SC1091
source "${APP_DIR}/.env"
set +a

PRIMARY_HOST="${PRIMARY_HOST:-terminal3}"
REPL_USER="${MYSQL_REPLICATION_USER:-repl}"
REPL_PASSWORD="${MYSQL_REPLICATION_PASSWORD:-}"

test_primary_connection() {
    local host="$1"
    docker run --rm --network host mysql:8.0 mysqladmin ping \
        -h "${host}" -P 3306 -u root -p"${MYSQL_ROOT_PASSWORD}" --connect-timeout=5 --silent 2>&1
}

if [[ -z "${MYSQL_ROOT_PASSWORD:-}" || -z "${REPL_PASSWORD}" ]]; then
    fail "Ustaw MYSQL_ROOT_PASSWORD i MYSQL_REPLICATION_PASSWORD w .env"
fi

# Obraz MySQL w Dockerze nie pozwala na MYSQL_USER=root przy pierwszej inicjalizacji.
if [[ "${MYSQLUSER:-root}" == "root" ]]; then
    log "MYSQLUSER=root w .env — kontener użyje mes_user (wymóg obrazu mysql:8.0)."
    export MYSQLUSER="mes_user"
fi

cd "${APP_DIR}"
export COMPOSE_FILE="${APP_DIR}/docker-compose.yml:${STANDBY_COMPOSE}"

log "Sprawdzam połączenie z PRIMARY (${PRIMARY_HOST}:3306)..."
CONN_ERROR="$(test_primary_connection "${PRIMARY_HOST}" || true)"
if [[ "${CONN_ERROR}" != *"mysqld is alive"* ]]; then
    log "Błąd połączenia: ${CONN_ERROR}"
    log ""
    log "Diagnostyka na terminal1:"
    log "  ping -c 2 ${PRIMARY_HOST}"
    log "  nc -zv ${PRIMARY_HOST} 3306"
    log "  getent hosts ${PRIMARY_HOST}"
    log ""
    log "Jeśli hostname nie działa, ustaw w .env IP terminal3:"
    log "  PRIMARY_HOST=100.x.x.x"
    log ""
    log "Na terminal3 uruchom ponownie (dodaje root@'%'):"
    log "  ./scripts/mysql-replication-setup-primary.sh"
    fail "Brak połączenia z PRIMARY."
fi
log "Połączenie z PRIMARY OK."

log "UWAGA: Zostanie nadpisana lokalna baza w Dockerze na terminal1."
read -r -p "Kontynuować inicjalizację repliki? (tak/nie): " CONFIRM
if [[ "${CONFIRM}" != "tak" ]]; then
    log "Anulowano."
    exit 0
fi

log "Zatrzymuję lokalny MySQL i usuwam stary wolumen..."
export COMPOSE_FILE="${APP_DIR}/docker-compose.yml:${STANDBY_COMPOSE}"
docker compose stop db web celery-worker flower 2>/dev/null || true
docker compose rm -f db 2>/dev/null || true
docker volume rm mes-parafina-app_mysql_data 2>/dev/null || \
    docker volume rm "$(basename "${APP_DIR}")_mysql_data" 2>/dev/null || true

wait_for_db() {
    local i
    for i in $(seq 1 30); do
        if docker compose exec -T db env MYSQL_PWD="${MYSQL_ROOT_PASSWORD}" \
            mysqladmin -h 127.0.0.1 -u root ping --silent 2>/dev/null; then
            return 0
        fi
        sleep 2
    done
    log "Logi kontenera db:"
    docker compose logs --tail 30 db
    fail "MySQL nie wystartował w czasie 60s."
}

log "Uruchamiam pusty kontener MySQL (replica)..."
docker compose up -d db
log "Czekam na gotowość MySQL..."
wait_for_db

log "Pobieram dump z PRIMARY (z pozycją binlog)..."
docker run --rm --network host mysql:8.0 mysqldump \
    -h "${PRIMARY_HOST}" -P 3306 \
    -u root -p"${MYSQL_ROOT_PASSWORD}" \
    --single-transaction \
    --source-data=2 \
    --set-gtid-purged=OFF \
    --routines \
    --triggers \
    --databases mes_parafina_db \
    > "${TMP_DUMP}"

log "Przywracam dane na replice..."
if ! docker compose exec -T db env MYSQL_PWD="${MYSQL_ROOT_PASSWORD}" \
    mysql -h 127.0.0.1 -u root < "${TMP_DUMP}"; then
    log "Sprawdź hasło root lokalnie:"
    log "  docker compose exec db env MYSQL_PWD=\"\$MYSQL_ROOT_PASSWORD\" mysql -h 127.0.0.1 -u root -e \"SELECT 1\""
    fail "Nie udało się przywrócić dumpa na replice."
fi

SOURCE_LINE="$(grep -m1 '^-- CHANGE REPLICATION SOURCE TO' "${TMP_DUMP}" | sed 's/^-- //' || true)"
MASTER_LINE="$(grep -m1 '^-- CHANGE MASTER TO' "${TMP_DUMP}" | sed 's/^-- //' || true)"

if [[ -n "${SOURCE_LINE}" ]]; then
    LOG_FILE="$(echo "${SOURCE_LINE}" | sed -n "s/.*SOURCE_LOG_FILE='\([^']*\)'.*/\1/p")"
    LOG_POS="$(echo "${SOURCE_LINE}" | sed -n 's/.*SOURCE_LOG_POS=\([0-9]*\).*/\1/p')"
elif [[ -n "${MASTER_LINE}" ]]; then
    LOG_FILE="$(echo "${MASTER_LINE}" | sed -n "s/.*MASTER_LOG_FILE='\([^']*\)'.*/\1/p")"
    LOG_POS="$(echo "${MASTER_LINE}" | sed -n 's/.*MASTER_LOG_POS=\([0-9]*\).*/\1/p')"
else
    fail "Nie znaleziono pozycji binlog w dumpie — czy PRIMARY ma włączony binlog?"
fi

if [[ -z "${LOG_FILE}" || -z "${LOG_POS}" ]]; then
    fail "Nie udało się odczytać pozycji binlog z dumpa."
fi

# Kontener MySQL nie zawsze rozwiązuje hostname — użyj IP dla MASTER_HOST
PRIMARY_IP="$(getent hosts "${PRIMARY_HOST}" | awk '{print $1}' | head -1)"
if [[ -z "${PRIMARY_IP}" ]]; then
    fail "Nie można rozwiązać PRIMARY_HOST=${PRIMARY_HOST} do adresu IP."
fi
log "MASTER_HOST=${PRIMARY_IP} (z ${PRIMARY_HOST})"

log "Konfiguruję replikację (MASTER_LOG_FILE=${LOG_FILE}, MASTER_LOG_POS=${LOG_POS})..."
docker compose exec -T db env MYSQL_PWD="${MYSQL_ROOT_PASSWORD}" mysql -h 127.0.0.1 -u root <<EOF
STOP SLAVE;
RESET SLAVE ALL;
CHANGE MASTER TO
  MASTER_HOST='${PRIMARY_IP}',
  MASTER_USER='${REPL_USER}',
  MASTER_PASSWORD='${REPL_PASSWORD}',
  MASTER_PORT=3306,
  MASTER_LOG_FILE='${LOG_FILE}',
  MASTER_LOG_POS=${LOG_POS};
START SLAVE;
SET GLOBAL read_only=ON;
SET GLOBAL super_read_only=ON;
EOF

sleep 5
"${APP_DIR}/scripts/mysql-replication-status.sh"

log ""
log "=== Replika skonfigurowana ==="
log "Na terminal1 uruchom tylko bazę (bez aplikacji web):"
log "  ./scripts/mysql-replication-start-db.sh"
log ""
log "Sprawdzaj status:"
log "  ./scripts/mysql-replication-status.sh"
