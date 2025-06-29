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