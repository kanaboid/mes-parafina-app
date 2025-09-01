web: gunicorn --worker-class eventlet -w 1 --preload "run:app"
worker: celery -A celery_app.celery worker --loglevel=info --max-tasks-per-child 100 --concurrency=2
beat: celery -A celery_app.celery beat -l info
