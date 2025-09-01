web: gunicorn --worker-class eventlet -w 1 --preload "run:app"
worker: celery -A celery_app.celery worker -l info
beat: celery -A celery_app.celery beat -l info
