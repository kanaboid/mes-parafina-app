# run.py
import eventlet
eventlet.monkey_patch()

# Stłumienie warnings dla engineio socket errors (głównie EBADF)
import warnings
warnings.filterwarnings('ignore', message='socket shutdown error')

from app import create_app, socketio

app = create_app()

if __name__ == '__main__':
    #app.run( debug=True, port=5000, host='0.0.0.0' )
    socketio.run(app, debug=True, port=5000, host='0.0.0.0')
