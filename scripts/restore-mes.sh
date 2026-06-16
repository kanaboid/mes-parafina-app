#!/bin/bash
# Przywracanie bazy MySQL z pliku .sql.gz (np. przy failover na terminal1).
#
# Przykład:
#   ./scripts/restore-mes.sh ~/mes-backups/mysql/latest.sql.gz
#   ./scripts/restore-mes.sh ~/mes-backups/mysql/mes_parafina_db_20260615_120000.sql.gz

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/mes-parafina-app}"
DUMP_FILE="${1:-}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

fail() {
    log "BŁĄD: $*"
    exit 1
}

if [[ -z "${DUMP_FILE}" ]]; then
    echo "Użycie: $0 <ścieżka_do_pliku.sql.gz>"
    echo ""
    echo "Przykłady:"
    echo "  $0 ~/mes-backups/mysql/latest.sql.gz"
    echo "  $0 ~/mes-backups/mysql/mes_parafina_db_20260615_120000.sql.gz"
    exit 1
fi

if [[ ! -f "${DUMP_FILE}" ]]; then
    fail "Plik nie istnieje: ${DUMP_FILE}"
fi

if [[ ! -f "${APP_DIR}/.env" ]]; then
    fail "Brak pliku ${APP_DIR}/.env"
fi

set -a
# shellcheck disable=SC1091
source "${APP_DIR}/.env"
set +a

if [[ -z "${MYSQL_ROOT_PASSWORD:-}" ]]; then
    fail "MYSQL_ROOT_PASSWORD nie jest ustawione w .env"
fi

cd "${APP_DIR}"

log "UWAGA: Ta operacja nadpisze dane w bazie mes_parafina_db."
read -r -p "Kontynuować? (tak/nie): " CONFIRM
if [[ "${CONFIRM}" != "tak" ]]; then
    log "Anulowano."
    exit 0
fi

if ! docker compose ps --status running db | grep -q "db"; then
    log "Kontener db nie działa — uruchamiam stack..."
    docker compose up -d db
    sleep 15
fi

log "Przywracam bazę z ${DUMP_FILE}..."

gunzip -c "${DUMP_FILE}" | docker compose exec -T db \
    mysql -u root -p"${MYSQL_ROOT_PASSWORD}"

log "Restore zakończony. Sprawdź aplikację:"
log "  docker compose up -d"
log "  docker compose exec web alembic upgrade head"
