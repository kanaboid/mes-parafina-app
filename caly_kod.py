# app/apollo_service.py

from datetime import datetime, timedelta, timezone
from .db import get_db_connection
import mysql.connector

class ApolloService:
    # ZakĹ‚adamy staĹ‚Ä… szybkoĹ›Ä‡ wytapiania w kg na godzinÄ™
    SZYBKOSC_WYTAPIANIA_KG_H = 1000.0

    @staticmethod
    def rozpocznij_sesje_apollo(id_sprzetu, typ_surowca, waga_kg, operator=None):
        """Rozpoczyna nowÄ… sesjÄ™ wytapiania i tworzy partiÄ™ surowca w Apollo."""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # SprawdĹş, czy nie ma juĹĽ aktywnej sesji
            cursor.execute("""
                SELECT id FROM apollo_sesje 
                WHERE id_sprzetu = %s AND status_sesji = 'aktywna'
            """, (id_sprzetu,))
            if cursor.fetchone():
                raise ValueError(f"Apollo o ID {id_sprzetu} ma juĹĽ aktywnÄ… sesjÄ™.")

            # Transakcja jest rozpoczynana automatycznie przez pierwsze zapytanie
            # przy autocommit=False, wiÄ™c nie ma potrzeby wywoĹ‚ywaÄ‡ start_transaction()
            
            # 1. StwĂłrz nowÄ… sesjÄ™
            czas_startu = datetime.now(timezone.utc)
            cursor.execute("""
                INSERT INTO apollo_sesje 
                (id_sprzetu, typ_surowca, czas_rozpoczecia, rozpoczeta_przez, status_sesji) 
                VALUES (%s, %s, %s, %s, 'aktywna')
            """, (id_sprzetu, typ_surowca, czas_startu, operator))
            id_sesji = cursor.lastrowid
            
            # 2. Dodaj pierwsze zdarzenie - zaĹ‚adunek poczÄ…tkowy
            cursor.execute("""
                INSERT INTO apollo_tracking
                (id_sesji, typ_zdarzenia, waga_kg, czas_zdarzenia, operator)
                VALUES (%s, 'DODANIE_SUROWCA', %s, %s, %s)
            """, (id_sesji, waga_kg, czas_startu, operator))
            
            # 3. StwĂłrz nowÄ… partiÄ™ surowca dla Apollo
            cursor.execute("SELECT nazwa_unikalna FROM sprzet WHERE id = %s", (id_sprzetu,))
            sprzet_info = cursor.fetchone()
            nazwa_sprzetu = sprzet_info['nazwa_unikalna'] if sprzet_info else f"ID{id_sprzetu}"
            
            teraz = datetime.now(timezone.utc)
            timestamp_str = teraz.strftime('%Y%m%d-%H%M%S')
            unikalny_kod_partii = f"{nazwa_sprzetu}-{timestamp_str}"
            nazwa_partii = f"Partia w {nazwa_sprzetu} ({typ_surowca}) - {timestamp_str}"
            
            cursor.execute("""
                INSERT INTO partie_surowca
                (unikalny_kod, nazwa_partii, typ_surowca, waga_poczatkowa_kg, waga_aktualna_kg, id_sprzetu, zrodlo_pochodzenia, status_partii, typ_transformacji)
                VALUES (%s, %s, %s, %s, %s, %s, 'apollo', 'Surowy w reaktorze', 'NOWA')
            """, (unikalny_kod_partii, nazwa_partii, typ_surowca, waga_kg, waga_kg, id_sprzetu))

            conn.commit()
            return id_sesji
            
        except mysql.connector.Error as err:
            conn.rollback()
            raise Exception(f"BĹ‚Ä…d bazy danych przy rozpoczynaniu sesji: {err}")
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def dodaj_surowiec_do_apollo(id_sprzetu, waga_kg, operator=None):
        """Dodaje staĹ‚y surowiec do aktywnej sesji i aktualizuje wagÄ™ partii w Apollo."""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # ZnajdĹş aktywnÄ… sesjÄ™
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
            """, (id_sesji, waga_kg, datetime.now(timezone.utc), operator))
            
            # Zaktualizuj wagÄ™ partii w Apollo
            cursor.execute("""
                UPDATE partie_surowca
                SET waga_aktualna_kg = waga_aktualna_kg + %s
                WHERE id_sprzetu = %s
            """, (waga_kg, id_sprzetu))
            
            if cursor.rowcount == 0:
                # JeĹ›li z jakiegoĹ› powodu partia nie istnieje, stwĂłrz jÄ…
                # (zabezpieczenie dla starszych danych lub nieprzewidzianych sytuacji)
                cursor.execute("SELECT typ_surowca FROM apollo_sesje WHERE id = %s", (id_sesji,))
                sesja_info = cursor.fetchone()
                typ_surowca = sesja_info['typ_surowca'] if sesja_info else 'Nieznany'

                cursor.execute("SELECT nazwa_unikalna FROM sprzet WHERE id = %s", (id_sprzetu,))
                sprzet_info = cursor.fetchone()
                nazwa_sprzetu = sprzet_info['nazwa_unikalna'] if sprzet_info else f"ID{id_sprzetu}"

                teraz = datetime.now(timezone.utc)
                timestamp_str = teraz.strftime('%Y%m%d-%H%M%S')
                unikalny_kod_partii = f"{nazwa_sprzetu}-{timestamp_str}-AUTOCREATED"
                nazwa_partii = f"Partia w {nazwa_sprzetu} ({typ_surowca}) - {timestamp_str}"
                
                cursor.execute("""
                    INSERT INTO partie_surowca
                    (unikalny_kod, nazwa_partii, typ_surowca, waga_poczatkowa_kg, waga_aktualna_kg, id_sprzetu, zrodlo_pochodzenia, status_partii, typ_transformacji)
                    VALUES (%s, %s, %s, %s, %s, %s, 'apollo', 'Surowy w reaktorze', 'NOWA')
                """, (unikalny_kod_partii, nazwa_partii, typ_surowca, waga_kg, waga_kg, id_sprzetu))

            conn.commit()
            
        except mysql.connector.Error as err:
            conn.rollback()
            raise Exception(f"BĹ‚Ä…d bazy danych przy dodawaniu surowca: {err}")
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def oblicz_aktualny_stan_apollo(id_sprzetu):
        """Oblicza przewidywany aktualny stan pĹ‚ynnego surowca w Apollo."""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # ZnajdĹş aktywnÄ… sesjÄ™
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

            # --- Nowa, bardziej precyzyjna logika obliczeĹ„ ---
            
            # ZnajdĹş ostatniÄ… korektÄ™, jeĹ›li istnieje
            korekty = [z for z in zdarzenia if z['typ_zdarzenia'] == 'KOREKTA_RECZNA']
            
            # Ustaw punkt startowy obliczeĹ„
            if korekty:
                ostatnia_korekta = korekty[-1]
                punkt_startowy_czas = ostatnia_korekta['czas_zdarzenia']
                ilosc_na_starcie = float(ostatnia_korekta['waga_kg'])
            else:
                punkt_startowy_czas = sesja['czas_rozpoczecia']
                ilosc_na_starcie = 0.0 # Zaczynamy z zerem pĹ‚ynu, wszystko jest staĹ‚e

            # Filtruj zdarzenia, ktĂłre nastÄ…piĹ‚y po naszym punkcie startowym
            zdarzenia_po_starcie = [z for z in zdarzenia if z['czas_zdarzenia'] > punkt_startowy_czas]

            # Oblicz sumy dodanego i przetransferowanego surowca OD punktu startowego
            przetransferowano_po_starcie = sum(float(z['waga_kg']) for z in zdarzenia_po_starcie if z['typ_zdarzenia'] == 'TRANSFER_WYJSCIOWY')

            # Oblicz Ĺ‚Ä…cznÄ… iloĹ›Ä‡ surowca dodanego w caĹ‚ej sesji (lub od ostatniej korekty)
            # To jest nasz limit tego, co mogĹ‚o siÄ™ stopiÄ‡
            if korekty:
                # Po korekcie, limit topnienia bazuje na tym co dodano po niej
                limit_topnienia = sum(float(z['waga_kg']) for z in zdarzenia_po_starcie if z['typ_zdarzenia'] == 'DODANIE_SUROWCA')
            else:
                # Przed korektÄ…, limit topnienia bazuje na wszystkim co dodano w sesji
                limit_topnienia = sum(float(z['waga_kg']) for z in zdarzenia if z['typ_zdarzenia'] == 'DODANIE_SUROWCA')

            # Oblicz, ile surowca mogĹ‚o siÄ™ stopiÄ‡ od punktu startowego
            czas_topienia_sekundy = (datetime.now(timezone.utc) - punkt_startowy_czas).total_seconds()
            wytopiono_w_czasie = (czas_topienia_sekundy / 3600.0) * ApolloService.SZYBKOSC_WYTAPIANIA_KG_H
            
            # IloĹ›Ä‡ stopiona nie moĹĽe przekroczyÄ‡ limitu dostÄ™pnego surowca staĹ‚ego
            realnie_wytopiono = min(wytopiono_w_czasie, limit_topnienia)

            # Finalne obliczenie dostÄ™pnej iloĹ›ci
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
            raise Exception(f"BĹ‚Ä…d bazy danych przy obliczaniu stanu: {err}")
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def koryguj_stan_apollo(id_sprzetu, rzeczywista_waga_kg, operator=None, uwagi=None):
        """Dodaje rÄ™cznÄ… korektÄ™ stanu pĹ‚ynnego surowca."""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            # ZnajdĹş aktywnÄ… sesjÄ™
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
            """, (id_sesji, rzeczywista_waga_kg, datetime.now(timezone.utc), operator, uwagi))
            
            conn.commit()

        except mysql.connector.Error as err:
            if conn.is_connected():
                conn.rollback()
            raise Exception(f"BĹ‚Ä…d bazy danych przy korekcie stanu: {err}")
        finally:
            cursor.close()
            conn.close()
            
    @staticmethod
    def zakoncz_sesje_apollo(id_sprzetu: int, operator: str = None):
        """KoĹ„czy aktywnÄ… sesjÄ™ wytapiania w danym Apollo."""
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # ZnajdĹş aktywnÄ… sesjÄ™
            cursor.execute("""
                SELECT id FROM apollo_sesje 
                WHERE id_sprzetu = %s AND status_sesji = 'aktywna'
            """, (id_sprzetu,))
            sesja = cursor.fetchone()
            if not sesja:
                raise ValueError(f"Apollo o ID {id_sprzetu} nie ma aktywnej sesji do zakoĹ„czenia.")
            
            # ZakoĹ„cz sesjÄ™
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
            raise Exception(f"BĹ‚Ä…d bazy danych przy koĹ„czeniu sesji: {err}")
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_stan_apollo(id_sprzetu: int):
        """Pobiera aktualny, dynamiczny stan danego Apollo."""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            # Pobierz info o Apollo, w tym nowÄ… kolumnÄ™
            cursor.execute("SELECT id, nazwa_unikalna, szybkosc_topnienia_kg_h FROM sprzet WHERE id = %s", (id_sprzetu,))
            apollo = cursor.fetchone()
            if not apollo:
                return None

            szybkosc_topnienia_db = apollo.get('szybkosc_topnienia_kg_h')
            # Konwersja Decimal na float, aby uniknÄ…Ä‡ bĹ‚Ä™du typĂłw przy mnoĹĽeniu
            szybkosc_topnienia_kg_h = float(szybkosc_topnienia_db) if szybkosc_topnienia_db is not None else 50.0

            # SprawdĹş aktywnÄ… sesjÄ™
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
                
                # 1. Oblicz caĹ‚kowity bilans materiaĹ‚u w sesji (ksiÄ™gowy)
                cursor.execute("SELECT SUM(waga_kg) as total FROM apollo_tracking WHERE id_sesji = %s AND typ_zdarzenia = 'dodanie_surowca'", (id_sesji,))
                total_added = (cursor.fetchone()['total'] or 0)
                
                cursor.execute("SELECT SUM(ilosc_kg) as total FROM operacje_log WHERE id_apollo_sesji = %s AND status_operacji = 'zakonczona'", (id_sesji,))
                total_transferred = (cursor.fetchone()['total'] or 0)
                
                bilans_ksiegowy_kg = total_added - total_transferred

                # 2. ZnajdĹş ostatniÄ… operacjÄ™ i oblicz iloĹ›Ä‡ wytopionÄ… od tamtego czasu
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
                
                # PorĂłwnujemy "naiwne" obiekty datetime.
                czas_teraz = datetime.now(timezone.utc)
                
                czas_od_ostatniej_operacji_s = (czas_teraz - punkt_odniesienia).total_seconds()
                czas_od_ostatniej_operacji_h = max(0, czas_od_ostatniej_operacji_s) / 3600

                wytopiono_od_ostatniego_razu_kg = czas_od_ostatniej_operacji_h * szybkosc_topnienia_kg_h

                # 3. Wybierz mniejszÄ… z dwĂłch wartoĹ›ci jako realnie dostÄ™pnÄ… iloĹ›Ä‡
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
            raise Exception(f"BĹ‚Ä…d bazy danych przy pobieraniu stanu Apollo: {err}")
        finally:
            cursor.close()
            conn.close() 
    # app/config.py

import os
from dotenv import load_dotenv

load_dotenv()

# class Config:
#     # Klucz do zabezpieczeĹ„ Flaska, np. sesji. Na razie nieistotny, ale potrzebny.
#     SECRET_KEY = os.environ.get('SECRET_KEY') or 'trudne-do-zgadniecia-haslo'

#     # Dane do poĹ‚Ä…czenia z bazÄ… danych MySQL
#     MYSQL_HOST = '10.200.184.217'
#     MYSQL_USER = 'remote_user' # ZmieĹ„, jeĹ›li masz innego uĹĽytkownika
#     MYSQL_PASSWORD = 'Radar123@@' # <-- WAĹ»NE: Wpisz swoje hasĹ‚o
#     MYSQL_DB = 'mes_parafina_db'



# class Config:
#     # Klucz do zabezpieczeĹ„ Flaska, np. sesji. Na razie nieistotny, ale potrzebny.
#     SECRET_KEY = os.environ.get('SECRET_KEY') or 'trudne-do-zgadniecia-haslo'

#     # Dane do poĹ‚Ä…czenia z bazÄ… danych MySQL
#     MYSQL_HOST = 'localhost'
#     MYSQL_USER = 'root' # ZmieĹ„, jeĹ›li masz innego uĹĽytkownika
#     MYSQL_PASSWORD = '' # <-- WAĹ»NE: Wpisz swoje hasĹ‚o
#     MYSQL_DB = 'mes_parafina_db'

class Config:
    # Klucz do zabezpieczeĹ„ Flaska, np. sesji. Na razie nieistotny, ale potrzebny.
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'trudne-do-zgadniecia-haslo'

    # Dane do poĹ‚Ä…czenia z bazÄ… danych MySQL
    MYSQL_HOST = os.environ.get('MYSQLHOST')
    MYSQL_USER = os.environ.get('MYSQLUSER') # ZmieĹ„, jeĹ›li masz innego uĹĽytkownika
    MYSQL_PASSWORD = os.environ.get('MYSQL_ROOT_PASSWORD') # <-- WAĹ»NE: Wpisz swoje hasĹ‚o
    MYSQL_DB = 'mes_parafina_db'
# app/cykle_api.py
"""
Dodatkowe API endpoints dla zarzÄ…dzania cyklami filtracyjnymi
"""

from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
from .db import get_db_connection
import mysql.connector

cykle_bp = Blueprint('cykle', __name__, url_prefix='/api')

@cykle_bp.route('/cykle-filtracyjne/<int:id_partii>')
def get_cykle_partii(id_partii):
    """Pobiera historiÄ™ wszystkich cykli filtracyjnych dla danej partii."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT cf.*, 
                   ps.unikalny_kod, ps.typ_surowca, ps.nazwa_partii,
                   TIMESTAMPDIFF(MINUTE, cf.czas_rozpoczecia, cf.czas_zakonczenia) as rzeczywisty_czas_minut
            FROM cykle_filtracyjne cf
            JOIN partie_surowca ps ON cf.id_partii = ps.id
            WHERE cf.id_partii = %s
            ORDER BY cf.numer_cyklu, cf.czas_rozpoczecia
        """, (id_partii,))
        
        cykle = cursor.fetchall()
        return jsonify(cykle)
        
    finally:
        cursor.close()
        conn.close()

@cykle_bp.route('/partie/aktualny-stan')
def get_partie_aktualny_stan():
    """Pobiera aktualny stan wszystkich partii w systemie z szczegĂłĹ‚ami procesu."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT ps.*,
                   s.nazwa_unikalna as nazwa_reaktora,
                   s.typ_sprzetu,
                   CASE 
                       WHEN ps.planowany_czas_zakonczenia IS NOT NULL 
                       THEN TIMESTAMPDIFF(MINUTE, NOW(), ps.planowany_czas_zakonczenia)
                       ELSE NULL
                   END as pozostale_minuty,
                   CASE 
                       WHEN ps.planowany_czas_zakonczenia IS NOT NULL AND NOW() > ps.planowany_czas_zakonczenia
                       THEN TRUE
                       ELSE FALSE
                   END as przekroczony_czas
            FROM partie_surowca ps
            LEFT JOIN sprzet s ON ps.id_aktualnego_sprzetu = s.id
            WHERE ps.status_partii NOT IN ('W magazynie czystym', 'Gotowy do wysĹ‚ania')
            ORDER BY ps.czas_rozpoczecia_etapu DESC
        """)
        
        partie = cursor.fetchall()
        return jsonify(partie)
        
    finally:
        cursor.close()
        conn.close()

@cykle_bp.route('/filtry/szczegolowy-status')
def get_filtry_szczegolowy_status():
    """Pobiera szczegĂłĹ‚owy status filtrĂłw z informacjami o partiach i cyklach."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Podstawowe informacje o filtrach
        cursor.execute("""
            SELECT id, nazwa_unikalna as nazwa_filtra, stan_sprzetu, typ_sprzetu
            FROM sprzet 
            WHERE typ_sprzetu = 'filtr'
            ORDER BY nazwa_unikalna
        """)
        filtry = cursor.fetchall()
        
        filtry_lista = []
        for filtr in filtry:
            filtr_dict = dict(filtr)
            
            # SprawdĹş czy filtr ma aktywnÄ… operacjÄ™
            cursor.execute("""
                SELECT ol.*, 
                       ps.unikalny_kod, ps.nazwa_partii, ps.typ_surowca,
                       ps.aktualny_etap_procesu, ps.numer_cyklu_aktualnego,
                       ps.czas_rozpoczecia_etapu, ps.planowany_czas_zakonczenia,
                       s_start.nazwa_unikalna as reaktor_startowy,
                       s_cel.nazwa_unikalna as reaktor_docelowy,
                       CASE 
                           WHEN ps.planowany_czas_zakonczenia IS NOT NULL 
                           THEN TIMESTAMPDIFF(MINUTE, NOW(), ps.planowany_czas_zakonczenia)
                           ELSE NULL
                       END as pozostale_minuty
                FROM operacje_log ol
                JOIN partie_surowca ps ON ol.id_partii_surowca = ps.id
                LEFT JOIN sprzet s_start ON ol.id_sprzetu_zrodlowego = s_start.id
                LEFT JOIN sprzet s_cel ON ol.id_sprzetu_docelowego = s_cel.id
                WHERE ol.status_operacji = 'aktywna' 
                AND ps.id_aktualnego_filtra = %s
                ORDER BY ol.czas_rozpoczecia DESC
                LIMIT 1
            """, (filtr_dict['nazwa_filtra'],))
            
            aktywna_operacja = cursor.fetchone()
            filtr_dict['aktywna_operacja'] = aktywna_operacja
            
            # JeĹ›li nie ma aktywnej operacji, sprawdĹş czy ktoĹ› czeka na ten filtr
            if not aktywna_operacja:
                cursor.execute("""
                    SELECT ps.*, s.nazwa_unikalna as nazwa_reaktora
                    FROM partie_surowca ps
                    JOIN sprzet s ON ps.id_aktualnego_sprzetu = s.id
                    WHERE ps.id_aktualnego_filtra = %s 
                    AND ps.aktualny_etap_procesu IN ('surowy', 'gotowy')
                    ORDER BY ps.czas_rozpoczecia_etapu ASC
                    LIMIT 3
                """, (filtr_dict['nazwa_filtra'],))
                
                filtr_dict['kolejka_oczekujacych'] = cursor.fetchall()
            else:
                filtr_dict['kolejka_oczekujacych'] = []
            
            filtry_lista.append(filtr_dict)
        
        return jsonify(filtry_lista)
        
    finally:
        cursor.close()
        conn.close()

@cykle_bp.route('/cykle/rozpocznij', methods=['POST'])
def rozpocznij_cykl_filtracyjny():
    """Rozpoczyna nowy cykl filtracyjny dla partii."""
    data = request.get_json()
    
    required_fields = ['id_partii', 'typ_cyklu', 'id_filtra', 'reaktor_startowy']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Brak wymaganych pĂłl'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Pobierz aktualny numer cyklu partii
        cursor.execute("SELECT numer_cyklu_aktualnego FROM partie_surowca WHERE id = %s", (data['id_partii'],))
        result = cursor.fetchone()
        if not result:
            return jsonify({'error': 'Nie znaleziono partii'}), 404
        
        numer_cyklu = result['numer_cyklu_aktualnego'] + 1
        
        # Oblicz planowany czas zakoĹ„czenia
        durations = {
            'placek': 30,
            'filtracja': 15,
            'dmuchanie': 45
        }
        
        planowany_czas = datetime.now(timezone.utc) + timedelta(minutes=durations.get(data['typ_cyklu'], 30))
        
        # Wstaw nowy cykl
        cursor.execute("""
            INSERT INTO cykle_filtracyjne 
            (id_partii, numer_cyklu, typ_cyklu, id_filtra, reaktor_startowy, 
             reaktor_docelowy, czas_rozpoczecia, wynik_oceny)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), 'oczekuje')
        """, (data['id_partii'], numer_cyklu, data['typ_cyklu'], data['id_filtra'], 
              data['reaktor_startowy'], data.get('reaktor_docelowy')))
        
        cykl_id = cursor.lastrowid
        
        # Aktualizuj partiÄ™
        etap_mapping = {
            'placek': 'placek',
            'filtracja': 'w_kole', 
            'dmuchanie': 'dmuchanie'
        }
        
        cursor.execute("""
            UPDATE partie_surowca 
            SET numer_cyklu_aktualnego = %s,
                aktualny_etap_procesu = %s,
                czas_rozpoczecia_etapu = NOW(),
                planowany_czas_zakonczenia = %s,
                id_aktualnego_filtra = %s,
                reaktor_docelowy = %s
            WHERE id = %s
        """, (numer_cyklu, etap_mapping[data['typ_cyklu']], planowany_czas,
              data['id_filtra'], data.get('reaktor_docelowy'), data['id_partii']))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'RozpoczÄ™to cykl {data["typ_cyklu"]} dla partii',
            'cykl_id': cykl_id,
            'numer_cyklu': numer_cyklu
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'BĹ‚Ä…d rozpoczynania cyklu: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@cykle_bp.route('/cykle/zakoncz', methods=['POST'])
def zakoncz_cykl_filtracyjny():
    """KoĹ„czy aktualny cykl filtracyjny i przechodzi do nastÄ™pnego etapu."""
    data = request.get_json()
    
    if 'id_partii' not in data:
        return jsonify({'error': 'Brak ID partii'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Pobierz aktualny stan partii
        cursor.execute("""
            SELECT * FROM partie_surowca WHERE id = %s
        """, (data['id_partii'],))
        
        partia = cursor.fetchone()
        if not partia:
            return jsonify({'error': 'Nie znaleziono partii'}), 404
        
        # ZakoĹ„cz aktualny cykl
        cursor.execute("""
            UPDATE cykle_filtracyjne 
            SET czas_zakonczenia = NOW(),
                czas_trwania_minut = TIMESTAMPDIFF(MINUTE, czas_rozpoczecia, NOW()),
                wynik_oceny = %s,
                komentarz = %s
            WHERE id_partii = %s 
            AND numer_cyklu = %s 
            AND czas_zakonczenia IS NULL
        """, (data.get('wynik_oceny', 'oczekuje'), data.get('komentarz', ''),
              data['id_partii'], partia['numer_cyklu_aktualnego']))
        
        # OkreĹ›l nastÄ™pny etap na podstawie aktualnego
        next_etap = 'gotowy'
        next_filtr = None
        
        if partia['aktualny_etap_procesu'] == 'placek':
            next_etap = 'przelew'
        elif partia['aktualny_etap_procesu'] == 'przelew':
            next_etap = 'w_kole'
        elif partia['aktualny_etap_procesu'] == 'w_kole':
            next_etap = 'ocena_probki'
        elif partia['aktualny_etap_procesu'] == 'dmuchanie':
            next_etap = 'gotowy'
            next_filtr = None
        
        # Aktualizuj partiÄ™
        cursor.execute("""
            UPDATE partie_surowca 
            SET aktualny_etap_procesu = %s,
                czas_rozpoczecia_etapu = NOW(),
                planowany_czas_zakonczenia = NULL,
                id_aktualnego_filtra = %s
            WHERE id = %s
        """, (next_etap, next_filtr, data['id_partii']))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'ZakoĹ„czono cykl. Partia przeszĹ‚a do etapu: {next_etap}',
            'next_etap': next_etap
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'BĹ‚Ä…d koĹ„czenia cyklu: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()
# app/db.py

import mysql.connector
from flask import current_app

def get_db_connection(config=None):
    """Tworzy i zwraca nowe poĹ‚Ä…czenie z bazÄ… danych na podstawie podanej konfiguracji lub z current_app."""
    if config is None:
        config = current_app.config
    connection = mysql.connector.connect(
        host=config['MYSQL_HOST'],
        user=config['MYSQL_USER'],
        password=config['MYSQL_PASSWORD'],
        database=config['MYSQL_DB'],
        autocommit=False
    )
    return connection
# app/migration_routes.py
from flask import Blueprint, jsonify, request
from .db import get_db_connection
import mysql.connector

migration_bp = Blueprint('migration', __name__, url_prefix='/admin')

@migration_bp.route('/migrate/cykle-filtracyjne', methods=['POST'])
def migrate_cykle_filtracyjne():
    """Endpoint do wykonania migracji bazy danych"""
    
    # Sprawdzenie hasĹ‚a administratora (dla bezpieczeĹ„stwa)
    admin_password = request.json.get('admin_password')
    if admin_password != 'admin123':  # ZmieĹ„ na bezpieczne hasĹ‚o
        return jsonify({'error': 'NieprawidĹ‚owe hasĹ‚o administratora'}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Lista zapytaĹ„ do wykonania
        queries = [
            # Rozszerzenie tabeli partie_surowca
            """ALTER TABLE partie_surowca 
               ADD COLUMN aktualny_etap_procesu ENUM(
                   'surowy', 'placek', 'przelew', 'w_kole', 
                   'ocena_probki', 'dmuchanie', 'gotowy', 'wydmuch'
               ) DEFAULT 'surowy' AFTER status_partii""",
            
            """ALTER TABLE partie_surowca 
               ADD COLUMN numer_cyklu_aktualnego INT DEFAULT 0 AFTER aktualny_etap_procesu""",
            
            """ALTER TABLE partie_surowca 
               ADD COLUMN czas_rozpoczecia_etapu DATETIME NULL AFTER numer_cyklu_aktualnego""",
            
            """ALTER TABLE partie_surowca 
               ADD COLUMN planowany_czas_zakonczenia DATETIME NULL AFTER czas_rozpoczecia_etapu""",
            
            """ALTER TABLE partie_surowca 
               ADD COLUMN id_aktualnego_filtra VARCHAR(10) NULL AFTER planowany_czas_zakonczenia""",
            
            """ALTER TABLE partie_surowca 
               ADD COLUMN reaktor_docelowy VARCHAR(10) NULL AFTER id_aktualnego_filtra""",
            
            # Nowe tabele
            """CREATE TABLE cykle_filtracyjne (
                id INT PRIMARY KEY AUTO_INCREMENT,
                id_partii INT,
                numer_cyklu INT,
                typ_cyklu ENUM('placek', 'filtracja', 'dmuchanie'),
                id_filtra VARCHAR(10),
                reaktor_startowy VARCHAR(10),
                reaktor_docelowy VARCHAR(10),
                czas_rozpoczecia DATETIME,
                czas_zakonczenia DATETIME,
                czas_trwania_minut INT,
                wynik_oceny ENUM('pozytywna', 'negatywna', 'oczekuje'),
                komentarz TEXT,
                FOREIGN KEY (id_partii) REFERENCES partie_surowca(id) ON DELETE CASCADE,
                INDEX idx_partia_cykl (id_partii, numer_cyklu),
                INDEX idx_filtr_czas (id_filtra, czas_rozpoczecia)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
            
            """CREATE TABLE probki_ocena (
                id INT PRIMARY KEY AUTO_INCREMENT,
                id_partii INT NOT NULL,
                id_cyklu_filtracyjnego INT NOT NULL,
                czas_pobrania DATETIME NOT NULL,
                czas_oceny DATETIME NULL,
                wynik_oceny ENUM('pozytywna', 'negatywna', 'oczekuje') DEFAULT 'oczekuje',
                ocena_koloru VARCHAR(50) NULL,
                decyzja ENUM('kontynuuj_filtracje', 'wyslij_do_magazynu', 'dodaj_ziemie') NULL,
                operator_oceniajacy VARCHAR(100) NULL,
                uwagi TEXT NULL,
                FOREIGN KEY (id_partii) REFERENCES partie_surowca(id) ON DELETE CASCADE,
                FOREIGN KEY (id_cyklu_filtracyjnego) REFERENCES cykle_filtracyjne(id) ON DELETE CASCADE,
                INDEX idx_partia_czas (id_partii, czas_pobrania)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"""
        ]
        
        results = []
        for i, query in enumerate(queries):
            try:
                cursor.execute(query)
                results.append(f"Query {i+1}: SUCCESS")
            except mysql.connector.Error as err:
                if "Duplicate column name" in str(err) or "already exists" in str(err):
                    results.append(f"Query {i+1}: SKIPPED (already exists)")
                else:
                    results.append(f"Query {i+1}: ERROR - {err}")
        
        conn.commit()
        return jsonify({
            'success': True,
            'message': 'Migracja wykonana pomyĹ›lnie',
            'results': results
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'BĹ‚Ä…d migracji: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()
from datetime import datetime
import mysql.connector
from flask import current_app
from .db import get_db_connection




class MonitoringService:
    
    def init_app(self, app):
        self.app = app

    def check_equipment_status(self):
        """
        Sprawdza stan wszystkich urzÄ…dzeĹ„. Tworzy nowe alarmy, gdy parametry
        sÄ… przekroczone i automatycznie zamyka istniejÄ…ce alarmy, gdy
        parametry wrĂłcÄ… do normy.
        """
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # 1. Pobierz stan wszystkich urzÄ…dzeĹ„
            cursor.execute("SELECT * FROM sprzet")
            all_equipment = cursor.fetchall()

            # 2. Pobierz wszystkie AKTYWNE alarmy, aby wiedzieÄ‡, co juĹĽ jest zgĹ‚oszone
            cursor.execute("SELECT id, nazwa_sprzetu, typ_alarmu FROM alarmy WHERE status_alarmu = 'AKTYWNY'")
            active_alarms_raw = cursor.fetchall()
            # StwĂłrzmy z tego sĹ‚ownik dla szybkich sprawdzeĹ„: (nazwa_sprzÄ™tu, typ_alarmu) -> id_alarmu
            active_alarms = {(a['nazwa_sprzetu'], a['typ_alarmu']): a['id'] for a in active_alarms_raw}

            # 3. PrzejdĹş przez kaĹĽde urzÄ…dzenie i zweryfikuj jego stan
            for item in all_equipment:
                nazwa_sprzetu = item['nazwa_unikalna']
                
                # --- Sprawdzanie temperatury ---
                aktualna_temp = item.get('temperatura_aktualna')
                max_temp = item.get('temperatura_max')
                is_temp_alarm = (nazwa_sprzetu, 'TEMPERATURA') in active_alarms

                # Sprawdzaj tylko, jeĹ›li obie wartoĹ›ci istniejÄ…
                if aktualna_temp is not None and max_temp is not None:
                    if aktualna_temp > max_temp:
                        # JeĹ›li temperatura jest za wysoka, a nie ma aktywnego alarmu, stwĂłrz go
                        if not is_temp_alarm:
                            self._create_alarm(cursor, 'TEMPERATURA', nazwa_sprzetu, aktualna_temp, max_temp)
                    elif is_temp_alarm:
                        # JeĹ›li temperatura jest w normie, a istnieje aktywny alarm, zamknij go
                        alarm_id = active_alarms[(nazwa_sprzetu, 'TEMPERATURA')]
                        self._resolve_alarm(cursor, alarm_id)

                # --- Sprawdzanie ciĹ›nienia ---
                aktualne_cisnienie = item.get('cisnienie_aktualne')
                max_cisnienie = item.get('cisnienie_max')
                is_pressure_alarm = (nazwa_sprzetu, 'CISNIENIE') in active_alarms

                # Sprawdzaj tylko, jeĹ›li obie wartoĹ›ci istniejÄ…
                if aktualne_cisnienie is not None and max_cisnienie is not None:
                    if aktualne_cisnienie > max_cisnienie:
                        # JeĹ›li ciĹ›nienie jest za wysokie, a nie ma aktywnego alarmu, stwĂłrz go
                        if not is_pressure_alarm:
                            self._create_alarm(cursor, 'CISNIENIE', nazwa_sprzetu, aktualne_cisnienie, max_cisnienie)
                    elif is_pressure_alarm:
                        # JeĹ›li ciĹ›nienie jest w normie, a istnieje aktywny alarm, zamknij go
                        alarm_id = active_alarms[(nazwa_sprzetu, 'CISNIENIE')]
                        self._resolve_alarm(cursor, alarm_id)
            
            conn.commit()

        finally:
            cursor.close()
            conn.close()

    def _create_alarm(self, cursor, typ_alarmu, nazwa_sprzetu, wartosc, limit):
        """Prywatna metoda do tworzenia nowego alarmu w bazie danych."""
        sql = """INSERT INTO alarmy 
                 (typ_alarmu, nazwa_sprzetu, wartosc, limit_przekroczenia, czas_wystapienia, status_alarmu) 
                 VALUES (%s, %s, %s, %s, %s, 'AKTYWNY')"""
        cursor.execute(sql, (typ_alarmu, nazwa_sprzetu, wartosc, limit, datetime.now(timezone.utc)))

    def _resolve_alarm(self, cursor, alarm_id):
        """Prywatna metoda do zamykania istniejÄ…cego alarmu."""
        sql = """UPDATE alarmy 
                 SET status_alarmu = 'ZAKOĹCZONY', czas_zakonczenia = %s 
                 WHERE id = %s"""
        cursor.execute(sql, (datetime.now(timezone.utc), alarm_id))
# app/operations_routes.py
from flask import Blueprint, jsonify, request, current_app
from datetime import datetime
import mysql.connector
from .db import get_db_connection
from .pathfinder_service import PathFinder
from .apollo_service import ApolloService
import traceback

# Utworzenie nowego Blueprintu dla operacji
bp = Blueprint('operations', __name__, url_prefix='/api/operations')

def get_pathfinder():
    """Pobiera instancjÄ™ serwisu PathFinder z kontekstu aplikacji."""
    return current_app.extensions['pathfinder']

# Endpoint do tworzenia nowej partii przez tankowanie
@bp.route('/tankowanie', methods=['POST'])
def tankowanie():
    dane = request.get_json()
    
    # Validation
    wymagane_pola = ['nazwa_portu_zrodlowego', 'nazwa_portu_docelowego', 
                     'typ_surowca', 'waga_kg', 'zrodlo_pochodzenia']
    if not dane or not all(k in dane for k in wymagane_pola):
        return jsonify({'message': 'Brak wymaganych danych'}), 400

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Get equipment IDs from port names
        cursor.execute("""
            SELECT s.id, s.nazwa_unikalna 
            FROM porty_sprzetu p 
            JOIN sprzet s ON p.id_sprzetu = s.id 
            WHERE p.nazwa_portu = %s
        """, (dane['nazwa_portu_zrodlowego'],))
        zrodlo = cursor.fetchone()
        
        cursor.execute("""
            SELECT s.id, s.nazwa_unikalna 
            FROM porty_sprzetu p 
            JOIN sprzet s ON p.id_sprzetu = s.id 
            WHERE p.nazwa_portu = %s
        """, (dane['nazwa_portu_docelowego'],))
        cel = cursor.fetchone()

        if not zrodlo or not cel:
            return jsonify({'message': 'NieprawidĹ‚owy port ĹşrĂłdĹ‚owy lub docelowy'}), 400

        id_zrodla = zrodlo['id']
        id_celu = cel['id']

        # Check if target reactor is empty
        cursor.execute("SELECT stan_sprzetu FROM sprzet WHERE id = %s", (id_celu,))
        stan_reaktora = cursor.fetchone()
        
        if not stan_reaktora or stan_reaktora['stan_sprzetu'] != 'Pusty':
            return jsonify({
                'message': f"Reaktor docelowy nie jest pusty (stan: {stan_reaktora['stan_sprzetu'] if stan_reaktora else 'nieznany'})"
            }), 400

        # Krok 4: Stworzenie unikalnego kodu partii
        teraz = datetime.now(timezone.utc)
        unikalny_kod = f"{dane['typ_surowca']}-{teraz.strftime('%Y%m%d-%H%M%S')}-{dane['zrodlo_pochodzenia'].upper()}"

        # Krok 5: Stworzenie nowej partii surowca
        sql_partia = """
            INSERT INTO partie_surowca 
            (unikalny_kod, typ_surowca, zrodlo_pochodzenia, waga_poczatkowa_kg, waga_aktualna_kg, id_sprzetu) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        # UĹ»YCIE ZMIENNEJ `id_celu`
        partia_dane = (unikalny_kod, dane['typ_surowca'], dane['zrodlo_pochodzenia'], dane['waga_kg'], dane['waga_kg'], id_celu)
        cursor.execute(sql_partia, partia_dane)
        nowa_partia_id = cursor.lastrowid

        # Krok 6: Nadanie statusu "Surowy"
        cursor.execute("INSERT IGNORE INTO partie_statusy (id_partii, id_statusu) VALUES (%s, 1)", (nowa_partia_id,))

        # Krok 7: Aktualizacja stanu reaktora docelowego
        # UĹ»YCIE ZMIENNEJ `id_celu`
        cursor.execute("UPDATE sprzet SET stan_sprzetu = 'Zatankowany (surowy)' WHERE id = %s", (id_celu,))

        # Krok 8: Zapisanie operacji w logu
        sql_log = """
            INSERT INTO operacje_log 
            (typ_operacji, id_partii_surowca, id_sprzetu_zrodlowego, id_sprzetu_docelowego, czas_rozpoczecia, ilosc_kg, opis, status_operacji) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'zakonczona')
        """
        # UĹ»YCIE ZMIENNYCH `id_zrodla` i `id_celu`
        log_dane = ('TRANSFER', nowa_partia_id, id_zrodla, id_celu, teraz, dane['waga_kg'], f"Tankowanie partii {unikalny_kod}")
        cursor.execute(sql_log, log_dane)
        
        conn.commit()
        return jsonify({'message': 'Tankowanie rozpoczÄ™te pomyĹ›lnie'}), 201

    except mysql.connector.Error as err:
        if conn: 
            conn.rollback()
        return jsonify({'message': f'BĹ‚Ä…d bazy danych: {str(err)}'}), 500
    finally:
        if conn and conn.is_connected():
            conn.close()


@bp.route('/rozpocznij_trase', methods=['POST'])
def rozpocznij_trase():
    dane = request.get_json()
    if not dane or not all(k in dane for k in ['start', 'cel', 'otwarte_zawory', 'typ_operacji']):
        return jsonify({"status": "error", "message": "Brak wymaganych pĂłl: start, cel, otwarte_zawory, typ_operacji."}), 400

    start_point = dane['start']
    end_point = dane['cel']
    open_valves_list = dane['otwarte_zawory']
    typ_operacji = dane['typ_operacji']
    sprzet_posredni = dane.get('sprzet_posredni')
    
    pathfinder = get_pathfinder()
    znaleziona_sciezka_nazwy = []

    # --- POPRAWIONA LOGIKA ZNAJDOWANIA TRASY ---
    if sprzet_posredni:
        # JeĹ›li jest sprzÄ™t poĹ›redni (np. filtr), szukamy trasy w dwĂłch czÄ™Ĺ›ciach.
        posredni_in = f"{sprzet_posredni}_IN"
        posredni_out = f"{sprzet_posredni}_OUT"

        sciezka_1 = pathfinder.find_path(start_point, posredni_in, open_valves_list)
        if not sciezka_1:
            return jsonify({"status": "error", "message": f"Nie znaleziono Ĺ›cieĹĽki z {start_point} do {posredni_in}."}), 404
        
        sciezka_wewnetrzna = pathfinder.find_path(posredni_in, posredni_out, open_valves_list)
        if not sciezka_wewnetrzna:
            return jsonify({"status": "error", "message": f"Nie znaleziono Ĺ›cieĹĽki wewnÄ™trznej w {sprzet_posredni} (z {posredni_in} do {posredni_out})."}), 404

        sciezka_2 = pathfinder.find_path(posredni_out, end_point, open_valves_list)
        if not sciezka_2:
            return jsonify({"status": "error", "message": f"Nie znaleziono Ĺ›cieĹĽki z {posredni_out} do {end_point}."}), 404

        znaleziona_sciezka_nazwy = sciezka_1 + sciezka_wewnetrzna + sciezka_2
    else:
        # JeĹ›li nie ma punktu poĹ›redniego (np. przelew bezpoĹ›redni), szukamy jednej, ciÄ…gĹ‚ej Ĺ›cieĹĽki.
        znaleziona_sciezka_nazwy = pathfinder.find_path(start_point, end_point, open_valves_list)

    # Sprawdzamy, czy ostatecznie udaĹ‚o siÄ™ znaleĹşÄ‡ trasÄ™.
    if not znaleziona_sciezka_nazwy:
        return jsonify({
            "status": "error",
            "message": f"Nie znaleziono kompletnej Ĺ›cieĹĽki z {start_point} do {end_point} przy podanym ustawieniu zaworĂłw."
        }), 404

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)



        # KROK 1.5: ZNAJDĹą PARTIÄ W REAKTORZE STARTOWYM
        # NOWA LOGIKA: Automatyczne znajdowanie partii w urzÄ…dzeniu startowym.
        # Na podstawie nazwy portu startowego znajdujemy ID sprzÄ™tu, a potem ID partii w tym sprzÄ™cie.
        sql_znajdz_partie = """
            SELECT p.id FROM partie_surowca p
            JOIN porty_sprzetu ps ON p.id_sprzetu = ps.id_sprzetu
            WHERE ps.nazwa_portu = %s
        """
        cursor.execute(sql_znajdz_partie, (start_point,))
        partia = cursor.fetchone()

        if not partia:
            return jsonify({"status": "error", "message": f"W urzÄ…dzeniu startowym ({start_point}) nie znaleziono ĹĽadnej partii."}), 404
        
        # Mamy ID partii, bÄ™dziemy go uĹĽywaÄ‡ do zapisu w logu.
        id_partii = partia['id']

        # KROK 2: SprawdĹş konflikty
        placeholders_konflikt = ', '.join(['%s'] * len(znaleziona_sciezka_nazwy))
        sql_konflikt = f"""
            SELECT s.nazwa_segmentu FROM log_uzyte_segmenty lus
            JOIN operacje_log ol ON lus.id_operacji_log = ol.id
            JOIN segmenty s ON lus.id_segmentu = s.id
            WHERE ol.status_operacji = 'aktywna' AND s.nazwa_segmentu IN ({placeholders_konflikt})
        """
        cursor.execute(sql_konflikt, znaleziona_sciezka_nazwy)
        konflikty = cursor.fetchall()

        if konflikty:
            nazwy_zajetych = [k['nazwa_segmentu'] for k in konflikty]
            
            conn.rollback() 
            return jsonify({
                "status": "error", "message": "Konflikt zasobĂłw.",
                "zajete_segmenty": [k['nazwa_segmentu'] for k in konflikty]
            }), 409

        # --- KROK 3: URUCHOMIENIE OPERACJI W TRANSAKCJI ---
       
        # UĹĽywamy nowego kursora bez `dictionary=True` do operacji zapisu
        write_cursor = conn.cursor()

        # 3a. Zaktualizuj stan zaworĂłw
        placeholders_zawory = ', '.join(['%s'] * len(open_valves_list))
        sql_zawory = f"UPDATE zawory SET stan = 'OTWARTY' WHERE nazwa_zaworu IN ({placeholders_zawory})"
        write_cursor.execute(sql_zawory, open_valves_list)

        # 3b. StwĂłrz nowÄ… operacjÄ™ w logu
        opis_operacji = f"Operacja {typ_operacji} z {start_point} do {end_point}"
        sql_log = """
            INSERT INTO operacje_log 
            (typ_operacji, id_partii_surowca, status_operacji, czas_rozpoczecia, opis, punkt_startowy, punkt_docelowy) 
            VALUES (%s, %s, 'aktywna', NOW(), %s, %s, %s)
        """
        # UĹĽywamy teraz `id_partii` znalezionego automatycznie.
        write_cursor.execute(sql_log, (typ_operacji, id_partii, opis_operacji, start_point, end_point))
        nowa_operacja_id = write_cursor.lastrowid

        # 3c. Pobierz ID segmentĂłw na trasie
        placeholders_segmenty = ', '.join(['%s'] * len(znaleziona_sciezka_nazwy))
        sql_id_segmentow = f"SELECT id FROM segmenty WHERE nazwa_segmentu IN ({placeholders_segmenty})"
        # UĹĽywamy z powrotem kursora z dictionary=True do odczytu
        cursor.execute(sql_id_segmentow, znaleziona_sciezka_nazwy)
        id_segmentow = [row['id'] for row in cursor.fetchall()]

        # 3d. Zablokuj segmenty
        sql_blokada = "INSERT INTO log_uzyte_segmenty (id_operacji_log, id_segmentu) VALUES (%s, %s)"
        dane_do_blokady = [(nowa_operacja_id, id_seg) for id_seg in id_segmentow]
        write_cursor.executemany(sql_blokada, dane_do_blokady)

        # 3e. ZatwierdĹş transakcjÄ™
        conn.commit()
        
        return jsonify({
            "status": "success",
            "message": "Operacja zostaĹ‚a pomyĹ›lnie rozpoczÄ™ta.",
            "id_operacji": nowa_operacja_id,
            "trasa": {
                "start": start_point,
                "cel": end_point,
                "uzyte_segmenty": znaleziona_sciezka_nazwy
            }
        }), 201

    except mysql.connector.Error as err:
        if conn:
            conn.rollback() # Wycofaj zmiany w razie bĹ‚Ä™du
        return jsonify({"status": "error", "message": f"BĹ‚Ä…d bazy danych: {err}"}), 500
    finally:
        if conn and conn.is_connected():
            # Zamykamy oba kursory
            if 'cursor' in locals() and cursor: cursor.close()
            if 'write_cursor' in locals() and write_cursor: write_cursor.close()
            conn.close()


@bp.route('/zakoncz', methods=['POST'])
def zakoncz_operacje():
    dane = request.get_json()
    if not dane or 'id_operacji' not in dane:
        return jsonify({"status": "error", "message": "Brak wymaganego pola: id_operacji."}), 400

    id_operacji = dane['id_operacji']

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # KROK 1: SprawdĹş, czy operacja istnieje i jest aktywna
        # Dodajemy `punkt_startowy`, aby wiedzieÄ‡, ktĂłry reaktor oprĂłĹĽniÄ‡
        sql_operacja = """
            SELECT status_operacji, typ_operacji, id_partii_surowca, punkt_startowy, punkt_docelowy 
            FROM operacje_log 
            WHERE id = %s
        """
        cursor.execute(sql_operacja, (id_operacji,))
        operacja = cursor.fetchone()

        if not operacja:
            return jsonify({"status": "error", "message": f"Operacja o ID {id_operacji} nie istnieje."}), 404
        if operacja['status_operacji'] != 'aktywna':
            return jsonify({
                "status": "error", 
                "message": f"Nie moĹĽna zakoĹ„czyÄ‡ operacji, poniewaĹĽ nie jest aktywna (status: {operacja['status_operacji']})."
            }), 409

        # --- POCZÄ„TEK TRANSAKCJI ---
        write_cursor = conn.cursor()

        # KROK 2: ZmieĹ„ status operacji
        sql_zakoncz = "UPDATE operacje_log SET status_operacji = 'zakonczona', czas_zakonczenia = NOW() WHERE id = %s"
        write_cursor.execute(sql_zakoncz, (id_operacji,))

        # KROK 3: ZnajdĹş i zamknij zawory
        sql_znajdz_zawory = """
            SELECT DISTINCT z.nazwa_zaworu FROM zawory z
            JOIN segmenty s ON z.id = s.id_zaworu
            JOIN log_uzyte_segmenty lus ON s.id = lus.id_segmentu
            WHERE lus.id_operacji_log = %s
        """
        cursor.execute(sql_znajdz_zawory, (id_operacji,))
        zawory_do_zamkniecia = [row['nazwa_zaworu'] for row in cursor.fetchall()]

        if zawory_do_zamkniecia:
            placeholders = ', '.join(['%s'] * len(zawory_do_zamkniecia))
            sql_zamknij_zawory = f"UPDATE zawory SET stan = 'ZAMKNIETY' WHERE nazwa_zaworu IN ({placeholders})"
            write_cursor.execute(sql_zamknij_zawory, zawory_do_zamkniecia)
        
        # KROK 4: Aktualizacja lokalizacji partii i stanu sprzÄ™tu
        typ_op = operacja['typ_operacji']
        id_partii = operacja['id_partii_surowca']
        punkt_startowy = operacja['punkt_startowy']
        punkt_docelowy = operacja['punkt_docelowy']

        # Sprawdzamy, czy operacja byĹ‚a przelewem (a nie np. operacjÄ… "w koĹ‚o")
        if id_partii and punkt_startowy and punkt_docelowy and punkt_startowy != punkt_docelowy:
            # ZnajdĹş ID sprzÄ™tu docelowego
            cursor.execute("SELECT id_sprzetu FROM porty_sprzetu WHERE nazwa_portu = %s", (punkt_docelowy,))
            sprzet_docelowy = cursor.fetchone()
            
            # ZnajdĹş ID sprzÄ™tu ĹşrĂłdĹ‚owego
            cursor.execute("SELECT id_sprzetu FROM porty_sprzetu WHERE nazwa_portu = %s", (punkt_startowy,))
            sprzet_zrodlowy = cursor.fetchone()

            if sprzet_docelowy and sprzet_zrodlowy:
                id_sprzetu_docelowego = sprzet_docelowy['id_sprzetu']
                id_sprzetu_zrodlowego = sprzet_zrodlowy['id_sprzetu']
                
                # 1. PrzenieĹ› partiÄ™ do nowego miejsca
                sql_przenies = "UPDATE partie_surowca SET id_sprzetu = %s WHERE id = %s"
                write_cursor.execute(sql_przenies, (id_sprzetu_docelowego, id_partii))
                
                # 2. Zaktualizuj stan sprzÄ™tu
                write_cursor.execute("UPDATE sprzet SET stan_sprzetu = 'Zatankowany' WHERE id = %s", (id_sprzetu_docelowego,))
                write_cursor.execute("UPDATE sprzet SET stan_sprzetu = 'Pusty' WHERE id = %s", (id_sprzetu_zrodlowego,))

        # KROK 5: ZatwierdĹş transakcjÄ™
        conn.commit()

        return jsonify({
            "status": "success",
            "message": f"Operacja o ID {id_operacji} zostaĹ‚a pomyĹ›lnie zakoĹ„czona.",
            "zamkniete_zawory": zawory_do_zamkniecia
        }), 200

    except mysql.connector.Error as err:
        if conn: conn.rollback()
        return jsonify({"status": "error", "message": f"BĹ‚Ä…d bazy danych: {err}"}), 500
    finally:
        if conn and conn.is_connected():
            if 'cursor' in locals(): cursor.close()
            if 'write_cursor' in locals(): write_cursor.close()
            conn.close()

@bp.route('/aktywne', methods=['GET'])
def get_aktywne_operacje():
    """Zwraca listÄ™ wszystkich operacji ze statusem 'aktywna'."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT id, typ_operacji, id_partii_surowca, czas_rozpoczecia, opis 
        FROM operacje_log 
        WHERE status_operacji = 'aktywna'
        ORDER BY czas_rozpoczecia DESC
    """
    cursor.execute(query)
    operacje = cursor.fetchall()
    cursor.close()
    conn.close()
    # Musimy przekonwertowaÄ‡ datetime na string, bo JSON nie ma typu daty
    for op in operacje:
        op['czas_rozpoczecia'] = op['czas_rozpoczecia'].strftime('%Y-%m-%d %H:%M:%S')
    return jsonify(operacje)

@bp.route('/dobielanie', methods=['POST'])
def dobielanie():
    dane = request.get_json()
    if not dane or not all(k in dane for k in ['id_reaktora', 'ilosc_workow', 'waga_worka_kg']):
        return jsonify({"status": "error", "message": "Brak wymaganych pĂłl: id_reaktora, ilosc_workow, waga_worka_kg."}), 400

    id_reaktora = dane['id_reaktora']
    ilosc_workow = dane['ilosc_workow']
    waga_worka_kg = dane['waga_worka_kg']
    dodana_waga = ilosc_workow * waga_worka_kg

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # ZnajdĹş partiÄ™ w podanym reaktorze
        cursor.execute("SELECT id FROM partie_surowca WHERE id_sprzetu = %s", (id_reaktora,))
        partia = cursor.fetchone()
        if not partia:
            return jsonify({"status": "error", "message": f"W reaktorze o ID {id_reaktora} nie znaleziono ĹĽadnej partii."}), 404
        
        id_partii = partia['id']

        # --- Transakcja ---
        write_cursor = conn.cursor()

        # 1. Dodaj wpis do operacje_log
        opis = f"Dodano {ilosc_workow} workĂłw ziemi ({dodana_waga} kg) do partii {id_partii}"
        sql_log = "INSERT INTO operacje_log (typ_operacji, id_partii_surowca, czas_rozpoczecia, status_operacji, opis, ilosc_kg) VALUES ('DOBIELANIE', %s, NOW(), 'zakonczona', %s, %s)"
        write_cursor.execute(sql_log, (id_partii, opis, dodana_waga))

        # 2. Zaktualizuj wagÄ™ partii
        sql_waga = "UPDATE partie_surowca SET waga_aktualna_kg = waga_aktualna_kg + %s WHERE id = %s"
        write_cursor.execute(sql_waga, (dodana_waga, id_partii))

        # 3. Dodaj status "Dobielony" do partii
        # ZaĹ‚ĂłĹĽmy, ĹĽe ID statusu "Dobielony" to 3
        # UĹĽywamy INSERT IGNORE, aby uniknÄ…Ä‡ bĹ‚Ä™du, jeĹ›li partia juĹĽ ma ten status
        sql_status = "INSERT IGNORE INTO partie_statusy (id_partii, id_statusu) VALUES (%s, 3)"
        write_cursor.execute(sql_status, (id_partii,))
        
        conn.commit()

        return jsonify({"status": "success", "message": opis}), 200

    except mysql.connector.Error as err:
        if conn: conn.rollback()
        return jsonify({"status": "error", "message": f"BĹ‚Ä…d bazy danych: {err}"}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@bp.route('/tankowanie-brudnego', methods=['POST'])
def tankowanie_brudnego():
    """Tankowanie brudnego surowca z beczki do reaktora"""
    dane = request.get_json()
    
    # Walidacja wymaganych pĂłl
    wymagane_pola = ['id_beczki', 'id_reaktora', 'typ_surowca', 'waga_kg', 'temperatura_surowca']
    if not dane or not all(k in dane for k in wymagane_pola):
        return jsonify({'message': 'Brak wymaganych danych'}), 400

    # Walidacja wagi
    waga = float(dane['waga_kg'])
    if waga <= 0 or waga > 9000:
        return jsonify({'message': 'Waga musi byÄ‡ w zakresie 1-9000 kg'}), 400

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # SprawdĹş czy reaktor jest pusty
        cursor.execute("SELECT id, nazwa_unikalna, stan_sprzetu FROM sprzet WHERE id = %s", (dane['id_reaktora'],))
        reaktor = cursor.fetchone()
        
        if not reaktor:
            return jsonify({'message': 'Reaktor nie znaleziony'}), 404
            
        if reaktor['stan_sprzetu'] != 'Pusty':
            return jsonify({
                'message': f"Reaktor {reaktor['nazwa_unikalna']} nie jest pusty (stan: {reaktor['stan_sprzetu']})"
            }), 400

        # SprawdĹş czy beczka istnieje
        cursor.execute("SELECT id, nazwa_unikalna FROM sprzet WHERE id = %s", (dane['id_beczki'],))
        beczka = cursor.fetchone()
        
        if not beczka:
            return jsonify({'message': 'Beczka nie znaleziona'}), 404

        # Stworzenie unikalnego kodu partii
        teraz = datetime.now(timezone.utc)
        unikalny_kod = f"{dane['typ_surowca']}-{teraz.strftime('%Y%m%d-%H%M%S')}-{beczka['nazwa_unikalna']}"

        # UĹĽycie kursora bez dictionary=True do operacji zapisu
        write_cursor = conn.cursor()

        # Stworzenie nowej partii surowca
        sql_partia = """
            INSERT INTO partie_surowca 
            (unikalny_kod, typ_surowca, zrodlo_pochodzenia, waga_poczatkowa_kg, waga_aktualna_kg, 
             id_sprzetu, nazwa_partii, status_partii) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        nazwa_partii = f"PARTIA_{unikalny_kod}"
        partia_dane = (
            unikalny_kod, dane['typ_surowca'], 'cysterna', waga, waga, 
            dane['id_reaktora'], nazwa_partii, 'Surowy w reaktorze'
        )
        write_cursor.execute(sql_partia, partia_dane)
        nowa_partia_id = write_cursor.lastrowid

        # Nadanie statusu "Surowy" w tabeli partie_statusy
        write_cursor.execute("INSERT IGNORE INTO partie_statusy (id_partii, id_statusu) VALUES (%s, 1)", (nowa_partia_id,))

        # Aktualizacja stanu reaktora
        write_cursor.execute("UPDATE sprzet SET stan_sprzetu = 'Zatankowany (surowy)' WHERE id = %s", (dane['id_reaktora'],))

        # Zapisanie temperatury poczÄ…tkowej do operator_temperatures
        write_cursor.execute("""
            INSERT INTO operator_temperatures (id_sprzetu, temperatura, czas_ustawienia)
            VALUES (%s, %s, NOW())
        """, (dane['id_reaktora'], dane['temperatura_surowca']))

        # Zapisanie operacji w logu
        sql_log = """
            INSERT INTO operacje_log 
            (typ_operacji, id_partii_surowca, id_sprzetu_zrodlowego, id_sprzetu_docelowego, 
             czas_rozpoczecia, czas_zakonczenia, ilosc_kg, opis, status_operacji) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'zakonczona')
        """
        opis = f"Tankowanie brudnego surowca {dane['typ_surowca']} z {beczka['nazwa_unikalna']} do {reaktor['nazwa_unikalna']}"
        log_dane = (
            'TANKOWANIE_BRUDNEGO', nowa_partia_id, dane['id_beczki'], dane['id_reaktora'], 
            teraz, teraz, waga, opis
        )
        write_cursor.execute(sql_log, log_dane)
        
        conn.commit()
        
        return jsonify({
            'message': 'Tankowanie zakoĹ„czone pomyĹ›lnie',
            'partia_kod': unikalny_kod,
            'komunikat_operatorski': 'WĹ‚Ä…cz palnik i sprawdĹş temperaturÄ™ surowca na reaktorze',
            'reaktor': reaktor['nazwa_unikalna'],
            'temperatura_poczatkowa': dane['temperatura_surowca']
        }), 201

    except mysql.connector.Error as err:
        if conn: 
            conn.rollback()
        return jsonify({'message': f'BĹ‚Ä…d bazy danych: {str(err)}'}), 500
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'message': f'BĹ‚Ä…d: {str(e)}'}), 500
    finally:
        if conn and conn.is_connected():
            if 'cursor' in locals() and cursor: cursor.close()
            if 'write_cursor' in locals() and write_cursor: write_cursor.close()
            conn.close()

@bp.route('/transfer-reaktorow', methods=['POST'])
def transfer_reaktorow():
    """Transfer surowca z jednego reaktora do drugiego, opcjonalnie przez filtr"""
    dane = request.get_json()
    
    # Walidacja wymaganych pĂłl
    wymagane_pola = ['id_reaktora_zrodlowego', 'id_reaktora_docelowego']
    if not dane or not all(k in dane for k in wymagane_pola):
        return jsonify({'message': 'Brak wymaganych danych: id_reaktora_zrodlowego, id_reaktora_docelowego'}), 400

    # Opcjonalne pola
    id_filtra = dane.get('id_filtra')  # None = transfer bezpoĹ›redni
    tylko_podglad = dane.get('podglad', False)  # True = tylko podglÄ…d trasy, bez wykonania
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # SprawdĹş reaktor ĹşrĂłdĹ‚owy - czy ma surowiec
        cursor.execute("SELECT id, nazwa_unikalna, stan_sprzetu FROM sprzet WHERE id = %s", (dane['id_reaktora_zrodlowego'],))
        reaktor_zrodlowy = cursor.fetchone()
        
        if not reaktor_zrodlowy:
            return jsonify({'message': 'Reaktor ĹşrĂłdĹ‚owy nie znaleziony'}), 404
            
        if reaktor_zrodlowy['stan_sprzetu'] == 'Pusty':
            return jsonify({
                'message': f"Reaktor ĹşrĂłdĹ‚owy {reaktor_zrodlowy['nazwa_unikalna']} jest pusty - brak surowca do transferu"
            }), 400

        # SprawdĹş reaktor docelowy - czy jest pusty
        cursor.execute("SELECT id, nazwa_unikalna, stan_sprzetu FROM sprzet WHERE id = %s", (dane['id_reaktora_docelowego'],))
        reaktor_docelowy = cursor.fetchone()
        
        if not reaktor_docelowy:
            return jsonify({'message': 'Reaktor docelowy nie znaleziony'}), 404
            
        if reaktor_docelowy['stan_sprzetu'] != 'Pusty':
            return jsonify({
                'message': f"Reaktor docelowy {reaktor_docelowy['nazwa_unikalna']} nie jest pusty (stan: {reaktor_docelowy['stan_sprzetu']})"
            }), 400

        # SprawdĹş filtr jeĹ›li podany
        filtr_info = None
        if id_filtra:
            cursor.execute("SELECT id, nazwa_unikalna, stan_sprzetu FROM sprzet WHERE id = %s", (id_filtra,))
            filtr_info = cursor.fetchone()
            
            if not filtr_info:
                return jsonify({'message': 'Filtr nie znaleziony'}), 404

        # ZnajdĹş partiÄ™ w reaktorze ĹşrĂłdĹ‚owym (nie jest wymagana dla podglÄ…du)
        partia = None
        if not tylko_podglad:
            cursor.execute("""
                SELECT ps.id, ps.unikalny_kod, ps.typ_surowca, ps.waga_aktualna_kg, ps.nazwa_partii, ps.status_partii
                FROM partie_surowca ps 
                WHERE ps.id_sprzetu = %s
            """, (dane['id_reaktora_zrodlowego'],))
            partia = cursor.fetchone()
            
            if not partia:
                return jsonify({'message': f'Brak partii w reaktorze ĹşrĂłdĹ‚owym {reaktor_zrodlowy["nazwa_unikalna"]}'}), 404

        # Przygotuj punkty dla PathFinder
        punkt_startowy = f"{reaktor_zrodlowy['nazwa_unikalna']}_OUT"
        punkt_docelowy = f"{reaktor_docelowy['nazwa_unikalna']}_IN"
        
        # UĹĽyj PathFinder do znalezienia trasy
        pathfinder = get_pathfinder()
        wszystkie_zawory = [data['valve_name'] for u, v, data in pathfinder.graph.edges(data=True)]
        
        # DomyĹ›lne wartoĹ›ci
        opis_operacji = ""
        
        if id_filtra:
            # Transfer przez filtr
            punkt_filtr_in = f"{filtr_info['nazwa_unikalna']}_IN"
            punkt_filtr_out = f"{filtr_info['nazwa_unikalna']}_OUT"
            
            sciezka_1 = pathfinder.find_path(punkt_startowy, punkt_filtr_in, wszystkie_zawory)
            sciezka_filtr = pathfinder.find_path(punkt_filtr_in, punkt_filtr_out, wszystkie_zawory)
            sciezka_2 = pathfinder.find_path(punkt_filtr_out, punkt_docelowy, wszystkie_zawory)
            
            if not all([sciezka_1, sciezka_filtr, sciezka_2]):
                return jsonify({
                    'message': f'Nie moĹĽna znaleĹşÄ‡ trasy z {reaktor_zrodlowy["nazwa_unikalna"]} przez {filtr_info["nazwa_unikalna"]} do {reaktor_docelowy["nazwa_unikalna"]}'
                }), 404
                
            trasa_segmentow = sciezka_1 + sciezka_filtr + sciezka_2
            typ_operacji = f"Transfer {partia['typ_surowca']} z {reaktor_zrodlowy['nazwa_unikalna']} przez {filtr_info['nazwa_unikalna']} do {reaktor_docelowy['nazwa_unikalna']}"
            if not tylko_podglad and partia:
                opis_operacji = f"Transfer {partia['typ_surowca']} z {reaktor_zrodlowy['nazwa_unikalna']} przez {filtr_info['nazwa_unikalna']} do {reaktor_docelowy['nazwa_unikalna']}"
        else:
            # Transfer bezpoĹ›redni
            trasa_segmentow = pathfinder.find_path(punkt_startowy, punkt_docelowy, wszystkie_zawory)
            
            if not trasa_segmentow:
                return jsonify({
                    'message': f'Nie moĹĽna znaleĹşÄ‡ trasy bezpoĹ›redniej z {reaktor_zrodlowy["nazwa_unikalna"]} do {reaktor_docelowy["nazwa_unikalna"]}'
                }), 404
                
            typ_operacji = f"Transfer bezpoĹ›redni {partia['typ_surowca']} z {reaktor_zrodlowy['nazwa_unikalna']} do {reaktor_docelowy['nazwa_unikalna']}"
            if not tylko_podglad and partia:
                opis_operacji = f"Transfer bezpoĹ›redni {partia['typ_surowca']} z {reaktor_zrodlowy['nazwa_unikalna']} do {reaktor_docelowy['nazwa_unikalna']}"

        # SprawdĹş konflikty segmentĂłw
        if trasa_segmentow:
            placeholders_konflikt = ', '.join(['%s'] * len(trasa_segmentow))
            sql_konflikt = f"""
                SELECT s.nazwa_segmentu FROM log_uzyte_segmenty lus
                JOIN operacje_log ol ON lus.id_operacji_log = ol.id
                JOIN segmenty s ON lus.id_segmentu = s.id
                WHERE ol.status_operacji = 'aktywna' AND s.nazwa_segmentu IN ({placeholders_konflikt})
            """
            cursor.execute(sql_konflikt, trasa_segmentow)
            konflikty = cursor.fetchall()

            if konflikty and not tylko_podglad:  # Konflikty blokujÄ… tylko rzeczywisty transfer
                nazwy_zajetych = [k['nazwa_segmentu'] for k in konflikty]
                return jsonify({
                    'message': 'Konflikt zasobĂłw - niektĂłre segmenty sÄ… uĹĽywane przez inne operacje',
                    'zajete_segmenty': nazwy_zajetych
                }), 409

        # ZnajdĹş zawory do otwarcia
        zawory_do_otwarcia = set()
        for segment_name in trasa_segmentow:
            for u, v, data in pathfinder.graph.edges(data=True):
                if data['segment_name'] == segment_name:
                    zawory_do_otwarcia.add(data['valve_name'])
                    break

        # JeĹ›li to tylko podglÄ…d, zwrĂłÄ‡ informacje o trasie
        if tylko_podglad:
            return jsonify({
                'message': 'PodglÄ…d trasy transferu',
                'trasa': trasa_segmentow,
                'zawory': list(zawory_do_otwarcia),
                'segmenty_do_zablokowania': trasa_segmentow,
                'reaktor_zrodlowy': reaktor_zrodlowy['nazwa_unikalna'],
                'reaktor_docelowy': reaktor_docelowy['nazwa_unikalna'],
                'filtr': filtr_info['nazwa_unikalna'] if filtr_info else None,
                'przez_filtr': bool(id_filtra),
                'typ_operacji': typ_operacji
            }), 200

        # Rozpocznij operacjÄ™ w transakcji
        write_cursor = conn.cursor()
        
        # ZnajdĹş zawory do otwarcia
        zawory_do_otwarcia = set()
        for segment_name in trasa_segmentow:
            for u, v, data in pathfinder.graph.edges(data=True):
                if data['segment_name'] == segment_name:
                    zawory_do_otwarcia.add(data['valve_name'])
                    break
        
        # OtwĂłrz zawory
        if zawory_do_otwarcia:
            placeholders_zawory = ', '.join(['%s'] * len(zawory_do_otwarcia))
            sql_zawory = f"UPDATE zawory SET stan = 'OTWARTY' WHERE nazwa_zaworu IN ({placeholders_zawory})"
            write_cursor.execute(sql_zawory, list(zawory_do_otwarcia))

        # StwĂłrz operacjÄ™ w logu
        sql_log = """
            INSERT INTO operacje_log 
            (typ_operacji, id_sprzetu_zrodlowego, id_sprzetu_docelowego, id_partii_surowca, status_operacji, czas_rozpoczecia, opis, 
             punkt_startowy, punkt_docelowy, ilosc_kg) 
            VALUES (%s, %s, %s, %s, 'aktywna', NOW(), %s, %s, %s, %s)
        """
        write_cursor.execute(sql_log, (
            typ_operacji, 
            dane['id_reaktora_zrodlowego'], 
            dane['id_reaktora_docelowego'], 
            partia['id'], 
            opis_operacji, 
            punkt_startowy, 
            punkt_docelowy, 
            partia['waga_aktualna_kg']
        ))
        operacja_id = write_cursor.lastrowid

        # Zablokuj segmenty
        if trasa_segmentow:
            placeholders_segmenty = ', '.join(['%s'] * len(trasa_segmentow))
            sql_id_segmentow = f"SELECT id FROM segmenty WHERE nazwa_segmentu IN ({placeholders_segmenty})"
            cursor.execute(sql_id_segmentow, trasa_segmentow)
            id_segmentow = [row['id'] for row in cursor.fetchall()]

            sql_blokada = "INSERT INTO log_uzyte_segmenty (id_operacji_log, id_segmentu) VALUES (%s, %s)"
            dane_do_blokady = [(operacja_id, id_seg) for id_seg in id_segmentow]
            write_cursor.executemany(sql_blokada, dane_do_blokady)

        # Aktualizuj stan sprzÄ™tu
        write_cursor.execute("UPDATE sprzet SET stan_sprzetu = 'W transferze' WHERE id = %s", (dane['id_reaktora_zrodlowego'],))
        write_cursor.execute("UPDATE sprzet SET stan_sprzetu = 'W transferze' WHERE id = %s", (dane['id_reaktora_docelowego'],))
        
        if id_filtra:
            write_cursor.execute("UPDATE sprzet SET stan_sprzetu = 'W transferze' WHERE id = %s", (id_filtra,))

        conn.commit()

        return jsonify({
            'message': 'Transfer rozpoczÄ™ty pomyĹ›lnie',
            'operacja_id': operacja_id,
            'typ_operacji': typ_operacji,
            'partia_kod': partia['unikalny_kod'] if partia else None,
            'reaktor_zrodlowy': reaktor_zrodlowy['nazwa_unikalna'],
            'reaktor_docelowy': reaktor_docelowy['nazwa_unikalna'],
            'filtr': filtr_info['nazwa_unikalna'] if filtr_info else None,
            'przez_filtr': bool(id_filtra),
            'trasa': trasa_segmentow,
            'zawory': list(zawory_do_otwarcia),
            'trasa_segmentow': trasa_segmentow,  # Dla kompatybilnoĹ›ci wstecznej
            'zawory_otwarte': list(zawory_do_otwarcia),  # Dla kompatybilnoĹ›ci wstecznej
            'komunikat_operatorski': f'Transfer {typ_operacji.lower().replace("_", " ")} rozpoczÄ™ty. Monitoruj przebieg operacji.'
        }), 201

    except mysql.connector.Error as err:
        if conn: 
            conn.rollback()
        return jsonify({'message': f'BĹ‚Ä…d bazy danych: {str(err)}'}), 500
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'message': f'BĹ‚Ä…d: {str(e)}'}), 500
    finally:
        if conn and conn.is_connected():
            if 'cursor' in locals() and cursor: cursor.close()
            if 'write_cursor' in locals() and write_cursor: write_cursor.close()
            conn.close() 

@bp.route('/apollo-transfer/start', methods=['POST'])
def start_apollo_transfer():
    """Rozpoczyna operacjÄ™ transferu z Apollo, blokujÄ…c zasoby w `log_uzyte_segmenty`."""
    data = request.get_json()
    
    id_zrodla = data['id_zrodla']
    id_celu = data['id_celu']
    operator = data.get('operator', 'SYSTEM')
    
    conn = None
    read_cursor = None
    write_cursor = None
    try:
        conn = get_db_connection()
        read_cursor = conn.cursor(dictionary=True)

        read_cursor.execute("SELECT id, nazwa_unikalna, typ_sprzetu, stan_sprzetu FROM sprzet WHERE id IN (%s, %s)", (id_zrodla, id_celu))
        sprzety = {s['id']: s for s in read_cursor.fetchall()}
        zrodlo = sprzety.get(id_zrodla)
        cel = sprzety.get(id_celu)

        if not zrodlo or zrodlo['typ_sprzetu'].lower() != 'apollo':
            return jsonify({'message': 'NieprawidĹ‚owe ĹşrĂłdĹ‚o. Oczekiwano urzÄ…dzenia typu "apollo".'}), 400
        if not cel or cel['typ_sprzetu'].lower() not in ['reaktor', 'beczka_brudna']:
            return jsonify({'message': 'NieprawidĹ‚owy cel. Oczekiwano reaktora lub beczki brudnej.'}), 400

        if cel['stan_sprzetu'] != 'Pusty':
            print(f"OSTRZEĹ»ENIE: Cel operacji {cel['nazwa_unikalna']} nie jest pusty (stan: {cel['stan_sprzetu']}).")

        pathfinder = get_pathfinder()
        punkt_startowy = f"{zrodlo['nazwa_unikalna']}_OUT"
        punkt_docelowy = f"{cel['nazwa_unikalna']}_IN"
        
        wszystkie_zawory = [edge_data['valve_name'] for _, _, edge_data in pathfinder.graph.edges(data=True)]
        trasa_segmentow_nazwy = pathfinder.find_path(punkt_startowy, punkt_docelowy, wszystkie_zawory)

        if not trasa_segmentow_nazwy:
            return jsonify({'message': f'Nie moĹĽna znaleĹşÄ‡ trasy z {punkt_startowy} do {punkt_docelowy}'}), 404
            
        placeholders_konflikt = ', '.join(['%s'] * len(trasa_segmentow_nazwy))
        sql_konflikt = f"SELECT s.nazwa_segmentu FROM log_uzyte_segmenty lus JOIN operacje_log ol ON lus.id_operacji_log = ol.id JOIN segmenty s ON lus.id_segmentu = s.id WHERE ol.status_operacji = 'aktywna' AND s.nazwa_segmentu IN ({placeholders_konflikt})"
        read_cursor.execute(sql_konflikt, trasa_segmentow_nazwy)
        konflikty = read_cursor.fetchall()

        if konflikty:
            nazwy_zajetych = [k['nazwa_segmentu'] for k in konflikty]
            return jsonify({'message': 'Konflikt zasobĂłw - niektĂłre segmenty sÄ… uĹĽywane przez inne operacje.','zajete_segmenty': nazwy_zajetych}), 409

        write_cursor = conn.cursor()

        # NOWY KROK: OtwĂłrz zawory na trasie
        zawory_do_otwarcia = set()
        for segment_name in trasa_segmentow_nazwy:
            for u, v, data in pathfinder.graph.edges(data=True):
                if data.get('segment_name') == segment_name:
                    zawory_do_otwarcia.add(data['valve_name'])
                    break
        
        if zawory_do_otwarcia:
            placeholders_zawory = ', '.join(['%s'] * len(zawory_do_otwarcia))
            sql_zawory = f"UPDATE zawory SET stan = 'OTWARTY' WHERE nazwa_zaworu IN ({placeholders_zawory})"
            write_cursor.execute(sql_zawory, list(zawory_do_otwarcia))

        typ_operacji = 'ROZTANKOWANIE_APOLLO'
        opis_operacji = f"Transfer z {zrodlo['nazwa_unikalna']} do {cel['nazwa_unikalna']}"
        
        sql_log = "INSERT INTO operacje_log (typ_operacji, id_sprzetu_zrodlowego, id_sprzetu_docelowego, status_operacji, czas_rozpoczecia, opis, punkt_startowy, punkt_docelowy, zmodyfikowane_przez) VALUES (%s, %s, %s, 'aktywna', NOW(), %s, %s, %s, %s)"
        write_cursor.execute(sql_log, (typ_operacji, id_zrodla, id_celu, opis_operacji, punkt_startowy, punkt_docelowy, operator))
        operacja_id = write_cursor.lastrowid

        placeholders_segmenty = ', '.join(['%s'] * len(trasa_segmentow_nazwy))
        sql_id_segmentow = f"SELECT id FROM segmenty WHERE nazwa_segmentu IN ({placeholders_segmenty})"
        read_cursor.execute(sql_id_segmentow, trasa_segmentow_nazwy)
        id_segmentow = [row['id'] for row in read_cursor.fetchall()]

        sql_blokada = "INSERT INTO log_uzyte_segmenty (id_operacji_log, id_segmentu) VALUES (%s, %s)"
        dane_do_blokady = [(operacja_id, id_seg) for id_seg in id_segmentow]
        write_cursor.executemany(sql_blokada, dane_do_blokady)
        
        write_cursor.execute("UPDATE sprzet SET stan_sprzetu = 'W transferze' WHERE id = %s", (id_zrodla,))
        write_cursor.execute("UPDATE sprzet SET stan_sprzetu = 'W transferze' WHERE id = %s", (id_celu,))
        
        conn.commit()

        return jsonify({'message': 'Transfer rozpoczÄ™ty pomyĹ›lnie.','id_operacji': operacja_id}), 201

    except mysql.connector.Error as err:
        import traceback; traceback.print_exc()
        if conn and conn.is_connected(): conn.rollback()
        return jsonify({'message': f'BĹ‚Ä…d bazy danych: {str(err)}'}), 500
    except Exception as e:
        if conn and conn.is_connected(): conn.rollback()
        return jsonify({'message': f'BĹ‚Ä…d aplikacji: {str(e)}'}), 500
    finally:
        if read_cursor: read_cursor.close()
        if write_cursor: write_cursor.close()
        if conn and conn.is_connected(): conn.close()

@bp.route('/apollo-transfer/end', methods=['POST'])
def end_apollo_transfer():
    """KoĹ„czy operacjÄ™ transferu z Apollo, zwalnia zasoby i zarzÄ…dza partiami surowca."""
    data = request.get_json()
    
    conn = None
    try:
        id_operacji = int(data['id_operacji'])
        waga_kg = float(data['waga_kg'])
        operator = data.get('operator', 'SYSTEM')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Pobierz dane operacji
        cursor.execute("SELECT id_sprzetu_zrodlowego, id_sprzetu_docelowego FROM operacje_log WHERE id = %s", (id_operacji,))
        operacja = cursor.fetchone()
        if not operacja: raise ValueError('Nie znaleziono operacji o podanym ID.')
        
        id_apollo = operacja['id_sprzetu_zrodlowego']
        id_celu = operacja['id_sprzetu_docelowego']
        
        # ZnajdĹş sesjÄ™ Apollo i typ surowca
        cursor.execute("SELECT id, typ_surowca FROM apollo_sesje WHERE id_sprzetu = %s AND status_sesji = 'aktywna'", (id_apollo,))
        sesja = cursor.fetchone()
        if not sesja: raise ValueError('Nie znaleziono aktywnej sesji dla danego Apollo.')
        typ_surowca_zrodla = sesja['typ_surowca']

        # Pobierz nazwy sprzÄ™tu do generowania kodu partii
        cursor.execute("SELECT nazwa_unikalna FROM sprzet WHERE id = %s", (id_apollo,))
        zrodlo_info = cursor.fetchone()
        cursor.execute("SELECT nazwa_unikalna FROM sprzet WHERE id = %s", (id_celu,))
        cel_info = cursor.fetchone()
        zrodlo_nazwa = zrodlo_info['nazwa_unikalna'] if zrodlo_info else f"ID{id_apollo}"
        cel_nazwa = cel_info['nazwa_unikalna'] if cel_info else f"ID{id_celu}"

        # DODATKOWY KROK: ZnajdĹş partiÄ™ ĹşrĂłdĹ‚owÄ… w Apollo
        cursor.execute("SELECT * FROM partie_surowca WHERE id_sprzetu = %s LIMIT 1", (id_apollo,))
        partia_w_apollo = cursor.fetchone()
        if not partia_w_apollo:
            # To nie powinno siÄ™ zdarzyÄ‡ po zmianach w ApolloService, ale dodajemy zabezpieczenie
            raise ValueError(f"Nie znaleziono partii surowca dla Apollo o ID {id_apollo}.")

        # 1. ZakoĹ„cz operacjÄ™ w logu
        cursor.execute("""
            UPDATE operacje_log SET status_operacji = 'zakonczona', czas_zakonczenia = NOW(), ilosc_kg = %s, zmodyfikowane_przez = %s, id_apollo_sesji = %s
            WHERE id = %s
        """, (waga_kg, operator, sesja['id'], id_operacji))

        # 2. ZWOLNIJ ZASOBY (przywrĂłcona, poprawna logika)
        sql_znajdz_zawory = """
            SELECT DISTINCT z.nazwa_zaworu FROM zawory z
            JOIN segmenty s ON z.id = s.id_zaworu
            JOIN log_uzyte_segmenty lus ON s.id = lus.id_segmentu
            WHERE lus.id_operacji_log = %s
        """
        cursor.execute(sql_znajdz_zawory, (id_operacji,))
        zawory_do_zamkniecia = [row['nazwa_zaworu'] for row in cursor.fetchall()]

        if zawory_do_zamkniecia:
            placeholders = ', '.join(['%s'] * len(zawory_do_zamkniecia))
            sql_zamknij_zawory = f"UPDATE zawory SET stan = 'ZAMKNIETY' WHERE nazwa_zaworu IN ({placeholders})"
            cursor.execute(sql_zamknij_zawory, zawory_do_zamkniecia)

        # 3. Zaktualizuj stany sprzÄ™tu
        cursor.execute("UPDATE sprzet SET stan_sprzetu = 'Gotowy' WHERE id = %s", (id_apollo,))
        cursor.execute("UPDATE sprzet SET stan_sprzetu = 'Zatankowany' WHERE id = %s", (id_celu,))
        
        # 4. ZARZÄ„DZANIE PARTIAMI (nowa logika z `partie_skladniki`)
        cursor.execute("SELECT * FROM partie_surowca WHERE id_sprzetu = %s LIMIT 1", (id_celu,))
        partia_w_celu = cursor.fetchone()

        data_transferu = datetime.now(timezone.utc).strftime('%Y%m%d')
        czas_transferu = datetime.now(timezone.utc).strftime('%H%M%S')

        if partia_w_celu:
            typ_surowca_w_celu = partia_w_celu['typ_surowca']
            
            # JeĹ›li typy sÄ… takie same, po prostu zaktualizuj wagÄ™
            if typ_surowca_w_celu == typ_surowca_zrodla:
                nowa_waga = float(partia_w_celu['waga_aktualna_kg']) + waga_kg
                cursor.execute("UPDATE partie_surowca SET waga_aktualna_kg = %s WHERE id = %s", (nowa_waga, partia_w_celu['id']))
            else:
                # JeĹ›li typy sÄ… rĂłĹĽne - tworzymy mieszaninÄ™
                cursor.execute("UPDATE partie_surowca SET id_sprzetu = NULL, status_partii = 'Archiwalna' WHERE id = %s", (partia_w_celu['id'],))
                
                # Inteligentne tworzenie nowego typu mieszaniny
                skladniki_typow = set()
                if typ_surowca_w_celu.startswith('MIX('):
                    # WyciÄ…gnij istniejÄ…ce typy z MIX(...)
                    istniejace_typy = typ_surowca_w_celu[4:-1].split(',')
                    for t in istniejace_typy:
                        skladniki_typow.add(t.strip())
                else:
                    skladniki_typow.add(typ_surowca_w_celu)
                
                skladniki_typow.add(typ_surowca_zrodla)
                nowy_typ_mieszaniny = f"MIX({', '.join(sorted(list(skladniki_typow)))})"

                # Nowy, bardziej szczegĂłĹ‚owy opis
                nowa_waga = float(partia_w_celu['waga_aktualna_kg']) + waga_kg
                pochodzenie_opis = (f"Mieszanina stworzona z: "
                                    f"{partia_w_celu['waga_aktualna_kg']}kg partii '{partia_w_celu['unikalny_kod']}' ({typ_surowca_w_celu}) "
                                    f"oraz {waga_kg}kg transferu z Apollo ({typ_surowca_zrodla}).")
                
                unikalny_kod = f"MIX-{data_transferu}_{czas_transferu}-{zrodlo_nazwa}-{cel_nazwa}"
                
                cursor.execute("""
                    INSERT INTO partie_surowca (unikalny_kod, nazwa_partii, typ_surowca, waga_aktualna_kg, waga_poczatkowa_kg, id_sprzetu, zrodlo_pochodzenia, pochodzenie_opis, status_partii, typ_transformacji)
                    VALUES (%s, %s, %s, %s, %s, %s, 'apollo', %s, 'Surowy w reaktorze', 'MIESZANIE')
                """, (unikalny_kod, unikalny_kod, nowy_typ_mieszaniny, nowa_waga, nowa_waga, id_celu, pochodzenie_opis))
                nowa_partia_id = cursor.lastrowid

                # Zapisz skĹ‚adniki w nowej tabeli
                skladniki = [
                    (nowa_partia_id, partia_w_celu['id'], partia_w_celu['waga_aktualna_kg']),
                    (nowa_partia_id, partia_w_apollo['id'], waga_kg)
                ]
                cursor.executemany("""
                    INSERT INTO partie_skladniki (id_partii_wynikowej, id_partii_skladowej, waga_skladowa_kg)
                    VALUES (%s, %s, %s)
                """, skladniki)
        else:
            # Tworzenie nowej partii w pustym urzÄ…dzeniu
            pochodzenie_opis = f"Roztankowanie z {zrodlo_nazwa} w ramach operacji ID: {id_operacji}"
            unikalny_kod = f"{typ_surowca_zrodla.replace(' ', '_')}-{data_transferu}_{czas_transferu}-{zrodlo_nazwa}-{cel_nazwa}"
            
            cursor.execute("""
                INSERT INTO partie_surowca (unikalny_kod, nazwa_partii, typ_surowca, waga_aktualna_kg, waga_poczatkowa_kg, id_sprzetu, 
                zrodlo_pochodzenia, pochodzenie_opis, status_partii, data_utworzenia, typ_transformacji)
                VALUES (%s, %s, %s, %s, %s, %s, 'apollo', %s, 'Surowy w reaktorze', NOW(), 'TRANSFER')
            """, (unikalny_kod, unikalny_kod, typ_surowca_zrodla, waga_kg, waga_kg, id_celu, pochodzenie_opis))
            nowa_partia_id = cursor.lastrowid
            
            # PowiÄ…ĹĽ nowÄ… partiÄ™ z partiÄ… w Apollo
            cursor.execute("""
                INSERT INTO partie_skladniki (id_partii_wynikowej, id_partii_skladowej, waga_skladowa_kg)
                VALUES (%s, %s, %s)
            """, (nowa_partia_id, partia_w_apollo['id'], waga_kg))

        # 5. Zaktualizuj wagÄ™ partii w Apollo
        nowa_waga_apollo = float(partia_w_apollo['waga_aktualna_kg']) - waga_kg
        cursor.execute("UPDATE partie_surowca SET waga_aktualna_kg = %s WHERE id = %s", (nowa_waga_apollo, partia_w_apollo['id']))

        conn.commit()
        return jsonify({'success': True, 'message': f'Operacja {id_operacji} zakoĹ„czona.'})

    except (ValueError, KeyError) as e:
        if conn and conn.is_connected(): conn.rollback()
        return jsonify({'error': str(e)}), 400
    except mysql.connector.Error as err:
        if conn and conn.is_connected(): conn.rollback()
        return jsonify({'error': f'BĹ‚Ä…d bazy danych: {err}'}), 500
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if conn and conn.is_connected(): conn.close() 

@bp.route('/apollo-transfer/anuluj', methods=['POST'])
def anuluj_apollo_transfer():
    """Anuluje aktywny transfer, zwalnia zasoby i przywraca stany sprzÄ™tu."""
    data = request.get_json()
    if not data or 'id_operacji' not in data:
        return jsonify({'error': 'Brak wymaganego pola: id_operacji'}), 400

    id_operacji = data['id_operacji']
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Pobierz dane operacji
        cursor.execute("""
            SELECT id, status_operacji, id_sprzetu_zrodlowego, id_sprzetu_docelowego 
            FROM operacje_log WHERE id = %s
        """, (id_operacji,))
        operacja = cursor.fetchone()

        if not operacja:
            return jsonify({'error': 'Nie znaleziono operacji'}), 404
        if operacja['status_operacji'] != 'aktywna':
            return jsonify({'error': f"Nie moĹĽna anulowaÄ‡ operacji, ktĂłra nie jest aktywna (status: {operacja['status_operacji']})"}), 409

        # 1. ZmieĹ„ status operacji na 'anulowana'
        cursor.execute("UPDATE operacje_log SET status_operacji = 'anulowana' WHERE id = %s", (id_operacji,))

        # 2. Zwolnij zasoby (znajdĹş i zamknij zawory)
        sql_znajdz_zawory = """
            SELECT DISTINCT z.nazwa_zaworu FROM zawory z
            JOIN segmenty s ON z.id = s.id_zaworu
            JOIN log_uzyte_segmenty lus ON s.id = lus.id_segmentu
            WHERE lus.id_operacji_log = %s
        """
        cursor.execute(sql_znajdz_zawory, (id_operacji,))
        zawory_do_zamkniecia = [row['nazwa_zaworu'] for row in cursor.fetchall()]

        if zawory_do_zamkniecia:
            placeholders = ', '.join(['%s'] * len(zawory_do_zamkniecia))
            sql_zamknij_zawory = f"UPDATE zawory SET stan = 'ZAMKNIETY' WHERE nazwa_zaworu IN ({placeholders})"
            cursor.execute(sql_zamknij_zawory, zawory_do_zamkniecia)

        # 3. PrzywrĂłÄ‡ stan sprzÄ™tu (ĹşrĂłdĹ‚a i celu) do 'Gotowy'
        id_zrodla = operacja['id_sprzetu_zrodlowego']
        id_celu = operacja['id_sprzetu_docelowego']
        cursor.execute("UPDATE sprzet SET stan_sprzetu = 'Gotowy' WHERE id = %s", (id_celu))
        cursor.execute("UPDATE sprzet SET stan_sprzetu = 'Zatankowany' WHERE id = %s", (id_zrodla))
        conn.commit()

        return jsonify({'success': True, 'message': f'Operacja {id_operacji} zostaĹ‚a anulowana.'})

    except mysql.connector.Error as err:
        if conn and conn.is_connected(): conn.rollback()
        return jsonify({'error': f'BĹ‚Ä…d bazy danych: {err}'}), 500
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'write_cursor' in locals() and write_cursor: write_cursor.close()
        if conn and conn.is_connected(): conn.close() 

@bp.route('/roztankuj-cysterne/start', methods=['POST'])
def start_cysterna_transfer():
    """
    Rozpoczyna operacjÄ™ roztankowania cysterny.
    (Wersja zmodyfikowana, aby dziaĹ‚aÄ‡ jak oryginalna 'start_apollo_transfer')
    """
    data = request.get_json()
    required_fields = ['id_cysterny', 'id_celu']
    if not data or not all(k in data for k in required_fields):
        return jsonify({'message': 'Brak wymaganych danych: id_cysterny, id_celu'}), 400

    id_cysterny = data['id_cysterny']
    id_celu = data['id_celu']
    operator = data.get('operator', 'SYSTEM')
    # ZMIANA 1: PrzywrĂłcono pobieranie flagi 'force' (chociaĹĽ w tej logice nie jest uĹĽywana do stanu celu)
    force = data.get('force', False)

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id, nazwa_unikalna, typ_sprzetu, stan_sprzetu FROM sprzet WHERE id IN (%s, %s)", (id_cysterny, id_celu))
        sprzety = {s['id']: s for s in cursor.fetchall()}
        zrodlo = sprzety.get(int(id_cysterny))
        cel = sprzety.get(int(id_celu))

        # Walidacja specyficzna dla Cysterny
        if not zrodlo or zrodlo['typ_sprzetu'].lower() != 'cysterna':
            return jsonify({'message': 'NieprawidĹ‚owe ĹşrĂłdĹ‚o. Oczekiwano urzÄ…dzenia typu "cysterna".'}), 400
        if not cel or cel['typ_sprzetu'].lower() not in ['reaktor', 'beczka_brudna', 'zbiornik', 'beczka_czysta']:
            return jsonify({'message': 'NieprawidĹ‚owy cel. Oczekiwano reaktora, beczki brudnej, beczki czystej lub zbiornika.'}), 400
        
        # ZMIANA 2: Zamiast blokowaÄ‡, tylko drukujemy ostrzeĹĽenie (tak jak w oryginalnym start_apollo_transfer)
        if cel['stan_sprzetu'] != 'Pusty':
            print(f"OSTRZEĹ»ENIE: Cel operacji {cel['nazwa_unikalna']} nie jest pusty (stan: {cel['stan_sprzetu']}). Operacja bÄ™dzie kontynuowana.")
            # Nie zwracamy bĹ‚Ä™du, pozwalamy na dalsze wykonanie kodu.

        pathfinder = get_pathfinder()
        punkt_startowy = f"{zrodlo['nazwa_unikalna']}_OUT"
        punkt_docelowy = f"{cel['nazwa_unikalna']}_IN"
        
        wszystkie_zawory = [edge_data['valve_name'] for _, _, edge_data in pathfinder.graph.edges(data=True) if 'valve_name' in edge_data]
        trasa_segmentow_nazwy = pathfinder.find_path(punkt_startowy, punkt_docelowy, wszystkie_zawory)

        if not trasa_segmentow_nazwy:
            return jsonify({'message': f'Nie moĹĽna znaleĹşÄ‡ trasy z {punkt_startowy} do {punkt_docelowy}'}), 404

        placeholders_konflikt = ', '.join(['%s'] * len(trasa_segmentow_nazwy))
        sql_konflikt = f"SELECT s.nazwa_segmentu FROM log_uzyte_segmenty lus JOIN operacje_log ol ON lus.id_operacji_log = ol.id JOIN segmenty s ON lus.id_segmentu = s.id WHERE ol.status_operacji = 'aktywna' AND s.nazwa_segmentu IN ({placeholders_konflikt})"
        cursor.execute(sql_konflikt, trasa_segmentow_nazwy)
        konflikty = cursor.fetchall()
        
        # ZMIANA 3: Logika konfliktu, ktĂłra byĹ‚a oryginalnie w start_apollo_transfer
        # Uwaga: ta logika jest trochÄ™ dziwna, bo 'force' nie jest tutaj uĹĽywane
        if konflikty:
            nazwy_zajetych = [k['nazwa_segmentu'] for k in konflikty]
            return jsonify({
                'message': 'Konflikt zasobĂłw - niektĂłre segmenty sÄ… uĹĽywane.',
                'zajete_segmenty': nazwy_zajetych
            }), 409

        write_cursor = conn.cursor()

        zawory_do_otwarcia = set()
        for segment_name in trasa_segmentow_nazwy:
            for u, v, d in pathfinder.graph.edges(data=True):
                if d.get('segment_name') == segment_name and 'valve_name' in d:
                    zawory_do_otwarcia.add(d['valve_name'])
                    break
        if zawory_do_otwarcia:
            placeholders_zawory = ', '.join(['%s'] * len(zawory_do_otwarcia))
            sql_zawory = f"UPDATE zawory SET stan = 'OTWARTY' WHERE nazwa_zaworu IN ({placeholders_zawory})"
            write_cursor.execute(sql_zawory, list(zawory_do_otwarcia))

        typ_operacji = 'ROZTANKOWANIE_CYSTERNY'
        opis_operacji = f"Transfer z {zrodlo['nazwa_unikalna']} do {cel['nazwa_unikalna']}"

        sql_log = "INSERT INTO operacje_log (typ_operacji, id_sprzetu_zrodlowego, id_sprzetu_docelowego, status_operacji, czas_rozpoczecia, opis, punkt_startowy, punkt_docelowy, zmodyfikowane_przez) VALUES (%s, %s, %s, 'aktywna', NOW(), %s, %s, %s, %s)"
        write_cursor.execute(sql_log, (typ_operacji, id_cysterny, id_celu, opis_operacji, punkt_startowy, punkt_docelowy, operator))
        operacja_id = write_cursor.lastrowid

        placeholders_segmenty = ', '.join(['%s'] * len(trasa_segmentow_nazwy))
        sql_id_segmentow = f"SELECT id FROM segmenty WHERE nazwa_segmentu IN ({placeholders_segmenty})"
        cursor.execute(sql_id_segmentow, trasa_segmentow_nazwy)
        id_segmentow = [row['id'] for row in cursor.fetchall()]
        sql_blokada = "INSERT INTO log_uzyte_segmenty (id_operacji_log, id_segmentu) VALUES (%s, %s)"
        dane_do_blokady = [(operacja_id, id_seg) for id_seg in id_segmentow]
        write_cursor.executemany(sql_blokada, dane_do_blokady)

        write_cursor.execute("UPDATE sprzet SET stan_sprzetu = 'W transferze' WHERE id = %s", (id_cysterny,))
        write_cursor.execute("UPDATE sprzet SET stan_sprzetu = 'W transferze' WHERE id = %s", (id_celu,))
        
        conn.commit()
        return jsonify({'message': 'Roztankowanie cysterny rozpoczÄ™te pomyĹ›lnie.', 'id_operacji': operacja_id}), 201

    except mysql.connector.Error as err:
        if conn: conn.rollback()
        return jsonify({'message': f'BĹ‚Ä…d bazy danych: {str(err)}'}), 500
    except Exception as e:
        if conn: conn.rollback()
        traceback.print_exc()
        return jsonify({'message': f'BĹ‚Ä…d aplikacji: {str(e)}'}), 500
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'write_cursor' in locals() and write_cursor: write_cursor.close()
        if conn and conn.is_connected(): conn.close()

@bp.route('/roztankuj-cysterne/zakoncz', methods=['POST'])
def end_cysterna_transfer():
    """
    KoĹ„czy operacjÄ™ roztankowania cysterny i zarzÄ…dza partiami surowca.
    Wymaga: id_operacji, waga_netto_kg, typ_surowca, nr_rejestracyjny, nr_dokumentu_dostawy, nazwa_dostawcy.
    """
    data = request.get_json()
    required_fields = ['id_operacji', 'waga_netto_kg', 'typ_surowca', 'nr_rejestracyjny', 'nr_dokumentu_dostawy', 'nazwa_dostawcy']
    if not data or not all(k in data for k in required_fields):
        return jsonify({'message': 'Brak wszystkich wymaganych danych.'}), 400

    try:
        id_operacji = int(data['id_operacji'])
        waga_kg = float(data['waga_netto_kg'])
        typ_surowca_dostawy = data['typ_surowca']
    except (ValueError, TypeError):
        return jsonify({'message': 'NieprawidĹ‚owy format danych.'}), 400

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM operacje_log WHERE id = %s AND status_operacji = 'aktywna'", (id_operacji,))
        operacja = cursor.fetchone()
        if not operacja:
            return jsonify({'message': 'Nie znaleziono aktywnej operacji o podanym ID.'}), 404

        id_cysterny = operacja['id_sprzetu_zrodlowego']
        id_celu = operacja['id_sprzetu_docelowego']
        
        # Aktualizacja logu operacji
        opis_operacji = (f"Dostawca: {data['nazwa_dostawcy']}, "
                         f"Pojazd: {data['nr_rejestracyjny']}, "
                         f"Dokument: {data['nr_dokumentu_dostawy']}, "
                         f"Surowiec: {typ_surowca_dostawy}, "
                         f"Waga: {waga_kg} kg")
        cursor.execute("UPDATE operacje_log SET status_operacji = 'zakonczona', czas_zakonczenia = NOW(), ilosc_kg = %s, opis = %s WHERE id = %s", (waga_kg, opis_operacji, id_operacji))

        # Zwolnienie zasobĂłw (zawory)
        sql_znajdz_zawory = "SELECT DISTINCT z.nazwa_zaworu FROM zawory z JOIN segmenty s ON z.id = s.id_zaworu JOIN log_uzyte_segmenty lus ON s.id = lus.id_segmentu WHERE lus.id_operacji_log = %s"
        cursor.execute(sql_znajdz_zawory, (id_operacji,))
        zawory_do_zamkniecia = [row['nazwa_zaworu'] for row in cursor.fetchall()]
        if zawory_do_zamkniecia:
            placeholders = ', '.join(['%s'] * len(zawory_do_zamkniecia))
            sql_zamknij_zawory = f"UPDATE zawory SET stan = 'ZAMKNIETY' WHERE nazwa_zaworu IN ({placeholders})"
            cursor.execute(sql_zamknij_zawory, zawory_do_zamkniecia)
        
        # ZARZÄ„DZANIE PARTIAMI - analogicznie do /apollo-transfer/end
        cursor.execute("SELECT * FROM partie_surowca WHERE id_sprzetu = %s LIMIT 1", (id_celu,))
        partia_w_celu = cursor.fetchone()

        # Stworzenie "wirtualnej" partii dla dostawy
        unikalny_kod_dostawy = f"{typ_surowca_dostawy.replace(' ', '_')}-{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}-DOSTAWA"
        cursor.execute("""
            INSERT INTO partie_surowca (unikalny_kod, nazwa_partii, typ_surowca, waga_aktualna_kg, waga_poczatkowa_kg, id_sprzetu, zrodlo_pochodzenia, pochodzenie_opis, status_partii, data_utworzenia)
            VALUES (%s, %s, %s, %s, %s, NULL, 'cysterna', %s, 'Archiwalna', NOW())
        """, (unikalny_kod_dostawy, unikalny_kod_dostawy, typ_surowca_dostawy, waga_kg, waga_kg, opis_operacji))
        id_partii_z_dostawy = cursor.lastrowid

        if partia_w_celu:
            # Mieszanie z istniejÄ…cÄ… partiÄ…
            # 1. Archiwizuj starÄ… partiÄ™ w celu
            cursor.execute("UPDATE partie_surowca SET id_sprzetu = NULL, status_partii = 'Archiwalna' WHERE id = %s", (partia_w_celu['id'],))
            
            # 2. UtwĂłrz nowy typ mieszaniny
            typ_surowca_w_celu = partia_w_celu['typ_surowca']
            skladniki_typow = set()
            if typ_surowca_w_celu.startswith('MIX('):
                istniejace_typy = typ_surowca_w_celu[4:-1].split(',')
                skladniki_typow.update(t.strip() for t in istniejace_typy)
            else:
                skladniki_typow.add(typ_surowca_w_celu)
            skladniki_typow.add(typ_surowca_dostawy)
            nowy_typ_mieszaniny = f"MIX({', '.join(sorted(list(skladniki_typow)))})"
            
            # 3. UtwĂłrz nowÄ… partiÄ™ wynikowÄ… (mieszaninÄ™)
            nowa_waga = float(partia_w_celu['waga_aktualna_kg']) + waga_kg
            unikalny_kod_mix = f"MIX-{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            cursor.execute("""
                INSERT INTO partie_surowca (unikalny_kod, nazwa_partii, typ_surowca, waga_aktualna_kg, waga_poczatkowa_kg, id_sprzetu, status_partii, typ_transformacji)
                VALUES (%s, %s, %s, %s, %s, %s, 'Surowy w reaktorze', 'MIESZANIE')
            """, (unikalny_kod_mix, unikalny_kod_mix, nowy_typ_mieszaniny, nowa_waga, nowa_waga, id_celu))
            id_nowej_partii = cursor.lastrowid

            # 4. Zapisz skĹ‚adniki w `partie_skladniki`
            skladniki = [
                (id_nowej_partii, partia_w_celu['id'], partia_w_celu['waga_aktualna_kg']),
                (id_nowej_partii, id_partii_z_dostawy, waga_kg)
            ]
            cursor.executemany("INSERT INTO partie_skladniki (id_partii_wynikowej, id_partii_skladowej, waga_skladowa_kg) VALUES (%s, %s, %s)", skladniki)
        else:
            # Cel jest pusty, wiÄ™c po prostu "przenosimy" partiÄ™ z dostawy do celu
            cursor.execute("UPDATE partie_surowca SET id_sprzetu = %s, status_partii = 'Surowy w reaktorze' WHERE id = %s", (id_celu, id_partii_z_dostawy))

        # Aktualizacja stanu sprzÄ™tu
        cursor.execute("UPDATE sprzet SET stan_sprzetu = 'Pusty' WHERE id = %s", (id_cysterny,))
        cursor.execute("UPDATE sprzet SET stan_sprzetu = 'Zatankowany' WHERE id = %s", (id_celu,))
        
        conn.commit()
        return jsonify({'message': 'Operacja zakoĹ„czona pomyĹ›lnie. Utworzono i przetworzono nowÄ… partiÄ™ surowca.'}), 200

    except mysql.connector.Error as err:
        if conn: conn.rollback()
        # Dodaj wiÄ™cej szczegĂłĹ‚Ăłw do logu bĹ‚Ä™du
        traceback.print_exc()
        return jsonify({'message': f'BĹ‚Ä…d bazy danych: {str(err)}'}), 500
    except Exception as e:
        if conn: conn.rollback()
        traceback.print_exc()
        return jsonify({'message': f'WystÄ…piĹ‚ nieoczekiwany bĹ‚Ä…d: {str(e)}'}), 500
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

@bp.route('/roztankuj-cysterne/anuluj', methods=['POST'])

def anuluj_cysterna_transfer():
    """
    Anuluje aktywnÄ… operacjÄ™ roztankowania cysterny.
    Wymaga: id_operacji.
    """
    data = request.get_json()
    if not data or 'id_operacji' not in data:
        return jsonify({'error': 'Brak wymaganego pola: id_operacji'}), 400

    id_operacji = data['id_operacji']
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM operacje_log WHERE id = %s AND status_operacji = 'aktywna'", (id_operacji,))
        operacja = cursor.fetchone()
        if not operacja:
            return jsonify({'error': 'Nie znaleziono aktywnej operacji o podanym ID.'}), 404

        write_cursor = conn.cursor()
        write_cursor.execute("UPDATE operacje_log SET status_operacji = 'anulowana', czas_zakonczenia = NOW() WHERE id = %s", (id_operacji,))

        # Zwolnij zasoby (zamknij zawory)
        sql_znajdz_zawory = """
            SELECT DISTINCT z.nazwa_zaworu FROM zawory z
            JOIN segmenty s ON z.id = s.id_zaworu
            JOIN log_uzyte_segmenty lus ON s.id = lus.id_segmentu
            WHERE lus.id_operacji_log = %s
        """
        cursor.execute(sql_znajdz_zawory, (id_operacji,))
        zawory_do_zamkniecia = [row['nazwa_zaworu'] for row in cursor.fetchall()]
        if zawory_do_zamkniecia:
            placeholders = ', '.join(['%s'] * len(zawory_do_zamkniecia))
            sql_zamknij_zawory = f"UPDATE zawory SET stan = 'ZAMKNIETY' WHERE nazwa_zaworu IN ({placeholders})"
            write_cursor.execute(sql_zamknij_zawory, zawory_do_zamkniecia)

        # PrzywrĂłÄ‡ stan sprzÄ™tu do 'Pusty'
        id_zrodla = operacja['id_sprzetu_zrodlowego']
        id_celu = operacja['id_sprzetu_docelowego']
        write_cursor.execute("UPDATE sprzet SET stan_sprzetu = 'Pusty' WHERE id = %s", (id_zrodla,))
        write_cursor.execute("UPDATE sprzet SET stan_sprzetu = 'Pusty' WHERE id = %s", (id_celu,))

        conn.commit()
        return jsonify({'success': True, 'message': f'Operacja {id_operacji} zostaĹ‚a anulowana.'})

    except mysql.connector.Error as err:
        if conn: conn.rollback()
        return jsonify({'error': f'BĹ‚Ä…d bazy danych: {err}'}), 500
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'write_cursor' in locals() and write_cursor: write_cursor.close()
        if conn and conn.is_connected(): conn.close()
# app/pathfinder_service.py

import networkx as nx
from .db import get_db_connection  # Importujemy funkcjÄ™ do poĹ‚Ä…czenia z bazÄ… danych
import mysql.connector # Added for mysql.connector.Error

class PathFinder:
    def __init__(self, app=None):
        self.graph = nx.DiGraph()
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """Metoda do inicjalizacji serwisu w kontekĹ›cie aplikacji Flask."""
        import sys
        print("INFO: Inicjalizacja PathFinder...")
        sys.stdout.flush()
        # Przechowujemy referencjÄ™ do aplikacji, aby mieÄ‡ dostÄ™p do konfiguracji
        self.app = app
        # Wczytujemy topologiÄ™ uĹĽywajÄ…c kontekstu aplikacji
        with app.app_context():
            self._load_topology()

    def _get_db_connection(self):
        """Prywatna metoda do Ĺ‚Ä…czenia siÄ™ z bazÄ…, uĹĽywajÄ…ca konfiguracji z aplikacji."""
        return get_db_connection()

    def _load_topology(self):
        """Wczytuje mapÄ™ instalacji z bazy danych."""
        print("INFO: Rozpoczynanie Ĺ‚adowania topologii...")
        conn = self._get_db_connection()
        # ... reszta tej metody pozostaje bez zmian ...
        cursor = conn.cursor(dictionary=True)
        # ...
        cursor.execute("SELECT nazwa_portu FROM porty_sprzetu")
        for row in cursor.fetchall():
            self.graph.add_node(row['nazwa_portu'])

        cursor.execute("SELECT nazwa_wezla FROM wezly_rurociagu")
        for row in cursor.fetchall():
            self.graph.add_node(row['nazwa_wezla'])

        query = """
            SELECT 
                s.nazwa_segmentu, 
                z.nazwa_zaworu,
                COALESCE(p_start.nazwa_portu, w_start.nazwa_wezla) AS punkt_startowy,
                COALESCE(p_koniec.nazwa_portu, w_koniec.nazwa_wezla) AS punkt_koncowy
            FROM segmenty s
            JOIN zawory z ON s.id_zaworu = z.id
            LEFT JOIN porty_sprzetu p_start ON s.id_portu_startowego = p_start.id
            LEFT JOIN wezly_rurociagu w_start ON s.id_wezla_startowego = w_start.id
            LEFT JOIN porty_sprzetu p_koniec ON s.id_portu_koncowego = p_koniec.id
            LEFT JOIN wezly_rurociagu w_koniec ON s.id_wezla_koncowego = w_koniec.id
        """
        cursor.execute(query)
        for row in cursor.fetchall():
            self.graph.add_edge(
                row['punkt_startowy'], 
                row['punkt_koncowy'], 
                segment_name=row['nazwa_segmentu'],
                valve_name=row['nazwa_zaworu']
            )
        
        cursor.close()
        conn.close()

        print("INFO: Topologia instalacji zaĹ‚adowana, graf zbudowany.")


    def find_path(self, start_node, end_node, open_valves=None):
        """Znajduje najkrĂłtszÄ… Ĺ›cieĹĽkÄ™ miÄ™dzy wÄ™zĹ‚ami"""
        print(f"DEBUG: PathFinder.find_path called with start='{start_node}', end='{end_node}'")
        
        # JeĹ›li nie podano stanĂłw zaworĂłw, pobierz z bazy lub uĹĽyj wszystkich
        if open_valves is None:
            open_valves = self._get_open_valves()
        
        print(f"DEBUG: Using open_valves: {open_valves[:5]}... (total: {len(open_valves)})")
        
        # SprawdĹş czy wÄ™zĹ‚y istniejÄ… w grafie
        if start_node not in self.graph.nodes():
            print(f"ERROR: Start node '{start_node}' not found in graph")
            print(f"Available nodes: {list(self.graph.nodes())[:10]}...")
            return None
            
        if end_node not in self.graph.nodes():
            print(f"ERROR: End node '{end_node}' not found in graph")
            print(f"Available nodes: {list(self.graph.nodes())[:10]}...")
            return None
        
        temp_graph = self.graph.copy()
        print(f"DEBUG: Temp graph has {len(temp_graph.nodes())} nodes and {len(temp_graph.edges())} edges")
        
        edges_to_remove = []
        for u, v, data in temp_graph.edges(data=True):
            if data['valve_name'] not in open_valves:
                edges_to_remove.append((u, v))
        
        print(f"DEBUG: Removing {len(edges_to_remove)} edges due to closed valves")
        temp_graph.remove_edges_from(edges_to_remove)
        print(f"DEBUG: After removal: {len(temp_graph.edges())} edges remain")

        try:
            path_nodes = nx.shortest_path(temp_graph, source=start_node, target=end_node)
            print(f"DEBUG: Found path nodes: {path_nodes}")
            
            path_segments = []
            for i in range(len(path_nodes) - 1):
                edge_data = self.graph.get_edge_data(path_nodes[i], path_nodes[i+1])
                if edge_data:
                    path_segments.append(edge_data['segment_name'])
            
            print(f"DEBUG: Path segments: {path_segments}")
            return path_segments
        except (nx.NetworkXNoPath, nx.NodeNotFound) as e:
            print(f"DEBUG: No path found - {type(e).__name__}: {e}")
            return None
    
    def _get_open_valves(self):
        """Pobiera listÄ™ otwartych zaworĂłw z bazy danych"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # SprawdĹş otwarte zawory (stan = 'OTWARTY')
            cursor.execute("SELECT nazwa_zaworu FROM zawory WHERE stan = 'OTWARTY'")
            open_valves = [row['nazwa_zaworu'] for row in cursor.fetchall()]
            
            # JeĹ›li nie ma otwartych zaworĂłw, zwrĂłÄ‡ wszystkie jako otwarte (dla testĂłw)
            if not open_valves:
                print("WARNING: Brak otwartych zaworĂłw w bazie. UĹĽywam wszystkich zaworĂłw dla testĂłw PathFinder.")
                cursor.execute("SELECT nazwa_zaworu FROM zawory")
                open_valves = [row['nazwa_zaworu'] for row in cursor.fetchall()]
            
            cursor.close()
            conn.close()
            
            return open_valves
        except Exception as e:
            print(f"BĹ‚Ä…d podczas pobierania stanĂłw zaworĂłw: {e}")
            # W przypadku bĹ‚Ä™du, zwrĂłÄ‡ wszystkie zawory jako otwarte
            try:
                conn = self._get_db_connection()
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT nazwa_zaworu FROM zawory")
                all_valves = [row['nazwa_zaworu'] for row in cursor.fetchall()]
                cursor.close()
                conn.close()
                return all_valves
            except Exception as ex:
                print(f"BĹ‚Ä…d podczas pobierania wszystkich zaworĂłw: {ex}")
                return []

    @staticmethod
    def release_path(zawory_names=None, segment_names=None):
        """Zwalnia zasoby po zakoĹ„czeniu operacji - zamyka zawory."""
        if not zawory_names:
            print("INFO: Brak zaworĂłw do zwolnienia w release_path.")
            return

        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Zamykanie zaworĂłw
            if isinstance(zawory_names, str):
                zawory_names = zawory_names.split(',')
            
            if zawory_names:
                placeholders = ', '.join(['%s'] * len(zawory_names))
                sql = f"UPDATE zawory SET stan = 'ZAMKNIETY' WHERE nazwa_zaworu IN ({placeholders})"
                cursor.execute(sql, zawory_names)

            # W przyszĹ‚oĹ›ci moĹĽna dodaÄ‡ logikÄ™ zwalniania segmentĂłw, jeĹ›li bÄ™dzie potrzebna
            
            conn.commit()
            print(f"INFO: PomyĹ›lnie zamkniÄ™to zawory: {zawory_names}")

        except mysql.connector.Error as err:
            if conn:
                conn.rollback()
            print(f"BĹ‚Ä…d bazy danych podczas zwalniania Ĺ›cieĹĽki: {err}")
            # Rzucenie wyjÄ…tku, aby operacja nadrzÄ™dna mogĹ‚a go obsĹ‚uĹĽyÄ‡
            raise
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()

# USUWAMY globalnÄ… instancjÄ™. BÄ™dziemy jÄ… tworzyÄ‡ w __init__.py
# pathfinder_instance = PathFinder()
# app/pathfinder_tester.py
# type: ignore

import mysql.connector
from flask import current_app, jsonify
from datetime import datetime
from .db import get_db_connection
from .pathfinder_service import PathFinder
import json

class PathFinderTester:
    """Tester poĹ‚Ä…czeĹ„ PathFinder do analizy dostÄ™pnoĹ›ci tras i optymalizacji Ĺ›cieĹĽek"""
    
    def __init__(self):
        self.pathfinder = None
    
    def get_pathfinder(self):
        """Pobiera instancjÄ™ PathFinder"""
        if not self.pathfinder:
            try:
                self.pathfinder = current_app.extensions.get('pathfinder')
            except:
                # Fallback - tworzenie nowej instancji
                self.pathfinder = PathFinder()
        return self.pathfinder
    
    def test_connection_availability(self, start_point, end_point, valve_states=None):
        """Testuje dostÄ™pnoĹ›Ä‡ poĹ‚Ä…czenia miÄ™dzy dwoma punktami"""
        try:
            pathfinder = self.get_pathfinder()
            
            # JeĹ›li podano stany zaworĂłw, zastosuj je tymczasowo
            original_states = {}
            if valve_states:
                original_states = self._apply_valve_states(valve_states)
            
            # ZnajdĹş Ĺ›cieĹĽkÄ™
            path = pathfinder.find_path(start_point, end_point)
            
            # PrzywrĂłÄ‡ oryginalne stany zaworĂłw
            if valve_states:
                self._restore_valve_states(original_states)
            
            if path:
                return {
                    'available': True,
                    'path': path,
                    'path_length': len(path),
                    'segments_used': self._get_segments_for_path(path),
                    'message': f"Znaleziono Ĺ›cieĹĽkÄ™ z {start_point} do {end_point}"
                }
            else:
                return {
                    'available': False,
                    'path': None,
                    'path_length': 0,
                    'segments_used': [],
                    'message': f"Brak dostÄ™pnej Ĺ›cieĹĽki z {start_point} do {end_point}"
                }
        except Exception as e:
            return {
                'available': False,
                'path': None,
                'error': str(e),
                'message': f"BĹ‚Ä…d podczas testowania poĹ‚Ä…czenia: {str(e)}"
            }
    
    def find_all_paths(self, start_point, end_point, max_paths=5):
        """Znajduje wszystkie moĹĽliwe Ĺ›cieĹĽki miÄ™dzy punktami"""
        try:
            pathfinder = self.get_pathfinder()
            
            # ZnajdĹş gĹ‚ĂłwnÄ… Ĺ›cieĹĽkÄ™
            main_path = pathfinder.find_path(start_point, end_point)
            if not main_path:
                return {
                    'paths': [],
                    'count': 0,
                    'message': f"Brak dostÄ™pnych Ĺ›cieĹĽek z {start_point} do {end_point}"
                }
            
            paths = [main_path]
            
            # SprĂłbuj znaleĹşÄ‡ alternatywne Ĺ›cieĹĽki poprzez blokowanie segmentĂłw gĹ‚Ăłwnej Ĺ›cieĹĽki
            for i in range(1, max_paths):
                # Tymczasowo zablokuj niektĂłre segmenty z poprzednich Ĺ›cieĹĽek
                blocked_segments = self._get_segments_to_block(paths)
                alt_path = self._find_alternative_path(start_point, end_point, blocked_segments)
                
                if alt_path and alt_path not in paths:
                    paths.append(alt_path)
                else:
                    break
            
            return {
                'paths': [
                    {
                        'path': path,
                        'length': len(path),
                        'segments': self._get_segments_for_path(path),
                        'estimated_cost': self._calculate_path_cost(path)
                    } for path in paths
                ],
                'count': len(paths),
                'message': f"Znaleziono {len(paths)} Ĺ›cieĹĽek z {start_point} do {end_point}"
            }
        except Exception as e:
            return {
                'paths': [],
                'count': 0,
                'error': str(e),
                'message': f"BĹ‚Ä…d podczas wyszukiwania Ĺ›cieĹĽek: {str(e)}"
            }
    
    def simulate_valve_states(self, valve_changes):
        """Symuluje zmiany stanĂłw zaworĂłw i testuje wpĹ‚yw na dostÄ™pnoĹ›Ä‡ tras"""
        try:
            results = []
            
            # Zapisz oryginalne stany zaworĂłw
            original_states = self._get_current_valve_states()
            
            for test_case in valve_changes:
                valve_name = test_case.get('valve_name')
                new_state = test_case.get('new_state')
                test_routes = test_case.get('test_routes', [])
                
                # Zastosuj zmianÄ™ stanu zaworu
                self._set_valve_state(valve_name, new_state)
                
                # Przetestuj wpĹ‚yw na trasy
                route_results = []
                for route in test_routes:
                    start = route.get('start')
                    end = route.get('end')
                    
                    result = self.test_connection_availability(start, end)
                    route_results.append({
                        'route': f"{start} -> {end}",
                        'available': result['available'],
                        'path_length': result['path_length'],
                        'message': result['message']
                    })
                
                results.append({
                    'valve_change': f"{valve_name}: {new_state}",
                    'route_results': route_results,
                    'overall_impact': self._assess_valve_impact(route_results)
                })
            
            # PrzywrĂłÄ‡ oryginalne stany zaworĂłw
            self._restore_valve_states(original_states)
            
            return {
                'simulation_results': results,
                'message': f"Wykonano symulacjÄ™ dla {len(valve_changes)} zmian zaworĂłw"
            }
        except Exception as e:
            # Upewnij siÄ™, ĹĽe stany zaworĂłw sÄ… przywrĂłcone nawet w przypadku bĹ‚Ä™du
            try:
                self._restore_valve_states(original_states)
            except:
                pass
            
            return {
                'simulation_results': [],
                'error': str(e),
                'message': f"BĹ‚Ä…d podczas symulacji: {str(e)}"
            }
    
    def analyze_critical_valves(self):
        """Analizuje krytyczne zawory - ktĂłrych zamkniÄ™cie blokuje najwiÄ™cej tras"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Pobierz wszystkie zawory i moĹĽliwe trasy
            cursor.execute("SELECT * FROM zawory ORDER BY nazwa_zaworu")
            zawory = cursor.fetchall()
            
            # Pobierz wszystkie moĹĽliwe punkty poczÄ…tkowe i koĹ„cowe
            cursor.execute("""
                SELECT DISTINCT nazwa_portu as punkt FROM porty_sprzetu
                UNION
                SELECT DISTINCT nazwa_wezla as punkt FROM wezly_rurociagu
                ORDER BY punkt
            """)
            punkty = [row['punkt'] for row in cursor.fetchall()]
            
            cursor.close()
            conn.close()
            
            # Analizuj kaĹĽdy zawĂłr
            critical_analysis = []
            
            for zawor in zawory:
                if zawor['stan'] == 'OTWARTY':
                    # Symuluj zamkniÄ™cie tego zaworu
                    blocked_routes = 0
                    affected_routes = []
                    
                    # Tymczasowo zamknij zawĂłr
                    self._set_valve_state(zawor['nazwa_zaworu'], 'ZAMKNIETY')
                    
                    # Testuj losowe pary punktĂłw
                    for i, start in enumerate(punkty[:10]):  # Ograniczamy do 10 punktĂłw dla wydajnoĹ›ci
                        for end in punkty[i+1:11]:  # Testuj z nastÄ™pnymi punktami
                            if start != end:
                                result = self.test_connection_availability(start, end)
                                if not result['available']:
                                    blocked_routes += 1
                                    affected_routes.append(f"{start} -> {end}")
                    
                    # PrzywrĂłÄ‡ stan zaworu
                    self._set_valve_state(zawor['nazwa_zaworu'], 'OTWARTY')
                    
                    critical_analysis.append({
                        'valve_name': zawor['nazwa_zaworu'],
                        'blocked_routes_count': blocked_routes,
                        'affected_routes': affected_routes[:5],  # PokaĹĽ tylko pierwsze 5
                        'criticality_score': blocked_routes,
                        'is_critical': blocked_routes > 0
                    })
            
            # Sortuj wedĹ‚ug krytycznoĹ›ci
            critical_analysis.sort(key=lambda x: x['criticality_score'], reverse=True)
            
            return {
                'critical_valves': critical_analysis,
                'most_critical': critical_analysis[0] if critical_analysis else None,
                'total_valves_analyzed': len(zawory),
                'message': f"Przeanalizowano {len(zawory)} zaworĂłw pod kÄ…tem krytycznoĹ›ci"
            }
        except Exception as e:
            return {
                'critical_valves': [],
                'error': str(e),
                'message': f"BĹ‚Ä…d podczas analizy krytycznych zaworĂłw: {str(e)}"
            }
    
    def get_test_history(self, limit=50):
        """Pobiera historiÄ™ testĂłw PathFinder"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # SprawdĹş czy istnieje tabela z historiÄ… testĂłw
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM information_schema.tables 
                WHERE table_schema = 'mes_parafina_db' 
                AND table_name = 'pathfinder_test_history'
            """)
            
            if cursor.fetchone()['count'] == 0:
                # UtwĂłrz tabelÄ™ jeĹ›li nie istnieje
                cursor.execute("""
                    CREATE TABLE pathfinder_test_history (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        test_type VARCHAR(50) NOT NULL,
                        start_point VARCHAR(100),
                        end_point VARCHAR(100),
                        test_parameters JSON,
                        result JSON,
                        success BOOLEAN,
                        execution_time_ms INT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
            
            # Pobierz historiÄ™ testĂłw
            cursor.execute("""
                SELECT * FROM pathfinder_test_history 
                ORDER BY created_at DESC 
                LIMIT %s
            """, (limit,))
            
            history = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            return {
                'test_history': history,
                'count': len(history),
                'message': f"Pobrano {len(history)} zapisĂłw z historii testĂłw"
            }
        except Exception as e:
            return {
                'test_history': [],
                'error': str(e),
                'message': f"BĹ‚Ä…d podczas pobierania historii testĂłw: {str(e)}"
            }
    
    def save_test_result(self, test_type, start_point, end_point, test_parameters, result, success, execution_time_ms):
        """Zapisuje wynik testu do historii"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO pathfinder_test_history 
                (test_type, start_point, end_point, test_parameters, result, success, execution_time_ms)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (test_type, start_point, end_point, json.dumps(test_parameters), 
                  json.dumps(result), success, execution_time_ms))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return True
        except Exception as e:
            return False
    
    # ================== METODY POMOCNICZE ==================
    
    def _apply_valve_states(self, valve_states):
        """Stosuje tymczasowe stany zaworĂłw i zwraca oryginalne stany"""
        original_states = {}
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            for valve_name, new_state in valve_states.items():
                # Pobierz oryginalny stan
                cursor.execute("SELECT stan FROM zawory WHERE nazwa_zaworu = %s", (valve_name,))
                result = cursor.fetchone()
                if result:
                    original_states[valve_name] = result['stan']
                    
                    # Ustaw nowy stan
                    cursor.execute("""
                        UPDATE zawory SET stan = %s WHERE nazwa_zaworu = %s
                    """, (new_state, valve_name))
            
            conn.commit()
            return original_states
        finally:
            cursor.close()
            conn.close()
    
    def _restore_valve_states(self, original_states):
        """Przywraca oryginalne stany zaworĂłw"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            for valve_name, original_state in original_states.items():
                cursor.execute("""
                    UPDATE zawory SET stan = %s WHERE nazwa_zaworu = %s
                """, (original_state, valve_name))
            
            conn.commit()
        finally:
            cursor.close()
            conn.close()
    
    def _get_current_valve_states(self):
        """Pobiera aktualne stany wszystkich zaworĂłw"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute("SELECT nazwa_zaworu, stan FROM zawory")
            results = cursor.fetchall()
            return {row['nazwa_zaworu']: row['stan'] for row in results}
        finally:
            cursor.close()
            conn.close()
    
    def _set_valve_state(self, valve_name, new_state):
        """Ustawia stan zaworu"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE zawory SET stan = %s WHERE nazwa_zaworu = %s
            """, (new_state, valve_name))
            conn.commit()
        finally:
            cursor.close()
            conn.close()
    
    def _get_segments_for_path(self, path):
        """Pobiera segmenty dla danej Ĺ›cieĹĽki"""
        if not path or len(path) < 2:
            return []
        
        segments = []
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            for i in range(len(path) - 1):
                start_point = path[i]
                end_point = path[i + 1]
                
                # ZnajdĹş segment Ĺ‚Ä…czÄ…cy te punkty
                cursor.execute("""
                    SELECT s.nazwa_segmentu, z.nazwa_zaworu, z.stan
                    FROM segmenty s
                    JOIN zawory z ON s.id_zaworu = z.id
                    LEFT JOIN porty_sprzetu ps_start ON s.id_portu_startowego = ps_start.id
                    LEFT JOIN porty_sprzetu ps_end ON s.id_portu_koncowego = ps_end.id
                    LEFT JOIN wezly_rurociagu ws_start ON s.id_wezla_startowego = ws_start.id
                    LEFT JOIN wezly_rurociagu ws_end ON s.id_wezla_koncowego = ws_end.id
                    WHERE (
                        (ps_start.nazwa_portu = %s AND ps_end.nazwa_portu = %s) OR
                        (ps_start.nazwa_portu = %s AND ps_end.nazwa_portu = %s) OR
                        (ps_start.nazwa_portu = %s AND ws_end.nazwa_wezla = %s) OR
                        (ws_start.nazwa_wezla = %s AND ps_end.nazwa_portu = %s) OR
                        (ws_start.nazwa_wezla = %s AND ws_end.nazwa_wezla = %s) OR
                        (ws_start.nazwa_wezla = %s AND ws_end.nazwa_wezla = %s)
                    )
                """, (start_point, end_point, end_point, start_point,
                      start_point, end_point, start_point, end_point,
                      start_point, end_point, end_point, start_point))
                
                segment = cursor.fetchone()
                if segment:
                    segments.append({
                        'segment_name': segment['nazwa_segmentu'],
                        'valve_name': segment['nazwa_zaworu'],
                        'valve_state': segment['stan']
                    })
            
            return segments
        finally:
            cursor.close()
            conn.close()
    
    def _get_segments_to_block(self, existing_paths):
        """OkreĹ›la segmenty do zablokowania dla znajdowania alternatywnych Ĺ›cieĹĽek"""
        segments_to_block = []
        for path in existing_paths:
            path_segments = self._get_segments_for_path(path)
            for segment in path_segments:
                if segment['segment_name'] not in segments_to_block:
                    segments_to_block.append(segment['segment_name'])
        return segments_to_block[:2]  # Blokuj maksymalnie 2 segmenty
    
    def _find_alternative_path(self, start_point, end_point, blocked_segments):
        """Znajduje alternatywnÄ… Ĺ›cieĹĽkÄ™ z pominiÄ™ciem zablokowanych segmentĂłw"""
        # Tymczasowo zamknij zawory w blokowanych segmentach
        original_states = {}
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            for segment_name in blocked_segments:
                cursor.execute("""
                    SELECT z.nazwa_zaworu, z.stan 
                    FROM segmenty s
                    JOIN zawory z ON s.id_zaworu = z.id
                    WHERE s.nazwa_segmentu = %s
                """, (segment_name,))
                
                result = cursor.fetchone()
                if result:
                    original_states[result['nazwa_zaworu']] = result['stan']
                    cursor.execute("""
                        UPDATE zawory SET stan = 'ZAMKNIETY' WHERE nazwa_zaworu = %s
                    """, (result['nazwa_zaworu'],))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            # ZnajdĹş alternatywnÄ… Ĺ›cieĹĽkÄ™
            pathfinder = self.get_pathfinder()
            alternative_path = pathfinder.find_path(start_point, end_point)
            
            return alternative_path
        except Exception as e:
            return None
        finally:
            # PrzywrĂłÄ‡ oryginalne stany zaworĂłw
            self._restore_valve_states(original_states)
    
    def _calculate_path_cost(self, path):
        """Oblicza szacunkowy koszt Ĺ›cieĹĽki (im krĂłtsze, tym lepsze)"""
        if not path:
            return float('inf')
        
        # Prosty koszt bazowany na dĹ‚ugoĹ›ci Ĺ›cieĹĽki
        base_cost = len(path) - 1
        
        # Dodaj koszt za wykorzystanie krytycznych segmentĂłw
        segments = self._get_segments_for_path(path)
        critical_penalty = sum(1 for seg in segments if seg['valve_state'] == 'ZAMKNIETY')
        
        return base_cost + critical_penalty * 10
    
    def _assess_valve_impact(self, route_results):
        """Ocenia ogĂłlny wpĹ‚yw zmiany stanu zaworu"""
        if not route_results:
            return 'brak_danych'
        
        total_routes = len(route_results)
        blocked_routes = sum(1 for result in route_results if not result['available'])
        
        if blocked_routes == 0:
            return 'brak_wpĹ‚ywu'
        elif blocked_routes < total_routes / 2:
            return 'umiarkowany_wpĹ‚yw'
        else:
            return 'duĹĽy_wpĹ‚yw'
# app/routes.py

from flask import Blueprint, jsonify, request, current_app, render_template, g
from datetime import datetime, timedelta
from .sensors import SensorService  # Importujemy serwis czujnikĂłw
import mysql.connector
import time
from .db import get_db_connection  # Importujemy funkcjÄ™ do poĹ‚Ä…czenia z bazÄ… danych
from .pathfinder_service import PathFinder
from .apollo_service import ApolloService  # Importujemy serwis Apollo
from mysql.connector.errors import OperationalError
from decimal import Decimal

def get_pathfinder():
    if 'pathfinder' not in g:
        g.pathfinder = PathFinder(get_db_connection())
    return g.pathfinder

def get_sensor_service():
    """Pobiera instancjÄ™ serwisu SensorService z kontekstu aplikacji."""
    return current_app.extensions['sensor_service']

# 1. Stworzenie obiektu Blueprint
# Pierwszy argument to nazwa blueprintu, drugi to nazwa moduĹ‚u (standardowo __name__)
# 'url_prefix' sprawi, ĹĽe wszystkie endpointy w tym pliku bÄ™dÄ… zaczynaÄ‡ siÄ™ od /api
bp = Blueprint('api', __name__, url_prefix='/')
# sensor_service = SensorService()



@bp.route('/')
def index():
    """Serwuje gĹ‚ĂłwnÄ… stronÄ™ aplikacji (frontend)."""
    return render_template('index.html')

# --- DODAJ TÄ NOWÄ„ FUNKCJÄ ---
@bp.route('/alarms')
def show_alarms():
    """WyĹ›wietla stronÄ™ z historiÄ… wszystkich alarmĂłw."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Pobierz wszystkie alarmy, sortujÄ…c od najnowszych
        cursor.execute("""
            SELECT * FROM alarmy 
            ORDER BY czas_wystapienia DESC
        """)
        all_alarms = cursor.fetchall()
        return render_template('alarms.html', alarms=all_alarms)
    finally:
        cursor.close()
        conn.close()
# --- KONIEC NOWEJ FUNKCJI ---

# --- DODAJ TÄ NOWÄ„ FUNKCJÄ ---
@bp.route('/operacje')
def show_operacje():
    """WyĹ›wietla stronÄ™ z operacjami tankowania."""
    return render_template('operacje.html')

@bp.route('/operacje-apollo')
def show_operacje_apollo():
    """WyĹ›wietla stronÄ™ do zarzÄ…dzania transferami z Apollo."""
    return render_template('operacje_apollo.html')

@bp.route('/operacje-cysterny')
def operacje_cysterny():
    """Strona do zarzÄ…dzania operacjami roztankowania cystern."""
    return render_template('operacje_cysterny.html')

@bp.route('/beczki')
def beczki():
    """Strona do zarzÄ…dzania operacjami roztankowania cystern."""
    return render_template('beczki.html')
# --- KONIEC NOWEJ FUNKCJI ---

# 2. Stworzenie pierwszego, prawdziwego endpointu API
@bp.route('/api/sprzet', methods=['GET'])
def get_sprzet():
    """Zwraca listÄ™ caĹ‚ego sprzÄ™tu WRAZ z informacjÄ… o znajdujÄ…cej siÄ™ w nim partii."""
    from .db import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # UĹĽywamy LEFT JOIN, aby pokazaÄ‡ sprzÄ™t nawet jeĹ›li jest pusty
    query = """
        SELECT 
            s.id, s.nazwa_unikalna, s.typ_sprzetu, s.stan_sprzetu,
            /* UĹĽywamy ANY_VALUE() dla wszystkich kolumn z tabeli 'p', 
               ktĂłre nie sÄ… w GROUP BY ani w funkcji agregujÄ…cej */
            ANY_VALUE(p.id) as id_partii, 
            ANY_VALUE(p.unikalny_kod) as unikalny_kod, 
            ANY_VALUE(p.typ_surowca) as typ_surowca, 
            ANY_VALUE(p.waga_aktualna_kg) as waga_aktualna_kg,
            
            /* Ta kolumna juĹĽ jest zagregowana, wiÄ™c jej nie ruszamy */
            GROUP_CONCAT(st.nazwa_statusu SEPARATOR ', ') AS statusy_partii
        FROM sprzet s
        LEFT JOIN partie_surowca p ON s.id = p.id_sprzetu
        LEFT JOIN partie_statusy ps ON p.id = ps.id_partii
        LEFT JOIN statusy st ON ps.id_statusu = st.id
        GROUP BY s.id  /* Grupowanie pozostaje bez zmian */
        ORDER BY s.typ_sprzetu, s.nazwa_unikalna;
    """
    cursor.execute(query)
    sprzet_list = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify(sprzet_list)

@bp.route('/api/zawory', methods=['GET'])
def get_wszystkie_zawory():
    """Zwraca listÄ™ wszystkich zaworĂłw i ich aktualny stan."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nazwa_zaworu, stan FROM zawory ORDER BY nazwa_zaworu")
    zawory = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(zawory)

@bp.route('/api/zawory/zmien_stan', methods=['POST'])
def zmien_stan_zaworu():
    """Zmienia stan pojedynczego zaworu."""
    dane = request.get_json()
    if not dane or 'id_zaworu' not in dane or 'stan' not in dane:
        return jsonify({"status": "error", "message": "Brak wymaganych pĂłl: id_zaworu, stan."}), 400
    
    id_zaworu = dane['id_zaworu']
    nowy_stan = dane['stan'] # Oczekujemy 'OTWARTY' lub 'ZAMKNIETY'

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE zawory SET stan = %s WHERE id = %s", (nowy_stan, id_zaworu))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"status": "success", "message": f"Zmieniono stan zaworu {id_zaworu} na {nowy_stan}."})

@bp.route('/api/punkty_startowe', methods=['GET'])
def get_punkty_startowe():
    """Zwraca listÄ™ wszystkich portĂłw wyjĹ›ciowych (OUT)."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Wybieramy porty ze sprzÄ™tu, ktĂłry moĹĽe byÄ‡ ĹşrĂłdĹ‚em (np. nie beczki czyste)
    query = """
        SELECT p.nazwa_portu, s.nazwa_unikalna as nazwa_sprzetu 
        FROM porty_sprzetu p
        JOIN sprzet s ON p.id_sprzetu = s.id
        WHERE p.typ_portu = 'OUT' AND s.typ_sprzetu != 'beczka_czysta'
        ORDER BY s.nazwa_unikalna
    """
    cursor.execute(query)
    porty = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(porty)

@bp.route('/api/punkty_docelowe', methods=['GET'])
def get_punkty_docelowe():
    """Zwraca listÄ™ wszystkich portĂłw wejĹ›ciowych (IN)."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Wybieramy porty ze sprzÄ™tu, ktĂłry moĹĽe byÄ‡ celem (np. nie beczki brudne)
    query = """
        SELECT p.nazwa_portu, s.nazwa_unikalna as nazwa_sprzetu 
        FROM porty_sprzetu p
        JOIN sprzet s ON p.id_sprzetu = s.id
        WHERE p.typ_portu = 'IN' AND s.typ_sprzetu NOT IN ('beczka_brudna', 'apollo')
        ORDER BY s.nazwa_unikalna
    """
    cursor.execute(query)
    porty = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(porty)

@bp.route('/api/sprzet/filtry', methods=['GET'])
def get_filtry():
    """Zwraca listÄ™ filtrĂłw."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nazwa_unikalna FROM sprzet WHERE typ_sprzetu = 'filtr'")
    filtry = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(filtry)

@bp.route('/api/topologia', methods=['GET'])
def get_topologia():
    """Zwraca peĹ‚nÄ… listÄ™ poĹ‚Ä…czeĹ„ (segmentĂłw) do wizualizacji."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # To samo zapytanie, ktĂłrego uĹĽywa PathFinder do budowy grafu
    query = """
        SELECT 
            s.id as id_segmentu,
            s.nazwa_segmentu, 
            z.nazwa_zaworu,
            z.stan as stan_zaworu,
            -- Dodajemy ID dla debugowania
            s.id_portu_startowego, s.id_wezla_startowego,
            s.id_portu_koncowego, s.id_wezla_koncowego,
            COALESCE(p_start.nazwa_portu, w_start.nazwa_wezla) AS punkt_startowy,
            COALESCE(p_koniec.nazwa_portu, w_koniec.nazwa_wezla) AS punkt_koncowy
        FROM segmenty s
        JOIN zawory z ON s.id_zaworu = z.id
        LEFT JOIN porty_sprzetu p_start ON s.id_portu_startowego = p_start.id
        LEFT JOIN wezly_rurociagu w_start ON s.id_wezla_startowego = w_start.id
        LEFT JOIN porty_sprzetu p_koniec ON s.id_portu_koncowego = p_koniec.id
        LEFT JOIN wezly_rurociagu w_koniec ON s.id_wezla_koncowego = w_koniec.id
    """
    cursor.execute(query)
    segmenty = cursor.fetchall()

    # Dodatkowo, pobierzmy listÄ™ aktualnie zajÄ™tych segmentĂłw
    sql_zajete = """
        SELECT s.id as id_segmentu FROM log_uzyte_segmenty lus
        JOIN operacje_log ol ON lus.id_operacji_log = ol.id
        JOIN segmenty s ON lus.id_segmentu = s.id
        WHERE ol.status_operacji = 'aktywna'
    """
    cursor.execute(sql_zajete)
    zajete_ids = {row['id_segmentu'] for row in cursor.fetchall()}

    # Dodaj informacjÄ™ o zajÄ™toĹ›ci do kaĹĽdego segmentu
    for seg in segmenty:
        seg['zajety'] = seg.get('id_segmentu') in zajete_ids

    cursor.close()
    conn.close()
    return jsonify(segmenty)

@bp.route('/api/sprzet/pomiary', methods=['GET'])
def get_aktualne_pomiary_sprzetu():
    """
    Zwraca listÄ™ caĹ‚ego sprzÄ™tu wraz z jego aktualnymi odczytami temperatury i ciĹ›nienia,
    bezpoĹ›rednio z tabeli `sprzet`.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Zapytanie jest teraz bardzo proste, poniewaĹĽ wszystkie potrzebne dane sÄ… w jednej tabeli.
    query = """
        SELECT
            id,
            nazwa_unikalna,
            typ_sprzetu,
            stan_sprzetu,
            temperatura_aktualna,
            cisnienie_aktualne,
            temperatura_docelowa,
            temperatura_max,
            cisnienie_max,
            ostatnia_aktualizacja
        FROM sprzet
        ORDER BY typ_sprzetu, nazwa_unikalna;
    """
    
    try:
        cursor.execute(query)
        sprzet_pomiary = cursor.fetchall()
        
        # Sformatuj datÄ™ ostatniej aktualizacji, aby byĹ‚a przyjazna dla formatu JSON
        for sprzet in sprzet_pomiary:
            if sprzet.get('ostatnia_aktualizacja'):
                sprzet['ostatnia_aktualizacja'] = sprzet.get('ostatnia_aktualizacja').strftime('%Y-%m-%d %H:%M:%S')
            
        return jsonify(sprzet_pomiary)
        
    except Exception as e:
        return jsonify({'error': f'BĹ‚Ä…d bazy danych: {str(e)}'}), 500
        
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/trasy/sugeruj', methods=['POST'])
def sugeruj_trase():
    """
    Na podstawie punktu startowego, koĹ„cowego i poĹ›redniego, znajduje
    najkrĂłtszÄ… moĹĽliwÄ… trasÄ™ i zwraca listÄ™ segmentĂłw oraz zaworĂłw
    potrzebnych do jej otwarcia. Ignoruje aktualny stan zaworĂłw.
    """
    dane = request.get_json()
    if not dane or 'start' not in dane or 'cel' not in dane:
        return jsonify({"status": "error", "message": "Brak wymaganych pĂłl: start, cel."}), 400

    start_point = dane['start']
    end_point = dane['cel']
    sprzet_posredni = dane.get('sprzet_posredni')
    
    pathfinder = get_pathfinder()
    
    # WAĹ»NE: Do szukania "idealnej" trasy przekazujemy WSZYSTKIE zawory jako otwarte.
    # W tym celu pobieramy ich nazwy z grafu Pathfindera.
    wszystkie_zawory = [data['valve_name'] for u, v, data in pathfinder.graph.edges(data=True)]
    
    sciezka_segmentow = []
    sciezka_zaworow = set() # UĹĽywamy seta, aby uniknÄ…Ä‡ duplikatĂłw zaworĂłw

    try :
        if sprzet_posredni:
            posredni_in = f"{sprzet_posredni}_IN"
            posredni_out = f"{sprzet_posredni}_OUT"

            # Trasa do sprzÄ™tu poĹ›redniego
            sciezka_1 = pathfinder.find_path(start_point, posredni_in, wszystkie_zawory)
            # Trasa wewnÄ…trz sprzÄ™tu poĹ›redniego
            sciezka_wewnetrzna = pathfinder.find_path(posredni_in, posredni_out, wszystkie_zawory)
            # Trasa od sprzÄ™tu poĹ›redniego do celu
            sciezka_2 = pathfinder.find_path(posredni_out, end_point, wszystkie_zawory)

            if not all([sciezka_1, sciezka_wewnetrzna, sciezka_2]):
                raise Exception("Nie moĹĽna zbudowaÄ‡ peĹ‚nej trasy przez punkt poĹ›redni.")

            sciezka_segmentow = sciezka_1 + sciezka_wewnetrzna + sciezka_2
        else:
            sciezka_segmentow = pathfinder.find_path(start_point, end_point, wszystkie_zawory)

        if not sciezka_segmentow:
            raise Exception("Nie znaleziono Ĺ›cieĹĽki.")

        # Na podstawie nazw segmentĂłw, znajdĹş nazwy przypisanych do nich zaworĂłw
        for segment_name in sciezka_segmentow:
            # Przeszukujemy krawÄ™dzie grafu, aby znaleĹşÄ‡ zawĂłr dla danego segmentu
            for u, v, data in pathfinder.graph.edges(data=True):
                if data['segment_name'] == segment_name:
                    sciezka_zaworow.add(data['valve_name'])
                    break
        
        return jsonify({
            "status": "success",
            "sugerowane_zawory": sorted(list(sciezka_zaworow)),
            "segmenty_trasy": sciezka_segmentow
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Nie moĹĽna byĹ‚o wytyczyÄ‡ trasy: {e}"
        }), 404

@bp.route('/api/alarmy/aktywne', methods=['GET'])
def get_aktywne_alarmy():
    """Zwraca listÄ™ aktywnych alarmĂłw"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT id, typ_alarmu, nazwa_sprzetu, wartosc, limit_przekroczenia, 
                   czas_wystapienia, status_alarmu 
            FROM alarmy 
            WHERE status_alarmu = 'AKTYWNY'
            ORDER BY czas_wystapienia DESC
        """)
        alarmy = cursor.fetchall()
        
        # Konwertuj datetime na string
        for alarm in alarmy:
            alarm['czas_wystapienia'] = alarm.get('czas_wystapienia').strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify(alarmy)
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/test/sensors', methods=['POST'])
def test_sensors():
    """Endpoint testowy do wymuszenia odczytu czujnikĂłw"""
    try:
        sensor_service = get_sensor_service() # <--- ZMIEĹ TÄ LINIÄ
        sensor_service.read_sensors()
        return jsonify({'message': 'Odczyt czujnikĂłw wykonany pomyĹ›lnie'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/pomiary/historia', methods=['GET'])
def get_historia_pomiarow():
    """Pobiera historiÄ™ pomiarĂłw z ostatnich 24 godzin"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Pobierz dane z ostatnich 24h
        cursor.execute("""
            SELECT h.*, s.nazwa_unikalna, s.typ_sprzetu
            FROM historia_pomiarow h
            JOIN sprzet s ON h.id_sprzetu = s.id
            WHERE h.czas_pomiaru > %s
            ORDER BY h.czas_pomiaru DESC
        """, (datetime.now(timezone.utc) - timedelta(hours=24),))
        
        pomiary = cursor.fetchall()
        
        # Formatuj daty do JSON
        for pomiar in pomiary:
            pomiar['czas_pomiaru'] = pomiar.get('czas_pomiaru').strftime('%Y-%m-%d %H:%M:%S')
            
        return jsonify(pomiary)
        
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/alarmy/potwierdz', methods=['POST'])
def potwierdz_alarm():
    """Endpoint do potwierdzania alarmĂłw"""
    dane = request.get_json()
    id_alarmu = dane.get('id_alarmu')
    
    if not id_alarmu:
        return jsonify({'message': 'Brak ID alarmu'}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE alarmy 
            SET status_alarmu = 'POTWIERDZONY',
                czas_potwierdzenia = %s
            WHERE id = %s AND status_alarmu = 'AKTYWNY'
        """, (datetime.now(timezone.utc), id_alarmu))
        
        conn.commit()
        
        if cursor.rowcount == 0:
            return jsonify({'message': 'Alarm nie znaleziony lub juĹĽ potwierdzony'}), 404
            
        return jsonify({'message': 'Alarm potwierdzony pomyĹ›lnie'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'message': f'BĹ‚Ä…d bazy danych: {str(e)}'}), 500
        
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/test/alarm', methods=['POST'])
def test_alarm():
    """Endpoint do testowania alarmĂłw"""
    try:
        dane = request.get_json()
        if not dane:
            return jsonify({'message': 'Brak danych w ĹĽÄ…daniu'}), 400
            
        sprzet_id = dane.get('sprzet_id')
        typ_alarmu = dane.get('typ_alarmu', 'temperatura')
        
        if not sprzet_id:
            return jsonify({'message': 'Brak ID sprzÄ™tu'}), 400
            
        if typ_alarmu not in ['temperatura', 'cisnienie']:
            return jsonify({'message': 'NieprawidĹ‚owy typ alarmu'}), 400
        sensor_service = get_sensor_service() # <--- ZMIEĹ TÄ LINIÄ    
        sensor_service.force_alarm(sprzet_id, typ_alarmu)
        return jsonify({'message': f'Wymuszono alarm {typ_alarmu} dla sprzÄ™tu ID={sprzet_id}'})
        
    except ValueError as ve:
        return jsonify({'message': str(ve)}), 400
    except Exception as e:
        return jsonify({'message': f'BĹ‚Ä…d serwera: {str(e)}'}), 500

@bp.route('/api/sprzet/<int:sprzet_id>/temperatura', methods=['POST'])
def set_temperatura(sprzet_id):
    """Ustawia docelowÄ… temperaturÄ™ dla danego sprzÄ™tu."""
    dane = request.get_json()
    nowa_temperatura = dane['temperatura']
    
    try:
        # Delegujemy caĹ‚Ä… pracÄ™ do serwisu
        sensor_service = get_sensor_service()
        sensor_service.set_temperature(sprzet_id, nowa_temperatura)
        
        return jsonify({"status": "success", "message": "Temperatura ustawiona."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"BĹ‚Ä…d serwera: {e}"}), 500
    

@bp.route('/filtry')
def show_filtry_panel():
    """Renderuje stronÄ™ z panelem monitoringu filtrĂłw."""
    return render_template('filtry_scada.html')

# NOWY, ZAAWANSOWANY ENDPOINT DO MONITORINGU FILTRĂ“W
@bp.route('/api/filtry/status')
def get_filtry_status_scada():
    """
    Zwraca kompletny, szczegĂłĹ‚owy status dla kaĹĽdego filtra (FZ i FN)
    na potrzeby interfejsu SCADA. Zawiera:
    - Podstawowe dane i parametry (temperatura, ciĹ›nienie).
    - Informacje o aktywnej operacji i przetwarzanej partii.
    - Planowany czas zakoĹ„czenia operacji.
    - ListÄ™ partii oczekujÄ…cych w kolejce (jeĹ›li filtr jest wolny).
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 1. Pobierz podstawowe dane o filtrach, w tym ich parametry fizyczne
        cursor.execute("""
            SELECT 
                id, nazwa_unikalna, stan_sprzetu, typ_sprzetu,
                temperatura_aktualna, cisnienie_aktualne, poziom_aktualny_procent,
                temperatura_max, cisnienie_max, ostatnia_aktualizacja
            FROM sprzet 
            WHERE typ_sprzetu = 'filtr'
            ORDER BY nazwa_unikalna
        """)
        filtry = cursor.fetchall()
        
        # SĹ‚ownik z definicjami czasĂłw trwania operacji w minutach
        DURATIONS = {
            'Budowanie placka': 30, 'Filtrowanie w koĹ‚o': 15, 'Przedmuchiwanie': 10,
            'Dmuchanie filtra': 45, 'Czyszczenie': 20, 'TRANSFER': 30, 'FILTRACJA': 30
        }

        # 2. Dla kaĹĽdego filtra, wzbogaÄ‡ go o dane operacyjne
        for filtr in filtry:
            filtr['aktywna_operacja'] = None
            filtr['kolejka_oczekujacych'] = []
            
            # 2a. SprawdĹş, czy filtr jest uĹĽywany w jakiejĹ› aktywnej operacji
            # UĹĽywamy zĹ‚Ä…czenia z log_uzyte_segmenty, aby to ustaliÄ‡
            cursor.execute("""
                SELECT
                    ol.id as id_operacji, ol.typ_operacji, ol.czas_rozpoczecia, ol.status_operacji,
                    ol.opis as opis_operacji,
                    ps.id as id_partii, ps.unikalny_kod, ps.nazwa_partii, ps.typ_surowca,
                    zrodlo.nazwa_unikalna AS sprzet_zrodlowy,
                    cel.nazwa_unikalna AS sprzet_docelowy
                FROM sprzet s
                JOIN porty_sprzetu ps_port ON s.id = ps_port.id_sprzetu
                JOIN segmenty seg ON ps_port.id = seg.id_portu_startowego OR ps_port.id = seg.id_portu_koncowego
                JOIN log_uzyte_segmenty lus ON seg.id = lus.id_segmentu
                JOIN operacje_log ol ON lus.id_operacji_log = ol.id
                LEFT JOIN partie_surowca ps ON ol.id_partii_surowca = ps.id
                LEFT JOIN sprzet zrodlo ON ol.id_sprzetu_zrodlowego = zrodlo.id
                LEFT JOIN sprzet cel ON ol.id_sprzetu_docelowego = cel.id
                WHERE ol.status_operacji = 'aktywna' AND s.id = %s
                LIMIT 1
            """, (filtr['id'],))
            
            aktywna_operacja = cursor.fetchone()
            
            if aktywna_operacja:
                filtr['aktywna_operacja'] = aktywna_operacja
                # Oblicz i dodaj planowany czas zakoĹ„czenia
                typ_op = aktywna_operacja.get('typ_operacji')
                czas_start = aktywna_operacja.get('czas_rozpoczecia')
                if typ_op in DURATIONS and czas_start:
                    duration_minutes = DURATIONS[typ_op]
                    end_time = czas_start + timedelta(minutes=duration_minutes)
                    filtr['aktywna_operacja']['czas_zakonczenia_iso'] = end_time.isoformat()
                else:
                    filtr['aktywna_operacja']['czas_zakonczenia_iso'] = None
            else:
                # 2b. JeĹ›li filtr nie jest zajÄ™ty, sprawdĹş, czy ktoĹ› na niego czeka
                # To sÄ… partie, ktĂłre majÄ… w polu `id_aktualnego_filtra` nazwÄ™ tego filtra
                cursor.execute("""
                    SELECT 
                        ps.id as id_partii, ps.unikalny_kod, ps.nazwa_partii,
                        ps.aktualny_etap_procesu, s.nazwa_unikalna as nazwa_reaktora
                    FROM partie_surowca ps
                    JOIN sprzet s ON ps.id_aktualnego_sprzetu = s.id
                    WHERE ps.id_aktualnego_filtra = %s AND ps.status_partii NOT IN ('Gotowy do wysĹ‚ania', 'W magazynie czystym')
                    ORDER BY ps.czas_rozpoczecia_etapu ASC
                """, (filtr['nazwa_unikalna'],))
                filtr['kolejka_oczekujacych'] = cursor.fetchall()

        return jsonify(filtry)
        
    except Exception as e:
        # ZwrĂłÄ‡ bĹ‚Ä…d w formacie JSON dla Ĺ‚atwiejszego debugowania na froncie
        return jsonify({'error': f'BĹ‚Ä…d po stronie serwera: {str(e)}'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# === NOWE API DLA ZARZÄ„DZANIA CYKLAMI FILTRACYJNYMI ===

@bp.route('/api/cykle-filtracyjne/<int:id_partii>')
def get_cykle_partii(id_partii):
    """Pobiera historiÄ™ wszystkich cykli filtracyjnych dla danej partii."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT cf.*, 
                   ps.unikalny_kod, ps.typ_surowca, ps.nazwa_partii,
                   TIMESTAMPDIFF(MINUTE, cf.czas_rozpoczecia, cf.czas_zakonczenia) as rzeczywisty_czas_minut
            FROM cykle_filtracyjne cf
            JOIN partie_surowca ps ON cf.id_partii = ps.id
            WHERE cf.id_partii = %s
            ORDER BY cf.numer_cyklu, cf.czas_rozpoczecia
        """, (id_partii,))
        
        cykle = cursor.fetchall()
        return jsonify(cykle)
        
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/partie/aktualny-stan')
def get_partie_aktualny_stan():
    """Pobiera aktualny stan wszystkich partii w systemie z szczegĂłĹ‚ami procesu."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT ps.*,
                   s.nazwa_unikalna as nazwa_reaktora,
                   s.typ_sprzetu,
                   CASE 
                       WHEN ps.planowany_czas_zakonczenia IS NOT NULL 
                       THEN TIMESTAMPDIFF(MINUTE, NOW(), ps.planowany_czas_zakonczenia)
                       ELSE NULL
                   END as pozostale_minuty,
                   CASE 
                       WHEN ps.planowany_czas_zakonczenia IS NOT NULL AND NOW() > ps.planowany_czas_zakonczenia
                       THEN TRUE
                       ELSE FALSE
                   END as przekroczony_czas
            FROM partie_surowca ps
            LEFT JOIN sprzet s ON ps.id_aktualnego_sprzetu = s.id
            WHERE ps.status_partii NOT IN ('W magazynie czystym', 'Gotowy do wysĹ‚ania')
            ORDER BY ps.czas_rozpoczecia_etapu DESC
        """)
        
        partie = cursor.fetchall()
        return jsonify(partie)
        
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/filtry/szczegolowy-status')
def get_filtry_szczegolowy_status():
    """Pobiera szczegĂłĹ‚owy status filtrĂłw z informacjami o partiach i cyklach."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Podstawowe informacje o filtrach
        cursor.execute("""
            SELECT id, nazwa_unikalna as nazwa_filtra, stan_sprzetu, typ_sprzetu
            FROM sprzet 
            WHERE typ_sprzetu = 'filtr'
            ORDER BY nazwa_unikalna
        """)
        filtry = cursor.fetchall()
        
        for filtr in filtry:
            # SprawdĹş czy filtr ma aktywnÄ… operacjÄ™
            cursor.execute("""
                SELECT ol.*, 
                       ps.unikalny_kod, ps.nazwa_partii, ps.typ_surowca,
                       ps.aktualny_etap_procesu, ps.numer_cyklu_aktualnego,
                       ps.czas_rozpoczecia_etapu, ps.planowany_czas_zakonczenia,
                       s_start.nazwa_unikalna as reaktor_startowy,
                       s_cel.nazwa_unikalna as reaktor_docelowy,
                       CASE 
                           WHEN ps.planowany_czas_zakonczenia IS NOT NULL 
                           THEN TIMESTAMPDIFF(MINUTE, NOW(), ps.planowany_czas_zakonczenia)
                           ELSE NULL
                       END as pozostale_minuty
                FROM operacje_log ol
                JOIN partie_surowca ps ON ol.id_partii_surowca = ps.id
                LEFT JOIN sprzet s_start ON ol.id_sprzetu_zrodlowego = s_start.id
                LEFT JOIN sprzet s_cel ON ol.id_sprzetu_docelowego = s_cel.id
                WHERE ol.status_operacji = 'aktywna' 
                AND ps.id_aktualnego_filtra = %s
                ORDER BY ol.czas_rozpoczecia DESC
                LIMIT 1
            """, (filtr['nazwa_filtra'],))
            
            aktywna_operacja = cursor.fetchone()
            filtr['aktywna_operacja'] = aktywna_operacja
            
            # JeĹ›li nie ma aktywnej operacji, sprawdĹş czy ktoĹ› czeka na ten filtr
            if not aktywna_operacja:
                cursor.execute("""
                    SELECT ps.*, s.nazwa_unikalna as nazwa_reaktora
                    FROM partie_surowca ps
                    JOIN sprzet s ON ps.id_aktualnego_sprzetu = s.id
                    WHERE ps.id_aktualnego_filtra = %s 
                    AND ps.aktualny_etap_procesu IN ('surowy', 'gotowy')
                    ORDER BY ps.czas_rozpoczecia_etapu ASC
                    LIMIT 3
                """, (filtr['nazwa_filtra'],))
                
                filtr['kolejka_oczekujacych'] = cursor.fetchall()
            else:
                filtr['kolejka_oczekujacych'] = []
        
        return jsonify(filtry)
        
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/cykle/rozpocznij', methods=['POST'])
def rozpocznij_cykl_filtracyjny():
    """Rozpoczyna nowy cykl filtracyjny dla partii."""
    data = request.get_json()
    
    required_fields = ['id_partii', 'typ_cyklu', 'id_filtra', 'reaktor_startowy']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Brak wymaganych pĂłl'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Pobierz aktualny numer cyklu partii
        cursor.execute("SELECT numer_cyklu_aktualnego FROM partie_surowca WHERE id = %s", (data['id_partii'],))
        result = cursor.fetchone()
        if not result:
            return jsonify({'error': 'Nie znaleziono partii'}), 404
        
        numer_cyklu = result[0] + 1
        
        # Oblicz planowany czas zakoĹ„czenia
        durations = {
            'placek': 30,
            'filtracja': 15,
            'dmuchanie': 45
        }
        
        planowany_czas = datetime.now(timezone.utc) + timedelta(minutes=durations.get(data['typ_cyklu'], 30))
        
        # Wstaw nowy cykl
        cursor.execute("""
            INSERT INTO cykle_filtracyjne 
            (id_partii, numer_cyklu, typ_cyklu, id_filtra, reaktor_startowy, 
             reaktor_docelowy, czas_rozpoczecia, wynik_oceny)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), 'oczekuje')
        """, (data['id_partii'], numer_cyklu, data['typ_cyklu'], data['id_filtra'], 
              data['reaktor_startowy'], data.get('reaktor_docelowy')))
        
        cykl_id = cursor.lastrowid
        
        # Aktualizuj partiÄ™
        etap_mapping = {
            'placek': 'placek',
            'filtracja': 'w_kole', 
            'dmuchanie': 'dmuchanie'
        }
        
        cursor.execute("""
            UPDATE partie_surowca 
            SET numer_cyklu_aktualnego = %s,
                aktualny_etap_procesu = %s,
                czas_rozpoczecia_etapu = NOW(),
                planowany_czas_zakonczenia = %s,
                id_aktualnego_filtra = %s,
                reaktor_docelowy = %s
            WHERE id = %s
        """, (numer_cyklu, etap_mapping[data['typ_cyklu']], planowany_czas,
              data['id_filtra'], data.get('reaktor_docelowy'), data['id_partii']))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'RozpoczÄ™to cykl {data["typ_cyklu"]} dla partii',
            'cykl_id': cykl_id,
            'numer_cyklu': numer_cyklu
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'BĹ‚Ä…d rozpoczynania cyklu: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/cykle/zakoncz', methods=['POST'])
def zakoncz_cykl_filtracyjny():
    """KoĹ„czy aktualny cykl filtracyjny i przechodzi do nastÄ™pnego etapu."""
    data = request.get_json()
    
    if 'id_partii' not in data:
        return jsonify({'error': 'Brak ID partii'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Pobierz aktualny stan partii
        cursor.execute("""
            SELECT * FROM partie_surowca WHERE id = %s
        """, (data['id_partii'],))
        
        partia = cursor.fetchone()
        if not partia:
            return jsonify({'error': 'Nie znaleziono partii'}), 404
        
        # ZakoĹ„cz aktualny cykl
        cursor.execute("""
            UPDATE cykle_filtracyjne 
            SET czas_zakonczenia = NOW(),
                czas_trwania_minut = TIMESTAMPDIFF(MINUTE, czas_rozpoczecia, NOW()),
                wynik_oceny = %s,
                komentarz = %s
            WHERE id_partii = %s 
            AND numer_cyklu = %s 
            AND czas_zakonczenia IS NULL
        """, (data.get('wynik_oceny', 'oczekuje'), data.get('komentarz', ''),
              data['id_partii'], partia['numer_cyklu_aktualnego']))
        
        # OkreĹ›l nastÄ™pny etap na podstawie aktualnego
        next_etap = 'gotowy'
        next_filtr = None
        
        if partia['aktualny_etap_procesu'] == 'placek':
            next_etap = 'przelew'
        elif partia['aktualny_etap_procesu'] == 'przelew':
            next_etap = 'w_kole'
        elif partia['aktualny_etap_procesu'] == 'w_kole':
            next_etap = 'ocena_probki'
        elif partia['aktualny_etap_procesu'] == 'dmuchanie':
            next_etap = 'gotowy'
            next_filtr = None
        
        # Aktualizuj partiÄ™
        cursor.execute("""
            UPDATE partie_surowca 
            SET aktualny_etap_procesu = %s,
                czas_rozpoczecia_etapu = NOW(),
                planowany_czas_zakonczenia = NULL,
                id_aktualnego_filtra = %s
            WHERE id = %s
        """, (next_etap, next_filtr, data['id_partii']))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'ZakoĹ„czono cykl. Partia przeszĹ‚a do etapu: {next_etap}',
            'next_etap': next_etap
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'BĹ‚Ä…d koĹ„czenia cyklu: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@bp.route('/cykle-monitor')
def cykle_monitor():
    """Serwuje stronÄ™ monitoringu cykli filtracyjnych."""
    return render_template('cykle_monitor.html')

# === ENDPOINTY API DLA AKTYWNYCH PARTII ===

@bp.route('/api/partie/aktywne', methods=['GET'])
def get_aktywne_partie():
    """
    Pobiera listÄ™ wszystkich aktywnych partii w systemie z peĹ‚nymi szczegĂłĹ‚ami:
    - Lokalizacja i status
    - Aktualny etap procesu
    - Czasy rozpoczÄ™cia i planowanego zakoĹ„czenia
    - Informacje o operacjach
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # GĹ‚Ăłwne zapytanie pobierajÄ…ce aktywne partie
        cursor.execute("""
            SELECT 
                ps.id,
                ps.unikalny_kod,
                ps.nazwa_partii,
                ps.typ_surowca,
                ps.zrodlo_pochodzenia,
                ps.waga_poczatkowa_kg,
                ps.waga_aktualna_kg,
                ps.data_utworzenia,
                ps.status_partii,
                ps.ilosc_cykli_filtracyjnych,
                
                -- Informacje o aktualnym sprzÄ™cie
                s.id as id_sprzetu,
                s.nazwa_unikalna as nazwa_sprzetu,
                s.typ_sprzetu,
                s.stan_sprzetu,
                
                -- Informacje o aktywnej operacji (jeĹ›li istnieje)
                ol.id as id_operacji,
                ol.typ_operacji,
                ol.status_operacji,
                ol.czas_rozpoczecia as czas_rozpoczecia_operacji,
                ol.opis as opis_operacji,
                ol.punkt_startowy,
                ol.punkt_docelowy,
                
                -- Obliczenia czasowe
                TIMESTAMPDIFF(MINUTE, ps.data_utworzenia, NOW()) as wiek_partii_minuty,
                CASE 
                    WHEN ol.czas_rozpoczecia IS NOT NULL 
                    THEN TIMESTAMPDIFF(MINUTE, ol.czas_rozpoczecia, NOW())
                    ELSE NULL
                END as czas_trwania_operacji_minuty
                
            FROM partie_surowca ps
            LEFT JOIN sprzet s ON ps.id_sprzetu = s.id
            LEFT JOIN operacje_log ol ON ps.id = ol.id_partii_surowca AND ol.status_operacji = 'aktywna'
            WHERE ps.status_partii NOT IN ('W magazynie czystym', 'Gotowy do wysĹ‚ania')
            ORDER BY ps.data_utworzenia DESC
        """)
        
        partie = cursor.fetchall()
        
        # Wzbogacenie danych o dodatkowe informacje
        for partia in partie:
            # Dodaj informacje o statusach partii
            cursor.execute("""
                SELECT st.id, st.nazwa_statusu
                FROM partie_statusy ps
                JOIN statusy st ON ps.id_statusu = st.id
                WHERE ps.id_partii = %s
            """, (partia['id'],))
            partia['statusy'] = cursor.fetchall()
            
            # Dodaj historiÄ™ ostatnich operacji
            cursor.execute("""
                SELECT 
                    ol.id,
                    ol.typ_operacji,
                    ol.status_operacji,
                    ol.czas_rozpoczecia,
                    ol.czas_zakonczenia,
                    ol.opis,
                    ol.punkt_startowy,
                    ol.punkt_docelowy,
                    TIMESTAMPDIFF(MINUTE, ol.czas_rozpoczecia, 
                        COALESCE(ol.czas_zakonczenia, NOW())) as czas_trwania_min
                FROM operacje_log ol
                WHERE ol.id_partii_surowca = %s
                ORDER BY ol.czas_rozpoczecia DESC
                LIMIT 5
            """, (partia['id'],))
            partia['historia_operacji'] = cursor.fetchall()
            
            # Formatuj daty dla JSON
            if partia['data_utworzenia']:
                partia['data_utworzenia'] = partia['data_utworzenia'].strftime('%Y-%m-%d %H:%M:%S')
            if partia['czas_rozpoczecia_operacji']:
                partia['czas_rozpoczecia_operacji'] = partia['czas_rozpoczecia_operacji'].strftime('%Y-%m-%d %H:%M:%S')
            
            # Formatuj daty w historii operacji
            for operacja in partia['historia_operacji']:
                if operacja['czas_rozpoczecia']:
                    operacja['czas_rozpoczecia'] = operacja['czas_rozpoczecia'].strftime('%Y-%m-%d %H:%M:%S')
                if operacja['czas_zakonczenia']:
                    operacja['czas_zakonczenia'] = operacja['czas_zakonczenia'].strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify(partie)
        
    except Exception as e:
        return jsonify({'error': f'BĹ‚Ä…d pobierania aktywnych partii: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/partie/szczegoly/<int:partia_id>', methods=['GET'])
def get_szczegoly_partii(partia_id):
    """Pobiera szczegĂłĹ‚owe informacje o konkretnej partii"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Podstawowe informacje o partii
        cursor.execute("""
            SELECT 
                ps.*,
                s.nazwa_unikalna as nazwa_sprzetu,
                s.typ_sprzetu,
                s.stan_sprzetu
            FROM partie_surowca ps
            LEFT JOIN sprzet s ON ps.id_sprzetu = s.id
            WHERE ps.id = %s
        """, (partia_id,))
        
        partia = cursor.fetchone()
        if not partia:
            return jsonify({'error': 'Partia nie znaleziona'}), 404
        
        # PeĹ‚na historia operacji
        cursor.execute("""
            SELECT 
                ol.*,
                s_start.nazwa_unikalna as nazwa_sprzetu_startowego,
                s_end.nazwa_unikalna as nazwa_sprzetu_docelowego,
                TIMESTAMPDIFF(MINUTE, ol.czas_rozpoczecia, 
                    COALESCE(ol.czas_zakonczenia, NOW())) as czas_trwania_min
            FROM operacje_log ol
            LEFT JOIN sprzet s_start ON ol.id_sprzetu_zrodlowego = s_start.id
            LEFT JOIN sprzet s_end ON ol.id_sprzetu_docelowego = s_end.id
            WHERE ol.id_partii_surowca = %s
            ORDER BY ol.czas_rozpoczecia DESC
        """, (partia_id,))
        
        partia['historia_operacji'] = cursor.fetchall()
        
        # Statusy partii
        cursor.execute("""
            SELECT st.id, st.nazwa_statusu
            FROM partie_statusy ps
            JOIN statusy st ON ps.id_statusu = st.id
            WHERE ps.id_partii = %s
        """, (partia_id,))
        partia['statusy'] = cursor.fetchall()
        
        # Cykle filtracyjne (jeĹ›li istniejÄ…)
        cursor.execute("""
            SELECT cf.*,
                   TIMESTAMPDIFF(MINUTE, cf.czas_rozpoczecia, cf.czas_zakonczenia) as rzeczywisty_czas_minut
            FROM cykle_filtracyjne cf
            WHERE cf.id_partii = %s
            ORDER BY cf.numer_cyklu DESC
        """, (partia_id,))
        partia['cykle_filtracyjne'] = cursor.fetchall()
        
        # Formatuj daty
        if partia['data_utworzenia']:
            partia['data_utworzenia'] = partia['data_utworzenia'].strftime('%Y-%m-%d %H:%M:%S')
        
        for operacja in partia['historia_operacji']:
            if operacja['czas_rozpoczecia']:
                operacja['czas_rozpoczecia'] = operacja['czas_rozpoczecia'].strftime('%Y-%m-%d %H:%M:%S')
            if operacja['czas_zakonczenia']:
                operacja['czas_zakonczenia'] = operacja['czas_zakonczenia'].strftime('%Y-%m-%d %H:%M:%S')
        
        for cykl in partia['cykle_filtracyjne']:
            if cykl['czas_rozpoczecia']:
                cykl['czas_rozpoczecia'] = cykl['czas_rozpoczecia'].strftime('%Y-%m-%d %H:%M:%S')
            if cykl['czas_zakonczenia']:
                cykl['czas_zakonczenia'] = cykl['czas_zakonczenia'].strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify(partia)
        
    except Exception as e:
        return jsonify({'error': f'BĹ‚Ä…d pobierania szczegĂłĹ‚Ăłw partii: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/partie/aktualizuj-status', methods=['POST'])
def aktualizuj_status_partii():
    """Aktualizuje status partii"""
    data = request.get_json()
    
    if not data or 'id_partii' not in data or 'nowy_status' not in data:
        return jsonify({'error': 'Brak wymaganych pĂłl: id_partii, nowy_status'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # SprawdĹş czy partia istnieje
        cursor.execute("SELECT id FROM partie_surowca WHERE id = %s", (data['id_partii'],))
        if not cursor.fetchone():
            return jsonify({'error': 'Partia nie znaleziona'}), 404
        
        # Aktualizuj status
        cursor.execute("""
            UPDATE partie_surowca 
            SET status_partii = %s
            WHERE id = %s
        """, (data['nowy_status'], data['id_partii']))
        
        # Dodaj wpis do historii operacji
        cursor.execute("""
            INSERT INTO operacje_log 
            (typ_operacji, id_partii_surowca, status_operacji, czas_rozpoczecia, czas_zakonczenia, opis)
            VALUES ('ZMIANA_STATUSU', %s, 'zakonczona', NOW(), NOW(), %s)
        """, (data['id_partii'], f"Zmiana statusu na: {data['nowy_status']}"))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Status partii zostaĹ‚ zaktualizowany na: {data["nowy_status"]}'
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'BĹ‚Ä…d aktualizacji statusu: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

# === KONIEC ENDPOINTĂ“W AKTYWNYCH PARTII ===

@bp.route('/aktywne-partie')
def show_aktywne_partie():
    """Serwuje stronÄ™ zarzÄ…dzania aktywnymi partiami."""
    return render_template('aktywne_partie.html')

@bp.route('/api/typy-surowca', methods=['GET'])
def get_typy_surowca():
    """Zwraca listÄ™ dostÄ™pnych typĂłw surowca"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT id, nazwa, opis FROM typy_surowca ORDER BY nazwa")
        typy = cursor.fetchall()
        return jsonify(typy)
    except Exception as e:
        return jsonify({'error': f'BĹ‚Ä…d pobierania typĂłw surowca: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/sprzet/beczki-brudne', methods=['GET'])
def get_beczki_brudne():
    """Zwraca listÄ™ beczek brudnych dostÄ™pnych do tankowania"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT id, nazwa_unikalna, stan_sprzetu
            FROM sprzet 
            WHERE typ_sprzetu = 'beczka_brudna'
            ORDER BY nazwa_unikalna
        """)
        beczki = cursor.fetchall()
        return jsonify(beczki)
    except Exception as e:
        return jsonify({'error': f'BĹ‚Ä…d pobierania beczek: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/sprzet/reaktory-puste', methods=['GET'])
def get_reaktory_puste():
    """Zwraca listÄ™ reaktorĂłw w stanie 'Pusty' dostÄ™pnych do tankowania"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT id, nazwa_unikalna, stan_sprzetu
            FROM sprzet 
            WHERE typ_sprzetu = 'reaktor' AND stan_sprzetu = 'Pusty'
            ORDER BY nazwa_unikalna
        """)
        reaktory = cursor.fetchall()
        return jsonify(reaktory)
    except Exception as e:
        return jsonify({'error': f'BĹ‚Ä…d pobierania reaktorĂłw: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/sprzet/reaktory-z-surowcem', methods=['GET'])
def get_reaktory_z_surowcem():
    """Zwraca listÄ™ reaktorĂłw ze stanem innym niĹĽ 'Pusty' (zawierajÄ…cych surowiec)"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT id, nazwa_unikalna, stan_sprzetu
            FROM sprzet 
            WHERE typ_sprzetu = 'reaktor' AND stan_sprzetu != 'Pusty'
            ORDER BY nazwa_unikalna
        """)
        reaktory = cursor.fetchall()
        return jsonify(reaktory)
    except Exception as e:
        return jsonify({'error': f'BĹ‚Ä…d pobierania reaktorĂłw z surowcem: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/monitoring/parametry', methods=['GET'])
def get_parametry_sprzetu():
    """Zwraca aktualne temperatury i ciĹ›nienia dla wszystkiego sprzÄ™tu."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                id,
                nazwa_unikalna,
                typ_sprzetu,
                stan_sprzetu,
                temperatura_aktualna,
                cisnienie_aktualne,
                poziom_aktualny_procent,
                temperatura_docelowa,
                temperatura_max,
                cisnienie_max,
                ostatnia_aktualizacja,
                CASE 
                    WHEN temperatura_aktualna > temperatura_max THEN 'PRZEKROCZENIE_TEMP'
                    WHEN cisnienie_aktualne > cisnienie_max THEN 'PRZEKROCZENIE_CISN'
                    WHEN temperatura_aktualna IS NULL OR cisnienie_aktualne IS NULL THEN 'BRAK_DANYCH'
                    ELSE 'OK'
                END as status_parametrow,
                CASE 
                    WHEN ostatnia_aktualizacja IS NULL THEN NULL
                    WHEN ostatnia_aktualizacja < NOW() - INTERVAL 5 MINUTE THEN 'NIEAKTUALNE'
                    ELSE 'AKTUALNE'
                END as status_danych
            FROM sprzet 
            ORDER BY typ_sprzetu, nazwa_unikalna
        """)
        
        sprzet_list = cursor.fetchall()
        
        # Formatuj daty do JSON
        for sprzet in sprzet_list:
            if sprzet.get('ostatnia_aktualizacja'):
                sprzet['ostatnia_aktualizacja'] = sprzet.get('ostatnia_aktualizacja').strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify(sprzet_list)
        
    except Exception as e:
        return jsonify({'error': f'BĹ‚Ä…d pobierania parametrĂłw sprzÄ™tu: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()


# ENDPOINT DO POBIERANIA PARAMETRĂ“W SPRZÄTU 
@bp.route('/api/monitoring/parametry/<int:sprzet_id>', methods=['GET'])
def get_parametry_konkretnego_sprzetu(sprzet_id):
    """Zwraca szczegĂłĹ‚owe parametry dla konkretnego sprzÄ™tu."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                id,
                nazwa_unikalna,
                typ_sprzetu,
                stan_sprzetu,
                temperatura_aktualna,
                cisnienie_aktualne,
                poziom_aktualny_procent,
                temperatura_docelowa,
                temperatura_max,
                cisnienie_max,
                ostatnia_aktualizacja,
                pojemnosc_kg,
                id_partii_surowca,
                CASE 
                    WHEN temperatura_aktualna > temperatura_max THEN 'PRZEKROCZENIE_TEMP'
                    WHEN cisnienie_aktualne > cisnienie_max THEN 'PRZEKROCZENIE_CISN'
                    WHEN temperatura_aktualna IS NULL OR cisnienie_aktualne IS NULL THEN 'BRAK_DANYCH'
                    ELSE 'OK'
                END as status_parametrow,
                CASE 
                    WHEN ostatnia_aktualizacja IS NULL THEN NULL
                    WHEN ostatnia_aktualizacja < NOW() - INTERVAL 5 MINUTE THEN 'NIEAKTUALNE'
                    ELSE 'AKTUALNE'
                END as status_danych,
                TIMESTAMPDIFF(MINUTE, ostatnia_aktualizacja, NOW()) as minuty_od_aktualizacji
            FROM sprzet 
            WHERE id = %s
        """, (sprzet_id,))
        
        sprzet = cursor.fetchone()
        
        if not sprzet:
            return jsonify({'error': 'SprzÄ™t nie znaleziony'}), 404
        
        # Formatuj datÄ™ do JSON
        if sprzet.get('ostatnia_aktualizacja'):
            sprzet['ostatnia_aktualizacja'] = sprzet.get('ostatnia_aktualizacja').strftime('%Y-%m-%d %H:%M:%S')
        
        # JeĹ›li sprzÄ™t ma partiÄ™, dodaj informacje o niej
        id_partii_surowca = sprzet.get('id_partii_surowca')
        if id_partii_surowca:
            cursor.execute("""
                SELECT unikalny_kod, typ_surowca, waga_aktualna_kg, status_partii
                FROM partie_surowca 
                WHERE id = %s
            """, (id_partii_surowca,))
            partia = cursor.fetchone()
            sprzet['partia'] = partia
        else:
            sprzet['partia'] = None
        
        return jsonify(sprzet)
        
    except Exception as e:
        return jsonify({'error': f'BĹ‚Ä…d pobierania parametrĂłw sprzÄ™tu: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/monitoring/alarmy-parametryczne', methods=['GET'])
def get_alarmy_parametryczne():
    """Zwraca listÄ™ sprzÄ™tu z przekroczonymi parametrami (temperatura/ciĹ›nienie)."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                id,
                nazwa_unikalna,
                typ_sprzetu,
                temperatura_aktualna,
                cisnienie_aktualne,
                temperatura_max,
                cisnienie_max,
                ostatnia_aktualizacja,
                CASE 
                    WHEN temperatura_aktualna > temperatura_max THEN 'TEMPERATURA_PRZEKROCZONA'
                    WHEN cisnienie_aktualne > cisnienie_max THEN 'CISNIENIE_PRZEKROCZONE'
                    ELSE 'INNE'
                END as typ_alarmu,
                CASE 
                    WHEN temperatura_aktualna > temperatura_max THEN temperatura_aktualna - temperatura_max
                    WHEN cisnienie_aktualne > cisnienie_max THEN cisnienie_aktualne - cisnienie_max
                    ELSE 0
                END as przekroczenie_wartosci
            FROM sprzet 
            WHERE 
                (temperatura_aktualna > temperatura_max AND temperatura_aktualna IS NOT NULL)
                OR 
                (cisnienie_aktualne > cisnienie_max AND cisnienie_aktualne IS NOT NULL)
            ORDER BY przekroczenie_wartosci DESC
        """)
        
        alarmy = cursor.fetchall()
        
        # Formatuj daty do JSON
        for alarm in alarmy:
            if alarm.get('ostatnia_aktualizacja'):
                alarm['ostatnia_aktualizacja'] = alarm.get('ostatnia_aktualizacja').strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify(alarmy)
        
    except Exception as e:
        return jsonify({'error': f'BĹ‚Ä…d pobierania alarmĂłw parametrycznych: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@bp.route('/monitoring-parametry')
def show_monitoring_parametry():
    """Serwuje stronÄ™ monitoringu parametrĂłw sprzÄ™tu."""
    return render_template('monitoring_parametry.html')


# ========================================
# ENDPOINTY API DLA SYSTEMU APOLLO
# ========================================

@bp.route('/api/apollo/stan/<int:id_sprzetu>', methods=['GET'])
def get_stan_apollo(id_sprzetu):
    """Pobiera aktualny stan Apollo z przewidywaniem dostÄ™pnej iloĹ›ci"""
    try:
        stan = ApolloService.oblicz_aktualny_stan_apollo(id_sprzetu)
        return jsonify(stan)
    except Exception as e:
        return jsonify({'error': f'BĹ‚Ä…d pobierania stanu Apollo: {str(e)}'}), 500

@bp.route('/api/apollo/rozpocznij-sesje', methods=['POST'])
def rozpocznij_sesje_apollo():
    """Rozpoczyna nowÄ… sesjÄ™ wytapiania w Apollo"""
    data = request.get_json()
    
    required_fields = ['id_sprzetu', 'typ_surowca', 'waga_kg']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Brak wymaganych pĂłl: id_sprzetu, typ_surowca, waga_kg'}), 400
    
    try:
        id_sesji = ApolloService.rozpocznij_sesje_apollo(
            data['id_sprzetu'], 
            data['typ_surowca'], 
            data['waga_kg'],
            data.get('operator')
        )
        
        return jsonify({
            'success': True,
            'message': f'RozpoczÄ™to nowÄ… sesjÄ™ wytapiania w Apollo',
            'id_sesji': id_sesji
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'BĹ‚Ä…d rozpoczynania sesji: {str(e)}'}), 500

@bp.route('/api/apollo/dodaj-surowiec', methods=['POST'])
def dodaj_surowiec_apollo():
    """Dodaje kolejnÄ… porcjÄ™ surowca staĹ‚ego do Apollo"""
    data = request.get_json()
    
    required_fields = ['id_sprzetu', 'waga_kg']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Brak wymaganych pĂłl: id_sprzetu, waga_kg'}), 400
    
    try:
        ApolloService.dodaj_surowiec_do_apollo(
            data['id_sprzetu'], 
            data['waga_kg'],
            data.get('operator')
        )
        
        return jsonify({
            'success': True,
            'message': f'Dodano {data["waga_kg"]}kg surowca do Apollo'
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'BĹ‚Ä…d dodawania surowca: {str(e)}'}), 500

@bp.route('/api/apollo/koryguj-stan', methods=['POST'])
def koryguj_stan_apollo():
    """RÄ™czna korekta stanu Apollo przez operatora"""
    data = request.get_json()
    
    required_fields = ['id_sprzetu', 'rzeczywista_waga_kg']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Brak wymaganych pĂłl: id_sprzetu, rzeczywista_waga_kg'}), 400
    
    try:
        ApolloService.koryguj_stan_apollo(
            data['id_sprzetu'], 
            data['rzeczywista_waga_kg'],
            data.get('operator'),
            data.get('uwagi')
        )
        
        return jsonify({
            'success': True,
            'message': f'Skorygowano stan Apollo na {data["rzeczywista_waga_kg"]}kg'
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'BĹ‚Ä…d korekty stanu: {str(e)}'}), 500

@bp.route('/api/apollo/lista-stanow', methods=['GET'])
def get_lista_stanow_apollo():
    """Pobiera stany wszystkich Apollo w systemie"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # UĹĽycie LOWER() aby zapewniÄ‡ brak wraĹĽliwoĹ›ci na wielkoĹ›Ä‡ liter
        cursor.execute("SELECT id FROM sprzet WHERE LOWER(typ_sprzetu) = 'apollo'")
        apollo_ids = [row['id'] for row in cursor.fetchall()]
        
        lista_stanow = []
        for apollo_id in apollo_ids:
            try:
                stan = ApolloService.get_stan_apollo(apollo_id)
                if stan:
                    lista_stanow.append(stan)
            except Exception as e:
                print(f"BĹ‚Ä…d przy pobieraniu stanu dla Apollo ID {apollo_id}: {e}")
                # MoĹĽna dodaÄ‡ logowanie bĹ‚Ä™du, ale kontynuowaÄ‡ dla innych
                continue
                
        return jsonify(lista_stanow)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/sprzet/dostepne-zrodla', methods=['GET'])
def get_dostepne_zrodla():
    """Zwraca listÄ™ dostÄ™pnych ĹşrĂłdeĹ‚ do transferu (Apollo + beczki brudne z zawartoĹ›ciÄ…)"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Apollo z aktywnymi sesjami
        apollo_query = """
            SELECT DISTINCT s.id, s.nazwa_unikalna, s.typ_sprzetu, 
                   'apollo' as kategoria_zrodla,
                   aps.typ_surowca,
                   'Aktywna sesja wytapiania' as opis_stanu
            FROM sprzet s
            JOIN apollo_sesje aps ON s.id = aps.id_sprzetu
            WHERE s.typ_sprzetu = 'apollo' AND aps.status_sesji = 'aktywna'
        """
        
        # Beczki brudne z partiami
        beczki_query = """
            SELECT DISTINCT s.id, s.nazwa_unikalna, s.typ_sprzetu,
                   'beczka_brudna' as kategoria_zrodla,
                   ps.typ_surowca,
                   CONCAT('Partia: ', ps.unikalny_kod, ' (', ps.waga_aktualna_kg, 'kg)') as opis_stanu
            FROM sprzet s
            JOIN partie_surowca ps ON s.id = ps.id_sprzetu
            WHERE s.typ_sprzetu = 'beczka_brudna' AND ps.status_partii NOT IN ('W magazynie czystym', 'Gotowy do wysĹ‚ania')
        """
        
        # Reaktory z partiami
        reaktory_query = """
            SELECT DISTINCT s.id, s.nazwa_unikalna, s.typ_sprzetu,
                   'reaktor' as kategoria_zrodla,
                   ps.typ_surowca,
                   CONCAT('Partia: ', ps.unikalny_kod, ' (', ps.waga_aktualna_kg, 'kg)') as opis_stanu
            FROM sprzet s
            JOIN partie_surowca ps ON s.id = ps.id_sprzetu
            WHERE s.typ_sprzetu = 'reaktor' AND ps.status_partii NOT IN ('W magazynie czystym', 'Gotowy do wysĹ‚ania')
        """
        
        cursor.execute(f"{apollo_query} UNION ALL {beczki_query} UNION ALL {reaktory_query} ORDER BY kategoria_zrodla, nazwa_unikalna")
        zrodla = cursor.fetchall()
        
        # Dla Apollo dodaj informacje o dostÄ™pnej iloĹ›ci
        for zrodlo in zrodla:
            if zrodlo.get('kategoria_zrodla') == 'apollo':
                zrodlo_id = zrodlo.get('id')
                if zrodlo_id:
                    stan = ApolloService.oblicz_aktualny_stan_apollo(zrodlo_id)
                    zrodlo['dostepne_kg'] = stan.get('dostepne_kg')
                    zrodlo['opis_stanu'] = f"DostÄ™pne: {stan.get('dostepne_kg')}kg {stan.get('typ_surowca')}"
        
        return jsonify(zrodla)
        
    except Exception as e:
        return jsonify({'error': f'BĹ‚Ä…d pobierania ĹşrĂłdeĹ‚: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/sprzet/dostepne-cele', methods=['GET'])
def get_dostepne_cele():
    """Zwraca listÄ™ wszystkich reaktorĂłw i beczek brudnych jako potencjalnych celĂłw transferu."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # LEFT JOIN z partiami, aby uzyskaÄ‡ informacje o zawartoĹ›ci
        query = """
            SELECT 
                s.id, 
                s.nazwa_unikalna, 
                s.typ_sprzetu, 
                s.stan_sprzetu,
                s.pojemnosc_kg,
                p.waga_aktualna_kg,
                p.typ_surowca
            FROM sprzet s
            LEFT JOIN partie_surowca p ON s.id = p.id_sprzetu
            WHERE s.typ_sprzetu IN ('reaktor', 'beczka_brudna', 'beczka_czysta')
            ORDER BY s.typ_sprzetu, s.nazwa_unikalna
        """
        cursor.execute(query)
        
        cele = cursor.fetchall()
        return jsonify(cele)
        
    except Exception as e:
        return jsonify({'error': f'BĹ‚Ä…d pobierania celĂłw: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/apollo/zakoncz-sesje', methods=['POST'])
def zakoncz_sesje_apollo():
    """KoĹ„czy aktywnÄ… sesjÄ™ wytapiania w Apollo"""
    data = request.get_json()
    
    if not data or 'id_sprzetu' not in data:
        return jsonify({'error': 'Brak wymaganego pola: id_sprzetu'}), 400
    
    try:
        ApolloService.zakoncz_sesje_apollo(
            data['id_sprzetu'],
            data.get('operator')
        )
        
        return jsonify({
            'success': True,
            'message': f'Sesja dla Apollo ID {data["id_sprzetu"]} zostaĹ‚a zakoĹ„czona.'
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'BĹ‚Ä…d koĹ„czenia sesji: {str(e)}'}), 500

@bp.route('/api/apollo/sesja/<int:id_sesji>/historia', methods=['GET'])
def get_historia_sesji_apollo(id_sesji):
    """Pobiera historiÄ™ transferĂłw dla danej sesji Apollo."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        sql = """
            SELECT 
                ol.czas_zakonczenia, 
                ol.ilosc_kg, 
                s.nazwa_unikalna as nazwa_celu
            FROM operacje_log ol
            LEFT JOIN sprzet s ON ol.id_sprzetu_docelowego = s.id
            WHERE ol.id_apollo_sesji = %s
              AND ol.typ_operacji = 'ROZTANKOWANIE_APOLLO'
              AND ol.status_operacji = 'zakonczona'
            ORDER BY ol.czas_zakonczenia DESC
        """
        cursor.execute(sql, (id_sesji,))
        historia = cursor.fetchall()
        
        # Formatowanie daty przed wysĹ‚aniem
        for row in historia:
            if row['czas_zakonczenia']:
                row['czas_zakonczenia'] = row['czas_zakonczenia'].strftime('%Y-%m-%d %H:%M:%S')

        return jsonify(historia)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

def get_base_components_recursive(partia_id, cursor):
    """
    Rekurencyjnie znajduje bazowe skĹ‚adniki dla danej partii, zwracajÄ…c sĹ‚ownik:
    {'TYP_SUROWCA': waga, ...}
    """
    cursor.execute("SELECT id, typ_surowca, waga_poczatkowa_kg FROM partie_surowca WHERE id = %s", (partia_id,))
    partia_info = cursor.fetchone()

    if not partia_info:
        return {}

    # JeĹ›li partia nie jest mieszaninÄ…, jest skĹ‚adnikiem bazowym. ZwrĂłÄ‡ jej typ i wagÄ™.
    if not partia_info['typ_surowca'].startswith('MIX('):
        return { partia_info['typ_surowca']: float(partia_info['waga_poczatkowa_kg']) }

    # Partia jest mieszaninÄ…, znajdĹş jej bezpoĹ›rednie skĹ‚adniki.
    query = """
        SELECT 
            ps.id_partii_skladowej,
            ps.waga_skladowa_kg,
            p.waga_poczatkowa_kg AS waga_calkowita_skladowej
        FROM partie_skladniki ps
        JOIN partie_surowca p ON ps.id_partii_skladowej = p.id
        WHERE ps.id_partii_wynikowej = %s;
    """
    cursor.execute(query, (partia_id,))
    direct_components = cursor.fetchall()
    
    final_composition_agg = {}

    for comp in direct_components:
        # Rekurencyjnie pobierz bazowe skĹ‚adniki dla kaĹĽdego skĹ‚adnika
        child_base_components = get_base_components_recursive(comp['id_partii_skladowej'], cursor)
        
        weight_of_comp_used_in_mix = float(comp['waga_skladowa_kg'])
        total_initial_weight_of_child_batch = float(comp['waga_calkowita_skladowej'])

        if total_initial_weight_of_child_batch == 0:
            continue
            
        # Rozdziel wagÄ™ uĹĽytego skĹ‚adnika proporcjonalnie na jego bazowe komponenty
        for base_type, base_weight_in_child in child_base_components.items():
            proportion = base_weight_in_child / total_initial_weight_of_child_batch
            weight_contribution = proportion * weight_of_comp_used_in_mix
            final_composition_agg[base_type] = final_composition_agg.get(base_type, 0) + weight_contribution
            
    return final_composition_agg

@bp.route('/api/sprzet/stan-partii', methods=['GET'])
def get_stan_partii_w_sprzecie():
    """
    Zwraca stan caĹ‚ego sprzÄ™tu, ktĂłry moĹĽe przechowywaÄ‡ partie, 
    wraz z informacjami o aktualnie znajdujÄ…cej siÄ™ w nim partii.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Pobierz caĹ‚y sprzÄ™t, ktĂłry nas interesuje, wraz z doĹ‚Ä…czonymi partiami
        query = """
            SELECT
                s.id, s.nazwa_unikalna, s.typ_sprzetu, s.stan_sprzetu,
                p.id AS partia_id, p.unikalny_kod, p.typ_surowca, p.waga_aktualna_kg
            FROM sprzet s
            LEFT JOIN partie_surowca p ON s.id = p.id_sprzetu
            WHERE s.typ_sprzetu IN ('reaktor', 'beczka_brudna', 'beczka_czysta')
            ORDER BY s.typ_sprzetu, s.nazwa_unikalna;
        """
        cursor.execute(query)
        wyniki = cursor.fetchall()
        
        # Przygotuj strukturÄ™ odpowiedzi
        odpowiedz = {
            'reaktory': [],
            'beczki_brudne': [],
            'beczki_czyste': []
        }

        for row in wyniki:
            sprzet_info = {
                'id': row['id'],
                'nazwa_unikalna': row['nazwa_unikalna'],
                'typ_sprzetu': row['typ_sprzetu'],
                'stan_sprzetu': row['stan_sprzetu'],
                'partia': None
            }
            if row['partia_id']:
                partia_info = {
                    'id': row['partia_id'],
                    'unikalny_kod': row['unikalny_kod'],
                    'typ_surowca': row['typ_surowca'],
                    'waga_aktualna_kg': float(row['waga_aktualna_kg']),
                    'sklad': None  # DomyĹ›lnie brak skĹ‚adu
                }

                # JeĹ›li partia jest mieszaninÄ…, oblicz jej skĹ‚ad
                if partia_info['typ_surowca'].startswith('MIX('):
                    sklad_dict = get_base_components_recursive(partia_info['id'], cursor)
                    total_waga_skladu = sum(sklad_dict.values())
                    
                    if total_waga_skladu > 0:
                        sklad_list = []
                        for typ, waga in sklad_dict.items():
                            procent = (waga / total_waga_skladu) * 100
                            sklad_list.append({
                                'typ_surowca': typ,
                                'waga_kg': round(waga, 2),
                                'procent': round(procent, 2)
                            })
                        partia_info['sklad'] = sorted(sklad_list, key=lambda x: x['typ_surowca'])

                sprzet_info['partia'] = partia_info
            
            if row['typ_sprzetu'] == 'reaktor':
                odpowiedz['reaktory'].append(sprzet_info)
            elif row['typ_sprzetu'] == 'beczka_brudna':
                odpowiedz['beczki_brudne'].append(sprzet_info)
            elif row['typ_sprzetu'] == 'beczka_czysta':
                odpowiedz['beczki_czyste'].append(sprzet_info)

        return jsonify(odpowiedz)

    except mysql.connector.Error as err:
        return jsonify({'error': f'BĹ‚Ä…d bazy danych: {err}'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@bp.route('/api/partie/<int:partia_id>/skladniki', methods=['GET'])
def get_skladniki_partii(partia_id):
    """Zwraca listÄ™ skĹ‚adnikĂłw dla danej partii (mieszaniny)."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT 
                ps.id_partii_skladowej,
                p.unikalny_kod AS unikalny_kod_skladowej,
                ps.waga_skladowa_kg
            FROM partie_skladniki ps
            JOIN partie_surowca p ON ps.id_partii_skladowej = p.id
            WHERE ps.id_partii_wynikowej = %s
            ORDER BY ps.data_dodania;
        """
        cursor.execute(query, (partia_id,))
        skladniki = cursor.fetchall()

        # Konwersja Decimal na float dla JSON
        for s in skladniki:
            s['waga_skladowa_kg'] = float(s['waga_skladowa_kg'])

        return jsonify(skladniki)

    except mysql.connector.Error as err:
        return jsonify({'error': f'BĹ‚Ä…d bazy danych: {err}'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@bp.route('/api/apollo/sesja/<int:sesja_id>/historia-zaladunku', methods=['GET'])
def get_historia_zaladunku_sesji(sesja_id):
    """Zwraca historiÄ™ zaĹ‚adunkĂłw i korekt dla danej sesji Apollo."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT 
                typ_zdarzenia,
                waga_kg,
                czas_zdarzenia,
                operator,
                uwagi
            FROM apollo_tracking
            WHERE id_sesji = %s AND typ_zdarzenia IN ('DODANIE_SUROWCA', 'KOREKTA_RECZNA')
            ORDER BY czas_zdarzenia DESC;
        """
        cursor.execute(query, (sesja_id,))
        historia = cursor.fetchall()

        # Konwersja typĂłw dla JSON
        for wpis in historia:
            if isinstance(wpis.get('czas_zdarzenia'), datetime):
                wpis['czas_zdarzenia'] = wpis['czas_zdarzenia'].isoformat()
            if isinstance(wpis.get('waga_kg'), Decimal):
                wpis['waga_kg'] = float(wpis['waga_kg'])

        return jsonify(historia)

    except mysql.connector.Error as err:
        return jsonify({'error': f'BĹ‚Ä…d bazy danych: {err}'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

import random
import time
from datetime import datetime
from flask import current_app
from mysql.connector.errors import OperationalError
from .db import get_db_connection

class SensorService:
    def __init__(self, app=None):
        self.app = app
        
       
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self.app = app
        # Don't load temperatures here - will do it in context
        self.app = app
        # Register a function to run before first request
            

    
    

    def set_temperature(self, sprzet_id, temperatura):
        """
        Ustawia nowÄ… temperaturÄ™ bazowÄ… dla sprzÄ™tu w tabeli operator_temperatures,
        implementujÄ…c mechanizm ponawiania transakcji.
        """
        max_retries = 3
        for attempt in range(max_retries):
            conn = None
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                current_time = datetime.now(timezone.utc)

                # Zapisz nowÄ… temperaturÄ™ bazowÄ…, od ktĂłrej symulacja bÄ™dzie liczyÄ‡
                cursor.execute("""
                    INSERT INTO operator_temperatures 
                    (id_sprzetu, temperatura, czas_ustawienia)
                    VALUES (%s, %s, %s)
                """, (sprzet_id, temperatura, current_time))

                # Natychmiast zaktualizuj teĹĽ stan w tabeli sprzet, aby zmiana byĹ‚a widoczna
                cursor.execute("""
                    UPDATE sprzet 
                    SET temperatura_aktualna = %s,
                        temperatura_docelowa = %s,
                        ostatnia_aktualizacja = %s
                    WHERE id = %s
                """, (temperatura, temperatura, current_time, sprzet_id))

                conn.commit()
                print(f"[{current_time}] Ustawiono nowÄ… temperaturÄ™ {temperatura}Â°C dla sprzÄ™tu ID={sprzet_id}")
                
                # JeĹ›li operacja siÄ™ udaĹ‚a, zakoĹ„cz dziaĹ‚anie metody
                return

            except OperationalError as e:
                if conn:
                    conn.rollback()
                # SprawdĹş, czy bĹ‚Ä…d to deadlock (1213) lub timeout (1205)
                if e.errno in (1213, 1205) and attempt < max_retries - 1:
                    print(f"Deadlock lub timeout przy ustawianiu temp. Ponawiam prĂłbÄ™ {attempt + 1}/{max_retries}...")
                    time.sleep(0.5)
                    continue # PrzejdĹş do nastÄ™pnej prĂłby
                else:
                    # JeĹ›li to inny bĹ‚Ä…d lub ostatnia prĂłba, rzuÄ‡ wyjÄ…tkiem dalej
                    raise e
            finally:
                if conn and conn.is_connected():
                    if 'cursor' in locals() and cursor:
                        cursor.close()
                    conn.close()
        
        # JeĹ›li pÄ™tla siÄ™ zakoĹ„czyĹ‚a bez sukcesu
        raise Exception("Nie udaĹ‚o siÄ™ ustawiÄ‡ temperatury po kilku prĂłbach z powodu blokady bazy danych.")

    def _simulate_temperature(self, sprzet_id, typ_sprzetu):
        """Symuluje wzrost temperatury od ostatniej znanej wartoĹ›ci"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Pobierz ostatniÄ… temperaturÄ™ ustawionÄ… przez operatora
            cursor.execute("""
                SELECT temperatura, czas_ustawienia
                FROM operator_temperatures
                WHERE id_sprzetu = %s
                ORDER BY czas_ustawienia DESC
                LIMIT 1
            """, (sprzet_id,))
            
            operator_temp = cursor.fetchone()
            current_time = datetime.now(timezone.utc)
            
            if not operator_temp:
                # Brak ustawionej temperatury - uĹĽyj domyĹ›lnej
                return 60.0
                
            # Oblicz przyrost temperatury
            minutes_passed = (current_time - operator_temp['czas_ustawienia']).total_seconds() / 60.0
            base_temperature = float(operator_temp['temperatura'])
            temperature_rise = minutes_passed * 0.14
            new_temperature = base_temperature + temperature_rise
            
            return round(new_temperature, 2)
            
        finally:
            cursor.close()
            conn.close()
    
    def read_sensors(self):
        """Odczytuje i aktualizuje dane z czujnikĂłw"""
        
        current_time = datetime.now(timezone.utc)
        print(f"[{current_time}] Rozpoczynam odczyt czujnikĂłw...")
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Pobierz aktywne urzÄ…dzenia
            cursor.execute("""
                SELECT id, nazwa_unikalna, typ_sprzetu 
                FROM sprzet 
                WHERE stan_sprzetu != 'WyĹ‚Ä…czony'
            """)
            equipment = cursor.fetchall()
            print(f"Znaleziono {len(equipment)} aktywnych urzÄ…dzeĹ„")
            
            for item in equipment:
                temperatura = self._simulate_temperature(item['id'], item['typ_sprzetu'])
                cisnienie = self._simulate_pressure(item['typ_sprzetu'])
                
                # Zapisz pomiar w historii
                cursor.execute("""
                    INSERT INTO historia_pomiarow 
                    (id_sprzetu, temperatura, cisnienie, czas_pomiaru)
                    VALUES (%s, %s, %s, %s)
                """, (item['id'], temperatura, cisnienie, current_time))
                
                # Aktualizuj stan sprzÄ™tu
                cursor.execute("""
                    UPDATE sprzet 
                    SET temperatura_aktualna = %s,
                        cisnienie_aktualne = %s,
                        ostatnia_aktualizacja = %s
                    WHERE id = %s
                """, (temperatura, cisnienie, current_time, item['id']))
                
                print(f"SprzÄ™t {item['nazwa_unikalna']}: T={temperatura}Â°C, P={cisnienie}bar")
            
            conn.commit()
            print(f"[{current_time}] Pomiary zapisane do bazy")
            
        except Exception as e:
            conn.rollback()
            print(f"BĹÄ„D podczas odczytu czujnikĂłw: {str(e)}")
            raise
        finally:
            cursor.close()
            conn.close()

    def _simulate_pressure(self, typ_sprzetu):
        """Symulacja odczytu ciĹ›nienia"""
        if typ_sprzetu == 'filtr':
            return round(random.uniform(4, 5), 2)
        elif typ_sprzetu == 'reaktor':
            return round(random.uniform(0, 2), 2)
        return 0.0
# app/topology_manager.py
# type: ignore

import mysql.connector
from flask import current_app, jsonify
from datetime import datetime
from .db import get_db_connection
import json

class TopologyManager:
    """MenedĹĽer do zarzÄ…dzania cyfrowÄ… mapÄ… rurociÄ…gu w systemie MES Parafina"""
    
    def __init__(self):
        pass
    
    # ================== ZAWORY ==================
    
    def get_zawory(self, include_segments=False):
        """Pobiera listÄ™ wszystkich zaworĂłw"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT z.*
                FROM zawory z
                ORDER BY z.nazwa_zaworu
            """)
            zawory = cursor.fetchall()
            
            if include_segments:
                for zawor in zawory:
                    cursor.execute("""
                        SELECT s.id, s.nazwa_segmentu 
                        FROM segmenty s 
                        WHERE s.id_zaworu = %s
                    """, (zawor['id'],))
                    zawor['segments'] = cursor.fetchall()
                    zawor['segments_count'] = len(zawor['segments'])
            else:
                for zawor in zawory:
                    zawor['segments_count'] = 0
            
            return zawory
        finally:
            cursor.close()
            conn.close()
    
    def get_zawor(self, zawor_id):
        """Pobiera szczegĂłĹ‚y konkretnego zaworu"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM zawory WHERE id = %s", (zawor_id,))
            zawor = cursor.fetchone()
            
            if zawor:
                # Pobierz segmenty uĹĽywajÄ…ce tego zaworu
                cursor.execute("""
                    SELECT s.id, s.nazwa_segmentu,
                           ps_start.nazwa_portu as port_startowy,
                           ps_end.nazwa_portu as port_koncowy,
                           ws_start.nazwa_wezla as wezel_startowy,
                           ws_end.nazwa_wezla as wezel_koncowy
                    FROM segmenty s
                    LEFT JOIN porty_sprzetu ps_start ON s.id_portu_startowego = ps_start.id
                    LEFT JOIN porty_sprzetu ps_end ON s.id_portu_koncowego = ps_end.id
                    LEFT JOIN wezly_rurociagu ws_start ON s.id_wezla_startowego = ws_start.id
                    LEFT JOIN wezly_rurociagu ws_end ON s.id_wezla_koncowego = ws_end.id
                    WHERE s.id_zaworu = %s
                """, (zawor_id,))
                zawor['segments'] = cursor.fetchall()
            
            return zawor
        finally:
            cursor.close()
            conn.close()
    
    def create_zawor(self, nazwa_zaworu, stan='ZAMKNIETY'):
        """Tworzy nowy zawĂłr"""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO zawory (nazwa_zaworu, stan)
                VALUES (%s, %s)
            """, (nazwa_zaworu, stan))
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()
            conn.close()
    
    def update_zawor(self, zawor_id, nazwa_zaworu=None, stan=None):
        """Aktualizuje zawĂłr"""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            updates = []
            params = []
            
            if nazwa_zaworu is not None:
                updates.append("nazwa_zaworu = %s")
                params.append(nazwa_zaworu)
            
            if stan is not None:
                updates.append("stan = %s")
                params.append(stan)
            
            if updates:
                params.append(zawor_id)
                cursor.execute(f"""
                    UPDATE zawory 
                    SET {', '.join(updates)}
                    WHERE id = %s
                """, params)
                conn.commit()
                return cursor.rowcount > 0
            return False
        finally:
            cursor.close()
            conn.close()
    
    def delete_zawor(self, zawor_id):
        """Usuwa zawĂłr (tylko jeĹ›li nie jest uĹĽywany w segmentach)"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # SprawdĹş czy zawĂłr jest uĹĽywany
            cursor.execute("SELECT COUNT(*) as count FROM segmenty WHERE id_zaworu = %s", (zawor_id,))
            result = cursor.fetchone()
            if result and result['count'] > 0:
                return False, "ZawĂłr jest uĹĽywany w segmentach i nie moĹĽe byÄ‡ usuniÄ™ty"
            
            cursor.execute("DELETE FROM zawory WHERE id = %s", (zawor_id,))
            conn.commit()
            return True, "ZawĂłr zostaĹ‚ usuniÄ™ty"
        finally:
            cursor.close()
            conn.close()
    
    # ================== WÄZĹY ==================
    
    def get_wezly(self, include_segments=False):
        """Pobiera listÄ™ wszystkich wÄ™zĹ‚Ăłw"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM wezly_rurociagu ORDER BY nazwa_wezla")
            wezly = cursor.fetchall()
            
            if include_segments:
                for wezel in wezly:
                    cursor.execute("""
                        SELECT s.id, s.nazwa_segmentu, z.nazwa_zaworu, z.stan as stan_zaworu,
                               CASE 
                                   WHEN s.id_wezla_startowego = %s THEN 'START'
                                   WHEN s.id_wezla_koncowego = %s THEN 'END'
                               END as pozycja
                        FROM segmenty s 
                        JOIN zawory z ON s.id_zaworu = z.id
                        WHERE s.id_wezla_startowego = %s OR s.id_wezla_koncowego = %s
                    """, (wezel['id'], wezel['id'], wezel['id'], wezel['id']))
                    wezel['segments'] = cursor.fetchall()
            
            return wezly
        finally:
            cursor.close()
            conn.close()
    
    def get_wezel(self, wezel_id):
        """Pobiera szczegĂłĹ‚y konkretnego wÄ™zĹ‚a"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM wezly_rurociagu WHERE id = %s", (wezel_id,))
            wezel = cursor.fetchone()
            
            if wezel:
                # Pobierz segmenty poĹ‚Ä…czone z tym wÄ™zĹ‚em
                cursor.execute("""
                    SELECT s.id, s.nazwa_segmentu, z.id as id_zaworu, z.nazwa_zaworu, z.stan as stan_zaworu,
                           CASE 
                               WHEN s.id_wezla_startowego = %s THEN 'START'
                               WHEN s.id_wezla_koncowego = %s THEN 'END'
                           END as pozycja,
                           CASE 
                               WHEN s.id_wezla_startowego = %s THEN 
                                   COALESCE(ps_end.nazwa_portu, ws_end.nazwa_wezla)
                               WHEN s.id_wezla_koncowego = %s THEN 
                                   COALESCE(ps_start.nazwa_portu, ws_start.nazwa_wezla)
                           END as drugi_koniec
                    FROM segmenty s
                    JOIN zawory z ON s.id_zaworu = z.id
                    LEFT JOIN porty_sprzetu ps_start ON s.id_portu_startowego = ps_start.id
                    LEFT JOIN porty_sprzetu ps_end ON s.id_portu_koncowego = ps_end.id
                    LEFT JOIN wezly_rurociagu ws_start ON s.id_wezla_startowego = ws_start.id
                    LEFT JOIN wezly_rurociagu ws_end ON s.id_wezla_koncowego = ws_end.id
                    WHERE s.id_wezla_startowego = %s OR s.id_wezla_koncowego = %s
                """, (wezel_id, wezel_id, wezel_id, wezel_id, wezel_id, wezel_id))
                wezel['segments'] = cursor.fetchall()
            
            return wezel
        finally:
            cursor.close()
            conn.close()
    
    def create_wezel(self, nazwa_wezla):
        """Tworzy nowy wÄ™zeĹ‚"""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO wezly_rurociagu (nazwa_wezla)
                VALUES (%s)
            """, (nazwa_wezla,))
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()
            conn.close()
    
    def update_wezel(self, wezel_id, nazwa_wezla):
        """Aktualizuje wÄ™zeĹ‚"""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE wezly_rurociagu 
                SET nazwa_wezla = %s
                WHERE id = %s
            """, (nazwa_wezla, wezel_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            cursor.close()
            conn.close()
    
    def delete_wezel(self, wezel_id):
        """Usuwa wÄ™zeĹ‚ (tylko jeĹ›li nie jest uĹĽywany w segmentach)"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # SprawdĹş czy wÄ™zeĹ‚ jest uĹĽywany
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM segmenty 
                WHERE id_wezla_startowego = %s OR id_wezla_koncowego = %s
            """, (wezel_id, wezel_id))
            if cursor.fetchone()['count'] > 0:
                return False, "WÄ™zeĹ‚ jest uĹĽywany w segmentach i nie moĹĽe byÄ‡ usuniÄ™ty"
            
            cursor.execute("DELETE FROM wezly_rurociagu WHERE id = %s", (wezel_id,))
            conn.commit()
            return True, "WÄ™zeĹ‚ zostaĹ‚ usuniÄ™ty"
        finally:
            cursor.close()
            conn.close()
    
    # ================== SEGMENTY ==================
    
    def get_segmenty(self, include_details=False):
        """Pobiera listÄ™ wszystkich segmentĂłw"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT s.*, z.nazwa_zaworu, z.stan as stan_zaworu,
                       ps_start.nazwa_portu as port_startowy,
                       ps_end.nazwa_portu as port_koncowy,
                       ws_start.nazwa_wezla as wezel_startowy,
                       ws_end.nazwa_wezla as wezel_koncowy,
                       sp_start.nazwa_unikalna as sprzet_startowy,
                       sp_end.nazwa_unikalna as sprzet_koncowy
                FROM segmenty s
                JOIN zawory z ON s.id_zaworu = z.id
                LEFT JOIN porty_sprzetu ps_start ON s.id_portu_startowego = ps_start.id
                LEFT JOIN porty_sprzetu ps_end ON s.id_portu_koncowego = ps_end.id
                LEFT JOIN wezly_rurociagu ws_start ON s.id_wezla_startowego = ws_start.id
                LEFT JOIN wezly_rurociagu ws_end ON s.id_wezla_koncowego = ws_end.id
                LEFT JOIN sprzet sp_start ON ps_start.id_sprzetu = sp_start.id
                LEFT JOIN sprzet sp_end ON ps_end.id_sprzetu = sp_end.id
                ORDER BY s.nazwa_segmentu
            """)
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()
    
    def get_segment(self, segment_id):
        """Pobiera szczegĂłĹ‚y konkretnego segmentu"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT s.*, z.nazwa_zaworu, z.stan as stan_zaworu,
                       ps_start.nazwa_portu as port_startowy,
                       ps_end.nazwa_portu as port_koncowy,
                       ws_start.nazwa_wezla as wezel_startowy,
                       ws_end.nazwa_wezla as wezel_koncowy,
                       sp_start.nazwa_unikalna as sprzet_startowy,
                       sp_start.typ_sprzetu as typ_sprzetu_startowego,
                       sp_end.nazwa_unikalna as sprzet_koncowy,
                       sp_end.typ_sprzetu as typ_sprzetu_koncowego
                FROM segmenty s
                JOIN zawory z ON s.id_zaworu = z.id
                LEFT JOIN porty_sprzetu ps_start ON s.id_portu_startowego = ps_start.id
                LEFT JOIN porty_sprzetu ps_end ON s.id_portu_koncowego = ps_end.id
                LEFT JOIN wezly_rurociagu ws_start ON s.id_wezla_startowego = ws_start.id
                LEFT JOIN wezly_rurociagu ws_end ON s.id_wezla_koncowego = ws_end.id
                LEFT JOIN sprzet sp_start ON ps_start.id_sprzetu = sp_start.id
                LEFT JOIN sprzet sp_end ON ps_end.id_sprzetu = sp_end.id
                WHERE s.id = %s
            """, (segment_id,))
            return cursor.fetchone()
        finally:
            cursor.close()
            conn.close()
    
    def create_segment(self, nazwa_segmentu, id_zaworu, id_portu_startowego=None, 
                      id_wezla_startowego=None, id_portu_koncowego=None, id_wezla_koncowego=None):
        """Tworzy nowy segment"""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Walidacja - kaĹĽdy segment musi mieÄ‡ punkt startowy i koĹ„cowy
            if not ((id_portu_startowego or id_wezla_startowego) and 
                    (id_portu_koncowego or id_wezla_koncowego)):
                return None, "Segment musi mieÄ‡ zdefiniowany punkt startowy i koĹ„cowy"
            
            cursor.execute("""
                INSERT INTO segmenty 
                (nazwa_segmentu, id_portu_startowego, id_wezla_startowego, 
                 id_portu_koncowego, id_wezla_koncowego, id_zaworu)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (nazwa_segmentu, id_portu_startowego, id_wezla_startowego,
                  id_portu_koncowego, id_wezla_koncowego, id_zaworu))
            conn.commit()
            return cursor.lastrowid, "Segment zostaĹ‚ utworzony"
        finally:
            cursor.close()
            conn.close()
    
    def update_segment(self, segment_id, **kwargs):
        """Aktualizuje segment"""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            allowed_fields = ['nazwa_segmentu', 'id_portu_startowego', 'id_wezla_startowego',
                             'id_portu_koncowego', 'id_wezla_koncowego', 'id_zaworu']
            
            updates = []
            params = []
            
            for field, value in kwargs.items():
                if field in allowed_fields:
                    updates.append(f"{field} = %s")
                    params.append(value)
            
            if updates:
                params.append(segment_id)
                cursor.execute(f"""
                    UPDATE segmenty 
                    SET {', '.join(updates)}
                    WHERE id = %s
                """, params)
                conn.commit()
                return cursor.rowcount > 0, "Segment zostaĹ‚ zaktualizowany"
            return False, "Brak danych do aktualizacji"
        finally:
            cursor.close()
            conn.close()
    
    def delete_segment(self, segment_id):
        """Usuwa segment"""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM segmenty WHERE id = %s", (segment_id,))
            conn.commit()
            return cursor.rowcount > 0, "Segment zostaĹ‚ usuniÄ™ty"
        finally:
            cursor.close()
            conn.close()
    
    # ================== PORTY I SPRZÄT ==================
    
    def get_porty_sprzetu(self):
        """Pobiera listÄ™ wszystkich portĂłw sprzÄ™tu"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT p.*, s.nazwa_unikalna, s.typ_sprzetu
                FROM porty_sprzetu p
                JOIN sprzet s ON p.id_sprzetu = s.id
                ORDER BY s.nazwa_unikalna, p.nazwa_portu
            """)
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()
    
    def get_sprzet(self):
        """Pobiera listÄ™ caĹ‚ego sprzÄ™tu"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT s.*, 
                       COUNT(p.id) as porty_count
                FROM sprzet s
                LEFT JOIN porty_sprzetu p ON s.id = p.id_sprzetu
                GROUP BY s.id
                ORDER BY s.nazwa_unikalna
            """)
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()
    
    # ================== WIZUALIZACJA TOPOLOGII ==================
    
    def get_topology_graph(self):
        """Zwraca dane topologii w formacie grafu dla wizualizacji"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # Pobierz wszystkie wÄ™zĹ‚y (sprzÄ™t + wÄ™zĹ‚y rurociÄ…gu)
            nodes = []
            edges = []
            
            # Dodaj sprzÄ™t jako wÄ™zĹ‚y
            cursor.execute("""
                SELECT id, nazwa_unikalna as name, typ_sprzetu as type, 
                       'equipment' as category, stan_sprzetu as status
                FROM sprzet
            """)
            equipment = cursor.fetchall()
            for eq in equipment:
                nodes.append({
                    'id': f"eq_{eq['id']}",
                    'name': eq['name'],
                    'type': eq['type'],
                    'category': 'equipment',
                    'status': eq['status']
                })
            
            # Dodaj wÄ™zĹ‚y rurociÄ…gu
            cursor.execute("SELECT id, nazwa_wezla as name FROM wezly_rurociagu")
            wezly = cursor.fetchall()
            for wezel in wezly:
                nodes.append({
                    'id': f"node_{wezel['id']}",
                    'name': wezel['name'],
                    'type': 'junction',
                    'category': 'junction'
                })
            
            # Dodaj krawÄ™dzie (segmenty)
            cursor.execute("""
                SELECT s.id, s.nazwa_segmentu, z.stan as stan_zaworu,
                       s.id_portu_startowego, s.id_wezla_startowego,
                       s.id_portu_koncowego, s.id_wezla_koncowego,
                       ps_start.id_sprzetu as sprzet_start_id,
                       ps_end.id_sprzetu as sprzet_end_id
                FROM segmenty s
                JOIN zawory z ON s.id_zaworu = z.id
                LEFT JOIN porty_sprzetu ps_start ON s.id_portu_startowego = ps_start.id
                LEFT JOIN porty_sprzetu ps_end ON s.id_portu_koncowego = ps_end.id
            """)
            segments = cursor.fetchall()
            
            for segment in segments:
                # OkreĹ›l wÄ™zeĹ‚ startowy
                if segment['id_portu_startowego']:
                    source = f"eq_{segment['sprzet_start_id']}"
                else:
                    source = f"node_{segment['id_wezla_startowego']}"
                
                # OkreĹ›l wÄ™zeĹ‚ koĹ„cowy
                if segment['id_portu_koncowego']:
                    target = f"eq_{segment['sprzet_end_id']}"
                else:
                    target = f"node_{segment['id_wezla_koncowego']}"
                
                edges.append({
                    'id': f"seg_{segment['id']}",
                    'source': source,
                    'target': target,
                    'name': segment['nazwa_segmentu'],
                    'valve_state': segment['stan_zaworu'],
                    'active': segment['stan_zaworu'] == 'OTWARTY'
                })
            
            return {
                'nodes': nodes,
                'edges': edges,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        finally:
            cursor.close()
            conn.close()
    
    def get_topology_text(self):
        """Zwraca tekstowy opis topologii"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT s.nazwa_segmentu, z.nazwa_zaworu, z.stan as stan_zaworu,
                       COALESCE(ps_start.nazwa_portu, ws_start.nazwa_wezla) as punkt_startowy,
                       COALESCE(ps_end.nazwa_portu, ws_end.nazwa_wezla) as punkt_koncowy,
                       COALESCE(sp_start.nazwa_unikalna, '') as sprzet_startowy,
                       COALESCE(sp_end.nazwa_unikalna, '') as sprzet_koncowy
                FROM segmenty s
                JOIN zawory z ON s.id_zaworu = z.id
                LEFT JOIN porty_sprzetu ps_start ON s.id_portu_startowego = ps_start.id
                LEFT JOIN porty_sprzetu ps_end ON s.id_portu_koncowego = ps_end.id
                LEFT JOIN wezly_rurociagu ws_start ON s.id_wezla_startowego = ws_start.id
                LEFT JOIN wezly_rurociagu ws_end ON s.id_wezla_koncowego = ws_end.id
                LEFT JOIN sprzet sp_start ON ps_start.id_sprzetu = sp_start.id
                LEFT JOIN sprzet sp_end ON ps_end.id_sprzetu = sp_end.id
                ORDER BY s.nazwa_segmentu
            """)
            segments = cursor.fetchall()
            
            text_lines = ["=== MAPA TOPOLOGII RUROCIÄ„GU ===", ""]
            
            for seg in segments:
                start_desc = f"{seg['sprzet_startowy']}:{seg['punkt_startowy']}" if seg['sprzet_startowy'] else seg['punkt_startowy']
                end_desc = f"{seg['sprzet_koncowy']}:{seg['punkt_koncowy']}" if seg['sprzet_koncowy'] else seg['punkt_koncowy']
                valve_status = "đźź˘ OTWARTY" if seg['stan_zaworu'] == 'OTWARTY' else "đź”´ ZAMKNIÄTY"
                
                text_lines.append(f"{seg['nazwa_segmentu']}: {start_desc} â†â†’ {end_desc}")
                text_lines.append(f"  ZawĂłr: {seg['nazwa_zaworu']} ({valve_status})")
                text_lines.append("")
            
            return "\n".join(text_lines)
        finally:
            cursor.close()
            conn.close()
# app/topology_routes.py
# type: ignore

from flask import Blueprint, jsonify, request, render_template
from datetime import datetime
from .topology_manager import TopologyManager
from .pathfinder_tester import PathFinderTester
from .db import get_db_connection
import time
import json

# Tworzenie blueprint dla topologii
topology_bp = Blueprint('topology', __name__, url_prefix='/topology')

# Inicjalizacja menedĹĽerĂłw
topology_manager = TopologyManager()
pathfinder_tester = PathFinderTester()

# ================== WIDOKI HTML ==================

@topology_bp.route('/')
def topology_index():
    """GĹ‚Ăłwna strona zarzÄ…dzania topologiÄ…"""
    return render_template('topology/index.html')

@topology_bp.route('/zawory')
def zawory_view():
    """Strona zarzÄ…dzania zaworami"""
    zawory = topology_manager.get_zawory(include_segments=True)
    return render_template('topology/zawory.html', zawory=zawory)

@topology_bp.route('/wezly')
def wezly_view():
    """Strona zarzÄ…dzania wÄ™zĹ‚ami"""
    wezly = topology_manager.get_wezly(include_segments=True)
    return render_template('topology/wezly.html', wezly=wezly)

@topology_bp.route('/segmenty')
def segmenty_view():
    """Strona zarzÄ…dzania segmentami"""
    segmenty = topology_manager.get_segmenty(include_details=True)
    return render_template('topology/segmenty.html', segmenty=segmenty)

@topology_bp.route('/visualization')
def visualization_view():
    """Strona wizualizacji topologii"""
    return render_template('topology/visualization.html')

@topology_bp.route('/pathfinder')
def pathfinder_view():
    """Strona testera PathFinder"""
    # Pobierz dostÄ™pne punkty do testowania
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT DISTINCT nazwa_portu as punkt, 'port' as typ FROM porty_sprzetu
            UNION
            SELECT DISTINCT nazwa_wezla as punkt, 'wezel' as typ FROM wezly_rurociagu
            ORDER BY punkt
        """)
        punkty = cursor.fetchall()
        
        # Pobierz zawory do selecta
        cursor.execute("SELECT id, nazwa_zaworu, stan FROM zawory ORDER BY nazwa_zaworu")
        zawory = cursor.fetchall()
        
        # Pobierz historiÄ™ testĂłw
        history = pathfinder_tester.get_test_history(limit=20)
        
        return render_template('topology/pathfinder.html', 
                             punkty=punkty, 
                             zawory=zawory,
                             test_history=history.get('test_history', []))
    finally:
        cursor.close()
        conn.close()

# ================== API ZAWORY ==================

@topology_bp.route('/api/zawory', methods=['GET'])
def api_get_zawory():
    """API: Pobiera listÄ™ zaworĂłw"""
    include_segments = request.args.get('include_segments', 'false').lower() == 'true'
    zawory = topology_manager.get_zawory(include_segments=include_segments)
    return jsonify({
        'success': True,
        'data': zawory,
        'count': len(zawory)
    })

@topology_bp.route('/api/zawory/<int:zawor_id>', methods=['GET'])
def api_get_zawor(zawor_id):
    """API: Pobiera szczegĂłĹ‚y zaworu"""
    zawor = topology_manager.get_zawor(zawor_id)
    if zawor:
        return jsonify({
            'success': True,
            'data': zawor
        })
    return jsonify({
        'success': False,
        'message': 'ZawĂłr nie zostaĹ‚ znaleziony'
    }), 404

@topology_bp.route('/api/zawory', methods=['POST'])
def api_create_zawor():
    """API: Tworzy nowy zawĂłr"""
    data = request.get_json()
    if not data or 'nazwa_zaworu' not in data:
        return jsonify({
            'success': False,
            'message': 'Wymagana jest nazwa zaworu'
        }), 400
    
    try:
        zawor_id = topology_manager.create_zawor(
            nazwa_zaworu=data['nazwa_zaworu'],
            stan=data.get('stan', 'ZAMKNIETY')
        )
        
        return jsonify({
            'success': True,
            'data': {'id': zawor_id},
            'message': 'ZawĂłr zostaĹ‚ utworzony'
        }), 201
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'BĹ‚Ä…d podczas tworzenia zaworu: {str(e)}'
        }), 500

@topology_bp.route('/api/zawory/<int:zawor_id>', methods=['PUT'])
def api_update_zawor(zawor_id):
    """API: Aktualizuje zawĂłr"""
    data = request.get_json()
    if not data:
        return jsonify({
            'success': False,
            'message': 'Brak danych do aktualizacji'
        }), 400
    
    try:
        success = topology_manager.update_zawor(
            zawor_id=zawor_id,
            nazwa_zaworu=data.get('nazwa_zaworu'),
            stan=data.get('stan')
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'ZawĂłr zostaĹ‚ zaktualizowany'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'ZawĂłr nie zostaĹ‚ znaleziony lub brak zmian'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'BĹ‚Ä…d podczas aktualizacji zaworu: {str(e)}'
        }), 500

@topology_bp.route('/api/zawory/<int:zawor_id>', methods=['DELETE'])
def api_delete_zawor(zawor_id):
    """API: Usuwa zawĂłr"""
    try:
        success, message = topology_manager.delete_zawor(zawor_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'BĹ‚Ä…d podczas usuwania zaworu: {str(e)}'
        }), 500

# ================== API WÄZĹY ==================

@topology_bp.route('/api/wezly', methods=['GET'])
def api_get_wezly():
    """API: Pobiera listÄ™ wÄ™zĹ‚Ăłw"""
    include_segments = request.args.get('include_segments', 'false').lower() == 'true'
    wezly = topology_manager.get_wezly(include_segments=include_segments)
    return jsonify({
        'success': True,
        'data': wezly,
        'count': len(wezly)
    })

@topology_bp.route('/api/wezly/<int:wezel_id>', methods=['GET'])
def api_get_wezel(wezel_id):
    """API: Pobiera szczegĂłĹ‚y wÄ™zĹ‚a"""
    wezel = topology_manager.get_wezel(wezel_id)
    if wezel:
        return jsonify({
            'success': True,
            'data': wezel
        })
    return jsonify({
        'success': False,
        'message': 'WÄ™zeĹ‚ nie zostaĹ‚ znaleziony'
    }), 404

@topology_bp.route('/api/wezly', methods=['POST'])
def api_create_wezel():
    """API: Tworzy nowy wÄ™zeĹ‚"""
    data = request.get_json()
    if not data or 'nazwa_wezla' not in data:
        return jsonify({
            'success': False,
            'message': 'Wymagana jest nazwa wÄ™zĹ‚a'
        }), 400
    
    try:
        wezel_id = topology_manager.create_wezel(data['nazwa_wezla'])
        
        return jsonify({
            'success': True,
            'data': {'id': wezel_id},
            'message': 'WÄ™zeĹ‚ zostaĹ‚ utworzony'
        }), 201
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'BĹ‚Ä…d podczas tworzenia wÄ™zĹ‚a: {str(e)}'
        }), 500

@topology_bp.route('/api/wezly/<int:wezel_id>', methods=['PUT'])
def api_update_wezel(wezel_id):
    """API: Aktualizuje wÄ™zeĹ‚"""
    data = request.get_json()
    if not data or 'nazwa_wezla' not in data:
        return jsonify({
            'success': False,
            'message': 'Wymagana jest nazwa wÄ™zĹ‚a'
        }), 400
    
    try:
        success = topology_manager.update_wezel(wezel_id, data['nazwa_wezla'])
        
        if success:
            return jsonify({
                'success': True,
                'message': 'WÄ™zeĹ‚ zostaĹ‚ zaktualizowany'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'WÄ™zeĹ‚ nie zostaĹ‚ znaleziony'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'BĹ‚Ä…d podczas aktualizacji wÄ™zĹ‚a: {str(e)}'
        }), 500

@topology_bp.route('/api/wezly/<int:wezel_id>', methods=['DELETE'])
def api_delete_wezel(wezel_id):
    """API: Usuwa wÄ™zeĹ‚"""
    try:
        success, message = topology_manager.delete_wezel(wezel_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'BĹ‚Ä…d podczas usuwania wÄ™zĹ‚a: {str(e)}'
        }), 500

# ================== API SEGMENTY ==================

@topology_bp.route('/api/segmenty', methods=['GET'])
def api_get_segmenty():
    """API: Pobiera listÄ™ segmentĂłw"""
    include_details = request.args.get('include_details', 'true').lower() == 'true'
    segmenty = topology_manager.get_segmenty(include_details=include_details)
    return jsonify({
        'success': True,
        'data': segmenty,
        'count': len(segmenty)
    })

@topology_bp.route('/api/segmenty/<int:segment_id>', methods=['GET'])
def api_get_segment(segment_id):
    """API: Pobiera szczegĂłĹ‚y segmentu"""
    segment = topology_manager.get_segment(segment_id)
    if segment:
        return jsonify({
            'success': True,
            'data': segment
        })
    return jsonify({
        'success': False,
        'message': 'Segment nie zostaĹ‚ znaleziony'
    }), 404

@topology_bp.route('/api/segmenty', methods=['POST'])
def api_create_segment():
    """API: Tworzy nowy segment"""
    data = request.get_json()
    if not data:
        return jsonify({
            'success': False,
            'message': 'Brak danych'
        }), 400
    
    required_fields = ['nazwa_segmentu', 'id_zaworu']
    if not all(field in data for field in required_fields):
        return jsonify({
            'success': False,
            'message': 'Wymagane pola: nazwa_segmentu, id_zaworu'
        }), 400
    
    try:
        segment_id, message = topology_manager.create_segment(
            nazwa_segmentu=data['nazwa_segmentu'],
            id_zaworu=data['id_zaworu'],
            id_portu_startowego=data.get('id_portu_startowego'),
            id_wezla_startowego=data.get('id_wezla_startowego'),
            id_portu_koncowego=data.get('id_portu_koncowego'),
            id_wezla_koncowego=data.get('id_wezla_koncowego')
        )
        
        if segment_id:
            return jsonify({
                'success': True,
                'data': {'id': segment_id},
                'message': message
            }), 201
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'BĹ‚Ä…d podczas tworzenia segmentu: {str(e)}'
        }), 500

@topology_bp.route('/api/segmenty/<int:segment_id>', methods=['PUT'])
def api_update_segment(segment_id):
    """API: Aktualizuje segment"""
    data = request.get_json()
    if not data:
        return jsonify({
            'success': False,
            'message': 'Brak danych do aktualizacji'
        }), 400
    
    try:
        success, message = topology_manager.update_segment(segment_id, **data)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'BĹ‚Ä…d podczas aktualizacji segmentu: {str(e)}'
        }), 500

@topology_bp.route('/api/segmenty/<int:segment_id>', methods=['DELETE'])
def api_delete_segment(segment_id):
    """API: Usuwa segment"""
    try:
        success, message = topology_manager.delete_segment(segment_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'BĹ‚Ä…d podczas usuwania segmentu: {str(e)}'
        }), 500

# ================== API WIZUALIZACJA ==================

@topology_bp.route('/api/visualization/graph', methods=['GET'])
def api_topology_graph():
    """API: Pobiera dane topologii w formacie grafu"""
    try:
        graph_data = topology_manager.get_topology_graph()
        return jsonify({
            'success': True,
            'data': graph_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'BĹ‚Ä…d podczas generowania grafu: {str(e)}'
        }), 500

@topology_bp.route('/api/visualization/text', methods=['GET'])
def api_topology_text():
    """API: Pobiera tekstowy opis topologii"""
    try:
        text_description = topology_manager.get_topology_text()
        return jsonify({
            'success': True,
            'data': {
                'text': text_description,
                'generated_at': datetime.now(timezone.utc).isoformat()
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'BĹ‚Ä…d podczas generowania opisu: {str(e)}'
        }), 500

# ================== API PATHFINDER ==================

@topology_bp.route('/api/pathfinder/test-connection', methods=['POST'])
def api_test_connection():
    """API: Testuje poĹ‚Ä…czenie miÄ™dzy punktami"""
    data = request.get_json()
    print(f"DEBUG: PathFinder API called with data: {data}")
    
    if not data or 'start_point' not in data or 'end_point' not in data:
        return jsonify({
            'success': False,
            'message': 'Wymagane pola: start_point, end_point'
        }), 400
    
    start_time = time.time()
    
    try:
        result = pathfinder_tester.test_connection_availability(
            start_point=data['start_point'],
            end_point=data['end_point'],
            valve_states=data.get('valve_states')
        )
        
        print(f"DEBUG: PathFinder result: {result}")
        
        execution_time = int((time.time() - start_time) * 1000)
        
        # Zapisz wynik do historii
        pathfinder_tester.save_test_result(
            test_type='connection_test',
            start_point=data['start_point'],
            end_point=data['end_point'],
            test_parameters={'valve_states': data.get('valve_states')},
            result=result,
            success=result.get('available', False),
            execution_time_ms=execution_time
        )
        
        return jsonify({
            'success': True,
            'data': result,
            'execution_time_ms': execution_time
        })
    except Exception as e:
        print(f"DEBUG: PathFinder API error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'BĹ‚Ä…d podczas testowania poĹ‚Ä…czenia: {str(e)}'
        }), 500

@topology_bp.route('/api/pathfinder/find-paths', methods=['POST'])
def api_find_paths():
    """API: Znajduje wszystkie Ĺ›cieĹĽki miÄ™dzy punktami"""
    data = request.get_json()
    if not data or 'start_point' not in data or 'end_point' not in data:
        return jsonify({
            'success': False,
            'message': 'Wymagane pola: start_point, end_point'
        }), 400
    
    start_time = time.time()
    
    try:
        result = pathfinder_tester.find_all_paths(
            start_point=data['start_point'],
            end_point=data['end_point'],
            max_paths=data.get('max_paths', 5)
        )
        
        execution_time = int((time.time() - start_time) * 1000)
        
        # Zapisz wynik do historii
        pathfinder_tester.save_test_result(
            test_type='find_paths',
            start_point=data['start_point'],
            end_point=data['end_point'],
            test_parameters={'max_paths': data.get('max_paths', 5)},
            result=result,
            success=result.get('count', 0) > 0,
            execution_time_ms=execution_time
        )
        
        return jsonify({
            'success': True,
            'data': result,
            'execution_time_ms': execution_time
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'BĹ‚Ä…d podczas wyszukiwania Ĺ›cieĹĽek: {str(e)}'
        }), 500

@topology_bp.route('/api/pathfinder/simulate-valves', methods=['POST'])
def api_simulate_valves():
    """API: Symuluje zmiany stanĂłw zaworĂłw"""
    data = request.get_json()
    if not data or 'valve_changes' not in data:
        return jsonify({
            'success': False,
            'message': 'Wymagane pole: valve_changes'
        }), 400
    
    start_time = time.time()
    
    try:
        result = pathfinder_tester.simulate_valve_states(data['valve_changes'])
        
        execution_time = int((time.time() - start_time) * 1000)
        
        # Zapisz wynik do historii
        pathfinder_tester.save_test_result(
            test_type='valve_simulation',
            start_point=None,
            end_point=None,
            test_parameters={'valve_changes': data['valve_changes']},
            result=result,
            success=len(result.get('simulation_results', [])) > 0,
            execution_time_ms=execution_time
        )
        
        return jsonify({
            'success': True,
            'data': result,
            'execution_time_ms': execution_time
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'BĹ‚Ä…d podczas symulacji zaworĂłw: {str(e)}'
        }), 500

@topology_bp.route('/api/pathfinder/critical-valves', methods=['GET'])
def api_critical_valves():
    """API: Analizuje krytyczne zawory"""
    start_time = time.time()
    
    try:
        result = pathfinder_tester.analyze_critical_valves()
        
        execution_time = int((time.time() - start_time) * 1000)
        
        return jsonify({
            'success': True,
            'data': result,
            'execution_time_ms': execution_time
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'BĹ‚Ä…d podczas analizy krytycznych zaworĂłw: {str(e)}'
        }), 500

@topology_bp.route('/api/pathfinder/history', methods=['GET'])
def api_pathfinder_history():
    """API: Pobiera historiÄ™ testĂłw PathFinder"""
    limit = request.args.get('limit', 50, type=int)
    
    try:
        result = pathfinder_tester.get_test_history(limit=limit)
        
        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'BĹ‚Ä…d podczas pobierania historii: {str(e)}'
        }), 500

# ================== API POMOCNICZE ==================

@topology_bp.route('/api/porty', methods=['GET'])
def api_get_porty():
    """API: Pobiera listÄ™ portĂłw sprzÄ™tu"""
    try:
        porty = topology_manager.get_porty_sprzetu()
        return jsonify({
            'success': True,
            'data': porty,
            'count': len(porty)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'BĹ‚Ä…d podczas pobierania portĂłw: {str(e)}'
        }), 500

@topology_bp.route('/api/sprzet', methods=['GET'])
def api_get_sprzet():
    """API: Pobiera listÄ™ sprzÄ™tu"""
    try:
        sprzet = topology_manager.get_sprzet()
        return jsonify({
            'success': True,
            'data': sprzet,
            'count': len(sprzet)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'BĹ‚Ä…d podczas pobierania sprzÄ™tu: {str(e)}'
        }), 500

@topology_bp.route('/api/points', methods=['GET'])
def api_get_points():
    """API: Pobiera wszystkie dostÄ™pne punkty (porty + wÄ™zĹ‚y)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT p.nazwa_portu as name, 'port' as type, s.nazwa_unikalna as equipment,
                   s.typ_sprzetu as equipment_type, p.typ_portu as port_type
            FROM porty_sprzetu p
            JOIN sprzet s ON p.id_sprzetu = s.id
            UNION
            SELECT w.nazwa_wezla as name, 'junction' as type, NULL as equipment,
                   NULL as equipment_type, NULL as port_type
            FROM wezly_rurociagu w
            ORDER BY name
        """)
        
        points = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': points,
            'count': len(points)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'BĹ‚Ä…d podczas pobierania punktĂłw: {str(e)}'
        }), 500

@topology_bp.route('/api/sprzet/<int:sprzet_id>/porty', methods=['GET'])
def api_get_sprzet_ports(sprzet_id):
    """API: Pobiera porty dla konkretnego sprzÄ™tu"""
    try:
        porty = topology_manager.get_porty_dla_sprzetu(sprzet_id)
        return jsonify({
            'success': True,
            'data': porty,
            'count': len(porty)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'BĹ‚Ä…d podczas pobierania portĂłw sprzÄ™tu: {str(e)}'
        }), 500

# ================== API DIAGNOSTYCZNE ==================

@topology_bp.route('/api/health-check', methods=['GET'])
def api_health_check():
    """API: Sprawdza stan zdrowia topologii i wykrywa problemy"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        health_issues = []
        warnings = []
        
        # SprawdĹş zawory bez segmentĂłw
        cursor.execute("""
            SELECT z.nazwa_zaworu 
            FROM zawory z 
            LEFT JOIN segmenty s ON z.id = s.id_zaworu 
            WHERE s.id IS NULL
        """)
        orphaned_valves = cursor.fetchall()
        if orphaned_valves:
            warnings.append({
                'type': 'orphaned_valves',
                'message': f'Znaleziono {len(orphaned_valves)} zaworĂłw bez segmentĂłw',
                'items': [v['nazwa_zaworu'] for v in orphaned_valves]
            })
        
        # SprawdĹş segmenty bez zaworĂłw
        cursor.execute("""
            SELECT s.nazwa_segmentu 
            FROM segmenty s 
            LEFT JOIN zawory z ON s.id_zaworu = z.id 
            WHERE z.id IS NULL
        """)
        segments_without_valves = cursor.fetchall()
        if segments_without_valves:
            health_issues.append({
                'type': 'segments_without_valves',
                'message': f'Znaleziono {len(segments_without_valves)} segmentĂłw bez zaworĂłw',
                'items': [s['nazwa_segmentu'] for s in segments_without_valves]
            })
        
        # SprawdĹş wÄ™zĹ‚y bez poĹ‚Ä…czeĹ„
        cursor.execute("""
            SELECT w.nazwa_wezla 
            FROM wezly_rurociagu w 
            LEFT JOIN segmenty s1 ON w.id = s1.id_wezla_startowego 
            LEFT JOIN segmenty s2 ON w.id = s2.id_wezla_koncowego 
            WHERE s1.id IS NULL AND s2.id IS NULL
        """)
        isolated_nodes = cursor.fetchall()
        if isolated_nodes:
            warnings.append({
                'type': 'isolated_nodes',
                'message': f'Znaleziono {len(isolated_nodes)} izolowanych wÄ™zĹ‚Ăłw',
                'items': [n['nazwa_wezla'] for n in isolated_nodes]
            })
        
        # SprawdĹş sprzÄ™t bez portĂłw
        cursor.execute("""
            SELECT s.nazwa_unikalna 
            FROM sprzet s 
            LEFT JOIN porty_sprzetu p ON s.id = p.id_sprzetu 
            WHERE p.id IS NULL
        """)
        equipment_without_ports = cursor.fetchall()
        if equipment_without_ports:
            warnings.append({
                'type': 'equipment_without_ports',
                'message': f'Znaleziono {len(equipment_without_ports)} sprzÄ™tĂłw bez portĂłw',
                'items': [e['nazwa_unikalna'] for e in equipment_without_ports]
            })
        
        # Oblicz ogĂłlny stan zdrowia
        total_issues = len(health_issues)
        total_warnings = len(warnings)
        
        if total_issues > 0:
            status = 'critical'
            status_message = f'Krytyczne problemy w topologii: {total_issues}'
        elif total_warnings > 0:
            status = 'warning'
            status_message = f'OstrzeĹĽenia w topologii: {total_warnings}'
        else:
            status = 'healthy'
            status_message = 'Topologia w dobrym stanie'
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                'status': status,
                'message': status_message,
                'issues': health_issues,
                'warnings': warnings,
                'summary': {
                    'total_issues': total_issues,
                    'total_warnings': total_warnings,
                    'checked_at': datetime.now(timezone.utc).isoformat()
                }
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'BĹ‚Ä…d podczas sprawdzania stanu topologii: {str(e)}'
        }), 500

@topology_bp.route('/api/isolated-nodes', methods=['GET'])
def api_isolated_nodes():
    """API: Znajduje izolowane wÄ™zĹ‚y w topologii"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # ZnajdĹş wÄ™zĹ‚y bez poĹ‚Ä…czeĹ„
        cursor.execute("""
            SELECT w.id, w.nazwa_wezla, w.opis,
                   COUNT(s1.id) + COUNT(s2.id) as connections_count
            FROM wezly_rurociagu w 
            LEFT JOIN segmenty s1 ON w.id = s1.id_wezla_startowego 
            LEFT JOIN segmenty s2 ON w.id = s2.id_wezla_koncowego 
            GROUP BY w.id, w.nazwa_wezla, w.opis
            HAVING connections_count = 0
            ORDER BY w.nazwa_wezla
        """)
        isolated_nodes = cursor.fetchall()
        
        # ZnajdĹş wÄ™zĹ‚y z tylko jednym poĹ‚Ä…czeniem (martwe koĹ„ce)
        cursor.execute("""
            SELECT w.id, w.nazwa_wezla, w.opis,
                   COUNT(s1.id) + COUNT(s2.id) as connections_count
            FROM wezly_rurociagu w 
            LEFT JOIN segmenty s1 ON w.id = s1.id_wezla_startowego 
            LEFT JOIN segmenty s2 ON w.id = s2.id_wezla_koncowego 
            GROUP BY w.id, w.nazwa_wezla, w.opis
            HAVING connections_count = 1
            ORDER BY w.nazwa_wezla
        """)
        dead_end_nodes = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                'isolated_nodes': isolated_nodes,
                'dead_end_nodes': dead_end_nodes,
                'summary': {
                    'isolated_count': len(isolated_nodes),
                    'dead_end_count': len(dead_end_nodes),
                    'analyzed_at': datetime.now(timezone.utc).isoformat()
                }
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'BĹ‚Ä…d podczas analizy izolowanych wÄ™zĹ‚Ăłw: {str(e)}'
        }), 500
# app/__init__.py

from flask import Flask
from .config import Config
from .pathfinder_service import PathFinder
from .monitoring import MonitoringService  # Dodaj import
from .sensors import SensorService
from flask_apscheduler import APScheduler
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime


# Tworzymy pustÄ… instancjÄ™, ktĂłra zostanie zainicjowana w create_app

pathfinder = PathFinder()
monitoring = MonitoringService()  # Dodaj instancjÄ™
sensor_service = SensorService()
scheduler = APScheduler()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Inicjalizacja serwisĂłw
    pathfinder.init_app(app)
    monitoring.init_app(app)  # Dodaj inicjalizacjÄ™
    sensor_service.init_app(app)
    app.extensions = getattr(app, 'extensions', {})
    app.extensions['pathfinder'] = pathfinder
    app.extensions['sensor_service'] = sensor_service
   # Konfiguracja schedulera
    app.config['SCHEDULER_API_ENABLED'] = True
    app.config['SCHEDULER_TIMEZONE'] = "Europe/Warsaw"
    
    scheduler.init_app(app)
    scheduler.scheduler.configure(timezone="Europe/Warsaw")

    @scheduler.task('interval', 
                   id='read_sensors', 
                   seconds=600,  # Odczyt co 10 minut
                   max_instances=1,
                   next_run_time=datetime.now(timezone.utc))
    def read_sensors():
        """Odczyt z czujnikĂłw co dokĹ‚adnie 60 sekund"""
        print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}] Zaplanowane uruchomienie odczytu czujnikĂłw")
        with app.app_context():
            try:
                sensor_service.read_sensors()
            except Exception as e:
                print(f"BĹ‚Ä…d podczas odczytu czujnikĂłw: {str(e)}")

    @scheduler.task('interval', 
                   id='check_alarms', 
                   seconds=30,
                   max_instances=1)
    def check_alarms():
        """Sprawdzanie alarmĂłw co 5 minut"""
        with app.app_context():
            monitoring.check_equipment_status()

    scheduler.start()

    # Rejestrujemy blueprinty
    from . import routes
    from .cykle_api import cykle_bp
    from .topology_routes import topology_bp  # Dodaj import topology blueprint
    from .operations_routes import bp as operations_bp # Import nowego blueprintu
    app.register_blueprint(routes.bp)
    app.register_blueprint(cykle_bp)
    app.register_blueprint(topology_bp)  # Zarejestruj topology blueprint
    app.register_blueprint(operations_bp) # Zarejestruj nowy blueprint

    @app.route('/hello')
    def hello():
        return "Witaj w aplikacji MES!"

    return app
