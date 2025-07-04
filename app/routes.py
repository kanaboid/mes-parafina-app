# app/routes.py

from flask import Blueprint, jsonify, request, current_app, render_template
from datetime import datetime, timedelta
from .sensors import SensorService  # Importujemy serwis czujników
import mysql.connector
import time
from .db import get_db_connection  # Importujemy funkcję do połączenia z bazą danych
from .pathfinder_service import PathFinder
from mysql.connector.errors import OperationalError

def get_pathfinder():
    """Pobiera instancję serwisu PathFinder z kontekstu aplikacji."""
    return current_app.extensions['pathfinder']

def get_sensor_service():
    """Pobiera instancję serwisu SensorService z kontekstu aplikacji."""
    return current_app.extensions['sensor_service']

# 1. Stworzenie obiektu Blueprint
# Pierwszy argument to nazwa blueprintu, drugi to nazwa modułu (standardowo __name__)
# 'url_prefix' sprawi, że wszystkie endpointy w tym pliku będą zaczynać się od /api
bp = Blueprint('api', __name__, url_prefix='/')
# sensor_service = SensorService()



@bp.route('/')
def index():
    """Serwuje główną stronę aplikacji (frontend)."""
    return render_template('index.html')

# --- DODAJ TĘ NOWĄ FUNKCJĘ ---
@bp.route('/alarms')
def show_alarms():
    """Wyświetla stronę z historią wszystkich alarmów."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Pobierz wszystkie alarmy, sortując od najnowszych
        cursor.execute("""
            SELECT * FROM alarmy 
            ORDER BY czas_wystapienia DESC
        """)
        all_alarms = cursor.fetchall()
        return render_template('alarms.html', alarms=all_alarms)
    finally:
        cursor.close()
        conn.close()
# --- KONIEC NOWEJ FUNKCJI ---

# 2. Stworzenie pierwszego, prawdziwego endpointu API
@bp.route('/api/sprzet', methods=['GET'])
def get_sprzet():
    """Zwraca listę całego sprzętu WRAZ z informacją o znajdującej się w nim partii."""
    from .db import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Używamy LEFT JOIN, aby pokazać sprzęt nawet jeśli jest pusty
    query = """
        SELECT 
            s.id, s.nazwa_unikalna, s.typ_sprzetu, s.stan_sprzetu,
            /* Używamy ANY_VALUE() dla wszystkich kolumn z tabeli 'p', 
               które nie są w GROUP BY ani w funkcji agregującej */
            ANY_VALUE(p.id) as id_partii, 
            ANY_VALUE(p.unikalny_kod) as unikalny_kod, 
            ANY_VALUE(p.typ_surowca) as typ_surowca, 
            ANY_VALUE(p.waga_aktualna_kg) as waga_aktualna_kg,
            
            /* Ta kolumna już jest zagregowana, więc jej nie ruszamy */
            GROUP_CONCAT(st.nazwa_statusu SEPARATOR ', ') AS statusy_partii
        FROM sprzet s
        LEFT JOIN partie_surowca p ON s.id = p.id_sprzetu
        LEFT JOIN partie_statusy ps ON p.id = ps.id_partii
        LEFT JOIN statusy st ON ps.id_statusu = st.id
        GROUP BY s.id  /* Grupowanie pozostaje bez zmian */
        ORDER BY s.typ_sprzetu, s.nazwa_unikalna;
    """
    cursor.execute(query)
    sprzet_list = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify(sprzet_list)

# Endpoint do tworzenia nowej partii przez tankowanie
@bp.route('/api/operacje/tankowanie', methods=['POST'])
def tankowanie():
    dane = request.get_json()
    
    # Validation
    wymagane_pola = ['nazwa_portu_zrodlowego', 'nazwa_portu_docelowego', 
                     'typ_surowca', 'waga_kg', 'zrodlo_pochodzenia']
    if not dane or not all(k in dane for k in wymagane_pola):
        return jsonify({'message': 'Brak wymaganych danych'}), 400

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Get equipment IDs from port names
        cursor.execute("""
            SELECT s.id, s.nazwa_unikalna 
            FROM porty_sprzetu p 
            JOIN sprzet s ON p.id_sprzetu = s.id 
            WHERE p.nazwa_portu = %s
        """, (dane['nazwa_portu_zrodlowego'],))
        zrodlo = cursor.fetchone()
        
        cursor.execute("""
            SELECT s.id, s.nazwa_unikalna 
            FROM porty_sprzetu p 
            JOIN sprzet s ON p.id_sprzetu = s.id 
            WHERE p.nazwa_portu = %s
        """, (dane['nazwa_portu_docelowego'],))
        cel = cursor.fetchone()

        if not zrodlo or not cel:
            return jsonify({'message': 'Nieprawidłowy port źródłowy lub docelowy'}), 400

        id_zrodla = zrodlo['id']
        id_celu = cel['id']

        # Check if target reactor is empty
        cursor.execute("SELECT stan_sprzetu FROM sprzet WHERE id = %s", (id_celu,))
        stan_reaktora = cursor.fetchone()
        
        if not stan_reaktora or stan_reaktora['stan_sprzetu'] != 'Pusty':
            return jsonify({
                'message': f"Reaktor docelowy nie jest pusty (stan: {stan_reaktora['stan_sprzetu'] if stan_reaktora else 'nieznany'})"
            }), 400

        # Krok 4: Stworzenie unikalnego kodu partii
        teraz = datetime.now()
        unikalny_kod = f"{dane['typ_surowca']}-{teraz.strftime('%Y%m%d-%H%M%S')}-{dane['zrodlo_pochodzenia'].upper()}"

        # Krok 5: Stworzenie nowej partii surowca
        sql_partia = """
            INSERT INTO partie_surowca 
            (unikalny_kod, typ_surowca, zrodlo_pochodzenia, waga_poczatkowa_kg, waga_aktualna_kg, id_sprzetu) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        # UŻYCIE ZMIENNEJ `id_celu`
        partia_dane = (unikalny_kod, dane['typ_surowca'], dane['zrodlo_pochodzenia'], dane['waga_kg'], dane['waga_kg'], id_celu)
        cursor.execute(sql_partia, partia_dane)
        nowa_partia_id = cursor.lastrowid

        # Krok 6: Nadanie statusu "Surowy"
        cursor.execute("INSERT IGNORE INTO partie_statusy (id_partii, id_statusu) VALUES (%s, 1)", (nowa_partia_id,))

        # Krok 7: Aktualizacja stanu reaktora docelowego
        # UŻYCIE ZMIENNEJ `id_celu`
        cursor.execute("UPDATE sprzet SET stan_sprzetu = 'Zatankowany (surowy)' WHERE id = %s", (id_celu,))

        # Krok 8: Zapisanie operacji w logu
        sql_log = """
            INSERT INTO operacje_log 
            (typ_operacji, id_partii_surowca, id_sprzetu_zrodlowego, id_sprzetu_docelowego, czas_rozpoczecia, ilosc_kg, opis, status_operacji) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'zakonczona')
        """
        # UŻYCIE ZMIENNYCH `id_zrodla` i `id_celu`
        log_dane = ('TRANSFER', nowa_partia_id, id_zrodla, id_celu, teraz, dane['waga_kg'], f"Tankowanie partii {unikalny_kod}")
        cursor.execute(sql_log, log_dane)
        
        conn.commit()
        return jsonify({'message': 'Tankowanie rozpoczęte pomyślnie'}), 201

    except mysql.connector.Error as err:
        if conn: 
            conn.rollback()
        return jsonify({'message': f'Błąd bazy danych: {str(err)}'}), 500
    finally:
        if conn and conn.is_connected():
            conn.close()

@bp.route('/api/operacje/rozpocznij_trase', methods=['POST'])
def rozpocznij_trase():
    dane = request.get_json()
    if not dane or not all(k in dane for k in ['start', 'cel', 'otwarte_zawory', 'typ_operacji']):
        return jsonify({"status": "error", "message": "Brak wymaganych pól: start, cel, otwarte_zawory, typ_operacji."}), 400

    start_point = dane['start']
    end_point = dane['cel']
    open_valves_list = dane['otwarte_zawory']
    typ_operacji = dane['typ_operacji']
    sprzet_posredni = dane.get('sprzet_posredni')
    
    pathfinder = get_pathfinder()
    znaleziona_sciezka_nazwy = []

    # --- POPRAWIONA LOGIKA ZNAJDOWANIA TRASY ---
    if sprzet_posredni:
        # Jeśli jest sprzęt pośredni (np. filtr), szukamy trasy w dwóch częściach.
        posredni_in = f"{sprzet_posredni}_IN"
        posredni_out = f"{sprzet_posredni}_OUT"

        sciezka_1 = pathfinder.find_path(start_point, posredni_in, open_valves_list)
        if not sciezka_1:
            return jsonify({"status": "error", "message": f"Nie znaleziono ścieżki z {start_point} do {posredni_in}."}), 404
        
        sciezka_wewnetrzna = pathfinder.find_path(posredni_in, posredni_out, open_valves_list)
        if not sciezka_wewnetrzna:
            return jsonify({"status": "error", "message": f"Nie znaleziono ścieżki wewnętrznej w {sprzet_posredni} (z {posredni_in} do {posredni_out})."}), 404

        sciezka_2 = pathfinder.find_path(posredni_out, end_point, open_valves_list)
        if not sciezka_2:
            return jsonify({"status": "error", "message": f"Nie znaleziono ścieżki z {posredni_out} do {end_point}."}), 404

        znaleziona_sciezka_nazwy = sciezka_1 + sciezka_wewnetrzna + sciezka_2
    else:
        # Jeśli nie ma punktu pośredniego (np. przelew bezpośredni), szukamy jednej, ciągłej ścieżki.
        znaleziona_sciezka_nazwy = pathfinder.find_path(start_point, end_point, open_valves_list)

    # Sprawdzamy, czy ostatecznie udało się znaleźć trasę.
    if not znaleziona_sciezka_nazwy:
        return jsonify({
            "status": "error",
            "message": f"Nie znaleziono kompletnej ścieżki z {start_point} do {end_point} przy podanym ustawieniu zaworów."
        }), 404

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)



        # KROK 1.5: ZNAJDŹ PARTIĘ W REAKTORZE STARTOWYM
        # NOWA LOGIKA: Automatyczne znajdowanie partii w urządzeniu startowym.
        # Na podstawie nazwy portu startowego znajdujemy ID sprzętu, a potem ID partii w tym sprzęcie.
        sql_znajdz_partie = """
            SELECT p.id FROM partie_surowca p
            JOIN porty_sprzetu ps ON p.id_sprzetu = ps.id_sprzetu
            WHERE ps.nazwa_portu = %s
        """
        cursor.execute(sql_znajdz_partie, (start_point,))
        partia = cursor.fetchone()

        if not partia:
            return jsonify({"status": "error", "message": f"W urządzeniu startowym ({start_point}) nie znaleziono żadnej partii."}), 404
        
        # Mamy ID partii, będziemy go używać do zapisu w logu.
        id_partii = partia['id']

        # KROK 2: Sprawdź konflikty
        placeholders_konflikt = ', '.join(['%s'] * len(znaleziona_sciezka_nazwy))
        sql_konflikt = f"""
            SELECT s.nazwa_segmentu FROM log_uzyte_segmenty lus
            JOIN operacje_log ol ON lus.id_operacji_log = ol.id
            JOIN segmenty s ON lus.id_segmentu = s.id
            WHERE ol.status_operacji = 'aktywna' AND s.nazwa_segmentu IN ({placeholders_konflikt})
        """
        cursor.execute(sql_konflikt, znaleziona_sciezka_nazwy)
        konflikty = cursor.fetchall()

        if konflikty:
            nazwy_zajetych = [k['nazwa_segmentu'] for k in konflikty]
            
            conn.rollback() 
            return jsonify({
                "status": "error", "message": "Konflikt zasobów.",
                "zajete_segmenty": [k['nazwa_segmentu'] for k in konflikty]
            }), 409

        # --- KROK 3: URUCHOMIENIE OPERACJI W TRANSAKCJI ---
       
        # Używamy nowego kursora bez `dictionary=True` do operacji zapisu
        write_cursor = conn.cursor()

        # 3a. Zaktualizuj stan zaworów
        placeholders_zawory = ', '.join(['%s'] * len(open_valves_list))
        sql_zawory = f"UPDATE zawory SET stan = 'OTWARTY' WHERE nazwa_zaworu IN ({placeholders_zawory})"
        write_cursor.execute(sql_zawory, open_valves_list)

        # 3b. Stwórz nową operację w logu
        opis_operacji = f"Operacja {typ_operacji} z {start_point} do {end_point}"
        sql_log = """
            INSERT INTO operacje_log 
            (typ_operacji, id_partii_surowca, status_operacji, czas_rozpoczecia, opis, punkt_startowy, punkt_docelowy) 
            VALUES (%s, %s, 'aktywna', NOW(), %s, %s, %s)
        """
        # Używamy teraz `id_partii` znalezionego automatycznie.
        write_cursor.execute(sql_log, (typ_operacji, id_partii, opis_operacji, start_point, end_point))
        nowa_operacja_id = write_cursor.lastrowid

        # 3c. Pobierz ID segmentów na trasie
        placeholders_segmenty = ', '.join(['%s'] * len(znaleziona_sciezka_nazwy))
        sql_id_segmentow = f"SELECT id FROM segmenty WHERE nazwa_segmentu IN ({placeholders_segmenty})"
        # Używamy z powrotem kursora z dictionary=True do odczytu
        cursor.execute(sql_id_segmentow, znaleziona_sciezka_nazwy)
        id_segmentow = [row['id'] for row in cursor.fetchall()]

        # 3d. Zablokuj segmenty
        sql_blokada = "INSERT INTO log_uzyte_segmenty (id_operacji_log, id_segmentu) VALUES (%s, %s)"
        dane_do_blokady = [(nowa_operacja_id, id_seg) for id_seg in id_segmentow]
        write_cursor.executemany(sql_blokada, dane_do_blokady)

        # 3e. Zatwierdź transakcję
        conn.commit()
        
        return jsonify({
            "status": "success",
            "message": "Operacja została pomyślnie rozpoczęta.",
            "id_operacji": nowa_operacja_id,
            "trasa": {
                "start": start_point,
                "cel": end_point,
                "uzyte_segmenty": znaleziona_sciezka_nazwy
            }
        }), 201 # 201 Created

    except mysql.connector.Error as err:
        if conn:
            conn.rollback() # Wycofaj zmiany w razie błędu
        return jsonify({"status": "error", "message": f"Błąd bazy danych: {err}"}), 500
    finally:
        if conn and conn.is_connected():
            # Zamykamy oba kursory
            if 'cursor' in locals() and cursor: cursor.close()
            if 'write_cursor' in locals() and write_cursor: write_cursor.close()
            conn.close()

# app/routes.py

@bp.route('/api/operacje/zakoncz', methods=['POST'])
def zakoncz_operacje():
    dane = request.get_json()
    if not dane or 'id_operacji' not in dane:
        return jsonify({"status": "error", "message": "Brak wymaganego pola: id_operacji."}), 400

    id_operacji = dane['id_operacji']

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # KROK 1: Sprawdź, czy operacja istnieje i jest aktywna
        # Dodajemy `punkt_startowy`, aby wiedzieć, który reaktor opróżnić
        sql_operacja = """
            SELECT status_operacji, typ_operacji, id_partii_surowca, punkt_startowy, punkt_docelowy 
            FROM operacje_log 
            WHERE id = %s
        """
        cursor.execute(sql_operacja, (id_operacji,))
        operacja = cursor.fetchone()

        if not operacja:
            return jsonify({"status": "error", "message": f"Operacja o ID {id_operacji} nie istnieje."}), 404
        if operacja['status_operacji'] != 'aktywna':
            return jsonify({
                "status": "error", 
                "message": f"Nie można zakończyć operacji, ponieważ nie jest aktywna (status: {operacja['status_operacji']})."
            }), 409

        # --- POCZĄTEK TRANSAKCJI ---
        write_cursor = conn.cursor()

        # KROK 2: Zmień status operacji
        sql_zakoncz = "UPDATE operacje_log SET status_operacji = 'zakonczona', czas_zakonczenia = NOW() WHERE id = %s"
        write_cursor.execute(sql_zakoncz, (id_operacji,))

        # KROK 3: Znajdź i zamknij zawory
        sql_znajdz_zawory = """
            SELECT DISTINCT z.nazwa_zaworu FROM zawory z
            JOIN segmenty s ON z.id = s.id_zaworu
            JOIN log_uzyte_segmenty lus ON s.id = lus.id_segmentu
            WHERE lus.id_operacji_log = %s
        """
        cursor.execute(sql_znajdz_zawory, (id_operacji,))
        zawory_do_zamkniecia = [row['nazwa_zaworu'] for row in cursor.fetchall()]

        if zawory_do_zamkniecia:
            placeholders = ', '.join(['%s'] * len(zawory_do_zamkniecia))
            sql_zamknij_zawory = f"UPDATE zawory SET stan = 'ZAMKNIETY' WHERE nazwa_zaworu IN ({placeholders})"
            write_cursor.execute(sql_zamknij_zawory, zawory_do_zamkniecia)
        
        # KROK 4: Aktualizacja lokalizacji partii i stanu sprzętu
        typ_op = operacja['typ_operacji']
        id_partii = operacja['id_partii_surowca']
        punkt_startowy = operacja['punkt_startowy']
        punkt_docelowy = operacja['punkt_docelowy']

        # Sprawdzamy, czy operacja była przelewem (a nie np. operacją "w koło")
        if id_partii and punkt_startowy and punkt_docelowy and punkt_startowy != punkt_docelowy:
            # Znajdź ID sprzętu docelowego
            cursor.execute("SELECT id_sprzetu FROM porty_sprzetu WHERE nazwa_portu = %s", (punkt_docelowy,))
            sprzet_docelowy = cursor.fetchone()
            
            # Znajdź ID sprzętu źródłowego
            cursor.execute("SELECT id_sprzetu FROM porty_sprzetu WHERE nazwa_portu = %s", (punkt_startowy,))
            sprzet_zrodlowy = cursor.fetchone()

            if sprzet_docelowy and sprzet_zrodlowy:
                id_sprzetu_docelowego = sprzet_docelowy['id_sprzetu']
                id_sprzetu_zrodlowego = sprzet_zrodlowy['id_sprzetu']
                
                # 1. Przenieś partię do nowego miejsca
                sql_przenies = "UPDATE partie_surowca SET id_sprzetu = %s WHERE id = %s"
                write_cursor.execute(sql_przenies, (id_sprzetu_docelowego, id_partii))
                
                # 2. Zaktualizuj stan sprzętu
                write_cursor.execute("UPDATE sprzet SET stan_sprzetu = 'Zatankowany' WHERE id = %s", (id_sprzetu_docelowego,))
                write_cursor.execute("UPDATE sprzet SET stan_sprzetu = 'Pusty' WHERE id = %s", (id_sprzetu_zrodlowego,))

        # KROK 5: Zatwierdź transakcję
        conn.commit()

        return jsonify({
            "status": "success",
            "message": f"Operacja o ID {id_operacji} została pomyślnie zakończona.",
            "zamkniete_zawory": zawory_do_zamkniecia
        }), 200

    except mysql.connector.Error as err:
        if conn: conn.rollback()
        return jsonify({"status": "error", "message": f"Błąd bazy danych: {err}"}), 500
    finally:
        if conn and conn.is_connected():
            if 'cursor' in locals(): cursor.close()
            if 'write_cursor' in locals(): write_cursor.close()
            conn.close()

@bp.route('/api/zawory', methods=['GET'])
def get_wszystkie_zawory():
    """Zwraca listę wszystkich zaworów i ich aktualny stan."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nazwa_zaworu, stan FROM zawory ORDER BY nazwa_zaworu")
    zawory = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(zawory)

@bp.route('/api/zawory/zmien_stan', methods=['POST'])
def zmien_stan_zaworu():
    """Zmienia stan pojedynczego zaworu."""
    dane = request.get_json()
    if not dane or 'id_zaworu' not in dane or 'stan' not in dane:
        return jsonify({"status": "error", "message": "Brak wymaganych pól: id_zaworu, stan."}), 400
    
    id_zaworu = dane['id_zaworu']
    nowy_stan = dane['stan'] # Oczekujemy 'OTWARTY' lub 'ZAMKNIETY'

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE zawory SET stan = %s WHERE id = %s", (nowy_stan, id_zaworu))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"status": "success", "message": f"Zmieniono stan zaworu {id_zaworu} na {nowy_stan}."})

@bp.route('/api/operacje/aktywne', methods=['GET'])
def get_aktywne_operacje():
    """Zwraca listę wszystkich operacji ze statusem 'aktywna'."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT id, typ_operacji, id_partii_surowca, czas_rozpoczecia, opis 
        FROM operacje_log 
        WHERE status_operacji = 'aktywna'
        ORDER BY czas_rozpoczecia DESC
    """
    cursor.execute(query)
    operacje = cursor.fetchall()
    cursor.close()
    conn.close()
    # Musimy przekonwertować datetime na string, bo JSON nie ma typu daty
    for op in operacje:
        op['czas_rozpoczecia'] = op['czas_rozpoczecia'].strftime('%Y-%m-%d %H:%M:%S')
    return jsonify(operacje)

# app/routes.py
# ...

@bp.route('/api/punkty_startowe', methods=['GET'])
def get_punkty_startowe():
    """Zwraca listę wszystkich portów wyjściowych (OUT)."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Wybieramy porty ze sprzętu, który może być źródłem (np. nie beczki czyste)
    query = """
        SELECT p.nazwa_portu, s.nazwa_unikalna as nazwa_sprzetu 
        FROM porty_sprzetu p
        JOIN sprzet s ON p.id_sprzetu = s.id
        WHERE p.typ_portu = 'OUT' AND s.typ_sprzetu != 'beczka_czysta'
        ORDER BY s.nazwa_unikalna
    """
    cursor.execute(query)
    porty = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(porty)

@bp.route('/api/punkty_docelowe', methods=['GET'])
def get_punkty_docelowe():
    """Zwraca listę wszystkich portów wejściowych (IN)."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Wybieramy porty ze sprzętu, który może być celem (np. nie beczki brudne)
    query = """
        SELECT p.nazwa_portu, s.nazwa_unikalna as nazwa_sprzetu 
        FROM porty_sprzetu p
        JOIN sprzet s ON p.id_sprzetu = s.id
        WHERE p.typ_portu = 'IN' AND s.typ_sprzetu NOT IN ('beczka_brudna', 'apollo')
        ORDER BY s.nazwa_unikalna
    """
    cursor.execute(query)
    porty = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(porty)

@bp.route('/api/sprzet/filtry', methods=['GET'])
def get_filtry():
    """Zwraca listę filtrów."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT nazwa_unikalna FROM sprzet WHERE typ_sprzetu = 'filtr'")
    filtry = [row['nazwa_unikalna'] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return jsonify(filtry)

# app/routes.py
# ...

# app/routes.py
# ...

@bp.route('/api/topologia', methods=['GET'])
def get_topologia():
    """Zwraca pełną listę połączeń (segmentów) do wizualizacji."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # To samo zapytanie, którego używa PathFinder do budowy grafu
    query = """
        SELECT 
            s.id as id_segmentu,
            s.nazwa_segmentu, 
            z.nazwa_zaworu,
            z.stan as stan_zaworu,
            -- Dodajemy ID dla debugowania
            s.id_portu_startowego, s.id_wezla_startowego,
            s.id_portu_koncowego, s.id_wezla_koncowego,
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
    segmenty = cursor.fetchall()

    # Dodatkowo, pobierzmy listę aktualnie zajętych segmentów
    sql_zajete = """
        SELECT s.id as id_segmentu FROM log_uzyte_segmenty lus
        JOIN operacje_log ol ON lus.id_operacji_log = ol.id
        JOIN segmenty s ON lus.id_segmentu = s.id
        WHERE ol.status_operacji = 'aktywna'
    """
    cursor.execute(sql_zajete)
    zajete_ids = {row['id_segmentu'] for row in cursor.fetchall()}

    # Dodaj informację o zajętości do każdego segmentu
    for seg in segmenty:
        seg['zajety'] = seg['id_segmentu'] in zajete_ids

    cursor.close()
    conn.close()
    return jsonify(segmenty)



@bp.route('/api/trasy/sugeruj', methods=['POST'])
def sugeruj_trase():
    """
    Na podstawie punktu startowego, końcowego i pośredniego, znajduje
    najkrótszą możliwą trasę i zwraca listę segmentów oraz zaworów
    potrzebnych do jej otwarcia. Ignoruje aktualny stan zaworów.
    """
    dane = request.get_json()
    if not dane or 'start' not in dane or 'cel' not in dane:
        return jsonify({"status": "error", "message": "Brak wymaganych pól: start, cel."}), 400

    start_point = dane['start']
    end_point = dane['cel']
    sprzet_posredni = dane.get('sprzet_posredni')
    
    pathfinder = get_pathfinder()
    
    # WAŻNE: Do szukania "idealnej" trasy przekazujemy WSZYSTKIE zawory jako otwarte.
    # W tym celu pobieramy ich nazwy z grafu Pathfindera.
    wszystkie_zawory = [data['valve_name'] for u, v, data in pathfinder.graph.edges(data=True)]
    
    sciezka_segmentow = []
    sciezka_zaworow = set() # Używamy seta, aby uniknąć duplikatów zaworów

    try :
        if sprzet_posredni:
            posredni_in = f"{sprzet_posredni}_IN"
            posredni_out = f"{sprzet_posredni}_OUT"

            # Trasa do sprzętu pośredniego
            sciezka_1 = pathfinder.find_path(start_point, posredni_in, wszystkie_zawory)
            # Trasa wewnątrz sprzętu pośredniego
            sciezka_wewnetrzna = pathfinder.find_path(posredni_in, posredni_out, wszystkie_zawory)
            # Trasa od sprzętu pośredniego do celu
            sciezka_2 = pathfinder.find_path(posredni_out, end_point, wszystkie_zawory)

            if not all([sciezka_1, sciezka_wewnetrzna, sciezka_2]):
                raise Exception("Nie można zbudować pełnej trasy przez punkt pośredni.")

            sciezka_segmentow = sciezka_1 + sciezka_wewnetrzna + sciezka_2
        else:
            sciezka_segmentow = pathfinder.find_path(start_point, end_point, wszystkie_zawory)

        if not sciezka_segmentow:
            raise Exception("Nie znaleziono ścieżki.")

        # Na podstawie nazw segmentów, znajdź nazwy przypisanych do nich zaworów
        for segment_name in sciezka_segmentow:
            # Przeszukujemy krawędzie grafu, aby znaleźć zawór dla danego segmentu
            for u, v, data in pathfinder.graph.edges(data=True):
                if data['segment_name'] == segment_name:
                    sciezka_zaworow.add(data['valve_name'])
                    break
        
        return jsonify({
            "status": "success",
            "sugerowane_zawory": sorted(list(sciezka_zaworow)),
            "segmenty_trasy": sciezka_segmentow
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Nie można było wytyczyć trasy: {e}"
        }), 404

# app/routes.py
# ...

@bp.route('/api/operacje/dobielanie', methods=['POST'])
def dobielanie():
    dane = request.get_json()
    if not dane or not all(k in dane for k in ['id_reaktora', 'ilosc_workow', 'waga_worka_kg']):
        return jsonify({"status": "error", "message": "Brak wymaganych pól: id_reaktora, ilosc_workow, waga_worka_kg."}), 400

    id_reaktora = dane['id_reaktora']
    ilosc_workow = dane['ilosc_workow']
    waga_worka_kg = dane['waga_worka_kg']
    dodana_waga = ilosc_workow * waga_worka_kg

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Znajdź partię w podanym reaktorze
        cursor.execute("SELECT id FROM partie_surowca WHERE id_sprzetu = %s", (id_reaktora,))
        partia = cursor.fetchone()
        if not partia:
            return jsonify({"status": "error", "message": f"W reaktorze o ID {id_reaktora} nie znaleziono żadnej partii."}), 404
        
        id_partii = partia['id']

        # --- Transakcja ---
        write_cursor = conn.cursor()

        # 1. Dodaj wpis do operacje_log
        opis = f"Dodano {ilosc_workow} worków ziemi ({dodana_waga} kg) do partii {id_partii}"
        sql_log = "INSERT INTO operacje_log (typ_operacji, id_partii_surowca, czas_rozpoczecia, status_operacji, opis, ilosc_kg) VALUES ('DOBIELANIE', %s, NOW(), 'zakonczona', %s, %s)"
        write_cursor.execute(sql_log, (id_partii, opis, dodana_waga))

        # 2. Zaktualizuj wagę partii
        sql_waga = "UPDATE partie_surowca SET waga_aktualna_kg = waga_aktualna_kg + %s WHERE id = %s"
        write_cursor.execute(sql_waga, (dodana_waga, id_partii))

        # 3. Dodaj status "Dobielony" do partii
        # Załóżmy, że ID statusu "Dobielony" to 3
        # Używamy INSERT IGNORE, aby uniknąć błędu, jeśli partia już ma ten status
        sql_status = "INSERT IGNORE INTO partie_statusy (id_partii, id_statusu) VALUES (%s, 3)"
        write_cursor.execute(sql_status, (id_partii,))
        
        conn.commit()

        return jsonify({"status": "success", "message": opis}), 200

    except mysql.connector.Error as err:
        if conn: conn.rollback()
        return jsonify({"status": "error", "message": f"Błąd bazy danych: {err}"}), 500
    finally:
        if conn and conn.is_connected():

            cursor.close()
            conn.close()
            # ... zamknięcie kursorów i połączenia ...

@bp.route('/api/alarmy/aktywne', methods=['GET'])
def get_aktywne_alarmy():
    """Zwraca listę aktywnych alarmów"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT id, typ_alarmu, nazwa_sprzetu, wartosc, limit_przekroczenia, 
                   czas_wystapienia, status_alarmu 
            FROM alarmy 
            WHERE status_alarmu = 'AKTYWNY'
            ORDER BY czas_wystapienia DESC
        """)
        alarmy = cursor.fetchall()
        
        # Konwertuj datetime na string
        for alarm in alarmy:
            alarm['czas_wystapienia'] = alarm['czas_wystapienia'].strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify(alarmy)
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/test/sensors', methods=['POST'])
def test_sensors():
    """Endpoint testowy do wymuszenia odczytu czujników"""
    try:
        sensor_service = get_sensor_service() # <--- ZMIEŃ TĘ LINIĘ
        sensor_service.read_sensors()
        return jsonify({'message': 'Odczyt czujników wykonany pomyślnie'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/pomiary/historia', methods=['GET'])
def get_historia_pomiarow():
    """Pobiera historię pomiarów z ostatnich 24 godzin"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Pobierz dane z ostatnich 24h
        cursor.execute("""
            SELECT h.*, s.nazwa_unikalna, s.typ_sprzetu
            FROM historia_pomiarow h
            JOIN sprzet s ON h.id_sprzetu = s.id
            WHERE h.czas_pomiaru > %s
            ORDER BY h.czas_pomiaru DESC
        """, (datetime.now() - timedelta(hours=24),))
        
        pomiary = cursor.fetchall()
        
        # Formatuj daty do JSON
        for pomiar in pomiary:
            pomiar['czas_pomiaru'] = pomiar['czas_pomiaru'].strftime('%Y-%m-%d %H:%M:%S')
            
        return jsonify(pomiary)
        
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/alarmy/potwierdz', methods=['POST'])
def potwierdz_alarm():
    """Endpoint do potwierdzania alarmów"""
    dane = request.get_json()
    id_alarmu = dane.get('id_alarmu')
    
    if not id_alarmu:
        return jsonify({'message': 'Brak ID alarmu'}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE alarmy 
            SET status_alarmu = 'POTWIERDZONY',
                czas_potwierdzenia = %s
            WHERE id = %s AND status_alarmu = 'AKTYWNY'
        """, (datetime.now(), id_alarmu))
        
        conn.commit()
        
        if cursor.rowcount == 0:
            return jsonify({'message': 'Alarm nie znaleziony lub już potwierdzony'}), 404
            
        return jsonify({'message': 'Alarm potwierdzony pomyślnie'})
        
    except Exception as e:
        conn.rollback()
        return jsonify({'message': f'Błąd bazy danych: {str(e)}'}), 500
        
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/test/alarm', methods=['POST'])
def test_alarm():
    """Endpoint do testowania alarmów"""
    try:
        dane = request.get_json()
        if not dane:
            return jsonify({'message': 'Brak danych w żądaniu'}), 400
            
        sprzet_id = dane.get('sprzet_id')
        typ_alarmu = dane.get('typ_alarmu', 'temperatura')
        
        if not sprzet_id:
            return jsonify({'message': 'Brak ID sprzętu'}), 400
            
        if typ_alarmu not in ['temperatura', 'cisnienie']:
            return jsonify({'message': 'Nieprawidłowy typ alarmu'}), 400
        sensor_service = get_sensor_service() # <--- ZMIEŃ TĘ LINIĘ    
        sensor_service.force_alarm(sprzet_id, typ_alarmu)
        return jsonify({'message': f'Wymuszono alarm {typ_alarmu} dla sprzętu ID={sprzet_id}'})
        
    except ValueError as ve:
        return jsonify({'message': str(ve)}), 400
    except Exception as e:
        return jsonify({'message': f'Błąd serwera: {str(e)}'}), 500

@bp.route('/api/sprzet/<int:sprzet_id>/temperatura', methods=['POST'])
def set_temperatura(sprzet_id):
    """Ustawia docelową temperaturę dla danego sprzętu."""
    dane = request.get_json()
    nowa_temperatura = dane['temperatura']
    
    try:
        # Delegujemy całą pracę do serwisu
        sensor_service = get_sensor_service()
        sensor_service.set_temperature(sprzet_id, nowa_temperatura)
        
        return jsonify({"status": "success", "message": "Temperatura ustawiona."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Błąd serwera: {e}"}), 500
    

@bp.route('/filtry')
def show_filtry_panel():
    """Renderuje stronę z panelem monitoringu filtrów."""
    return render_template('filtry.html')

@bp.route('/api/filtry/status')
def get_filtry_status():
    """
    Zwraca szczegółowy, aktualny status dla każdego filtra (FZ i FN),
    wzbogacony o informacje o aktywnej operacji i partii.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Krok 1: Pobierz wszystkie filtry i ich podstawowy status
        cursor.execute("SELECT id, nazwa_unikalna, stan_sprzetu FROM sprzet WHERE typ_sprzetu = 'filtr'")
        filtry = {f['nazwa_unikalna']: f for f in cursor.fetchall()}
        
        # Przygotuj domyślną odpowiedź
        wynik = {
            'FZ': {'id_filtra': filtry.get('FZ', {}).get('id'), 'nazwa_filtra': 'FZ', 'stan_sprzetu': filtry.get('FZ', {}).get('stan_sprzetu', 'Brak danych'), 'aktywna_operacja': None},
            'FN': {'id_filtra': filtry.get('FN', {}).get('id'), 'nazwa_filtra': 'FN', 'stan_sprzetu': filtry.get('FN', {}).get('stan_sprzetu', 'Brak danych'), 'aktywna_operacja': None}
        }

        # Krok 2: Pobierz wszystkie aktywne operacje
        query_aktywne_operacje = """
            SELECT 
                ol.id, ol.typ_operacji, ol.czas_rozpoczecia, ol.status_operacji,
                ps.nazwa_partii,
                ps.unikalny_kod,
                zrodlo.nazwa_unikalna AS sprzet_zrodlowy,
                cel.nazwa_unikalna AS sprzet_docelowy
            FROM operacje_log ol
            LEFT JOIN partie_surowca ps ON ol.id_partii_surowca = ps.id
            LEFT JOIN sprzet zrodlo ON ol.id_sprzetu_zrodlowego = zrodlo.id
            LEFT JOIN sprzet cel ON ol.id_sprzetu_docelowego = cel.id
            WHERE ol.status_operacji = 'aktywna'
        """
        cursor.execute(query_aktywne_operacje)
        aktywne_operacje = cursor.fetchall()

        # Krok 3: Dla każdej aktywnej operacji sprawdź, czy używa któregoś z filtrów
        for op in aktywne_operacje:
            query_segmenty_operacji = """
                SELECT s.nazwa_unikalna FROM sprzet s
                JOIN porty_sprzetu ps ON s.id = ps.id_sprzetu
                JOIN segmenty seg ON ps.id = seg.id_portu_startowego OR ps.id = seg.id_portu_koncowego
                JOIN log_uzyte_segmenty lus ON seg.id = lus.id_segmentu
                WHERE lus.id_operacji_log = %s AND s.typ_sprzetu = 'filtr'
            """
            cursor.execute(query_segmenty_operacji, (op['id'],))
            uzyte_filtry = [row['nazwa_unikalna'] for row in cursor.fetchall()]

            for nazwa_filtra in uzyte_filtry:
                if nazwa_filtra in wynik:
                    wynik[nazwa_filtra]['aktywna_operacja'] = op

        # Krok 4: Sformatuj ostateczną odpowiedź
        ostateczna_odpowiedz = []
        for nazwa_filtra, dane in wynik.items():
            final_obj = {
                'id_filtra': dane['id_filtra'],
                'nazwa_filtra': dane['nazwa_filtra'],
                'stan_sprzetu': dane['stan_sprzetu'],
                'id_operacji': None, 'typ_operacji': None, 'czas_rozpoczecia': None,
                'status_operacji': None, 'nazwa_partii': None, 'sprzet_zrodlowy': None,
                'sprzet_docelowy': None,
                'unikalny_kod': None
            }
            if dane['aktywna_operacja']:
                final_obj.update(dane['aktywna_operacja'])
            ostateczna_odpowiedz.append(final_obj)

    finally:
        cursor.close()
        conn.close()

    # Definicje czasów trwania operacji w minutach
    DURATIONS = {
        'Budowanie placka': 30, 'Filtrowanie w koło': 15, 'Przedmuchiwanie': 10,
        'Dmuchanie filtra': 45, 'Czyszczenie': 20, 'TRANSFER': 30, 'FILTRACJA': 30
    }

    # Dodajemy obliczony czas zakończenia do danych
    for filtr in ostateczna_odpowiedz:
        filtr['czas_zakonczenia_iso'] = None
        if filtr.get('status_operacji') == 'aktywna' and filtr.get('typ_operacji') in DURATIONS and filtr.get('czas_rozpoczecia'):
            duration_minutes = DURATIONS[filtr['typ_operacji']]
            end_time = filtr['czas_rozpoczecia'] + timedelta(minutes=duration_minutes)
            filtr['czas_zakonczenia_iso'] = end_time.isoformat()

    return jsonify(ostateczna_odpowiedz)