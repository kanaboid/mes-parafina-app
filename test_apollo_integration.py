# test_apollo_integration.py
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch # <--- DODAJ TEN IMPORT

from app import create_app, db
from app.config import TestConfig
from app.models import Sprzet, Batches, TankMixes, MixComponents, AuditTrail, ApolloSesje, ApolloTracking
from sqlalchemy import select, text

from app.batch_management_service import BatchManagementService
# ApolloService jest importowany tylko po to, by wskazać cel dla patcha
from app import apollo_service 

TEST_APOLLO_ID = 999
TEST_APOLLO_NAZWA = 'AP999'
TEST_TANK_ID = 201
TEST_TANK_NAZWA = 'B01b'

class TestApolloBatchIntegration(unittest.TestCase):
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
            
            sprzet_apollo = Sprzet(id=TEST_APOLLO_ID, nazwa_unikalna=TEST_APOLLO_NAZWA, typ_sprzetu='apollo', stan_sprzetu='Gotowy')
            tank = Sprzet(id=TEST_TANK_ID, nazwa_unikalna=TEST_TANK_NAZWA, typ_sprzetu='reaktor')
            db.session.add_all([sprzet_apollo, tank])
            db.session.commit()

    def tearDown(self):
        db.session.remove()
        self.app_context.pop()
    
    # Dekorator 'patch' tymczasowo podmienia metodę w apollo_service
    @patch('app.apollo_service.ApolloService.oblicz_aktualny_stan_apollo')
    def test_01_transfer_from_apollo_with_overdraw_creates_batch_and_audit_log(self, mock_oblicz_stan):
        """
        Sprawdza, czy transfer z Apollo z ilością WIĘKSZĄ niż prognozowana:
        1. Tworzy poprawną Partię Pierwotną (`Batches`) z rzeczywistą wagą.
        2. Tankuje tę partię do zbiornika docelowego.
        3. Tworzy wpis w AuditTrail o dokonanej korekcie bilansu Apollo.
        4. Poprawnie aktualizuje ApolloTracking.
        """
        # --- Przygotowanie (Arrange) ---
        prognozowana_ilosc = Decimal('100.00')
        mock_oblicz_stan.return_value = {
            'dostepne_kg': prognozowana_ilosc,
            'id_sesji': 1,
            'typ_surowca': 'T-SPECIAL'
        }

        czas_startu = datetime.now(timezone.utc) - timedelta(hours=1)
        sesja = ApolloSesje(id=1, id_sprzetu=TEST_APOLLO_ID, typ_surowca='T-SPECIAL', status_sesji='aktywna', czas_rozpoczecia=czas_startu)
        db.session.add(sesja)
        db.session.commit()

        rzeczywista_ilosc = Decimal('125.50')
        operator = 'TEST_USER'
        
        # --- Działanie (Act) ---
        result = BatchManagementService.create_batch_from_apollo_transfer(
            apollo_id=TEST_APOLLO_ID,
            destination_tank_id=TEST_TANK_ID,
            actual_quantity_transferred=rzeczywista_ilosc,
            operator=operator
        )
        
        # --- Asercje (Assert) ---
        
        # Asercja 1: Sprawdź zwrócone dane i informację o korekcie
        self.assertTrue(result['adjusted'])
        self.assertAlmostEqual(result['discrepancy'], Decimal('25.50'))

        # Asercja 2: Sprawdź, czy powstała nowa partia (`Batches`) i ma poprawną wagę
        new_batch = db.session.get(Batches, result['batch_id'])
        self.assertIsNotNone(new_batch)
        self.assertEqual(new_batch.source_type, 'APOLLO')
        self.assertEqual(new_batch.source_name, TEST_APOLLO_NAZWA)
        self.assertEqual(new_batch.material_type, 'T-SPECIAL')
        self.assertAlmostEqual(new_batch.initial_quantity, rzeczywista_ilosc)
        self.assertAlmostEqual(new_batch.current_quantity, Decimal('0.00')) # Powinna być od razu wyzerowana po tankowaniu

        # Asercja 3: Sprawdź, czy ta partia została zatankowana do zbiornika
        mix = db.session.get(TankMixes, result['mix_id'])
        self.assertIsNotNone(mix)
        self.assertEqual(len(mix.components), 1)
        self.assertAlmostEqual(mix.components[0].quantity_in_mix, rzeczywista_ilosc)

        # Asercja 4: Sprawdź, czy w AuditTrail jest odpowiedni wpis o korekcie
        audit_log = db.session.execute(select(AuditTrail)).scalar_one()
        self.assertEqual(audit_log.entity_type, 'ApolloSesje')
        self.assertEqual(audit_log.entity_id, sesja.id)
        self.assertEqual(audit_log.operation_type, 'BALANCE_CORRECTION')
        self.assertEqual(audit_log.old_value, str(prognozowana_ilosc))
        self.assertEqual(audit_log.new_value, str(rzeczywista_ilosc))
        
        # Asercja 5: Sprawdź, czy w ApolloTracking jest wpis o transferze
        tracking_log = db.session.execute(select(ApolloTracking)).scalar_one()
        self.assertEqual(tracking_log.id_sesji, sesja.id)
        self.assertEqual(tracking_log.typ_zdarzenia, 'TRANSFER_WYJSCIOWY')
        self.assertAlmostEqual(tracking_log.waga_kg, rzeczywista_ilosc)