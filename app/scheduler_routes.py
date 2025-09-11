# app/scheduler_routes.py
from flask import Blueprint, jsonify, request
from app.extensions import db
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'local_libs'))
from celery_sqlalchemy_scheduler import models
from celery_sqlalchemy_scheduler.models import PeriodicTask, IntervalSchedule


scheduler_bp = Blueprint('scheduler', __name__, url_prefix='/scheduler')

@scheduler_bp.route('/tasks', methods=['GET'])
def get_all_tasks():
    tasks = db.session.query(PeriodicTask).all()
    result = []
    for task in tasks:
        result.append({
            'id': task.id,
            'name': task.name,
            'task': task.task,
            'enabled': task.enabled,
            'interval': str(task.interval),
            'last_run_at': task.last_run_at
        })
    return jsonify(result)

@scheduler_bp.route('/tasks/<int:task_id>/toggle', methods=['POST'])
def toggle_task(task_id):
    """Włącza lub wyłącza zadanie."""
    task = db.session.query(PeriodicTask).get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
        
    task.enabled = not task.enabled
    db.session.commit()
    return jsonify({'message': f"Task '{task.name}' is now {'enabled' if task.enabled else 'disabled'}"})

@scheduler_bp.route('/tasks/<int:task_id>/interval', methods=['POST'])
def set_task_interval(task_id):
    """Zmienia interwał zadania. Oczekuje JSON: {"every": 30, "period": "seconds"}"""
    task = db.session.query(PeriodicTask).get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    data = request.get_json()
    every = data.get('every')
    period = data.get('period', 'seconds')

    if not every:
        return jsonify({'error': 'Missing "every" parameter'}), 400

    # Znajdź lub stwórz nowy interwał
    interval = db.session.query(IntervalSchedule).filter_by(every=every, period=period).first()
    if not interval:
        interval = IntervalSchedule(every=every, period=period)
        db.session.add(interval)
        db.session.commit()
    
    task.interval_id = interval.id
    db.session.commit()
    return jsonify({'message': f"Task '{task.name}' interval set to every {every} {period}"})

# Pamiętaj, aby zarejestrować ten blueprint w app/__init__.py:
# from .scheduler_routes import scheduler_bp
# app.register_blueprint(scheduler_bp)