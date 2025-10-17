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