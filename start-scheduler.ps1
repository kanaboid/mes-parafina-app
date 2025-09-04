# start-scheduler.ps1
# Uruchamia Celery Beat (scheduler) - zadania będą wysyłane automatycznie
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "Uruchamiam Celery Beat (scheduler)..." -ForegroundColor Yellow
docker-compose up -d celery-worker
Write-Host "Scheduler uruchomiony. Zadania będą wysyłane automatycznie." -ForegroundColor Green
Write-Host "Aby zatrzymać, użyj: .\stop-scheduler.ps1" -ForegroundColor Cyan
