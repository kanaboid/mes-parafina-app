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
            
            # Asercja, że w ogóle znaleziono jakiekolwiek trasy
            self.assertGreater(len(results["possible_routes"]), 0, "Nie znaleziono ŻADNYCH możliwych tras w całej topologii!")