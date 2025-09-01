# test_operations_routes.py
import unittest
import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

# Importy z aplikacji
from app import create_app, db
from app.config import TestConfig
from app.models import Sprzet, PartieSurowca, PortySprzetu, Segmenty, Zawory, OperacjeLog
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
        partia = PartieSurowca(
            id=50, 
            id_sprzetu=1, 
            unikalny_kod='PARTIA-TEST-1', 
            nazwa_partii='Partia Test 1',
            zrodlo_pochodzenia='cysterna', # Wymagane
            waga_poczatkowa_kg=5000,      # Wymagane
            waga_aktualna_kg=5000,
            status_partii='Surowy w reaktorze'   # Wymagane
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
        partia = PartieSurowca(
            id=50, id_sprzetu=1, unikalny_kod='PARTIA-DO-ZAKONCZENIA', nazwa_partii='P-TEST',
            zrodlo_pochodzenia='cysterna', waga_poczatkowa_kg=1000, waga_aktualna_kg=1000,
            status_partii='Surowy w reaktorze'
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

        partia_po = db.session.get(PartieSurowca, 50)
        self.assertEqual(partia_po.id_sprzetu, 2) # Sprawdź, czy partia została przeniesiona do celu

        zrodlo_po = db.session.get(Sprzet, 1)
        self.assertEqual(zrodlo_po.stan_sprzetu, 'Pusty')
        
        cel_po = db.session.get(Sprzet, 2)
        self.assertEqual(cel_po.stan_sprzetu, 'Zatankowany')

if __name__ == '__main__':
    unittest.main()