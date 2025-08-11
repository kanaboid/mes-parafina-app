from . import db
from .models import * #TODO: zmienić na importy z models.py, tylko te, które są potrzebne
from datetime import datetime
from sqlalchemy import func, select
from decimal import Decimal

class BatchManagementService:
    
    @staticmethod
    def _generate_unique_code(material_type, source_name):
        today_str = datetime.now().strftime('%y%m%d')
        base_prefix = f"S-{source_name}-{material_type}-{today_str}"
        query = select(func.count(Batches.id)).where(Batches.unique_code.like(f"{base_prefix}%"))
        daily_count = db.session.execute(query).scalar()
        return f"{base_prefix}-{daily_count + 1:02d}"

    @staticmethod
    def create_raw_material_batch(material_type, source_type, source_name, quantity, operator):
        unique_code = BatchManagementService._generate_unique_code(material_type, source_name)
        new_batch = Batches(
            unique_code=unique_code, material_type=material_type, source_type=source_type,
            source_name=source_name, initial_quantity=quantity, current_quantity=quantity
        )
        db.session.add(new_batch)
        db.session.commit()
        return {'batch_id': new_batch.id, 'unique_code': new_batch.unique_code}

    @staticmethod
    def _generate_mix_code(tank_name):
        today_str = datetime.now().strftime('%y%m%d')
        base_prefix = f"B-{tank_name}-{today_str}"
        query = select(func.count(TankMixes.id)).where(TankMixes.unique_code.like(f"{base_prefix}%"))
        daily_count = db.session.execute(query).scalar()
        return f"{base_prefix}-{daily_count + 1:02d}"
        
    @staticmethod
    def tank_into_dirty_tank(batch_id, tank_id, operator):
        """
        Tankuje CAŁĄ Partię Pierwotną do zbiornika. Jej masa jest teraz śledzona
        w MixComponents, a `current_quantity` w Batches jest zerowane.
        """
        try:
            tank = db.session.get(Sprzet, tank_id)
            batch = db.session.get(Batches, batch_id)
            if not tank or not batch: raise ValueError("Zbiornik lub partia nie istnieje.")

            # Znajdź lub stwórz aktywną mieszaninę
            active_mix_query = select(TankMixes).where(TankMixes.tank_id == tank_id, TankMixes.status == 'ACTIVE')
            active_mix = db.session.execute(active_mix_query).scalar_one_or_none()
            if not active_mix:
                mix_code = BatchManagementService._generate_mix_code(tank.nazwa_unikalna)
                active_mix = TankMixes(unique_code=mix_code, tank_id=tank_id)
                db.session.add(active_mix)

            quantity_to_add = batch.current_quantity
            if quantity_to_add <= 0: raise ValueError("Nie można dodać partii o zerowej ilości.")

            # Znajdź istniejący składnik lub stwórz nowy
            existing_component = next((c for c in active_mix.components if c.batch_id == batch_id), None)
            if existing_component:
                existing_component.quantity_in_mix += quantity_to_add
            else:
                new_component = MixComponents(batch_id=batch_id, quantity_in_mix=quantity_to_add)
                active_mix.components.append(new_component)
            
            batch.current_quantity = 0 # Przenosimy całą masę do śledzenia w mieszaninie
            
            db.session.commit()
            return {'mix_id': active_mix.id}
        except Exception as e:
            db.session.rollback(); raise e

    @staticmethod
    def get_mix_composition(mix_id):
        """Zwraca skład na podstawie wag zapisanych w MixComponents."""
        mix = db.session.get(TankMixes, mix_id)
        if not mix: return {'total_weight': Decimal('0.00'), 'components': []}
        
        components_with_quantity = [c for c in mix.components if c.quantity_in_mix > 0]
        total_weight = sum(c.quantity_in_mix for c in components_with_quantity)
        if total_weight == 0: return {'total_weight': Decimal('0.00'), 'components': []}

        composition_details = []
        for c in components_with_quantity:
            composition_details.append({
                'batch_id': c.batch.id, 'batch_code': c.batch.unique_code,
                'material_type': c.batch.material_type,
                'quantity_in_mix': c.quantity_in_mix,
                'percentage': (c.quantity_in_mix / total_weight) * 100
            })
        return {'total_weight': total_weight, 'components': composition_details}

    @staticmethod
    def withdraw_from_dirty_tank(tank_id, quantity_to_withdraw, operator):
        """
        Publiczna metoda do pobierania materiału ze zbiornika.
        Aktualizuje wagi w MixComponents i zwraca szczegóły pobrania.
        """
        try:
            source_tank = db.session.get(Sprzet, tank_id)
            if not source_tank or not source_tank.active_mix:
                raise ValueError("Zbiornik źródłowy jest pusty.")
            
            source_mix = source_tank.active_mix
            composition = BatchManagementService.get_mix_composition(source_mix.id)
            total_weight = composition['total_weight']
            if quantity_to_withdraw > total_weight:
                raise ValueError("Próba pobrania większej ilości niż dostępna.")

            withdrawal_details = []
            for component in source_mix.components:
                if component.quantity_in_mix > 0:
                    proportion = component.quantity_in_mix / total_weight
                    amount_to_deduct = quantity_to_withdraw * proportion
                    
                    component.quantity_in_mix -= amount_to_deduct
                    
                    withdrawal_details.append({
                        'batch_id': component.batch_id,
                        'quantity': amount_to_deduct
                    })
            
            db.session.commit()
            return withdrawal_details
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def transfer_between_dirty_tanks(source_tank_id, destination_tank_id, quantity_to_transfer, operator):
        """Orkiestruje transfer między dwoma zbiornikami brudnymi."""
        try:
            # --- Rozchód ---
            source_tank = db.session.get(Sprzet, source_tank_id)
            if not source_tank: raise ValueError("Zbiornik źródłowy nie istnieje.")
            source_mix_query = select(TankMixes).where(TankMixes.tank_id == source_tank_id, TankMixes.status == 'ACTIVE')
            source_mix = db.session.execute(source_mix_query).scalar_one_or_none()
            if not source_mix: raise ValueError("Zbiornik źródłowy jest pusty.")

            composition = BatchManagementService.get_mix_composition(source_mix.id)
            total_weight = composition['total_weight']
            if quantity_to_transfer > total_weight: raise ValueError("Próba pobrania większej ilości niż dostępna.")

            withdrawal_details = []
            for component_in_source in source_mix.components:
                if component_in_source.quantity_in_mix > 0:
                    proportion = component_in_source.quantity_in_mix / total_weight
                    amount_to_deduct = quantity_to_transfer * proportion
                    component_in_source.quantity_in_mix -= amount_to_deduct
                    withdrawal_details.append({'batch_id': component_in_source.batch_id, 'quantity': amount_to_deduct})

            # --- Przyjęcie ---
            dest_tank = db.session.get(Sprzet, destination_tank_id)
            if not dest_tank: raise ValueError("Zbiornik docelowy nie istnieje.")
            
            dest_mix_query = select(TankMixes).where(TankMixes.tank_id == destination_tank_id, TankMixes.status == 'ACTIVE')
            dest_mix = db.session.execute(dest_mix_query).scalar_one_or_none()
            if not dest_mix:
                mix_code = BatchManagementService._generate_mix_code(dest_tank.nazwa_unikalna)
                dest_mix = TankMixes(unique_code=mix_code, tank_id=dest_tank.id)
                db.session.add(dest_mix)
            
            components_in_dest = {c.batch_id: c for c in dest_mix.components}
            for detail in withdrawal_details:
                if detail['quantity'] > 0:
                    if detail['batch_id'] in components_in_dest:
                        components_in_dest[detail['batch_id']].quantity_in_mix += detail['quantity']
                    else:
                        new_component = MixComponents(batch_id=detail['batch_id'], quantity_in_mix=detail['quantity'])
                        dest_mix.components.append(new_component)
            
            db.session.commit()
        except Exception as e:
            db.session.rollback(); raise e

    @staticmethod
    def correct_batch_quantity(batch_id, new_quantity, operator, reason):
        """
        Dokonuje ręcznej korekty ilości partii i tworzy wpis w dzienniku zdarzeń.
        """
        try:
            batch_to_correct = db.session.get(Batches, batch_id)
            if not batch_to_correct:
                raise ValueError(f"Partia o ID {batch_id} nie istnieje.")
            
            original_quantity = batch_to_correct.current_quantity
            
            # Stwórz wpis w dzienniku zdarzeń
            audit_log = AuditTrail(
                user_id=operator,
                entity_type='Batches',
                entity_id=batch_id,
                operation_type='CORRECTION',
                field_name='current_quantity',
                old_value=str(original_quantity),
                new_value=str(new_quantity),
                reason=reason
            )
            
            # Zaktualizuj ilość w partii
            batch_to_correct.current_quantity = new_quantity
            
            db.session.add(audit_log)
            db.session.commit()
            
            return {'success': True, 'audit_log_id': audit_log.id}
        except Exception as e:
            db.session.rollback()
            raise e