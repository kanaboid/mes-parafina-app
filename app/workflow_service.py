# app/workflow_service.py
from datetime import timezone
from datetime import datetime
from .extensions import db
from .models import TankMixes, OperacjeLog, Sprzet
from decimal import Decimal
from sqlalchemy import select

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
    def add_bleaching_earth(cls, mix_id: int, bags_count: int, bag_weight: Decimal, operator: str) -> dict:
        """
        Rejestruje dodanie ziemi bielącej. Jeśli mieszanina jest już w stanie 'DOBIELONY_OCZEKUJE',
        aktualizuje ostatni log dobielania, zamiast tworzyć nowy, z walidacją do 160kg.
        """
        mix = db.session.get(TankMixes, mix_id)
        if not mix: raise ValueError(f"Mieszanina o ID {mix_id} nie istnieje.")
        if not mix.tank: raise ValueError("Mieszanina nie jest przypisana do żadnego reaktora.")
        if mix.is_wydmuch_mix: raise ValueError("Nie można dodawać ziemi bielącej do mieszaniny będącej wydmuchem.")
        if not mix.tank.temperatura_aktualna or mix.tank.temperatura_aktualna < 110.0:
            raise ValueError(f"Zbyt niska temperatura reaktora ({mix.tank.temperatura_aktualna}°C). Wymagane min. 110°C.")
        
        total_added_weight = Decimal(bags_count) * bag_weight
        MAX_BLEACH_WEIGHT = Decimal('160.0')

        if mix.process_status == 'DOBIELONY_OCZEKUJE':
            # Scenariusz: Dokładka do istniejącego dobielania
            log_entry_to_update = db.session.execute(
                select(OperacjeLog)
                .filter_by(id_tank_mix=mix.id, typ_operacji='DOBIELANIE')
                .order_by(OperacjeLog.czas_rozpoczecia.desc())
            ).scalars().first()

            if not log_entry_to_update:
                # Sytuacja awaryjna: stan to DOBIELONY, ale nie ma logu. Traktuj jak nowe dobielanie.
                return cls._create_new_bleaching_log(mix, bags_count, bag_weight, operator, total_added_weight, MAX_BLEACH_WEIGHT)

            new_total_weight = (log_entry_to_update.ilosc_kg or 0) + total_added_weight
            if new_total_weight > MAX_BLEACH_WEIGHT:
                raise ValueError(f"Łączna waga ziemi w tej operacji ({new_total_weight} kg) przekroczy limit {MAX_BLEACH_WEIGHT} kg.")

            log_entry_to_update.ilosc_workow = (log_entry_to_update.ilosc_workow or 0) + bags_count
            log_entry_to_update.ilosc_kg = new_total_weight
            log_entry_to_update.opis = f"Zaktualizowano: łącznie {log_entry_to_update.ilosc_workow} worków, waga {new_total_weight} kg."
            log_entry_to_update.zmodyfikowane_przez = operator
            log_entry_to_update.ostatnia_modyfikacja = datetime.now(timezone.utc)
            
            mix.bleaching_earth_bags_total = (mix.bleaching_earth_bags_total or 0) + bags_count # Globalny licznik nadal rośnie
            message = f"Dodano kolejne {bags_count} worków. Łączna waga w tej operacji: {new_total_weight} kg."
        else:
            # Scenariusz: Nowe dobielanie
            result = cls._create_new_bleaching_log(mix, bags_count, bag_weight, operator, total_added_weight, MAX_BLEACH_WEIGHT)
            message = result['message']
        
        db.session.commit()
        return {"mix": mix, "message": message}

    @classmethod
    def _create_new_bleaching_log(cls, mix, bags_count, bag_weight, operator, total_added_weight, max_weight):
        """Metoda pomocnicza do tworzenia nowego logu dobielania."""
        if total_added_weight > max_weight:
            raise ValueError(f"Ilość ziemi ({total_added_weight} kg) przekracza maksymalny limit {max_weight} kg dla pojedynczej operacji.")
            
        mix.process_status = 'DOBIELONY_OCZEKUJE'
        mix.bleaching_earth_bags_total = (mix.bleaching_earth_bags_total or 0) + bags_count
        
        log_entry = OperacjeLog(
            typ_operacji='DOBIELANIE',
            id_tank_mix=mix.id,
            status_operacji='zakonczona',
            czas_rozpoczecia=datetime.now(timezone.utc),
            czas_zakonczenia=datetime.now(timezone.utc),
            zmodyfikowane_przez=operator,
            ilosc_workow=bags_count,
            ilosc_kg=total_added_weight,
            opis=f"Dodano {bags_count} worków ziemi o łącznej wadze {total_added_weight} kg."
        )
        db.session.add(log_entry)
        
        return {"mix": mix, "message": f"Zarejestrowano dodanie {bags_count} worków. Status: DOBIELONY_OCZEKUJE."}  