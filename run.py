# run.py
import eventlet
eventlet.monkey_patch()

# Stłumienie warnings dla engineio socket errors (głównie EBADF)
import warnings
warnings.filterwarnings('ignore', message='socket shutdown error')

# --- WORKAROUND dla "Bad file descriptor" w eventlet ---
# Patch dla eventlet.green.socket aby ignorować EBADF podczas zamykania
import errno
try:
    from eventlet.green import socket as green_socket
    _original_shutdown = green_socket.socket.shutdown
    
    def _patched_shutdown(self, how):
        """Graceful socket shutdown - ignoruje błąd 'Bad file descriptor'"""
        try:
            return _original_shutdown(self, how)
        except OSError as e:
            # Ignoruj tylko EBADF (Bad file descriptor) - socket już zamknięty
            if e.errno not in (errno.EBADF, errno.ENOTCONN):
                raise
            # Socket już zamknięty lub nie połączony, to nie jest prawdziwy błąd
    
    green_socket.socket.shutdown = _patched_shutdown
except (ImportError, AttributeError):
    # Jeśli nie ma eventlet lub struktura inna - nie patch
    pass
# ---------------------------------------------------------------

from app import create_app, socketio

app = create_app()

if __name__ == '__main__':
    #app.run( debug=True, port=5000, host='0.0.0.0' )
    socketio.run(app, debug=True, port=5000, host='0.0.0.0')
