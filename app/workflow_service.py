# app/workflow_service.py
from datetime import datetime, timezone
from decimal import Decimal
from app.extensions import db
from app.models import TankMixes, OperacjeLog, Sprzet, MixComponents, Batches
from app.batch_management_service import BatchManagementService
from sqlalchemy import select
class WorkflowService:
    """
    Serwis odpowiedzialny za zarządzanie logiką przepływów pracy i zmianą statusów.
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
            typ_operacji='OCENA_JAKOSCI',
            id_tank_mix=mix.id,
            status_operacji='zakonczona',
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
        Rejestruje dodanie ziemi bielącej. Jeśli mieszanina jest w stanie 'DOBIELONY_OCZEKUJE',
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
                # Sytuacja awaryjna: status to DOBRANY, ale nie ma logu. Traktuj jak nowe.
                return cls._create_new_bleaching_log(mix, bags_count, bag_weight, operator, total_added_weight, MAX_BLEACH_WEIGHT)

            new_total_weight = (log_entry_to_update.ilosc_kg or 0) + total_added_weight
            if new_total_weight > MAX_BLEACH_WEIGHT:
                raise ValueError(f"Łączna waga ziemi w tej operacji ({new_total_weight} kg) przekroczy limit {MAX_BLEACH_WEIGHT} kg.")

            log_entry_to_update.ilosc_workow = (log_entry_to_update.ilosc_workow or 0) + bags_count
            log_entry_to_update.ilosc_kg = new_total_weight
            log_entry_to_update.opis = f"Zaktualizowano: łącznie {log_entry_to_update.ilosc_workow} worków, waga {new_total_weight} kg."
            log_entry_to_update.zmodyfikowane_przez = operator
            log_entry_to_update.ostatnia_modyfikacja = datetime.now(timezone.utc)
            
            mix.bleaching_earth_bags_total = (mix.bleaching_earth_bags_total or 0) + bags_count
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

    @staticmethod
    def load_batches_to_reactor(reactor_id: int, batches_to_load: list, operator: str) -> tuple[TankMixes, bool]:
        """
        Tworzy nową mieszaninę w reaktorze lub dodaje do istniejącej.
        Zwraca krotkę: (obiekt TankMix, flaga bool informująca, czy mieszanina została nowo utworzona).
        """
        was_created = False
        try:
            reactor = db.session.get(Sprzet, reactor_id)
            if not reactor or reactor.typ_sprzetu != 'reaktor':
                raise ValueError(f"Sprzęt o ID {reactor_id} nie jest reaktorem.")

            if not batches_to_load:
                raise ValueError("Lista partii do załadowania nie może być pusta.")

            # --- Rozpoczęcie transakcji ---
            
            if reactor.active_mix_id:
                # SCENARIUSZ: Dodawanie do istniejącej mieszaniny
                mix_to_update = db.session.get(TankMixes, reactor.active_mix_id)
                if not mix_to_update:
                    reactor.active_mix_id = None
                    db.session.commit()
                    return WorkflowService.load_batches_to_reactor(reactor_id, batches_to_load, operator)

                if mix_to_update.process_status != 'SUROWY':
                    raise ValueError(f"Nie można dodać surowca. Mieszanina nie jest w stanie 'SUROWY' (aktualny stan: '{mix_to_update.process_status}').")
                
                was_created = False
                
            else:
                # SCENARIUSZ: Tworzenie nowej mieszaniny
                mix_code = BatchManagementService.generate_reactor_mix_code(reactor.nazwa_unikalna)
                mix_to_update = TankMixes(
                    unique_code=mix_code,
                    tank_id=reactor.id,
                    process_status='SUROWY'
                )
                db.session.add(mix_to_update)
                db.session.flush() 
                reactor.active_mix_id = mix_to_update.id
                was_created = True

            # Wspólna logika dla obu scenariuszy: przetwarzanie partii
            for batch_info in batches_to_load:
                batch_id = batch_info['batch_id']
                quantity_to_use = Decimal(batch_info['quantity_to_use'])

                batch = db.session.get(Batches, batch_id)
                if not batch:
                    raise ValueError(f"Partia o ID {batch_id} nie została znaleziona.")
                if batch.current_quantity < quantity_to_use:
                    raise ValueError(f"Niewystarczająca ilość w partii {batch.unique_code}. Dostępne: {batch.current_quantity}, Potrzebne: {quantity_to_use}.")

                batch.current_quantity -= quantity_to_use
                
                existing_component = db.session.query(MixComponents).filter_by(mix_id=mix_to_update.id, batch_id=batch.id).first()
                if existing_component:
                    existing_component.quantity_in_mix += quantity_to_use
                else:
                    component = MixComponents(
                        mix_id=mix_to_update.id,
                        batch_id=batch.id,
                        quantity_in_mix=quantity_to_use
                    )
                    db.session.add(component)

            db.session.commit()
            # --- Koniec transakcji ---
            
            return mix_to_update, was_created

        except Exception as e:
            db.session.rollback()
            raise e