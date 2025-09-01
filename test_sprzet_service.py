# test_sprzet_service.py
import unittest
from decimal import Decimal
from app import create_app, db
from app.config import TestConfig
from app.models import Sprzet, TankMixes, Batches, MixComponents
from app.sprzet_service import SprzetService
from sqlalchemy import text

class TestSprzetService(unittest.TestCase):
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

    def test_01_start_heating_process_success(self):
        """
        Sprawdza, czy serwis poprawnie rozpoczyna proces podgrzewania.
        """
        # --- Przygotowanie (Arrange) ---
        # 1. Stwórz reaktor z zadaną prędkością grzania
        reaktor = Sprzet(
            id=1, nazwa_unikalna='R1', typ_sprzetu='reaktor', 
            szybkosc_grzania_c_na_minute=Decimal('0.5'),
            temperatura_docelowa=Decimal('120.0'),
            stan_palnika='WYLACZONY'
        )
        # 2. Stwórz w nim mieszaninę w stanie 'SUROWY'
        mix = TankMixes(id=10, tank_id=1, unique_code='MIX-TEST-HEAT', process_status='SUROWY')
        reaktor.active_mix_id = mix.id
        db.session.add_all([reaktor, mix])
        db.session.commit()
        
        start_temp = Decimal('75.0')

        # --- Działanie (Act) ---
        # Wywołujemy metodę, która jeszcze nie istnieje
        result = SprzetService.start_heating_process(
            sprzet_id=reaktor.id, 
            start_temperature=start_temp
        )

        # --- Asercje (Assert) ---
        # 1. Sprawdź, czy metoda zwróciła poprawnie obliczony czas
        self.assertIn('estimated_minutes_remaining', result)
        # Oczekiwany czas: (120 - 75) / 0.5 = 90 minut
        self.assertAlmostEqual(result['estimated_minutes_remaining'], 90.0)

        # 2. Odśwież obiekty z bazy, aby sprawdzić ich nowy stan
        db.session.refresh(reaktor)
        db.session.refresh(mix)

        # 3. Sprawdź, czy stan palnika został zmieniony
        self.assertEqual(reaktor.stan_palnika, 'WLACZONY')
        # 4. Sprawdź, czy temperatura startowa została ustawiona
        self.assertAlmostEqual(reaktor.temperatura_aktualna, start_temp)
        # 5. Sprawdź, czy status mieszaniny został zmieniony
        self.assertEqual(mix.process_status, 'PODGRZEWANY')