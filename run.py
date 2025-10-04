# run.py
import sys
import os
# Dodaj local_libs do ścieżki dla lokalnych, zmodyfikowanych pakietów
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'local_libs'))

import eventlet
eventlet.monkey_patch()

from app import create_app, socketio

app = create_app()

if __name__ == '__main__':
    #app.run( debug=True, port=5000, host='0.0.0.0' )
    socketio.run(app, debug=True, port=5000, host='0.0.0.0')
