# app/extensions.py

import os
import socket
import errno
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from sqlalchemy import event
from sqlalchemy.engine import Engine


db = SQLAlchemy()

# --- WORKAROUND dla "Bad file descriptor" w eventlet ---
# Patch socket.socket.shutdown aby ignorować EBADF podczas zamykania
_original_socket_shutdown = socket.socket.shutdown

def _patched_socket_shutdown(self, how):
    """Graceful socket shutdown - ignoruje błąd 'Bad file descriptor'"""
    try:
        return _original_socket_shutdown(self, how)
    except OSError as e:
        # Ignoruj tylko EBADF (Bad file descriptor) - socket już zamknięty
        if e.errno != errno.EBADF:
            raise
        # Socket już zamknięty, to nie jest prawdziwy błąd

socket.socket.shutdown = _patched_socket_shutdown
# ---------------------------------------------------------------

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

# Dodatkowy patch dla eventlet WebSocket - ignoruje EBADF podczas zamykania WS
import eventlet.wsgi
_original_close = eventlet.wsgi.WebSocket.close if hasattr(eventlet.wsgi, 'WebSocket') else None

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