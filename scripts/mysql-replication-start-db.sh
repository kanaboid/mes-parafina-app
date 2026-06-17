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
sleep 5
"${APP_DIR}/scripts/mysql-replication-status.sh"
