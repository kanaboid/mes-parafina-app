# mes-parafina-app
Aplikacja MES do zarządzania produkcją parafiny

## 🚀 Instalacja i uruchomienie

### Wymagania
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) - szybki menedżer pakietów Python

### Instalacja uv
```powershell
# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Instalacja zależności
```bash
# Synchronizacja środowiska z uv.lock
uv sync

# Lub instalacja z automatyczną aktualizacją
uv sync --upgrade
```

### Uruchomienie aplikacji

#### Lokalnie (dewelopersko)
```bash
# Uruchomienie Flask app
uv run python run.py

# Lub z gunicorn
uv run gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 --reload "run:app"
```

#### Docker (produkcyjnie)
```bash
# Budowanie i uruchomienie
docker-compose up --build

# W tle
docker-compose up -d
```

### Migracje bazy danych

Używamy skryptu `migrate.ps1` (działa z uv automatycznie):

```powershell
# Generowanie nowej migracji
.\migrate.ps1 generate "Opis zmian"

# Aktualizacja do najnowszej wersji
.\migrate.ps1 upgrade

# Sprawdzenie aktualnej wersji
.\migrate.ps1 current

# Historia migracji
.\migrate.ps1 history
```

### Zarządzanie zależnościami

```bash
# Dodanie nowej zależności
uv add nazwa-pakietu

# Dodanie zależności deweloperskiej
uv add --dev pytest

# Usunięcie zależności
uv remove nazwa-pakietu

# Aktualizacja wszystkich zależności
uv sync --upgrade
```

## 📦 Struktura projektu

- `pyproject.toml` - konfiguracja projektu i zależności
- `uv.lock` - lockfile z dokładnymi wersjami pakietów
- `Dockerfile` - konfiguracja kontenera (używa uv)
- `docker-compose.yml` - orchestracja kontenerów
- `migrate.ps1` - skrypt do zarządzania migracjami Alembic

## 🔄 Migracja z pip

Projekt używa obecnie **uv** zamiast pip. Pliki `requirements.in` i `requirements.txt` są zachowane dla kompatybilności, ale nie są używane.

Jeśli potrzebujesz wygenerować `requirements.txt`:
```bash
uv pip compile pyproject.toml -o requirements.txt
```