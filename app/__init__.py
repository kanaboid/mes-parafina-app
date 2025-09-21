# app/__init__.py

from flask import Flask
from .config import Config, ProdConfig, TestConfig
from .pathfinder_service import PathFinder
from .monitoring import MonitoringService
from .sensors import SensorService
import logging
import os
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from .extensions import db, socketio
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from logging.handlers import RotatingFileHandler
from flask_cors import CORS

# ... instancje pathfinder, monitoring, sensor_service, scheduler ...
pathfinder = PathFinder()
monitoring = MonitoringService()
sensor_service = SensorService()


# Globalne referencje do zadań schedulera
scheduler_jobs = {}

# logging.basicConfig()
# logging.getLogger('apscheduler').setLevel(logging.DEBUG)

def create_app(config_class=None):
    # --- KROK 1: WŁĄCZENIE SZCZEGÓŁOWEGO LOGOWANIA ---
    #logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # ----------------------------------------------------

    app = Flask(__name__)
    
    CORS(app, origins=[
        "https://react-production-91c7.up.railway.app",  # Twój frontend
        "http://localhost:5173",  # Development
        "http://localhost:3000",  # Alternatywny dev port
    ])


    # --- OSTATECZNA POPRAWKA: Dynamiczne ładowanie konfiguracji ---
    if config_class:
        app.config.from_object(config_class)
    else:
        env = os.environ.get('FLASK_ENV', 'development')
        if env == 'production':
            app.config.from_object(ProdConfig)
            print("--- Załadowano konfigurację produkcyjną (ProdConfig) ---")
        else:
            app.config.from_object(Config)
            print("--- Załadowano konfigurację deweloperską (Config) ---")
    # -----------------------------------------------------------------

    # --- OSTATECZNA POPRAWKA: Logowanie do pliku ---
    if not os.path.exists('instance'):
        os.makedirs('instance')
    file_handler = RotatingFileHandler('instance/app.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('--- Aplikacja MES Parafina startuje ---')

    # === FIX: Configure logging filters to reduce session error noise ===
    # Filter out "Invalid session" messages which are normal WebSocket behavior
    class InvalidSessionFilter(logging.Filter):
        def filter(self, record):
            # Filter out common invalid session messages
            if hasattr(record, 'msg') and 'Invalid session' in str(record.msg):
                return False
            return True

    # Apply filter to relevant loggers
    socketio_logger = logging.getLogger('socketio.server')
    socketio_logger.addFilter(InvalidSessionFilter())
    engineio_logger = logging.getLogger('engineio.server')
    engineio_logger.addFilter(InvalidSessionFilter())

    # Also filter at the root logger level for broader coverage
    root_logger = logging.getLogger()
    root_logger.addFilter(InvalidSessionFilter())

    # ----------------------------------------------------

    print(f"--- [PID: {os.getpid()}] START FABRYKI APLIKACJI (Debug: {app.debug}) ---")

    if app.config.get('ENVIRONMENT') == 'production':
        app.config['PREFERRED_URL_SCHEME'] = 'https'
    else:
        app.config['PREFERRED_URL_SCHEME'] = 'http'
        @app.after_request
        def add_security_headers(response):
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'
            return response
    
    # --- OSTATECZNA POPRAWKA: Konfiguracja SocketIO z Redis Manager ---
    # To jest kluczowy element dla komunikacji między Celery a Gunicornem
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    if "REDIS_URL" not in os.environ:
        try:
            import socket
            socket.gethostbyname('redis')
            REDIS_URL = 'redis://redis:6379/0'
        except socket.error:
            pass
    socketio.init_app(app, message_queue=REDIS_URL)
    # --------------------------------------------------------------------

    db.init_app(app)
    
    
    
    # Inicjalizacja serwisów
    pathfinder_service = PathFinder()
    sensor_service = SensorService()
    monitoring = MonitoringService()

    pathfinder_service.init_app(app)
    sensor_service.init_app(app)
    monitoring.init_app(app)
    
    # Rejestrujemy serwisy w extensions
    app.extensions['pathfinder'] = pathfinder_service
    app.extensions['sensor_service'] = sensor_service
    app.extensions['monitoring'] = monitoring
    
    print(f"DEBUG: Registered extensions: {list(app.extensions.keys())}")

    

    # Rejestrujemy blueprinty
    from . import routes
    from .cykle_api import cykle_bp
    from .topology_routes import topology_bp
    from .operations_routes import bp as operations_bp
    from .batch_routes import batch_bp
    from .sprzet_routes import sprzet_bp
    from .scheduler_routes import scheduler_bp
    app.register_blueprint(routes.bp)
    app.register_blueprint(cykle_bp)
    app.register_blueprint(topology_bp)
    app.register_blueprint(operations_bp)
    app.register_blueprint(batch_bp)
    app.register_blueprint(sprzet_bp)
    app.register_blueprint(scheduler_bp)
    @app.route('/hello')
    def hello():
        return "Witaj w aplikacji MES!"
    from . import sockets

    # === FIX: Configure logging to reduce "Invalid session" noise ===
    # These errors are normal when clients try to use HTTP session cookies with WebSocket
    logging.getLogger('socketio').setLevel(logging.WARNING)
    logging.getLogger('engineio').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.INFO)
    
    
    # Konfiguracja Flask-Admin
    
    
    admin = Admin(app, name='MES', template_mode='bootstrap4')
    from . import models
    admin.add_view(ModelView(models.Sprzet, db.session, name="Sprzęt", endpoint="sprzet_admin"))
    admin.add_view(ModelView(models.PartieSurowca, db.session, name="Partie (stare)"))
    admin.add_view(ModelView(models.Zawory, db.session))
    admin.add_view(ModelView(models.Segmenty, db.session))
    admin.add_view(ModelView(models.PortySprzetu, db.session, name="Porty Sprzętu"))
    
    # Dodajmy też widoki dla nowego systemu partii
    admin.add_view(ModelView(models.Batches, db.session, name="Partie Pierwotne (nowe)", endpoint="batches_admin"))
    admin.add_view(ModelView(models.TankMixes, db.session, name="Mieszaniny w Zbiornikach"))
    admin.add_view(ModelView(models.MixComponents, db.session, name="Składniki Mieszanin"))
    admin.add_view(ModelView(models.AuditTrail, db.session, name="Ślad Audytowy"))

    

    return app