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
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TESTING = False

class ProdConfig(Config):
    """Konfiguracja produkcyjna"""
    DEBUG = False
    TESTING = False
    ENVIRONMENT = 'production'

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