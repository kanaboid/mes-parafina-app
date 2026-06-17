#!/bin/bash
# Uruchamia stack monitoringu (Uptime Kuma lub Netdata).
#
# Użycie:
#   ./scripts/monitoring-start.sh kuma     # tylko oczyszczalnia-aio
#   ./scripts/monitoring-start.sh netdata  # na każdym hoście
#
# Przed pierwszym uruchomieniem:
#   cp monitoring/.env.example monitoring/.env
#   # edytuj MONITORING_HOSTNAME na każdym hoście

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/mes-parafina-app}"
MONITORING_DIR="${APP_DIR}/monitoring"
ENV_FILE="${MONITORING_DIR}/.env"

usage() {
    echo "Użycie: $0 kuma|netdata"
    exit 1
}

[[ $# -eq 1 ]] || usage

MODE="$1"
case "${MODE}" in
    kuma|netdata) ;;
    *) usage ;;
esac

if [[ ! -f "${MONITORING_DIR}/docker-compose.${MODE}.yml" ]]; then
    echo "Brak pliku ${MONITORING_DIR}/docker-compose.${MODE}.yml"
    exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "Brak ${ENV_FILE} — skopiuj z monitoring/.env.example i uzupełnij."
    exit 1
fi

cd "${MONITORING_DIR}"
docker compose --env-file "${ENV_FILE}" -f "docker-compose.${MODE}.yml" up -d

echo "Monitoring (${MODE}) uruchomiony."
if [[ "${MODE}" == "kuma" ]]; then
    # shellcheck disable=SC1091
    set -a && source "${ENV_FILE}" && set +a
    echo "Panel Kuma: http://$(hostname):${KUMA_PORT:-3001}/"
elif [[ "${MODE}" == "netdata" ]]; then
  echo "Panel Netdata: http://$(hostname):19999/"
fi
