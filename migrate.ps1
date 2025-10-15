# migrate.ps1
# Wersja z obsługą bazy produkcyjnej Railway

param (
    [Parameter(Mandatory=$true, Position=0)]
    [ValidateSet("generate", "upgrade", "downgrade", "history", "current", "stamp-test", "stamp-prod", "upgrade-prod", "downgrade-prod")]
    [string]$Command,

    [Parameter(Position=1)]
    [string]$Message
)

function Check-Last-Success {
    if ($LASTEXITCODE -ne 0) {
        Write-Output "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        Write-Output "!!! BLAD: Poprzednia komenda zakonczyla sie niepowodzeniem. Przerwanie skryptu."
        Write-Output "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        # Przywróć zmienną środowiskową na wszelki wypadek
        $env:ALEMBIC_TEST_MODE = $null
        $env:ALEMBIC_PROD_MODE = $null
        exit 1
    }
}

if ($Command -eq "generate") {
    if ([string]::IsNullOrEmpty($Message)) {
        Write-Output "BLAD: Komenda 'generate' wymaga podania komunikatu migracji."
        Write-Output "Przyklad: .\migrate.ps1 generate 'Dodanie nowej tabeli uzytkownikow'"
        exit 1
    }
    Write-Output "--- Generowanie nowej migracji... ---"
    alembic revision --autogenerate -m "$Message"

} elseif ($Command -eq "upgrade") {
    Write-Output "--- Aktualizacja bazy DEWELOPERSKIEJ do najnowszej wersji... ---"
    alembic upgrade head
    Check-Last-Success

    Write-Output ""
    Write-Output "--- Aktualizacja bazy TESTOWEJ do najnowszej wersji... ---"
    try {
        $env:ALEMBIC_TEST_MODE = "true"
        alembic upgrade head
    } finally {
        $env:ALEMBIC_TEST_MODE = $null
    }
    Check-Last-Success

    Write-Output ""
    Write-Output "==================================================="
    Write-Output "UWAGA: Baza PRODUKCYJNA (Railway) nie jest automatycznie aktualizowana!"
    Write-Output "Aby zaktualizowac baze produkcyjna, uzyj komendy:"
    Write-Output "  railway run pwsh migrate.ps1 upgrade-prod"
    Write-Output "==================================================="

} elseif ($Command -eq "upgrade-prod") {
    Write-Output "--- UWAGA: Aktualizacja bazy PRODUKCYJNEJ na Railway! ---"
    Write-Output "Upewnij sie, ze masz ustawiona zmienna DATABASE_URL_PROD."
    Write-Output "Nacisnij Ctrl+C aby anulowac, lub Enter aby kontynuowac..."
    Read-Host
    
    try {
        $env:ALEMBIC_PROD_MODE = "true"
        alembic upgrade head
    } finally {
        $env:ALEMBIC_PROD_MODE = $null
    }
    Check-Last-Success

} elseif ($Command -eq "downgrade") {
    Write-Output "--- Wycofanie ostatniej migracji z bazy DEWELOPERSKIEJ... ---"
    alembic downgrade -1
    Check-Last-Success

    Write-Output ""
    Write-Output "--- Wycofanie ostatniej migracji z bazy TESTOWEJ... ---"
    try {
        $env:ALEMBIC_TEST_MODE = "true"
        alembic downgrade -1
    } finally {
        $env:ALEMBIC_TEST_MODE = $null
    }
    Check-Last-Success

} elseif ($Command -eq "downgrade-prod") {
    Write-Output "--- UWAGA: Wycofanie migracji z bazy PRODUKCYJNEJ na Railway! ---"
    Write-Output "To jest NIEBEZPIECZNA operacja!"
    Write-Output "Nacisnij Ctrl+C aby anulowac, lub Enter aby kontynuowac..."
    Read-Host
    
    try {
        $env:ALEMBIC_PROD_MODE = "true"
        alembic downgrade -1
    } finally {
        $env:ALEMBIC_PROD_MODE = $null
    }
    Check-Last-Success

} elseif ($Command -eq "history") {
    Write-Output "--- Historia migracji... ---"
    alembic history

} elseif ($Command -eq "current") {
    Write-Output "--- Aktualna wersja bazy deweloperskiej... ---"
    alembic current
    
    Write-Output ""
    Write-Output "--- Aktualna wersja bazy testowej... ---"
    try {
        $env:ALEMBIC_TEST_MODE = "true"
        alembic current
    } finally {
        $env:ALEMBIC_TEST_MODE = $null
    }

    Write-Output ""
    Write-Output "--- Aktualna wersja bazy produkcyjnej (Railway)... ---"
    try {
        $env:ALEMBIC_PROD_MODE = "true"
        alembic current
    } finally {
        $env:ALEMBIC_PROD_MODE = $null
    }

} elseif ($Command -eq "stamp-test") {
    Write-Output "--- Stemplowanie bazy TESTOWEJ do najnowszej wersji (head)... ---"
    try {
        $env:ALEMBIC_TEST_MODE = "true"
        alembic stamp head
    } finally {
        $env:ALEMBIC_TEST_MODE = $null
    }
    Check-Last-Success

} elseif ($Command -eq "stamp-prod") {
    Write-Output "--- UWAGA: Stemplowanie bazy PRODUKCYJNEJ (Railway) do head! ---"
    Write-Output "Nacisnij Ctrl+C aby anulowac, lub Enter aby kontynuowac..."
    Read-Host
    
    try {
        $env:ALEMBIC_PROD_MODE = "true"
        alembic stamp head
    } finally {
        $env:ALEMBIC_PROD_MODE = $null
    }
    Check-Last-Success
}


Write-Output ""
Write-Output "--- Skrypt zakonczyl dzialanie ---"