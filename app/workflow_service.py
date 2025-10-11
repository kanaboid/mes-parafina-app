# app/workflow_service.py
from datetime import datetime, timezone
from .extensions import db
from .models import TankMixes, OperacjeLog, Sprzet

class WorkflowService:
    """
    Serwis odpowiedzialny za zarządzanie logiką przepływów pracy i zmianą stanów.
    """
    @classmethod
    def assess_mix_quality(cls, mix_id: int, decision: str, operator: str, reason: str = None) -> TankMixes:
        """
        Ocenia jakość mieszaniny i zmienia jej status procesowy.

        :param mix_id: ID Mieszaniny (TankMixes).
        :param decision: Decyzja operatora ('OK' lub 'ZLA').
        :param operator: Identyfikator operatora dokonującego oceny.
        :param reason: Opcjonalny powód, wymagany przy negatywnej ocenie.
        :return: Zaktualizowany obiekt TankMix.
        :raises ValueError: Gdy mieszanina nie istnieje, jest w niepoprawnym stanie lub brakuje powodu.
        """
        mix = db.session.get(TankMixes, mix_id)
        if not mix:
            raise ValueError(f"Mieszanina o ID {mix_id} nie istnieje.")

        if mix.process_status != 'OCZEKUJE_NA_OCENE':
            raise ValueError(f"Nie można ocenić mieszaniny. Obecny status: '{mix.process_status}'. Wymagany: 'OCZEKUJE_NA_OCENE'.")

        log_entry = OperacjeLog(
            typ_operacji='OCENA_JAKOSCI',  # pyright: ignore[reportCallIssue]
            id_tank_mix=mix.id, # Powiązanie z mieszaniną jako "partią"  # pyright: ignore[reportCallIssue]
            status_operacji='zakonczona',  # pyright: ignore[reportCallIssue]
            czas_rozpoczecia=datetime.now(timezone.utc),
            czas_zakonczenia=datetime.now(timezone.utc),
            zmodyfikowane_przez=operator
        )

        if decision.upper() == 'OK':
            mix.process_status = 'ZATWIERDZONA'
            log_entry.opis = f"Wynik oceny: POZYTYWNY. Mieszanina zatwierdzona."
        elif decision.upper() == 'ZLA':
            if not reason:
                raise ValueError("Powód jest wymagany przy negatywnej ocenie jakości.")
            mix.process_status = 'DO_PONOWNEJ_FILTRACJI'
            log_entry.opis = f"Wynik oceny: NEGATYWNY. Powód: {reason}"
        else:
            raise ValueError(f"Nieznana decyzja: '{decision}'. Oczekiwano 'OK' lub 'ZLA'.")
            
        db.session.add(log_entry)
        db.session.commit()
        return mix

    @classmethod
    def add_bleaching_earth(cls, mix_id: int, bags_count: int, operator: str) -> TankMixes:
        """
        Rejestruje dodanie ziemi bielącej do mieszaniny w reaktorze.

        :param mix_id: ID Mieszaniny (TankMixes).
        :param bags_count: Liczba dodanych worków.
        :param operator: Identyfikator operatora.
        :return: Zaktualizowany obiekt TankMix.
        :raises ValueError: Gdy mieszanina nie istnieje, reaktor nie ma temperatury lub stan jest nieprawidłowy.
        """
        mix = db.session.get(TankMixes, mix_id)
        if not mix:
            raise ValueError(f"Mieszanina o ID {mix_id} nie istnieje.")

        if not mix.tank:
            raise ValueError("Mieszanina nie jest przypisana do żadnego reaktora.")

        # Zgodnie z dokumentacją, sprawdzamy temperaturę reaktora
        if not mix.tank.temperatura_aktualna or mix.tank.temperatura_aktualna < 110.0:
            raise ValueError(f"Zbyt niska temperatura reaktora ({mix.tank.temperatura_aktualna}°C). Wymagane min. 110°C.")

        if mix.process_status != 'PODGRZEWANY':
            raise ValueError(f"Nie można dobielić mieszaniny. Obecny status: '{mix.process_status}'. Wymagany: 'PODGRZEWANY'.")

        # Aktualizacja stanu mieszaniny
        mix.process_status = 'DOBIELONY_OCZEKUJE'
        mix.bleaching_earth_bags_total = (mix.bleaching_earth_bags_total or 0) + bags_count

        # Utworzenie wpisu w logu operacji
        log_entry = OperacjeLog(
            typ_operacji='DOBIELANIE',
            id_tank_mix=mix.id,
            status_operacji='zakonczona',
            czas_rozpoczecia=datetime.now(timezone.utc),
            czas_zakonczenia=datetime.now(timezone.utc),
            zmodyfikowane_przez=operator,
            opis=f"Dodano {bags_count} worków ziemi bielącej."
        )
        db.session.add(log_entry)
        db.session.commit()

        return mix