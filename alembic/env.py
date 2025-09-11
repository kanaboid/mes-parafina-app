# alembic/env.py

# --- KROK 1: Konfiguracja ścieżek i podstawowe importy ---
import sys
from os.path import abspath, dirname, realpath, join
# Dodajemy główny folder projektu do ścieżki Pythona. Robimy to tylko raz.
sys.path.insert(0, dirname(dirname(abspath(__file__))))

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os

# --- KROK 2: Import metadanych z obu źródeł ---
# Importujemy obiekt `db` z Twojej aplikacji, aby uzyskać dostęp do Twoich modeli
from app.extensions import db  # Zakładam, że db jest w extensions.py, jeśli nie, zmień ścieżkę
# Importujemy `ModelBase` z biblioteki schedulera, zgodnie z tym, co odkryliśmy
from celery_sqlalchemy_scheduler.session import ModelBase as SchedulerModelBase

# --- KROK 3: Konfiguracja Alembic i logiki URI ---
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Logika wyboru URI - jest dobra, zostawiamy ją
DB_USER = os.environ.get('MYSQLUSER', 'root')
DB_PASSWORD = os.environ.get('MYSQL_ROOT_PASSWORD', '')
DB_HOST = os.environ.get('MYSQLHOST', 'localhost')

if os.environ.get('ALEMBIC_TEST_MODE') == 'true':
    database_uri = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/mes_parafina_db_test"
else:
    database_uri = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/mes_parafina_db"

config.set_main_option('sqlalchemy.url', database_uri)

# --- KROK 4: Zdefiniowanie celu dla Alembic ---
# To jest najważniejsza część. Tworzymy listę obiektów MetaData.
# Alembic musi wiedzieć o WSZYSTKICH modelach, aby działać poprawnie.
# Import `from app import models` zapewnia, że SQLAlchemy "widzi" Twoje tabele.
from app import models
target_metadata = [
    db.metadata,                   # Metadane z Twojej aplikacji
    SchedulerModelBase.metadata    # Metadane z biblioteki Celery
]

# --- KROK 5: Funkcje uruchomieniowe (bez zmian) ---
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