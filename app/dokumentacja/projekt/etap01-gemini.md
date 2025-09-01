Master prompt do etapu 1:

### **Dokumentacja Projektowa Systemu MES: Rozdział 1 - Śledzenie Surowca w Strefie Magazynowej Brudnej**

#### **1.1. Cel Etapu**
Celem tego etapu jest zaimplementowanie pełnej identyfikowalności (traceability) surowca od momentu jego fizycznego przyjęcia (dostawa w cysternie lub wytop w wytapiarce) do momentu pobrania go ze zbiornika brudnego w celu przetworzenia w reaktorze. System musi precyzyjnie śledzić pochodzenie, lokalizację, ilość oraz skład procentowy mieszanin surowców.

#### **1.2. Model Danych i Encje Systemu**

**1.2.1. Zasoby Fizyczne (Equipment)**
Wszystkie zasoby fizyczne są jednoznacznie identyfikowane. Obowiązuje konwencja nazewnicza z zerami wiodącymi (padding) w celu zapewnienia poprawnego sortowania alfanumerycznego.
*   **Zbiorniki Brudne:** `B01b, B02b, ..., B12b`
*   **Wytapiarki:** `Apollo 01, Apollo 02` (lub `AP01`, `AP02` w kodach systemowych)
*   **Reaktory:** `R01, R02, ..., R09`

**1.2.2. Partia Surowca (Raw Material Batch)**
Jest to atomowa, podstawowa jednostka śledzona, reprezentująca konkretną, jednorodną dostawę surowca.
*   **Format Nazwy:** `S-[ZRODLO][NR_ZRODLA]-[TYP_SUROWCA]-RRMMDD-[NR_DZIENNY]`
*   **Przykłady:**
    *   Dostawa w cysternie: `S-CYS-T10-231030-01`
    *   Wytop w Apollo 02: `S-AP02-44-231030-01`
*   **Kluczowe Atrybuty (w tabeli `Batches`):** `BatchID` (Primary Key), `MaterialType`, `Source`, `CreationDate`, `InitialQuantity`, `CurrentQuantity`.

**1.2.3. Mieszanina w Zbiorniku Brudnym (Dirty Tank Mix)**
Jest to logiczny kontener reprezentujący jednorodną, fizyczną zawartość jednego zbiornika brudnego w danym czasie.
*   **Format Nazwy:** `B-[ID_ZBIORNIKA]-RRMMDD-[NR]`
*   **Przykład:** `B-B08b-231030-01`
*   **Relacja:** Obiekt `Mix` ma relację "jeden do wielu" z obiektami `Raw Material Batch`. Sam `Mix` nie przechowuje masy; jego masa i skład są dynamicznie wyliczane na podstawie sumy `CurrentQuantity` wszystkich jego składników.

#### **1.3. Kluczowe Procesy i Logika Systemu**

**1.3.1. Przyjęcie Surowca i Tworzenie Partii**
Każda operacja przyjęcia (z `CYS` lub `AP*`) generuje nowy, unikalny rekord `Raw Material Batch` z nadanym automatycznie numerem ID.

**1.3.2. Tankowanie do Zbiornika Brudnego**
Transfer `Raw Material Batch` do zbiornika brudnego (`B*b`) uruchamia następującą logikę:
1.  **Sprawdź stan zbiornika:** System weryfikuje, czy dla danego zbiornika istnieje aktywny obiekt `Dirty Tank Mix`.
2.  **Scenariusz A (Zbiornik pusty):** Jeśli nie ma aktywnego `Mix`, system **tworzy nowy** obiekt `Dirty Tank Mix`, nadając mu numer zgodnie z konwencją (np. `B-B08b-231030-01`). Następnie przypisuje transferowaną `Raw Material Batch` jako jego pierwszy składnik.
3.  **Scenariusz B (Zbiornik zajęty):** Jeśli aktywny `Mix` już istnieje, system **nie tworzy nowego**. Po prostu dodaje transferowaną `Raw Material Batch` jako kolejny składnik do **istniejącego** `Mix`.
4.  Po każdej operacji system musi przeliczyć skład procentowy `Mix`.

**1.3.3. Rozchód ze Zbiornika Brudnego**
Wszystkie operacje pobrania materiału (tankowanie reaktora, przetankowanie) są realizowane **zawsze z obiektu `Dirty Tank Mix`**. System musi zaimplementować metodę rozchodu **Średniej Ważonej (Weighted Average)**.
*   **Algorytm:**
    1.  Określ procentowy udział każdej `Raw Material Batch` w całkowitej masie `Mix`.
    2.  Pobraną masę rozdziel proporcjonalnie na każdą `Raw Material Batch`.
    3.  Zaktualizuj (zmniejsz) pole `CurrentQuantity` dla każdego rekordu `Raw Material Batch` będącego składnikiem `Mix`.

#### **1.4. Fundamentalne Zasady Systemowe**

*   **Edycja i Integralność Danych:** System musi pozwalać na ręczną korektę zarejestrowanej masy po fakcie. Każda taka operacja musi być niemożliwa do usunięcia i musi generować wpis w dzienniku zdarzeń (`Audit Trail`) zawierający co najmniej: `Timestamp`, `UserID`, `OperationID`, `OldValue`, `NewValue`, `Reason`. Korekta musi wyzwalać automatyczną rekalkulację wszystkich powiązanych bilansów masowych i procentowych.
*   **Unikalność Nazw:** System musi programowo zapewniać unikalność wszystkich generowanych identyfikatorów partii (`S-*`, `B-*`, itd.).

#### **1.5. Scenariusz Użycia (Use Case)**

1.  **Przyjęcie #1:** `10,000 kg` surowca `T10` z cysterny. System tworzy partię `S-CYS-T10-231030-01`.
2.  **Tankowanie #1:** Partia `...-01` jest tankowana do pustego zbiornika `B01b`. System tworzy `B-B01b-231030-01`, którego skład to 100% partii `...-01`.
3.  **Przyjęcie #2:** `5,000 kg` surowca `44` z `AP01`. System tworzy partię `S-AP01-44-231030-01`.
4.  **Tankowanie #2:** Partia `...-01` z `AP01` jest tankowana do zbiornika `B01b`. Skład `B-B01b-231030-01` zostaje zaktualizowany:
    *   Całkowita masa: 15,000 kg
    *   Składniki: `S-CYS-T10-231030-01` (10,000 kg, 66.67%) i `S-AP01-44-231030-01` (5,000 kg, 33.33%).
5.  **Tankowanie Reaktora:** Operator pobiera `3,000 kg` z `B01b` do reaktora `R01`.
6.  **Logika Systemu:** System oblicza:
    *   Pobrano z `S-CYS-T10...`: 3000 * 66.67% = 2000 kg. Nowy `CurrentQuantity` = 8000 kg.
    *   Pobrano z `S-AP01-44...`: 3000 * 33.33% = 1000 kg. Nowy `CurrentQuantity` = 4000 kg.
    *   Tworzona jest nowa **Szarża Produkcyjna**, której genealogia wskazuje na pobranie 2000 kg z jednej partii i 1000 kg z drugiej.

---
