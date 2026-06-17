#!/bin/bash
# Backup bazy MySQL i konfiguracji MES Parafina.
# Uruchamiaj na hoście produkcyjnym (terminal3), np. z crona co godzinę.
#
# Zmienne opcjonalne:
#   KEEP_DAYS=14           — retencja lokalnie i na terminal1 (domyślnie 14)
#   ARCHIVE_KEEP_DAYS=90   — retencja archiwum na oczyszczalnia-aio (domyślnie 90)
#
# Wymaga:
# - działającego stacku Docker (docker compose up)
# - skonfigurowanego SSH do terminal1 i oczyszczalnia-aio
# - pliku .env w katalogu aplikacji

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/mes-parafina-app}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/mes-backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
ARCHIVE_KEEP_DAYS="${ARCHIVE_KEEP_DAYS:-90}"
DATE="$(date +%Y%m%d_%H%M%S)"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"

REMOTE_STANDBY="${REMOTE_STANDBY:-terminal1}"
REMOTE_STANDBY_PATH="${REMOTE_STANDBY_PATH:-~/mes-backups}"

REMOTE_ARCHIVE="${REMOTE_ARCHIVE:-oczyszczalnia-aio}"
REMOTE_ARCHIVE_PATH="${REMOTE_ARCHIVE_PATH:-~/mes-backups-archive}"

log() {
    echo "${LOG_PREFIX} $*"
}

fail() {
    log "BŁĄD: $*"
    exit 1
}

if [[ ! -f "${APP_DIR}/.env" ]]; then
    fail "Brak pliku ${APP_DIR}/.env"
fi

if [[ ! -f "${APP_DIR}/docker-compose.yml" ]]; then
    fail "Brak pliku ${APP_DIR}/docker-compose.yml"
fi

# Wczytaj hasła i zmienne z .env
set -a
# shellcheck disable=SC1091
source "${APP_DIR}/.env"
set +a

if [[ -z "${MYSQL_ROOT_PASSWORD:-}" ]]; then
    fail "MYSQL_ROOT_PASSWORD nie jest ustawione w .env"
fi

mkdir -p "${BACKUP_DIR}/mysql" "${BACKUP_DIR}/config"

cd "${APP_DIR}"

if ! docker compose ps --status running db | grep -q "db"; then
    fail "Kontener bazy danych (db) nie działa. Uruchom: docker compose up -d db"
fi

DUMP_FILE="${BACKUP_DIR}/mysql/mes_parafina_db_${DATE}.sql.gz"
log "Tworzę dump bazy do ${DUMP_FILE}..."

docker compose exec -T db \
    mysqldump -u root -p"${MYSQL_ROOT_PASSWORD}" \
    --single-transaction \
    --routines \
    --triggers \
    --databases mes_parafina_db \
    | gzip > "${DUMP_FILE}"

log "Dump utworzony ($(du -h "${DUMP_FILE}" | cut -f1))."

# Kopia konfiguracji (bez commitowania do git)
cp "${APP_DIR}/.env" "${BACKUP_DIR}/config/env_${DATE}.bak"
cp "${APP_DIR}/docker-compose.yml" "${BACKUP_DIR}/config/docker-compose_${DATE}.yml"

# Symlink względny — działa też na terminal1 po rsync (nie używaj ścieżek absolutnych)
ln -sfn "mes_parafina_db_${DATE}.sql.gz" "${BACKUP_DIR}/mysql/latest.sql.gz"
ln -sfn "env_${DATE}.bak" "${BACKUP_DIR}/config/env_latest.bak"

# Usuń stare backupy lokalne
find "${BACKUP_DIR}/mysql" -name "*.sql.gz" -type f -mtime +"${KEEP_DAYS}" -delete
find "${BACKUP_DIR}/config" -name "env_*.bak" -type f -mtime +"${KEEP_DAYS}" -delete
find "${BACKUP_DIR}/config" -name "docker-compose_*.yml" -type f -mtime +"${KEEP_DAYS}" -delete

log "Wysyłam kopię na ${REMOTE_STANDBY}:${REMOTE_STANDBY_PATH}..."
rsync -az --delete "${BACKUP_DIR}/" "${REMOTE_STANDBY}:${REMOTE_STANDBY_PATH}/"

log "Wysyłam archiwum dumpa na ${REMOTE_ARCHIVE}:${REMOTE_ARCHIVE_PATH}/mysql/..."
ssh "${REMOTE_ARCHIVE}" "mkdir -p ${REMOTE_ARCHIVE_PATH}/mysql"
rsync -az "${DUMP_FILE}" "${REMOTE_ARCHIVE}:${REMOTE_ARCHIVE_PATH}/mysql/"

log "Usuwam archiwum starsze niż ${ARCHIVE_KEEP_DAYS} dni na ${REMOTE_ARCHIVE}..."
ssh "${REMOTE_ARCHIVE}" \
    "find ${REMOTE_ARCHIVE_PATH}/mysql -name 'mes_parafina_db_*.sql.gz' -type f -mtime +${ARCHIVE_KEEP_DAYS} -delete"

log "Backup zakończony pomyślnie."

if [[ -n "${UPTIME_KUMA_BACKUP_PUSH_URL:-}" ]]; then
    UPTIME_KUMA_PUSH_URL="${UPTIME_KUMA_BACKUP_PUSH_URL}" \
        UPTIME_KUMA_PUSH_MSG="backup OK ${DATE}" \
        "${APP_DIR}/scripts/monitoring-kuma-push.sh"
fi
