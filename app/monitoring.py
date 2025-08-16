from datetime import datetime, timezone
import mysql.connector
from flask import current_app
from .db import get_db_connection




class MonitoringService:
    
    def init_app(self, app):
        self.app = app

    def check_equipment_status(self):
        """
        Sprawdza stan wszystkich urządzeń. Tworzy nowe alarmy, gdy parametry
        są przekroczone i automatycznie zamyka istniejące alarmy, gdy
        parametry wrócą do normy.
        """
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # 1. Pobierz stan wszystkich urządzeń
            cursor.execute("SELECT * FROM sprzet")
            all_equipment = cursor.fetchall()

            # 2. Pobierz wszystkie AKTYWNE alarmy, aby wiedzieć, co już jest zgłoszone
            cursor.execute("SELECT id, nazwa_sprzetu, typ_alarmu FROM alarmy WHERE status_alarmu = 'AKTYWNY'")
            active_alarms_raw = cursor.fetchall()
            # Stwórzmy z tego słownik dla szybkich sprawdzeń: (nazwa_sprzętu, typ_alarmu) -> id_alarmu
            active_alarms = {(a['nazwa_sprzetu'], a['typ_alarmu']): a['id'] for a in active_alarms_raw}

            # 3. Przejdź przez każde urządzenie i zweryfikuj jego stan
            for item in all_equipment:
                nazwa_sprzetu = item['nazwa_unikalna']
                
                # --- Sprawdzanie temperatury ---
                aktualna_temp = item.get('temperatura_aktualna')
                max_temp = item.get('temperatura_max')
                is_temp_alarm = (nazwa_sprzetu, 'TEMPERATURA') in active_alarms

                # Sprawdzaj tylko, jeśli obie wartości istnieją
                if aktualna_temp is not None and max_temp is not None:
                    if aktualna_temp > max_temp:
                        # Jeśli temperatura jest za wysoka, a nie ma aktywnego alarmu, stwórz go
                        if not is_temp_alarm:
                            self._create_alarm(cursor, 'TEMPERATURA', nazwa_sprzetu, aktualna_temp, max_temp)
                    elif is_temp_alarm:
                        # Jeśli temperatura jest w normie, a istnieje aktywny alarm, zamknij go
                        alarm_id = active_alarms[(nazwa_sprzetu, 'TEMPERATURA')]
                        self._resolve_alarm(cursor, alarm_id)

                # --- Sprawdzanie ciśnienia ---
                aktualne_cisnienie = item.get('cisnienie_aktualne')
                max_cisnienie = item.get('cisnienie_max')
                is_pressure_alarm = (nazwa_sprzetu, 'CISNIENIE') in active_alarms

                # Sprawdzaj tylko, jeśli obie wartości istnieją
                if aktualne_cisnienie is not None and max_cisnienie is not None:
                    if aktualne_cisnienie > max_cisnienie:
                        # Jeśli ciśnienie jest za wysokie, a nie ma aktywnego alarmu, stwórz go
                        if not is_pressure_alarm:
                            self._create_alarm(cursor, 'CISNIENIE', nazwa_sprzetu, aktualne_cisnienie, max_cisnienie)
                    elif is_pressure_alarm:
                        # Jeśli ciśnienie jest w normie, a istnieje aktywny alarm, zamknij go
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
        """Prywatna metoda do zamykania istniejącego alarmu."""
        sql = """UPDATE alarmy 
                 SET status_alarmu = 'ZAKONCZONY', czas_zakonczenia = %s 
                 WHERE id = %s"""
        cursor.execute(sql, (datetime.now(timezone.utc), alarm_id))