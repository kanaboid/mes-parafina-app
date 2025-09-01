# app/tasks.py

from celery_app import celery, flask_app
from .sensors import SensorService
from .monitoring import MonitoringService
from .sockets import broadcast_dashboard_update
from datetime import datetime
import os
from flask_socketio import SocketIO
from memory_profiler import profile

# Ustal adres URL brokera Redis
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
if "REDIS_URL" not in os.environ:
    try:
        import socket
        socket.gethostbyname('redis')
        REDIS_URL = 'redis://redis:6379/0'
    except socket.error:
        pass

# Utwórz instancję SocketIO dedykowaną dla workera Celery
# Używa ona tego samego brokera Redis, co główna aplikacja
celery_socketio = SocketIO(message_queue=REDIS_URL)

@celery.task(name='app.tasks.read_sensors_task')
@profile
def read_sensors_task():
    """
    Zadanie Celery do odczytu danych z czujników.
    Używa memory_profiler do logowania zużycia pamięci.
    """
    print(f"\n--- [PID: {os.getpid()}] CELERY TASK: Uruchamiam read_sensors_task (z profilowaniem pamięci) o {datetime.now()} ---")
    try:
        # Serwisy są już zainicjowane w celery_app.py, więc możemy ich używać
        sensor_service = SensorService()
        sensor_service.read_sensors()
    except Exception as e:
        print(f"Błąd w zadaniu Celery 'read_sensors_task': {e}")
        # Można dodać bardziej zaawansowane logowanie lub ponawianie zadania
        
@celery.task(name='app.tasks.check_alarms_task')
def check_alarms_task():
    """
    Zadanie Celery do sprawdzania alarmów.
    Po zakończeniu, emituje zdarzenie Socket.IO przez Redisa.
    """
    print(f"\n--- [PID: {os.getpid()}] CELERY TASK: Uruchamiam check_alarms_task o {datetime.now()} ---")
    try:
        # Używamy kontekstu aplikacji zaimportowanego z celery_app
        with flask_app.app_context():
            monitoring_service = MonitoringService()
            monitoring_service.check_equipment_status()
            
            # Pobierz świeże dane
            from .dashboard_service import DashboardService
            dashboard_data = DashboardService.get_main_dashboard_data()
            
            # Wyemituj zdarzenie do wszystkich klientów przez Redisa
            celery_socketio.emit('dashboard_update', dashboard_data)
            print(f"--- [PID: {os.getpid()}] CELERY TASK: Wyemitowano 'dashboard_update' przez Redis. ---")

    except Exception as e:
        print(f"Błąd w zadaniu Celery 'check_alarms_task': {e}")
