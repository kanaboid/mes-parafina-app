# test_apollo_service.py

import unittest
from datetime import datetime, timedelta
import time

from app import create_app
from app.config import Config
from app.apollo_service import ApolloService
from app.db import get_db_connection
from app.models import ApolloSesje, PartieSurowca, Sprzet, ApolloTracking, OperacjeLog
from app import db
from sqlalchemy import text

class TestConfig(Config):
    TESTING = True
    MYSQL_HOST = 'localhost'
    MYSQL_USER = 'root'
    MYSQL_PASSWORD = ''
    MYSQL_DB = 'mes_parafina_db_test'
    SERVER_NAME = 'localhost.localdomain'

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+mysqlconnector://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DB}"
    )

TEST_APOLLO_ID = 999
TEST_APOLLO_NAZWA = 'AP999'

class TestApolloService(unittest.TestCase): 
    
    @classmethod
    def setUpClass(cls):
        """
        Uruchamiane raz na początku. Czyści bazę i tworzy testowy sprzęt.
        """
        app = create_app(TestConfig)
        with app.app_context():
            # ZMIANA: Używamy `db.session` zamiast `get_db_connection`
            try:
                # Wyłączamy sprawdzanie kluczy obcych
                db.session.execute(text("SET FOREIGN_KEY_CHECKS=0"))
                
                # Używamy `TRUNCATE` dla szybszego czyszczenia
                
                db.session.execute(text("TRUNCATE TABLE operacje_log"))
                db.session.execute(text("TRUNCATE TABLE apollo_tracking"))
                db.session.execute(text("TRUNCATE TABLE partie_surowca"))
                db.session.execute(text("TRUNCATE TABLE apollo_sesje"))
                db.session.execute(text(f"DELETE FROM sprzet WHERE id = {TEST_APOLLO_ID}"))
                
                # Dodajemy testowy sprzęt
                nowy_sprzet = Sprzet(id=TEST_APOLLO_ID, nazwa_unikalna=TEST_APOLLO_NAZWA, typ_sprzetu='apollo', stan_sprzetu='Gotowy')
                db.session.add(nowy_sprzet)

                db.session.commit()
            finally:
                # Zawsze włączamy klucze obce z powrotem
                db.session.execute(text("SET FOREIGN_KEY_CHECKS=1"))
                db.session.commit() # Upewnij się, że zmiana jest zapisana

    def setUp(self):
        """
        Uruchamiane przed każdym testem. Tworzy kontekst i czyści dane transakcyjne.
        """
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()

        self.conn = get_db_connection()
        self.cursor = self.conn.cursor(dictionary=True)

        # Czyścimy tylko to, co mogło zostać stworzone w trakcie testu
        self.cursor.execute("SET FOREIGN_KEY_CHECKS=0")
        self.cursor.execute("TRUNCATE TABLE apollo_tracking")
        self.cursor.execute("TRUNCATE TABLE partie_surowca")
        self.cursor.execute("TRUNCATE TABLE apollo_sesje")
        self.cursor.execute("SET FOREIGN_KEY_CHECKS=1")
        self.conn.commit()

    def tearDown(self):
        """Uruchamiane po każdym teście."""
        self.cursor.close()
        self.conn.close()
        self.app_context.pop()
    
    # ... Reszta metod testowych (test_01 do test_07) pozostaje bez zmian ...
    def test_01_rozpocznij_sesje_sukces(self):
        """Sprawdza, czy można poprawnie rozpocząć nową sesję."""
        waga_startowa = 500.0
        id_sesji = ApolloService.rozpocznij_sesje_apollo(
            id_sprzetu=TEST_APOLLO_ID,
            typ_surowca='TEST-SUROWIEC',
            waga_kg=waga_startowa,
            operator='TESTER'
        )
        self.assertIsInstance(id_sesji, int)
        self.assertGreater(id_sesji, 0)
        self.cursor.execute("SELECT * FROM apollo_sesje WHERE id = %s", (id_sesji,))
        sesja_db = self.cursor.fetchone()
        self.assertIsNotNone(sesja_db)
        self.assertEqual(sesja_db['status_sesji'], 'aktywna')
        self.assertEqual(sesja_db['id_sprzetu'], TEST_APOLLO_ID)
        self.cursor.execute("SELECT * FROM apollo_tracking WHERE id_sesji = %s", (id_sesji,))
        tracking_db = self.cursor.fetchone()
        self.assertIsNotNone(tracking_db)
        self.assertEqual(tracking_db['typ_zdarzenia'], 'DODANIE_SUROWCA')
        self.assertEqual(float(tracking_db['waga_kg']), waga_startowa)
        self.cursor.execute("SELECT * FROM partie_surowca WHERE id_sprzetu = %s", (TEST_APOLLO_ID,))
        partia_db = self.cursor.fetchone()
        self.assertIsNotNone(partia_db)
        self.assertEqual(float(partia_db['waga_aktualna_kg']), waga_startowa)

    def test_02_rozpocznij_sesje_gdy_juz_aktywna(self):
        """Sprawdza, czy próba otwarcia drugiej sesji na tym samym sprzęcie zwróci błąd."""
        ApolloService.rozpocznij_sesje_apollo(TEST_APOLLO_ID, 'TYP1', 100)
        with self.assertRaises(ValueError) as context:
            ApolloService.rozpocznij_sesje_apollo(TEST_APOLLO_ID, 'TYP2', 200)
        self.assertIn(f"Apollo o ID {TEST_APOLLO_ID} ma już aktywną sesję.", str(context.exception))

    def test_03_dodaj_surowiec_do_aktywnej_sesji(self):
        """Sprawdza, czy można poprawnie dodać surowiec do istniejącej sesji."""
        waga_startowa = 500.0
        dodana_waga = 250.0
        id_sesji = ApolloService.rozpocznij_sesje_apollo(TEST_APOLLO_ID, 'TEST-SUROWIEC', waga_startowa)
        ApolloService.dodaj_surowiec_do_apollo(TEST_APOLLO_ID, dodana_waga)
        self.cursor.execute("SELECT waga_aktualna_kg FROM partie_surowca WHERE id_sprzetu = %s", (TEST_APOLLO_ID,))
        partia_db = self.cursor.fetchone()
        oczekiwana_waga = waga_startowa + dodana_waga
        self.assertAlmostEqual(float(partia_db['waga_aktualna_kg']), oczekiwana_waga)
        self.cursor.execute("SELECT COUNT(*) as count FROM apollo_tracking WHERE id_sesji = %s AND typ_zdarzenia = 'DODANIE_SUROWCA'", (id_sesji,))
        zdarzenia_db = self.cursor.fetchone()
        self.assertEqual(zdarzenia_db['count'], 2)

    def test_04_zakoncz_sesje(self):
        """Sprawdza, czy sesja jest poprawnie zamykana."""
        id_sesji = ApolloService.rozpocznij_sesje_apollo(TEST_APOLLO_ID, 'TEST-SUROWIEC', 500)
        ApolloService.zakoncz_sesje_apollo(TEST_APOLLO_ID)
        self.cursor.execute("SELECT status_sesji, czas_zakonczenia FROM apollo_sesje WHERE id = %s", (id_sesji,))
        sesja_db = self.cursor.fetchone()
        self.assertEqual(sesja_db['status_sesji'], 'zakonczona')
        self.assertIsNotNone(sesja_db['czas_zakonczenia'])

    def test_05_oblicz_stan_prosty_przypadek(self):
        """Testuje obliczanie stanu po krótkim czasie topnienia."""
        waga_startowa = 2000.0
        
        # ZMIANA: Używamy stałych czasów
        czas_teraz = datetime(2025, 1, 1, 12, 0, 36)
        czas_startu_sesji = datetime(2025, 1, 1, 12, 0, 0)
        
        ApolloService.rozpocznij_sesje_apollo(
            TEST_APOLLO_ID, 'TEST-SUROWIEC', waga_startowa, event_time=czas_startu_sesji
        )

        szybkosc_topnienia = ApolloService.SZYBKOSC_WYTAPIANIA_KG_H
        oczekiwana_ilosc_wytopiona = (36 / 3600.0) * szybkosc_topnienia # 10.0 kg
        
        # ZMIANA: Przekazujemy `current_time`
        stan = ApolloService.oblicz_aktualny_stan_apollo(TEST_APOLLO_ID, current_time=czas_teraz)
        
        self.assertTrue(stan['aktywna_sesja'])
        self.assertAlmostEqual(stan['dostepne_kg'], oczekiwana_ilosc_wytopiona, delta=0.1)

    def test_06_oblicz_stan_z_limitem_surowca(self):
        """Testuje, czy ilość wytopiona nie przekroczy ilości dodanego surowca."""
        waga_startowa = 5.0

        # ZMIANA: Używamy stałych czasów
        czas_teraz = datetime(2025, 1, 1, 13, 0, 0) # Godzina później
        czas_startu_sesji = datetime(2025, 1, 1, 12, 0, 0)

        ApolloService.rozpocznij_sesje_apollo(
            TEST_APOLLO_ID, 'TEST-SUROWIEC', waga_startowa, event_time=czas_startu_sesji
        )
        
        # ZMIANA: Przekazujemy `current_time`
        stan = ApolloService.oblicz_aktualny_stan_apollo(TEST_APOLLO_ID, current_time=czas_teraz)
        
        # Oczekujemy, że wynik będzie ograniczony do wagi startowej
        self.assertAlmostEqual(stan['dostepne_kg'], waga_startowa, delta=0.1)

    def test_07_oblicz_stan_po_korekcie_recznej(self):
        """Testuje, czy obliczenia poprawnie restartują się od momentu korekty."""
        # --- Przygotowanie ---
        czas_teraz = datetime(2025, 1, 1, 12, 0, 0)
        czas_startu_sesji = czas_teraz - timedelta(minutes=20)   # 11:40:00
        czas_korekty = czas_teraz - timedelta(minutes=10)        # 11:50:00
        czas_dodania_1 = czas_teraz - timedelta(minutes=5)      # 11:55:00

        ApolloService.rozpocznij_sesje_apollo(
            id_sprzetu=TEST_APOLLO_ID, 
            typ_surowca='TEST-SUROWIEC', 
            waga_kg=1000,
            event_time=czas_startu_sesji
        )
        
        waga_korekty = 150.0
        ApolloService.koryguj_stan_apollo(
            id_sprzetu=TEST_APOLLO_ID,
            rzeczywista_waga_kg=waga_korekty,
            event_time=czas_korekty
        )
        
        waga_dodania_1 = 50.0
        ApolloService.dodaj_surowiec_do_apollo(
            id_sprzetu=TEST_APOLLO_ID,
            waga_kg=waga_dodania_1,
            event_time=czas_dodania_1
        )

        # --- Obliczenia oczekiwane ---
        czas_topnienia_h = 10 / 60.0 # 10 minut od korekty do "teraz"
        wytopiono_teoretycznie = czas_topnienia_h * ApolloService.SZYBKOSC_WYTAPIANIA_KG_H # 166.67 kg
        
        limit_topnienia = waga_dodania_1 # Tylko 50kg dodano po korekcie
        
        realnie_wytopiono = min(wytopiono_teoretycznie, limit_topnienia) # Czyli 50.0 kg
        
        oczekiwany_stan = waga_korekty + realnie_wytopiono # 150.0 + 50.0 = 200.0

        # --- Wywołanie i Asercja ---
        stan = ApolloService.oblicz_aktualny_stan_apollo(TEST_APOLLO_ID, current_time=czas_teraz)

        self.assertAlmostEqual(stan['dostepne_kg'], oczekiwany_stan, places=4)


    def test_08_zakoncz_sesje_sukces(self):
        """
        Sprawdza scenariusz 'happy path': zakończenie sesji, 
        która ma powiązaną partię surowca.
        """
        # --- Krok 1: Przygotowanie (Arrange) ---
        # Używamy serwisu, aby stworzyć spójny stan początkowy (sesja + partia)
        id_sesji = ApolloService.rozpocznij_sesje_apollo(TEST_APOLLO_ID, 'TEST-ZAKONCZENIE', 1000)
        
        # Znajdźmy ID partii, która właśnie powstała, aby ją później zweryfikować
        partia_przed = db.session.execute(
            db.select(PartieSurowca).filter_by(id_sprzetu=TEST_APOLLO_ID)
        ).scalar_one()
        self.assertEqual(partia_przed.status_partii, 'Surowy w reaktorze')

        # --- Krok 2: Działanie (Act) ---
        ApolloService.zakoncz_sesje_apollo(TEST_APOLLO_ID)

        # --- Krok 3: Asercje (Assert) ---
        # 3a. Sprawdź, czy sesja została poprawnie zamknięta
        sesja_po = db.session.get(ApolloSesje, id_sesji)
        self.assertIsNotNone(sesja_po)
        self.assertEqual(sesja_po.status_sesji, 'zakonczona')
        self.assertIsNotNone(sesja_po.czas_zakonczenia)

        # 3b. Sprawdź, czy partia została zarchiwizowana
        partia_po = db.session.get(PartieSurowca, partia_przed.id)
        self.assertIsNotNone(partia_po)
        self.assertEqual(partia_po.status_partii, 'Archiwalna')

    def test_09_zakoncz_sesje_gdy_brak_aktywnej(self):
        """
        Sprawdza, czy próba zakończenia nieistniejącej sesji poprawnie rzuca błąd.
        """
        # Oczekujemy błędu ValueError, ponieważ nie ma aktywnej sesji
        with self.assertRaises(ValueError) as context:
            ApolloService.zakoncz_sesje_apollo(TEST_APOLLO_ID)
        
        # Sprawdź, czy komunikat błędu jest poprawny
        self.assertIn("nie ma aktywnej sesji do zakończenia", str(context.exception))

    def test_10_zakoncz_sesje_bez_powiazanej_partii(self):
        """
        Sprawdza, czy funkcja działa poprawnie, jeśli istnieje sesja,
        ale (z jakiegoś powodu) nie ma powiązanej z nią partii surowca.
        """
        # --- Krok 1: Przygotowanie (Arrange) ---
        # Ręcznie tworzymy tylko sesję, bez partii
        czas_startu = datetime.now()
        tylko_sesja = ApolloSesje(
            id_sprzetu=TEST_APOLLO_ID,
            typ_surowca='SESJA_BEZ_PARTII',
            czas_rozpoczecia=czas_startu,
            status_sesji='aktywna'
        )
        db.session.add(tylko_sesja)
        db.session.commit()
        id_sesji = tylko_sesja.id

        # --- Krok 2: Działanie (Act) ---
        # Ta operacja nie powinna rzucić żadnego błędu
        try:
            ApolloService.zakoncz_sesje_apollo(TEST_APOLLO_ID)
        except Exception as e:
            self.fail(f"zakoncz_sesje_apollo rzuciło nieoczekiwany wyjątek: {e}")

        # --- Krok 3: Asercje (Assert) ---
        # Sprawdź, czy sesja została zamknięta
        sesja_po = db.session.get(ApolloSesje, id_sesji)
        self.assertEqual(sesja_po.status_sesji, 'zakonczona')


    def test_11_get_stan_apollo_brak_sesji(self):
        """
        Sprawdza, czy `get_stan_apollo` zwraca poprawne dane, gdy nie ma aktywnej sesji.
        """
        stan = ApolloService.get_stan_apollo(TEST_APOLLO_ID)

        self.assertIsNotNone(stan)
        self.assertEqual(stan['id_sprzetu'], TEST_APOLLO_ID)
        self.assertFalse(stan['aktywna_sesja'])

    def test_12_get_stan_apollo_aktywna_sesja_bez_transferow(self):
        """
        Sprawdza obliczenia `get_stan_apollo` dla prostej sesji (WERSJA ORM).
        """
        # --- Krok 1: Przygotowanie (Arrange) z SQLAlchemy ---
        czas_teraz = datetime.now()
        czas_startu_sesji = czas_teraz - timedelta(minutes=6)

        sesja = ApolloSesje(
            id_sprzetu=TEST_APOLLO_ID, typ_surowca='T-STAN',
            status_sesji='aktywna', czas_rozpoczecia=czas_startu_sesji
        )
        db.session.add(sesja)
        db.session.commit() # Commit, aby sesja była widoczna i miała ID

        tracking = ApolloTracking(
            id_sesji=sesja.id, typ_zdarzenia='DODANIE_SUROWCA',
            waga_kg=500, czas_zdarzenia=czas_startu_sesji
        )
        db.session.add(tracking)

        sprzet = db.session.get(Sprzet, TEST_APOLLO_ID)
        sprzet.szybkosc_topnienia_kg_h = 1000.0
        
        db.session.commit()
        print(f"\n[DEBUG TEST 12] Przygotowano sesję ID: {sesja.id} i tracking ID: {tracking.id}")

        # --- Krok 2: Działanie (Act) ---
        oczekiwana_dostepnosc = 100.0
        stan = ApolloService.get_stan_apollo(TEST_APOLLO_ID)

        # --- Krok 3: Asercje (Assert) ---
        self.assertTrue(stan['aktywna_sesja'])
        self.assertEqual(stan['id_sesji'], sesja.id)
        self.assertAlmostEqual(stan['bilans_sesji_kg'], 500.0)
        self.assertAlmostEqual(stan['dostepne_kg'], oczekiwana_dostepnosc, delta=1.0)

    def test_13_get_stan_apollo_z_transferem(self):
        """
        Sprawdza obliczenia `get_stan_apollo` po transferze (WERSJA ORM).
        """
        # --- Krok 1: Przygotowanie (Arrange) z SQLAlchemy ---
        czas_teraz = datetime.now()
        czas_startu_sesji = czas_teraz - timedelta(minutes=30)
        czas_zakonczenia_transferu = czas_teraz - timedelta(minutes=12)

        sesja = ApolloSesje(
            id_sprzetu=TEST_APOLLO_ID, typ_surowca='T-STAN-TR',
            status_sesji='aktywna', czas_rozpoczecia=czas_startu_sesji
        )
        db.session.add(sesja)
        db.session.commit()

        tracking = ApolloTracking(
            id_sesji=sesja.id, typ_zdarzenia='DODANIE_SUROWCA',
            waga_kg=1000, czas_zdarzenia=czas_startu_sesji
        )
        operacja = OperacjeLog(
            typ_operacji='TRANSFER_Z_APOLLO',
            id_apollo_sesji=sesja.id,
            status_operacji='zakonczona',
            ilosc_kg=200,
            czas_rozpoczecia=czas_zakonczenia_transferu,
            czas_zakonczenia=czas_zakonczenia_transferu
        )
        db.session.add_all([tracking, operacja])

        sprzet = db.session.get(Sprzet, TEST_APOLLO_ID)
        sprzet.szybkosc_topnienia_kg_h = 1000.0
        db.session.commit()
        print(f"\n[DEBUG TEST 13] Przygotowano sesję ID: {sesja.id}, tracking ID: {tracking.id}, operacja ID: {operacja.id}")

        # --- Krok 2: Działanie (Act) ---
        oczekiwana_dostepnosc = 200.0
        stan = ApolloService.get_stan_apollo(TEST_APOLLO_ID)

        # --- Krok 3: Asercje (Assert) ---
        self.assertTrue(stan['aktywna_sesja'])
        self.assertAlmostEqual(stan['bilans_sesji_kg'], 800.0)
        self.assertAlmostEqual(stan['dostepne_kg'], oczekiwana_dostepnosc, delta=1.0)



if __name__ == '__main__':
    unittest.main()