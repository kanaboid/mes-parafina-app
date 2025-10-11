# test_workflow_service.py
import unittest
from app import create_app, db
from app.config import TestConfig
from app.models import Sprzet, TankMixes, OperacjeLog
from app.workflow_service import WorkflowService
from sqlalchemy import select, text
from decimal import Decimal

class TestWorkflowService(unittest.TestCase):
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

    def _prepare_mix_for_assessment(self):
        """Helper to create a mix ready for assessment."""
        tank = Sprzet(id=201, nazwa_unikalna='R1', typ_sprzetu='reaktor')
        mix = TankMixes(
            id=10,
            tank_id=tank.id,
            unique_code='MIX-FOR-ASSESSMENT',
            process_status='OCZEKUJE_NA_OCENE'
        )
        db.session.add_all([tank, mix])
        db.session.commit()
        return mix

    def test_approve_mix_quality_success(self):
        """Testuje pomyślne zatwierdzenie jakości mieszaniny."""
        mix = self._prepare_mix_for_assessment()
        
        updated_mix = WorkflowService.assess_mix_quality(
            mix_id=mix.id,
            decision='OK',
            operator='TEST_USER'
        )

        self.assertEqual(updated_mix.process_status, 'ZATWIERDZONA')
        
        log = db.session.execute(select(OperacjeLog)).scalar_one()
        self.assertEqual(log.typ_operacji, 'OCENA_JAKOSCI')
        self.assertIn('POZYTYWNY', log.opis)
        self.assertEqual(log.zmodyfikowane_przez, 'TEST_USER')

    def test_reject_mix_quality_success(self):
        """Testuje pomyślne odrzucenie jakości mieszaniny z podaniem powodu."""
        mix = self._prepare_mix_for_assessment()
        
        updated_mix = WorkflowService.assess_mix_quality(
            mix_id=mix.id,
            decision='ZLA',
            operator='TEST_USER',
            reason='Zbyt ciemny kolor'
        )

        self.assertEqual(updated_mix.process_status, 'DO_PONOWNEJ_FILTRACJI')
        
        log = db.session.execute(select(OperacjeLog)).scalar_one()
        self.assertEqual(log.typ_operacji, 'OCENA_JAKOSCI')
        self.assertIn('NEGATYWNY', log.opis)
        self.assertIn('Zbyt ciemny kolor', log.opis)

    def test_reject_mix_quality_without_reason_fails(self):
        """Testuje, czy odrzucenie bez powodu rzuca błąd."""
        mix = self._prepare_mix_for_assessment()
        with self.assertRaisesRegex(ValueError, "Powód jest wymagany"):
            WorkflowService.assess_mix_quality(
                mix_id=mix.id,
                decision='ZLA',
                operator='TEST_USER'
            )

    def test_assess_mix_in_wrong_state_fails(self):
        """Testuje próbę oceny mieszaniny w niepoprawnym stanie."""
        mix = self._prepare_mix_for_assessment()
        mix.process_status = 'SUROWY'
        db.session.commit()
        
        with self.assertRaisesRegex(ValueError, "Nie można ocenić mieszaniny"):
            WorkflowService.assess_mix_quality(
                mix_id=mix.id,
                decision='OK',
                operator='TEST_USER'
            )

    def test_assess_nonexistent_mix_fails(self):
        """Testuje próbę oceny nieistniejącej mieszaniny."""
        with self.assertRaisesRegex(ValueError, "Mieszanina o ID 999 nie istnieje"):
            WorkflowService.assess_mix_quality(
                mix_id=999,
                decision='OK',
                operator='TEST_USER'
            )

    def test_assess_with_invalid_decision_fails(self):
        """Testuje próbę oceny z nieprawidłową decyzją."""
        mix = self._prepare_mix_for_assessment()
        with self.assertRaisesRegex(ValueError, "Nieznana decyzja"):
            WorkflowService.assess_mix_quality(
                mix_id=mix.id,
                decision='MOZE_BYC',
                operator='TEST_USER'
            )

    def _prepare_mix_for_bleaching(self, temp=Decimal('115.0')):
        """Helper to create a mix ready for bleaching."""
        reaktor = Sprzet(
            id=1, nazwa_unikalna='R1', typ_sprzetu='reaktor', 
            temperatura_aktualna=temp
        )
        mix = TankMixes(
            id=10, tank=reaktor, unique_code='MIX-FOR-BLEACHING',
            process_status='PODGRZEWANY', bleaching_earth_bags_total=0
        )
        reaktor.active_mix_id = mix.id
        db.session.add_all([reaktor, mix])
        db.session.commit()
        return mix

    def test_add_bleaching_earth_success(self):
        """Testuje pomyślne zarejestrowanie dodania ziemi bielącej."""
        mix = self._prepare_mix_for_bleaching()
        
        updated_mix = WorkflowService.add_bleaching_earth(
            mix_id=mix.id,
            bags_count=5,
            operator='TEST_USER'
        )

        self.assertEqual(updated_mix.process_status, 'DOBIELONY_OCZEKUJE')
        self.assertEqual(updated_mix.bleaching_earth_bags_total, 5)
        
        log = db.session.execute(select(OperacjeLog).where(OperacjeLog.typ_operacji == 'DOBIELANIE')).scalar_one()
        self.assertIsNotNone(log)
        self.assertIn("Dodano 5 worków", log.opis)

    def test_add_bleaching_earth_accumulates_bags(self):
        """Testuje, czy kolejne dobielanie akumuluje liczbę worków."""
        mix = self._prepare_mix_for_bleaching()
        mix.bleaching_earth_bags_total = 3 # Ustawiamy stan początkowy
        db.session.commit()
        
        updated_mix = WorkflowService.add_bleaching_earth(
            mix_id=mix.id,
            bags_count=4,
            operator='TEST_USER'
        )
        self.assertEqual(updated_mix.bleaching_earth_bags_total, 7) # 3 + 4

    def test_add_bleaching_earth_too_cold_fails(self):
        """Testuje, czy próba dobielania przy zbyt niskiej temperaturze rzuca błąd."""
        mix = self._prepare_mix_for_bleaching(temp=Decimal('105.0'))
        
        with self.assertRaisesRegex(ValueError, "Zbyt niska temperatura reaktora"):
            WorkflowService.add_bleaching_earth(
                mix_id=mix.id,
                bags_count=5,
                operator='TEST_USER'
            )

    def test_add_bleaching_earth_wrong_status_fails(self):
        """Testuje, czy próba dobielania mieszaniny w złym stanie rzuca błąd."""
        mix = self._prepare_mix_for_bleaching()
        mix.process_status = 'SUROWY'
        db.session.commit()

        with self.assertRaisesRegex(ValueError, "Nie można dobielić mieszaniny"):
            WorkflowService.add_bleaching_earth(
                mix_id=mix.id,
                bags_count=5,
                operator='TEST_USER'
            )