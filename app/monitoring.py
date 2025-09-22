# app/monitoring.py

from datetime import datetime, timezone
from .extensions import db
from .models import Sprzet, Alarmy

class MonitoringService:
    
    def init_app(self, app):
        self.app = app

    def check_equipment_status(self):
        """
        Sprawdza stan wszystkich urządzeń (wersja ORM). Tworzy i zamyka alarmy.
        """
        try:
            # 1. Pobierz stan wszystkich urządzeń
            all_equipment = db.session.execute(db.select(Sprzet)).scalars().all()

            # 2. Pobierz wszystkie AKTYWNE alarmy
            active_alarms_q = db.select(Alarmy).where(Alarmy.status_alarmu == 'AKTYWNY')
            active_alarms_raw = db.session.execute(active_alarms_q).scalars().all()
            
            # Stwórz słownik dla szybkich sprawdzeń: (nazwa_sprzętu, typ_alarmu) -> obiekt Alarm
            active_alarms = {(a.nazwa_sprzetu, a.typ_alarmu): a for a in active_alarms_raw}

            # 3. Przejdź przez każde urządzenie i zweryfikuj jego stan
            for item in all_equipment:
                nazwa_sprzetu = item.nazwa_unikalna
                
                # --- Sprawdzanie temperatury ---
                # Używamy teraz dostępu przez atrybut (kropkę)
                aktualna_temp = item.temperatura_aktualna
                max_temp = item.temperatura_max
                is_temp_alarm = (nazwa_sprzetu, 'TEMPERATURA') in active_alarms

                if aktualna_temp is not None and max_temp is not None:
                    if aktualna_temp > max_temp:
                        if not is_temp_alarm:
                            self._create_alarm('TEMPERATURA', nazwa_sprzetu, aktualna_temp, max_temp)
                    elif is_temp_alarm:
                        alarm_to_resolve = active_alarms[(nazwa_sprzetu, 'TEMPERATURA')]
                        self._resolve_alarm(alarm_to_resolve)

                # --- Sprawdzanie ciśnienia ---
                aktualne_cisnienie = item.cisnienie_aktualne
                max_cisnienie = item.cisnienie_max
                is_pressure_alarm = (nazwa_sprzetu, 'CISNIENIE') in active_alarms

                if aktualne_cisnienie is not None and max_cisnienie is not None:
                    if aktualne_cisnienie > max_cisnienie:
                        if not is_pressure_alarm:
                            self._create_alarm('CISNIENIE', nazwa_sprzetu, aktualne_cisnienie, max_cisnienie)
                    elif is_pressure_alarm:
                        alarm_to_resolve = active_alarms[(nazwa_sprzetu, 'CISNIENIE')]
                        self._resolve_alarm(alarm_to_resolve)
            
            db.session.commit()

        except Exception as e:
            db.session.rollback()
            print(f"BŁĄD podczas sprawdzania alarmów: {e}")
            raise


    def _create_alarm(self, typ_alarmu, nazwa_sprzetu, wartosc, limit):
        """Prywatna metoda do tworzenia nowego alarmu w bazie danych (wersja ORM)."""
        nowy_alarm = Alarmy(
            typ_alarmu=typ_alarmu,
            nazwa_sprzetu=nazwa_sprzetu,
            wartosc=wartosc,
            limit_przekroczenia=limit,
            czas_wystapienia=datetime.now(timezone.utc),
            status_alarmu='AKTYWNY'
        )
        db.session.add(nowy_alarm)

    def _resolve_alarm(self, alarm_obj):
        """Prywatna metoda do zamykania istniejącego alarmu (wersja ORM)."""
        alarm_obj.status_alarmu = 'ZAKONCZONY'
        alarm_obj.czas_zakonczenia = datetime.now(timezone.utc)