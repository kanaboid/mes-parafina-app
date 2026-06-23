#!/bin/bash
# Uruchamia stack monitoringu (Uptime Kuma lub Netdata).
#
# Użycie:
#   ./scripts/monitoring-start.sh kuma     # tylko oczyszczalnia-aio
#   ./scripts/monitoring-start.sh netdata  # na każdym hoście
#   ./scripts/monitoring-start.sh dashboard  # tylko oczyszczalnia-aio
#
# Przed pierwszym uruchomieniem:
#   cp monitoring/.env.example monitoring/.env
#   # edytuj MONITORING_HOSTNAME na każdym hoście

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/mes-parafina-app}"
MONITORING_DIR="${APP_DIR}/monitoring"
ENV_FILE="${MONITORING_DIR}/.env"

usage() {
    echo "Użycie: $0 kuma|netdata|dashboard"
    exit 1
}

[[ $# -eq 1 ]] || usage

MODE="$1"
case "${MODE}" in
    kuma|netdata|dashboard) ;;
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

if [[ ! -S /var/run/docker.sock ]]; then
    echo "BŁĄD: Docker nie działa na tym hoście (brak /var/run/docker.sock)."
    echo ""
    echo "Na oczyszczalnia-aio Docker trzeba zainstalować jednorazowo:"
    echo "  sudo apt update"
    echo "  sudo apt install -y docker.io"
    echo "  sudo systemctl enable --now docker"
    echo "  sudo usermod -aG docker \$USER"
    echo "  docker compose version   # jeśli brak — docker-compose-plugin LUB docker-compose-v2 (nie oba)"
    echo "  # wyloguj się i zaloguj ponownie, potem:"
    echo "  docker ps"
  echo "  ./scripts/monitoring-start.sh ${MODE}"
    echo ""
    echo "Szczegóły: docs/monitoring.md (sekcja „Instalacja Dockera”)"
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    if [[ -S /var/run/docker.sock ]] && ! groups | grep -q '\bdocker\b'; then
        echo "BŁĄD: Brak uprawnień do Dockera (grupa docker)."
        echo ""
        echo "  sudo usermod -aG docker \"\$USER\""
        echo "  # wyloguj się i zaloguj ponownie (lub: newgrp docker)"
        echo "  docker ps"
        exit 1
    fi
    echo "BŁĄD: Docker zainstalowany, ale daemon nie odpowiada lub brak uprawnień."
    echo "Spróbuj: sudo systemctl start docker"
    echo "Albo dodaj użytkownika do grupy docker: sudo usermod -aG docker \$USER (wymaga ponownego logowania)"
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
  echo "Panel Netdata: http://$(hostname):19999/v3"
elif [[ "${MODE}" == "dashboard" ]]; then
  echo "Panel metryk: http://$(hostname):${METRICS_DASHBOARD_PORT:-3080}/"
fi
