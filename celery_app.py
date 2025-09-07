from app import create_app
from celery import Celery
from celery.schedules import crontab
import os

# Ustal adres URL brokera Redis na podstawie zmiennych środowiskowych
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
if "REDIS_URL" not in os.environ:
    # Docker-compose ustawia hostname 'redis', a my chcemy go użyć, jeśli jest dostępny.
    # To jest mały "hack", aby dynamicznie przełączać się między localhost a dockerem.
    try:
        import socket
        socket.gethostbyname('redis')
        REDIS_URL = 'redis://redis:6379/0'
    except socket.error:
        pass # Pozostajemy przy localhost

# Utwórz instancję aplikacji Flask, aby mieć dostęp do jej konfiguracji
flask_app = create_app()

def make_celery(app):
    """
    Tworzy i konfiguruje instancję Celery, łącząc ją z aplikacją Flask.
    """
    # Użyj Redisa jako brokera wiadomości i backendu wyników
    celery = Celery(
        app.import_name,
        backend=REDIS_URL,
        broker=REDIS_URL
    )
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery

celery = make_celery(flask_app)

# --- OSTATECZNA POPRAWKA: Jawne zaimportowanie modułu z zadaniami ---
celery.autodiscover_tasks(['app.tasks'])
# --------------------------------------------------------------------

# Tutaj zdefiniujemy zadania cykliczne używając Celery Beat
# Interwały można kontrolować przez zmienne środowiskowe

# Pobierz interwały z zmiennych środowiskowych (domyślnie: 10s i 5s)
SENSORS_INTERVAL = float(os.environ.get('SENSORS_INTERVAL', '10.0'))
ALARMS_INTERVAL = float(os.environ.get('ALARMS_INTERVAL', '5.0'))

# Sprawdź czy zadania są włączone (domyślnie: włączone)
SENSORS_ENABLED = os.environ.get('SENSORS_ENABLED', 'true').lower() == 'true'
ALARMS_ENABLED = os.environ.get('ALARMS_ENABLED', 'true').lower() == 'true'

print(f"DEBUG: SENSORS_INTERVAL={SENSORS_INTERVAL}s, SENSORS_ENABLED={SENSORS_ENABLED}")
print(f"DEBUG: ALARMS_INTERVAL={ALARMS_INTERVAL}s, ALARMS_ENABLED={ALARMS_ENABLED}")

# Buduj harmonogram na podstawie zmiennych środowiskowych
beat_schedule = {}

if SENSORS_ENABLED:
    beat_schedule['read-sensors-periodic'] = {
        'task': 'app.tasks.read_sensors_task',
        'schedule': SENSORS_INTERVAL,
    }

if ALARMS_ENABLED:
    beat_schedule['check-alarms-periodic'] = {
        'task': 'app.tasks.check_alarms_task',
        'schedule': ALARMS_INTERVAL,
    }

celery.conf.beat_schedule = beat_schedule
print(f"DEBUG: beat_schedule={beat_schedule}")
