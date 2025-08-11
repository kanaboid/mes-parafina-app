# test_batch_management.py
import unittest
from datetime import datetime as dt
from decimal import Decimal

from app import create_app, db
from app.config import TestConfig
from app.models import *
from sqlalchemy import select, text

# Zakładamy, że ten plik będzie istniał
from app.batch_management_service import BatchManagementService

class TestBatchManagementService(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        with self.app.app_context():
            db.session.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            for table in reversed(db.metadata.sorted_tables):
                db.session.execute(text(f'TRUNCATE TABLE {table.name}'))
            db.session.execute(text("SET FOREIGN_KEY_CHECKS=1"))
            db.session.commit()

    def tearDown(self):
        db.session.remove()
        self.app_context.pop()

    def test_01_create_raw_material_batch_sukces(self):
        """
        Sprawdza, czy serwis poprawnie tworzy nową Partię Pierwotną w bazie danych.
        """
        # --- Przygotowanie (Arrange) ---
        material_type = 'T10'
        source_name = 'CYS01'
        quantity = Decimal('10000.50')
        operator = 'USER_TEST'
        
        # --- Działanie (Act) ---
        result = BatchManagementService.create_raw_material_batch(
            material_type=material_type,
            source_type='CYS',
            source_name=source_name,
            quantity=quantity,
            operator=operator
        )

        # --- Asercje (Assert) ---
        # 1. Sprawdź, czy funkcja zwróciła oczekiwane dane
        self.assertIsNotNone(result)
        self.assertIn('batch_id', result)
        self.assertIn('unique_code', result)

        # 2. Sprawdź, czy rekord faktycznie istnieje w bazie i ma poprawne dane
        batch_in_db = db.session.get(Batches, result['batch_id'])
        self.assertIsNotNone(batch_in_db)
        self.assertEqual(batch_in_db.material_type, material_type)
        self.assertEqual(batch_in_db.source_name, source_name)
        self.assertEqual(batch_in_db.initial_quantity, quantity)
        self.assertEqual(batch_in_db.current_quantity, quantity)
        self.assertEqual(batch_in_db.status, 'ACTIVE')
        
        # 3. Sprawdź, czy unikalny kod został wygenerowany w oczekiwanym formacie
        today_str = dt.now().strftime('%y%m%d')
        expected_prefix = f"S-{source_name}-{material_type}-{today_str}"
        self.assertTrue(result['unique_code'].startswith(expected_prefix))

    def test_02_tank_into_empty_dirty_tank_creates_mix_with_quantity(self):
        """
        Sprawdza, czy tankowanie do PUSTEGO zbiornika tworzy Mieszaninę
        i zapisuje w niej poprawną ilość surowca.
        """
        # --- Przygotowanie (Arrange) ---
        batch = Batches(unique_code='S1', material_type='T10', source_type='CYS', source_name='C1', initial_quantity=1000, current_quantity=1000)
        tank = Sprzet(id=201, nazwa_unikalna='B01b', typ_sprzetu='reaktor')
        db.session.add_all([batch, tank])
        db.session.commit()

        # --- Działanie (Act) ---
        result = BatchManagementService.tank_into_dirty_tank(
            batch_id=batch.id,
            tank_id=tank.id,
            operator='USER_TEST'
        )
        
        # --- Asercje (Assert) ---
        new_mix = db.session.get(TankMixes, result['mix_id'])
        self.assertEqual(len(new_mix.components), 1)
        
        # NOWA ASERCJA: Sprawdź, czy ilość w składniku została poprawnie zapisana
        component = new_mix.components[0]
        self.assertEqual(component.batch_id, batch.id)
        self.assertEqual(component.quantity_in_mix, batch.initial_quantity)

        # Sprawdź, czy partia pierwotna została "wyzerowana" (jej masa została przeniesiona)
        db.session.refresh(batch)
        self.assertEqual(batch.current_quantity, 0)

    def test_03_tank_into_occupied_dirty_tank_adds_component_with_quantity(self):
        """
        Sprawdza, czy tankowanie do ZAJĘTEGO zbiornika dodaje składnik
        z poprawną ilością.
        """
        # --- Przygotowanie (Arrange) ---
        batch1 = Batches(unique_code='S1', material_type='T10', source_type='CYS', source_name='C1', initial_quantity=1000, current_quantity=1000)
        batch2 = Batches(unique_code='S2', material_type='44', source_type='APOLLO', source_name='AP1', initial_quantity=500, current_quantity=500)
        tank = Sprzet(id=201, nazwa_unikalna='B01b', typ_sprzetu='reaktor')
        
        # Tworzymy istniejącą mieszaninę
        existing_mix = TankMixes(unique_code='M1', tank=tank)
        db.session.add_all([batch1, batch2, tank])
        db.session.commit()
        
        # Dodajemy do niej pierwszy składnik
        component1 = MixComponents(mix_id=existing_mix.id, batch_id=batch1.id, quantity_in_mix=batch1.current_quantity)
        db.session.add(component1)
        db.session.commit()
        
        # --- Działanie (Act) ---
        # Dolewamy partię batch2
        BatchManagementService.tank_into_dirty_tank(batch_id=batch2.id, tank_id=tank.id, operator='USER_TEST')

        # --- Asercje (Assert) ---
        mix_after = db.session.get(TankMixes, existing_mix.id)
        self.assertEqual(len(mix_after.components), 2)

        # Znajdź nowo dodany składnik i sprawdź jego ilość
        new_component = next(c for c in mix_after.components if c.batch_id == batch2.id)
        self.assertEqual(new_component.quantity_in_mix, batch2.initial_quantity)

    def test_04a_get_mix_composition_calculates_correctly(self):
        """Sprawdza `get_mix_composition`."""
        batch1 = Batches(unique_code='S1', material_type='T10', source_type='CYS', source_name='C1', initial_quantity=750, current_quantity=750)
        batch2 = Batches(unique_code='S2', material_type='44', source_type='APOLLO', source_name='AP1', initial_quantity=250, current_quantity=250)
        tank = Sprzet(id=201, nazwa_unikalna='B01b')
        mix = TankMixes(id=50, unique_code='M1', tank=tank)
        db.session.add_all([batch1, batch2, tank])
        db.session.commit()
        
        # POPRAWKA: Dodajemy `quantity_in_mix`
        component1 = MixComponents(mix_id=mix.id, batch_id=batch1.id, quantity_in_mix=Decimal('750.00'))
        component2 = MixComponents(mix_id=mix.id, batch_id=batch2.id, quantity_in_mix=Decimal('250.00'))
        db.session.add_all([component1, component2])
        db.session.commit()

        composition = BatchManagementService.get_mix_composition(mix_id=mix.id)

        self.assertAlmostEqual(composition['total_weight'], Decimal('1000.00'))
        comp1_data = next(c for c in composition['components'] if c['batch_id'] == batch1.id)
        self.assertAlmostEqual(comp1_data['percentage'], Decimal('75.0'))

    def test_04b_get_mix_composition_for_empty_mix(self):
        """Sprawdza `get_mix_composition` dla pustej mieszaniny."""
        tank = Sprzet(id=201, nazwa_unikalna='B01b')
        mix = TankMixes(id=50, unique_code='M1', tank=tank)
        db.session.add(mix)
        db.session.commit()
        composition = BatchManagementService.get_mix_composition(mix_id=mix.id)
        self.assertEqual(composition['total_weight'], Decimal('0.00'))

    def test_05_withdraw_from_dirty_tank_updates_quantities_proportionally(self):
        """Sprawdza `withdraw...`."""
        batch1 = Batches(unique_code='S1', material_type='T10', source_type='CYS', source_name='C1', initial_quantity=1000, current_quantity=1000)
        batch2 = Batches(unique_code='S2', material_type='44', source_type='APOLLO', source_name='AP1', initial_quantity=500, current_quantity=500)
        tank = Sprzet(id=201, nazwa_unikalna='B01b')
        mix = TankMixes(id=50, unique_code='M1', tank=tank)
        db.session.add_all([batch1, batch2, tank])
        db.session.commit()
        
        # POPRAWKA: Dodajemy `quantity_in_mix`
        component1 = MixComponents(mix_id=mix.id, batch_id=batch1.id, quantity_in_mix=Decimal('1000.00'))
        component2 = MixComponents(mix_id=mix.id, batch_id=batch2.id, quantity_in_mix=Decimal('500.00'))
        db.session.add_all([component1, component2])
        db.session.commit()

        withdrawal_details = BatchManagementService.withdraw_from_dirty_tank(
            tank_id=tank.id,
            quantity_to_withdraw=Decimal('300.00'),
            operator='USER_TEST'
        )
        
        # W `withdraw_from_dirty_tank` aktualizujemy `current_quantity` w Batches.
        # W nowej logice powinniśmy aktualizować `quantity_in_mix` w MixComponents.
        # Sprawdźmy to drugie.
        comp1_after = db.session.get(MixComponents, component1.id)
        comp2_after = db.session.get(MixComponents, component2.id)

        self.assertAlmostEqual(comp1_after.quantity_in_mix, Decimal('800.00')) # 1000 - 200
        self.assertAlmostEqual(comp2_after.quantity_in_mix, Decimal('400.00')) # 500 - 100

    def test_06_transfer_between_dirty_tanks_updates_component_quantities(self):
        """
        Sprawdza, czy transfer poprawnie przenosi proporcjonalne ilości
        między wpisami w MixComponents obu mieszanin.
        """
        # --- Przygotowanie (Arrange) ---
        # POPRAWKA: Uzupełniamy obiekty Batches o wszystkie wymagane pola
        batch1 = Batches(
            unique_code='S1', material_type='T10', source_type='CYS', source_name='C1', 
            initial_quantity=1000, current_quantity=1000
        )
        batch2 = Batches(
            unique_code='S2', material_type='44', source_type='APOLLO', source_name='AP1', 
            initial_quantity=500, current_quantity=500
        )
        
        tank1 = Sprzet(id=201, nazwa_unikalna='B01b')
        tank2 = Sprzet(id=202, nazwa_unikalna='B02b')
        db.session.add_all([batch1, batch2, tank1, tank2])
        db.session.commit()
        
        # Zatankuj obie partie do tank1
        BatchManagementService.tank_into_dirty_tank(batch1.id, tank1.id, 'TEST')
        BatchManagementService.tank_into_dirty_tank(batch2.id, tank1.id, 'TEST')
        # W mix1 w tank1 jest teraz 1000kg T10 i 500kg 44

        # --- Działanie (Act) ---
        BatchManagementService.transfer_between_dirty_tanks(
            source_tank_id=tank1.id,
            destination_tank_id=tank2.id,
            quantity_to_transfer=Decimal('300.00'),
            operator='USER_TEST'
        )

        # --- Asercje (Assert) ---
        source_mix_q = select(TankMixes).where(TankMixes.tank_id == tank1.id)
        source_mix = db.session.execute(source_mix_q).scalar_one()
        dest_mix_q = select(TankMixes).where(TankMixes.tank_id == tank2.id)
        dest_mix = db.session.execute(dest_mix_q).scalar_one()

        # Sprawdź stan zbiornika źródłowego
        mix1_comp1 = db.session.execute(select(MixComponents).filter_by(mix_id=source_mix.id, batch_id=batch1.id)).scalar_one()
        mix1_comp2 = db.session.execute(select(MixComponents).filter_by(mix_id=source_mix.id, batch_id=batch2.id)).scalar_one()
        self.assertAlmostEqual(mix1_comp1.quantity_in_mix, Decimal('800.00')) # 1000 - 200
        self.assertAlmostEqual(mix1_comp2.quantity_in_mix, Decimal('400.00')) # 500 - 100

        # Sprawdź stan zbiornika docelowego
        mix2_comp1 = db.session.execute(select(MixComponents).filter_by(mix_id=dest_mix.id, batch_id=batch1.id)).scalar_one()
        mix2_comp2 = db.session.execute(select(MixComponents).filter_by(mix_id=dest_mix.id, batch_id=batch2.id)).scalar_one()
        self.assertAlmostEqual(mix2_comp1.quantity_in_mix, Decimal('200.00'))
        self.assertAlmostEqual(mix2_comp2.quantity_in_mix, Decimal('100.00'))

    def test_07_add_new_batch_to_existing_mix(self):
        """
        Sprawdza scenariusz dołożenia nowej partii pierwotnej (inny typ)
        do zbiornika, w którym już znajduje się mieszanina.
        """
        # --- Przygotowanie (Arrange) ---
        # 1. Tworzymy istniejący stan: tank2 zawiera mieszaninę (mix2)
        #    składającą się z 200kg (120kg T10 + 80kg 44)
        batch1 = Batches(unique_code='S1', material_type='T10', source_type='CYS', source_name='C1', initial_quantity=1000, current_quantity=880)
        batch2 = Batches(unique_code='S2', material_type='44', source_type='APOLLO', source_name='AP1', initial_quantity=500, current_quantity=420)
        tank2 = Sprzet(id=202, nazwa_unikalna='B02b')
        mix2 = TankMixes(unique_code='M2', tank=tank2)
        db.session.add_all([batch1, batch2, tank2])
        db.session.commit()
        
        comp1_in_mix2 = MixComponents(mix_id=mix2.id, batch_id=batch1.id, quantity_in_mix=Decimal('120.00'))
        comp2_in_mix2 = MixComponents(mix_id=mix2.id, batch_id=batch2.id, quantity_in_mix=Decimal('80.00'))
        db.session.add_all([comp1_in_mix2, comp2_in_mix2])
        db.session.commit()
        
        # 2. Tworzymy nową, "świeżą" partię, którą będziemy dolewać
        batch3_fresh = Batches(
            unique_code='S3', material_type='38-2/L', source_type='APOLLO', source_name='AP2',
            initial_quantity=300, current_quantity=300
        )
        db.session.add(batch3_fresh)
        db.session.commit()

        # --- Działanie (Act) ---
        # Używamy funkcji `tank_into_dirty_tank`, aby dołożyć nową partię do tank2
        BatchManagementService.tank_into_dirty_tank(
            batch_id=batch3_fresh.id,
            tank_id=tank2.id,
            operator='USER_TEST'
        )

        # --- Asercje (Assert) ---
        # 1. Sprawdź, czy `current_quantity` nowej partii zostało poprawnie wyzerowane
        db.session.refresh(batch3_fresh)
        self.assertEqual(batch3_fresh.current_quantity, 0)
        
        # 2. Pobierz skład mieszaniny w tank2 po operacji
        composition_after = BatchManagementService.get_mix_composition(mix_id=mix2.id)
        
        # 3. Sprawdź, czy całkowita waga się zgadza
        # Oczekiwana waga: 200kg (stara) + 300kg (nowa) = 500kg
        self.assertAlmostEqual(composition_after['total_weight'], Decimal('500.00'))
        
        # 4. Sprawdź, czy mieszanina ma teraz TRZY składniki
        self.assertEqual(len(composition_after['components']), 3)
        
        # 5. Sprawdź, czy ilość nowego składnika w mieszaninie jest poprawna
        new_component_data = next(c for c in composition_after['components'] if c['batch_id'] == batch3_fresh.id)
        self.assertAlmostEqual(new_component_data['quantity_in_mix'], Decimal('300.00'))

        # 6. Sprawdź, czy stare składniki pozostały nienaruszone
        old_component1_data = next(c for c in composition_after['components'] if c['batch_id'] == batch1.id)
        self.assertAlmostEqual(old_component1_data['quantity_in_mix'], Decimal('120.00'))

    def test_08_correct_batch_quantity_updates_value_and_creates_audit_log(self):
        """
        Sprawdza, czy korekta ilości poprawnie zmienia wagę partii
        i tworzy szczegółowy wpis w dzienniku zdarzeń (AuditTrail).
        """
        # --- Przygotowanie (Arrange) ---
        # 1. Stwórz partię z początkową ilością 1000 kg
        batch = Batches(
            unique_code='S1', material_type='T10', source_type='CYS', source_name='C1',
            initial_quantity=1000, current_quantity=1000
        )
        db.session.add(batch)
        db.session.commit()

        # 2. Zdefiniuj parametry korekty
        original_quantity = batch.current_quantity
        new_quantity = Decimal('950.55')
        operator = 'SUPERVISOR'
        reason = 'Korekta po inwentaryzacji'

        # --- Działanie (Act) ---
        result = BatchManagementService.correct_batch_quantity(
            batch_id=batch.id,
            new_quantity=new_quantity,
            operator=operator,
            reason=reason
        )

        # --- Asercje (Assert) ---
        self.assertTrue(result['success'])
        
        # 1. Sprawdź, czy ilość w partii została zaktualizowana
        db.session.refresh(batch)
        self.assertAlmostEqual(batch.current_quantity, new_quantity)
        
        # 2. Sprawdź, czy w AuditTrail powstał dokładnie jeden, poprawny wpis
        audit_log_query = select(AuditTrail).where(
            AuditTrail.entity_type == 'Batches',
            AuditTrail.entity_id == batch.id
        )
        audit_logs = db.session.execute(audit_log_query).scalars().all()
        
        self.assertEqual(len(audit_logs), 1)
        
        audit_log = audit_logs[0]
        self.assertEqual(audit_log.user_id, operator)
        self.assertEqual(audit_log.operation_type, 'CORRECTION')
        self.assertEqual(audit_log.field_name, 'current_quantity')
        self.assertEqual(audit_log.old_value, str(original_quantity))
        self.assertEqual(audit_log.new_value, str(new_quantity))
        self.assertEqual(audit_log.reason, reason)

    def test_09_correct_batch_quantity_for_nonexistent_batch_fails(self):
        """
        Sprawdza, czy próba korekty nieistniejącej partii rzuca błąd.
        """
        with self.assertRaises(ValueError) as context:
            BatchManagementService.correct_batch_quantity(
                batch_id=999, # Nieistniejące ID
                new_quantity=Decimal('100'),
                operator='TEST',
                reason='Test'
            )
        self.assertIn("Partia o ID 999 nie istnieje", str(context.exception))