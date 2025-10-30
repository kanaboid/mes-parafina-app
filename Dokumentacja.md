# Dokumentacja Funkcjonalna i Architektoniczna: System MES Parafina
## Wersja: 1.2
## Data: 2025-10-17

### 1. Wprowadzenie i Główne Koncepcje

Niniejszy dokument opisuje logikę biznesową i architekturę systemu MES (Manufacturing Execution System) przeznaczonego do zarządzania procesem produkcji i oczyszczania parafiny. System ma na celu cyfryzację, automatyzację i śledzenie wszystkich kluczowych operacji produkcyjnych.

#### 1.1. Kluczowe Byty Systemu

System opiera się na kilku fundamentalnych obiektach, które modelują fizyczne i logiczne elementy procesu:

*   **Partia Pierwotna (Batches):** Atomowa, niezmienna porcja surowca o znanym pochodzeniu, typie i wadze. Reprezentuje fizyczną dostawę z cysterny lub transfer z wytapiarki Apollo. Jest "cegiełką" służącą do budowania mieszanin i zapewnia pełną identyfikowalność (traceability). Jej masa (`current_quantity`) jest zużywana podczas tankowania.

*   **Mieszanina (TankMix):** Centralny obiekt biznesowy w systemie. Reprezentuje dynamiczną, aktualną zawartość jednego zbiornika (reaktora lub beczki). Mieszanina jest bytem ewoluującym w trakcie procesu. Składa się z jednej lub więcej Partii Pierwotnych. Posiada własny cykl życia, historię operacji i unikalny skład procentowy.

*   **Składnik Mieszaniny (MixComponents):** Rekord łączący Mieszaninę z Partią Pierwotną. Przechowuje informację o tym, jaka masa (`quantity_in_mix`) danej partii pierwotnej znajduje się aktualnie w konkretnej mieszaninie.

*   **Operacja (OperacjeLog):** Zapis każdej intencjonalnej akcji wykonanej w systemie, która zmienia stan Mieszaniny lub Sprzętu (np. transfer, dobielanie, filtracja, zmiana statusu). Stanowi audytowalny ślad wszystkich działań.

*   **Sprzęt (Sprzet) i Topologia:** Cyfrowa reprezentacja fizycznej fabryki, włączając w to reaktory, filtry, beczki, zawory i rurociągi (segmenty). System `Pathfinder` wykorzystuje ten model do znajdowania tras dla operacji.

*   **Zasób Globalny:** Reprezentuje element infrastruktury, który może być używany tylko przez jedną operację w danym momencie (np. system sprężonego powietrza).

### 2. Opis Procesów Biznesowych i Cykl Życia Mieszaniny

#### 2.1. Pozyskiwanie Surowca i Tworzenie Mieszanin

*   **Transfer z Apollo:** Operator podaje rzeczywistą przelaną ilość surowca. System:
    1.  Tworzy nową `Partię Pierwotną` (`Batches`) z `source_type='APOLLO'`.
    2.  Porównuje rzeczywistą ilość z prognozowaną; w przypadku rozbieżności tworzy wpis w `AuditTrail`.
    3.  Natychmiast "tankuje" nową partię do wskazanego zbiornika.

*   **Rozładunek Cysterny:** Operator rejestruje dostawę, podając typ surowca, wagę i zbiornik docelowy. W jednej, atomowej operacji, system:
    1.  Tworzy nową `Partię Pierwotną` (`Batches`) z `source_type='CYS'`.
    2.  "Tankuje" tę partię do wskazanego zbiornika brudnego.

*   **Logika Tankowania:**
    *   Jeśli zbiornik docelowy jest pusty (lub jego ostatnia mieszanina jest zarchiwizowana), tworzona jest w nim nowa `Mieszanina` (`TankMix`).
    *   Jeśli w zbiorniku docelowym jest już aktywna `Mieszanina`, nowa partia jest do niej dodawana jako kolejny `Składnik Mieszaniny` (`MixComponents`), a skład procentowy jest aktualizowany.

#### 2.2. Cykl Życia Mieszaniny w Reaktorze

Mieszanina w reaktorze przechodzi przez serię zdefiniowanych stanów (`TankMix.process_status`), które dyktują, jakie akcje są dozwolone.

*   **Stany Procesu (`process_status`):**
    *   `SUROWY`: (Domyślny) Mieszanina świeżo zatankowana. Możliwe jest dodawanie kolejnych partii lub rozpoczęcie podgrzewania.
    *   `PODGRZEWANY`: W trakcie osiągania temperatury roboczej. System monitoruje temperaturę.
    *   `DOBIELONY_OCZEKUJE`: Dodano ziemię bielącą. Mieszanina czeka na rozpoczęcie cyklu filtracji.
    *   `FILTRACJA_PLACEK_KOLO`, `FILTRACJA_PRZELEW`, `FILTRACJA_KOLO`: Różne typy aktywnych cykli filtracyjnych.
    *   `OCZEKUJE_NA_OCENE`: Cykl filtracji zakończony, pobrano próbkę, system czeka na decyzję operatora.
    *   `ZATWIERDZONA`: Ocena pozytywna. Mieszanina gotowa do wypompowania do magazynu czystego.
    *   `DO_PONOWNEJ_FILTRACJI`: Ocena negatywna. Mieszanina wymaga dalszego przetwarzania.

*   **Kluczowe Operacje i Przejścia Stanów:**
    1.  **Podgrzewanie:** Operator włącza palnik (`Sprzet.stan_palnika = 'WLACZONY'`). Status mieszaniny zmienia się z `SUROWY` na `PODGRZEWANY`. Każdy cykl grzania jest logowany w `historia_podgrzewania`. Po osiągnięciu temperatury docelowej system wysyła powiadomienie `Socket.IO`, ale nie wyłącza palnika automatycznie.
    2.  **Dobielanie:** Operator wykonuje akcję dodania ziemi (`add_bleaching_earth`).
        *   **Warunki:** Temperatura reaktora musi wynosić >= 110°C, a mieszanina nie może być "wydmuchem" (`is_wydmuch_mix=False`).
        *   **Logika:** Jeśli stan to `DOBIELONY_OCZEKUJE`, system aktualizuje ostatni log operacji dobielania, sumując liczbę worków i wagę (z limitem do 160 kg na operację). W przeciwnym razie tworzy nowy log i zmienia status na `DOBIELONY_OCZEKUJE`.
    3.  **Rozpoczęcie Filtracji:** Operator uruchamia cykl filtracji.
        *   **Warunek:** System sprawdza w `OperacjeLog`, czy od ostatniego cyklu filtracji dla tej mieszaniny dodano nowe worki z ziemią. Jeśli nie, operacja jest blokowana.
        *   **Logika:** "Silnik Reguł" automatycznie wybiera typ cyklu (np. `PLACEK`, `PRZELEW`). System rezerwuje trasę w `Pathfinder` i zmienia status mieszaniny.
    4.  **Ocena Jakości:** Operator podejmuje decyzję "OK" lub "ZŁA".
        *   `OK` -> status `ZATWIERDZONA`.
        *   `ZŁA` -> status `DO_PONOWNEJ_FILTRACJI`.

#### 2.3. Dmuchanie i Zarządzanie Wydmuchem

*   Operacje `DMUCHANIE_*` wymagają wyłącznego dostępu do zasobu `SYSTEM_POWIETRZA`.
*   Produkt dmuchania ("wydmuch") jest modelowany jako nowa, specjalna `Mieszanina` (`TankMix`) z flagą `is_wydmuch_mix = True`.
*   Do mieszaniny oznaczonej jako "wydmuch" nie można dodawać ziemi bielącej.

#### 2.4. Nazwa Wyświetlana Mieszaniny

System dynamicznie generuje czytelną nazwę mieszaniny w GUI, aby ułatwić operatorom szybką identyfikację.
*   **Format:** `GŁÓWNY_SKŁAD(ID_WHITEBOARD) HISTORIA_OPERACJI (ZANIECZYSZCZENIA)`
*   **Przykład:** `T-10(A) 2x +12W 2xWYD`
    *   `T-10`: Główny składnik (`main_composition`).
    *   `(A)`: Opcjonalny, ręcznie przypisany `whiteboard_id`.
    *   `2x`: Liczba cykli filtracji (`filtration_cycles_count`).
    *   `+12W`: Suma dodanych worków ziemi (`bleaching_earth_bags_total`).
    *   `2xWYD`: Liczba cykli dmuchania (`wydmuch_cycles_count`).

### 3. Model Danych (Kluczowe Zmiany i Nowe Tabele)

*   **Tabela `TankMixes` (Rozbudowa):**
    *   `process_status`: `String(50)` - Przechowuje aktualny stan z cyklu życia (np. `SUROWY`, `PODGRZEWANY`).
    *   `main_composition`: `JSON` - Słownik głównych składników z procentami.
    *   `whiteboard_id`: `String(10)` - Krótki, ludzki identyfikator.
    *   `is_wydmuch_mix`: `Boolean` - Flaga oznaczająca, że mieszanina jest "wydmuchem".
    *   `filtration_cycles_count`, `wydmuch_cycles_count`, `bleaching_earth_bags_total`: Liczniki operacji.

*   **Tabela `Sprzet` (Rozbudowa):**
    *   `stan_palnika`: `Enum('WLACZONY', 'WYLACZONY')`.
    *   `szybkosc_grzania_c_na_minute`, `szybkosc_chlodzenia_c_na_minute`: Parametry symulacji.
    *   `filter_cake_origin_mix_id`: ID mieszaniny, z której pochodzi placek na filtrze.

*   **Tabela `OperacjeLog` (Rozbudowa):**
    *   `id_tank_mix`: Klucz obcy do `tank_mixes.id` do logowania operacji na mieszaninach.
    *   `ilosc_workow`: `Integer` do precyzyjnego zapisu liczby worków w operacji `DOBIELANIE`.

*   **Nowa Tabela `historia_podgrzewania`:**
    *   `id`, `id_sprzetu`, `id_mieszaniny`, `czas_startu`, `temp_startowa`, `czas_konca`, `temp_koncowa`, `temperatura_zewnetrzna`, `waga_wsadu`.

*   **Planowana Tabela `zgloszenia_serwisowe`:**
    *   `id`, `id_sprzetu`, `opis`, `status`, `zgloszony_przez`, `sciezka_do_zdjecia`.

### 4. Architektura i Interfejsy Użytkownika

*   **Architektura Serwisowa:** Logika biznesowa jest hermetyzowana w dedykowanych serwisach:
    *   `BatchManagementService`: Tworzenie partii i transfery.
    *   `WorkflowService`: Zarządzanie stanami procesu (ocena, filtracja).
    *   `SprzetService`: Zarządzanie fizycznym stanem sprzętu.
    *   `HeatingService`: Logowanie historii podgrzewania.
    *   `PredictionService` (Planowany): Predykcje AI.
    *   `ServiceRequestService` (Planowany): Zgłoszenia serwisowe.

*   **Socket.IO:** Jest kluczowym elementem do realizacji powiadomień w czasie rzeczywistym i aktualizacji dashboardów bez potrzeby odświeżania strony.

*   **GUI/UX:** Interfejs musi być zorientowany na zadania. Piktogramy i dynamicznie generowane nazwy (`display_name`) mają na celu maksymalne uproszczenie i przyspieszenie pracy operatora.