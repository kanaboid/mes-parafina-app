# app/scheduler_service.py

from .extensions import db
from sqlalchemy import text
from datetime import datetime, timedelta
from decimal import Decimal

class SchedulerService:
    
    @staticmethod
    def get_all_tasks():
        """
        Pobiera wszystkie zadania z harmonogramu Celery z bazy danych.
        """
        try:
            # Pobierz zadania z tabeli periodic_task wraz z informacjami o interwałach
            query = text("""
                SELECT 
                    pt.id,
                    pt.name,
                    pt.enabled,
                    pt.last_run_at,
                    pt.total_run_count,
                    cis.every as interval_seconds,
                    cis.period as interval_period
                FROM celery_periodic_task pt
                LEFT JOIN celery_interval_schedule cis ON pt.interval_id = cis.id
                WHERE pt.name IN ('read-sensors-periodic', 'check-alarms-periodic')
                ORDER BY pt.name
            """)
            
            result = db.session.execute(query)
            tasks = []
            
            for row in result:
                # Konwertuj interwał na sekundy
                interval_seconds = 0
                if row.interval_seconds and row.interval_period:
                    if row.interval_period == 'seconds':
                        interval_seconds = int(row.interval_seconds)
                    elif row.interval_period == 'minutes':
                        interval_seconds = int(row.interval_seconds) * 60
                    elif row.interval_period == 'hours':
                        interval_seconds = int(row.interval_seconds) * 3600
                
                # Oblicz następne wykonanie
                next_run = None
                if row.last_run_at and row.enabled:
                    last_run = row.last_run_at
                    next_run = last_run + timedelta(seconds=interval_seconds)
                
                task_data = {
                    'id': row.id,
                    'name': row.name,
                    'enabled': bool(row.enabled),
                    'interval_seconds': interval_seconds,
                    'last_run_at': row.last_run_at.isoformat() + 'Z' if row.last_run_at else None,
                    'next_run_at': next_run.isoformat() + 'Z' if next_run else None,
                    'total_run_count': row.total_run_count or 0
                }
                tasks.append(task_data)
            
            return tasks
            
        except Exception as e:
            print(f"Błąd podczas pobierania zadań: {e}")
            return []
    
    @staticmethod
    def toggle_task(task_id, enabled):
        """
        Włącza lub wyłącza zadanie.
        """
        try:
            query = text("""
                UPDATE celery_periodic_task 
                SET enabled = :enabled 
                WHERE id = :task_id
            """)
            
            db.session.execute(query, {
                'enabled': 1 if enabled else 0,
                'task_id': task_id
            })
            
            # WAŻNE: Zaktualizuj timestamp w PeriodicTaskChanged, aby Celery Beat wiedział o zmianie
            SchedulerService._notify_schedule_changed()
            
            db.session.commit()
            return True
            
        except Exception as e:
            print(f"Błąd podczas zmiany stanu zadania: {e}")
            db.session.rollback()
            return False
    
    @staticmethod
    def update_task_interval(task_id, interval_seconds):
        """
        Aktualizuje interwał zadania.
        """
        try:
            # Najpierw znajdź istniejący interwał lub utwórz nowy
            interval_query = text("""
                SELECT id FROM celery_interval_schedule 
                WHERE every = :every AND period = 'seconds'
            """)
            
            result = db.session.execute(interval_query, {'every': interval_seconds})
            interval_row = result.fetchone()
            
            if interval_row:
                interval_id = interval_row.id
            else:
                # Utwórz nowy interwał
                insert_interval = text("""
                    INSERT INTO celery_interval_schedule (every, period) 
                    VALUES (:every, 'seconds')
                """)
                db.session.execute(insert_interval, {'every': interval_seconds})
                db.session.flush()
                
                # Pobierz ID nowego interwału
                interval_id = db.session.execute(text("SELECT LAST_INSERT_ID()")).scalar()
            
            # Zaktualizuj zadanie
            update_query = text("""
                UPDATE celery_periodic_task 
                SET interval_id = :interval_id 
                WHERE id = :task_id
            """)
            
            db.session.execute(update_query, {
                'interval_id': interval_id,
                'task_id': task_id
            })
            
            # WAŻNE: Zaktualizuj timestamp w PeriodicTaskChanged, aby Celery Beat wiedział o zmianie
            SchedulerService._notify_schedule_changed()
            
            db.session.commit()
            return True
            
        except Exception as e:
            print(f"Błąd podczas aktualizacji interwału: {e}")
            db.session.rollback()
            return False
    
    @staticmethod
    def get_predefined_intervals():
        """
        Zwraca listę predefiniowanych interwałów.
        """
        return [
            {'value': 1, 'label': '1 sekunda'},
            {'value': 5, 'label': '5 sekund'},
            {'value': 30, 'label': '30 sekund'},
            {'value': 60, 'label': '1 minuta'},
            {'value': 300, 'label': '5 minut'},
            {'value': 600, 'label': '10 minut'}
        ]
    
    @staticmethod
    def _notify_schedule_changed():
        """
        Powiadamia Celery Beat o zmianie w harmonogramie poprzez aktualizację
        pola last_update w tabeli celery_periodic_task_changed.
        """
        try:
            # Sprawdź czy istnieje wpis w PeriodicTaskChanged
            check_query = text("SELECT id FROM celery_periodic_task_changed WHERE id = 1")
            result = db.session.execute(check_query).fetchone()
            
            if result:
                # Aktualizuj istniejący wpis
                update_query = text("""
                    UPDATE celery_periodic_task_changed 
                    SET last_update = NOW() 
                    WHERE id = 1
                """)
                db.session.execute(update_query)
            else:
                # Utwórz nowy wpis
                insert_query = text("""
                    INSERT INTO celery_periodic_task_changed (id, last_update) 
                    VALUES (1, NOW())
                """)
                db.session.execute(insert_query)
            
            print("Powiadomiono Celery Beat o zmianie harmonogramu")
            
        except Exception as e:
            print(f"Błąd podczas powiadamiania o zmianie harmonogramu: {e}")
