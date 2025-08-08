# migrate.ps1
# Wersja finalna, używająca zmiennych środowiskowych do przełączania trybu.

param (
    [Parameter(Mandatory=$true, Position=0)]
    [ValidateSet("generate", "upgrade", "downgrade", "history", "current")]
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
        # Ustaw zmienną środowiskową TYLKO na czas trwania tej komendy
        $env:ALEMBIC_TEST_MODE = "true"
        alembic upgrade head
    } finally {
        # Upewnij się, że zmienna jest zawsze czyszczona, nawet w przypadku błędu
        $env:ALEMBIC_TEST_MODE = $null
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
}

Write-Output ""
Write-Output "--- Skrypt zakonczyl dzialanie ---"