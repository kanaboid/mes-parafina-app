# app/sprzet_service.py

from .extensions import db
from .models import Sprzet
from datetime import datetime, timezone

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
        
        # Opcjonalnie: Możemy tu dodać logowanie do nowej tabeli `historia_palnika`
        # np. log_burner_activity(sprzet_id, status, operator, datetime.now(timezone.utc))
        
        db.session.commit()
        
        print(f"Zmieniono stan palnika dla '{sprzet.nazwa_unikalna}' na {status}.")
        
        return sprzet