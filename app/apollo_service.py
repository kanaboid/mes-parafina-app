# app/apollo_service.py

from datetime import datetime, timedelta, timezone
from .db import get_db_connection
import mysql.connector

class ApolloService:
    # Zakładamy stałą szybkość wytapiania w kg na godzinę
    SZYBKOSC_WYTAPIANIA_KG_H = 1000.0

    @staticmethod
    def rozpocznij_sesje_apollo(id_sprzetu, typ_surowca, waga_kg, operator=None):
        """Rozpoczyna nową sesję wytapiania i tworzy partię surowca w Apollo."""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Sprawdź, czy nie ma już aktywnej sesji
            cursor.execute("""
                SELECT id FROM apollo_sesje 
                WHERE id_sprzetu = %s AND status_sesji = 'aktywna'
            """, (id_sprzetu,))
            if cursor.fetchone():
                raise ValueError(f"Apollo o ID {id_sprzetu} ma już aktywną sesję.")

            # Transakcja jest rozpoczynana automatycznie przez pierwsze zapytanie
            # przy autocommit=False, więc nie ma potrzeby wywoływać start_transaction()
            
            # 1. Stwórz nową sesję
            czas_startu = datetime.now()
            cursor.execute("""
                INSERT INTO apollo_sesje 
                (id_sprzetu, typ_surowca, czas_rozpoczecia, rozpoczeta_przez, status_sesji) 
                VALUES (%s, %s, %s, %s, 'aktywna')
            """, (id_sprzetu, typ_surowca, czas_startu, operator))
            id_sesji = cursor.lastrowid
            
            # 2. Dodaj pierwsze zdarzenie - załadunek początkowy
            cursor.execute("""
                INSERT INTO apollo_tracking
                (id_sesji, typ_zdarzenia, waga_kg, czas_zdarzenia, operator)
                VALUES (%s, 'DODANIE_SUROWCA', %s, %s, %s)
            """, (id_sesji, waga_kg, czas_startu, operator))
            
            # 3. Stwórz nową partię surowca dla Apollo
            teraz = datetime.now()
            unikalny_kod_partii = f"AP{id_sprzetu}-{teraz.strftime('%Y%m%d-%H%M%S')}"
            nazwa_partii = f"Partia w Apollo {id_sprzetu} ({typ_surowca})"
            
            cursor.execute("""
                INSERT INTO partie_surowca
                (unikalny_kod, nazwa_partii, typ_surowca, waga_poczatkowa_kg, waga_aktualna_kg, id_sprzetu, zrodlo_pochodzenia, status_partii, typ_transformacji)
                VALUES (%s, %s, %s, %s, %s, %s, 'apollo', 'Surowy w reaktorze', 'NOWA')
            """, (unikalny_kod_partii, nazwa_partii, typ_surowca, waga_kg, waga_kg, id_sprzetu))

            conn.commit()
            return id_sesji
            
        except mysql.connector.Error as err:
            conn.rollback()
            raise Exception(f"Błąd bazy danych przy rozpoczynaniu sesji: {err}")
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def dodaj_surowiec_do_apollo(id_sprzetu, waga_kg, operator=None):
        """Dodaje stały surowiec do aktywnej sesji i aktualizuje wagę partii w Apollo."""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Znajdź aktywną sesję
            cursor.execute("""
                SELECT id FROM apollo_sesje 
                WHERE id_sprzetu = %s AND status_sesji = 'aktywna'
            """, (id_sprzetu,))
            sesja = cursor.fetchone()
            if not sesja:
                raise ValueError(f"Apollo o ID {id_sprzetu} nie ma aktywnej sesji.")
            
            id_sesji = sesja['id']
            
            # Dodaj zdarzenie
            cursor.execute("""
                INSERT INTO apollo_tracking
                (id_sesji, typ_zdarzenia, waga_kg, czas_zdarzenia, operator)
                VALUES (%s, 'DODANIE_SUROWCA', %s, %s, %s)
            """, (id_sesji, waga_kg, datetime.now(), operator))
            
            # Zaktualizuj wagę partii w Apollo
            cursor.execute("""
                UPDATE partie_surowca
                SET waga_aktualna_kg = waga_aktualna_kg + %s
                WHERE id_sprzetu = %s
            """, (waga_kg, id_sprzetu))
            
            if cursor.rowcount == 0:
                # Jeśli z jakiegoś powodu partia nie istnieje, stwórz ją
                # (zabezpieczenie dla starszych danych lub nieprzewidzianych sytuacji)
                cursor.execute("SELECT typ_surowca FROM apollo_sesje WHERE id = %s", (id_sesji,))
                sesja_info = cursor.fetchone()
                typ_surowca = sesja_info['typ_surowca'] if sesja_info else 'Nieznany'

                teraz = datetime.now()
                unikalny_kod_partii = f"AP{id_sprzetu}-{teraz.strftime('%Y%m%d-%H%M%S')}-AUTOCREATED"
                nazwa_partii = f"Partia w Apollo {id_sprzetu} ({typ_surowca})"
                
                cursor.execute("""
                    INSERT INTO partie_surowca
                    (unikalny_kod, nazwa_partii, typ_surowca, waga_poczatkowa_kg, waga_aktualna_kg, id_sprzetu, zrodlo_pochodzenia, status_partii, typ_transformacji)
                    VALUES (%s, %s, %s, %s, %s, %s, 'apollo', 'Surowy w reaktorze', 'NOWA')
                """, (unikalny_kod_partii, nazwa_partii, typ_surowca, waga_kg, waga_kg, id_sprzetu))

            conn.commit()
            
        except mysql.connector.Error as err:
            conn.rollback()
            raise Exception(f"Błąd bazy danych przy dodawaniu surowca: {err}")
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def oblicz_aktualny_stan_apollo(id_sprzetu):
        """Oblicza przewidywany aktualny stan płynnego surowca w Apollo."""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Znajdź aktywną sesję
            cursor.execute("""
                SELECT * FROM apollo_sesje 
                WHERE id_sprzetu = %s AND status_sesji = 'aktywna'
            """, (id_sprzetu,))
            sesja = cursor.fetchone()
            
            if not sesja:
                return {
                    'aktywna_sesja': False,
                    'id_sesji': None,
                    'typ_surowca': None,
                    'dostepne_kg': 0,
                    'czas_rozpoczecia': None
                }

            id_sesji = sesja['id']
            
            # Pobierz wszystkie zdarzenia dla tej sesji
            cursor.execute("""
                SELECT * FROM apollo_tracking 
                WHERE id_sesji = %s 
                ORDER BY czas_zdarzenia ASC
            """, (id_sesji,))
            zdarzenia = cursor.fetchall()

            # --- Nowa, bardziej precyzyjna logika obliczeń ---
            
            # Znajdź ostatnią korektę, jeśli istnieje
            korekty = [z for z in zdarzenia if z['typ_zdarzenia'] == 'KOREKTA_RECZNA']
            
            # Ustaw punkt startowy obliczeń
            if korekty:
                ostatnia_korekta = korekty[-1]
                punkt_startowy_czas = ostatnia_korekta['czas_zdarzenia']
                ilosc_na_starcie = float(ostatnia_korekta['waga_kg'])
            else:
                punkt_startowy_czas = sesja['czas_rozpoczecia']
                ilosc_na_starcie = 0.0 # Zaczynamy z zerem płynu, wszystko jest stałe

            # Filtruj zdarzenia, które nastąpiły po naszym punkcie startowym
            zdarzenia_po_starcie = [z for z in zdarzenia if z['czas_zdarzenia'] > punkt_startowy_czas]

            # Oblicz sumy dodanego i przetransferowanego surowca OD punktu startowego
            przetransferowano_po_starcie = sum(float(z['waga_kg']) for z in zdarzenia_po_starcie if z['typ_zdarzenia'] == 'TRANSFER_WYJSCIOWY')

            # Oblicz łączną ilość surowca dodanego w całej sesji (lub od ostatniej korekty)
            # To jest nasz limit tego, co mogło się stopić
            if korekty:
                # Po korekcie, limit topnienia bazuje na tym co dodano po niej
                limit_topnienia = sum(float(z['waga_kg']) for z in zdarzenia_po_starcie if z['typ_zdarzenia'] == 'DODANIE_SUROWCA')
            else:
                # Przed korektą, limit topnienia bazuje na wszystkim co dodano w sesji
                limit_topnienia = sum(float(z['waga_kg']) for z in zdarzenia if z['typ_zdarzenia'] == 'DODANIE_SUROWCA')

            # Oblicz, ile surowca mogło się stopić od punktu startowego
            czas_topienia_sekundy = (datetime.now() - punkt_startowy_czas).total_seconds()
            wytopiono_w_czasie = (czas_topienia_sekundy / 3600.0) * ApolloService.SZYBKOSC_WYTAPIANIA_KG_H
            
            # Ilość stopiona nie może przekroczyć limitu dostępnego surowca stałego
            realnie_wytopiono = min(wytopiono_w_czasie, limit_topnienia)

            # Finalne obliczenie dostępnej ilości
            dostepne_kg = ilosc_na_starcie + realnie_wytopiono - przetransferowano_po_starcie
            dostepne_kg = max(0, dostepne_kg)

            return {
                'aktywna_sesja': True,
                'id_sesji': id_sesji,
                'typ_surowca': sesja['typ_surowca'],
                'dostepne_kg': round(dostepne_kg, 2),
                'czas_rozpoczecia': sesja['czas_rozpoczecia'].isoformat()
            }
            
        except mysql.connector.Error as err:
            raise Exception(f"Błąd bazy danych przy obliczaniu stanu: {err}")
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def koryguj_stan_apollo(id_sprzetu, rzeczywista_waga_kg, operator=None, uwagi=None):
        """Dodaje ręczną korektę stanu płynnego surowca."""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            # Znajdź aktywną sesję
            cursor.execute("""
                SELECT id FROM apollo_sesje 
                WHERE id_sprzetu = %s AND status_sesji = 'aktywna'
            """, (id_sprzetu,))
            sesja = cursor.fetchone()
            if not sesja:
                raise ValueError(f"Apollo o ID {id_sprzetu} nie ma aktywnej sesji.")
            
            id_sesji = sesja['id']

            # Dodaj zdarzenie korekty
            cursor.execute("""
                INSERT INTO apollo_tracking
                (id_sesji, typ_zdarzenia, waga_kg, czas_zdarzenia, operator, uwagi)
                VALUES (%s, 'KOREKTA_RECZNA', %s, %s, %s, %s)
            """, (id_sesji, rzeczywista_waga_kg, datetime.now(), operator, uwagi))
            
            conn.commit()

        except mysql.connector.Error as err:
            if conn.is_connected():
                conn.rollback()
            raise Exception(f"Błąd bazy danych przy korekcie stanu: {err}")
        finally:
            cursor.close()
            conn.close()
            
    @staticmethod
    def zakoncz_sesje_apollo(id_sprzetu: int, operator: str = None):
        """Kończy aktywną sesję wytapiania w danym Apollo."""
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Znajdź aktywną sesję
            cursor.execute("""
                SELECT id FROM apollo_sesje 
                WHERE id_sprzetu = %s AND status_sesji = 'aktywna'
            """, (id_sprzetu,))
            sesja = cursor.fetchone()
            if not sesja:
                raise ValueError(f"Apollo o ID {id_sprzetu} nie ma aktywnej sesji do zakończenia.")
            
            # Zakończ sesję
            cursor.execute("""
                UPDATE apollo_sesje
                SET status_sesji = 'zakonczona',
                    czas_zakonczenia = NOW()
                WHERE id = %s
            """, (sesja[0],))
            
            conn.commit()

        except mysql.connector.Error as err:
            if conn.is_connected():
                conn.rollback()
            raise Exception(f"Błąd bazy danych przy kończeniu sesji: {err}")
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_stan_apollo(id_sprzetu: int):
        """Pobiera aktualny, dynamiczny stan danego Apollo."""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            # Pobierz info o Apollo, w tym nową kolumnę
            cursor.execute("SELECT id, nazwa_unikalna, szybkosc_topnienia_kg_h FROM sprzet WHERE id = %s", (id_sprzetu,))
            apollo = cursor.fetchone()
            if not apollo:
                return None

            szybkosc_topnienia_db = apollo.get('szybkosc_topnienia_kg_h')
            # Konwersja Decimal na float, aby uniknąć błędu typów przy mnożeniu
            szybkosc_topnienia_kg_h = float(szybkosc_topnienia_db) if szybkosc_topnienia_db is not None else 50.0

            # Sprawdź aktywną sesję
            cursor.execute("""
                SELECT id, typ_surowca, czas_rozpoczecia 
                FROM apollo_sesje 
                WHERE id_sprzetu = %s AND status_sesji = 'aktywna'
            """, (id_sprzetu,))
            sesja = cursor.fetchone()

            result = {
                'id_sprzetu': apollo['id'],
                'nazwa_apollo': apollo['nazwa_unikalna'],
                'aktywna_sesja': False
            }

            if sesja:
                id_sesji = sesja['id']
                
                # 1. Oblicz całkowity bilans materiału w sesji (księgowy)
                cursor.execute("SELECT SUM(waga_kg) as total FROM apollo_tracking WHERE id_sesji = %s AND typ_zdarzenia = 'dodanie_surowca'", (id_sesji,))
                total_added = (cursor.fetchone()['total'] or 0)
                
                cursor.execute("SELECT SUM(ilosc_kg) as total FROM operacje_log WHERE id_apollo_sesji = %s AND status_operacji = 'zakonczona'", (id_sesji,))
                total_transferred = (cursor.fetchone()['total'] or 0)
                
                bilans_ksiegowy_kg = total_added - total_transferred

                # 2. Znajdź ostatnią operację i oblicz ilość wytopioną od tamtego czasu
                cursor.execute("""
                    SELECT czas_zakonczenia, ilosc_kg
                    FROM operacje_log 
                    WHERE id_apollo_sesji = %s AND status_operacji = 'zakonczona'
                    ORDER BY czas_zakonczenia DESC
                    LIMIT 1
                """, (id_sesji,))
                ostatnia_operacja = cursor.fetchone()
                
                czas_ostatniej_operacji = ostatnia_operacja['czas_zakonczenia'] if ostatnia_operacja else None
                ilosc_ostatniej_operacji_kg = ostatnia_operacja['ilosc_kg'] if ostatnia_operacja else None

                punkt_odniesienia = czas_ostatniej_operacji or sesja['czas_rozpoczecia']
                
                # Porównujemy "naiwne" obiekty datetime.
                czas_teraz = datetime.now()
                
                czas_od_ostatniej_operacji_s = (czas_teraz - punkt_odniesienia).total_seconds()
                czas_od_ostatniej_operacji_h = max(0, czas_od_ostatniej_operacji_s) / 3600

                wytopiono_od_ostatniego_razu_kg = czas_od_ostatniej_operacji_h * szybkosc_topnienia_kg_h

                # 3. Wybierz mniejszą z dwóch wartości jako realnie dostępną ilość
                realnie_dostepne_kg = min(bilans_ksiegowy_kg, wytopiono_od_ostatniego_razu_kg)

                result.update({
                    'aktywna_sesja': True,
                    'id_sesji': id_sesji,
                    'typ_surowca': sesja['typ_surowca'],
                    'dostepne_kg': round(max(0, realnie_dostepne_kg), 2),
                    'bilans_sesji_kg': round(max(0, bilans_ksiegowy_kg), 2),
                    'ostatni_transfer_czas': czas_ostatniej_operacji.strftime('%Y-%m-%d %H:%M:%S') if czas_ostatniej_operacji else None,
                    'ostatni_transfer_kg': float(ilosc_ostatniej_operacji_kg) if ilosc_ostatniej_operacji_kg is not None else None
                })

            return result

        except mysql.connector.Error as err:
            raise Exception(f"Błąd bazy danych przy pobieraniu stanu Apollo: {err}")
        finally:
            cursor.close()
            conn.close() 