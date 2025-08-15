# app/extensions.py

import os
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO

db = SQLAlchemy()

redis_url = os.environ.get('REDIS_URL')

socketio = SocketIO(
    async_mode='eventlet',
    cors_allowed_origins="*",
    logger=True,
    engineio_logger=True,
    message_queue=redis_url
)