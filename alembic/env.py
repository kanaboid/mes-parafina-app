# alembic/env.py

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Dodaj ścieżkę do swojego projektu, aby importy zadziałały
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))

# Zaimportuj tylko obiekt `db` z __init__, aby dostać się do metadanych
from app import db
# UWAGA: Celowo NIE importujemy klas Config i TestConfig

config = context.config

# --- BEZPOŚREDNIA I JAWNA LOGIKA WYBORU URI ---

# Pobieramy potrzebne zmienne środowiskowe, tak jak robi to Config
DB_USER = os.environ.get('MYSQLUSER', 'root')
DB_PASSWORD = os.environ.get('MYSQL_ROOT_PASSWORD', '')
DB_HOST = os.environ.get('MYSQLHOST', 'localhost')



if os.environ.get('ALEMBIC_TEST_MODE') == 'true':
    #print("--- Running Alembic in TEST mode (via environment variable) ---")
    database_uri = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/mes_parafina_db_test"
else:
    #print("--- Running Alembic in DEV mode ---")
    database_uri = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/mes_parafina_db"

# Ustawiamy URI i drukujemy go, aby mieć 100% pewności
config.set_main_option('sqlalchemy.url', database_uri)
#print(f"--- Alembic will connect to: {database_uri} ---")

# --- KONIEC LOGIKI ---

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Wskaż Alembicowi, które metadane ma śledzić
# Aby to zadziałało, musimy zaimportować WSZYSTKIE modele
from app import models
target_metadata = db.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()