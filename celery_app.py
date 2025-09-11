# celery_app.py
from app import create_app
from celery import Celery
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'local_libs'))

print(f"--- [DEBUG] Dodano do sys.path: {os.path.join(os.path.dirname(__file__), 'local_libs')}")
print(f"--- [CELERY_APP DEBUG] SYS.PATH na starcie: {sys.path[0]}")

# Ustal adres URL brokera Redis na podstawie zmiennych środowiskowych
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
if "REDIS_URL" not in os.environ:
    try:
        import socket
        socket.gethostbyname('redis')
        REDIS_URL = 'redis://redis:6379/0'
    except socket.error:
        pass

# Utwórz instancję aplikacji Flask, aby mieć dostęp do jej konfiguracji
print("--- [CELERY_APP DEBUG] Przed wywołaniem create_app()...")
flask_app = create_app()
print("--- [CELERY_APP DEBUG] Po wywołaniu create_app(). Aplikacja stworzona.")

def make_celery(app):
    """
    Tworzy i konfiguruje instancję Celery, łącząc ją z aplikacją Flask.
    """
    celery = Celery(
        app.import_name,
        backend=REDIS_URL,
        broker=REDIS_URL
    )
    print(f"--- [CELERY_APP DEBUG] Konfiguracja z Flaska (app.config): {app.config.get('CELERY_BEAT_DBURI')}")
    celery.config_from_object('app.config.Config')

    # Sprawdźmy, co Celery ma po załadowaniu konfiguracji
    print(f"--- [CELERY_APP DEBUG] Konfiguracja w Celery (po config_from_object): {celery.conf.get('beat_scheduler_dburi')}")

    beat_db_uri = app.config.get('CELERY_BEAT_DBURI')
    print(f"--- [CELERY_APP DEBUG] Jawne ustawianie 'beat_dburi' na: {beat_db_uri}")
    celery.conf.update({
        'beat_dburi': beat_db_uri
    })

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    return celery

celery = make_celery(flask_app)

# Jawne zaimportowanie modułu z zadaniami
celery.autodiscover_tasks(['app.tasks'])

# --- USUNIĘTA SEKCJA ---
# Cała logika związana z SENSORS_INTERVAL, ALARMS_ENABLED
# i budowaniem słownika `beat_schedule` została usunięta.
# Teraz harmonogram będzie w całości w bazie danych.
# -----------------------