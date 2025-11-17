# test_workflow_service.py
import unittest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from app import create_app, db
from app.config import TestConfig
from app.models import Sprzet, Batches, TankMixes, MixComponents, OperacjeLog
from app.workflow_service import WorkflowService
from sqlalchemy import select, text

class TestWorkflowService(unittest.TestCase):
    def setUp(self):
        """Uruchamiane przed każdym testem, czyści bazę danych."""
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        with self.app.app_context():
            db.session.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            for table in reversed(db.metadata.sorted_tables):
                db.session.execute(text(f'TRUNCATE TABLE {table.name}'))
            db.session.execute(text("SET FOREIGN_KEY_CHECKS=1"))
            db.session.commit()
        self._setup_initial_data() # Używamy metody prywatnej

    def tearDown(self):
        """Uruchamiane po każdym teście."""
        db.session.remove()
        self.app_context.pop()

    def _setup_initial_data(self):
        """Tworzy dane początkowe dla testów."""
        # Sprzęt
        reactor1 = Sprzet(id=201, nazwa_unikalna='R1', typ_sprzetu='reaktor')
        tank1 = Sprzet(id=301, nazwa_unikalna='B01b', typ_sprzetu='beczka_brudna')
        db.session.add_all([reactor1, tank1])

        # Partie pierwotne
        batch1 = Batches(id=101, unique_code='S-C1-T10-251020-01', material_type='T10', source_type='CYS', source_name='C1', initial_quantity=1000, current_quantity=800)
        batch2 = Batches(id=102, unique_code='S-AP1-44-251020-01', material_type='44', source_type='APOLLO', source_name='AP1', initial_quantity=500, current_quantity=500)
        db.session.add_all([batch1, batch2])
        
        db.session.commit()

    # --- Testy dla nowej funkcji: load_batches_to_reactor ---

    def test_01_load_batches_to_empty_reactor_success(self):
        """Sprawdza pomyślne załadowanie partii do pustego reaktora."""
        # Arrange
        reactor_id = 201
        batches_to_load = [
            {'batch_id': 101, 'quantity_to_use': Decimal('150.5')},
            {'batch_id': 102, 'quantity_to_use': Decimal('100.0')}
        ]
        operator = 'TEST_USER'

        # Act
        result_mix, was_created = WorkflowService.load_batches_to_reactor(
            reactor_id=reactor_id,
            batches_to_load=batches_to_load,
            operator=operator
        )

        # Assert
        self.assertTrue(was_created)
        self.assertEqual(result_mix.process_status, 'SUROWY')
        self.assertTrue(result_mix.unique_code.startswith('P-R1-'))
        
        reactor = db.session.get(Sprzet, reactor_id)
        self.assertEqual(reactor.active_mix_id, result_mix.id)
        
        batch1 = db.session.get(Batches, 101)
        self.assertEqual(batch1.current_quantity, Decimal('649.5'))

    def test_02_load_batches_to_non_reactor_fails(self):
        """Testuje próbę załadowania do sprzętu, który nie jest reaktorem."""
        with self.assertRaises(ValueError) as context:
            WorkflowService.load_batches_to_reactor(
                reactor_id=301, # ID beczki
                batches_to_load=[{'batch_id': 101, 'quantity_to_use': 100}],
                operator='TEST_USER'
            )
        self.assertIn("nie jest reaktorem", str(context.exception))

    def test_03_load_batches_to_occupied_reactor_adds_components(self):
        """Testuje, czy załadowanie do zajętego reaktora (w stanie SUROWY) dodaje składniki."""
        # Arrange
        initial_load = [{'batch_id': 101, 'quantity_to_use': Decimal('100.0')}]
        initial_mix, _ = WorkflowService.load_batches_to_reactor(
            reactor_id=201, batches_to_load=initial_load, operator='USER_A'
        )

        # Act
        second_load = [{'batch_id': 102, 'quantity_to_use': Decimal('50.0')}]
        updated_mix, was_created = WorkflowService.load_batches_to_reactor(
            reactor_id=201, batches_to_load=second_load, operator='USER_B'
        )

        # Assert
        self.assertFalse(was_created)
        self.assertEqual(updated_mix.id, initial_mix.id)
        self.assertEqual(len(updated_mix.components), 2)
        total_weight = sum(c.quantity_in_mix for c in updated_mix.components)
        self.assertEqual(total_weight, Decimal('150.0'))

    def test_04_load_batches_to_occupied_reactor_with_wrong_status_fails(self):
        """Testuje próbę dodania partii do mieszaniny w nieprawidłowym stanie."""
        # Arrange
        initial_load = [{'batch_id': 101, 'quantity_to_use': Decimal('100.0')}]
        initial_mix, _ = WorkflowService.load_batches_to_reactor(
            reactor_id=201, batches_to_load=initial_load, operator='USER_A'
        )
        initial_mix.process_status = 'PODGRZEWANY'
        db.session.commit()

        # Act & Assert
        with self.assertRaisesRegex(ValueError, "Mieszanina nie jest w stanie 'SUROWY'"):
            WorkflowService.load_batches_to_reactor(
                reactor_id=201,
                batches_to_load=[{'batch_id': 102, 'quantity_to_use': 50}],
                operator='USER_B'
            )

    def test_05_load_with_insufficient_quantity_fails(self):
        """Testuje próbę użycia większej ilości surowca niż dostępna."""
        with self.assertRaisesRegex(ValueError, "Niewystarczająca ilość"):
            WorkflowService.load_batches_to_reactor(
                reactor_id=201,
                batches_to_load=[{'batch_id': 101, 'quantity_to_use': 9999}],
                operator='TEST_USER'
            )
        
    def test_06_load_with_nonexistent_batch_fails(self):
        """Testuje próbę użycia nieistniejącej partii."""
        with self.assertRaisesRegex(ValueError, "nie została znaleziona"):
            WorkflowService.load_batches_to_reactor(
                reactor_id=201,
                batches_to_load=[{'batch_id': 999, 'quantity_to_use': 100}],
                operator='TEST_USER'
            )

    # --- Istniejące testy z Twojego pliku ---
    
    def _prepare_mix_for_assessment(self):
        reaktor = db.session.get(Sprzet, 201)
        mix = TankMixes(id=10, tank_id=reaktor.id, unique_code='MIX-TEST-ASSESS', process_status='OCZEKUJE_NA_OCENE')
        reaktor.active_mix_id = mix.id
        db.session.add(mix)
        db.session.commit()
        return mix

    def test_assess_mix_ok_success(self):
        """Testuje pomyślne zatwierdzenie jakości mieszaniny."""
        mix = self._prepare_mix_for_assessment()
        updated_mix = WorkflowService.assess_mix_quality(mix_id=mix.id, decision='OK', operator='TEST_USER')
        self.assertEqual(updated_mix.process_status, 'ZATWIERDZONA')
        log = db.session.execute(select(OperacjeLog)).scalar_one()
        self.assertEqual(log.typ_operacji, 'OCENA_JAKOSCI')
        self.assertIn('POZYTYWNY', log.opis)
        self.assertEqual(log.zmodyfikowane_przez, 'TEST_USER')

    def test_reject_mix_quality_success(self):
        """Testuje pomyślne odrzucenie jakości mieszaniny z podaniem powodu."""
        mix = self._prepare_mix_for_assessment()
        updated_mix = WorkflowService.assess_mix_quality(mix.id, 'ZLA', 'TEST_USER', 'Zbyt ciemny kolor')
        self.assertEqual(updated_mix.process_status, 'DO_PONOWNEJ_FILTRACJI')
        log = db.session.execute(select(OperacjeLog)).scalar_one()
        self.assertIn('NEGATYWNY', log.opis)
        self.assertIn('Zbyt ciemny kolor', log.opis)
    
    def _prepare_mix_for_bleaching(self, temp=Decimal('115.0'), status='PODGRZEWANY', is_wydmuch=False, initial_bags=0):
        reaktor = db.session.get(Sprzet, 201)
        reaktor.temperatura_aktualna = temp
        mix = TankMixes(id=10, tank=reaktor, unique_code='MIX-TEST-BLEACH',
                        process_status=status, bleaching_earth_bags_total=initial_bags,
                        is_wydmuch_mix=is_wydmuch)
        reaktor.active_mix_id = mix.id
        db.session.add(mix)
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

    def test_add_bleaching_earth_second_time_updates_existing_log(self):
        """Testuje, czy drugie dobielenie aktualizuje istniejący log."""
        mix = self._prepare_mix_for_bleaching(status='DOBIELONY_OCZEKUJE', initial_bags=4)
        initial_log = OperacjeLog(
            typ_operacji='DOBIELANIE', id_tank_mix=mix.id, status_operacji='zakonczona',
            czas_rozpoczecia=datetime.now(timezone.utc)-timedelta(minutes=10),
            ilosc_workow=4, ilosc_kg=Decimal('100.0')
        )
        db.session.add(initial_log)
        db.session.commit()
        WorkflowService.add_bleaching_earth(mix.id, 2, Decimal('25.0'), 'USER2')
        db.session.refresh(mix)
        self.assertEqual(mix.bleaching_earth_bags_total, 6)
        logs = db.session.execute(select(OperacjeLog)).scalars().all()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].ilosc_workow, 6)
        self.assertAlmostEqual(logs[0].ilosc_kg, Decimal('150.0'))

    def test_add_bleaching_earth_exceeds_160kg_limit_in_one_op(self):
        """Testuje blokadę przekroczenia limitu 160kg w jednej operacji."""
        mix = self._prepare_mix_for_bleaching(status='PODGRZEWANY')
        with self.assertRaisesRegex(ValueError, "przekracza maksymalny limit 160.0 kg"):
            WorkflowService.add_bleaching_earth(mix.id, 7, Decimal('25.0'), 'USER1')

    def test_add_bleaching_earth_exceeds_160kg_limit_in_second_op(self):
        """Testuje blokadę przekroczenia limitu 160kg w drugiej 'dokładce'."""
        mix = self._prepare_mix_for_bleaching(status='DOBIELONY_OCZEKUJE', initial_bags=4)
        initial_log = OperacjeLog(typ_operacji='DOBIELANIE', id_tank_mix=mix.id, ilosc_workow=4, ilosc_kg=Decimal('100.0'), czas_rozpoczecia=datetime.now(timezone.utc)-timedelta(minutes=10))
        db.session.add(initial_log)
        db.session.commit()
        with self.assertRaisesRegex(ValueError, "przekroczy limit 160.0 kg"):
            WorkflowService.add_bleaching_earth(mix.id, 3, Decimal('25.0'), 'USER2')

    def test_add_bleaching_earth_too_cold_fails(self):
        """Testuje blokadę dobielania przy zbyt niskiej temperaturze."""
        mix = self._prepare_mix_for_bleaching(temp=Decimal('105.0'))
        with self.assertRaisesRegex(ValueError, "Zbyt niska temperatura reaktora"):
            WorkflowService.add_bleaching_earth(mix.id, 5, Decimal('25.0'), 'TEST_USER')

    def test_add_bleaching_earth_to_wydmuch_mix_fails(self):
        """Testuje blokadę dobielania dla mieszaniny typu 'wydmuch'."""
        mix = self._prepare_mix_for_bleaching(is_wydmuch=True)
        with self.assertRaisesRegex(ValueError, "Nie można dodawać ziemi bielącej"):
            WorkflowService.add_bleaching_earth(mix.id, 5, Decimal('25.0'), 'TEST_USER')