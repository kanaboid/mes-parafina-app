# disable-sensors.ps1
# Wyłącza zadanie odczytu czujników

Write-Host "Wylaczam zadanie odczytu czujnikow..." -ForegroundColor Yellow
$env:SENSORS_ENABLED = "false"
docker-compose stop celery-worker
docker-compose up -d celery-worker
Write-Host "Zadanie odczytu czujnikow wylaczone!" -ForegroundColor Green
