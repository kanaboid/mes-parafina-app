# Wybierz oficjalny obraz bazowy Python
FROM python:3.11-slim

# Instalacja uv - szybki menedżer pakietów Python
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Ustaw katalog roboczy w kontenerze
WORKDIR /app

# Skopiuj pliki konfiguracyjne projektu
COPY pyproject.toml uv.lock ./

# Instalacja zależności (bez venv w kontenerze - używamy systemowego Pythona)
# --frozen: używa dokładnych wersji z uv.lock (deterministyczne buildy)
# --no-dev: bez zależności deweloperskich (pytest itp.)
RUN uv sync --frozen --no-dev

# Skopiuj resztę kodu aplikacji do kontenera
COPY . .

ENV ENVIRONMENT=production
ENV FLASK_ENV=production
# Dodaj .venv/bin do PATH, aby używać zainstalowanych pakietów
ENV PATH="/app/.venv/bin:$PATH"

# Uruchom aplikację używając Gunicorna z opcją --preload
# --preload zapewnia, że scheduler jest inicjowany tylko raz w procesie master
# uv run automatycznie używa pakietów z .venv
CMD ["uv", "run", "gunicorn", "--worker-class", "eventlet", "-w", "1", "--bind", "0.0.0.0:5000", "--preload", "run:app"]