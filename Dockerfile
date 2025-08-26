# Wybierz oficjalny obraz bazowy Python
FROM python:3.11-slim

# Ustaw katalog roboczy w kontenerze
WORKDIR /app

# Skopiuj plik z zależnościami i zainstaluj je
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Skopiuj resztę kodu aplikacji do kontenera
COPY . .

ENV ENVIRONMENT=production
ENV FLASK_ENV=production

# Uruchom aplikację używając Gunicorna
# Załóżmy, że plik startowy to "run.py", a obiekt aplikacji to "app"
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "--bind", "0.0.0.0:5000", "run:app"]