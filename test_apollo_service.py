# test_apollo_service.py

import unittest
from datetime import datetime, timedelta
import time

from app import create_app
from app.config import Config
from app.apollo_service import ApolloService
from app.db import get_db_connection

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
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # ZMIANA: Prawidłowa kolejność czyszczenia i wyłączenie sprawdzania kluczy obcych
            try:
                # 1. Tymczasowo wyłącz sprawdzanie kluczy obcych
                cursor.execute("SET FOREIGN_KEY_CHECKS=0")
                
                # 2. Czyść tabele w poprawnej kolejności (od "dzieci" do "rodziców")
                # Chociaż przy wyłączonych kluczach kolejność nie jest krytyczna,
                # jest to dobra praktyka.
                cursor.execute("TRUNCATE TABLE apollo_tracking")
                cursor.execute("TRUNCATE TABLE partie_surowca")
                cursor.execute("TRUNCATE TABLE apollo_sesje")
                cursor.execute("DELETE FROM sprzet WHERE id = %s", (TEST_APOLLO_ID,))
                
                # 3. Włącz ponownie sprawdzanie kluczy obcych
                cursor.execute("SET FOREIGN_KEY_CHECKS=1")

                # 4. Dodaj testowy sprzęt
                cursor.execute("""
                    INSERT INTO sprzet (id, nazwa_unikalna, typ_sprzetu, stan_sprzetu) 
                    VALUES (%s, %s, 'apollo', 'Gotowy')
                """, (TEST_APOLLO_ID, TEST_APOLLO_NAZWA))
                
                conn.commit()
            finally:
                cursor.close()
                conn.close()

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
        ApolloService.rozpocznij_sesje_apollo(TEST_APOLLO_ID, 'TEST-SUROWIEC', waga_startowa)
        szybkosc_topnienia = ApolloService.SZYBKOSC_WYTAPIANIA_KG_H
        oczekiwana_ilosc_wytopiona = (36 / 3600.0) * szybkosc_topnienia
        czas_startu_symulowany = datetime.now() - timedelta(seconds=36)
        self.cursor.execute("UPDATE apollo_sesje SET czas_rozpoczecia = %s WHERE id_sprzetu = %s", (czas_startu_symulowany, TEST_APOLLO_ID))
        self.conn.commit()
        stan = ApolloService.oblicz_aktualny_stan_apollo(TEST_APOLLO_ID)
        self.assertTrue(stan['aktywna_sesja'])
        self.assertAlmostEqual(stan['dostepne_kg'], oczekiwana_ilosc_wytopiona, delta=0.1)

    def test_06_oblicz_stan_z_limitem_surowca(self):
        """Testuje, czy ilość wytopiona nie przekroczy ilości dodanego surowca."""
        waga_startowa = 5.0
        ApolloService.rozpocznij_sesje_apollo(TEST_APOLLO_ID, 'TEST-SUROWIEC', waga_startowa)
        czas_startu_symulowany = datetime.now() - timedelta(hours=1)
        self.cursor.execute("UPDATE apollo_sesje SET czas_rozpoczecia = %s WHERE id_sprzetu = %s", (czas_startu_symulowany, TEST_APOLLO_ID))
        self.conn.commit()
        stan = ApolloService.oblicz_aktualny_stan_apollo(TEST_APOLLO_ID)
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


if __name__ == '__main__':
    unittest.main()