#!/bin/bash
# Przywrócenie trybu standby na terminal1 po teście failover.
# Zatrzymuje aplikację, synchronizuje bazę z terminal3 i uruchamia samą replikę.
#
# UWAGA: Nadpisuje lokalną bazę na terminal1 danymi z terminal3
# (zmiany z testu failover na terminal1 zostaną utracone).

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/mes-parafina-app}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log "=== Przywracanie trybu standby (replika) ==="
log ""

if docker compose -f "${APP_DIR}/docker-compose.yml" \
    -f "${APP_DIR}/docker-compose.standby.yml" ps --status running 2>/dev/null | grep -qE 'web|celery'; then
    log "Krok 1/3: Zatrzymuję stack failover..."
    "${APP_DIR}/scripts/failover-stop.sh"
else
    log "Krok 1/3: Stack aplikacji już zatrzymany — pomijam failover-stop."
    docker compose -f "${APP_DIR}/docker-compose.yml" \
        -f "${APP_DIR}/docker-compose.standby.yml" down 2>/dev/null || true
fi

log ""
log "Krok 2/3: Synchronizacja bazy z terminal3 (setup-replica)..."
"${APP_DIR}/scripts/mysql-replication-setup-replica.sh"

log ""
log "Krok 3/3: Uruchamiam tylko kontener MySQL (bez aplikacji web)..."
"${APP_DIR}/scripts/mysql-replication-start-db.sh"

log ""
log "=== Standby przywrócony ==="
log "terminal1 jest z powrotem repliką terminal3."
log "Produkcja powinna działać tylko na terminal3."
