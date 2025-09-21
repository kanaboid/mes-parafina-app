# app/config.py

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Konfiguracja produkcyjna / deweloperska"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'trudne-do-zgadniecia-haslo'
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() in ('true', '1', 't')

    # Dane do połączenia z bazą danych MySQL
    MYSQL_HOST = os.environ.get('MYSQLHOST', 'localhost')
    MYSQL_USER = os.environ.get('MYSQLUSER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_ROOT_PASSWORD', '')
    MYSQL_DB = 'mes_parafina_db'
    ENVIRONMENT = os.environ.get('ENVIRONMENT', 'development')
    PREFERRED_URL_SCHEME = 'https' if ENVIRONMENT == 'production' else 'http'
    print(f"ENVIRONMENT: {ENVIRONMENT}")
    print(f"PREFERRED_URL_SCHEME: {PREFERRED_URL_SCHEME}")
    # URI dla bazy deweloperskiej/produkcyjnej
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+mysqlconnector://{MYSQL_USER}:{MYSQL_PASSWORD}@"
        f"{MYSQL_HOST}/{MYSQL_DB}"
        "?charset=utf8mb4"
    )
    print(f"--- [CONFIG DEBUG] Zbudowano SQLALCHEMY_DATABASE_URI: {SQLALCHEMY_DATABASE_URI}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TESTING = False

    # === CONNECTION POOL CONFIGURATION ===
    SQLALCHEMY_ENGINE_OPTIONS = {
        # Liczba połączeń w puli (dla Twojej aplikacji 5-10 jest wystarczające)
        'pool_size': 5,

        # Maksymalna liczba dodatkowych połączeń poza pulą
        'max_overflow': 10,

        # Jak często odnawiać połączenia (w sekundach)
        'pool_recycle': 3600,  # 1 godzina

        # Sprawdzenie czy połączenie jest żywe przed użyciem
        'pool_pre_ping': True,

        # Wyłącz echo w produkcji (logowanie zapytań)
        'echo': False
    }

    # Timeout dla pozyskania połączenia z puli
    SQLALCHEMY_POOL_TIMEOUT = 30

    # Reset połączenia po zwróceniu do puli
    SQLALCHEMY_POOL_RESET_ON_RETURN = 'commit'

    CELERY_BEAT_DBURI = SQLALCHEMY_DATABASE_URI
    print(f"--- [CONFIG DEBUG] Ustawiono CELERY_BEAT_DBURI na: {CELERY_BEAT_DBURI}")


class ProdConfig(Config):
    """Konfiguracja produkcyjna"""
    DEBUG = False
    TESTING = False
    ENVIRONMENT = 'production'

    # === PRODUCTION CONNECTION POOL ===
    # W produkcji zwiększamy pulę dla lepszej wydajności
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,        # Większa pula dla produkcji
        'max_overflow': 20,      # Więcej połączeń dodatkowych
        'pool_recycle': 3600,   # Odnawianie co godzinę
        'pool_pre_ping': True,  # Sprawdzenie żywotności
        'echo': False           # Brak logowania zapytań
    }

    SQLALCHEMY_POOL_TIMEOUT = 20  # Krótszy timeout w produkcji

class TestConfig(Config):
    TESTING = True
    # Nadpisujemy wszystko, bez polegania na dziedziczeniu
    MYSQL_HOST = os.environ.get('MYSQLHOST', 'localhost')
    MYSQL_USER = os.environ.get('MYSQLUSER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_ROOT_PASSWORD', '')
    MYSQL_DB = 'mes_parafina_db_test' # Jedyna prawdziwa zmiana

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+mysqlconnector://{MYSQL_USER}:{MYSQL_PASSWORD}@"
        f"{MYSQL_HOST}/{MYSQL_DB}"
        "?charset=utf8mb4"
    )

class DevConfigForTesting(Config):
    """
    Specjalna konfiguracja do testów, które muszą być uruchomione
    na deweloperskiej bazie danych (z pełnymi danymi).
    """
    TESTING = True