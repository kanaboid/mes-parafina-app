#!/bin/bash
# Uruchomienie systemu MES na hoście standby (terminal1) po awarii produkcji (terminal3).
#
# Przykłady:
#   ./scripts/failover-start.sh
#   ./scripts/failover-start.sh --no-restore
#   ./scripts/failover-start.sh --sync-env
#   DUMP_FILE=~/mes-backups/mysql/mes_parafina_db_20260616_180001.sql.gz ./scripts/failover-start.sh

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/mes-parafina-app}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/mes-backups}"
DUMP_FILE="${DUMP_FILE:-${BACKUP_DIR}/mysql/latest.sql.gz}"
APP_URL="${APP_URL:-http://localhost/}"
DB_WAIT_SECONDS="${DB_WAIT_SECONDS:-30}"

DO_RESTORE=1
SYNC_ENV=0

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

fail() {
    log "BŁĄD: $*"
    exit 1
}

usage() {
    cat <<EOF
Użycie: $0 [opcje]

Opcje:
  --no-restore   Uruchom stack bez przywracania bazy (baza już istnieje)
  --sync-env     Skopiuj .env z ostatniego backupu przed startem
  -h, --help     Ta pomoc

Zmienne środowiskowe:
  APP_DIR        Katalog aplikacji (domyślnie ~/mes-parafina-app)
  BACKUP_DIR     Katalog backupów (domyślnie ~/mes-backups)
  DUMP_FILE      Plik dumpa do restore (domyślnie ~/mes-backups/mysql/latest.sql.gz)
  APP_URL        URL do testu HTTP (domyślnie http://localhost/ — port 80)
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-restore) DO_RESTORE=0; shift ;;
        --sync-env) SYNC_ENV=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) fail "Nieznana opcja: $1 (użyj --help)" ;;
    esac
done

if [[ ! -d "${APP_DIR}" ]]; then
    fail "Brak katalogu aplikacji: ${APP_DIR}"
fi

cd "${APP_DIR}"

STANDBY_COMPOSE="${APP_DIR}/docker-compose.standby.yml"
if [[ ! -f "${STANDBY_COMPOSE}" ]]; then
    fail "Brak pliku docker-compose.standby.yml"
fi
export COMPOSE_FILE="${APP_DIR}/docker-compose.yml:${STANDBY_COMPOSE}"
log "Używam portu 80 (docker-compose.standby.yml)."

if [[ "${SYNC_ENV}" -eq 1 ]]; then
    ENV_BACKUP="${BACKUP_DIR}/config/env_latest.bak"
    if [[ ! -f "${ENV_BACKUP}" ]]; then
        fail "Brak pliku ${ENV_BACKUP} — najpierw uruchom backup na terminal3"
    fi
    cp "${ENV_BACKUP}" "${APP_DIR}/.env"
    log "Skopiowano .env z backupu."
fi

if [[ ! -f "${APP_DIR}/.env" ]]; then
    fail "Brak pliku .env — uruchom z --sync-env lub skopiuj ręcznie z backupu"
fi

log "Uruchamiam kontener bazy danych..."
docker compose up -d db
log "Czekam ${DB_WAIT_SECONDS}s na MySQL..."
sleep "${DB_WAIT_SECONDS}"

if [[ "${DO_RESTORE}" -eq 1 ]]; then
    if [[ ! -f "${DUMP_FILE}" ]]; then
        fail "Brak pliku dumpa: ${DUMP_FILE}"
    fi
    log "Przywracam bazę z ${DUMP_FILE}..."
    SKIP_CONFIRM=tak "${APP_DIR}/scripts/restore-mes.sh" "${DUMP_FILE}"
else
    log "Pomijam restore (--no-restore)."
fi

log "Uruchamiam pełny stack..."
docker compose up -d

log "Aktualizuję schemat bazy (alembic)..."
docker compose exec -T web alembic upgrade head

log "Sprawdzam dostępność aplikacji pod ${APP_URL}..."
if curl -sf --max-time 15 -o /dev/null "${APP_URL}/"; then
    log "Aplikacja odpowiada OK."
else
    log "UWAGA: Brak odpowiedzi HTTP pod ${APP_URL} — sprawdź logi:"
    log "  docker compose logs -f web"
fi

log ""
log "=== Failover zakończony ==="
log "Następne kroki:"
log "  1. Sprawdź aplikację w przeglądarce: http://terminal1/"
log "  2. Przekieruj użytkowników (DNS / /etc/hosts: terminal3 → IP terminal1)"
log "  3. Logi: docker compose -f docker-compose.yml -f docker-compose.standby.yml logs -f web"
log "  4. Szczegóły: docs/disaster-recovery.md"
