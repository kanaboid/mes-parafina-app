# show-config.ps1
# Pokazuje aktualną konfigurację zadań

Write-Host "=== AKTUALNA KONFIGURACJA ZADAŃ ===" -ForegroundColor Yellow
Write-Host "SENSORS_INTERVAL: $env:SENSORS_INTERVAL s" -ForegroundColor Cyan
Write-Host "ALARMS_INTERVAL: $env:ALARMS_INTERVAL s" -ForegroundColor Cyan
Write-Host "SENSORS_ENABLED: $env:SENSORS_ENABLED" -ForegroundColor Cyan
Write-Host "ALARMS_ENABLED: $env:ALARMS_ENABLED" -ForegroundColor Cyan

Write-Host "`n=== STATUS WORKERA ===" -ForegroundColor Yellow
docker-compose exec celery-worker celery -A celery_app.celery inspect registered
