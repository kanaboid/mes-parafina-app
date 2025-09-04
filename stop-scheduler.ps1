# stop-scheduler.ps1
# Zatrzymuje Celery Beat (scheduler) - zadania przestana byc wysylane automatycznie

Write-Host "Zatrzymuje Celery Beat (scheduler)..." -ForegroundColor Yellow
docker-compose stop celery-worker
Write-Host "Scheduler zatrzymany. Zadania nie beda juz wysylane automatycznie." -ForegroundColor Green
Write-Host "Aby uruchomic ponownie, uzyj: .\start-scheduler.ps1" -ForegroundColor Cyan
