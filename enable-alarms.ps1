# enable-alarms.ps1
# Włącza zadanie sprawdzania alarmów

param([float]$Interval = 5.0)

Write-Host "Włączam zadanie sprawdzania alarmów z interwałem $Interval s..." -ForegroundColor Yellow
$env:ALARMS_ENABLED = "true"
$env:ALARMS_INTERVAL = $Interval.ToString()
docker-compose restart celery-worker
Write-Host "Zadanie sprawdzania alarmów włączone!" -ForegroundColor Green
