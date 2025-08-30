# app/sprzet_service.py

from .extensions import db
from .models import Sprzet, TankMixes
from decimal import Decimal
from datetime import datetime, timezone
from .models import OperatorTemperatures

class SprzetService:
    @staticmethod
    def set_burner_status(sprzet_id: int, status: str, operator: str = 'SYSTEM'):
        """
        Ustawia stan palnika dla danego sprzętu i zwraca zaktualizowany obiekt.
        
        :param sprzet_id: ID sprzętu (reaktora).
        :param status: Nowy status, musi być 'WLACZONY' lub 'WYLACZONY'.
        :param operator: Operator wykonujący akcję.
        :return: Zaktualizowany obiekt Sprzet.
        :raises ValueError: Jeśli podano nieprawidłowy status lub sprzęt nie jest reaktorem.
        """
        if status not in ['WLACZONY', 'WYLACZONY']:
            raise ValueError("Nieprawidłowy status palnika. Dozwolone wartości: 'WLACZONY', 'WYLACZONY'.")
            
        sprzet = db.session.get(Sprzet, sprzet_id)

        if not sprzet:
            raise ValueError(f"Nie znaleziono sprzętu o ID {sprzet_id}.")
        
        if sprzet.typ_sprzetu != 'reaktor':
            raise ValueError(f"Sprzęt '{sprzet.nazwa_unikalna}' nie jest reaktorem i nie posiada palnika.")
            
        # Jeśli stan się nie zmienia, nic nie rób
        if sprzet.stan_palnika == status:
            return sprzet

        sprzet.stan_palnika = status

        if status == 'WLACZONY':
            mix = db.session.get(TankMixes, sprzet.active_mix_id) if sprzet.active_mix_id else None
            if mix and mix.process_status == 'SUROWY':
                mix.process_status = 'PODGRZEWANY'
                print(f"Automatycznie zmieniono status mieszaniny ID {mix.id} na PODGRZEWANY.")
        
        # Opcjonalnie: Możemy tu dodać logowanie do nowej tabeli `historia_palnika`
        # np. log_burner_activity(sprzet_id, status, operator, datetime.now(timezone.utc))
        
        db.session.commit()
        
        print(f"Zmieniono stan palnika dla '{sprzet.nazwa_unikalna}' na {status}.")
        
        return sprzet

    @staticmethod
    def start_heating_process(sprzet_id: int, start_temperature: Decimal):
        """
        Rozpoczyna proces podgrzewania dla mieszaniny w reaktorze.
        
        - Ustawia temperaturę startową.
        - Włącza palnik.
        - Zmienia status mieszaniny na 'PODGRZEWANY'.
        - Oblicza i zwraca szacowany czas do osiągnięcia temperatury docelowej.
        
        :param sprzet_id: ID reaktora.
        :param start_temperature: Temperatura wsadu podana przez operatora.
        :return: Słownik zawierający oszacowany czas w minutach.
        :raises ValueError: Jeśli sprzęt nie jest reaktorem, jest pusty lub ma nieprawidłowy status.
        """
        try:
            reaktor = db.session.get(Sprzet, sprzet_id)

            if not reaktor or reaktor.typ_sprzetu != 'reaktor':
                raise ValueError("Podany sprzęt nie jest reaktorem.")

            mix = db.session.get(TankMixes, reaktor.active_mix_id) if reaktor.active_mix_id else None
            
            if not mix:
                raise ValueError("Reaktor jest pusty, nie można rozpocząć podgrzewania.")
            
            if mix.process_status != 'SUROWY':
                raise ValueError(f"Nie można rozpocząć podgrzewania. Obecny status procesu to '{mix.process_status}'.")

            szybkosc_grzania = reaktor.szybkosc_grzania_c_na_minute
            temp_docelowa = reaktor.temperatura_docelowa

            if not szybkosc_grzania or not temp_docelowa or szybkosc_grzania <= 0:
                raise ValueError("Prędkość grzania lub temperatura docelowa nie są zdefiniowane dla tego reaktora.")

            # Aktualizacja stanu reaktora
            reaktor.stan_palnika = 'WLACZONY'
            reaktor.temperatura_aktualna = start_temperature
            reaktor.ostatnia_aktualizacja = datetime.now(timezone.utc)
            
            # Aktualizacja stanu mieszaniny
            mix.process_status = 'PODGRZEWANY'
            
            # Obliczenie czasu
            roznica_temp = temp_docelowa - start_temperature
            if roznica_temp <= 0:
                estimated_minutes = 0
            else:
                estimated_minutes = float(roznica_temp / szybkosc_grzania)

            db.session.commit()

            return {
                "estimated_minutes_remaining": estimated_minutes
            }

        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def set_simulation_params(sprzet_id: int, szybkosc_grzania: Decimal, szybkosc_chlodzenia: Decimal):
        """
        Ustawia nowe prędkości symulacji dla danego sprzętu.
        """
        sprzet = db.session.get(Sprzet, sprzet_id)

        if not sprzet:
            raise ValueError(f"Nie znaleziono sprzętu o ID {sprzet_id}.")
        
        if sprzet.typ_sprzetu != 'reaktor':
            raise ValueError(f"Sprzęt '{sprzet.nazwa_unikalna}' nie jest reaktorem.")

        sprzet.szybkosc_grzania_c_na_minute = szybkosc_grzania
        sprzet.szybkosc_chlodzenia_c_na_minute = szybkosc_chlodzenia
        
        db.session.commit()
        
        print(f"Zaktualizowano parametry symulacji dla '{sprzet.nazwa_unikalna}': Grzanie={szybkosc_grzania}, Chłodzenie={szybkosc_chlodzenia}")
        
        return sprzet

    @staticmethod
    def get_simulation_params(sprzet_id: int):
        """
        Pobiera aktualne parametry symulacji dla danego sprzętu.
        """
        sprzet = db.session.get(Sprzet, sprzet_id)

        if not sprzet:
            raise ValueError(f"Nie znaleziono sprzętu o ID {sprzet_id}.")
        
        if sprzet.typ_sprzetu != 'reaktor':
            raise ValueError(f"Sprzęt '{sprzet.nazwa_unikalna}' nie jest reaktorem.")

        return {
            "szybkosc_grzania": sprzet.szybkosc_grzania_c_na_minute,
            "szybkosc_chlodzenia": sprzet.szybkosc_chlodzenia_c_na_minute
        }

    @staticmethod
    def set_temperatures(sprzet_id: int, temperatura: Decimal, target: str):
        """
        Ustawia temperaturę aktualną i/lub docelową dla danego sprzętu.
        """
        sprzet = db.session.get(Sprzet, sprzet_id)
        if not sprzet:
            raise ValueError(f"Nie znaleziono sprzętu o ID {sprzet_id}.")

        current_time = datetime.now(timezone.utc)
        
        if target == 'current' or target == 'both':
            sprzet.temperatura_aktualna = temperatura
        
        if target == 'both':
            sprzet.temperatura_docelowa = temperatura
        
        sprzet.ostatnia_aktualizacja = current_time

        # Dodaj wpis do historii OperatorTemperatures, jeśli ustawiono docelową
        if target == 'both':
            history_entry = OperatorTemperatures(
                id_sprzetu=sprzet_id, 
                temperatura=temperatura, 
                czas_ustawienia=current_time
            )
            db.session.add(history_entry)

        db.session.commit()
        return sprzet