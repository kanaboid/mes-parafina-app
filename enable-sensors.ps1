# enable-sensors.ps1
# Włącza zadanie odczytu czujników

param([float]$Interval = 10.0)

Write-Host "Włączam zadanie odczytu czujników z interwałem $Interval s..." -ForegroundColor Yellow
$env:SENSORS_ENABLED = "true"
$env:SENSORS_INTERVAL = $Interval.ToString()
docker-compose restart celery-worker
Write-Host "Zadanie odczytu czujników włączone!" -ForegroundColor Green
