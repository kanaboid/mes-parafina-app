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