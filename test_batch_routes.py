# test_batch_routes.py
import unittest
import json
from decimal import Decimal

from app import create_app, db
from app.config import TestConfig
from app.models import *
from sqlalchemy import text, select
from app.batch_management_service import BatchManagementService


class TestBatchRoutes(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        with self.app.app_context():
            db.session.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            for table in reversed(db.metadata.sorted_tables):
                db.session.execute(text(f'TRUNCATE TABLE {table.name}'))
            db.session.execute(text("SET FOREIGN_KEY_CHECKS=1"))
            db.session.commit()

    def tearDown(self):
        db.session.remove()
        self.app_context.pop()

    def test_01_receive_from_tanker_success(self):
        """
        Sprawdza, czy POST /api/batches/receive/from-tanker poprawnie
        tworzy nową Partię Pierwotną w bazie danych.
        """
        # --- Przygotowanie (Arrange) ---
        payload = {
            "material_type": "T10",
            "source_name": "CYS-WAW-01",
            "quantity_kg": "12345.67",
            "operator": "Jan Kowalski"
        }

        # --- Działanie (Act) ---
        response = self.client.post(
            '/api/batches/receive/from-tanker',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        # --- Asercje (Assert) ---
        # 1. Sprawdź odpowiedź API
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('batch_id', data['data'])

        # 2. Sprawdź stan bazy danych
        batch_id = data['data']['batch_id']
        batch_in_db = db.session.get(Batches, batch_id)
        self.assertIsNotNone(batch_in_db)
        self.assertEqual(batch_in_db.material_type, "T10")
        self.assertEqual(batch_in_db.source_type, "CYS")
        self.assertAlmostEqual(batch_in_db.initial_quantity, Decimal("12345.67"))


    def test_02_transfer_to_dirty_tank_success(self):
        """
        Sprawdza, czy POST /api/batches/transfer/to-dirty-tank poprawnie
        tankuje partię do zbiornika, tworząc nową mieszaninę.
        """
        # --- Przygotowanie (Arrange) ---
        # 1. Stwórz w bazie partię pierwotną i pusty zbiornik
        batch = Batches(
            unique_code='S1', material_type='T10', source_type='CYS', source_name='C1',
            initial_quantity=1000, current_quantity=1000
        )
        tank = Sprzet(id=201, nazwa_unikalna='B01b', typ_sprzetu='reaktor')
        db.session.add_all([batch, tank])
        db.session.commit()

        # 2. Przygotuj dane żądania
        payload = {
            "batch_id": batch.id,
            "tank_id": tank.id
        }

        # --- Działanie (Act) ---
        response = self.client.post(
            '/api/batches/transfer/to-dirty-tank',
            data=json.dumps(payload),
            content_type='application/json'
        )

        # --- Asercje (Assert) ---
        # 1. Sprawdź odpowiedź API
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('mix_id', data['data'])

        # 2. Sprawdź stan bazy danych
        # Upewnij się, że zbiornik ma teraz powiązaną aktywną mieszaninę
        tank_after = db.session.get(Sprzet, tank.id)
        self.assertIsNotNone(tank_after.active_mix)
        self.assertEqual(tank_after.active_mix.id, data['data']['mix_id'])
        
        # Sprawdź, czy ta mieszanina zawiera nasz składnik
        mix_in_db = db.session.get(TankMixes, data['data']['mix_id'])
        self.assertEqual(len(mix_in_db.components), 1)
        self.assertEqual(mix_in_db.components[0].batch_id, batch.id)

    def test_03_transfer_between_tanks_success(self):
        """
        Sprawdza, czy POST /api/batches/transfer/tank-to-tank poprawnie
        przenosi masę i składniki między mieszaninami w dwóch zbiornikach.
        """
        # --- Przygotowanie (Arrange) ---
        # 1. Zbiornik źródłowy z mieszaniną 1500kg (1000kg T10 + 500kg 44)
        batch1 = Batches(unique_code='S1', material_type='T10', source_type='CYS', source_name='C1', initial_quantity=1000, current_quantity=0)
        batch2 = Batches(unique_code='S2', material_type='44', source_type='APOLLO', source_name='AP1', initial_quantity=500, current_quantity=0)
        tank1 = Sprzet(id=201, nazwa_unikalna='B01b')
        mix1 = TankMixes(unique_code='M1', tank_id=tank1.id)
        db.session.add_all([batch1, batch2, tank1, mix1])
        db.session.commit()
        tank1.active_mix_id = mix1.id # Jawne przypisanie
        comp1 = MixComponents(mix_id=mix1.id, batch_id=batch1.id, quantity_in_mix=Decimal('1000.00'))
        comp2 = MixComponents(mix_id=mix1.id, batch_id=batch2.id, quantity_in_mix=Decimal('500.00'))
        tank2 = Sprzet(id=202, nazwa_unikalna='B02b')
        db.session.add_all([comp1, comp2, tank2])
        db.session.commit()

        # 3. Dane żądania
        payload = {
            "source_tank_id": tank1.id,
            "destination_tank_id": tank2.id,
            "quantity_kg": "300.00"
        }

        # --- Działanie (Act) ---
        response = self.client.post(
            '/api/batches/transfer/tank-to-tank',
            data=json.dumps(payload),
            content_type='application/json'
        )

        # --- Asercje (Assert) ---
        # 1. Sprawdź odpowiedź API
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['status'], 'success')
        
        # 2. Sprawdź stan zbiornika źródłowego (musi mieć 1200kg)
        composition1_after = BatchManagementService.get_mix_composition(mix_id=mix1.id)
        self.assertAlmostEqual(composition1_after['total_weight'], Decimal('1200.00'))
        
        # ZMIANA: Sprawdzamy `active_mix_id`, a nie `active_mix`
        tank2_after = db.session.get(Sprzet, tank2.id)
        self.assertIsNotNone(tank2_after.active_mix_id)
        composition2_after = BatchManagementService.get_mix_composition(mix_id=tank2_after.active_mix_id)
        self.assertAlmostEqual(composition2_after['total_weight'], Decimal('300.00'))
        self.assertEqual(len(composition2_after['components']), 2)

        # 4. Sprawdźmy konkretną ilość jednego ze składników w nowej mieszaninie
        # Oczekiwane: 300 * (1000/1500) = 200kg partii S1
        comp1_in_mix2_data = next(c for c in composition2_after['components'] if c['batch_id'] == batch1.id)
        self.assertAlmostEqual(comp1_in_mix2_data['quantity_in_mix'], Decimal('200.00'))


    def test_04_receive_from_apollo_success(self):
        """
        Sprawdza, czy POST /api/batches/receive/from-apollo poprawnie
        tworzy nową Partię Pierwotną z wytapiarki Apollo.
        """
        # --- Przygotowanie (Arrange) ---
        payload = {
            "material_type": "44",
            "source_name": "AP01", # Nazwa wytapiarki
            "quantity_kg": "550.75"
        }

        # --- Działanie (Act) ---
        response = self.client.post(
            '/api/batches/receive/from-apollo',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        # --- Asercje (Assert) ---
        # 1. Sprawdź odpowiedź API
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('batch_id', data['data'])

        # 2. Sprawdź stan bazy danych
        batch_id = data['data']['batch_id']
        batch_in_db = db.session.get(Batches, batch_id)
        self.assertIsNotNone(batch_in_db)
        self.assertEqual(batch_in_db.material_type, "44")
        
        # Kluczowa asercja: sprawdź, czy źródło to 'APOLLO'
        self.assertEqual(batch_in_db.source_type, "APOLLO")
        self.assertEqual(batch_in_db.source_name, "AP01")
        
        self.assertAlmostEqual(batch_in_db.initial_quantity, Decimal("550.75"))

    def test_05_get_tank_status_for_occupied_tank(self):
        """
        Sprawdza, czy GET /api/tanks/<id>/status poprawnie zwraca
        skład dla zajętego zbiornika.
        """
        # --- Przygotowanie (Arrange) ---
        # Zbiornik z mieszaniną 2 składników (750kg + 250kg = 1000kg)
        batch1 = Batches(unique_code='S1', material_type='T10', source_type='CYS', source_name='C1', initial_quantity=750, current_quantity=0)
        batch2 = Batches(unique_code='S2', material_type='44', source_type='APOLLO', source_name='AP1', initial_quantity=250, current_quantity=0)
        tank = Sprzet(id=201, nazwa_unikalna='B01b')
        mix = TankMixes(unique_code='M1', tank=tank)
        db.session.add_all([batch1, batch2, tank])
        db.session.commit()
        tank.active_mix_id = mix.id
        comp1 = MixComponents(mix_id=mix.id, batch_id=batch1.id, quantity_in_mix=Decimal('750.00'))
        comp2 = MixComponents(mix_id=mix.id, batch_id=batch2.id, quantity_in_mix=Decimal('250.00'))
        db.session.add_all([comp1, comp2])
        db.session.commit()

        # --- Działanie (Act) ---
        response = self.client.get(f'/api/batches/tanks/{tank.id}/status')

        # --- Asercje (Assert) ---
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        
        self.assertEqual(data['status'], 'success')
        self.assertFalse(data['is_empty'])
        self.assertEqual(data['tank_name'], 'B01b')
        
        # Sprawdź dane mieszaniny
        mix_data = data['data']
        self.assertEqual(mix_data['total_weight'], '1000.00')
        self.assertEqual(len(mix_data['components']), 2)
        
        # Sprawdź dane jednego ze składników
        comp1_data = next(c for c in mix_data['components'] if c['batch_id'] == batch1.id)
        self.assertEqual(comp1_data['quantity_in_mix'], '750.00')
        self.assertEqual(comp1_data['percentage'], '75.00')

    def test_06_get_tank_status_for_empty_tank(self):
        """
        Sprawdza, czy GET /api/tanks/<id>/status poprawnie zwraca
        informację o pustym zbiorniku.
        """
        # --- Przygotowanie (Arrange) ---
        tank = Sprzet(id=201, nazwa_unikalna='B01b')
        db.session.add(tank)
        db.session.commit()

        # --- Działanie (Act) ---
        response = self.client.get(f'/api/batches/tanks/{tank.id}/status')

        # --- Asercje (Assert) ---
        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        self.assertEqual(data['status'], 'success')
        self.assertTrue(data['is_empty'])
        self.assertEqual(len(data['data']['components']), 0)