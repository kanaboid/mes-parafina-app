# app/pathfinder_service.py
from .extensions import db
import networkx as nx
#from .db import get_db_connection  # Importujemy funkcję do połączenia z bazą danych
#import mysql.connector # Added for mysql.connector.Error
from .models import *


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

    # def _get_db_connection(self):
    #     """Prywatna metoda do łączenia się z bazą, używająca konfiguracji z aplikacji."""
    #     return get_db_connection()

    def _load_topology(self):
        """Wczytuje mapę instalacji z bazy danych przy użyciu SQLAlchemy ORM."""
        print("INFO: Rozpoczynanie ładowania topologii (wersja ORM)...")
        
        # Czyszczenie grafu przed ponownym załadowaniem
        self.graph.clear()

        # Pobieranie portów
        porty_q = db.select(PortySprzetu.nazwa_portu)
        porty = db.session.execute(porty_q).scalars().all()
        for nazwa_portu in porty:
            self.graph.add_node(nazwa_portu)

        # Pobieranie węzłów
        wezly_q = db.select(WezlyRurociagu.nazwa_wezla)
        wezly = db.session.execute(wezly_q).scalars().all()
        for nazwa_wezla in wezly:
            self.graph.add_node(nazwa_wezla)

        # Pobieranie segmentów z relacjami
        segmenty_q = db.select(Segmenty)
        segmenty = db.session.execute(segmenty_q).scalars().all()
        
        for segment in segmenty:
            punkt_startowy = segment.porty_sprzetu_.nazwa_portu if segment.porty_sprzetu_ else segment.wezly_rurociagu_.nazwa_wezla
            punkt_koncowy = segment.porty_sprzetu.nazwa_portu if segment.porty_sprzetu else segment.wezly_rurociagu.nazwa_wezla
            
            if punkt_startowy and punkt_koncowy:
                self.graph.add_edge(
                    punkt_startowy, 
                    punkt_koncowy, 
                    segment_name=segment.nazwa_segmentu,
                    valve_name=segment.zawory.nazwa_zaworu
                )
        
        print("INFO: Topologia instalacji załadowana (ORM), graf zbudowany.")


    def find_path(self, start_node, end_node, open_valves=None):
        """Znajduje najkrótszą ścieżkę między węzłami"""
        print(f"DEBUG: PathFinder.find_path called with start='{start_node}', end='{end_node}'")
        
        # Jeśli nie podano stanów zaworów, pobierz z bazy lub użyj wszystkich
        if open_valves is None:
            open_valves = self._get_open_valves()
        
        print(f"DEBUG: Using open_valves: {open_valves[:5]}... (total: {len(open_valves)})")
        
        # Sprawdź czy węzły istnieją w grafie
        if start_node not in self.graph.nodes():
            print(f"ERROR: Start node '{start_node}' not found in graph")
            print(f"Available nodes: {list(self.graph.nodes())[:10]}...")
            return None
            
        if end_node not in self.graph.nodes():
            print(f"ERROR: End node '{end_node}' not found in graph")
            print(f"Available nodes: {list(self.graph.nodes())[:10]}...")
            return None
        
        temp_graph = self.graph.copy()
        print(f"DEBUG: Temp graph has {len(temp_graph.nodes())} nodes and {len(temp_graph.edges())} edges")
        
        edges_to_remove = []
        for u, v, data in temp_graph.edges(data=True):
            if data['valve_name'] not in open_valves:
                edges_to_remove.append((u, v))
        
        print(f"DEBUG: Removing {len(edges_to_remove)} edges due to closed valves")
        temp_graph.remove_edges_from(edges_to_remove)
        print(f"DEBUG: After removal: {len(temp_graph.edges())} edges remain")

        try:
            path_nodes = nx.shortest_path(temp_graph, source=start_node, target=end_node)
            print(f"DEBUG: Found path nodes: {path_nodes}")
            
            path_segments = []
            for i in range(len(path_nodes) - 1):
                edge_data = self.graph.get_edge_data(path_nodes[i], path_nodes[i+1])
                if edge_data:
                    path_segments.append(edge_data['segment_name'])
            
            print(f"DEBUG: Path segments: {path_segments}")
            return path_segments
        except (nx.NetworkXNoPath, nx.NodeNotFound) as e:
            print(f"DEBUG: No path found - {type(e).__name__}: {e}")
            return None
    
    def _get_open_valves(self):
        """Pobiera listę otwartych zaworów z bazy danych (wersja ORM)."""
        try:
            # Używamy sesji i modelu Zawory do zbudowania zapytania
            query = db.select(Zawory.nazwa_zaworu).where(Zawory.stan == 'OTWARTY')
            open_valves = db.session.execute(query).scalars().all()
            
            # Logika awaryjna pozostaje bez zmian, ale również używa ORM
            if not open_valves:
                print("WARNING: Brak otwartych zaworów w bazie. Używam wszystkich zaworów dla testów PathFinder.")
                query_all = db.select(Zawory.nazwa_zaworu)
                open_valves = db.session.execute(query_all).scalars().all()
                
            return open_valves
        except Exception as e:
            print(f"Błąd podczas pobierania stanów zaworów (ORM): {e}")
            # W przypadku błędu, zachowanie awaryjne również używa ORM
            try:
                query_all = db.select(Zawory.nazwa_zaworu)
                return db.session.execute(query_all).scalars().all()
            except Exception as ex:
                print(f"Błąd podczas pobierania wszystkich zaworów (ORM): {ex}")
                return []

    @staticmethod
    def release_path(zawory_names=None, segment_names=None):
        """Zwalnia zasoby po zakończeniu operacji - zamyka zawory (wersja ORM)."""
        if not zawory_names:
            print("INFO: Brak zaworów do zwolnienia w release_path.")
            return

        try:
            if isinstance(zawory_names, str):
                zawory_names = zawory_names.split(',')

            if zawory_names:
                # Tworzymy zapytanie UPDATE za pomocą składni ORM
                stmt = db.update(Zawory).where(
                    Zawory.nazwa_zaworu.in_(zawory_names)
                ).values(stan='ZAMKNIETY')
                
                # Wykonujemy zapytanie i commitujemy transakcję
                db.session.execute(stmt)
                db.session.commit()
            
            print(f"INFO: Pomyślnie zamknięto zawory (ORM): {zawory_names}")

        except Exception as e:
            db.session.rollback()
            print(f"Błąd bazy danych podczas zwalniania ścieżki (ORM): {e}")
            raise

# USUWAMY globalną instancję. Będziemy ją tworzyć w __init__.py
# pathfinder_instance = PathFinder()