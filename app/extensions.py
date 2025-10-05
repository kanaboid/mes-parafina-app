# app/extensions.py

import os
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from sqlalchemy import event
from sqlalchemy.engine import Engine


db = SQLAlchemy()

@event.listens_for(Engine, "connect")
def set_utc_timezone(dbapi_connection, connection_record):
    """
    Wykonuje SET time_zone = '+00:00' dla każdego nowego połączenia.
    Zapewnia to, że sesja MySQL zawsze działa w UTC.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("SET time_zone = '+00:00'")
    cursor.close()

# WAŻNE: Inicjalizujemy SocketIO tylko jeśli nie jesteśmy w trybie migracji Alembic
# Dzięki temu Alembic może importować models bez błędów SocketIO
if not os.environ.get('ALEMBIC_MIGRATION_MODE'):
    redis_url = os.environ.get('REDIS_URL')

    socketio = SocketIO(
        async_mode='eventlet',
        cors_allowed_origins="*",
        #logger=True,
        #engineio_logger=True,
        message_queue=redis_url,
        ping_timeout=60,        # Zwiększone dla stabilności na Railway (było 20s)
        ping_interval=25,       # Zwiększone dla stabilności na Railway (było 10s)
        always_connect=True,    # Zawsze pozwalaj na połączenia
        manage_session=True     # Zarządzaj sesjami automatycznie
    )
else:
    # W trybie migracji Alembic tworzymy "mock" socketio
    socketio = None
    print("ℹ️  SocketIO pominięte - tryb migracji Alembic")