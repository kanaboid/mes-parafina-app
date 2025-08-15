# app/sockets.py

from app import socketio
from flask_socketio import emit

@socketio.on('connect')
def handle_connect():
    """Wykonywane, gdy klient (przeglądarka) nawiązuje połączenie."""
    print('Klient połączony!')
    # Wyślij wiadomość powitalną tylko do tego jednego klienta
    emit('response', {'data': 'Połączono z serwerem. Witaj w konsoli administracyjnej!'})

@socketio.on('message_from_client')
def handle_message(json):
    """Odbiera wiadomości od klienta."""
    print('Otrzymano wiadomość: ' + str(json))
    # Odsyłamy prostą odpowiedź "echo"
    emit('response', {'data': f"Serwer otrzymał Twoją wiadomość: {json.get('data')}"})