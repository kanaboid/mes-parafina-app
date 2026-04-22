#!/usr/bin/env bash
# migrate.sh
# Wersja z obsluga bazy produkcyjnej Railway

set -u

COMMAND="${1:-}"
MESSAGE="${2:-}"

cleanup_env() {
  unset ALEMBIC_TEST_MODE 2>/dev/null || true
  unset ALEMBIC_PROD_MODE 2>/dev/null || true
}

check_last_success() {
  local exit_code="$1"
  if [ "$exit_code" -ne 0 ]; then
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    echo "!!! BLAD: Poprzednia komenda zakonczyla sie niepowodzeniem. Przerwanie skryptu."
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    cleanup_env
    exit 1
  fi
}

confirm_continue() {
  local prompt="$1"
  echo "$prompt"
  read -r _
}

print_usage() {
  cat <<'EOF'
Uzycie:
  ./migrate.sh <komenda> [wiadomosc]

Dostepne komendy:
  generate
  upgrade
  downgrade
  history
  current
  stamp-test
  stamp-prod
  upgrade-prod
  downgrade-prod

Przyklad:
  ./migrate.sh generate "Dodanie nowej tabeli uzytkownikow"
EOF
}

case "$COMMAND" in
  generate)
    if [ -z "$MESSAGE" ]; then
      echo "BLAD: Komenda 'generate' wymaga podania komunikatu migracji."
      echo "Przyklad: ./migrate.sh generate 'Dodanie nowej tabeli uzytkownikow'"
      exit 1
    fi
    echo "--- Generowanie nowej migracji... ---"
    alembic revision --autogenerate -m "$MESSAGE"
    check_last_success "$?"
    ;;

  upgrade)
    echo "--- Aktualizacja bazy DEWELOPERSKIEJ do najnowszej wersji... ---"
    alembic upgrade head
    check_last_success "$?"

    echo ""
    echo "--- Aktualizacja bazy TESTOWEJ do najnowszej wersji... ---"
    ALEMBIC_TEST_MODE=true alembic upgrade head
    check_last_success "$?"

    echo ""
    echo "==================================================="
    echo "UWAGA: Baza PRODUKCYJNA (Railway) nie jest automatycznie aktualizowana!"
    echo "Aby zaktualizowac baze produkcyjna, uzyj komendy:"
    echo "  railway run ./migrate.sh upgrade-prod"
    echo "==================================================="
    ;;

  upgrade-prod)
    echo "--- UWAGA: Aktualizacja bazy PRODUKCYJNEJ na Railway! ---"
    echo "Upewnij sie, ze masz ustawiona zmienna DATABASE_URL_PROD."
    confirm_continue "Nacisnij Ctrl+C aby anulowac, lub Enter aby kontynuowac..."

    ALEMBIC_PROD_MODE=true alembic upgrade head
    check_last_success "$?"
    ;;

  downgrade)
    echo "--- Wycofanie ostatniej migracji z bazy DEWELOPERSKIEJ... ---"
    alembic downgrade -1
    check_last_success "$?"

    echo ""
    echo "--- Wycofanie ostatniej migracji z bazy TESTOWEJ... ---"
    ALEMBIC_TEST_MODE=true alembic downgrade -1
    check_last_success "$?"
    ;;

  downgrade-prod)
    echo "--- UWAGA: Wycofanie migracji z bazy PRODUKCYJNEJ na Railway! ---"
    echo "To jest NIEBEZPIECZNA operacja!"
    confirm_continue "Nacisnij Ctrl+C aby anulowac, lub Enter aby kontynuowac..."

    ALEMBIC_PROD_MODE=true alembic downgrade -1
    check_last_success "$?"
    ;;

  history)
    echo "--- Historia migracji... ---"
    alembic history
    check_last_success "$?"
    ;;

  current)
    echo "--- Aktualna wersja bazy deweloperskiej... ---"
    alembic current
    check_last_success "$?"

    echo ""
    echo "--- Aktualna wersja bazy testowej... ---"
    ALEMBIC_TEST_MODE=true alembic current
    check_last_success "$?"

    echo ""
    echo "--- Aktualna wersja bazy produkcyjnej (Railway)... ---"
    ALEMBIC_PROD_MODE=true alembic current
    check_last_success "$?"
    ;;

  stamp-test)
    echo "--- Stemplowanie bazy TESTOWEJ do najnowszej wersji (head)... ---"
    ALEMBIC_TEST_MODE=true alembic stamp head
    check_last_success "$?"
    ;;

  stamp-prod)
    echo "--- UWAGA: Stemplowanie bazy PRODUKCYJNEJ (Railway) do head! ---"
    confirm_continue "Nacisnij Ctrl+C aby anulowac, lub Enter aby kontynuowac..."

    ALEMBIC_PROD_MODE=true alembic stamp head
    check_last_success "$?"
    ;;

  *)
    echo "BLAD: Nieznana lub brakujaca komenda."
    print_usage
    exit 1
    ;;
esac

cleanup_env
echo ""
echo "--- Skrypt zakonczyl dzialanie ---"
