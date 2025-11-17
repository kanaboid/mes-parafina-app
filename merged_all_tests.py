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
# test_apollo_service.py
import unittest
from datetime import datetime, timedelta
from datetime import timezone

from app import create_app, db
from app.config import TestConfig
from app.apollo_service import ApolloService
from app.models import Sprzet, PartieApollo, ApolloSesje, ApolloTracking, OperacjeLog
from sqlalchemy import text, select

TEST_APOLLO_ID = 999
TEST_APOLLO_NAZWA = 'AP999'

def _as_aware_utc(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

class TestApolloService(unittest.TestCase):
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
            db.session.add(sprzet_apollo)
            db.session.commit()

    def tearDown(self):
        db.session.remove()
        self.app_context.pop()

    # Testy 1-11 pozostają bez zmian
    def test_01_rozpocznij_sesje_sukces(self):
        id_sesji = ApolloService.rozpocznij_sesje_apollo(TEST_APOLLO_ID, 'TEST-SUROWIEC', 500.0)
        sesja_db = db.session.get(ApolloSesje, id_sesji)
        self.assertEqual(sesja_db.status_sesji, 'aktywna')

    def test_02_rozpocznij_sesje_gdy_juz_aktywna(self):
        ApolloService.rozpocznij_sesje_apollo(TEST_APOLLO_ID, 'TYP1', 100)
        with self.assertRaises(ValueError):
            ApolloService.rozpocznij_sesje_apollo(TEST_APOLLO_ID, 'TYP2', 200)

    def test_03_dodaj_surowiec_do_aktywnej_sesji(self):
        ApolloService.rozpocznij_sesje_apollo(TEST_APOLLO_ID, 'TEST-SUROWIEC', 500.0)
        ApolloService.dodaj_surowiec_do_apollo(TEST_APOLLO_ID, 250.0)
        partia_db = db.session.execute(select(PartieApollo).where(PartieApollo.id_sprzetu == TEST_APOLLO_ID)).scalar_one()
        self.assertAlmostEqual(float(partia_db.waga_aktualna_kg), 750.0)

    def test_04_zakoncz_sesje(self):
        id_sesji = ApolloService.rozpocznij_sesje_apollo(TEST_APOLLO_ID, 'TEST-SUROWIEC', 500)
        ApolloService.zakoncz_sesje_apollo(TEST_APOLLO_ID)
        sesja_db = db.session.get(ApolloSesje, id_sesji)
        self.assertEqual(sesja_db.status_sesji, 'zakonczona')

    def test_05_oblicz_stan_prosty_przypadek(self):
        czas_teraz = datetime(2025, 1, 1, 12, 0, 36)
        czas_startu = datetime(2025, 1, 1, 12, 0, 0)
        ApolloService.rozpocznij_sesje_apollo(TEST_APOLLO_ID, 'TEST-SUROWIEC', 2000.0, event_time=czas_startu)
        stan = ApolloService.oblicz_aktualny_stan_apollo(TEST_APOLLO_ID, current_time=czas_teraz)
        self.assertAlmostEqual(stan['dostepne_kg'], 10.0, delta=0.1)

    def test_06_oblicz_stan_z_limitem_surowca(self):
        waga_startowa = 5.0
        czas_teraz = datetime(2025, 1, 1, 13, 0, 0)
        czas_startu = datetime(2025, 1, 1, 12, 0, 0)
        ApolloService.rozpocznij_sesje_apollo(TEST_APOLLO_ID, 'TEST-SUROWIEC', waga_startowa, event_time=czas_startu)
        stan = ApolloService.oblicz_aktualny_stan_apollo(TEST_APOLLO_ID, current_time=czas_teraz)
        self.assertAlmostEqual(stan['dostepne_kg'], waga_startowa, delta=0.1)

    def test_07_oblicz_stan_po_korekcie_recznej(self):
        teraz = _as_aware_utc(datetime(2025, 1, 1, 12, 0, 0))
        
        ApolloService.rozpocznij_sesje_apollo(TEST_APOLLO_ID, 'TEST-SUROWIEC', 1000, event_time=teraz - timedelta(minutes=20))
        ApolloService.koryguj_stan_apollo(TEST_APOLLO_ID, 150.0, event_time=teraz - timedelta(minutes=10))
        ApolloService.dodaj_surowiec_do_apollo(TEST_APOLLO_ID, 50.0, event_time=teraz - timedelta(minutes=5))
        
        stan = ApolloService.oblicz_aktualny_stan_apollo(TEST_APOLLO_ID, current_time=teraz)
        
        self.assertAlmostEqual(stan['dostepne_kg'], 200.0, places=2)

    def test_08_zakoncz_sesje_sukces(self):
        id_sesji = ApolloService.rozpocznij_sesje_apollo(TEST_APOLLO_ID, 'TEST-ZAKONCZENIE', 1000)
        partia_przed = db.session.execute(select(PartieApollo).filter_by(id_sprzetu=TEST_APOLLO_ID)).scalar_one()
        ApolloService.zakoncz_sesje_apollo(TEST_APOLLO_ID)
        db.session.refresh(partia_przed)
        sesja_po = db.session.get(ApolloSesje, id_sesji)
        self.assertEqual(sesja_po.status_sesji, 'zakonczona')
        self.assertEqual(partia_przed.status_partii, 'Archiwalna')

    def test_09_zakoncz_sesje_gdy_brak_aktywnej(self):
        with self.assertRaises(ValueError):
            ApolloService.zakoncz_sesje_apollo(TEST_APOLLO_ID)

    def test_10_zakoncz_sesje_bez_powiazanej_partii(self):
        sesja = ApolloSesje(
            id_sprzetu=TEST_APOLLO_ID, typ_surowca='TYP_TESTOWY',
            status_sesji='aktywna', czas_rozpoczecia=datetime.now(timezone.utc)
        )
        db.session.add(sesja)
        db.session.commit()
        ApolloService.zakoncz_sesje_apollo(TEST_APOLLO_ID)
        self.assertEqual(sesja.status_sesji, 'zakonczona')

    def test_11_get_stan_apollo_brak_sesji(self):
        stan = ApolloService.get_stan_apollo(TEST_APOLLO_ID)
        self.assertFalse(stan['aktywna_sesja'])

    # --- Poprawione testy 12 i 13 ---
    def test_12_get_stan_apollo_aktywna_sesja_bez_transferow(self):
        czas_teraz = _as_aware_utc(datetime.now())
        czas_startu_sesji = czas_teraz - timedelta(minutes=6)
        sesja = ApolloSesje(id_sprzetu=TEST_APOLLO_ID, typ_surowca='T-STAN', status_sesji='aktywna', czas_rozpoczecia=czas_startu_sesji)
        db.session.add(sesja)
        db.session.commit()
        
        tracking = ApolloTracking(id_sesji=sesja.id, typ_zdarzenia='DODANIE_SUROWCA', waga_kg=500, czas_zdarzenia=czas_startu_sesji)
        db.session.add(tracking)
        
        sprzet = db.session.get(Sprzet, TEST_APOLLO_ID)
        sprzet.szybkosc_topnienia_kg_h = 1000.0
        db.session.commit()
        
        stan = ApolloService.get_stan_apollo(TEST_APOLLO_ID, current_time=czas_teraz)
        self.assertTrue(stan['aktywna_sesja'])
        self.assertAlmostEqual(stan['bilans_sesji_kg'], 500.0)
        self.assertAlmostEqual(stan['dostepne_kg'], 100.0, delta=1.0)

    def test_13_get_stan_apollo_z_transferem(self):
        czas_teraz = _as_aware_utc(datetime.now())
        czas_startu_sesji = czas_teraz - timedelta(minutes=30)
        sesja = ApolloSesje(id_sprzetu=TEST_APOLLO_ID, typ_surowca='T-STAN-TR', status_sesji='aktywna', czas_rozpoczecia=czas_startu_sesji)
        db.session.add(sesja)
        db.session.commit()

        tracking_dodanie = ApolloTracking(id_sesji=sesja.id, typ_zdarzenia='DODANIE_SUROWCA', waga_kg=1000, czas_zdarzenia=czas_startu_sesji)
        
        czas_transferu = _as_aware_utc(datetime.now()) - timedelta(minutes=12)
        tracking_transfer = ApolloTracking(id_sesji=sesja.id, typ_zdarzenia='TRANSFER_WYJSCIOWY', waga_kg=200, czas_zdarzenia=czas_transferu)
        
        db.session.add_all([tracking_dodanie, tracking_transfer])
        db.session.commit() # <-- Ważne, aby zapisać dane PRZED wywołaniem serwisu
        
        sprzet = db.session.get(Sprzet, TEST_APOLLO_ID)
        sprzet.szybkosc_topnienia_kg_h = 1000.0
        db.session.commit()
        
        stan = ApolloService.get_stan_apollo(TEST_APOLLO_ID, current_time=czas_teraz)
        self.assertTrue(stan['aktywna_sesja'])
        self.assertAlmostEqual(stan['bilans_sesji_kg'], 800.0) # 1000 - 200
        
        # Oczekiwany wytop: w 30 minut stopiło się 500 kg. Po transferze 200kg, zostało 300kg.
        self.assertAlmostEqual(stan['dostepne_kg'], 300.0, delta=1.0)

    def test_14_oblicz_stan_po_czesciowym_transferze_i_doladowaniu(self):
        """
        Sprawdza poprawność obliczeń w scenariuszu:
        1. Start sesji.
        2. Częściowy transfer (mniej niż się stopiło).
        3. Dodanie nowego surowca.
        4. Finalny odczyt stanu.
        System powinien poprawnie obliczyć, że część płynnego surowca
        pozostała po transferze i kontynuować topienie nowego wsadu.
        """
        # --- Przygotowanie (Arrange) ---
        # Używamy konkretnych, łatwych do weryfikacji punktów w czasie
        czas_startu_sesji = datetime(2025, 8, 1, 12, 0, 0)
        czas_transferu = datetime(2025, 8, 1, 12, 30, 0)
        czas_dodania_surowca = datetime(2025, 8, 1, 13, 0, 0)
        czas_finalnego_odczytu = datetime(2025, 8, 1, 13, 15, 0)

        # 1. Rozpocznij sesję z 500 kg surowca o 12:00
        sesja_id = ApolloService.rozpocznij_sesje_apollo(
            TEST_APOLLO_ID, 'TEST-CZESCIOWY', 500.0, event_time=czas_startu_sesji
        )
        sesja = db.session.get(ApolloSesje, sesja_id)

        # 2. Dokonaj transferu 200 kg o 12:30
        # W tym momencie stopiło się 0.5h * 1000kg/h = 500 kg. Dostępne jest 500 kg.
        # Po transferze powinno zostać 300 kg płynnego surowca.
        operacja = OperacjeLog(
            typ_operacji='TRANSFER', id_apollo_sesji=sesja.id, status_operacji='zakonczona',
            ilosc_kg=200.0, czas_rozpoczecia=czas_transferu, czas_zakonczenia=czas_transferu
        )
        # UWAGA: Nowa logika będzie wymagała wpisu w ApolloTracking, dodajmy go od razu
        tracking_transfer = ApolloTracking(
            id_sesji=sesja.id, typ_zdarzenia='TRANSFER_WYJSCIOWY', waga_kg=200.0,
            czas_zdarzenia=czas_transferu
        )

        # 3. Dodaj 400 kg surowca o 13:00
        ApolloService.dodaj_surowiec_do_apollo(TEST_APOLLO_ID, 400.0, event_time=czas_dodania_surowca)
        
        db.session.add_all([operacja, tracking_transfer])
        db.session.commit()
        
        # --- Działanie (Act) ---
        # Odczytaj stan o 13:15
        # Oczekiwana logika:
        # - O 13:00 w Apollo było 300 kg płynu i 400 kg granulatu.
        # - Przez 15 minut (0.25h) stopiło się 0.25 * 1000 = 250 kg granulatu.
        # - Finalny stan: 300 kg (stary płyn) + 250 kg (nowy płyn) = 550 kg płynu.
        stan = ApolloService.oblicz_aktualny_stan_apollo(TEST_APOLLO_ID, current_time=czas_finalnego_odczytu)
        
        # --- Asercja (Assert) ---
        self.assertAlmostEqual(stan['dostepne_kg'], 550.0, places=2)

if __name__ == '__main__':
    unittest.main()
# test_batch_management.py
import unittest
from datetime import datetime as dt
from datetime import timezone
from decimal import Decimal

from app import create_app, db
from app.config import TestConfig
from app.models import Sprzet, Batches, TankMixes, MixComponents, AuditTrail
from sqlalchemy import select, text
import pytz
# Zakładamy, że ten plik będzie istniał
from app.batch_management_service import BatchManagementService

WARSAW_TZ = pytz.timezone('Europe/Warsaw')

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
        now_utc = dt.now(timezone.utc)
        now_warsaw = now_utc.astimezone(WARSAW_TZ)
        # 3. Użyj czasu lokalnego do sformatowania stringa
        today_str = now_warsaw.strftime('%y%m%d')
        
        
        print(today_str)
        expected_prefix = f"S-{source_name}-{material_type}-{today_str}"
        print(expected_prefix)
        print(result['unique_code'])
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
# test_operations_routes.py
import unittest
import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

# Importy z aplikacji
from app import create_app, db
from app.config import TestConfig
from app.models import Sprzet, PartieApollo, PortySprzetu, Segmenty, Zawory, OperacjeLog
from sqlalchemy import text, select

class TestOperationsRoutes(unittest.TestCase):
    def setUp(self):
        """Uruchamiane przed każdym testem."""
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()

        # Spójne i niezawodne czyszczenie bazy danych
        with self.app.app_context():
            db.session.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            for table in reversed(db.metadata.sorted_tables):
                db.session.execute(text(f'TRUNCATE TABLE {table.name}'))
            db.session.execute(text("SET FOREIGN_KEY_CHECKS=1"))
            db.session.commit()

    def tearDown(self):
        """Uruchamiane po każdym teście."""
        db.session.remove()
        self.app_context.pop()

    # --- Testy dla /api/operations/aktywne ---

    def test_01_get_aktywne_operacje_gdy_pusto(self):
        """Sprawdza, czy GET /aktywne zwraca pustą listę, gdy brak operacji."""
        # --- Działanie (Act) ---
        response = self.client.get('/api/operations/aktywne')
        
        # --- Asercje (Assert) ---
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])

    def test_02_get_aktywne_operacje_zwraca_tylko_aktywne(self):
        """Sprawdza, czy GET /aktywne zwraca tylko operacje ze statusem 'aktywna'."""
        # --- Przygotowanie (Arrange) ---
        aktywna = OperacjeLog(typ_operacji='AKTYWNA', status_operacji='aktywna', czas_rozpoczecia=datetime.now(timezone.utc), opis='Test Op')
        zakonczona = OperacjeLog(typ_operacji='ZAKONCZONA', status_operacji='zakonczona', czas_rozpoczecia=datetime.now(timezone.utc))
        db.session.add_all([aktywna, zakonczona])
        db.session.commit()

        # --- Działanie (Act) ---
        response = self.client.get('/api/operations/aktywne')
        data = response.get_json()

        # --- Asercje (Assert) ---
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['typ_operacji'], 'AKTYWNA')

    # --- Testy dla /api/operations/rozpocznij_trase ---

    @patch('app.operations_routes.get_pathfinder')
    def test_03_rozpocznij_trase_sukces(self, mock_get_pathfinder):
        """
        Sprawdza, czy POST /rozpocznij_trase poprawnie tworzy operację,
        gdy PathFinder znajduje trasę.
        """
        # --- Przygotowanie (Arrange) ---
        # 1. Konfiguracja mocka PathFinder
        mock_pathfinder = MagicMock()
        mock_pathfinder.find_path.return_value = ['SEGMENT-A', 'SEGMENT-B']
        mock_get_pathfinder.return_value = mock_pathfinder

        # 2. Przygotowanie danych w bazie
        reaktor_start = Sprzet(id=1, nazwa_unikalna='R01')
        port_start = PortySprzetu(id=10, id_sprzetu=1, nazwa_portu='R01_OUT', typ_portu='OUT')
        
        # POPRAWKA: Uzupełniamy obiekt PartiaSurowca o wszystkie wymagane pola
        partia = PartieApollo(
            id=50, 
            id_sprzetu=1, 
            unikalny_kod='PARTIA-TEST-1', 
            nazwa_partii='Partia Test 1',
            zrodlo_pochodzenia='cysterna', # Wymagane
            waga_poczatkowa_kg=5000,      # Wymagane
            waga_aktualna_kg=5000,
            status_partii='Wytapiany'   # Wymagane
        )

        zawor1 = Zawory(id=100, nazwa_zaworu='V1', stan='ZAMKNIETY')
        segment1 = Segmenty(id=1000, nazwa_segmentu='SEGMENT-A', id_zaworu=100)
        segment2 = Segmenty(id=1001, nazwa_segmentu='SEGMENT-B', id_zaworu=100)
        db.session.add_all([reaktor_start, port_start, partia, zawor1, segment1, segment2])
        db.session.commit()

        # 3. Przygotowanie danych żądania (bez zmian)
        dane_trasy = {
            "start": "R01_OUT",
            "cel": "R02_IN",
            "otwarte_zawory": ["V1"],
            "typ_operacji": "TEST_TRANSFER"
        }

        # --- Działanie (Act) ---
        response = self.client.post(
            '/api/operations/rozpocznij_trase',
            data=json.dumps(dane_trasy),
            content_type='application/json'
        )

        # --- Asercje (Assert) ---
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertEqual(data['status'], 'success')
        
        operacja = db.session.get(OperacjeLog, data['id_operacji'])
        self.assertIsNotNone(operacja)
        self.assertEqual(operacja.status_operacji, 'aktywna')
        self.assertEqual(operacja.id_partii_surowca, 50)
        
        segmenty_zablokowane_q = db.session.execute(
            text("SELECT COUNT(*) FROM log_uzyte_segmenty WHERE id_operacji_log = :id_op"),
            {'id_op': data['id_operacji']}
        ).scalar()
        self.assertEqual(segmenty_zablokowane_q, 2)

        zawor_po = db.session.get(Zawory, 100)
        self.assertEqual(zawor_po.stan, 'OTWARTY')

    def test_04_zakoncz_operacje_sukces(self):
        """
        Sprawdza, czy POST /zakoncz poprawnie kończy operację,
        zwalnia zasoby i aktualizuje stany.
        """
        # --- Przygotowanie (Arrange) ---
        # 1. Tworzymy scenariusz: aktywna operacja transferu z R01 do R02
        zrodlo = Sprzet(id=1, nazwa_unikalna='R01', stan_sprzetu='W transferze')
        cel = Sprzet(id=2, nazwa_unikalna='R02', stan_sprzetu='W transferze')
        port_zrodlowy = PortySprzetu(id_sprzetu=1, nazwa_portu='R01_OUT', typ_portu='OUT')
        port_docelowy = PortySprzetu(id_sprzetu=2, nazwa_portu='R02_IN', typ_portu='IN')
        partia = PartieApollo(
            id=50, id_sprzetu=1, unikalny_kod='PARTIA-DO-ZAKONCZENIA', nazwa_partii='P-TEST',
            zrodlo_pochodzenia='cysterna', waga_poczatkowa_kg=1000, waga_aktualna_kg=1000,
            status_partii='Wytapiany'
        )
        operacja = OperacjeLog(
            id=123, typ_operacji='TRANSFER', status_operacji='aktywna',
            id_partii_surowca=50, id_sprzetu_zrodlowego=1, id_sprzetu_docelowego=2,
            punkt_startowy='R01_OUT', punkt_docelowy='R02_IN',
            czas_rozpoczecia=datetime.now(timezone.utc)
        )
        zawor = Zawory(id=100, nazwa_zaworu='V-ZAKONCZ', stan='OTWARTY')
        segment = Segmenty(id=1000, nazwa_segmentu='SEG-ZAKONCZ', id_zaworu=100)
        
        db.session.add_all([zrodlo, cel, port_zrodlowy, port_docelowy, partia, operacja, zawor, segment])
        db.session.commit()

        # Ręcznie tworzymy blokadę segmentu (łączymy operację z segmentem)
        db.session.execute(
            text("INSERT INTO log_uzyte_segmenty (id_operacji_log, id_segmentu) VALUES (123, 1000)")
        )
        db.session.commit()

        # 2. Dane żądania
        dane_zakonczenia = {'id_operacji': 123}

        # --- Działanie (Act) ---
        response = self.client.post(
            '/api/operations/zakoncz',
            data=json.dumps(dane_zakonczenia),
            content_type='application/json'
        )

        # --- Asercje (Assert) ---
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('V-ZAKONCZ', data['zamkniete_zawory'])

        # Sprawdzenie stanu bazy danych po operacji
        operacja_po = db.session.get(OperacjeLog, 123)
        self.assertEqual(operacja_po.status_operacji, 'zakonczona')
        
        zawor_po = db.session.get(Zawory, 100)
        self.assertEqual(zawor_po.stan, 'ZAMKNIETY')

        partia_po = db.session.get(PartieApollo, 50)
        self.assertEqual(partia_po.id_sprzetu, 2) # Sprawdź, czy partia została przeniesiona do celu

        zrodlo_po = db.session.get(Sprzet, 1)
        self.assertEqual(zrodlo_po.stan_sprzetu, 'Pusty')
        
        cel_po = db.session.get(Sprzet, 2)
        self.assertEqual(cel_po.stan_sprzetu, 'Zatankowany')

if __name__ == '__main__':
    unittest.main()
# test_pathfinder_service.py
import unittest
from app import create_app, db
from app.config import TestConfig
from app.models import Sprzet, PortySprzetu, WezlyRurociagu, Zawory, Segmenty
from app.pathfinder_service import PathFinder
from sqlalchemy import text

class TestPathFinderService(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # Czysta baza danych przed każdym testem
        with self.app.app_context():
            db.session.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            for table in reversed(db.metadata.sorted_tables):
                db.session.execute(text(f'TRUNCATE TABLE {table.name}'))
            db.session.execute(text("SET FOREIGN_KEY_CHECKS=1"))
            db.session.commit()
            
            # Stworzenie prostej, ale kompletnej topologii do testów
            self._create_test_topology()

        # Inicjalizacja PathFinder w kontekście aplikacji testowej
        self.pathfinder = PathFinder(self.app)

    def tearDown(self):
        db.session.remove()
        self.app_context.pop()

    def _create_test_topology(self):
        """Tworzy spójną topologię w testowej bazie danych."""
        # Sprzęt
        r01 = Sprzet(id=1, nazwa_unikalna='R01', typ_sprzetu='reaktor')
        r02 = Sprzet(id=2, nazwa_unikalna='R02', typ_sprzetu='reaktor')
        fz1 = Sprzet(id=3, nazwa_unikalna='FZ1', typ_sprzetu='filtr')
        
        # Porty
        p_r01_out = PortySprzetu(id=10, id_sprzetu=1, nazwa_portu='R01_OUT', typ_portu='OUT')
        p_r02_in = PortySprzetu(id=20, id_sprzetu=2, nazwa_portu='R02_IN', typ_portu='IN')
        p_fz1_in = PortySprzetu(id=30, id_sprzetu=3, nazwa_portu='FZ1_IN', typ_portu='IN')
        p_fz1_out = PortySprzetu(id=31, id_sprzetu=3, nazwa_portu='FZ1_OUT', typ_portu='OUT')
        
        # Węzły
        w1 = WezlyRurociagu(id=100, nazwa_wezla='W1')
        
        # Zawory
        v1 = Zawory(id=101, nazwa_zaworu='V1', stan='OTWARTY')
        v2 = Zawory(id=102, nazwa_zaworu='V2', stan='OTWARTY')
        v3 = Zawory(id=103, nazwa_zaworu='V3', stan='ZAMKNIETY')
        v_fz1_internal = Zawory(id=104, nazwa_zaworu='V-FZ1-INT', stan='OTWARTY')

        # Segmenty: R01 -> W1 -> FZ1 -> R02 (trasa blokowana przez V3)
        # R01_OUT --(V1)--> W1
        seg1 = Segmenty(id=1001, nazwa_segmentu='SEG-R01-W1', id_zaworu=101, id_portu_startowego=10, id_wezla_koncowego=100)
        # W1 --(V2)--> FZ1_IN
        seg2 = Segmenty(id=1002, nazwa_segmentu='SEG-W1-FZ1', id_zaworu=102, id_wezla_startowego=100, id_portu_koncowego=30)
        
        seg_internal = Segmenty(id=1004, nazwa_segmentu='SEG-FZ1-INTERNAL', id_zaworu=104, id_portu_startowego=30, id_portu_koncowego=31)
        
        # FZ1_OUT --(V3)--> R02_IN (ten segment jest domyślnie zablokowany)
        seg3 = Segmenty(id=1003, nazwa_segmentu='SEG-FZ1-R02', id_zaworu=103, id_portu_startowego=31, id_portu_koncowego=20)
        
        db.session.add_all([
            r01, r02, fz1, p_r01_out, p_r02_in, p_fz1_in, p_fz1_out, 
            w1, v1, v2, v3, v_fz1_internal,  # Dodaj nowy zawór
            seg1, seg2, seg3, seg_internal  # Dodaj nowy segment
        ])
        db.session.commit()

    def test_01_topology_loads_correctly(self):
        """Sprawdza, czy graf jest budowany poprawnie z danymi z bazy."""
        # Oczekujemy 4 portów + 1 węzeł = 5 węzłów w grafie
        self.assertEqual(len(self.pathfinder.graph.nodes()), 5)
        # Oczekujemy 3 segmentów
        self.assertEqual(len(self.pathfinder.graph.edges()), 4)

    def test_02_find_simple_path_succeeds(self):
        """Sprawdza znajdowanie prostej, otwartej ścieżki."""
        # Z R01_OUT do FZ1_IN przez W1
        path = self.pathfinder.find_path('R01_OUT', 'FZ1_IN')
        self.assertIsNotNone(path)
        self.assertEqual(path, ['SEG-R01-W1', 'SEG-W1-FZ1'])

    def test_03_find_path_fails_when_valve_is_closed(self):
        """Sprawdza, czy zamknięty zawór poprawnie blokuje ścieżkę."""
        # Próba przejścia przez zamknięty V3 z FZ1_OUT do R02_IN
        path = self.pathfinder.find_path('FZ1_OUT', 'R02_IN')
        self.assertIsNone(path)

    def test_04_find_path_succeeds_when_blocked_valve_is_opened(self):
        """Sprawdza, czy ścieżka staje się dostępna po otwarciu zaworu."""
        # Otwieramy V3
        zawor_v3 = db.session.get(Zawory, 103)
        zawor_v3.stan = 'OTWARTY'
        db.session.commit()
        
        # Ponownie inicjalizujemy pathfinder, aby przeładował stany zaworów
        # W prawdziwej aplikacji stany zaworów są dynamiczne
        # Tutaj symulujemy to przez przekazanie listy otwartych zaworów
        open_valves = ['V1', 'V2', 'V3', 'V-FZ1-INT'] 
        path = self.pathfinder.find_path('R01_OUT', 'R02_IN', open_valves)
        
        self.assertIsNotNone(path)
        self.assertEqual(path, ['SEG-R01-W1', 'SEG-W1-FZ1', 'SEG-FZ1-INTERNAL', 'SEG-FZ1-R02'])

    def test_05_find_path_fails_for_nonexistent_path(self):
        """Sprawdza, czy dla niepołączonych punktów zwracany jest None."""
        path = self.pathfinder.find_path('R01_OUT', 'R02_IN') # Trasa jest fizycznie, ale V3 jest zamknięty
        self.assertIsNone(path)

    def test_06_release_path_closes_valves(self):
        """Sprawdza, czy metoda statyczna `release_path` poprawnie zamyka zawory."""
        # Upewnijmy się, że V1 i V2 są otwarte
        v1_before = db.session.get(Zawory, 101)
        v2_before = db.session.get(Zawory, 102)
        self.assertEqual(v1_before.stan, 'OTWARTY')
        self.assertEqual(v2_before.stan, 'OTWARTY')
        
        # Wywołujemy metodę do zamknięcia
        PathFinder.release_path(zawory_names=['V1', 'V2'])
        
        # Sprawdzamy stan w bazie
        db.session.commit() # Wymuszamy odświeżenie obiektów z bazy
        v1_after = db.session.get(Zawory, 101)
        v2_after = db.session.get(Zawory, 102)
        self.assertEqual(v1_after.stan, 'ZAMKNIETY')
        self.assertEqual(v2_after.stan, 'ZAMKNIETY')

    def test_07_find_path_with_nonexistent_start_node(self):
        """Sprawdza, czy find_path zwraca None dla nieistniejącego startu."""
        path = self.pathfinder.find_path('NIE_ISTNIEJE', 'R02_IN')
        self.assertIsNone(path)
        
    def test_08_find_path_with_same_start_and_end_node(self):
        """Sprawdza, czy find_path zwraca pustą listę dla tego samego startu i celu."""
        path = self.pathfinder.find_path('R01_OUT', 'R01_OUT')
        self.assertIsNotNone(path)
        self.assertEqual(path, [])
        
    def test_09_release_path_with_nonexistent_valve_name(self):
        """Sprawdza, czy release_path ignoruje nieistniejące zawory i nie rzuca błędu."""
        v1_before = db.session.get(Zawory, 101)
        self.assertEqual(v1_before.stan, 'OTWARTY')
        
        try:
            PathFinder.release_path(zawory_names=['V1', 'NIE_ISTNIEJE'])
        except Exception as e:
            self.fail(f"release_path rzucił nieoczekiwany błąd: {e}")
            
        db.session.commit()
        v1_after = db.session.get(Zawory, 101)
        self.assertEqual(v1_after.stan, 'ZAMKNIETY')
        
    # --- NOWE TESTY: Złożona topologia ---
    
    def test_10_find_path_chooses_shorter_of_two_paths(self):
        """Sprawdza, czy algorytm wybiera najkrótszą z dwóch dostępnych tras."""
        # Dodajemy dłuższą, alternatywną trasę z R01 do W1
        w2 = WezlyRurociagu(id=101, nazwa_wezla='W2')
        v_alt1 = Zawory(id=105, nazwa_zaworu='V-ALT1', stan='OTWARTY')
        v_alt2 = Zawory(id=106, nazwa_zaworu='V-ALT2', stan='OTWARTY')
        seg_alt1 = Segmenty(id=1005, nazwa_segmentu='SEG-ALT1', id_zaworu=105, id_portu_startowego=10, id_wezla_koncowego=101)
        seg_alt2 = Segmenty(id=1006, nazwa_segmentu='SEG-ALT2', id_zaworu=106, id_wezla_startowego=101, id_wezla_koncowego=100)
        db.session.add_all([w2, v_alt1, v_alt2, seg_alt1, seg_alt2])
        db.session.commit()
        
        # Przeładowujemy graf po zmianie topologii
        self.pathfinder._load_topology()
        
        # Szukamy ścieżki - powinna być wybrana krótsza, jedno-segmentowa (SEG-R01-W1)
        path = self.pathfinder.find_path('R01_OUT', 'W1')
        self.assertEqual(path, ['SEG-R01-W1'])

    def test_11_find_path_finds_alternative_when_primary_is_blocked(self):
        """Sprawdza, czy algorytm znajduje dłuższą trasę, gdy krótsza jest zablokowana."""
        # Dodajemy dłuższą trasę jak w teście 10
        w2 = WezlyRurociagu(id=101, nazwa_wezla='W2')
        v_alt1 = Zawory(id=105, nazwa_zaworu='V-ALT1', stan='OTWARTY')
        v_alt2 = Zawory(id=106, nazwa_zaworu='V-ALT2', stan='OTWARTY')
        seg_alt1 = Segmenty(id=1005, nazwa_segmentu='SEG-ALT1', id_zaworu=105, id_portu_startowego=10, id_wezla_koncowego=101)
        seg_alt2 = Segmenty(id=1006, nazwa_segmentu='SEG-ALT2', id_zaworu=106, id_wezla_startowego=101, id_wezla_koncowego=100)
        db.session.add_all([w2, v_alt1, v_alt2, seg_alt1, seg_alt2])
        
        # Zamykamy zawór na krótszej ścieżce
        v1 = db.session.get(Zawory, 101)
        v1.stan = 'ZAMKNIETY'
        db.session.commit()
        
        self.pathfinder._load_topology()
        
        # Szukamy ścieżki - powinna być wybrana dłuższa, dwu-segmentowa
        path = self.pathfinder.find_path('R01_OUT', 'W1', open_valves=['V-ALT1', 'V-ALT2'])
        self.assertEqual(path, ['SEG-ALT1', 'SEG-ALT2'])

    def test_12_find_path_with_corrected_leading_zero_names(self):
        """
        Weryfikuje, czy Pathfinder znajduje trasy dla sprzętu po 
        korekcie nazw (np. z B1c na B01c).
        Ten test dodaje do środowiska testowego sprzęt i porty, które
        wcześniej sprawiały problemy, aby upewnić się, że logika ładowania
        topologii jest na to odporna.
        """
        # --- Przygotowanie (Arrange) ---
        # 1. Dodajemy do naszej testowej topologii sprzęt i porty z nową konwencją nazewniczą
        sprzet_b01c = Sprzet(id=20, nazwa_unikalna='B01c', typ_sprzetu='beczka_czysta')
        port_b01c_in = PortySprzetu(id=200, id_sprzetu=20, nazwa_portu='B01c_IN', typ_portu='IN')
        
        # Łączymy istniejący węzeł W1 z nowym portem B01c_IN
        zawor_v_b01c = Zawory(id=201, nazwa_zaworu='V-B01c', stan='OTWARTY')
        seg_do_b01c = Segmenty(
            id=2001, 
            nazwa_segmentu='SEG-W1-B01c', 
            id_zaworu=201, 
            id_wezla_startowego=100,  # ID węzła W1 z _create_test_topology
            id_portu_koncowego=200
        )
        
        db.session.add_all([sprzet_b01c, port_b01c_in, zawor_v_b01c, seg_do_b01c])
        db.session.commit()
        
        # 2. Kluczowy krok: przeładowujemy topologię, aby Pathfinder "zobaczył" nowe elementy
        self.pathfinder._load_topology()
        
        # 3. Definiujemy trasę do znalezienia
        start_node = 'R01_OUT'
        end_node = 'B01c_IN'

        # --- Działanie (Act) ---
        # Używamy listy wszystkich otwartych zaworów, aby mieć pewność, że testujemy tylko topologię
        open_valves = [v.nazwa_zaworu for v in db.session.execute(db.select(Zawory)).scalars().all()]
        path = self.pathfinder.find_path(start_node, end_node, open_valves)
        
        # --- Asercje (Assert) ---
        self.assertIsNotNone(path, f"Pathfinder powinien znaleźć ścieżkę z {start_node} do {end_node}")
        self.assertEqual(path, ['SEG-R01-W1', 'SEG-W1-B01c'])
        
        # Sprawdźmy też, czy graf został poprawnie zaktualizowany
        self.assertIn('B01c_IN', self.pathfinder.graph.nodes())
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
# test_topology_integrity.py
import unittest
import json
from app import create_app, db
from app.config import DevConfigForTesting
from app.models import Sprzet, PortySprzetu, Zawory
from app.pathfinder_service import PathFinder
from itertools import product

class TestTopologyIntegrity(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        """Uruchamiane raz dla całej klasy testowej."""
        cls.app = create_app(DevConfigForTesting)
        cls.app_context = cls.app.app_context()
        cls.app_context.push()
        cls.pathfinder = PathFinder(cls.app)

    @classmethod
    def tearDownClass(cls):
        """Uruchamiane raz po zakończeniu wszystkich testów w klasie."""
        cls.app_context.pop()

    def test_generate_equipment_connectivity_matrix(self):
        """
        Generuje "macierz połączeń" dla całego kluczowego sprzętu.
        Testuje każdą możliwą kombinację połączenia z portu OUT jednego
        urządzenia do portu IN innego, aby zidentyfikować istniejące i
        brakujące trasy w topologii.
        """
        with self.app.app_context():
            # 1. Zdefiniuj typy sprzętu, które mają porty i biorą udział w transferach
            relevant_equipment_types = ['reaktor', 'beczka_brudna', 'beczka_czysta', 'apollo', 'cysterna', 'mauzer']
            
            # 2. Pobierz wszystkie porty OUT i IN dla relevantnego sprzętu
            ports_out_q = db.select(PortySprzetu.nazwa_portu).join(Sprzet).where(
                Sprzet.typ_sprzetu.in_(relevant_equipment_types),
                PortySprzetu.typ_portu == 'OUT'
            )
            ports_in_q = db.select(PortySprzetu.nazwa_portu).join(Sprzet).where(
                Sprzet.typ_sprzetu.in_(relevant_equipment_types),
                PortySprzetu.typ_portu == 'IN'
            )
            
            source_ports = db.session.execute(ports_out_q).scalars().all()
            destination_ports = db.session.execute(ports_in_q).scalars().all()

            self.assertGreater(len(source_ports), 0, "Nie znaleziono żadnych portów wyjściowych (OUT) do testowania.")
            self.assertGreater(len(destination_ports), 0, "Nie znaleziono żadnych portów wejściowych (IN) do testowania.")

            # Przekazujemy wszystkie zawory jako otwarte, aby testować tylko fizyczną możliwość połączenia
            all_valves = db.session.execute(db.select(Zawory.nazwa_zaworu)).scalars().all()

            results = {
                "possible_routes": [],
                "impossible_routes": []
            }

            # 3. Pętla "każdy z każdym"
            total_combinations = len(source_ports) * len(destination_ports)
            print(f"\n--- Rozpoczynam testowanie {total_combinations} możliwych połączeń ---")
            
            for start_node, end_node in product(source_ports, destination_ports):
                # Ignorujemy bezsensowne połączenia z punktu do samego siebie
                if start_node == end_node:
                    continue

                path = self.pathfinder.find_path(start_node, end_node, open_valves=all_valves)
                
                route_info = f"{start_node} -> {end_node}"
                if path:
                    results["possible_routes"].append({
                        "route": route_info,
                        "path": path,
                        "segments_count": len(path)
                    })
                else:
                    results["impossible_routes"].append({
                        "route": route_info
                    })

            # 4. Wyświetl wyniki w czytelny sposób
            print("\n--- ZNALEZIONE MOŻLIWE TRASY ---")
            # Sortujemy po liczbie segmentów, od najkrótszych
            for route_data in sorted(results["possible_routes"], key=lambda x: x["segments_count"]):
                 print(f"[ OK ] {route_data['route']} (Liczba segmentów: {route_data['segments_count']})")
            
            print("\n--- TRASY NIEMOŻLIWE DO ZESTAWIENIA ---")
            for route_data in sorted(results["impossible_routes"], key=lambda x: x["route"]):
                 print(f"[FAIL] {route_data['route']}")

            # 5. Opcjonalna asercja
            # Możesz dodać asercję, jeśli wiesz, że jakaś konkretna trasa MUSI istnieć.
            # Na przykład, jeśli połączenie z AP1 do R1 jest kluczowe:
            self.assertTrue(
                any(r['route'] == 'AP1_OUT -> R1_IN' for r in results['possible_routes']),
                "Krytyczne połączenie z AP1_OUT do R1_IN nie istnieje!"
            )
            
            # Wszystkie znalezione trasy - asercje według liczby segmentów
            
            # Trasy 2-segmentowe
            self.assertTrue(any(r['route'] == 'CYSTERNA_B01b_OUT -> CYSTERNA_B01b_IN' for r in results['possible_routes']), "CYSTERNA_B01b_OUT -> CYSTERNA_B01b_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'BIALA_OUT -> CYSTERNA_B12c_IN' for r in results['possible_routes']), "BIALA_OUT -> CYSTERNA_B12c_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'CYSTERNA_B12c_OUT -> CYSTERNA_B12c_IN' for r in results['possible_routes']), "CYSTERNA_B12c_OUT -> CYSTERNA_B12c_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'B12c_OUT -> CYSTERNA_B12c_IN' for r in results['possible_routes']), "B12c_OUT -> CYSTERNA_B12c_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'BIALA_OUT -> B12c_IN' for r in results['possible_routes']), "BIALA_OUT -> B12c_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'CYSTERNA_B12c_OUT -> B12c_IN' for r in results['possible_routes']), "CYSTERNA_B12c_OUT -> B12c_IN nie istnieje!")
            
            # Trasy 3-segmentowe
            self.assertTrue(any(r['route'] == 'B12c_OUT -> CYSTERNA_B12c_IN' for r in results['possible_routes']), "B12c_OUT -> CYSTERNA_B12c_IN (3 seg) nie istnieje!")
            self.assertTrue(any(r['route'] == 'BIALA_OUT -> B12c_IN' for r in results['possible_routes']), "BIALA_OUT -> B12c_IN (3 seg) nie istnieje!")
            self.assertTrue(any(r['route'] == 'CYSTERNA_B12c_OUT -> B12c_IN' for r in results['possible_routes']), "CYSTERNA_B12c_OUT -> B12c_IN (3 seg) nie istnieje!")
            
            # Trasy 4-segmentowe
            self.assertTrue(any(r['route'] == 'B08b_OUT -> R1_IN' for r in results['possible_routes']), "B08b_OUT -> R1_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'B08b_OUT -> R2_IN' for r in results['possible_routes']), "B08b_OUT -> R2_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'B08b_OUT -> R3_IN' for r in results['possible_routes']), "B08b_OUT -> R3_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'B08b_OUT -> R4_IN' for r in results['possible_routes']), "B08b_OUT -> R4_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'B08b_OUT -> R5_IN' for r in results['possible_routes']), "B08b_OUT -> R5_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'B08b_OUT -> R6_IN' for r in results['possible_routes']), "B08b_OUT -> R6_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'B08b_OUT -> R7_IN' for r in results['possible_routes']), "B08b_OUT -> R7_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'B08b_OUT -> R8_IN' for r in results['possible_routes']), "B08b_OUT -> R8_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'B08b_OUT -> R9_IN' for r in results['possible_routes']), "B08b_OUT -> R9_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'B11c_OUT -> CYSTERNA_B12c_IN' for r in results['possible_routes']), "B11c_OUT -> CYSTERNA_B12c_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'B12c_OUT -> B12c_IN' for r in results['possible_routes']), "B12c_OUT -> B12c_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'BIALA_OUT -> B11c_IN' for r in results['possible_routes']), "BIALA_OUT -> B11c_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'CYSTERNA_B12c_OUT -> B11c_IN' for r in results['possible_routes']), "CYSTERNA_B12c_OUT -> B11c_IN nie istnieje!")
            
            # Trasy 5-segmentowe - Reaktory między sobą
            self.assertTrue(any(r['route'] == 'R3_OUT -> R1_IN' for r in results['possible_routes']), "R3_OUT -> R1_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'R3_OUT -> R2_IN' for r in results['possible_routes']), "R3_OUT -> R2_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'R3_OUT -> R3_IN' for r in results['possible_routes']), "R3_OUT -> R3_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'R3_OUT -> R4_IN' for r in results['possible_routes']), "R3_OUT -> R4_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'R3_OUT -> R5_IN' for r in results['possible_routes']), "R3_OUT -> R5_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'R3_OUT -> R6_IN' for r in results['possible_routes']), "R3_OUT -> R6_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'R3_OUT -> R7_IN' for r in results['possible_routes']), "R3_OUT -> R7_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'R3_OUT -> R8_IN' for r in results['possible_routes']), "R3_OUT -> R8_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'R3_OUT -> R9_IN' for r in results['possible_routes']), "R3_OUT -> R9_IN nie istnieje!")
            
            self.assertTrue(any(r['route'] == 'R6_OUT -> R1_IN' for r in results['possible_routes']), "R6_OUT -> R1_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'R6_OUT -> R2_IN' for r in results['possible_routes']), "R6_OUT -> R2_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'R6_OUT -> R3_IN' for r in results['possible_routes']), "R6_OUT -> R3_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'R6_OUT -> R4_IN' for r in results['possible_routes']), "R6_OUT -> R4_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'R6_OUT -> R5_IN' for r in results['possible_routes']), "R6_OUT -> R5_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'R6_OUT -> R6_IN' for r in results['possible_routes']), "R6_OUT -> R6_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'R6_OUT -> R7_IN' for r in results['possible_routes']), "R6_OUT -> R7_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'R6_OUT -> R8_IN' for r in results['possible_routes']), "R6_OUT -> R8_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'R6_OUT -> R9_IN' for r in results['possible_routes']), "R6_OUT -> R9_IN nie istnieje!")
            
            self.assertTrue(any(r['route'] == 'R7_OUT -> R6_IN' for r in results['possible_routes']), "R7_OUT -> R6_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'R7_OUT -> R7_IN' for r in results['possible_routes']), "R7_OUT -> R7_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'R7_OUT -> R8_IN' for r in results['possible_routes']), "R7_OUT -> R8_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'R7_OUT -> R9_IN' for r in results['possible_routes']), "R7_OUT -> R9_IN nie istnieje!")
            
            self.assertTrue(any(r['route'] == 'R9_OUT -> R1_IN' for r in results['possible_routes']), "R9_OUT -> R1_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'R9_OUT -> R2_IN' for r in results['possible_routes']), "R9_OUT -> R2_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'R9_OUT -> R3_IN' for r in results['possible_routes']), "R9_OUT -> R3_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'R9_OUT -> R4_IN' for r in results['possible_routes']), "R9_OUT -> R4_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'R9_OUT -> R5_IN' for r in results['possible_routes']), "R9_OUT -> R5_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'R9_OUT -> R6_IN' for r in results['possible_routes']), "R9_OUT -> R6_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'R9_OUT -> R7_IN' for r in results['possible_routes']), "R9_OUT -> R7_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'R9_OUT -> R8_IN' for r in results['possible_routes']), "R9_OUT -> R8_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'R9_OUT -> R9_IN' for r in results['possible_routes']), "R9_OUT -> R9_IN nie istnieje!")
            
            # Trasy 5-segmentowe - Beczki do reaktorów
            self.assertTrue(any(r['route'] == 'B07b_OUT -> R1_IN' for r in results['possible_routes']), "B07b_OUT -> R1_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'B07b_OUT -> R2_IN' for r in results['possible_routes']), "B07b_OUT -> R2_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'B07b_OUT -> R3_IN' for r in results['possible_routes']), "B07b_OUT -> R3_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'B07b_OUT -> R4_IN' for r in results['possible_routes']), "B07b_OUT -> R4_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'B07b_OUT -> R5_IN' for r in results['possible_routes']), "B07b_OUT -> R5_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'B07b_OUT -> R6_IN' for r in results['possible_routes']), "B07b_OUT -> R6_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'B07b_OUT -> R7_IN' for r in results['possible_routes']), "B07b_OUT -> R7_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'B07b_OUT -> R8_IN' for r in results['possible_routes']), "B07b_OUT -> R8_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'B07b_OUT -> R9_IN' for r in results['possible_routes']), "B07b_OUT -> R9_IN nie istnieje!")
            
            # Trasy 5-segmentowe - Loopback beczek
            self.assertTrue(any(r['route'] == 'B08b_OUT -> B08b_IN' for r in results['possible_routes']), "B08b_OUT -> B08b_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'B09b_OUT -> B09b_IN' for r in results['possible_routes']), "B09b_OUT -> B09b_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'B08c_OUT -> B08c_IN' for r in results['possible_routes']), "B08c_OUT -> B08c_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'B08c_OUT -> B09c_IN' for r in results['possible_routes']), "B08c_OUT -> B09c_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'B09c_OUT -> B08c_IN' for r in results['possible_routes']), "B09c_OUT -> B08c_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'B09c_OUT -> B09c_IN' for r in results['possible_routes']), "B09c_OUT -> B09c_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'B10c_OUT -> CYSTERNA_B12c_IN' for r in results['possible_routes']), "B10c_OUT -> CYSTERNA_B12c_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'B11c_OUT -> B12c_IN' for r in results['possible_routes']), "B11c_OUT -> B12c_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'B12c_OUT -> B11c_IN' for r in results['possible_routes']), "B12c_OUT -> B11c_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'BIALA_OUT -> B10c_IN' for r in results['possible_routes']), "BIALA_OUT -> B10c_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'CYSTERNA_B12c_OUT -> B10c_IN' for r in results['possible_routes']), "CYSTERNA_B12c_OUT -> B10c_IN nie istnieje!")
            
            # Dodatkowe kluczowe trasy z dalszych segmentów
            self.assertTrue(any(r['route'] == 'AP1_OUT -> B09b_IN' for r in results['possible_routes']), "AP1_OUT -> B09b_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'MAUZER_OUT -> B09b_IN' for r in results['possible_routes']), "MAUZER_OUT -> B09b_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'NIEBIESKA_OUT -> B09b_IN' for r in results['possible_routes']), "NIEBIESKA_OUT -> B09b_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'CYSTERNA_B01b_OUT -> B08b_IN' for r in results['possible_routes']), "CYSTERNA_B01b_OUT -> B08b_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'CYSTERNA_B10b_OUT -> B09b_IN' for r in results['possible_routes']), "CYSTERNA_B10b_OUT -> B09b_IN nie istnieje!")
            self.assertTrue(any(r['route'] == 'AP2_OUT -> B09b_IN' for r in results['possible_routes']), "AP2_OUT -> B09b_IN nie istnieje!")
            
            # Asercja, że w ogóle znaleziono jakiekolwiek trasy
            self.assertGreater(len(results["possible_routes"]), 0, "Nie znaleziono ŻADNYCH możliwych tras w całej topologii!")
# test_workflow_routes.py
import unittest
import json
from app import create_app, db
from app.config import TestConfig
from app.models import Sprzet, TankMixes, OperacjeLog # Dodano OperacjeLog
from sqlalchemy import select, text
from decimal import Decimal
from datetime import datetime, timedelta, timezone # Dodano datetime

class TestWorkflowRoutes(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        with self.app.app_context():
            db.session.execute(text("SET FOREIGN_key_CHECKS=0"))
            for table in reversed(db.metadata.sorted_tables):
                db.session.execute(text(f'TRUNCATE TABLE {table.name}'))
            db.session.execute(text("SET FOREIGN_KEY_CHECKS=1"))
            db.session.commit()

    def tearDown(self):
        db.session.remove()
        self.app_context.pop()
    
    def _prepare_mix_for_assessment(self):
        reaktor = Sprzet(id=201, nazwa_unikalna='R1', typ_sprzetu='reaktor')
        mix = TankMixes(id=10, tank_id=reaktor.id, unique_code='MIX-TEST-ROUTE', process_status='OCZEKUJE_NA_OCENE')
        reaktor.active_mix_id = mix.id
        db.session.add_all([reaktor, mix])
        db.session.commit()
        return mix

    def _prepare_mix_for_bleaching(self, temp=Decimal('115.0'), status='PODGRZEWANY', is_wydmuch=False, initial_bags=0):
        reaktor = Sprzet(id=1, nazwa_unikalna='R1', typ_sprzetu='reaktor', temperatura_aktualna=temp)
        mix = TankMixes(id=10, tank=reaktor, unique_code='MIX-FOR-BLEACHING',
                        process_status=status, bleaching_earth_bags_total=initial_bags,
                        is_wydmuch_mix=is_wydmuch,
                        creation_date=datetime.now(timezone.utc) - timedelta(hours=1))
        reaktor.active_mix_id = mix.id
        db.session.add_all([reaktor, mix])
        db.session.commit()
        return mix

    # --- Testy dla /assess ---
    def test_assess_mix_ok_success(self):
        mix = self._prepare_mix_for_assessment()
        payload = {"decision": "OK", "operator": "API_USER"}
        response = self.client.post(f'/api/workflow/mix/{mix.id}/assess', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['new_status'], 'ZATWIERDZONA')

    def test_assess_mix_zla_with_reason_success(self):
        mix = self._prepare_mix_for_assessment()
        payload = {"decision": "ZLA", "operator": "API_USER", "reason": "Testowy powód"}
        response = self.client.post(f'/api/workflow/mix/{mix.id}/assess', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['new_status'], 'DO_PONOWNEJ_FILTRACJI')

    def test_assess_mix_missing_payload_fails(self):
        mix = self._prepare_mix_for_assessment()
        response = self.client.post(f'/api/workflow/mix/{mix.id}/assess', content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_assess_mix_in_wrong_state_fails_422(self):
        mix = self._prepare_mix_for_assessment()
        mix.process_status = 'ZATWIERDZONA'
        db.session.commit()
        payload = {"decision": "OK", "operator": "API_USER"}
        response = self.client.post(f'/api/workflow/mix/{mix.id}/assess', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 422)
        data = response.get_json()
        self.assertIn("Nie można ocenić mieszaniny", data['error'])

    # --- NOWE TESTY dla /add-bleach ---

    def test_add_bleaching_earth_success_api(self):
        """Testuje pomyślne dodanie ziemi bielącej przez API."""
        mix = self._prepare_mix_for_bleaching()
        payload = {"bags_count": 5, "bag_weight": 25.0, "operator": "API_USER"}
        
        response = self.client.post(
            f'/api/workflow/mix/{mix.id}/add-bleach',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['new_status'], 'DOBIELONY_OCZEKUJE')
        self.assertEqual(data['total_bags'], 5)

    def test_add_bleaching_earth_second_time_updates_api(self):
        """Testuje, czy drugie dobielenie przez API aktualizuje istniejący log."""
        mix = self._prepare_mix_for_bleaching(status='DOBIELONY_OCZEKUJE', initial_bags=4)
        initial_log = OperacjeLog(
            typ_operacji='DOBIELANIE', id_tank_mix=mix.id, status_operacji='zakonczona',
            czas_rozpoczecia=datetime.now(timezone.utc)-timedelta(minutes=10),
            ilosc_workow=4, ilosc_kg=Decimal('100.0')
        )
        db.session.add(initial_log)
        db.session.commit()
        
        payload = {"bags_count": 2, "bag_weight": 25.0, "operator": "API_USER"}
        response = self.client.post(
            f'/api/workflow/mix/{mix.id}/add-bleach',
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['total_bags'], 6)
        self.assertIn("Dodano kolejne 2 worków", data['message'])

        # Sprawdź, czy w bazie jest nadal tylko jeden log
        logs = db.session.execute(select(OperacjeLog)).scalars().all()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].ilosc_kg, Decimal('150.0'))

    def test_add_bleaching_earth_invalid_payload_fails_400(self):
        """Testuje błąd 400 dla niepoprawnych danych wejściowych."""
        mix = self._prepare_mix_for_bleaching()
        
        # Brak wagi worka
        bad_payload = {"bags_count": 5, "operator": "API_USER"}
        response = self.client.post(
            f'/api/workflow/mix/{mix.id}/add-bleach',
            data=json.dumps(bad_payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_add_bleaching_earth_exceeds_limit_fails_422(self):
        """Testuje błąd 422 (logiki biznesowej) przy przekroczeniu limitu wagi."""
        mix = self._prepare_mix_for_bleaching()
        payload = {"bags_count": 7, "bag_weight": 25.0, "operator": "API_USER"} # 175 kg

        response = self.client.post(
            f'/api/workflow/mix/{mix.id}/add-bleach',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 422)
        data = response.get_json()
        self.assertIn("przekracza maksymalny limit", data['error'])
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
