Oczywiście, oto lista wszystkich endpointów z pliku `app/routes.py` wraz z krótkimi opisami ich funkcjonalności. Lista została podzielona na kategorie dla lepszej czytelności.

---

### I. Strony HTML (Frontend)
Endpointy, które serwują interfejs użytkownika w postaci stron HTML.

1.  **GET /**
    *   **Opis:** Serwuje główną stronę aplikacji (`index.html`), która prawdopodobnie jest panelem startowym lub pulpitem nawigacyjnym.

2.  **GET /alarms**
    *   **Opis:** Wyświetla stronę (`alarms.html`) z historią wszystkich alarmów zarejestrowanych w systemie.

3.  **GET /operacje**
    *   **Opis:** Wyświetla stronę (`operacje.html`) przeznaczoną do zarządzania i inicjowania różnych operacji, takich jak tankowanie czy transfery.

4.  **GET /filtry**
    *   **Opis:** Wyświetla dedykowaną stronę (`filtry.html`) do monitorowania stanu i operacji na filtrach.

5.  **GET /cykle-monitor**
    *   **Opis:** Serwuje stronę (`cykle_monitor.html`) do monitorowania przebiegu cykli filtracyjnych dla różnych partii surowca.

6.  **GET /aktywne-partie**
    *   **Opis:** Wyświetla stronę (`aktywne_partie.html`) do zarządzania i przeglądania wszystkich aktywnych partii w procesie produkcyjnym.

### II. API - Sprzęt, Topologia i Zasoby
Endpointy dostarczające dane o stanie systemu, jego komponentach i dostępnych zasobach.

1.  **GET /api/sprzet**
    *   **Opis:** Zwraca listę całego sprzętu (reaktory, filtry itp.) wraz ze szczegółowymi informacjami o partii surowca, która aktualnie się w nim znajduje (jeśli jakaś jest).

2.  **GET /api/zawory**
    *   **Opis:** Zwraca listę wszystkich zaworów w systemie wraz z ich aktualnym stanem ('OTWARTY' lub 'ZAMKNIETY').

3.  **GET /api/punkty_startowe**
    *   **Opis:** Zwraca listę wszystkich portów wyjściowych (typu 'OUT'), które mogą być punktem startowym dla operacji transferu.

4.  **GET /api/punkty_docelowe**
    *   **Opis:** Zwraca listę wszystkich portów wejściowych (typu 'IN'), które mogą być punktem docelowym dla operacji transferu.

5.  **GET /api/sprzet/filtry**
    *   **Opis:** Zwraca uproszczoną listę dostępnych filtrów, zawierającą ich ID i nazwę.

6.  **GET /api/topologia**
    *   **Opis:** Zwraca pełną topologię rurociągów w formie listy segmentów. Każdy segment zawiera informacje o punktach połączeń, przypisanym zaworze oraz o tym, czy jest aktualnie zajęty przez jakąś operację. Służy do wizualizacji sieci.

7.  **GET /api/typy-surowca**
    *   **Opis:** Zwraca listę wszystkich zdefiniowanych typów surowca, przydatną np. w formularzach.

8.  **GET /api/sprzet/beczki-brudne**
    *   **Opis:** Zwraca listę beczek z brudnym surowcem, które są dostępne do rozpoczęcia procesu tankowania.

9.  **GET /api/sprzet/reaktory-puste**
    *   **Opis:** Zwraca listę reaktorów, które są aktualnie puste i gotowe na przyjęcie nowej partii surowca.

10. **GET /api/sprzet/reaktory-z-surowcem**
    *   **Opis:** Zwraca listę reaktorów, które zawierają surowiec i mogą być źródłem dla operacji transferu.

### III. API - Główne Operacje i Procesy
Endpointy do inicjowania, modyfikowania i kończenia kluczowych operacji technologicznych.

1.  **POST /api/operacje/tankowanie**
    *   **Opis:** Inicjuje proces tankowania. Tworzy nową partię surowca w systemie na podstawie danych wejściowych (porty, waga, typ surowca), aktualizuje stan reaktora i zapisuje operację w logach.

2.  **POST /api/operacje/rozpocznij_trase**
    *   **Opis:** Rozpoczyna operację transferu surowca. Na podstawie punktu startowego, docelowego i otwartych zaworów znajduje trasę, sprawdza konflikty, blokuje używane segmenty rurociągów i tworzy w logu wpis o "aktywnej" operacji.

3.  **POST /api/operacje/zakoncz**
    *   **Opis:** Kończy aktywną operację transferu o podanym ID. Zmienia jej status na "zakończona", zamyka używane zawory i, co najważniejsze, aktualizuje lokalizację partii surowca, przenosząc ją do sprzętu docelowego i zmieniając stany obu urządzeń (źródłowego i docelowego).

4.  **POST /api/zawory/zmien_stan**
    *   **Opis:** Umożliwia ręczną zmianę stanu pojedynczego zaworu (otwarcie lub zamknięcie) na podstawie jego ID.

5.  **POST /api/trasy/sugeruj**
    *   **Opis:** Znajduje i zwraca najkrótszą możliwą trasę między dwoma punktami (opcjonalnie przez punkt pośredni, np. filtr). **Ignoruje aktualny stan zaworów**, aby pokazać operatorowi, które zawory *powinien* otworzyć, aby zrealizować transfer. Nie wykonuje żadnej operacji.

6.  **POST /api/operacje/dobielanie**
    *   **Opis:** Rejestruje operację dobielania (dodawania ziemi okrzemkowej). Aktualizuje wagę istniejącej partii i dodaje jej status "Dobielony", a także zapisuje zdarzenie w logu operacji.

7.  **POST /api/operacje/tankowanie-brudnego**
    *   **Opis:** Specjalistyczny endpoint do tankowania brudnego surowca z beczki do reaktora. Tworzy nową partię, aktualizuje stany sprzętu i zapisuje początkową temperaturę surowca.

8.  **POST /api/operacje/transfer-reaktorow**
    *   **Opis:** Kompleksowy endpoint do zarządzania transferem surowca między reaktorami, z opcjonalnym użyciem filtra. Posiada tryb "podglądu" (symulacja trasy) oraz tryb wykonawczy, który rozpoczyna rzeczywistą operację, blokując zasoby.

### IV. API - Zarządzanie Partiami i Cyklami Filtracyjnymi
Endpointy dedykowane do śledzenia i zarządzania cyklem życia partii surowca.

1.  **GET /api/partie/aktywne**
    *   **Opis:** Zwraca bardzo szczegółową listę wszystkich aktywnych partii w systemie, wzbogaconą o ich lokalizację, statusy, wiek, informacje o aktywnej operacji oraz historię ostatnich zdarzeń.

2.  **GET /api/partie/szczegoly/<int:partia_id>**
    *   **Opis:** Pobiera wszystkie dostępne informacje o jednej, konkretnej partii, w tym jej pełną historię operacji, statusy i historię cykli filtracyjnych.

3.  **POST /api/partie/aktualizuj-status**
    *   **Opis:** Pozwala na ręczną zmianę głównego statusu partii (np. z 'Gotowy do wysłania' na 'W magazynie czystym').

4.  **GET /api/cykle-filtracyjne/<int:id_partii>**
    *   **Opis:** Pobiera historię wszystkich cykli filtracyjnych (budowanie placka, filtrowanie w koło, przedmuchiwanie) wykonanych dla konkretnej partii surowca.

5.  **POST /api/cykle/rozpocznij**
    *   **Opis:** Rozpoczyna nowy cykl filtracyjny dla danej partii, aktualizując jej status i tworząc odpowiedni wpis w tabeli cykli.

6.  **POST /api/cykle/zakoncz**
    *   **Opis:** Kończy bieżący cykl filtracyjny partii, zapisuje jego wynik i przygotowuje partię do następnego etapu procesu.

### V. API - Monitoring, Alarmy i Pomiary
Endpointy związane z odczytem danych z sensorów i zarządzaniem alarmami.

1.  **GET /api/operacje/aktywne**
    *   **Opis:** Zwraca listę wszystkich operacji, które mają aktualnie status "aktywna".

2.  **GET /api/filtry/status** (oraz nowszy **GET /api/filtry/szczegolowy-status**)
    *   **Opis:** Zwraca szczegółowy status filtrów. Oprócz podstawowych danych (stan, nazwa), informuje o aktywnej operacji, przetwarzanej partii oraz o partiach oczekujących w kolejce na użycie filtra.

3.  **GET /api/alarmy/aktywne**
    *   **Opis:** Zwraca listę wszystkich alarmów, które mają status "AKTYWNY" i wymagają uwagi operatora.

4.  **GET /api/pomiary/historia**
    *   **Opis:** Pobiera historię pomiarów (np. temperatury, ciśnienia) z czujników z ostatnich 24 godzin.

5.  **POST /api/alarmy/potwierdz**
    *   **Opis:** Umożliwia operatorowi "potwierdzenie" (skwitowanie) aktywnego alarmu, zmieniając jego status na "POTWIERDZONY".

6.  **POST /api/sprzet/<int:sprzet_id>/temperatura**
    *   **Opis:** Pozwala ustawić docelową temperaturę dla danego sprzętu (np. reaktora), która będzie używana przez system kontroli do sterowania np. palnikiem.

### VI. API - Endpointy Testowe
Endpointy służące do deweloperskich testów funkcjonalności.

1.  **POST /api/test/sensors**
    *   **Opis:** Endpoint testowy, który wymusza natychmiastowy odczyt wszystkich czujników przez `SensorService`.

2.  **POST /api/test/alarm**
    *   **Opis:** Endpoint testowy, który pozwala na sztuczne wygenerowanie alarmu (temperatury lub ciśnienia) dla wybranego sprzętu w celach testowania systemu alarmowego.