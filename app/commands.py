import click
from flask.cli import with_appcontext

# Zaimportuj obiekt `db` ze swojego pliku z rozszerzeniami (np. extensions.py)
from app.extensions import db

# Zaimportuj modele z biblioteki schedulera
from celery_sqlalchemy_scheduler.models import PeriodicTask, IntervalSchedule

@click.command(name='seed_tasks')
@with_appcontext
def seed_tasks():
    """
    Tworzy domyślne, cykliczne zadania Celery Beat w bazie danych.
    Ta komenda jest idempotentna - nie stworzy duplikatów.
    """
    print("Rozpoczęto inicjalizację domyślnych zadań Celery...")

    # --- Zadanie 1: Cykliczny odczyt sensorów ---
    task_name_1 = 'read-sensors-periodic'
    
    # Sprawdź, czy zadanie o tej nazwie już istnieje
    if not db.session.query(PeriodicTask).filter_by(name=task_name_1).first():
        
        # Znajdź lub stwórz interwał "co 10 sekund"
        interval_10s = db.session.query(IntervalSchedule).filter_by(every=10, period='seconds').first()
        if not interval_10s:
            interval_10s = IntervalSchedule(every=10, period='seconds')
            db.session.add(interval_10s)
            # Musimy zapisać do bazy, aby uzyskać ID dla interwału
            db.session.commit()
        
        # Stwórz obiekt zadania
        task1 = PeriodicTask(
            interval_id=interval_10s.id,
            name=task_name_1,
            task='app.tasks.read_sensors_task'  # Upewnij się, że ścieżka jest poprawna
        )
        db.session.add(task1)
        print(f"-> Stworzono zadanie: '{task_name_1}'")

    # --- Zadanie 2: Cykliczne sprawdzanie alarmów ---
    task_name_2 = 'check-alarms-periodic'

    # Sprawdź, czy zadanie o tej nazwie już istnieje
    if not db.session.query(PeriodicTask).filter_by(name=task_name_2).first():

        # Znajdź lub stwórz interwał "co 5 sekund"
        interval_5s = db.session.query(IntervalSchedule).filter_by(every=5, period='seconds').first()
        if not interval_5s:
            interval_5s = IntervalSchedule(every=5, period='seconds')
            db.session.add(interval_5s)
            db.session.commit()

        # Stwórz obiekt zadania
        task2 = PeriodicTask(
            interval_id=interval_5s.id,
            name=task_name_2,
            task='app.tasks.check_alarms_task'  # Upewnij się, że ścieżka jest poprawna
        )
        db.session.add(task2)
        print(f"-> Stworzono zadanie: '{task_name_2}'")

    # Zapisz wszystkie zmiany w bazie danych
    db.session.commit()
    print("Zakończono inicjalizację domyślnych zadań.")