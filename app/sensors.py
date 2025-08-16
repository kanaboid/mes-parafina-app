import random
import time
from datetime import datetime, timezone
from flask import current_app
from mysql.connector.errors import OperationalError
from .db import get_db_connection
from .extensions import db
from .models import Sprzet, OperatorTemperatures

class SensorService:
    def __init__(self, app=None):
        self.app = app
        
       
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self.app = app
        # Don't load temperatures here - will do it in context
        
            

    
    

    def set_temperature(self, sprzet_id, temperatura):
        """
        Ustawia nową temperaturę bazową dla sprzętu w tabeli operator_temperatures,
        implementując mechanizm ponawiania transakcji.
        """
        max_retries = 3
        for attempt in range(max_retries):
            conn = None
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                current_time = datetime.now(timezone.utc)

                # Zapisz nową temperaturę bazową, od której symulacja będzie liczyć
                cursor.execute("""
                    INSERT INTO operator_temperatures 
                    (id_sprzetu, temperatura, czas_ustawienia)
                    VALUES (%s, %s, %s)
                """, (sprzet_id, temperatura, current_time))

                # Natychmiast zaktualizuj też stan w tabeli sprzet, aby zmiana była widoczna
                cursor.execute("""
                    UPDATE sprzet 
                    SET temperatura_aktualna = %s,
                        temperatura_docelowa = %s,
                        ostatnia_aktualizacja = %s
                    WHERE id = %s
                """, (temperatura, temperatura, current_time, sprzet_id))

                conn.commit()
                print(f"[{current_time}] Ustawiono nową temperaturę {temperatura}°C dla sprzętu ID={sprzet_id}")
                
                # Jeśli operacja się udała, zakończ działanie metody
                return

            except OperationalError as e:
                if conn:
                    conn.rollback()
                # Sprawdź, czy błąd to deadlock (1213) lub timeout (1205)
                if e.errno in (1213, 1205) and attempt < max_retries - 1:
                    print(f"Deadlock lub timeout przy ustawianiu temp. Ponawiam próbę {attempt + 1}/{max_retries}...")
                    time.sleep(0.5)
                    continue # Przejdź do następnej próby
                else:
                    # Jeśli to inny błąd lub ostatnia próba, rzuć wyjątkiem dalej
                    raise e
            finally:
                if conn and conn.is_connected():
                    if 'cursor' in locals() and cursor:
                        cursor.close()
                    conn.close()
        
        # Jeśli pętla się zakończyła bez sukcesu
        raise Exception("Nie udało się ustawić temperatury po kilku próbach z powodu blokady bazy danych.")

    def _simulate_temperature(self, sprzet_id, typ_sprzetu):
        """Symuluje wzrost temperatury od ostatniej znanej wartości"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Pobierz ostatnią temperaturę ustawioną przez operatora
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
                # Brak ustawionej temperatury - użyj domyślnej
                return 60.0
            czas_ustawienia_z_bazy = operator_temp['czas_ustawienia']
            czas_ustawienia_aware = czas_ustawienia_z_bazy.replace(tzinfo=timezone.utc)
            # Oblicz przyrost temperatury
            minutes_passed = (current_time - czas_ustawienia_aware).total_seconds() / 60.0
            base_temperature = float(operator_temp['temperatura'])
            temperature_rise = minutes_passed * 0.14
            new_temperature = base_temperature + temperature_rise
            
            return round(new_temperature, 2)
            
        finally:
            cursor.close()
            conn.close()
    
    def read_sensors(self):
        """Odczytuje i aktualizuje dane z czujników"""
        
        current_time = datetime.now(timezone.utc)
        print(f"[{current_time}] Rozpoczynam odczyt czujników...")
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Pobierz aktywne urządzenia
            cursor.execute("""
                SELECT id, nazwa_unikalna, typ_sprzetu 
                FROM sprzet 
                WHERE stan_sprzetu != 'Wyłączony'
            """)
            equipment = cursor.fetchall()
            print(f"Znaleziono {len(equipment)} aktywnych urządzeń")
            
            for item in equipment:
                temperatura = self._simulate_temperature(item['id'], item['typ_sprzetu'])
                cisnienie = self._simulate_pressure(item['typ_sprzetu'])
                
                # Zapisz pomiar w historii
                cursor.execute("""
                    INSERT INTO historia_pomiarow 
                    (id_sprzetu, temperatura, cisnienie, czas_pomiaru)
                    VALUES (%s, %s, %s, %s)
                """, (item['id'], temperatura, cisnienie, current_time))
                
                # Aktualizuj stan sprzętu
                cursor.execute("""
                    UPDATE sprzet 
                    SET temperatura_aktualna = %s,
                        cisnienie_aktualne = %s,
                        ostatnia_aktualizacja = %s
                    WHERE id = %s
                """, (temperatura, cisnienie, current_time, item['id']))
                
                print(f"Sprzęt {item['nazwa_unikalna']}: T={temperatura}°C, P={cisnienie}bar")
            
            conn.commit()
            print(f"[{current_time}] Pomiary zapisane do bazy")
            
        except Exception as e:
            conn.rollback()
            print(f"BŁĄD podczas odczytu czujników: {str(e)}")
            raise
        finally:
            cursor.close()
            conn.close()

    def _simulate_pressure(self, typ_sprzetu):
        """Symulacja odczytu ciśnienia"""
        if typ_sprzetu == 'filtr':
            return round(random.uniform(4, 5), 2)
        elif typ_sprzetu == 'reaktor':
            return round(random.uniform(0, 2), 2)
        return 0.0

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