# app/batch_management_service.py
from .extensions import db
from .models import Batches, Sprzet, TankMixes, MixComponents, AuditTrail, ApolloSesje, ApolloTracking
from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload
from decimal import Decimal
from .apollo_service import ApolloService
import pytz
from collections import defaultdict

WARSAW_TZ = pytz.timezone('Europe/Warsaw')

class BatchManagementService:
    
    def _generate_unique_code(material_type, source_name):
        # 1. Pobierz aktualny czas w UTC
        now_utc = datetime.now(timezone.utc)
        # 2. Skonwertuj go do strefy czasowej Warszawy
        now_warsaw = now_utc.astimezone(WARSAW_TZ)
        # 3. Użyj czasu lokalnego do sformatowania stringa
        today_str = now_warsaw.strftime('%y%m%d')
        
        base_prefix = f"S-{source_name}-{material_type}-{today_str}"
        query = select(func.count(Batches.id)).where(Batches.unique_code.like(f"{base_prefix}%"))
        daily_count = db.session.execute(query).scalar()
        return f"{base_prefix}-{daily_count + 1:02d}"

    @staticmethod
    def create_raw_material_batch(material_type, source_type, source_name, quantity, operator):
        try:
            unique_code = BatchManagementService._generate_unique_code(material_type, source_name)
            new_batch = Batches(
                unique_code=unique_code, material_type=material_type, source_type=source_type,
                source_name=source_name, initial_quantity=quantity, current_quantity=quantity
            )
            db.session.add(new_batch)
            db.session.commit()
            return {'batch_id': new_batch.id, 'unique_code': new_batch.unique_code}
        except Exception as e:
            db.session.rollback(); raise e

    @staticmethod
    def _generate_mix_code(tank_name):
        # Zastosuj tę samą logikę co powyżej
        now_utc = datetime.now(timezone.utc)
        now_warsaw = now_utc.astimezone(WARSAW_TZ)
        today_str = now_warsaw.strftime('%y%m%d')

        base_prefix = f"B-{tank_name}-{today_str}"
        query = select(func.count(TankMixes.id)).where(TankMixes.unique_code.like(f"{base_prefix}%"))
        daily_count = db.session.execute(query).scalar()
        return f"{base_prefix}-{daily_count + 1:02d}"
        
    @staticmethod
    def tank_into_dirty_tank(batch_id, tank_id, operator):
        """Tankuje partię do zbiornika, zarządzając `active_mix_id`."""
        try:
            tank = db.session.get(Sprzet, tank_id)
            batch = db.session.get(Batches, batch_id)
            if not tank or not batch: raise ValueError("Zbiornik lub partia nie istnieje.")

            active_mix = db.session.get(TankMixes, tank.active_mix_id) if tank.active_mix_id else None
            
            if not active_mix or active_mix.status == 'ARCHIVED':
                mix_code = BatchManagementService._generate_mix_code(tank.nazwa_unikalna)
                active_mix = TankMixes(unique_code=mix_code, tank_id=tank.id)
                db.session.add(active_mix)
                db.session.flush()
                tank.active_mix_id = active_mix.id

            quantity_to_add = batch.current_quantity
            if quantity_to_add <= 0: raise ValueError("Nie można dodać partii o zerowej ilości.")

            existing_component = next((c for c in active_mix.components if c.batch_id == batch_id), None)
            if existing_component:
                existing_component.quantity_in_mix += quantity_to_add
            else:
                new_component = MixComponents(mix_id=active_mix.id, batch_id=batch_id, quantity_in_mix=quantity_to_add)
                db.session.add(new_component)
            
            batch.current_quantity = 0
            db.session.commit()
            return {'mix_id': active_mix.id}
        except Exception as e:
            db.session.rollback(); raise e

    @staticmethod
    def get_mix_composition(mix_id):
        """Zwraca skład na podstawie wag zapisanych w MixComponents. (Wersja wzmocniona)"""
        # print(f"DEBUG: Uruchomiono get_mix_composition dla mix_id: {mix_id}")
        
        # Użyj joinedload, aby od razu załadować powiązane obiekty Batch
        query = db.select(TankMixes).options(
            joinedload(TankMixes.components).joinedload(MixComponents.batch)
        ).where(TankMixes.id == mix_id)
        
        mix = db.session.execute(query).unique().scalar_one_or_none()

        if not mix:
            # print(f"DEBUG: Nie znaleziono mieszaniny o ID {mix_id}")
            return {'total_weight': 0.0, 'components_by_batch': [], 'summary_by_material': []}
        
        # Filtruj składniki, które mają realną wagę w mieszaninie
        components_with_quantity = [c for c in mix.components if c.quantity_in_mix > 0]
        print(f"DEBUG: Znaleziono {len(components_with_quantity)} składników z wagą > 0.")

        total_weight = sum(c.quantity_in_mix for c in components_with_quantity)
        if total_weight == 0:
            # print("DEBUG: Całkowita waga mieszaniny wynosi 0.")
            return {'total_weight': 0.0, 'components_by_batch': [], 'summary_by_material': []}

        # Oblicz szczegóły dla każdej partii pierwotnej
        composition_details = []
        for c in components_with_quantity:
            percentage = (c.quantity_in_mix / total_weight) * 100 if total_weight > 0 else 0
            composition_details.append({
                'batch_id': c.batch.id,
                'batch_code': c.batch.unique_code,
                'material_type': c.batch.material_type,
                'quantity_in_mix': c.quantity_in_mix,
                'percentage': percentage
            })

        # Agreguj wyniki po typie materiału
        material_type_summary = defaultdict(lambda: Decimal('0.0'))
        for c in components_with_quantity:
            material_type_summary[c.batch.material_type] += c.quantity_in_mix

        material_summary_details = []
        for material_type, total_quantity in material_type_summary.items():
            percentage = (total_quantity / total_weight) * 100 if total_weight > 0 else 0
            material_summary_details.append({
                'material_type': material_type,
                'total_quantity': total_quantity,
                'percentage': percentage
            })
        
        # Przygotuj finalny wynik
        final_result = {
            'total_weight': total_weight, 
            'components_by_batch': composition_details,
            'components': composition_details, # <-- ZWRACAMY KLUCZ 'components'
            'summary_by_material': sorted(material_summary_details, key=lambda x: x['material_type'])
        }
        
        # print(f"DEBUG: Zwracane dane składu: {final_result}")
        return final_result

    @staticmethod
    def transfer_between_dirty_tanks(source_tank_id, destination_tank_id, quantity_to_transfer, operator):
        """Orkiestruje transfer między zbiornikami, obsługując korekty."""
        if source_tank_id == destination_tank_id:
            raise ValueError("Zbiornik źródłowy i docelowy nie mogą być takie same.")
        if quantity_to_transfer < 0:
            raise ValueError("Ilość do przelania musi być dodatnia.")
        if quantity_to_transfer == 0:
            return {'was_adjusted': False, 'discrepancy': Decimal('0.00'), 'transferred_quantity': Decimal('0.00')}
        
        try:
            source_tank = db.session.get(Sprzet, source_tank_id)
            dest_tank = db.session.get(Sprzet, destination_tank_id)
            if not source_tank or not dest_tank: raise ValueError("Jeden ze zbiorników nie istnieje.")
            
            source_mix = db.session.get(TankMixes, source_tank.active_mix_id) if source_tank.active_mix_id else None
            if not source_mix or source_mix.status == 'ARCHIVED':
                raise ValueError("Zbiornik źródłowy jest pusty.")

            composition = BatchManagementService.get_mix_composition(source_mix.id)
            total_weight_in_system = composition['total_weight']
            was_adjusted, discrepancy = False, Decimal('0.00')

            if quantity_to_transfer > total_weight_in_system:
                was_adjusted = True
                discrepancy = quantity_to_transfer - total_weight_in_system
                if total_weight_in_system > 0:
                    for component in source_mix.components:
                        proportion = component.quantity_in_mix / total_weight_in_system
                        component.quantity_in_mix += discrepancy * proportion
                
                audit_log = AuditTrail(
                    user_id=operator, entity_type='TankMixes', entity_id=source_mix.id,
                    operation_type='BALANCE_CORRECTION', field_name='total_weight',
                    old_value=str(total_weight_in_system), new_value=str(total_weight_in_system + discrepancy),
                    reason=f"Automatyczna korekta bilansu podczas transferu z {source_tank.nazwa_unikalna}"
                )
                db.session.add(audit_log)

            # Używamy zaktualizowanej wagi do obliczeń proporcji
            total_weight_for_proportion = sum(c.quantity_in_mix for c in source_mix.components)
            withdrawal_details = []
            if total_weight_for_proportion > 0:
                for component in source_mix.components:
                    proportion = component.quantity_in_mix / total_weight_for_proportion
                    amount_to_deduct = quantity_to_transfer * proportion
                    component.quantity_in_mix -= amount_to_deduct
                    withdrawal_details.append({'batch_id': component.batch_id, 'quantity': amount_to_deduct})
            
            if sum(c.quantity_in_mix for c in source_mix.components) <= Decimal('0.01'): # Tolerancja dla błędów zaokrągleń
                source_mix.status = 'ARCHIVED'
                source_tank.active_mix_id = None
            
            dest_mix = db.session.get(TankMixes, dest_tank.active_mix_id) if dest_tank.active_mix_id else None
            if not dest_mix or dest_mix.status == 'ARCHIVED':
                mix_code = BatchManagementService._generate_mix_code(dest_tank.nazwa_unikalna)
                dest_mix = TankMixes(unique_code=mix_code, tank_id=dest_tank.id)
                db.session.add(dest_mix); db.session.flush()
                dest_tank.active_mix_id = dest_mix.id
            
            components_in_dest = {c.batch_id: c for c in dest_mix.components}
            for detail in withdrawal_details:
                if detail['quantity'] > 0:
                    if detail['batch_id'] in components_in_dest:
                        components_in_dest[detail['batch_id']].quantity_in_mix += detail['quantity']
                    else:
                        new_component = MixComponents(mix_id=dest_mix.id, batch_id=detail['batch_id'], quantity_in_mix=detail['quantity'])
                        db.session.add(new_component)
            
            db.session.commit()
            return {'was_adjusted': was_adjusted, 'discrepancy': discrepancy, 'transferred_quantity': quantity_to_transfer}
        except Exception as e:
            db.session.rollback(); raise e

    @staticmethod
    def correct_batch_quantity(batch_id, new_quantity, operator, reason):
        """Dokonuje ręcznej korekty ilości partii i tworzy wpis w dzienniku zdarzeń."""
        try:
            batch_to_correct = db.session.get(Batches, batch_id)
            if not batch_to_correct:
                raise ValueError(f"Partia o ID {batch_id} nie istnieje.")
            
            original_quantity = batch_to_correct.current_quantity
            audit_log = AuditTrail(
                user_id=operator, entity_type='Batches', entity_id=batch_id,
                operation_type='CORRECTION', field_name='current_quantity',
                old_value=str(original_quantity), new_value=str(new_quantity),
                reason=reason
            )
            batch_to_correct.current_quantity = new_quantity
            db.session.add(audit_log)
            db.session.commit()
            return {'success': True, 'audit_log_id': audit_log.id}
        except Exception as e:
            db.session.rollback(); raise e

    @staticmethod
    def create_batch_from_apollo_transfer(apollo_id, destination_tank_id, actual_quantity_transferred, operator):
        """
        Orkiestruje transfer z Apollo do zbiornika, tworzy partię pierwotną,
        tankuje ją i obsługuje rozbieżności między prognozą a rzeczywistością.
        """
        try:
            # 1. Pobierz dane kontekstowe
            apollo_equipment = db.session.get(Sprzet, apollo_id)
            if not apollo_equipment or apollo_equipment.typ_sprzetu != 'apollo':
                raise ValueError(f"Sprzęt o ID {apollo_id} nie jest wytapiarką Apollo.")

            # Wywołaj prawdziwą metodę serwisu Apollo, którą w teście mockujemy
            apollo_state = ApolloService.oblicz_aktualny_stan_apollo(apollo_id)
            prognozowana_ilosc = Decimal(apollo_state.get('dostepne_kg', 0))
            id_sesji = apollo_state.get('id_sesji')
            typ_surowca = apollo_state.get('typ_surowca')

            if not id_sesji:
                raise ValueError(f"Apollo o ID {apollo_id} nie ma aktywnej sesji.")

            # 2. Obsługa rozbieżności
            was_adjusted = False
            discrepancy = Decimal('0.00')
            if actual_quantity_transferred > prognozowana_ilosc:
                was_adjusted = True
                discrepancy = actual_quantity_transferred - prognozowana_ilosc
                
                audit_log = AuditTrail(
                    user_id=operator,
                    entity_type='ApolloSesje',
                    entity_id=id_sesji,
                    operation_type='BALANCE_CORRECTION',
                    field_name='available_quantity_forecast',
                    old_value=str(prognozowana_ilosc),
                    new_value=str(actual_quantity_transferred),
                    reason="Automatyczna korekta bilansu Apollo na podstawie rzeczywistego transferu."
                )
                db.session.add(audit_log)
            
            # 3. Wykonanie transferu
            # 3a. Zaktualizuj stan w Apollo
            tracking_log = ApolloTracking(
                id_sesji=id_sesji,
                typ_zdarzenia='TRANSFER_WYJSCIOWY',
                waga_kg=actual_quantity_transferred,
                czas_zdarzenia=datetime.now(timezone.utc),
                operator=operator
            )
            db.session.add(tracking_log)

            # 3b. Stwórz Partię Pierwotną
            batch_result = BatchManagementService.create_raw_material_batch(
                material_type=typ_surowca,
                source_type='APOLLO',
                source_name=apollo_equipment.nazwa_unikalna,
                quantity=actual_quantity_transferred,
                operator=operator
            )
            batch_id = batch_result['batch_id']

            # 3c. Zatankuj do zbiornika
            tanking_result = BatchManagementService.tank_into_dirty_tank(
                batch_id=batch_id,
                tank_id=destination_tank_id,
                operator=operator
            )
            mix_id = tanking_result['mix_id']

            # 4. Zatwierdź transakcję i zwróć wynik
            db.session.commit()
            
            return {
                'batch_id': batch_id,
                'mix_id': mix_id,
                'adjusted': was_adjusted,
                'discrepancy': discrepancy
            }
        
        except Exception as e:
            db.session.rollback()
            raise e