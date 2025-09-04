# set-intervals.ps1
# Ustawia interwały zadań i restartuje worker

param(
    [float]$SensorsInterval = 10.0,
    [float]$AlarmsInterval = 5.0,
    [bool]$SensorsEnabled = $true,
    [bool]$AlarmsEnabled = $true
)

Write-Host "Ustawiam interwaly zadan..." -ForegroundColor Yellow
Write-Host "Sensors: $SensorsInterval s (enabled: $SensorsEnabled)" -ForegroundColor Cyan
Write-Host "Alarms: $AlarmsInterval s (enabled: $AlarmsEnabled)" -ForegroundColor Cyan

# Ustaw zmienne środowiskowe
$env:SENSORS_INTERVAL = $SensorsInterval.ToString()
$env:ALARMS_INTERVAL = $AlarmsInterval.ToString()
$env:SENSORS_ENABLED = $SensorsEnabled.ToString().ToLower()
$env:ALARMS_ENABLED = $AlarmsEnabled.ToString().ToLower()

# Restartuj worker z nowymi ustawieniami
Write-Host "Restartuje worker z nowymi ustawieniami..." -ForegroundColor Yellow
docker-compose stop celery-worker
docker-compose up -d celery-worker

Write-Host "Interwaly zaktualizowane!" -ForegroundColor Green
Write-Host "Sprawdz logi: docker-compose logs celery-worker --tail=10" -ForegroundColor Cyan
