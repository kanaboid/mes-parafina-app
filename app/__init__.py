# app/__init__.py

from flask import Flask
from .config import Config
from .pathfinder_service import PathFinder
from .monitoring import MonitoringService
from .sensors import SensorService
from flask_apscheduler import APScheduler
import logging
import os
import atexit
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from .extensions import db, socketio
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from logging.handlers import RotatingFileHandler


# ... instancje pathfinder, monitoring, sensor_service, scheduler ...
pathfinder = PathFinder()
monitoring = MonitoringService()
sensor_service = SensorService()
scheduler = APScheduler()

# Globalne referencje do zadań schedulera
scheduler_jobs = {}

# logging.basicConfig()
# logging.getLogger('apscheduler').setLevel(logging.DEBUG)

def create_app(config_class=None):
    # --- KROK 1: WŁĄCZENIE SZCZEGÓŁOWEGO LOGOWANIA ---
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logging.getLogger('apscheduler').setLevel(logging.DEBUG)
    # ----------------------------------------------------

    app = Flask(__name__)
    if config_class:
        app.config.from_object(config_class)
    else:
        # Domyślna konfiguracja, jeśli żadna nie zostanie przekazana
        app.config.from_object(Config)

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

    # Funkcje do tworzenia zadań schedulera (muszą być dostępne dla API)
    def create_read_sensors_job(seconds=30):
        # Usuń istniejące zadanie o tym samym ID, jeśli istnieje
        existing_job = scheduler.get_job('read_sensors')
        if existing_job:
            scheduler.remove_job('read_sensors')
            print(f"🔄 Usunięto istniejące zadanie read_sensors przed utworzeniem nowego z interwałem {seconds}s")
        
        @scheduler.task('interval',     
                       id='read_sensors', 
                       seconds=seconds,
                       max_instances=1,
                       next_run_time=datetime.now(timezone.utc))
        def read_sensors():
            current_time = datetime.now()
            print(f"\n--- SCHEDULER [read_sensors-{seconds}s] Uruchamiam zadanie o {current_time} ---")
            with app.app_context():
                try:
                    sensor_service.read_sensors()
                except Exception as e:
                    print(f"Błąd podczas odczytu czujników: {str(e)}")
        
        # Zapisz referencję do zadania
        scheduler_jobs['read_sensors'] = read_sensors
        print(f"✅ Utworzono nowe zadanie read_sensors z interwałem {seconds}s")
        return read_sensors

    def create_check_alarms_job(seconds=5):
        # Usuń istniejące zadanie o tym samym ID, jeśli istnieje
        existing_job = scheduler.get_job('check_alarms')
        if existing_job:
            scheduler.remove_job('check_alarms')
            print(f"🔄 [PID: {os.getpid()}] Usunięto istniejące zadanie check_alarms przed utworzeniem nowego z interwałem {seconds}s")
        
        @scheduler.task('interval', 
                       id='check_alarms', 
                       seconds=seconds,
                       max_instances=1)
        def check_alarms():
            current_time = datetime.now()
            print(f"\n--- [PID: {os.getpid()}] SCHEDULER [check_alarms-{seconds}s] Uruchamiam zadanie o {current_time} ---")
            with app.app_context():
                monitoring.check_equipment_status()
                from .sockets import broadcast_dashboard_update
                broadcast_dashboard_update()
        
        # Zapisz referencję do zadania
        scheduler_jobs['check_alarms'] = check_alarms
        print(f"✅ [PID: {os.getpid()}] Utworzono nowe zadanie check_alarms z interwałem {seconds}s")
        return check_alarms

    def cleanup_existing_jobs():
        """Usuwa wszystkie istniejące zadania schedulera przed inicjalizacją"""
        existing_jobs = scheduler.get_jobs()
        if existing_jobs:
            print(f"🧹 Znaleziono {len(existing_jobs)} istniejących zadań - usuwam...")
            for job in existing_jobs:
                scheduler.remove_job(job.id)
                print(f"🗑️ Usunięto zadanie: {job.id}")
        else:
            print("✨ Brak istniejących zadań do usunięcia")

    def get_job_real_status(job_id):
        """Sprawdza rzeczywisty status zadania - czy jest aktywne czy nie"""
        job = scheduler.get_job(job_id)
        if not job:
            return False, "Zadanie nie istnieje"
        
        # Sprawdź czy zadanie ma następny czas uruchomienia
        is_active = job.next_run_time is not None
        status_text = "AKTYWNE" if is_active else "WYŁĄCZONE"
        
        return is_active, status_text

    # ZMIANA: Cały blok dodawania zadań i uruchamiania schedulera
    if not app.config.get('TESTING'):
        # OSTATECZNE ROZWIĄZANIE: Mechanizm blokady plikowej (file lock)
        # Gwarantuje, że tylko jeden proces (nawet przy reloaderze lub wielu workerach Gunicorna) uruchomi scheduler.
        
        # Utwórz folder 'instance', jeśli nie istnieje
        try:
            os.makedirs(app.instance_path, exist_ok=True)
        except OSError as e:
            app.logger.error(f"Błąd podczas tworzenia folderu instance: {e}")

        lock_file_path = os.path.join(app.instance_path, 'scheduler.lock')
        
        try:
            # O_CREAT | O_EXCL to operacja atomowa - zapobiega race conditions.
            lock_fd = os.open(lock_file_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(lock_fd)
            
            print(f"🔒 [PID: {os.getpid()}] Zdobyto blokadę. Ten proces będzie zarządzał schedulerem.")
            
            def cleanup_lock_file():
                """Funkcja do usunięcia pliku blokady przy zamknięciu aplikacji."""
                try:
                    if os.path.exists(lock_file_path):
                        os.remove(lock_file_path)
                        print(f"🧹 [PID: {os.getpid()}] Usunięto plik blokady schedulera.")
                except OSError as e:
                    print(f"Błąd podczas usuwania pliku blokady: {e}")
            
            atexit.register(cleanup_lock_file)

            # Uruchomienie logiki schedulera
            print(f"🚀 [PID: {os.getpid()}] Uruchamiam scheduler...")
            cleanup_existing_jobs()
            create_read_sensors_job(5)
            create_check_alarms_job(5)
            
            if not scheduler.running:
                scheduler.start()
                print(f"✅ [PID: {os.getpid()}] Scheduler został uruchomiony.")

        except FileExistsError:
            print(f"ℹ️ [PID: {os.getpid()}] Blokada schedulera jest już aktywna w innym procesie. Ten proces pomija uruchomienie schedulera.")

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

    # Endpointy do zarządzania schedulerami
    @app.route('/api/scheduler/status', methods=['GET'])
    def get_scheduler_status():
        """Zwraca status wszystkich zadań w schedulerze"""
        print(f"--- [PID: {os.getpid()}] Zapytanie API: /api/scheduler/status ---")
        if app.config.get('TESTING'):
            return {'error': 'Scheduler niedostępny w trybie testowym'}, 400
            
        jobs = []
        for job in scheduler.get_jobs():
            # Użyj nowej funkcji do sprawdzenia rzeczywistego statusu
            is_active, status_text = get_job_real_status(job.id)
            
            jobs.append({
                'id': job.id,
                'name': job.name,
                'func': job.func.__name__ if hasattr(job.func, '__name__') else str(job.func),
                'trigger': str(job.trigger),
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'active': is_active,
                'status_text': status_text
            })
        
        return {
            'jobs': jobs, 
            'scheduler_state': scheduler.state,
            'scheduler_state_text': {0: 'STOPPED', 1: 'RUNNING', 2: 'PAUSED'}.get(scheduler.state, 'UNKNOWN'),
            'total_jobs': len(jobs),
            'active_jobs': len([j for j in jobs if j['active']]),
            'api_pid': os.getpid()
        }

    @app.route('/api/scheduler/job/<job_id>/toggle', methods=['POST'])
    def toggle_scheduler_job(job_id):
        """Włącza/wyłącza konkretne zadanie w schedulerze"""
        print(f"--- [PID: {os.getpid()}] Zapytanie API: /api/scheduler/job/{job_id}/toggle ---")
        if app.config.get('TESTING'):
            return {'error': 'Scheduler niedostępny w trybie testowym'}, 400
            
        try:
            job = scheduler.get_job(job_id)
            if not job:
                return {'error': f'Zadanie {job_id} nie istnieje'}, 404
                
            if job.next_run_time is None:
                # Włącz zadanie - utwórz nowe z domyślnym interwałem
                if job_id == 'read_sensors':
                    create_read_sensors_job(5)  # Domyślnie 5 sekund
                elif job_id == 'check_alarms':
                    create_check_alarms_job(5)  # Domyślnie 5 sekund
                else:
                    return {'error': f'Nieznane zadanie: {job_id}'}, 400
                return {'message': f'Zadanie {job_id} zostało włączone', 'status': 'active'}
            else:
                # Wyłącz zadanie - usuń je całkowicie
                scheduler.remove_job(job_id)
                return {'message': f'Zadanie {job_id} zostało wyłączone', 'status': 'paused'}
        except Exception as e:
            print(f"Błąd w [PID: {os.getpid()}] podczas przełączania zadania: {str(e)}")
            return {'error': f'Błąd podczas przełączania zadania: {str(e)}'}, 500

    @app.route('/api/scheduler/job/<job_id>/interval', methods=['POST'])
    def change_job_interval(job_id):
        """Zmienia interwał dla konkretnego zadania"""
        print(f"--- [PID: {os.getpid()}] Zapytanie API: /api/scheduler/job/{job_id}/interval ---")
        if app.config.get('TESTING'):
            return {'error': 'Scheduler niedostępny w trybie testowym'}, 400
            
        try:
            from flask import request
            data = request.get_json()
            new_seconds = data.get('seconds')
            
            if not new_seconds or new_seconds not in [1, 5, 10, 30, 60, 600]:
                return {'error': 'Nieprawidłowy interwał. Dozwolone wartości: 1, 5, 10, 30, 60, 600 sekund'}, 400
                
            # Usuń stare zadanie
            scheduler.remove_job(job_id)
            
            # Utwórz nowe zadanie z nowym interwałem
            if job_id == 'read_sensors':
                create_read_sensors_job(new_seconds)
            elif job_id == 'check_alarms':
                create_check_alarms_job(new_seconds)
            
            return {'message': f'Interwał dla zadania {job_id} został zmieniony na {new_seconds} sekund'}
        except Exception as e:
            print(f"Błąd w [PID: {os.getpid()}] podczas zmiany interwału: {str(e)}")
            return {'error': f'Błąd podczas zmiany interwału: {str(e)}'}, 500

    @app.route('/api/scheduler/start', methods=['POST'])
    def start_scheduler():
        """Uruchamia lub wznawia scheduler"""
        print(f"--- [PID: {os.getpid()}] Zapytanie API: /api/scheduler/start ---")
        if app.config.get('TESTING'):
            return {'error': 'Scheduler niedostępny w trybie testowym'}, 400
            
        try:
            if scheduler.state == 2:  # STATE_PAUSED
                scheduler.resume()
                print(f"--- [PID: {os.getpid()}] Scheduler został wznowiony (RESUMED). ---")
                return {'message': 'Scheduler został wznowiony', 'status': 'running'}
            elif scheduler.state == 1:  # STATE_RUNNING
                return {'message': 'Scheduler już działa', 'status': 'running'}
            elif scheduler.state == 0: # STATE_STOPPED
                return {'message': 'Scheduler został trwale zatrzymany (shutdown). Użyj Reset, aby go zrestartować.', 'status': 'stopped'}
            else:
                return {'message': f'Scheduler w nieznanym stanie: {scheduler.state}', 'status': 'unknown'}
        except Exception as e:
            print(f"Błąd w [PID: {os.getpid()}] podczas wznawiania schedulera: {str(e)}")
            return {'error': f'Błąd podczas wznawiania schedulera: {str(e)}'}, 500

    @app.route('/api/scheduler/stop', methods=['POST'])
    def stop_scheduler():
        """Zatrzymuje (pauzuje) scheduler"""
        print(f"--- [PID: {os.getpid()}] Zapytanie API: /api/scheduler/stop ---")
        if app.config.get('TESTING'):
            return {'error': 'Scheduler niedostępny w trybie testowym'}, 400
        try:
            if scheduler.state == 1:  # STATE_RUNNING
                scheduler.pause()
                print(f"--- [PID: {os.getpid()}] Scheduler został wstrzymany (PAUSED). ---")
                return {'message': 'Scheduler został wstrzymany', 'status': 'paused'}
            else:
                # Obejmuje stany PAUSED i STOPPED
                return {'message': 'Scheduler nie jest w stanie uruchomienia', 'status': 'paused'}
        except Exception as e:
            print(f"Błąd w [PID: {os.getpid()}] podczas pauzowania schedulera: {str(e)}")
            return {'error': f'Błąd podczas pauzowania schedulera: {str(e)}'}, 500

    @app.route('/api/scheduler/reset', methods=['POST'])
    def reset_scheduler():
        """Resetuje scheduler - usuwa wszystkie zadania i tworzy nowe z domyślnymi ustawieniami"""
        print(f"--- [PID: {os.getpid()}] Zapytanie API: /api/scheduler/reset ---")
        if app.config.get('TESTING'):
            return {'error': 'Scheduler niedostępny w trybie testowym'}, 400
        try:
            # Miękki reset: usuń wszystkie zadania, ale nie zatrzymuj samego schedulera
            scheduler.remove_all_jobs()
            print(f"--- [PID: {os.getpid()}] Wszystkie zadania usunięte w ramach resetu. ---")

            # Utwórz nowe zadania z domyślnymi ustawieniami
            create_read_sensors_job(5)
            create_check_alarms_job(5)
            
            # Jeśli scheduler był wstrzymany, wznow go, aby nowe zadanie mogło działać.
            if scheduler.state == 2: # PAUSED
                scheduler.resume()
                print(f"--- [PID: {os.getpid()}] Scheduler wznowiony po resecie. ---")

            return {'message': 'Scheduler został zresetowany z domyślnymi ustawieniami', 'status': 'reset'}
        except Exception as e:
            print(f"Błąd w [PID: {os.getpid()}] podczas resetowania schedulera: {str(e)}")
            return {'error': f'Błąd podczas resetowania schedulera: {str(e)}'}, 500

    @app.route('/api/scheduler/debug', methods=['GET'])
    def debug_scheduler():
        """Endpoint do debugowania schedulera - pokazuje szczegółowe informacje o wszystkich zadaniach"""
        print(f"--- [PID: {os.getpid()}] Zapytanie API: /api/scheduler/debug ---")
        if app.config.get('TESTING'):
            return {'error': 'Scheduler niedostępny w trybie testowym'}, 400
            
        try:
            jobs = []
            for job in scheduler.get_jobs():
                jobs.append({
                    'id': job.id,
                    'name': job.name,
                    'func': job.func.__name__ if hasattr(job.func, '__name__') else str(job.func),
                    'trigger': str(job.trigger),
                    'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                    'active': job.next_run_time is not None,
                    'max_instances': job.max_instances,
                    'misfire_grace_time': job.misfire_grace_time,
                    'coalesce': job.coalesce
                })
            
            return {
                'scheduler_running': scheduler.running,
                'total_jobs': len(jobs),
                'active_jobs': len([j for j in jobs if j['active']]),
                'jobs': jobs,
                'scheduler_jobs_keys': list(scheduler_jobs.keys()),
                'api_pid': os.getpid()
            }
        except Exception as e:
            return {'error': f'Błąd podczas debugowania: {str(e)}'}, 500

    @app.route('/api/scheduler/force-stop-all', methods=['POST'])
    def force_stop_all_jobs():
        """Wymusza wyłączenie wszystkich zadań schedulera"""
        print(f"--- [PID: {os.getpid()}] Zapytanie API: /api/scheduler/force-stop-all ---")
        if app.config.get('TESTING'):
            return {'error': 'Scheduler niedostępny w trybie testowym'}, 400
            
        try:
            # Zatrzymaj scheduler
            if scheduler.running:
                scheduler.shutdown()
            
            # Usuń wszystkie zadania
            existing_jobs = scheduler.get_jobs()
            removed_count = 0
            for job in existing_jobs:
                scheduler.remove_job(job.id)
                removed_count += 1
                print(f"🛑 Wymuszenie wyłączenia zadania: {job.id}")
            
            return {
                'message': f'Wymuszenie wyłączenia {removed_count} zadań', 
                'status': 'stopped',
                'removed_jobs': removed_count,
                'api_pid': os.getpid()
            }
        except Exception as e:
            print(f"Błąd w [PID: {os.getpid()}] podczas wymuszenia wyłączenia: {str(e)}")
            return {'error': f'Błąd podczas wymuszenia wyłączenia: {str(e)}'}, 500

    return app