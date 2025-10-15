# test_workflow_service.py
import unittest
from app import create_app, db
from app.config import TestConfig
from app.models import Sprzet, TankMixes, OperacjeLog
from app.workflow_service import WorkflowService
from sqlalchemy import select, text
from decimal import Decimal
from datetime import datetime, timezone, timedelta

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

    def _prepare_mix_for_bleaching(self, temp=Decimal('115.0'), status='PODGRZEWANY', is_wydmuch=False, initial_bags=0):
        # Ta funkcja pomocnicza pozostaje bez zmian
        reaktor = Sprzet(id=1, nazwa_unikalna='R1', typ_sprzetu='reaktor', temperatura_aktualna=temp)
        mix = TankMixes(id=10, tank=reaktor, unique_code='MIX-TEST', process_status=status,
                        bleaching_earth_bags_total=initial_bags, is_wydmuch_mix=is_wydmuch,
                        creation_date=datetime.now(timezone.utc) - timedelta(hours=1))
        reaktor.active_mix_id = mix.id
        db.session.add_all([reaktor, mix])
        db.session.commit()
        return mix

    def test_add_bleaching_earth_first_time_creates_new_log(self):
        """Testuje, czy pierwsze dobielanie tworzy nowy log i zmienia status."""
        mix = self._prepare_mix_for_bleaching(status='PODGRZEWANY')
        
        WorkflowService.add_bleaching_earth(mix.id, 4, Decimal('25.0'), 'USER1')

        db.session.refresh(mix)
        self.assertEqual(mix.process_status, 'DOBIELONY_OCZEKUJE')
        self.assertEqual(mix.bleaching_earth_bags_total, 4)
        
        logs = db.session.execute(select(OperacjeLog)).scalars().all()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].ilosc_workow, 4)
        self.assertAlmostEqual(logs[0].ilosc_kg, Decimal('100.0'))

    def test_add_bleaching_earth_second_time_updates_existing_log(self):
        """Testuje, czy drugie dobielanie aktualizuje istniejący log."""
        mix = self._prepare_mix_for_bleaching(status='DOBIELONY_OCZEKUJE', initial_bags=4)
        # Symulujemy istnienie poprzedniego logu
        initial_log = OperacjeLog(
            typ_operacji='DOBIELANIE', id_tank_mix=mix.id, status_operacji='zakonczona',
            czas_rozpoczecia=datetime.now(timezone.utc) - timedelta(minutes=10),
            ilosc_workow=4, ilosc_kg=Decimal('100.0')
        )
        db.session.add(initial_log)
        db.session.commit()
        
        WorkflowService.add_bleaching_earth(mix.id, 2, Decimal('25.0'), 'USER2')

        db.session.refresh(mix)
        self.assertEqual(mix.process_status, 'DOBIELONY_OCZEKUJE') # Status bez zmian
        self.assertEqual(mix.bleaching_earth_bags_total, 6) # Suma globalna 4 + 2

        logs = db.session.execute(select(OperacjeLog)).scalars().all()
        self.assertEqual(len(logs), 1) # Powinien być wciąż tylko JEDEN log
        self.assertEqual(logs[0].ilosc_workow, 6) # 4 + 2
        self.assertAlmostEqual(logs[0].ilosc_kg, Decimal('150.0')) # 100 + 50

    def test_add_bleaching_earth_exceeds_160kg_limit_in_one_op(self):
        """Testuje, czy przekroczenie limitu 160kg w jednej operacji jest blokowane."""
        mix = self._prepare_mix_for_bleaching(status='PODGRZEWANY')
    
        with self.assertRaisesRegex(ValueError, "przekracza maksymalny limit 160.0 kg"): # Poprawiony oczekiwany tekst
            WorkflowService.add_bleaching_earth(mix.id, 7, Decimal('25.0'), 'USER1') # 7 * 25 = 175 kg

    def test_add_bleaching_earth_exceeds_160kg_limit_in_second_op(self):
        """Testuje, czy przekroczenie limitu 160kg w drugiej 'dokładce' jest blokowane."""
        mix = self._prepare_mix_for_bleaching(status='DOBIELONY_OCZEKUJE', initial_bags=4)
        initial_log = OperacjeLog(typ_operacji='DOBIELANIE', id_tank_mix=mix.id, ilosc_workow=4, ilosc_kg=Decimal('100.0'), czas_rozpoczecia=datetime.now(timezone.utc)-timedelta(minutes=10))
        db.session.add(initial_log)
        db.session.commit()

        with self.assertRaisesRegex(ValueError, "przekroczy limit 160.0 kg"): # Poprawiony oczekiwany tekst
            # Próba dodania 3 worków (75kg), co da łącznie 175kg w tej operacji
            WorkflowService.add_bleaching_earth(mix.id, 3, Decimal('25.0'), 'USER2')

    def test_add_bleaching_earth_too_cold_fails(self):
        mix = self._prepare_mix_for_bleaching(temp=Decimal('105.0'))
        with self.assertRaisesRegex(ValueError, "Zbyt niska temperatura reaktora"):
            WorkflowService.add_bleaching_earth(mix.id, 5, Decimal('25.0'), 'TEST_USER')

    def test_add_bleaching_earth_to_wydmuch_mix_fails(self):
        mix = self._prepare_mix_for_bleaching(is_wydmuch=True)
        with self.assertRaisesRegex(ValueError, "Nie można dodawać ziemi bielącej"):
            WorkflowService.add_bleaching_earth(mix.id, 5, Decimal('25.0'), 'TEST_USER')