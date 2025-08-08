# app/apollo_service.py

from datetime import datetime, timedelta, timezone
from .db import get_db_connection
import mysql.connector
from . import db  # Importujemy obiekt `db` z __init__.py
from .models import Sprzet, ApolloSesje, ApolloTracking, PartieSurowca
from decimal import Decimal
class ApolloService:
    SZYBKOSC_WYTAPIANIA_KG_H = 1000.0

    
    @staticmethod
    def rozpocznij_sesje_apollo(id_sprzetu, typ_surowca, waga_kg, operator=None, event_time=None):
        czas_startu = event_time if event_time is not None else datetime.now()
        try:
            istniejaca_sesja = db.session.execute(
                db.select(ApolloSesje).filter_by(id_sprzetu=id_sprzetu, status_sesji='aktywna')
            ).scalar_one_or_none()
            if istniejaca_sesja:
                raise ValueError(f"Apollo o ID {id_sprzetu} ma już aktywną sesję.")

            nowa_sesja = ApolloSesje(
                id_sprzetu=id_sprzetu, typ_surowca=typ_surowca, czas_rozpoczecia=czas_startu,
                rozpoczeta_przez=operator, status_sesji='aktywna'
            )
            
            poczatek_trackingu = ApolloTracking(
                apollo_sesje=nowa_sesja, typ_zdarzenia='DODANIE_SUROWCA', waga_kg=waga_kg,
                czas_zdarzenia=czas_startu, operator=operator
            )
            
            sprzet = db.session.get(Sprzet, id_sprzetu)
            nazwa_sprzetu = sprzet.nazwa_unikalna if sprzet else f"ID{id_sprzetu}"
            timestamp_str = czas_startu.strftime('%Y%m%d-%H%M%S')
            unikalny_kod_partii = f"{nazwa_sprzetu}-{timestamp_str}"
            nazwa_partii = f"Partia w {nazwa_sprzetu} ({typ_surowca}) - {timestamp_str}"

            nowa_partia = PartieSurowca(
                unikalny_kod=unikalny_kod_partii, nazwa_partii=nazwa_partii, typ_surowca=typ_surowca,
                waga_poczatkowa_kg=waga_kg, waga_aktualna_kg=waga_kg, id_sprzetu=id_sprzetu,
                zrodlo_pochodzenia='apollo', status_partii='Surowy w reaktorze', typ_transformacji='NOWA'
            )

            db.session.add_all([nowa_sesja, poczatek_trackingu, nowa_partia])
            db.session.commit()
            return nowa_sesja.id
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def dodaj_surowiec_do_apollo(id_sprzetu, waga_kg, operator=None, event_time=None):
        czas_zdarzenia = event_time if event_time is not None else datetime.now()
        try:
            sesja = db.session.execute(
                db.select(ApolloSesje).filter_by(id_sprzetu=id_sprzetu, status_sesji='aktywna')
            ).scalar_one_or_none()
            if not sesja:
                raise ValueError(f"Apollo o ID {id_sprzetu} nie ma aktywnej sesji.")

            nowy_tracking = ApolloTracking(
                id_sesji=sesja.id, typ_zdarzenia='DODANIE_SUROWCA', waga_kg=waga_kg,
                czas_zdarzenia=czas_zdarzenia, operator=operator
            )
            db.session.add(nowy_tracking)
            
            partia = db.session.execute(
                db.select(PartieSurowca).filter_by(id_sprzetu=id_sprzetu)
            ).scalar_one_or_none()
            if partia:
                partia.waga_aktualna_kg += Decimal(waga_kg)
            else:
                # Gałąź awaryjna
                sprzet = db.session.get(Sprzet, id_sprzetu)
                nazwa_sprzetu = sprzet.nazwa_unikalna if sprzet else f"ID{id_sprzetu}"
                timestamp_str = czas_zdarzenia.strftime('%Y%m%d-%H%M%S')
                unikalny_kod_partii = f"{nazwa_sprzetu}-{timestamp_str}-AUTOCREATED"
                nazwa_partii = f"Partia w {nazwa_sprzetu} ({sesja.typ_surowca}) - {timestamp_str}"
                partia_awaryjna = PartieSurowca(
                    unikalny_kod=unikalny_kod_partii, nazwa_partii=nazwa_partii, typ_surowca=sesja.typ_surowca,
                    waga_poczatkowa_kg=waga_kg, waga_aktualna_kg=waga_kg, id_sprzetu=id_sprzetu,
                    zrodlo_pochodzenia='apollo', status_partii='Surowy w reaktorze', typ_transformacji='NOWA'
                )
                db.session.add(partia_awaryjna)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def oblicz_aktualny_stan_apollo(id_sprzetu, current_time=None):
        czas_teraz = current_time if current_time is not None else datetime.now()
        
        sesja = db.session.execute(
            db.select(ApolloSesje).filter_by(id_sprzetu=id_sprzetu, status_sesji='aktywna')
        ).scalar_one_or_none()
        if not sesja:
            return {'aktywna_sesja': False, 'dostepne_kg': 0}
        
        zdarzenia_query = db.select(ApolloTracking).filter_by(id_sesji=sesja.id).order_by(ApolloTracking.czas_zdarzenia)
        zdarzenia = db.session.execute(zdarzenia_query).scalars().all()

        # --- ORYGINALNA, POPRAWNA LOGIKA W WERSJI ORM ---
        
        ilosc_na_starcie = 0.0
        punkt_startowy_czas = sesja.czas_rozpoczecia
        
        korekty = [z for z in zdarzenia if z.typ_zdarzenia == 'KOREKTA_RECZNA']
        if korekty:
            ostatnia_korekta = korekty[-1]
            punkt_startowy_czas = ostatnia_korekta.czas_zdarzenia
            ilosc_na_starcie = float(ostatnia_korekta.waga_kg)

        # 1. Oblicz transfery, które nastąpiły PO punkcie startowym
        przetransferowano_po_starcie = sum(
            float(z.waga_kg) for z in zdarzenia 
            if z.typ_zdarzenia == 'TRANSFER_WYJSCIOWY' and z.czas_zdarzenia > punkt_startowy_czas
        )

        # 2. Oblicz limit topnienia na podstawie tego, co dodano
        if korekty:
            # Po korekcie, limit to tylko surowiec dodany PO niej
            limit_topnienia = sum(
                float(z.waga_kg) for z in zdarzenia 
                if z.typ_zdarzenia == 'DODANIE_SUROWCA' and z.czas_zdarzenia > punkt_startowy_czas
            )
        else:
            # Przed korektą, limit to CAŁY dodany surowiec
            limit_topnienia = sum(
                float(z.waga_kg) for z in zdarzenia if z.typ_zdarzenia == 'DODANIE_SUROWCA'
            )

        # 3. Oblicz topnienie
        czas_topienia_sekundy = (czas_teraz - punkt_startowy_czas).total_seconds()
        wytopiono_w_czasie = (max(0, czas_topienia_sekundy) / 3600.0) * ApolloService.SZYBKOSC_WYTAPIANIA_KG_H
        
        realnie_wytopiono = min(wytopiono_w_czasie, limit_topnienia)
        
        # 4. Finalne obliczenie
        dostepne_kg = ilosc_na_starcie + realnie_wytopiono - przetransferowano_po_starcie

        return {
            'aktywna_sesja': True,
            'id_sesji': sesja.id,
            'typ_surowca': sesja.typ_surowca,
            'dostepne_kg': round(max(0, dostepne_kg), 2),
            'czas_rozpoczecia': sesja.czas_rozpoczecia.isoformat()
        }

    @staticmethod
    def koryguj_stan_apollo(id_sprzetu, rzeczywista_waga_kg, operator=None, uwagi=None, event_time=None):
        czas_zdarzenia = event_time if event_time is not None else datetime.now()
        try:
            sesja = db.session.execute(
                db.select(ApolloSesje).filter_by(id_sprzetu=id_sprzetu, status_sesji='aktywna')
            ).scalar_one_or_none()
            if not sesja:
                raise ValueError(f"Apollo o ID {id_sprzetu} nie ma aktywnej sesji.")

            korekta = ApolloTracking(
                id_sesji=sesja.id, typ_zdarzenia='KOREKTA_RECZNA', waga_kg=rzeczywista_waga_kg,
                czas_zdarzenia=czas_zdarzenia, operator=operator, uwagi=uwagi
            )
            db.session.add(korekta)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

    
            
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