Oto lista wszystkich endpointów wraz z krótkimi opisami:

## Strony HTML (Frontend)
- `GET /` - Serwuje główną stronę aplikacji
- `GET /alarms` - Wyświetla stronę z historią wszystkich alarmów
- `GET /operacje` - Wyświetla stronę z operacjami tankowania
- `GET /filtry` - Renderuje stronę z panelem monitoringu filtrów
- `GET /cykle-monitor` - Serwuje stronę monitoringu cykli filtracyjnych
- `GET /aktywne-partie` - Serwuje stronę zarządzania aktywnymi partiami

## API - Sprzęt i Topologia
- `GET /api/sprzet` - Zwraca listę całego sprzętu wraz z informacją o partiach
- `GET /api/zawory` - Zwraca listę wszystkich zaworów i ich aktualny stan
- `POST /api/zawory/zmien_stan` - Zmienia stan pojedynczego zaworu
- `GET /api/topologia` - Zwraca pełną listę połączeń (segmentów) do wizualizacji
- `GET /api/sprzet/filtry` - Zwraca listę filtrów
- `GET /api/sprzet/beczki-brudne` - Zwraca listę beczek brudnych dostępnych do tankowania
- `GET /api/sprzet/reaktory-puste` - Zwraca listę reaktorów w stanie 'Pusty'
- `GET /api/sprzet/reaktory-z-surowcem` - Zwraca listę reaktorów zawierających surowiec

## API - Operacje i Transfery
- `POST /api/operacje/tankowanie` - Tworzy nową partię przez tankowanie (z czystego źródła)
- `POST /api/operacje/tankowanie-brudnego` - Tankowanie brudnego surowca z beczki do reaktora
- `POST /api/operacje/rozpocznij_trase` - Rozpoczyna operację transferu na określonej trasie
- `POST /api/operacje/zakoncz` - Kończy aktywną operację i zamyka zawory
- `GET /api/operacje/aktywne` - Zwraca listę wszystkich operacji ze statusem 'aktywna'
- `POST /api/operacje/dobielanie` - Dodaje ziemię bielejącą do partii (dodaje worki)
- `POST /api/operacje/transfer-reaktorow` - Transfer surowca między reaktorami, opcjonalnie przez filtr

## API - Planowanie Tras
- `GET /api/punkty_startowe` - Zwraca listę wszystkich portów wyjściowych (OUT)
- `GET /api/punkty_docelowe` - Zwraca listę wszystkich portów wejściowych (IN)
- `POST /api/trasy/sugeruj` - Znajduje optymalną trasę i zwraca potrzebne zawory

## API - Partie i Cykle Filtracyjne
- `GET /api/partie/aktywne` - Pobiera listę aktywnych partii z pełnymi szczegółami
- `GET /api/partie/szczegoly/<int:partia_id>` - Pobiera szczegółowe informacje o konkretnej partii
- `POST /api/partie/aktualizuj-status` - Aktualizuje status partii
- `GET /api/partie/aktualny-stan` - Pobiera aktualny stan wszystkich partii w systemie
- `GET /api/cykle-filtracyjne/<int:id_partii>` - Pobiera historię cykli filtracyjnych dla partii
- `POST /api/cykle/rozpocznij` - Rozpoczyna nowy cykl filtracyjny dla partii
- `POST /api/cykle/zakoncz` - Kończy aktualny cykl filtracyjny

## API - Filtry
- `GET /api/filtry/status` - Zwraca aktualny status filtrów z informacją o operacjach
- `GET /api/filtry/szczegolowy-status` - Pobiera szczegółowy status filtrów z partiami i cyklami

## API - Alarmy i Monitoring
- `GET /api/alarmy/aktywne` - Zwraca listę aktywnych alarmów
- `POST /api/alarmy/potwierdz` - Potwierdza alarm (zmienia status na 'POTWIERDZONY')
- `GET /api/pomiary/historia` - Pobiera historię pomiarów z ostatnich 24 godzin
- `POST /api/sprzet/<int:sprzet_id>/temperatura` - Ustawia docelową temperaturę dla sprzętu

## API - Testowe/Debugowanie
- `POST /api/test/sensors` - Endpoint testowy do wymuszenia odczytu czujników
- `POST /api/test/alarm` - Endpoint do testowania alarmów (wymuszanie alarmu)

## API - Dane Słownikowe
- `GET /api/typy-surowca` - Zwraca listę dostępnych typów surowca

System obsługuje głównie operacje typu POST dla akcji (tankowanie, transfery, zarządzanie cyklami) oraz GET dla pobierania danych i wyświetlania stron. Endpointy są podzielone logicznie na grupy funkcjonalne: zarządzanie sprzętem, operacje produkcyjne, monitoring i alarmy.