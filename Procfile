web: uv run gunicorn --worker-class eventlet -w 1 --preload "run:app"
worker: uv run celery -A celery_app.celery worker --loglevel=info --max-tasks-per-child 100 --concurrency=2
beat: uv run celery -A celery_app.celery beat -l info --scheduler celery_sqlalchemy_scheduler.schedulers.DatabaseScheduler
