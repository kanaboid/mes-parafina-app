# Topologia MES Parafina - Dokumentacja

## Przegląd

System zarządzania cyfrową mapą rurociągu w aplikacji MES Parafina został pomyślnie zaimplementowany. System umożliwia zarządzanie elementami topologii instalacji, testowanie połączeń PathFinder oraz wizualizację sieci rurociągów.

## Funkcjonalności

### 1. Zarządzanie Zaworami (`/topology/zawory`)
- **Wyświetlanie listy zaworów** z filtrami i wyszukiwarką
- **Dodawanie nowych zaworów** z walidacją danych
- **Edycja istniejących zaworów**
- **Usuwanie zaworów** z potwierdzeniem
- **Podgląd szczegółów** zaworu w modalnym oknie

### 2. Zarządzanie Węzłami (`/topology/wezly`)
- **Wyświetlanie listy węzłów** rurociągu
- **Dodawanie nowych węzłów** z określeniem pozycji
- **Edycja węzłów** z aktualizacją współrzędnych
- **Usuwanie węzłów** 
- **Podgląd szczegółów** węzła

### 3. Zarządzanie Segmentami (`/topology/segmenty`)
- **Wyświetlanie listy segmentów** z powiązanym sprzętem
- **Dodawanie nowych segmentów** z wyborem sprzętu źródłowego/docelowego
- **Edycja segmentów** z aktualizacją portów i zaworów
- **Usuwanie segmentów**
- **Podgląd szczegółów** segmentu z pełną informacją o połączeniach

### 4. Wizualizacja Topologii (`/topology/visualization`)
- **Wizualizacja graficzna** - interaktywny graf sieci (NetworkX + D3.js)
- **Widok tekstowy** - strukturalna reprezentacja połączeń
- **Widok tabelaryczny** - szczegółowa tabela wszystkich elementów
- **Eksport danych** - możliwość pobierania danych w różnych formatach

### 5. Tester PathFinder (`/topology/pathfinder`)
- **Testowanie tras** między punktami startowymi a docelowymi
- **Symulacja stanów zaworów** z różnymi scenariuszami
- **Historia testów** z możliwością porównania wyników
- **Analiza krytycznych zaworów** wpływających na dostępność tras

## Struktura API

### Endpointy Zaworów
- `GET /topology/api/zawory` - Lista zaworów
- `GET /topology/api/zawory/<id>` - Szczegóły zaworu
- `POST /topology/api/zawory` - Tworzenie zaworu
- `PUT /topology/api/zawory/<id>` - Aktualizacja zaworu
- `DELETE /topology/api/zawory/<id>` - Usuwanie zaworu

### Endpointy Węzłów
- `GET /topology/api/wezly` - Lista węzłów
- `GET /topology/api/wezly/<id>` - Szczegóły węzła
- `POST /topology/api/wezly` - Tworzenie węzła
- `PUT /topology/api/wezly/<id>` - Aktualizacja węzła
- `DELETE /topology/api/wezly/<id>` - Usuwanie węzła

### Endpointy Segmentów
- `GET /topology/api/segmenty` - Lista segmentów
- `GET /topology/api/segmenty/<id>` - Szczegóły segmentu
- `POST /topology/api/segmenty` - Tworzenie segmentu
- `PUT /topology/api/segmenty/<id>` - Aktualizacja segmentu
- `DELETE /topology/api/segmenty/<id>` - Usuwanie segmentu

### Endpointy Pomocnicze
- `GET /topology/api/sprzet` - Lista sprzętu
- `GET /topology/api/sprzet/<id>/porty` - Porty konkretnego sprzętu
- `GET /topology/api/porty` - Lista wszystkich portów
- `GET /topology/api/points` - Wszystkie punkty (porty + węzły)

## Struktura Plików

### Logika Biznesowa
- `app/topology_manager.py` - Menedżer operacji CRUD na topologii
- `app/pathfinder_tester.py` - Tester algorytmu PathFinder
- `app/topology_routes.py` - Definicje endpointów API i widoków

### Szablony HTML
- `app/templates/topology/index.html` - Panel główny topologii
- `app/templates/topology/zawory.html` - Zarządzanie zaworami
- `app/templates/topology/wezly.html` - Zarządzanie węzłami
- `app/templates/topology/segmenty.html` - Zarządzanie segmentami
- `app/templates/topology/visualization.html` - Wizualizacja topologii
- `app/templates/topology/pathfinder.html` - Tester PathFinder

## Konfiguracja

### Integracja z Główną Aplikacją
- Blueprint `topology_bp` zarejestrowany w `app/__init__.py`
- Link do topologii dodany w menu głównym (`base.html`)
- Dodano Font Awesome i jQuery dla funkcjonalności UI

### Baza Danych
System wykorzystuje istniejące tabele:
- `zawory` - definicje zaworów
- `wezly_rurociagu` - węzły sieci
- `segmenty` - segmenty rurociągu
- `porty_sprzetu` - porty sprzętu
- `sprzet` - definicje sprzętu

## Testowanie

### Środowisko Testowe
- Aplikacja uruchamiana w trybie debug na `http://127.0.0.1:5000`
- Dostępne wszystkie endpointy API
- Interaktywne testy przez przeglądarkę

### Status Funkcjonalności
✅ **Zawory** - pełna funkcjonalność CRUD
✅ **Węzły** - pełna funkcjonalność CRUD
✅ **Segmenty** - pełna funkcjonalność CRUD
✅ **API** - wszystkie endpointy działają poprawnie
✅ **Wizualizacja** - widoki graficzne i tabelaryczne
✅ **PathFinder** - tester algorytmu tras

## Przyszłe Rozszerzenia

### Planowane Funkcjonalności
- **Walidacja spójności** - automatyczne sprawdzanie integralności topologii
- **Import/Export** - możliwość importu/eksportu konfiguracji
- **Wersjonowanie** - historia zmian topologii
- **Szablony** - predefiniowane konfiguracje
- **Backup/Restore** - zarządzanie kopiami zapasowymi
- **Integracja z alarmami** - powiadomienia o problemach z topologią

### Możliwości Rozwoju
- **Zaawansowana wizualizacja** - 3D, animacje, interaktywne mapy
- **Analiza przepływów** - symulacja przepływów materiałów
- **Optymalizacja tras** - algorytmy optymalizacji
- **Monitoring real-time** - śledzenie stanu w czasie rzeczywistym
- **Raportowanie** - generowanie raportów o stanie instalacji

## Kontakt i Wsparcie

System został zaimplementowany zgodnie z wymaganiami, zachowując kompatybilność z istniejącą aplikacją MES Parafina. Wszystkie nowe funkcje zostały dodane jako rozszerzenia, bez modyfikacji istniejących endpointów.

**Data implementacji:** 5 lipca 2025
**Wersja:** 1.0
**Status:** Gotowy do użycia
