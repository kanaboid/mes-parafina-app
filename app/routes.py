# app/routes.py

from flask import Blueprint, jsonify, request, current_app, render_template
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
bp = Blueprint('api', __name__, url_prefix='/')


@bp.route('/')
def index():
    """Serwuje główną stronę aplikacji (frontend)."""
    return render_template('index.html')

# 2. Stworzenie pierwszego, prawdziwego endpointu API
@bp.route('/api/sprzet', methods=['GET'])
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
@bp.route('/api/operacje/tankowanie', methods=['POST'])
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

# app/routes.py
# ... (importy i inne endpointy bez zmian) ...

@bp.route('/api/operacje/rozpocznij_trase', methods=['POST'])
def rozpocznij_trase():
    dane = request.get_json()
    if not dane or not all(k in dane for k in ['start', 'cel', 'otwarte_zawory', 'typ_operacji', 'id_partii']):
        return jsonify({"status": "error", "message": "Brak wymaganych pól: start, cel, otwarte_zawory, typ_operacji, id_partii."}), 400

    start_point = dane['start']
    end_point = dane['cel']
    open_valves_list = dane['otwarte_zawory']
    typ_operacji = dane['typ_operacji']
    id_partii = dane['id_partii']
    
    # KROK 1: Znajdź ścieżkę
    pathfinder = get_pathfinder()
    znaleziona_sciezka_nazwy = pathfinder.find_path(start_point, end_point, open_valves_list)

    if not znaleziona_sciezka_nazwy:
        return jsonify({
            "status": "error",
            "message": f"Nie znaleziono ścieżki z {start_point} do {end_point} przy podanym ustawieniu zaworów."
        }), 404

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

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
        sql_log = "INSERT INTO operacje_log (typ_operacji, id_partii_surowca, status_operacji, czas_rozpoczecia, opis) VALUES (%s, %s, 'aktywna', NOW(), %s)"
        write_cursor.execute(sql_log, (typ_operacji, id_partii, opis_operacji))
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
        cursor.execute("SELECT status_operacji FROM operacje_log WHERE id = %s", (id_operacji,))
        operacja = cursor.fetchone()

        if not operacja:
            return jsonify({"status": "error", "message": f"Operacja o ID {id_operacji} nie istnieje."}), 404
        if operacja['status_operacji'] != 'aktywna':
            return jsonify({
                "status": "error", 
                "message": f"Nie można zakończyć operacji, ponieważ nie jest aktywna (status: {operacja['status_operacji']})."
            }), 409 # Conflict

        # --- POCZĄTEK TRANSAKCJI ---
        # (Transakcja już trwa, bo mamy autocommit=False)
        write_cursor = conn.cursor()

        # KROK 2: Zmień status operacji i dodaj czas zakończenia
        sql_zakoncz = "UPDATE operacje_log SET status_operacji = 'zakonczona', czas_zakonczenia = NOW() WHERE id = %s"
        write_cursor.execute(sql_zakoncz, (id_operacji,))

        # KROK 3: Znajdź zawory używane w tej operacji i zamknij je
        # To zapytanie znajduje nazwy zaworów powiązanych z segmentami używanymi przez naszą operację
        sql_znajdz_zawory = """
            SELECT DISTINCT z.nazwa_zaworu 
            FROM zawory z
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
        
        # KROK 4: Zatwierdź transakcję
        conn.commit()

        return jsonify({
            "status": "success",
            "message": f"Operacja o ID {id_operacji} została pomyślnie zakończona.",
            "zamkniete_zawory": zawory_do_zamkniecia
        }), 200

    except mysql.connector.Error as err:
        if conn:
            conn.rollback()
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