# app/apollo_service.py

from datetime import datetime, timedelta, timezone
#from .db import get_db_connection
#import mysql.connector
from .extensions import db  # Importujemy obiekt `db` z __init__.py
from .models import Sprzet, ApolloSesje, ApolloTracking, PartieSurowca, OperacjeLog
from decimal import Decimal
from sqlalchemy import func
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
        """
        Oblicza aktualny stan Apollo na podstawie sumy wytopionych porcji.
        Wersja 4: Niezawodny model "wielu porcji".
        """
        czas_teraz = current_time if current_time is not None else datetime.now()
        
        sesja = db.session.execute(
            db.select(ApolloSesje).filter_by(id_sprzetu=id_sprzetu, status_sesji='aktywna')
        ).scalar_one_or_none()

        if not sesja:
            return {'aktywna_sesja': False, 'dostepne_kg': 0}

        # Pobierz wszystkie zdarzenia, które dodają surowiec do puli
        porcje_q = db.select(ApolloTracking).filter(
            ApolloTracking.id_sesji == sesja.id,
            ApolloTracking.typ_zdarzenia.in_(['DODANIE_SUROWCA', 'KOREKTA_RECZNA'])
        ).order_by(ApolloTracking.czas_zdarzenia)
        
        porcje = db.session.execute(porcje_q).scalars().all()

        calkowity_plynny_potencjal = Decimal('0.0')

        # Jeśli ostatnim zdarzeniem jest korekta, tylko ona się liczy
        if porcje and porcje[-1].typ_zdarzenia == 'KOREKTA_RECZNA':
            ostatnia_korekta = porcje[-1]
            czas_od_korekty_s = (czas_teraz - ostatnia_korekta.czas_zdarzenia).total_seconds()
            wytopiono_po_korekcie = (Decimal(max(0, czas_od_korekty_s)) / Decimal(3600)) * Decimal(ApolloService.SZYBKOSC_WYTAPIANIA_KG_H)
            
            # W tym uproszczonym modelu po korekcie zakładamy, że dalszy wsad (którego nie ma) ogranicza topienie
            calkowity_plynny_potencjal = ostatnia_korekta.waga_kg + wytopiono_po_korekcie
            # Należałoby dodać logikę sumowania wsadów po korekcie, ale na razie to uprościmy
            # Dla pewności, że nie wytopimy "z powietrza", ograniczmy to do wagi korekty
            calkowity_plynny_potencjal = ostatnia_korekta.waga_kg

        else: # Standardowa logika sumowania porcji
            for porcja in porcje:
                czas_topienia_s = (czas_teraz - porcja.czas_zdarzenia).total_seconds()
                
                if czas_topienia_s > 0:
                    wytopiono_z_porcji_potencjalnie = (Decimal(czas_topienia_s) / Decimal(3600)) * Decimal(ApolloService.SZYBKOSC_WYTAPIANIA_KG_H)
                    realnie_wytopiono_z_porcji = min(porcja.waga_kg, wytopiono_z_porcji_potencjalnie)
                    calkowity_plynny_potencjal += realnie_wytopiono_z_porcji

        # Odejmij wszystkie transfery, które miały miejsce w sesji
        suma_transferow_q = db.select(func.sum(ApolloTracking.waga_kg)).filter(
            ApolloTracking.id_sesji == sesja.id,
            ApolloTracking.typ_zdarzenia == 'TRANSFER_WYJSCIOWY'
        )
        suma_transferow = db.session.execute(suma_transferow_q).scalar() or Decimal('0.0')

        dostepne_kg = calkowity_plynny_potencjal - suma_transferow
        
        return {
            'aktywna_sesja': True,
            'id_sesji': sesja.id,
            'typ_surowca': sesja.typ_surowca,
            'dostepne_kg': round(float(max(Decimal('0.0'), dostepne_kg)), 2),
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
        """
        Kończy aktywną sesję w Apollo i archiwizuje powiązaną partię surowca.
        """
        try:
            # 1. Znajdź aktywną sesję
            sesja = db.session.execute(
                db.select(ApolloSesje).filter_by(id_sprzetu=id_sprzetu, status_sesji='aktywna')
            ).scalar_one_or_none()

            if not sesja:
                raise ValueError(f"Apollo o ID {id_sprzetu} nie ma aktywnej sesji do zakończenia.")
            
            # 2. Zmień status sesji
            sesja.status_sesji = 'zakonczona'
            sesja.czas_zakonczenia = datetime.now()

            # 3. Znajdź partię powiązaną z tą sesją i zarchiwizuj ją
            #    Zakładamy, że partia ma podobny czas utworzenia co sesja.
            #    To jest założenie, które musimy poprawić w przyszłości.
            #    Lepszym rozwiązaniem byłoby dodanie `id_sesji` do tabeli `partie_surowca`.
            partia = db.session.execute(
                db.select(PartieSurowca).filter(
                    PartieSurowca.id_sprzetu == id_sprzetu,
                    PartieSurowca.status_partii == 'Surowy w reaktorze'
                ).order_by(PartieSurowca.data_utworzenia.desc())
            ).scalars().first()
            
            if partia:
                partia.status_partii = 'Archiwalna'
                # Opcjonalnie: odepnij partię od sprzętu
                partia.id_sprzetu = None

            db.session.commit()

        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_stan_apollo(id_sprzetu: int):
        """
        Pobiera aktualny, dynamiczny stan danego Apollo, delegując
        obliczenia do nowej, precyzyjnej metody symulacyjnej.
        """
        try:
            apollo = db.session.get(Sprzet, id_sprzetu)
            if not apollo:
                return None # lub rzucić wyjątek

            # Podstawowe dane o sprzęcie
            result = {
                'id_sprzetu': apollo.id,
                'nazwa_apollo': apollo.nazwa_unikalna,
                'aktywna_sesja': False
            }
            
            sesja = db.session.execute(
                db.select(ApolloSesje).filter_by(id_sprzetu=id_sprzetu, status_sesji='aktywna')
            ).scalar_one_or_none()

            if not sesja:
                return result # Zwróć podstawowe dane, jeśli nie ma sesji

            # --- KLUCZOWA ZMIANA ---
            # Wywołaj nową, poprawną metodę, aby uzyskać dokładną dostępną ilość
            stan_obliczony = ApolloService.oblicz_aktualny_stan_apollo(id_sprzetu)
            
            # Oblicz bilans "księgowy" dla informacji dodatkowej w GUI
            total_added_q = db.select(func.sum(ApolloTracking.waga_kg)).where(
                ApolloTracking.id_sesji == sesja.id,
                ApolloTracking.typ_zdarzenia == 'DODANIE_SUROWCA'
            )
            total_added = db.session.execute(total_added_q).scalar() or Decimal('0.0')

            total_transferred_q = db.select(func.sum(ApolloTracking.waga_kg)).where(
                ApolloTracking.id_sesji == sesja.id,
                ApolloTracking.typ_zdarzenia == 'TRANSFER_WYJSCIOWY'
            )
            total_transferred = db.session.execute(total_transferred_q).scalar() or Decimal('0.0')

            bilans_ksiegowy_kg = float(total_added - total_transferred)
            
            # Pobierz ostatni transfer dla celów informacyjnych
            ostatni_transfer = db.session.execute(
                db.select(ApolloTracking).where(
                    ApolloTracking.id_sesji == sesja.id,
                    ApolloTracking.typ_zdarzenia == 'TRANSFER_WYJSCIOWY'
                ).order_by(ApolloTracking.czas_zdarzenia.desc())
            ).scalars().first()

            # Zaktualizuj słownik wynikowy o wszystkie potrzebne dane
            result.update({
                'aktywna_sesja': True,
                'id_sesji': sesja.id,
                'typ_surowca': sesja.typ_surowca,
                'dostepne_kg': stan_obliczony['dostepne_kg'], # Użyj wyniku z nowej metody
                'bilans_sesji_kg': round(max(0, bilans_ksiegowy_kg), 2),
                'ostatni_transfer_czas': ostatni_transfer.czas_zdarzenia.strftime('%Y-%m-%d %H:%M:%S') if ostatni_transfer else None,
                'ostatni_transfer_kg': float(ostatni_transfer.waga_kg) if ostatni_transfer else None
            })

            return result
        except Exception as e:
            # Lepsze logowanie błędów
            print(f"Błąd bazy danych przy pobieraniu stanu Apollo (ID: {id_sprzetu}): {e}")
            import traceback
            traceback.print_exc()
            raise # Rzuć wyjątkiem, aby warstwa API mogła go obsłużyć