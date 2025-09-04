# disable-alarms.ps1
# Wylacza zadanie sprawdzania alarmow

Write-Host "Wylaczam zadanie sprawdzania alarmow..." -ForegroundColor Yellow
$env:ALARMS_ENABLED = "false"
docker-compose stop celery-worker
docker-compose up -d celery-worker
Write-Host "Zadanie sprawdzania alarmow wylaczone!" -ForegroundColor Green
