# app/extensions.py

import os
import time
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

# === CONNECTION POOL MONITORING ===
# TODO: Add proper event listeners for connection pool monitoring
# For now, monitoring will be done through the test script

redis_url = os.environ.get('REDIS_URL')

socketio = SocketIO(
    async_mode='eventlet',
    cors_allowed_origins="*",
    logger=False,                   # Disable SocketIO logging to reduce noise
    engineio_logger=False,          # Disable Engine.IO logging
    message_queue=redis_url,
    ping_timeout=20,
    ping_interval=10,
    # === FIX: Comprehensive session handling fix ===
    # Disable all session-related features to prevent "Invalid session" errors
    cookie=None,                    # Disable cookie-based sessions
    manage_session=False,           # Disable session management
    # Additional logging configuration
    # log_output=False,             # Uncomment to disable all SocketIO output
)