import random
import time
from datetime import datetime, timezone
from flask import current_app
from mysql.connector.errors import OperationalError
from .db import get_db_connection
from .extensions import db
from .models import Sprzet, OperatorTemperatures, HistoriaPomiarow
from decimal import Decimal

class SensorService:
    def __init__(self, app=None):
        self.app = app
        
       
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self.app = app
        # Don't load temperatures here - will do it in context
        
            
    @staticmethod
    def set_current_temperature(equipment_names, temperatura):
        """
        Ustawia TYLKO aktualną temperaturę dla listy sprzętów, np. po zatankowaniu.
        Nie zmienia temperatury docelowej.
        """
        if not equipment_names:
            return []

        try:
            # Używamy UPDATE, aby zmienić tylko te dwa pola
            stmt = db.update(Sprzet).where(
                Sprzet.nazwa_unikalna.in_(equipment_names)
            ).values(
                temperatura_aktualna=temperatura,
                ostatnia_aktualizacja=datetime.now(timezone.utc)
            )
            
            # `execute` zwraca obiekt result, z którego możemy odczytać, ile wierszy zmieniono
            result = db.session.execute(stmt)
            db.session.commit()
            
            print(f"Zaktualizowano `temperatura_aktualna` dla {result.rowcount} urządzeń.")
            
            # Zwracamy listę podanych nazw, aby potwierdzić, że polecenie zostało przyjęte
            # (nawet jeśli niektóre nazwy nie istniały w bazie)
            return equipment_names

        except Exception as e:
            db.session.rollback()
            print(f"Wystąpił błąd podczas ustawiania temperatury aktualnej: {e}")
            raise
    
    

    def _calculate_new_temperature(self, reaktor: Sprzet) -> Decimal:
        """Czysta funkcja obliczeniowa z dodatkowym logowaniem."""
        #print(f"    [CALC] --- Rozpoczynam obliczenia dla: {reaktor.nazwa_unikalna} ---")
        
        base_temperature = reaktor.temperatura_aktualna or Decimal('20.0')
        #print(f"    [CALC] Temperatura bazowa (aktualna): {base_temperature}°C")
        
        last_update_time = reaktor.ostatnia_aktualizacja or datetime.now(timezone.utc)
        if last_update_time.tzinfo is None:
            last_update_time = last_update_time.replace(tzinfo=timezone.utc)
        #print(f"    [CALC] Czas ostatniej aktualizacji: {last_update_time}")

        current_time = datetime.now(timezone.utc)
        #print(f"    [CALC] Obecny czas: {current_time}")
        
        minutes_passed = Decimal((current_time - last_update_time).total_seconds()) / Decimal(60)
        #print(f"    [CALC] Minut od ostatniej aktualizacji: {minutes_passed:.4f}")
        
        if minutes_passed <= 0:
            #print(f"    [CALC] Czas < 0. Zwracam temperaturę bazową: {base_temperature}°C")
            return base_temperature

        if reaktor.stan_palnika == 'WLACZONY':
            #print("    [CALC] Stan palnika: WLACZONY. Obliczam grzanie.")
            szybkosc_grzania = reaktor.szybkosc_grzania_c_na_minute or Decimal('0.5')
            temp_docelowa = reaktor.temperatura_docelowa or Decimal('120.0')
            przyrost = minutes_passed * szybkosc_grzania
            new_temperature = min(temp_docelowa, base_temperature + przyrost)
            #print(f"    [CALC] Szybkość grzania: {szybkosc_grzania}°C/min, Przyrost: {przyrost:.4f}°C, Nowa temp: {new_temperature:.4f}°C")
        else:
            #print(f"    [CALC] Stan palnika: {reaktor.stan_palnika}. Obliczam chłodzenie.")
            szybkosc_chlodzenia = reaktor.szybkosc_chlodzenia_c_na_minute or Decimal('0.1')
            spadek = minutes_passed * szybkosc_chlodzenia
            new_temperature = max(Decimal('20.0'), base_temperature - spadek)
            #print(f"    [CALC] Szybkość chłodzenia: {szybkosc_chlodzenia}°C/min, Spadek: {spadek:.4f}°C, Nowa temp: {new_temperature:.4f}°C")

        #print(f"    [CALC] --- Koniec obliczeń dla {reaktor.nazwa_unikalna}. Zwracam: {new_temperature} ---")
        return new_temperature

    def read_sensors(self):
        """Odczytuje i aktualizuje dane z czujników (wersja ORM z odświeżaniem)."""
        current_time = datetime.now(timezone.utc)
        print(f"\n--- SCHEDULER: Uruchamiam read_sensors o {current_time} ---")

        try:
            aktywny_sprzet_q = db.select(Sprzet).where(Sprzet.stan_sprzetu != 'Wyłączony')
            equipment_list = db.session.execute(aktywny_sprzet_q).scalars().all()
            print(f"Znaleziono {len(equipment_list)} aktywnych urządzeń.")
            print(equipment_list)
            pomiary_do_dodania = []
            
            # KROK 1: Oblicz wszystkie nowe wartości w pętli
            for item in equipment_list:
                nowa_temperatura = item.temperatura_aktualna
                if item.typ_sprzetu == 'reaktor':
                    # Obliczenia bazują na stanie obiektu z poprzedniej iteracji w pamięci
                    nowa_temperatura = self._calculate_new_temperature(item)
                
                nowe_cisnienie = self._simulate_pressure(item.typ_sprzetu)

                # Zaktualizuj stan obiektu w pamięci sesji
                item.temperatura_aktualna = nowa_temperatura
                item.cisnienie_aktualne = nowe_cisnienie
                item.ostatnia_aktualizacja = current_time
                
                pomiary_do_dodania.append(
                    HistoriaPomiarow(id_sprzetu=item.id, temperatura=nowa_temperatura, cisnienie=nowe_cisnienie, czas_pomiaru=current_time)
                )

            # KROK 2: Zapisz wszystkie zmiany do bazy w jednej transakcji
            if pomiary_do_dodania:
                db.session.add_all(pomiary_do_dodania)

            db.session.commit()
            print(f"\n[{current_time}] Pomiary zapisane do bazy.")
            
        except Exception as e:
            db.session.rollback()
            print(f"BŁĄD podczas odczytu czujników: {e}")
            import traceback
            traceback.print_exc()
            raise

    def _simulate_pressure(self, typ_sprzetu):
        if typ_sprzetu == 'filtr': return Decimal(str(round(random.uniform(4.0, 5.0), 2)))
        elif typ_sprzetu == 'reaktor': return Decimal(str(round(random.uniform(0.0, 2.0), 2)))
        return Decimal('0.0')

    @staticmethod
    def set_temperature_for_multiple(equipment_names, temperatura):
        """
        Ustawia hurtowo temperaturę docelową dla listy sprzętów.
        
        :param equipment_names: Lista stringów z nazwami unikalnymi sprzętów.
        :param temperatura: Nowa temperatura docelowa.
        :return: Lista nazw sprzętów, które udało się zaktualizować.
        """
        if not equipment_names:
            return []

        try:
            # Krok 1: Znajdź ID sprzętów na podstawie ich nazw
            sprzety_q = db.select(Sprzet).where(Sprzet.nazwa_unikalna.in_(equipment_names))
            sprzety_do_aktualizacji = db.session.execute(sprzety_q).scalars().all()

            if not sprzety_do_aktualizacji:
                print("Nie znaleziono żadnego sprzętu o podanych nazwach.")
                return []

            ids_do_aktualizacji = [s.id for s in sprzety_do_aktualizacji]
            nazwy_zaktualizowane = [s.nazwa_unikalna for s in sprzety_do_aktualizacji]
            current_time = datetime.now(timezone.utc)

            # Krok 2: Użyj `update` do masowej aktualizacji w tabeli `sprzet`
            stmt_sprzet = db.update(Sprzet).where(
                Sprzet.id.in_(ids_do_aktualizacji)
            ).values(
                temperatura_aktualna=temperatura,
                temperatura_docelowa=temperatura,
                ostatnia_aktualizacja=current_time
            )
            db.session.execute(stmt_sprzet)

            # Krok 3: Dodaj wpisy do historii `operator_temperatures`
            # Robimy to w pętli, ponieważ musimy dodać osobne wiersze
            nowe_wpisy_historii = []
            for sprzet_id in ids_do_aktualizacji:
                nowe_wpisy_historii.append(
                    OperatorTemperatures(id_sprzetu=sprzet_id, temperatura=temperatura, czas_ustawienia=current_time)
                )
            db.session.add_all(nowe_wpisy_historii)
            
            db.session.commit()
            return nazwy_zaktualizowane

        except Exception as e:
            db.session.rollback()
            print(f"Wystąpił błąd podczas masowej aktualizacji temperatury: {e}")
            raise

    @staticmethod
    def get_temperatures_for_multiple(equipment_names):
        """
        Pobiera aktualne i docelowe temperatury dla listy sprzętów.
        
        :param equipment_names: Lista stringów z nazwami unikalnymi sprzętów.
        :return: Lista słowników z danymi o temperaturze dla każdego znalezionego sprzętu.
        """
        if not equipment_names:
            return []

        try:
            # Używamy select() do wybrania konkretnych kolumn, co jest bardziej wydajne
            sprzety_q = db.select(
                Sprzet.nazwa_unikalna,
                Sprzet.temperatura_aktualna,
                Sprzet.temperatura_docelowa
            ).where(
                Sprzet.nazwa_unikalna.in_(equipment_names)
            )
            
            # .all() zwróci listę obiektów Row, które działają podobnie do słowników
            results = db.session.execute(sprzety_q).all()
            
            # Konwertujemy listę Row na listę słowników dla łatwiejszego użycia
            return [
                {
                    "nazwa": row.nazwa_unikalna,
                    "aktualna": row.temperatura_aktualna,
                    "docelowa": row.temperatura_docelowa
                } 
                for row in results
            ]
        except Exception as e:
            print(f"Wystąpił błąd podczas pobierania temperatur: {e}")
            raise