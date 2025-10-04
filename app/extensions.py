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

redis_url = os.environ.get('REDIS_URL')

socketio = SocketIO(
    async_mode='eventlet',
    cors_allowed_origins="*",
    #logger=True,
    #engineio_logger=True,
    message_queue=redis_url,
    ping_timeout=20,
    ping_interval=10

)