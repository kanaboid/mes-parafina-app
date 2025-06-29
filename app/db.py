# app/db.py

import mysql.connector
from flask import current_app

def get_db_connection(config=None):
    """Tworzy i zwraca nowe połączenie z bazą danych na podstawie podanej konfiguracji lub z current_app."""
    if config is None:
        config = current_app.config
    connection = mysql.connector.connect(
        host=config['MYSQL_HOST'],
        user=config['MYSQL_USER'],
        password=config['MYSQL_PASSWORD'],
        database=config['MYSQL_DB']
    )
    return connection