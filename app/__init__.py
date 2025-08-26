# app/__init__.py

from flask import Flask
from .config import Config
from .pathfinder_service import PathFinder
from .monitoring import MonitoringService
from .sensors import SensorService
from flask_apscheduler import APScheduler
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from .extensions import db, socketio
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
import logging


# ... instancje pathfinder, monitoring, sensor_service, scheduler ...
pathfinder = PathFinder()
monitoring = MonitoringService()
sensor_service = SensorService()
scheduler = APScheduler()

# logging.basicConfig()
# logging.getLogger('apscheduler').setLevel(logging.DEBUG)

def create_app(config_class=Config): # ZMIANA: Dodajemy opcjonalny argument
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    db.init_app(app)
    socketio.init_app(app)
    # Inicjalizacja serwisów
    if not app.config.get('TESTING'):
        pathfinder.init_app(app)
    
    monitoring.init_app(app)
    sensor_service.init_app(app)
    app.extensions = getattr(app, 'extensions', {})
    if not app.config.get('TESTING'):
        app.extensions['pathfinder'] = pathfinder
    app.extensions['sensor_service'] = sensor_service

    # Konfiguracja schedulera
    app.config.setdefault('SCHEDULER_API_ENABLED', True) # Użyj setdefault
    app.config.setdefault('SCHEDULER_TIMEZONE', "Europe/Warsaw")

    scheduler.init_app(app)
    # ZMIANA: Usuwamy ręczną konfigurację strefy czasowej, bo jest już w configu
    # scheduler.scheduler.configure(timezone="Europe/Warsaw")

    # ZMIANA: Cały blok dodawania zadań i uruchamiania schedulera
    # umieszczamy w warunku, który sprawdza, czy NIE jesteśmy w trybie testowym.
    if not app.config.get('TESTING'):
        @scheduler.task('interval',     
                       id='read_sensors', 
                       seconds=600,
                       max_instances=1,
                       next_run_time=datetime.now(timezone.utc))
        def read_sensors():
            with app.app_context():
                try:
                    sensor_service.read_sensors()
                except Exception as e:
                    print(f"Błąd podczas odczytu czujników: {str(e)}")

        @scheduler.task('interval', 
                       id='check_alarms', 
                       seconds=30,
                       max_instances=1)
        def check_alarms():
            with app.app_context():
                monitoring.check_equipment_status()

        @scheduler.task('interval', id='broadcast_dashboard', seconds=10, max_instances=1)
        def broadcast_dashboard_job():
            """
            Regularnie pobiera i wysyła aktualne dane do wszystkich dashboardów.
            """
            print(f"\n--- SCHEDULER: Uruchamiam zadanie broadcast_dashboard o {datetime.now()} ---\n")
            with app.app_context():
                from .sockets import broadcast_dashboard_update
                broadcast_dashboard_update()

        scheduler.start()

    # Rejestrujemy blueprinty
    from . import routes
    from .cykle_api import cykle_bp
    from .topology_routes import topology_bp
    from .operations_routes import bp as operations_bp
    from .batch_routes import batch_bp
    from .sprzet_routes import sprzet_bp
    app.register_blueprint(routes.bp)
    app.register_blueprint(cykle_bp)
    app.register_blueprint(topology_bp)
    app.register_blueprint(operations_bp)
    app.register_blueprint(batch_bp)
    app.register_blueprint(sprzet_bp)

    @app.route('/hello')
    def hello():
        return "Witaj w aplikacji MES!"
    from . import sockets
    
    
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