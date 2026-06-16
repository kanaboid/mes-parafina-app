#!/bin/bash
# Zatrzymanie stacku MES na hoście standby (np. po teście lub przed powrotem na terminal3).
#
# Przykład:
#   ./scripts/failover-stop.sh
#   ./scripts/failover-stop.sh --volumes   # UWAGA: kasuje dane MySQL w Dockerze

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/mes-parafina-app}"
REMOVE_VOLUMES=0

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --volumes) REMOVE_VOLUMES=1; shift ;;
        -h|--help)
            echo "Użycie: $0 [--volumes]"
            echo "  --volumes  Usuń wolumeny Docker (kasuje lokalną bazę w kontenerze)"
            exit 0
            ;;
        *) log "Nieznana opcja: $1"; exit 1 ;;
    esac
done

cd "${APP_DIR}"

if [[ "${REMOVE_VOLUMES}" -eq 1 ]]; then
    log "UWAGA: Zatrzymuję stack i usuwam wolumeny (dane MySQL w Dockerze zostaną skasowane)."
    read -r -p "Kontynuować? (tak/nie): " CONFIRM
    if [[ "${CONFIRM}" != "tak" ]]; then
        log "Anulowano."
        exit 0
    fi
    docker compose down -v
else
    log "Zatrzymuję stack (dane w wolumenie mysql_data zostają)..."
    docker compose down
fi

log "Stack zatrzymany."
