# app/__init__.py

from flask import Flask
from .config import Config
from .pathfinder_service import PathFinder
from .monitoring import MonitoringService  # Dodaj import
from .sensors import SensorService
from flask_apscheduler import APScheduler
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
# Tworzymy pustą instancję, która zostanie zainicjowana w create_app
pathfinder = PathFinder()
monitoring = MonitoringService()  # Dodaj instancję
sensor_service = SensorService()
scheduler = APScheduler()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Inicjalizacja serwisów
    pathfinder.init_app(app)
    monitoring.init_app(app)  # Dodaj inicjalizację
    sensor_service.init_app(app)
    app.extensions = getattr(app, 'extensions', {})
    app.extensions['pathfinder'] = pathfinder
    app.extensions['sensor_service'] = sensor_service
   # Konfiguracja schedulera
    app.config['SCHEDULER_API_ENABLED'] = True
    app.config['SCHEDULER_TIMEZONE'] = "Europe/Warsaw"
    
    scheduler.init_app(app)
    scheduler.scheduler.configure(timezone="Europe/Warsaw")

    @scheduler.task('interval', 
                   id='read_sensors', 
                   seconds=60,
                   max_instances=1,
                   next_run_time=datetime.now())
    def read_sensors():
        """Odczyt z czujników co dokładnie 60 sekund"""
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Zaplanowane uruchomienie odczytu czujników")
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
        """Sprawdzanie alarmów co 5 minut"""
        with app.app_context():
            monitoring.check_equipment_status()

    scheduler.start()

    # Rejestrujemy blueprinty
    from . import routes
    from .cykle_api import cykle_bp
    from .topology_routes import topology_bp  # Dodaj import topology blueprint
    app.register_blueprint(routes.bp)
    app.register_blueprint(cykle_bp)
    app.register_blueprint(topology_bp)  # Zarejestruj topology blueprint

    @app.route('/hello')
    def hello():
        return "Witaj w aplikacji MES!"

    return app