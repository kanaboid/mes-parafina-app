# test_apollo_integration.py
import unittest
from datetime import datetime, timedelta
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
        # 1. Konfigurujemy mock, aby zwracał prognozowaną wartość 100 kg
        prognozowana_ilosc = 100.0
        mock_oblicz_stan.return_value = {'dostepne_kg': prognozowana_ilosc, 'id_sesji': 1, 'typ_surowca': 'T-SPECIAL'}

        # 2. Stwórz aktywną sesję w Apollo
        czas_startu = datetime.now() - timedelta(hours=1)
        sesja = ApolloSesje(id=1, id_sprzetu=TEST_APOLLO_ID, typ_surowca='T-SPECIAL', status_sesji='aktywna', czas_rozpoczecia=czas_startu)
        db.session.add(sesja)
        db.session.commit()

        # 3. Definiujemy rzeczywistą ilość, która została przelana
        rzeczywista_ilosc = Decimal('125.50')
        operator = 'TEST_USER'
        
        # --- Działanie (Act) ---
        # Wywołujemy metodę, która jeszcze nie istnieje
        result = BatchManagementService.create_batch_from_apollo_transfer(
            apollo_id=TEST_APOLLO_ID,
            destination_tank_id=TEST_TANK_ID,
            actual_quantity_transferred=rzeczywista_ilosc,
            operator=operator
        )
        
        # --- Asercje (Assert) ---
        # Na razie tylko jedna asercja, aby sprawdzić, czy metoda cokolwiek zwróciła
        self.assertIsNotNone(result)