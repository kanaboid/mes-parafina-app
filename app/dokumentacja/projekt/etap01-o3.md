────────────────────────────────────────
SYSTEM MES – ETAP 1  (Dostawa → Zbiornik brudny)  
Prompt referencyjny do dalszego kodowania
────────────────────────────────────────

1. KLUCZOWE OBIEKTY SPRZĘTOWE  
   • Bxxb – zbiorniki brudne, zero-pad 2 cyfry (B01b…B10b)  
   • Rxx  – reaktory (R01…R09)  
   • Bxxc – zbiorniki czyste, zero-pad 2 cyfry (B01c…B12c)  

2. FORMATY ID PARTII  
   a) Surowiec wejściowy (dostawa / wytop)  
      S-[ŹRÓDŁO][NR_ŹRÓDŁA]-[TYP]-RRMMDD-[SEQ]  
      – Cysterna T-10   S-CYS-T10-231030-01  
      – Cysterna 19    S-CYS-19-231030-02  
      – Apollo 2, wytop 44 S-AP02-44-231030-01  

   b) Kontener MIX w zbiorniku brudnym  
      B-[ID_ZB]-RRMMDD-[SEQ]  (przykł. B-B08b-231030-01)  

   c) Sub-partia (odzwierciedla konkretną dostawę wlatującą do MIX)  
      tworzy się automatycznie:  
      SB-<autoUUID> – ukryta dla operatora, widoczna w Composition.  

   d) Reaktor (pierwszy cykl)  
      P-[ID_R]-RRMMDD-[SEQ]   (P-R01-231030-01)  

   e) Kontener czysty  
      C-[ID_ZB]-RRMMDD-[SEQ]   (C-B05c-231030-01)  

3. ZDARZENIA I GENERATORY  
   • ROZTANKOWANIE  
     input: Dostawa_ID, Zbiornik_Bxxb, kg, „zbiornik pusty?”  
     – jeśli pusty → zamyka stary MIX, zakłada nowy B-Bxxb-…-01  
     – zawsze dopisuje kg do MIX + sub-partię w Composition.  

   • TANKOWANIE_REAKTORA / PRZETANKOWANIE  
     input: Źródło MIX, Cel (Rxx lub Byyb), kg  
     – algorytm Weighted Average odejmuje kg proporcjonalnie z Composition.  
     – zamyka MIX gdy qty==0 kg (±1 kg).  

   • KOREKTA_MASY  
     uprawniony user zmienia kg transferu → rollback + ponowne WA, wpis audit.  

4. TABELARYCZNA STRUKTURA (skrót)  
   BATCH(id, type, equipment_id, start_ts, qty_kg, status)  
   TRANSFER(id, src_batch_id, tgt_batch_id, qty_kg, ts, user)  
   COMPOSITION(mix_batch_id, source_batch_id, qty_kg)  
   AUDIT(entity, entity_id, field, old_val, new_val, user, ts)  

5. ALGORYTM WA (pobranie kg_p):  
   for each SB_i in COMPOSITION:  
      udział_i = SB_i.qty / MIX.qty  
      redukcja_i = udział_i * kg_p  
      SB_i.qty  -= redukcja_i  
   MIX.qty -= kg_p ; auto-close if 0 kg.  

6. NAZWY STAŁE VS. SORTOWANIE  
   • Zero-padding (B01b, R02…) gwarantuje poprawne ORDER BY.  
   • Nazwa partii jest immutable; zmiany mas nie modyfikują ID.  

7. 5-MINUTOWY RAPORT TRACEABILITY  
   • genealogię wyznacza rekursywne łączenie TRANSFER + COMPOSITION.  
   • procentowy udział dostaw w każdej partii kalkulowany on-the-fly z COMPOSITION.  

Przykład pełnego przebiegu (30-10-2023):  
1) S-CYS-T10-231030-01 8 000 kg → ROZTANKOWANIE → B-B08b-231030-01 (MIX 8 000)  
2) S-CYS-19-231030-02 2 000 kg → ROZTANKOWANIE → B-B08b-231030-01 (MIX 10 000)  
3) MIX → TANKOWANIE R01 5 800 kg → P-R01-231030-01  
4) MIX → PRZETANKOWANIE 4 200 kg → B-B09b-231030-01 (nowy MIX)  
5) MIX(B08b) qty==0 kg → status=CLOSED.  

