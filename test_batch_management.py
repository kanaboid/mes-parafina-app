# test_batch_management.py
import unittest
from datetime import datetime
from decimal import Decimal

from app import create_app, db
from app.config import TestConfig
from app.models import Batches
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
        today_str = datetime.now().strftime('%y%m%d')
        expected_prefix = f"S-{source_name}-{material_type}-{today_str}"
        self.assertTrue(result['unique_code'].startswith(expected_prefix))