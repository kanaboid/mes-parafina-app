# app/config.py

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Konfiguracja produkcyjna / deweloperska"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'trudne-do-zgadniecia-haslo'

    # Dane do połączenia z bazą danych MySQL
    MYSQL_HOST = os.environ.get('MYSQLHOST', 'localhost')
    MYSQL_USER = os.environ.get('MYSQLUSER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_ROOT_PASSWORD', '')
    MYSQL_DB = 'mes_parafina_db'

    # URI dla bazy deweloperskiej/produkcyjnej
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+mysqlconnector://{MYSQL_USER}:{MYSQL_PASSWORD}@"
        f"{MYSQL_HOST}/{MYSQL_DB}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TESTING = False

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
    )

class DevConfigForTesting(Config):
    """
    Specjalna konfiguracja do testów, które muszą być uruchomione
    na deweloperskiej bazie danych (z pełnymi danymi).
    """
    TESTING = True