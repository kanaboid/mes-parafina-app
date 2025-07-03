import random
from datetime import datetime
from flask import current_app
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
        """Ustawia nową temperaturę bazową dla sprzętu"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            current_time = datetime.now()
            
            # Zapisz nową temperaturę bazową
            cursor.execute("""
                INSERT INTO operator_temperatures 
                (id_sprzetu, temperatura, czas_ustawienia)
                VALUES (%s, %s, %s)
            """, (sprzet_id, temperatura, current_time))
            
            # Zapisz pomiar w historii
            cursor.execute("""
                INSERT INTO historia_pomiarow 
                (id_sprzetu, temperatura, czas_pomiaru)
                VALUES (%s, %s, %s)
            """, (sprzet_id, temperatura, current_time))
            
            # Aktualizuj stan sprzętu
            cursor.execute("""
                UPDATE sprzet 
                SET temperatura_aktualna = %s,
                    ostatnia_aktualizacja = %s
                WHERE id = %s
            """, (temperatura, current_time, sprzet_id))
            
            conn.commit()
            print(f"[{current_time}] Ustawiono nową temperaturę {temperatura}°C dla sprzętu ID={sprzet_id}")
            
        finally:
            cursor.close()
            conn.close()

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
            current_time = datetime.now()
            
            if not operator_temp:
                # Brak ustawionej temperatury - użyj domyślnej
                return 60.0
                
            # Oblicz przyrost temperatury
            minutes_passed = (current_time - operator_temp['czas_ustawienia']).total_seconds() / 60.0
            base_temperature = float(operator_temp['temperatura'])
            temperature_rise = minutes_passed * 0.5
            new_temperature = base_temperature + temperature_rise
            
            return round(new_temperature, 2)
            
        finally:
            cursor.close()
            conn.close()
    
    def read_sensors(self):
        """Odczytuje i aktualizuje dane z czujników"""
        
        current_time = datetime.now()
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