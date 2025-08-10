# Aktywne Partie w Systemie - Dokumentacja Rozbudowy

## Opis funkcjonalności

Sekcja "Aktywne Partie w Systemie" została znacznie rozbudowana i teraz oferuje kompleksowe zarządzanie partiami produkcyjnymi. System umożliwia:

- **Przeglądanie aktywnych partii** - szczegółowa tabela z filtrami i wyszukiwaniem
- **Monitorowanie statusu** - realne czas, lokalizacja, operacje
- **Zarządzanie statusami** - edycja statusów partii z historią zmian
- **Szczegóły partii** - kompletna historia operacji i cykli filtracyjnych
- **Statystyki** - ogólne statystyki o partiach w systemie

## Nowe endpointy API

### 1. `/api/partie/aktywne` (GET)
Zwraca listę wszystkich aktywnych partii w systemie z pełnymi szczegółami:
- Informacje o partii (kod, nazwa, typ surowca, waga, data utworzenia)
- Lokalizacja (aktualne urządzenie, typ sprzętu, stan)
- Status operacji (aktywne operacje, czas trwania)
- Czasy (wiek partii, czas operacji)
- Statusy i historia operacji

### 2. `/api/partie/szczegoly/<int:partia_id>` (GET)
Pobiera szczegółowe informacje o konkretnej partii:
- Pełne informacje podstawowe
- Kompletna historia wszystkich operacji
- Lista wszystkich statusów partii
- Historia cykli filtracyjnych (jeśli istnieją)

### 3. `/api/partie/aktualizuj-status` (POST)
Aktualizuje status partii:
```json
{
    "id_partii": 1,
    "nowy_status": "Filtrowanie",
    "komentarz": "Opcjonalny komentarz"
}
```

## Nowa strona interfejsu

### `/aktywne-partie`
Dedykowana strona z kompleksowym interfejsem zawierająca:

#### Statystyki
- Liczba wszystkich partii
- Liczba aktywnych operacji
- Łączna waga wszystkich partii
- Średni wiek partii w systemie
- Najczęstsza lokalizacja

#### Filtry i wyszukiwanie
- **Wyszukiwanie tekstowe** - po kodzie partii, nazwie, typie surowca, lokalizacji
- **Filtr statusu** - według aktualnego statusu partii
- **Filtr typu surowca** - według typu materiału
- **Filtr lokalizacji** - według aktualnej lokalizacji
- **Filtr operacji** - tylko aktywne operacje lub bez operacji

#### Tabela partii
- **Kod partii** - z czasem w systemie
- **Nazwa** - ze źródłem pochodzenia
- **Typ surowca** - w formie znacznika
- **Status** - kolorowe znaczniki według statusu
- **Waga** - aktualna z paskiem postępu i różnicą
- **Lokalizacja** - nazwa i typ sprzętu
- **Czas w systemie** - z kolorowym oznaczeniem
- **Operacja** - status z animowanym wskaźnikiem
- **Akcje** - szczegóły, edycja statusu, historia, zatrzymanie operacji

#### Panel szczegółów
Rozwijaný panel z:
- Informacjami podstawowymi w tabeli
- Informacjami o wadze i lokalizacji
- Timeline historii operacji z animacjami
- Tabelą cykli filtracyjnych (jeśli istnieją)

#### Modal edycji statusu
Formularz do zmiany statusu partii z:
- Wyborem nowego statusu z listy rozwijanej
- Opcjonalnym komentarzem
- Automatycznym logowaniem zmian

## Ulepszona integracja

### Monitor Cykli (`/cykle-monitor`)
Zaktualizowana sekcja aktywnych partii w monitorze cykli teraz:
- Korzysta z nowego endpointu `/api/partie/aktywne`
- Wyświetla dane w formacie zgodnym z nową strukturą bazy
- Obsługuje nowe statusy partii
- Pokazuje aktualny czas trwania operacji

### Nawigacja
Dodano nowy link "Aktywne Partie" w głównej nawigacji systemu.

## Funkcje dodatkowe

### Automatyczne odświeżanie
- Strona aktywnych partii odświeża się automatycznie co 60 sekund
- Monitor cykli odświeża się co 30 sekund
- Timery działają w czasie rzeczywistym

### Eksport danych
- Funkcja eksportu do CSV z aktualnymi filtrami
- Eksport zawiera: kod partii, nazwę, typ surowca, status, wagę, lokalizację, czas w systemie

### Responsywność
- Interfejs dostosowany do różnych rozmiarów ekranu
- Mobilne menu nawigacji
- Responsywne tabele ze skrolowaniem

### Animacje i UX
- Efekty ładowania (skeleton loading)
- Animowane wskaźniki aktywnych operacji
- Płynne przejścia i hover effects
- Toast notifications dla wszystkich akcji
- Timeline z animowanymi znacznikami

## Możliwości dalszej rozbudowy

### 1. Zaawansowane filtrowanie
- Filtr według zakresu dat
- Filtr według zakresu wag
- Filtr według czasu w systemie
- Zapisywanie predefiniowanych filtrów

### 2. Raporty i analityki
- Wykresy czasu procesu partii
- Analiza wydajności filtrów
- Raporty zużycia surowców
- Trendy czasowe

### 3. Planowanie produkcji
- Kalendarz planowania partii
- Prognozowanie zakończenia procesów
- Optymalizacja kolejności operacji
- Zarządzanie priorytetami

### 4. Integracja z zewnętrznymi systemami
- Import danych o partiach z ERP
- Eksport do systemów jakości
- Integracja z systemami SCADA
- API dla aplikacji mobilnych

### 5. Zaawansowane zarządzanie
- Masowe operacje na partiach
- Szablony operacji
- Przepływy automatyzacji (workflows)
- System powiadomień

### 6. Zarządzanie dokumentacją
- Załączniki do partii
- Protokoły jakości
- Certyfikaty
- Historia dokumentów

## Struktura plików

### Backend (Python/Flask)
- `app/routes.py` - nowe endpointy API dla partii
- `app/templates/aktywne_partie.html` - nowa strona interfejsu
- `app/templates/base.html` - zaktualizowana nawigacja

### Frontend (JavaScript/CSS)
- `app/static/js/aktywne_partie.js` - logika nowej strony
- `app/static/js/cykle_monitor.js` - zaktualizowana logika monitora cykli

### Zmiany w bazie danych
System korzysta z istniejącej struktury bazy danych bez zmian, ale wykorzystuje:
- Tabela `partie_surowca` - podstawowe informacje o partiach
- Tabela `operacje_log` - historia operacji
- Tabela `partie_statusy` + `statusy` - statusy partii
- Tabela `cykle_filtracyjne` - cykle filtracyjne
- Tabela `sprzet` - informacje o lokalizacji

## Testowanie

Wszystkie nowe funkcjonalności zostały przetestowane:
- ✅ Endpointy API zwracają poprawne dane
- ✅ Interfejs wyświetla partie z filtrami
- ✅ Edycja statusów działa poprawnie
- ✅ Szczegóły partii pokazują pełną historię
- ✅ Integracja z monitorem cykli działa
- ✅ Nawigacja i responsywność działają

System jest gotowy do użycia produkcyjnego i dalszej rozbudowy.
