# test_batch_management.py
import unittest
from datetime import datetime as dt
from datetime import timezone
from decimal import Decimal

from app import create_app, db
from app.config import TestConfig
from app.models import Sprzet, Batches, TankMixes, MixComponents, AuditTrail
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
        today_str = dt.now(timezone.utc).strftime('%y%m%d')
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
        """Sprawdza, czy tankowanie do ZAJĘTEGO zbiornika dodaje składnik."""
        batch1 = Batches(unique_code='S1', material_type='T10', source_type='CYS', source_name='C1', initial_quantity=1000, current_quantity=1000)
        batch2 = Batches(unique_code='S2', material_type='44', source_type='APOLLO', source_name='AP1', initial_quantity=500, current_quantity=500)
        tank = Sprzet(id=201, nazwa_unikalna='B01b', typ_sprzetu='reaktor')
        existing_mix = TankMixes(unique_code='M1', tank_id=tank.id)
        db.session.add_all([batch1, batch2, tank, existing_mix])
        db.session.commit()
        
        # POPRAWKA: Jawnie łączymy zbiornik z jego aktywną mieszaniną
        tank.active_mix_id = existing_mix.id
        
        component1 = MixComponents(mix_id=existing_mix.id, batch_id=batch1.id, quantity_in_mix=batch1.initial_quantity)
        db.session.add(component1)
        db.session.commit()

        BatchManagementService.tank_into_dirty_tank(batch_id=batch2.id, tank_id=tank.id, operator='USER_TEST')

        mix_after = db.session.get(TankMixes, existing_mix.id)
        self.assertEqual(len(mix_after.components), 2)
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

    def test_05_transfer_between_dirty_tanks_updates_component_quantities(self):
        """Sprawdza, czy transfer poprawnie przenosi proporcjonalne ilości."""
        batch1 = Batches(unique_code='S1', material_type='T10', source_type='CYS', source_name='C1', initial_quantity=1000, current_quantity=1000)
        batch2 = Batches(unique_code='S2', material_type='44', source_type='APOLLO', source_name='AP1', initial_quantity=500, current_quantity=500)
        tank1 = Sprzet(id=201, nazwa_unikalna='B01b')
        tank2 = Sprzet(id=202, nazwa_unikalna='B02b')
        db.session.add_all([batch1, batch2, tank1, tank2]); db.session.commit()
        
        BatchManagementService.tank_into_dirty_tank(batch1.id, tank1.id, 'TEST')
        BatchManagementService.tank_into_dirty_tank(batch2.id, tank1.id, 'TEST')

        BatchManagementService.transfer_between_dirty_tanks(
            source_tank_id=tank1.id, destination_tank_id=tank2.id,
            quantity_to_transfer=Decimal('300.00'), operator='USER_TEST'
        )
        
        source_mix = db.session.execute(select(TankMixes).where(TankMixes.tank_id == tank1.id)).scalar_one()
        dest_mix = db.session.execute(select(TankMixes).where(TankMixes.tank_id == tank2.id)).scalar_one()

        mix1_comp1 = db.session.execute(select(MixComponents).filter_by(mix_id=source_mix.id, batch_id=batch1.id)).scalar_one()
        self.assertAlmostEqual(mix1_comp1.quantity_in_mix, Decimal('800.00'))
        mix2_comp1 = db.session.execute(select(MixComponents).filter_by(mix_id=dest_mix.id, batch_id=batch1.id)).scalar_one()
        self.assertAlmostEqual(mix2_comp1.quantity_in_mix, Decimal('200.00'))

    def test_06_add_new_batch_to_existing_mix(self):
        """Sprawdza dołożenie nowej partii do istniejącej mieszaniny."""
        # POPRAWKA: Uzupełniamy `batch1` o wszystkie wymagane pola
        batch1 = Batches(
            unique_code='S1', material_type='T10', source_type='CYS', source_name='C1',
            initial_quantity=120, current_quantity=0 # Symulujemy resztki
        )
        tank2 = Sprzet(id=202, nazwa_unikalna='B02b')
        mix2 = TankMixes(unique_code='M2', tank_id=tank2.id)
        db.session.add_all([batch1, tank2, mix2]); db.session.commit()
        
        tank2.active_mix_id = mix2.id
        comp1_in_mix2 = MixComponents(mix_id=mix2.id, batch_id=batch1.id, quantity_in_mix=Decimal('120.00'))
        db.session.add(comp1_in_mix2); db.session.commit()

        batch3_fresh = Batches(
            unique_code='S3', material_type='38-2/L', source_type='APOLLO', source_name='AP2',
            initial_quantity=300, current_quantity=300
        )
        db.session.add(batch3_fresh); db.session.commit()

        BatchManagementService.tank_into_dirty_tank(
            batch_id=batch3_fresh.id, tank_id=tank2.id, operator='USER_TEST'
        )

        composition_after = BatchManagementService.get_mix_composition(mix_id=mix2.id)
        self.assertAlmostEqual(composition_after['total_weight'], Decimal('420.00')) # 120 + 300
        self.assertEqual(len(composition_after['components']), 2)

    
    def test_08_transfer_with_overdraw_corrects_source_and_logs_audit(self):
        """
        Sprawdza, czy transfer z ilością WIĘKSZĄ niż w systemie:
        1. "Magicznie" koryguje (dodaje) brakującą ilość w zbiorniku źródłowym.
        2. Tworzy wpis w AuditTrail o tej korekcie.
        3. Wykonuje transfer na pełnej, żądanej ilości.
        4. Poprawnie zeruje zbiornik źródłowy.
        """
        # --- Przygotowanie (Arrange) ---
        system_quantity = Decimal('100.00')
        batch1 = Batches(unique_code='S1', material_type='T10', source_type='CYS', source_name='C1', initial_quantity=system_quantity, current_quantity=system_quantity)
        tank1 = Sprzet(id=201, nazwa_unikalna='B01b')
        tank2 = Sprzet(id=202, nazwa_unikalna='B02b')
        db.session.add_all([batch1, tank1, tank2])
        db.session.commit()
        BatchManagementService.tank_into_dirty_tank(batch1.id, tank1.id, 'TEST')

        quantity_from_flowmeter = Decimal('110.00')

        # --- Działanie (Act) ---
        result = BatchManagementService.transfer_between_dirty_tanks(
            source_tank_id=tank1.id,
            destination_tank_id=tank2.id,
            quantity_to_transfer=quantity_from_flowmeter,
            operator='USER_TEST'
        )
        
        # --- Asercje (Assert) ---
        # 1. Sprawdź, czy funkcja zwróciła poprawne informacje
        self.assertTrue(result['was_adjusted'])
        self.assertAlmostEqual(result['transferred_quantity'], quantity_from_flowmeter)
        self.assertAlmostEqual(result['discrepancy'], Decimal('10.00'))

        # 2. Sprawdź, czy w AuditTrail powstał poprawny wpis
        audit_log = db.session.execute(
            select(AuditTrail).where(AuditTrail.operation_type == 'BALANCE_CORRECTION')
        ).scalar_one()
        
        self.assertEqual(audit_log.entity_type, 'TankMixes')
        self.assertEqual(audit_log.reason, f"Automatyczna korekta bilansu podczas transferu z B01b")
        
        # POPRAWKA: Sprawdzamy stan "przed" i "po", a nie samą różnicę
        self.assertEqual(audit_log.old_value, str(system_quantity))
        self.assertEqual(audit_log.new_value, str(quantity_from_flowmeter))
        self.assertEqual(audit_log.field_name, 'total_weight')

        # 3. Sprawdź stan zbiornika źródłowego - powinien być pusty
        source_mix_q = select(TankMixes).where(TankMixes.tank_id == tank1.id)
        source_mix = db.session.execute(source_mix_q).scalar_one()
        composition1_after = BatchManagementService.get_mix_composition(mix_id=source_mix.id)
        self.assertAlmostEqual(composition1_after['total_weight'], Decimal('0.00'))

        # 4. Sprawdź stan zbiornika docelowego - powinno do niego trafić pełne 110 kg
        dest_mix_q = select(TankMixes).where(TankMixes.tank_id == tank2.id)
        dest_mix = db.session.execute(dest_mix_q).scalar_one()
        composition2_after = BatchManagementService.get_mix_composition(mix_id=dest_mix.id)
        self.assertAlmostEqual(composition2_after['total_weight'], quantity_from_flowmeter)

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

    def test_09_transfer_with_zero_or_negative_quantity_is_rejected(self):
        """
        Sprawdza, czy próba transferu zerowej lub ujemnej ilości jest
        poprawnie blokowana i nie zmienia stanu systemu.
        """
        # --- Przygotowanie (Arrange) ---
        # 1. Stwórz stan początkowy: zbiornik `tank1` z mieszaniną o masie 100 kg
        batch1 = Batches(unique_code='S1', material_type='T10', source_type='CYS', source_name='C1', initial_quantity=100, current_quantity=100)
        tank1 = Sprzet(id=201, nazwa_unikalna='B01b')
        tank2 = Sprzet(id=202, nazwa_unikalna='B02b')
        db.session.add_all([batch1, tank1, tank2])
        db.session.commit()
        
        # 2. Użyj serwisu, aby poprawnie zatankować partię do zbiornika.
        #    Ta funkcja sama stworzy mieszaninę i ustawi `tank1.active_mix_id`.
        BatchManagementService.tank_into_dirty_tank(batch1.id, tank1.id, 'TEST')

        # 3. ZMIANA: Aby odczytać zaktualizowany `active_mix_id`, musimy odświeżyć
        #    obiekt `tank1` z bazy danych, ponieważ `commit` wewnątrz serwisu
        #    zakończył poprzednią sesję.
        tank1 = db.session.get(Sprzet, tank1.id)
        
        # 4. Pobierz stan początkowy do późniejszego porównania
        composition_before = BatchManagementService.get_mix_composition(mix_id=tank1.active_mix_id)
        self.assertAlmostEqual(composition_before['total_weight'], Decimal('100.00'))

        # --- Działanie 1: Transfer 0 kg ---
        result_zero = BatchManagementService.transfer_between_dirty_tanks(
            source_tank_id=tank1.id,
            destination_tank_id=tank2.id,
            quantity_to_transfer=Decimal('0.00'),
            operator='USER_TEST'
        )

        # --- Asercje 1 ---
        self.assertFalse(result_zero['was_adjusted'])
        self.assertEqual(result_zero['transferred_quantity'], Decimal('0.00'))
        
        composition_after_zero = BatchManagementService.get_mix_composition(mix_id=tank1.active_mix_id)
        self.assertEqual(composition_before, composition_after_zero)

        # --- Działanie 2: Transfer -50 kg ---
        with self.assertRaises(ValueError) as context:
            BatchManagementService.transfer_between_dirty_tanks(
                source_tank_id=tank1.id,
                destination_tank_id=tank2.id,
                quantity_to_transfer=Decimal('-50.00'),
                operator='USER_TEST'
            )
        self.assertIn("Ilość do przelania musi być dodatnia", str(context.exception))
        
        # --- Asercje 2 ---
        self.assertIn("Ilość do przelania musi być dodatnia", str(context.exception))

        # Sprawdź, czy stan zbiorników nadal jest nienaruszony
        composition_after_negative = BatchManagementService.get_mix_composition(mix_id=tank1.active_mix.id)
        self.assertEqual(composition_before, composition_after_negative)

    def test_10_transfer_of_exact_full_quantity_empties_source_perfectly(self):
        """
        Sprawdza, czy transfer DOKŁADNIE całej zawartości zbiornika
        poprawnie go zeruje, testując precyzję obliczeń Decimal.
        """
        # --- Przygotowanie (Arrange) ---
        # 1. Zbiornik źródłowy z mieszaniną o niecałkowitej masie 123.45 kg
        initial_qty_1 = Decimal('73.11')
        initial_qty_2 = Decimal('50.34')
        total_quantity = initial_qty_1 + initial_qty_2 # Dokładnie 123.45

        batch1 = Batches(unique_code='S1', material_type='T10', source_type='CYS', source_name='C1', initial_quantity=initial_qty_1, current_quantity=initial_qty_1)
        batch2 = Batches(unique_code='S2', material_type='44', source_type='APOLLO', source_name='AP1', initial_quantity=initial_qty_2, current_quantity=initial_qty_2)
        tank1 = Sprzet(id=201, nazwa_unikalna='B01b')
        tank2 = Sprzet(id=202, nazwa_unikalna='B02b')
        db.session.add_all([batch1, batch2, tank1, tank2])
        db.session.commit()
        BatchManagementService.tank_into_dirty_tank(batch1.id, tank1.id, 'TEST')
        BatchManagementService.tank_into_dirty_tank(batch2.id, tank1.id, 'TEST')

        # --- Działanie (Act) ---
        # Przelewamy DOKŁADNIE całą zawartość
        result = BatchManagementService.transfer_between_dirty_tanks(
            source_tank_id=tank1.id,
            destination_tank_id=tank2.id,
            quantity_to_transfer=total_quantity,
            operator='USER_TEST'
        )

        # --- Asercje (Assert) ---
        # 1. Sprawdź, czy funkcja zwróciła poprawne dane
        self.assertFalse(result['was_adjusted'])
        self.assertAlmostEqual(result['transferred_quantity'], total_quantity)

        # 2. Sprawdź, czy zbiornik źródłowy jest IDEALNIE pusty
        source_mix_q = select(TankMixes).where(TankMixes.tank_id == tank1.id)
        source_mix = db.session.execute(source_mix_q).scalar_one()
        composition1_after = BatchManagementService.get_mix_composition(mix_id=source_mix.id)
        self.assertEqual(composition1_after['total_weight'], Decimal('0.00'))
        
        # Sprawdźmy też poszczególne składniki
        for component in source_mix.components:
            self.assertEqual(component.quantity_in_mix, Decimal('0.00'))

        # 3. Sprawdź, czy do zbiornika docelowego trafiła DOKŁADNIE cała ilość
        dest_mix_q = select(TankMixes).where(TankMixes.tank_id == tank2.id)
        dest_mix = db.session.execute(dest_mix_q).scalar_one()
        composition2_after = BatchManagementService.get_mix_composition(mix_id=dest_mix.id)
        self.assertAlmostEqual(composition2_after['total_weight'], total_quantity)

    def test_11_tanking_into_fully_drained_tank_creates_new_mix(self):
        """
        Sprawdza, czy tankowanie do opróżnionego zbiornika:
        1. Tworzy nową mieszaninę.
        2. Archiwizuje starą mieszaninę.
        3. Odpina starą mieszaninę od sprzętu.
        """
        # --- Przygotowanie (Arrange) ---
        batch1 = Batches(unique_code='S1', material_type='T10', source_type='CYS', source_name='C1', initial_quantity=100, current_quantity=100)
        tank1 = Sprzet(id=201, nazwa_unikalna='B01b')
        tank2 = Sprzet(id=202, nazwa_unikalna='B02b')
        db.session.add_all([batch1, tank1, tank2]); db.session.commit()
        BatchManagementService.tank_into_dirty_tank(batch1.id, tank1.id, 'TEST')
        
        old_mix = db.session.execute(select(TankMixes).where(TankMixes.tank_id == tank1.id)).scalar_one()
        old_mix_id = old_mix.id

        BatchManagementService.transfer_between_dirty_tanks(
            source_tank_id=tank1.id, destination_tank_id=tank2.id,
            quantity_to_transfer=Decimal('100.00'), operator='TEST'
        )
        
        # Sprawdzenie stanu pośredniego
        db.session.refresh(old_mix)
        self.assertEqual(old_mix.status, 'ARCHIVED')

        batch_fresh = Batches(unique_code='S-FRESH', material_type='NEW', source_type='CYS', source_name='C2', initial_quantity=500, current_quantity=500)
        db.session.add(batch_fresh); db.session.commit()

        # --- Działanie (Act) ---
        result = BatchManagementService.tank_into_dirty_tank(batch_id=batch_fresh.id, tank_id=tank1.id, operator='TEST')

        # --- Asercje (Assert) ---
        new_mix_id = result['mix_id']
        self.assertNotEqual(new_mix_id, old_mix_id)
        
        # NOWA, KLUCZOWA ASERCJA: Sprawdź, czy zbiornik jest poprawnie powiązany
        tank1_after = db.session.get(Sprzet, tank1.id)
        self.assertIsNotNone(tank1_after.active_mix)
        self.assertEqual(tank1_after.active_mix.id, new_mix_id)

        new_mix = db.session.get(TankMixes, new_mix_id)
        self.assertEqual(new_mix.status, 'ACTIVE')
        self.assertEqual(len(new_mix.components), 1)

    def test_12_composition_with_depleted_component_is_correct(self):
        """
        Sprawdza, czy skład jest poprawnie obliczany, gdy jeden ze składników
        mieszaniny ma zerową ilość.
        """
        # --- Przygotowanie (Arrange) ---
        # Scenariusz: Mieszanina z trzema składnikami, ale jeden jest pusty.
        # Aktywny skład: 500kg (S1) + 250kg (S3). Razem 750kg.
        batch1 = Batches(unique_code='S1', material_type='T10', source_type='CYS', source_name='C1', initial_quantity=1000, current_quantity=500)
        batch2_empty = Batches(unique_code='S2-EMPTY', material_type='44', source_type='APOLLO', source_name='AP1', initial_quantity=200, current_quantity=0)
        batch3 = Batches(unique_code='S3', material_type='38-2/L', source_type='APOLLO', source_name='AP2', initial_quantity=250, current_quantity=250)
        
        tank = Sprzet(id=201, nazwa_unikalna='B01b')
        mix = TankMixes(unique_code='M1', tank_id=tank.id)
        db.session.add_all([batch1, batch2_empty, batch3, tank, mix])
        db.session.commit()
        
        # Tworzymy składniki, jeden z nich ma zerową ilość
        comp1 = MixComponents(mix_id=mix.id, batch_id=batch1.id, quantity_in_mix=Decimal('500.00'))
        comp2_empty = MixComponents(mix_id=mix.id, batch_id=batch2_empty.id, quantity_in_mix=Decimal('0.00'))
        comp3 = MixComponents(mix_id=mix.id, batch_id=batch3.id, quantity_in_mix=Decimal('250.00'))
        db.session.add_all([comp1, comp2_empty, comp3])
        db.session.commit()

        # --- Działanie (Act) ---
        composition = BatchManagementService.get_mix_composition(mix_id=mix.id)

        # --- Asercje (Assert) ---
        # 1. Sprawdź, czy całkowita waga jest sumą tylko aktywnych składników
        self.assertAlmostEqual(composition['total_weight'], Decimal('750.00'))
        
        # 2. Sprawdź, czy w zwróconej kompozycji są tylko DWA składniki
        self.assertEqual(len(composition['components']), 2)
        
        # 3. Sprawdź, czy procenty są obliczone na podstawie poprawnej sumy (750)
        # Oczekiwane proporcje: S1 = 500/750 (~66.67%), S3 = 250/750 (~33.33%)
        comp1_data = next(c for c in composition['components'] if c['batch_id'] == batch1.id)
        comp3_data = next(c for c in composition['components'] if c['batch_id'] == batch3.id)
        
        self.assertAlmostEqual(comp1_data['percentage'], Decimal('66.6666'), places=2)
        self.assertAlmostEqual(comp3_data['percentage'], Decimal('33.3333'), places=2)


    def test_13_operations_use_corrected_quantity(self):
        """
        Sprawdza, czy operacje (np. tankowanie) używają ilości partii
        po ręcznej korekcie, a nie oryginalnej.
        """
        # --- Przygotowanie (Arrange) ---
        # 1. Stwórz partię pierwotną z początkową ilością 1000 kg
        batch = Batches(
            unique_code='S1-CORRECT', material_type='T10', source_type='CYS', source_name='C1',
            initial_quantity=1000, current_quantity=1000
        )
        tank = Sprzet(id=201, nazwa_unikalna='B01b')
        db.session.add_all([batch, tank])
        db.session.commit()

        # 2. Wykonaj ręczną korektę ilości w dół do 950 kg
        corrected_quantity = Decimal('950.00')
        BatchManagementService.correct_batch_quantity(
            batch_id=batch.id,
            new_quantity=corrected_quantity,
            operator='SUPERVISOR',
            reason='Inwentaryzacja'
        )

        # Asercja pośrednia - upewnij się, że korekta zadziałała
        db.session.refresh(batch)
        self.assertAlmostEqual(batch.current_quantity, corrected_quantity)

        # --- Działanie (Act) ---
        # Zatankuj tę skorygowaną partię do zbiornika
        BatchManagementService.tank_into_dirty_tank(
            batch_id=batch.id,
            tank_id=tank.id,
            operator='USER_TEST'
        )

        # --- Asercje (Assert) ---
        # 1. Sprawdź, czy `current_quantity` partii pierwotnej jest teraz 0
        db.session.refresh(batch)
        self.assertEqual(batch.current_quantity, 0)
        
        # 2. Sprawdź skład mieszaniny w zbiorniku
        mix = db.session.execute(
            select(TankMixes).where(TankMixes.tank_id == tank.id, TankMixes.status == 'ACTIVE')
        ).scalar_one()
        composition = BatchManagementService.get_mix_composition(mix_id=mix.id)
        
        # Kluczowa asercja: masa w mieszaninie musi być równa skorygowanej ilości
        self.assertAlmostEqual(composition['total_weight'], corrected_quantity)
        self.assertEqual(len(composition['components']), 1)
        self.assertAlmostEqual(composition['components'][0]['quantity_in_mix'], corrected_quantity)