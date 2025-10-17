# test_heating_service.py
import unittest
from decimal import Decimal
from app import create_app, db
from app.config import TestConfig
from app.models import Sprzet, TankMixes, MixComponents, HistoriaPodgrzewania
from app.sprzet_service import SprzetService
from sqlalchemy import select, text

class TestHeatingService(unittest.TestCase):
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

    def test_heating_cycle_is_logged_correctly(self):
        """
        Sprawdza pełny cykl: włączenie palnika tworzy log, wyłączenie go zamyka.
        """
        # --- Przygotowanie (Arrange) ---
        reaktor = Sprzet(
            id=1, nazwa_unikalna='R1', typ_sprzetu='reaktor', 
            stan_palnika='WYLACZONY', temperatura_aktualna=Decimal('25.0')
        )
        mix = TankMixes(id=10, tank_id=1, unique_code='MIX-LOG-TEST', process_status='SUROWY')
        reaktor.active_mix_id = mix.id
        # Dodajmy składnik, aby waga wsadu była > 0
        comp = MixComponents(mix_id=mix.id, batch_id=1, quantity_in_mix=Decimal('5000.0'))
        # Musimy stworzyć atrapę partii, inaczej klucz obcy zawiedzie
        from app.models import Batches
        batch = Batches(id=1, unique_code='dummy', material_type='dummy', source_type='CYS', source_name='dummy', initial_quantity=5000, current_quantity=5000)

        db.session.add_all([reaktor, mix, batch, comp])
        db.session.commit()

        # --- Działanie 1: Włącz palnik ---
        SprzetService.set_burner_status(sprzet_id=reaktor.id, status='WLACZONY')

        # --- Asercje 1 ---
        log_entry = db.session.execute(select(HistoriaPodgrzewania)).scalar_one()
        self.assertIsNotNone(log_entry)
        self.assertEqual(log_entry.id_sprzetu, reaktor.id)
        self.assertEqual(log_entry.id_mieszaniny, mix.id)
        self.assertAlmostEqual(log_entry.temp_startowa, Decimal('25.0'))
        self.assertAlmostEqual(log_entry.waga_wsadu, Decimal('5000.0'))
        self.assertIsNone(log_entry.czas_konca) # Kluczowe - cykl jest otwarty

        # --- Działanie 2: Zaktualizuj temperaturę i wyłącz palnik ---
        reaktor.temperatura_aktualna = Decimal('115.0')
        db.session.commit()
        SprzetService.set_burner_status(sprzet_id=reaktor.id, status='WYLACZONY')

        # --- Asercje 2 ---
        db.session.refresh(log_entry)
        self.assertIsNotNone(log_entry.czas_konca)
        self.assertAlmostEqual(log_entry.temp_koncowa, Decimal('115.0'))