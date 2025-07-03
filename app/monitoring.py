from datetime import datetime
import mysql.connector
from flask import current_app
from .db import get_db_connection




class MonitoringService:
    def __init__(self):
        self.app = None

    def init_app(self, app):
        self.app = app

    def check_equipment_status(self):
        """Sprawdza stan wszystkich urządzeń i generuje alarmy"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Sprawdzanie temperatur
            cursor.execute("""
                SELECT id, nazwa_unikalna, temperatura_aktualna, temperatura_max 
                FROM sprzet 
                WHERE temperatura_aktualna > temperatura_max
            """)
            temp_alerts = cursor.fetchall()

            # Sprawdzanie ciśnienia
            cursor.execute("""
                SELECT id, nazwa_unikalna, cisnienie_aktualne, cisnienie_max 
                FROM sprzet 
                WHERE cisnienie_aktualne > cisnienie_max
            """)
            pressure_alerts = cursor.fetchall()

            alerts = []
            for alert in temp_alerts:
                self._create_alarm(
                    'TEMPERATURA',
                    alert['nazwa_unikalna'],
                    alert['temperatura_aktualna'],
                    alert['temperatura_max']
                )

            for alert in pressure_alerts:
                self._create_alarm(
                    'CISNIENIE',
                    alert['nazwa_unikalna'],
                    alert['cisnienie_aktualne'],
                    alert['cisnienie_max']
                )

            return alerts

        finally:
            cursor.close()
            conn.close()

    def _create_alarm(self, typ_alarmu, nazwa_sprzetu, wartosc, limit):
        """Tworzy nowy alarm w bazie danych"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            sql = """INSERT INTO alarmy 
                    (typ_alarmu, nazwa_sprzetu, wartosc, limit_przekroczenia, czas_wystapienia, status_alarmu) 
                    VALUES (%s, %s, %s, %s, %s, 'AKTYWNY')"""
            
            cursor.execute(sql, (typ_alarmu, nazwa_sprzetu, wartosc, limit, datetime.now()))
            conn.commit()
            
        finally:
            cursor.close()
            conn.close()