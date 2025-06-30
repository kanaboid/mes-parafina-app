Zmieniłem kod jak ponizej i zadzialalo:

# app/__init__.py

from flask import Flask
from .config import Config
from .pathfinder_service import PathFinder

# Tworzymy pustą instancję, która zostanie zainicjowana w create_app
pathfinder = PathFinder()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Inicjalizujemy serwis
    pathfinder.init_app(app)
    app.extensions = getattr(app, 'extensions', {})
    app.extensions['pathfinder'] = pathfinder

    # Rejestrujemy blueprinty
    from . import routes
    app.register_blueprint(routes.bp)

    @app.route('/hello')
    def hello():
        return "Witaj w aplikacji MES!"

    return app

# app/db.py

import mysql.connector
from flask import current_app

def get_db_connection(config=None):
    """Tworzy i zwraca nowe połączenie z bazą danych na podstawie podanej konfiguracji lub z current_app."""
    if config is None:
        config = current_app.config
    connection = mysql.connector.connect(
        host=config['MYSQL_HOST'],
        user=config['MYSQL_USER'],
        password=config['MYSQL_PASSWORD'],
        database=config['MYSQL_DB']
    )
    return connection

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


    def find_path(self, start_node, end_node, open_valves):
        # Ta metoda pozostaje bez zmian
        # ...
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
                path_segments.append(edge_data['segment_name'])
            
            return path_segments
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

# USUWAMY globalną instancję. Będziemy ją tworzyć w __init__.py
# pathfinder_instance = PathFinder()

# app/routes.py

from flask import Blueprint, jsonify, request, current_app
from datetime import datetime
import mysql.connector

from .db import get_db_connection  # Importujemy funkcję do połączenia z bazą danych
from .pathfinder_service import PathFinder

def get_pathfinder():
    """Pobiera instancję serwisu PathFinder z kontekstu aplikacji."""
    return current_app.extensions['pathfinder']

# 1. Stworzenie obiektu Blueprint
# Pierwszy argument to nazwa blueprintu, drugi to nazwa modułu (standardowo __name__)
# 'url_prefix' sprawi, że wszystkie endpointy w tym pliku będą zaczynać się od /api
bp = Blueprint('api', __name__, url_prefix='/api')



# 2. Stworzenie pierwszego, prawdziwego endpointu API
@bp.route('/sprzet', methods=['GET'])
def get_sprzet():
    """Zwraca listę całego sprzętu z bazy danych."""
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True) # dictionary=True zwraca wiersze jako słowniki
    
    query = "SELECT id, nazwa_unikalna, typ_sprzetu, pojemnosc_kg, stan_sprzetu FROM sprzet ORDER BY typ_sprzetu, nazwa_unikalna;"
    cursor.execute(query)
    
    sprzet_list = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify(sprzet_list)

# Endpoint do tworzenia nowej partii przez tankowanie
@bp.route('/operacje/tankowanie', methods=['POST'])
def tankowanie():
    # Pobranie danych JSON z żądania
    
    dane = request.get_json()
    if not dane:
        return jsonify({"status": "error", "message": "Brak danych w formacie JSON."}), 400

    # Podstawowa walidacja danych wejściowych
    wymagane_pola = ['id_sprzetu_zrodlowego', 'id_sprzetu_docelowego', 'typ_surowca', 'waga_kg', 'zrodlo_pochodzenia']
    if not all(pole in dane for pole in wymagane_pola):
        return jsonify({"status": "error", "message": "Brak wszystkich wymaganych pól."}), 400

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # --- POCZĄTEK TRANSAKCJI ---
        # Dzięki transakcji wszystkie poniższe operacje albo się udadzą w całości,
        # albo żadna z nich nie zostanie zapisana w razie błędu.
        conn.start_transaction()

        # KROK 1: Sprawdzenie, czy reaktor docelowy jest pusty
        cursor.execute("SELECT stan_sprzetu FROM sprzet WHERE id = %s", (dane['id_sprzetu_docelowego'],))
        stan_reaktora = cursor.fetchone()
        if not stan_reaktora or stan_reaktora[0] != 'Pusty':
             return jsonify({"status": "error", "message": "Reaktor docelowy nie jest pusty!"}), 409 # 409 Conflict

        # KROK 2: Stworzenie unikalnego kodu partii
        teraz = datetime.now()
        unikalny_kod = f"{dane['typ_surowca']}-{teraz.strftime('%Y%m%d-%H%M%S')}-{dane['zrodlo_pochodzenia'].upper()}"

        # KROK 3: Stworzenie nowej partii surowca
        sql_partia = """
            INSERT INTO partie_surowca 
            (unikalny_kod, typ_surowca, zrodlo_pochodzenia, waga_poczatkowa_kg, waga_aktualna_kg, id_sprzetu) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        partia_dane = (unikalny_kod, dane['typ_surowca'], dane['zrodlo_pochodzenia'], dane['waga_kg'], dane['waga_kg'], dane['id_sprzetu_docelowego'])
        cursor.execute(sql_partia, partia_dane)
        nowa_partia_id = cursor.lastrowid # Pobranie ID właśnie wstawionego wiersza

        # KROK 4: Nadanie statusu "Surowy"
        # ID statusu "Surowy" to 1 (zgodnie z naszymi danymi startowymi)
        cursor.execute("INSERT INTO partie_statusy (id_partii, id_statusu) VALUES (%s, %s)", (nowa_partia_id, 1))

        # KROK 5: Aktualizacja stanu reaktora docelowego
        cursor.execute("UPDATE sprzet SET stan_sprzetu = 'Zatankowany (surowy)' WHERE id = %s", (dane['id_sprzetu_docelowego'],))

        # KROK 6: Zapisanie operacji w logu
        sql_log = """
            INSERT INTO operacje_log 
            (typ_operacji, id_partii_surowca, id_sprzetu_zrodlowego, id_sprzetu_docelowego, czas_rozpoczecia, ilosc_kg, opis) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        log_dane = ('TRANSFER', nowa_partia_id, dane['id_sprzetu_zrodlowego'], dane['id_sprzetu_docelowego'], teraz, dane['waga_kg'], f"Tankowanie partii {unikalny_kod}")
        cursor.execute(sql_log, log_dane)
        
        # --- ZATWIERDZENIE TRANSAKCJI ---
        conn.commit()

        return jsonify({
            "status": "success", 
            "message": f"Partia {unikalny_kod} została pomyślnie utworzona i zatankowana.",
            "nowa_partia_id": nowa_partia_id
        }), 201 # 201 Created

    except mysql.connector.Error as err:
        # W razie błędu wycofaj wszystkie zmiany
        if conn:
            conn.rollback()
        return jsonify({"status": "error", "message": f"Błąd bazy danych: {err}"}), 500
    finally:
        # Zawsze zamykaj połączenie
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@bp.route('/operacje/rozpocznij_trase', methods=['POST'])
def rozpocznij_trase():
    dane = request.get_json()
    if not dane or not all(k in dane for k in ['start', 'cel', 'otwarte_zawory']):
        return jsonify({"status": "error", "message": "Brak wymaganych pól."}), 400

    start_point = dane['start'] # np. 'R3_OUT'
    end_point = dane['cel'] # np. 'R5_IN'
    open_valves_list = dane['otwarte_zawory'] # lista nazw zaworów, np. ['V_R2_R3', 'V_R1_R2', ...]

    
    # KROK 1: Znajdź ścieżkę używając naszego serwisu
    znaleziona_sciezka = get_pathfinder().find_path(start_point, end_point, open_valves_list)

    if not znaleziona_sciezka:
        return jsonify({
            "status": "error",
            "message": f"Nie znaleziono ścieżki z {start_point} do {end_point} przy podanym ustawieniu zaworów."
        }), 404

    # KROK 2: Sprawdź, czy segmenty na ścieżce nie są już zajęte
    # (To jest uproszczona wersja, w przyszłości trzeba pobrać ID segmentów)
    # Na razie zakładamy, że droga jest wolna.

    # KROK 3: Uruchom operację (symulacja)
    # - Zmień stan zaworów w bazie danych
    # - Stwórz wpis w operacje_log ze statusem 'aktywna'
    # - Stwórz wpisy w log_uzyte_segmenty dla każdego segmentu na ścieżce

    # Na razie tylko zwracamy znalezioną ścieżkę
    return jsonify({
        "status": "success",
        "message": "Trasa została pomyślnie znaleziona i zwalidowana.",
        "trasa": {
            "start": start_point,
            "cel": end_point,
            "wymagane_segmenty": znaleziona_sciezka
        }
    }), 200