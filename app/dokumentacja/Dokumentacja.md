Dokumentacja Funkcjonalna i Architektoniczna: System MES Parafina
Wersja: 1.0
Data: 2025-08-16
1. Wprowadzenie i Główne Koncepcje
Niniejszy dokument opisuje logikę biznesową i architekturę systemu MES (Manufacturing Execution System) przeznaczonego do zarządzania procesem produkcji i oczyszczania parafiny. System ma na celu cyfryzację, automatyzację i śledzenie wszystkich kluczowych operacji produkcyjnych.
1.1. Kluczowe Byty Systemu
System opiera się na kilku fundamentalnych obiektach, które modelują fizyczne i logiczne elementy procesu:
Partia Pierwotna (Batch): Niezmienny, atomowy "wsad" surowca o znanym pochodzeniu, typie i wadze. Reprezentuje fizyczną dostawę z cysterny lub pojedynczy, kompletny transfer z wytapiarki Apollo. Partia Pierwotna jest tylko "cegiełką" i służy do śledzenia pochodzenia (traceability).
Mieszanina (TankMix): Główny obiekt biznesowy w systemie. Reprezentuje całą, aktualną zawartość jednego zbiornika (reaktora lub beczki). Mieszanina jest dynamicznym bytem, który ewoluuje w trakcie procesu. Składa się z jednej lub więcej Partii Pierwotnych. Posiada własny cykl życia, historię operacji i unikalny skład procentowy.
Operacja (OperacjeLog): Zapis każdej intencjonalnej akcji wykonanej w systemie, która zmienia stan Mieszaniny lub Sprzętu (np. transfer, dobielanie, filtracja, dmuchanie).
Sprzęt (Sprzet) i Topologia: Cyfrowa reprezentacja fizycznej fabryki, włączając w to reaktory, filtry, beczki, zawory i rurociągi (segmenty). System PathFinder wykorzystuje ten model do znajdowania tras dla operacji.
Zasób Globalny: Reprezentuje element infrastruktury, który może być używany tylko przez jedną operację w danym momencie (np. system sprężonego powietrza). Modelowany jest jako "wirtualny" rekord w tabeli Sprzet.
2. Opis Procesów Biznesowych i Cyklu Życia Mieszaniny
2.1. Pozyskiwanie Surowca i Tworzenie Partii Pierwotnych
Transfer z Apollo: Operator podaje rzeczywistą, przelaną ilość surowca. System porównuje ją z prognozą, loguje ewentualną rozbieżność w AuditTrail i tworzy nową Batch o zadanym typie i wadze.
Rozładunek Cysterny: Operator rejestruje dostawę, podając typ surowca, wagę i dane dostawy. System tworzy nową Batch.
Magazynowanie w Beczkach Brudnych: Stworzona Batch jest "tankowana" (logicznie) do wybranej beczki brudnej za pomocą BatchManagementService.tank_into_dirty_tank.
Jeśli beczka jest pusta, tworzona jest w niej nowa TankMix.
Jeśli w beczce jest już TankMix, nowa Batch jest dodawana jako kolejny składnik, a skład procentowy Mieszaniny jest aktualizowany.
Dozwolone jest mieszanie różnych typów surowców. System musi ostrzegać operatora przed pierwszym zmieszaniem różnych typów w jednym zbiorniku.
2.2. Cykl Życia Mieszaniny w Reaktorze
Mieszanina w reaktorze (TankMix) przechodzi przez serię zdefiniowanych stanów, które dyktują, jakie akcje są dozwolone.
Stany Procesu (TankMix.process_status):
SUROWY: (Domyślny) Mieszanina świeżo zatankowana z magazynu brudnego.
PODGRZEWANY: W trakcie osiągania temperatury roboczej.
DOBIELONY_OCZEKUJE: Dodano ziemię bielącą, mieszanina czeka na rozpoczęcie cyklu filtracji typu "Placek".
FILTRACJA_PLACEK_KOŁO: Cyrkulacja w obiegu zamkniętym w celu budowy placka (30 min).
FILTRACJA_PRZELEW: Transfer przez filtr do innego, pustego reaktora.
FILTRACJA_KOŁO: Cyrkulacja w obiegu zamkniętym po przelewie (15 min).
OCZEKUJE_NA_OCENE: Zakończono cykl, pobrano próbkę, system czeka na decyzję operatora (10 min na stygnięcie).
ZATWIERDZONA: Ocena pozytywna, Mieszanina gotowa do wysłania do magazynu czystego.
ZATWIERDZONA_OCZEKUJE_NA_TRANSFER: Jw., ale rurociąg jest zajęty.
DO_PONOWNEJ_FILTRACJI: Ocena negatywna, Mieszanina wymaga dalszego przetwarzania.
2.3. Kluczowe Operacje Procesowe
2.3.1. Zarządzanie Temperaturą i Palnikiem:
Każdy reaktor posiada palnik (Sprzet.stan_palnika), którym operator steruje manualnie.
System symuluje zmianę temperatury w zależności od stanu palnika, używając szybkosc_grzania_c_na_minute i szybkosc_chlodzenia_c_na_minute.
System aktywnie monitoruje temperaturę i wysyła powiadomienia (przez Socket.IO) o osiągnięciu celu oraz monity z sugestiami (np. "Czy włączyć palnik po transferze?").
Wszystkie cykle grzania są logowane w historia_podgrzewania w celu przyszłej analizy i treningu modelu predykcyjnego AI.
2.3.2. Dobielanie (Dodanie Ziemi Bielącej):
Reguła Biznesowa: Operacja jest zablokowana, jeśli temperatura_aktualna < 110°C. Walidacja musi odbywać się po stronie GUI (nieaktywny przycisk) i serwera (logika w serwisie).
Operacja jest logowana w OperacjeLog, a licznik TankMix.bleaching_earth_bags_total jest inkrementowany.
Status Mieszaniny zmienia się na DOBIELONY_OCZEKUJE.
2.3.3. Proces Filtracji i Zarządzanie Filtrem:
Automatyzacja Wyboru Cyklu: System, na podstawie statusu DOBIELONY_OCZEKUJE, automatycznie wie, czy rozpocząć Cykl 1 (Placek) czy Cykl 2 (Czysta Filtracja).
Stan Filtra: Filtr (Sprzet) posiada status filter_cake_status (CZYSTY lub PLACEK_GOTOWY) oraz filter_cake_origin_mix_id, które śledzi, z której Mieszaniny pochodzi placek.
Silnik Reguł (Ostrzeżenia): Przed rozpoczęciem filtracji system waliduje zgodność typu surowca Mieszaniny z typem surowca placka na filtrze. W przypadku ryzyka niedozwolonej kontaminacji (na podstawie przeznaczenia partii), system wyświetla ostrzeżenie i wymaga potwierdzenia od operatora.
Śledzenie Kontaminacji: W przypadku dozwolonego mieszania na filtrze, system symuluje kontaminację, tworząc wirtualną Batch o typie RESZTKI_FILTRACYJNE i dodając ją do Mieszaniny docelowej.
2.3.4. Ocena Jakości i Przepływ Pracy (WorkflowService):
Po cyklu filtracyjnym Mieszanina przechodzi w stan OCZEKUJE_NA_OCENE.
Decyzja operatora ("OK" / "ZŁA") jest zapisywana w ProbkiOcena i działa jak wyzwalacz:
Wynik "OK": Mieszanina -> ZATWIERDZONA. System sprawdza dostępność rurociągu i automatycznie proponuje operację TRANSFER_DO_MAGAZYNU lub przechodzi w stan ZATWIERDZONA_OCZEKUJE_NA_TRANSFER.
Wynik "ZŁA": Mieszanina -> DO_PONOWNEJ_FILTRACJI. System automatycznie inicjuje operację DMUCHANIE_PO_OCENIE.
2.3.5. Dmuchanie i Zarządzanie Wydmuchem:
Operacje DMUCHANIE_* i PRZEDMUCH_* wymagają wyłącznego dostępu do zasobu SYSTEM_POWIETRZA. System blokuje możliwość uruchomienia drugiego dmuchania w tym samym czasie.
"Wydmuch" jest modelowany jako specjalny rodzaj Mieszaniny (TankMix), oznaczony flagą is_wydmuch_mix = True.
Do Mieszaniny wydmuchowej można dodawać kolejne wydmuchy lub tankować świeży surowiec. Dodanie świeżego surowca nie zmienia flagi is_wydmuch_mix.
Flaga is_wydmuch_mix jest resetowana do False dopiero po pierwszym udanym cyklu filtracyjnym tej Mieszaniny.
Reaktor z Mieszaniną wydmuchową nie może być celem dla standardowych transferów.
2.4. Nazwa Wyświetlana Mieszaniny
System musi przechowywać komponenty nazwy w ustrukturyzowanych polach w TankMixes i dynamicznie generować czytelną reprezentację w GUI.
Format: GŁÓWNY_SKŁAD (ID_WHITEBOARD) HISTORIA_OPERACJI (ZANIECZYSZCZENIA)
GŁÓWNY_SKŁAD: Generowany z main_composition. Pokazuje tylko składniki > 1%, np. MIX(T10[78%], 19[18%]).
HISTORIA_OPERACJI: Na podstawie liczników, np. 4x 2xWYD.
ZANIECZYSZCZENIA: Na podstawie wydmuch_percentage i filter_remains_percentage, wyświetlane w sposób mniej eksponowany, np. (W[3%], F[1%]).
3. Model Danych (Kluczowe Zmiany i Nowe Tabele)
Tabela TankMixes (Rozbudowa):
process_status: String(50)
main_composition: JSON
wydmuch_percentage: DECIMAL(5, 2)
filter_remains_percentage: DECIMAL(5, 2)
filtration_cycles_count: Integer
wydmuch_cycles_count: Integer
bleaching_earth_bags_total: Integer
whiteboard_id: String(10)
is_wydmuch_mix: Boolean
Tabela Sprzet (Rozbudowa):
szybkosc_grzania_c_na_minute: DECIMAL(5,2)
szybkosc_chlodzenia_c_na_minute: DECIMAL(5,2)
stan_palnika: ENUM('WLACZONY', 'WYLACZONY')
filter_cake_status: String(50)
filter_cake_origin_mix_id: Integer (ForeignKey do TankMixes.id)
Nowa Tabela historia_podgrzewania:
id, id_sprzetu, id_mieszaniny, czas_startu, temp_startowa, czas_konca, temp_koncowa, temperatura_zewnetrzna, waga_wsadu
4. Architektura i Interfejs Użytkownika
Serwisy: Należy rozważyć stworzenie dedykowanych serwisów WorkflowService i OperationsService do obsługi logiki przepływu pracy i zarządzania operacjami.
Socket.IO: Jest kluczowym elementem do realizacji powiadomień w czasie rzeczywistym i aktualizacji dashboardów.
GUI/UX: Interfejs musi być zorientowany na zadania. Należy zaprojektować dedykowane piktogramy dla każdego stanu, procesu i typu sprzętu w celu poprawy czytelności.