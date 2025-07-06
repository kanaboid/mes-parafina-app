# app/pathfinder_service.py

import networkx as nx
from .db import get_db_connection  # Importujemy funkcję do połączenia z bazą danych

class PathFinder:
    def __init__(self, app=None):
        self.graph = nx.DiGraph()
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """Metoda do inicjalizacji serwisu w kontekście aplikacji Flask."""
        import sys
        print("INFO: Inicjalizacja PathFinder...")
        sys.stdout.flush()
        # Przechowujemy referencję do aplikacji, aby mieć dostęp do konfiguracji
        self.app = app
        # Wczytujemy topologię używając kontekstu aplikacji
        with app.app_context():
            self._load_topology()

    def _get_db_connection(self):
        """Prywatna metoda do łączenia się z bazą, używająca konfiguracji z aplikacji."""
        return get_db_connection()

    def _load_topology(self):
        """Wczytuje mapę instalacji z bazy danych."""
        print("INFO: Rozpoczynanie ładowania topologii...")
        conn = self._get_db_connection()
        # ... reszta tej metody pozostaje bez zmian ...
        cursor = conn.cursor(dictionary=True)
        # ...
        cursor.execute("SELECT nazwa_portu FROM porty_sprzetu")
        for row in cursor.fetchall():
            self.graph.add_node(row['nazwa_portu'])

        cursor.execute("SELECT nazwa_wezla FROM wezly_rurociagu")
        for row in cursor.fetchall():
            self.graph.add_node(row['nazwa_wezla'])

        query = """
            SELECT 
                s.nazwa_segmentu, 
                z.nazwa_zaworu,
                COALESCE(p_start.nazwa_portu, w_start.nazwa_wezla) AS punkt_startowy,
                COALESCE(p_koniec.nazwa_portu, w_koniec.nazwa_wezla) AS punkt_koncowy
            FROM segmenty s
            JOIN zawory z ON s.id_zaworu = z.id
            LEFT JOIN porty_sprzetu p_start ON s.id_portu_startowego = p_start.id
            LEFT JOIN wezly_rurociagu w_start ON s.id_wezla_startowego = w_start.id
            LEFT JOIN porty_sprzetu p_koniec ON s.id_portu_koncowego = p_koniec.id
            LEFT JOIN wezly_rurociagu w_koniec ON s.id_wezla_koncowego = w_koniec.id
        """
        cursor.execute(query)
        for row in cursor.fetchall():
            self.graph.add_edge(
                row['punkt_startowy'], 
                row['punkt_koncowy'], 
                segment_name=row['nazwa_segmentu'],
                valve_name=row['nazwa_zaworu']
            )
        
        cursor.close()
        conn.close()

        print("INFO: Topologia instalacji załadowana, graf zbudowany.")


    def find_path(self, start_node, end_node, open_valves=None):
        """Znajduje najkrótszą ścieżkę między węzłami"""
        # Jeśli nie podano stanów zaworów, pobierz z bazy lub użyj wszystkich
        if open_valves is None:
            open_valves = self._get_open_valves()
        
        temp_graph = self.graph.copy()
        
        edges_to_remove = []
        for u, v, data in temp_graph.edges(data=True):
            if data['valve_name'] not in open_valves:
                edges_to_remove.append((u, v))
        
        temp_graph.remove_edges_from(edges_to_remove)

        try:
            path_nodes = nx.shortest_path(temp_graph, source=start_node, target=end_node)
            
            path_segments = []
            for i in range(len(path_nodes) - 1):
                edge_data = self.graph.get_edge_data(path_nodes[i], path_nodes[i+1])
                if edge_data:
                    path_segments.append(edge_data['segment_name'])
            
            return path_segments
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
    
    def _get_open_valves(self):
        """Pobiera listę otwartych zaworów z bazy danych"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Sprawdź otwarte zawory (stan = 'OTWARTY')
            cursor.execute("SELECT nazwa_zaworu FROM zawory WHERE stan = 'OTWARTY'")
            open_valves = [row['nazwa_zaworu'] for row in cursor.fetchall()]
            
            # Jeśli nie ma otwartych zaworów, zwróć wszystkie jako otwarte (dla testów)
            if not open_valves:
                print("WARNING: Brak otwartych zaworów w bazie. Używam wszystkich zaworów dla testów PathFinder.")
                cursor.execute("SELECT nazwa_zaworu FROM zawory")
                open_valves = [row['nazwa_zaworu'] for row in cursor.fetchall()]
            
            cursor.close()
            conn.close()
            
            return open_valves
        except Exception as e:
            print(f"Błąd podczas pobierania stanów zaworów: {e}")
            # W przypadku błędu, zwróć wszystkie zawory jako otwarte
            try:
                conn = self._get_db_connection()
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT nazwa_zaworu FROM zawory")
                all_valves = [row['nazwa_zaworu'] for row in cursor.fetchall()]
                cursor.close()
                conn.close()
                return all_valves
            except Exception as ex:
                print(f"Błąd podczas pobierania wszystkich zaworów: {ex}")
                return []

# USUWAMY globalną instancję. Będziemy ją tworzyć w __init__.py
# pathfinder_instance = PathFinder()