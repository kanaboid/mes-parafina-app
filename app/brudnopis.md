

1. **Tabela typów surowca** - wystarczy kolumna opis

2. **Temperatura** - początkowa partii

3. **Walidacja wagi** - nie

4. **Status beczki** - nie, pozniej bedzie po prostu odejmowana waga, na razie ignoruj walidacje beczki

5. **Nawigacja** - w przyszlosci trafia tu tez inne operacje.




### 3. **Formularz tankowania brudnego surowca**
Pola:
- **Źródło** - select z beczek B1b-B10b (filtr `typ_sprzetu = 'beczka_brudna'`)
- **Reaktor docelowy** - select z reaktorów R1-R5 w stanie "Pusty" (filtr `typ_sprzetu = 'reaktor'`)
- **Waga** - input number (max 9000 kg)
- **Typ surowca** - select z nowej tabeli `typy_surowca`
- **Temperatura surowca** - input number (°C)

