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