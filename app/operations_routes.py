# app/operations_routes.py
from flask import Blueprint, jsonify, request, current_app
from datetime import datetime
import mysql.connector
from .db import get_db_connection
from .pathfinder_service import PathFinder
from .apollo_service import ApolloService
import traceback

# Utworzenie nowego Blueprintu dla operacji
bp = Blueprint('operations', __name__, url_prefix='/api/operations')

def get_pathfinder():
    """Pobiera instancję serwisu PathFinder z kontekstu aplikacji."""
    return current_app.extensions['pathfinder']

# Endpoint do tworzenia nowej partii przez tankowanie
@bp.route('/tankowanie', methods=['POST'])
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


@bp.route('/rozpocznij_trase', methods=['POST'])
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


@bp.route('/zakoncz', methods=['POST'])
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

@bp.route('/aktywne', methods=['GET'])
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

@bp.route('/dobielanie', methods=['POST'])
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

@bp.route('/tankowanie-brudnego', methods=['POST'])
def tankowanie_brudnego():
    """Tankowanie brudnego surowca z beczki do reaktora"""
    dane = request.get_json()
    
    # Walidacja wymaganych pól
    wymagane_pola = ['id_beczki', 'id_reaktora', 'typ_surowca', 'waga_kg', 'temperatura_surowca']
    if not dane or not all(k in dane for k in wymagane_pola):
        return jsonify({'message': 'Brak wymaganych danych'}), 400

    # Walidacja wagi
    waga = float(dane['waga_kg'])
    if waga <= 0 or waga > 9000:
        return jsonify({'message': 'Waga musi być w zakresie 1-9000 kg'}), 400

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Sprawdź czy reaktor jest pusty
        cursor.execute("SELECT id, nazwa_unikalna, stan_sprzetu FROM sprzet WHERE id = %s", (dane['id_reaktora'],))
        reaktor = cursor.fetchone()
        
        if not reaktor:
            return jsonify({'message': 'Reaktor nie znaleziony'}), 404
            
        if reaktor['stan_sprzetu'] != 'Pusty':
            return jsonify({
                'message': f"Reaktor {reaktor['nazwa_unikalna']} nie jest pusty (stan: {reaktor['stan_sprzetu']})"
            }), 400

        # Sprawdź czy beczka istnieje
        cursor.execute("SELECT id, nazwa_unikalna FROM sprzet WHERE id = %s", (dane['id_beczki'],))
        beczka = cursor.fetchone()
        
        if not beczka:
            return jsonify({'message': 'Beczka nie znaleziona'}), 404

        # Stworzenie unikalnego kodu partii
        teraz = datetime.now()
        unikalny_kod = f"{dane['typ_surowca']}-{teraz.strftime('%Y%m%d-%H%M%S')}-{beczka['nazwa_unikalna']}"

        # Użycie kursora bez dictionary=True do operacji zapisu
        write_cursor = conn.cursor()

        # Stworzenie nowej partii surowca
        sql_partia = """
            INSERT INTO partie_surowca 
            (unikalny_kod, typ_surowca, zrodlo_pochodzenia, waga_poczatkowa_kg, waga_aktualna_kg, 
             id_sprzetu, nazwa_partii, status_partii) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        nazwa_partii = f"PARTIA_{unikalny_kod}"
        partia_dane = (
            unikalny_kod, dane['typ_surowca'], 'cysterna', waga, waga, 
            dane['id_reaktora'], nazwa_partii, 'Surowy w reaktorze'
        )
        write_cursor.execute(sql_partia, partia_dane)
        nowa_partia_id = write_cursor.lastrowid

        # Nadanie statusu "Surowy" w tabeli partie_statusy
        write_cursor.execute("INSERT IGNORE INTO partie_statusy (id_partii, id_statusu) VALUES (%s, 1)", (nowa_partia_id,))

        # Aktualizacja stanu reaktora
        write_cursor.execute("UPDATE sprzet SET stan_sprzetu = 'Zatankowany (surowy)' WHERE id = %s", (dane['id_reaktora'],))

        # Zapisanie temperatury początkowej do operator_temperatures
        write_cursor.execute("""
            INSERT INTO operator_temperatures (id_sprzetu, temperatura, czas_ustawienia)
            VALUES (%s, %s, NOW())
        """, (dane['id_reaktora'], dane['temperatura_surowca']))

        # Zapisanie operacji w logu
        sql_log = """
            INSERT INTO operacje_log 
            (typ_operacji, id_partii_surowca, id_sprzetu_zrodlowego, id_sprzetu_docelowego, 
             czas_rozpoczecia, czas_zakonczenia, ilosc_kg, opis, status_operacji) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'zakonczona')
        """
        opis = f"Tankowanie brudnego surowca {dane['typ_surowca']} z {beczka['nazwa_unikalna']} do {reaktor['nazwa_unikalna']}"
        log_dane = (
            'TANKOWANIE_BRUDNEGO', nowa_partia_id, dane['id_beczki'], dane['id_reaktora'], 
            teraz, teraz, waga, opis
        )
        write_cursor.execute(sql_log, log_dane)
        
        conn.commit()
        
        return jsonify({
            'message': 'Tankowanie zakończone pomyślnie',
            'partia_kod': unikalny_kod,
            'komunikat_operatorski': 'Włącz palnik i sprawdź temperaturę surowca na reaktorze',
            'reaktor': reaktor['nazwa_unikalna'],
            'temperatura_poczatkowa': dane['temperatura_surowca']
        }), 201

    except mysql.connector.Error as err:
        if conn: 
            conn.rollback()
        return jsonify({'message': f'Błąd bazy danych: {str(err)}'}), 500
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'message': f'Błąd: {str(e)}'}), 500
    finally:
        if conn and conn.is_connected():
            if 'cursor' in locals() and cursor: cursor.close()
            if 'write_cursor' in locals() and write_cursor: write_cursor.close()
            conn.close()

@bp.route('/transfer-reaktorow', methods=['POST'])
def transfer_reaktorow():
    """Transfer surowca z jednego reaktora do drugiego, opcjonalnie przez filtr"""
    dane = request.get_json()
    
    # Walidacja wymaganych pól
    wymagane_pola = ['id_reaktora_zrodlowego', 'id_reaktora_docelowego']
    if not dane or not all(k in dane for k in wymagane_pola):
        return jsonify({'message': 'Brak wymaganych danych: id_reaktora_zrodlowego, id_reaktora_docelowego'}), 400

    # Opcjonalne pola
    id_filtra = dane.get('id_filtra')  # None = transfer bezpośredni
    tylko_podglad = dane.get('podglad', False)  # True = tylko podgląd trasy, bez wykonania
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Sprawdź reaktor źródłowy - czy ma surowiec
        cursor.execute("SELECT id, nazwa_unikalna, stan_sprzetu FROM sprzet WHERE id = %s", (dane['id_reaktora_zrodlowego'],))
        reaktor_zrodlowy = cursor.fetchone()
        
        if not reaktor_zrodlowy:
            return jsonify({'message': 'Reaktor źródłowy nie znaleziony'}), 404
            
        if reaktor_zrodlowy['stan_sprzetu'] == 'Pusty':
            return jsonify({
                'message': f"Reaktor źródłowy {reaktor_zrodlowy['nazwa_unikalna']} jest pusty - brak surowca do transferu"
            }), 400

        # Sprawdź reaktor docelowy - czy jest pusty
        cursor.execute("SELECT id, nazwa_unikalna, stan_sprzetu FROM sprzet WHERE id = %s", (dane['id_reaktora_docelowego'],))
        reaktor_docelowy = cursor.fetchone()
        
        if not reaktor_docelowy:
            return jsonify({'message': 'Reaktor docelowy nie znaleziony'}), 404
            
        if reaktor_docelowy['stan_sprzetu'] != 'Pusty':
            return jsonify({
                'message': f"Reaktor docelowy {reaktor_docelowy['nazwa_unikalna']} nie jest pusty (stan: {reaktor_docelowy['stan_sprzetu']})"
            }), 400

        # Sprawdź filtr jeśli podany
        filtr_info = None
        if id_filtra:
            cursor.execute("SELECT id, nazwa_unikalna, stan_sprzetu FROM sprzet WHERE id = %s", (id_filtra,))
            filtr_info = cursor.fetchone()
            
            if not filtr_info:
                return jsonify({'message': 'Filtr nie znaleziony'}), 404

        # Znajdź partię w reaktorze źródłowym (nie jest wymagana dla podglądu)
        partia = None
        if not tylko_podglad:
            cursor.execute("""
                SELECT ps.id, ps.unikalny_kod, ps.typ_surowca, ps.waga_aktualna_kg, ps.nazwa_partii, ps.status_partii
                FROM partie_surowca ps 
                WHERE ps.id_sprzetu = %s
            """, (dane['id_reaktora_zrodlowego'],))
            partia = cursor.fetchone()
            
            if not partia:
                return jsonify({'message': f'Brak partii w reaktorze źródłowym {reaktor_zrodlowy["nazwa_unikalna"]}'}), 404

        # Przygotuj punkty dla PathFinder
        punkt_startowy = f"{reaktor_zrodlowy['nazwa_unikalna']}_OUT"
        punkt_docelowy = f"{reaktor_docelowy['nazwa_unikalna']}_IN"
        
        # Użyj PathFinder do znalezienia trasy
        pathfinder = get_pathfinder()
        wszystkie_zawory = [data['valve_name'] for u, v, data in pathfinder.graph.edges(data=True)]
        
        # Domyślne wartości
        opis_operacji = ""
        
        if id_filtra:
            # Transfer przez filtr
            punkt_filtr_in = f"{filtr_info['nazwa_unikalna']}_IN"
            punkt_filtr_out = f"{filtr_info['nazwa_unikalna']}_OUT"
            
            sciezka_1 = pathfinder.find_path(punkt_startowy, punkt_filtr_in, wszystkie_zawory)
            sciezka_filtr = pathfinder.find_path(punkt_filtr_in, punkt_filtr_out, wszystkie_zawory)
            sciezka_2 = pathfinder.find_path(punkt_filtr_out, punkt_docelowy, wszystkie_zawory)
            
            if not all([sciezka_1, sciezka_filtr, sciezka_2]):
                return jsonify({
                    'message': f'Nie można znaleźć trasy z {reaktor_zrodlowy["nazwa_unikalna"]} przez {filtr_info["nazwa_unikalna"]} do {reaktor_docelowy["nazwa_unikalna"]}'
                }), 404
                
            trasa_segmentow = sciezka_1 + sciezka_filtr + sciezka_2
            typ_operacji = f"Transfer {partia['typ_surowca']} z {reaktor_zrodlowy['nazwa_unikalna']} przez {filtr_info['nazwa_unikalna']} do {reaktor_docelowy['nazwa_unikalna']}"
            if not tylko_podglad and partia:
                opis_operacji = f"Transfer {partia['typ_surowca']} z {reaktor_zrodlowy['nazwa_unikalna']} przez {filtr_info['nazwa_unikalna']} do {reaktor_docelowy['nazwa_unikalna']}"
        else:
            # Transfer bezpośredni
            trasa_segmentow = pathfinder.find_path(punkt_startowy, punkt_docelowy, wszystkie_zawory)
            
            if not trasa_segmentow:
                return jsonify({
                    'message': f'Nie można znaleźć trasy bezpośredniej z {reaktor_zrodlowy["nazwa_unikalna"]} do {reaktor_docelowy["nazwa_unikalna"]}'
                }), 404
                
            typ_operacji = f"Transfer bezpośredni {partia['typ_surowca']} z {reaktor_zrodlowy['nazwa_unikalna']} do {reaktor_docelowy['nazwa_unikalna']}"
            if not tylko_podglad and partia:
                opis_operacji = f"Transfer bezpośredni {partia['typ_surowca']} z {reaktor_zrodlowy['nazwa_unikalna']} do {reaktor_docelowy['nazwa_unikalna']}"

        # Sprawdź konflikty segmentów
        if trasa_segmentow:
            placeholders_konflikt = ', '.join(['%s'] * len(trasa_segmentow))
            sql_konflikt = f"""
                SELECT s.nazwa_segmentu FROM log_uzyte_segmenty lus
                JOIN operacje_log ol ON lus.id_operacji_log = ol.id
                JOIN segmenty s ON lus.id_segmentu = s.id
                WHERE ol.status_operacji = 'aktywna' AND s.nazwa_segmentu IN ({placeholders_konflikt})
            """
            cursor.execute(sql_konflikt, trasa_segmentow)
            konflikty = cursor.fetchall()

            if konflikty and not tylko_podglad:  # Konflikty blokują tylko rzeczywisty transfer
                nazwy_zajetych = [k['nazwa_segmentu'] for k in konflikty]
                return jsonify({
                    'message': 'Konflikt zasobów - niektóre segmenty są używane przez inne operacje',
                    'zajete_segmenty': nazwy_zajetych
                }), 409

        # Znajdź zawory do otwarcia
        zawory_do_otwarcia = set()
        for segment_name in trasa_segmentow:
            for u, v, data in pathfinder.graph.edges(data=True):
                if data['segment_name'] == segment_name:
                    zawory_do_otwarcia.add(data['valve_name'])
                    break

        # Jeśli to tylko podgląd, zwróć informacje o trasie
        if tylko_podglad:
            return jsonify({
                'message': 'Podgląd trasy transferu',
                'trasa': trasa_segmentow,
                'zawory': list(zawory_do_otwarcia),
                'segmenty_do_zablokowania': trasa_segmentow,
                'reaktor_zrodlowy': reaktor_zrodlowy['nazwa_unikalna'],
                'reaktor_docelowy': reaktor_docelowy['nazwa_unikalna'],
                'filtr': filtr_info['nazwa_unikalna'] if filtr_info else None,
                'przez_filtr': bool(id_filtra),
                'typ_operacji': typ_operacji
            }), 200

        # Rozpocznij operację w transakcji
        write_cursor = conn.cursor()
        
        # Znajdź zawory do otwarcia
        zawory_do_otwarcia = set()
        for segment_name in trasa_segmentow:
            for u, v, data in pathfinder.graph.edges(data=True):
                if data['segment_name'] == segment_name:
                    zawory_do_otwarcia.add(data['valve_name'])
                    break
        
        # Otwórz zawory
        if zawory_do_otwarcia:
            placeholders_zawory = ', '.join(['%s'] * len(zawory_do_otwarcia))
            sql_zawory = f"UPDATE zawory SET stan = 'OTWARTY' WHERE nazwa_zaworu IN ({placeholders_zawory})"
            write_cursor.execute(sql_zawory, list(zawory_do_otwarcia))

        # Stwórz operację w logu
        sql_log = """
            INSERT INTO operacje_log 
            (typ_operacji, id_sprzetu_zrodlowego, id_sprzetu_docelowego, id_partii_surowca, status_operacji, czas_rozpoczecia, opis, 
             punkt_startowy, punkt_docelowy, ilosc_kg) 
            VALUES (%s, %s, %s, %s, 'aktywna', NOW(), %s, %s, %s, %s)
        """
        write_cursor.execute(sql_log, (
            typ_operacji, 
            dane['id_reaktora_zrodlowego'], 
            dane['id_reaktora_docelowego'], 
            partia['id'], 
            opis_operacji, 
            punkt_startowy, 
            punkt_docelowy, 
            partia['waga_aktualna_kg']
        ))
        operacja_id = write_cursor.lastrowid

        # Zablokuj segmenty
        if trasa_segmentow:
            placeholders_segmenty = ', '.join(['%s'] * len(trasa_segmentow))
            sql_id_segmentow = f"SELECT id FROM segmenty WHERE nazwa_segmentu IN ({placeholders_segmenty})"
            cursor.execute(sql_id_segmentow, trasa_segmentow)
            id_segmentow = [row['id'] for row in cursor.fetchall()]

            sql_blokada = "INSERT INTO log_uzyte_segmenty (id_operacji_log, id_segmentu) VALUES (%s, %s)"
            dane_do_blokady = [(operacja_id, id_seg) for id_seg in id_segmentow]
            write_cursor.executemany(sql_blokada, dane_do_blokady)

        # Aktualizuj stan sprzętu
        write_cursor.execute("UPDATE sprzet SET stan_sprzetu = 'W transferze' WHERE id = %s", (dane['id_reaktora_zrodlowego'],))
        write_cursor.execute("UPDATE sprzet SET stan_sprzetu = 'W transferze' WHERE id = %s", (dane['id_reaktora_docelowego'],))
        
        if id_filtra:
            write_cursor.execute("UPDATE sprzet SET stan_sprzetu = 'W transferze' WHERE id = %s", (id_filtra,))

        conn.commit()

        return jsonify({
            'message': 'Transfer rozpoczęty pomyślnie',
            'operacja_id': operacja_id,
            'typ_operacji': typ_operacji,
            'partia_kod': partia['unikalny_kod'] if partia else None,
            'reaktor_zrodlowy': reaktor_zrodlowy['nazwa_unikalna'],
            'reaktor_docelowy': reaktor_docelowy['nazwa_unikalna'],
            'filtr': filtr_info['nazwa_unikalna'] if filtr_info else None,
            'przez_filtr': bool(id_filtra),
            'trasa': trasa_segmentow,
            'zawory': list(zawory_do_otwarcia),
            'trasa_segmentow': trasa_segmentow,  # Dla kompatybilności wstecznej
            'zawory_otwarte': list(zawory_do_otwarcia),  # Dla kompatybilności wstecznej
            'komunikat_operatorski': f'Transfer {typ_operacji.lower().replace("_", " ")} rozpoczęty. Monitoruj przebieg operacji.'
        }), 201

    except mysql.connector.Error as err:
        if conn: 
            conn.rollback()
        return jsonify({'message': f'Błąd bazy danych: {str(err)}'}), 500
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({'message': f'Błąd: {str(e)}'}), 500
    finally:
        if conn and conn.is_connected():
            if 'cursor' in locals() and cursor: cursor.close()
            if 'write_cursor' in locals() and write_cursor: write_cursor.close()
            conn.close() 

@bp.route('/apollo-transfer/start', methods=['POST'])
def start_apollo_transfer():
    """Rozpoczyna operację transferu z Apollo, blokując zasoby w `log_uzyte_segmenty`."""
    data = request.get_json()
    
    id_zrodla = data['id_zrodla']
    id_celu = data['id_celu']
    operator = data.get('operator', 'SYSTEM')
    
    conn = None
    read_cursor = None
    write_cursor = None
    try:
        conn = get_db_connection()
        read_cursor = conn.cursor(dictionary=True)

        read_cursor.execute("SELECT id, nazwa_unikalna, typ_sprzetu, stan_sprzetu FROM sprzet WHERE id IN (%s, %s)", (id_zrodla, id_celu))
        sprzety = {s['id']: s for s in read_cursor.fetchall()}
        zrodlo = sprzety.get(id_zrodla)
        cel = sprzety.get(id_celu)

        if not zrodlo or zrodlo['typ_sprzetu'].lower() != 'apollo':
            return jsonify({'message': 'Nieprawidłowe źródło. Oczekiwano urządzenia typu "apollo".'}), 400
        if not cel or cel['typ_sprzetu'].lower() not in ['reaktor', 'beczka_brudna']:
            return jsonify({'message': 'Nieprawidłowy cel. Oczekiwano reaktora lub beczki brudnej.'}), 400

        if cel['stan_sprzetu'] != 'Pusty':
            print(f"OSTRZEŻENIE: Cel operacji {cel['nazwa_unikalna']} nie jest pusty (stan: {cel['stan_sprzetu']}).")

        pathfinder = get_pathfinder()
        punkt_startowy = f"{zrodlo['nazwa_unikalna']}_OUT"
        punkt_docelowy = f"{cel['nazwa_unikalna']}_IN"
        
        wszystkie_zawory = [edge_data['valve_name'] for _, _, edge_data in pathfinder.graph.edges(data=True)]
        trasa_segmentow_nazwy = pathfinder.find_path(punkt_startowy, punkt_docelowy, wszystkie_zawory)

        if not trasa_segmentow_nazwy:
            return jsonify({'message': f'Nie można znaleźć trasy z {punkt_startowy} do {punkt_docelowy}'}), 404
            
        placeholders_konflikt = ', '.join(['%s'] * len(trasa_segmentow_nazwy))
        sql_konflikt = f"SELECT s.nazwa_segmentu FROM log_uzyte_segmenty lus JOIN operacje_log ol ON lus.id_operacji_log = ol.id JOIN segmenty s ON lus.id_segmentu = s.id WHERE ol.status_operacji = 'aktywna' AND s.nazwa_segmentu IN ({placeholders_konflikt})"
        read_cursor.execute(sql_konflikt, trasa_segmentow_nazwy)
        konflikty = read_cursor.fetchall()

        if konflikty:
            nazwy_zajetych = [k['nazwa_unikalna'] for k in konflikty]
            return jsonify({'message': 'Konflikt zasobów - niektóre segmenty są używane przez inne operacje.','zajete_segmenty': nazwy_zajetych}), 409

        write_cursor = conn.cursor()

        # NOWY KROK: Otwórz zawory na trasie
        zawory_do_otwarcia = set()
        for segment_name in trasa_segmentow_nazwy:
            for u, v, data in pathfinder.graph.edges(data=True):
                if data.get('segment_name') == segment_name:
                    zawory_do_otwarcia.add(data['valve_name'])
                    break
        
        if zawory_do_otwarcia:
            placeholders_zawory = ', '.join(['%s'] * len(zawory_do_otwarcia))
            sql_zawory = f"UPDATE zawory SET stan = 'OTWARTY' WHERE nazwa_zaworu IN ({placeholders_zawory})"
            write_cursor.execute(sql_zawory, list(zawory_do_otwarcia))

        typ_operacji = 'ROZTANKOWANIE_APOLLO'
        opis_operacji = f"Transfer z {zrodlo['nazwa_unikalna']} do {cel['nazwa_unikalna']}"
        
        sql_log = "INSERT INTO operacje_log (typ_operacji, id_sprzetu_zrodlowego, id_sprzetu_docelowego, status_operacji, czas_rozpoczecia, opis, punkt_startowy, punkt_docelowy, zmodyfikowane_przez) VALUES (%s, %s, %s, 'aktywna', NOW(), %s, %s, %s, %s)"
        write_cursor.execute(sql_log, (typ_operacji, id_zrodla, id_celu, opis_operacji, punkt_startowy, punkt_docelowy, operator))
        operacja_id = write_cursor.lastrowid

        placeholders_segmenty = ', '.join(['%s'] * len(trasa_segmentow_nazwy))
        sql_id_segmentow = f"SELECT id FROM segmenty WHERE nazwa_segmentu IN ({placeholders_segmenty})"
        read_cursor.execute(sql_id_segmentow, trasa_segmentow_nazwy)
        id_segmentow = [row['id'] for row in read_cursor.fetchall()]

        sql_blokada = "INSERT INTO log_uzyte_segmenty (id_operacji_log, id_segmentu) VALUES (%s, %s)"
        dane_do_blokady = [(operacja_id, id_seg) for id_seg in id_segmentow]
        write_cursor.executemany(sql_blokada, dane_do_blokady)
        
        write_cursor.execute("UPDATE sprzet SET stan_sprzetu = 'W transferze' WHERE id = %s", (id_zrodla,))
        write_cursor.execute("UPDATE sprzet SET stan_sprzetu = 'W transferze' WHERE id = %s", (id_celu,))
        
        conn.commit()

        return jsonify({'message': 'Transfer rozpoczęty pomyślnie.','id_operacji': operacja_id}), 201

    except mysql.connector.Error as err:
        if conn and conn.is_connected(): conn.rollback()
        return jsonify({'message': f'Błąd bazy danych: {str(err)}'}), 500
    except Exception as e:
        if conn and conn.is_connected(): conn.rollback()
        return jsonify({'message': f'Błąd aplikacji: {str(e)}'}), 500
    finally:
        if read_cursor: read_cursor.close()
        if write_cursor: write_cursor.close()
        if conn and conn.is_connected(): conn.close()

@bp.route('/apollo-transfer/end', methods=['POST'])
def end_apollo_transfer():
    """Kończy operację transferu z Apollo, zwalnia zasoby i zarządza partiami surowca."""
    data = request.get_json()
    
    conn = None
    try:
        id_operacji = int(data['id_operacji'])
        waga_kg = float(data['waga_kg'])
        operator = data.get('operator', 'SYSTEM')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Pobierz dane operacji
        cursor.execute("SELECT id_sprzetu_zrodlowego, id_sprzetu_docelowego FROM operacje_log WHERE id = %s", (id_operacji,))
        operacja = cursor.fetchone()
        if not operacja: raise ValueError('Nie znaleziono operacji o podanym ID.')
        
        id_apollo = operacja['id_sprzetu_zrodlowego']
        id_celu = operacja['id_sprzetu_docelowego']
        
        # Znajdź sesję Apollo i typ surowca
        cursor.execute("SELECT id, typ_surowca FROM apollo_sesje WHERE id_sprzetu = %s AND status_sesji = 'aktywna'", (id_apollo,))
        sesja = cursor.fetchone()
        if not sesja: raise ValueError('Nie znaleziono aktywnej sesji dla danego Apollo.')
        typ_surowca_zrodla = sesja['typ_surowca']

        # Pobierz nazwy sprzętu do generowania kodu partii
        cursor.execute("SELECT nazwa_unikalna FROM sprzet WHERE id = %s", (id_apollo,))
        zrodlo_info = cursor.fetchone()
        cursor.execute("SELECT nazwa_unikalna FROM sprzet WHERE id = %s", (id_celu,))
        cel_info = cursor.fetchone()
        zrodlo_nazwa = zrodlo_info['nazwa_unikalna'] if zrodlo_info else f"ID{id_apollo}"
        cel_nazwa = cel_info['nazwa_unikalna'] if cel_info else f"ID{id_celu}"

        # DODATKOWY KROK: Znajdź partię źródłową w Apollo
        cursor.execute("SELECT * FROM partie_surowca WHERE id_sprzetu = %s LIMIT 1", (id_apollo,))
        partia_w_apollo = cursor.fetchone()
        if not partia_w_apollo:
            # To nie powinno się zdarzyć po zmianach w ApolloService, ale dodajemy zabezpieczenie
            raise ValueError(f"Nie znaleziono partii surowca dla Apollo o ID {id_apollo}.")

        # 1. Zakończ operację w logu
        cursor.execute("""
            UPDATE operacje_log SET status_operacji = 'zakonczona', czas_zakonczenia = NOW(), ilosc_kg = %s, zmodyfikowane_przez = %s, id_apollo_sesji = %s
            WHERE id = %s
        """, (waga_kg, operator, sesja['id'], id_operacji))

        # 2. ZWOLNIJ ZASOBY (przywrócona, poprawna logika)
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
            cursor.execute(sql_zamknij_zawory, zawory_do_zamkniecia)

        # 3. Zaktualizuj stany sprzętu
        cursor.execute("UPDATE sprzet SET stan_sprzetu = 'Gotowy' WHERE id = %s", (id_apollo,))
        cursor.execute("UPDATE sprzet SET stan_sprzetu = 'Zatankowany' WHERE id = %s", (id_celu,))
        
        # 4. ZARZĄDZANIE PARTIAMI (nowa logika z `partie_skladniki`)
        cursor.execute("SELECT * FROM partie_surowca WHERE id_sprzetu = %s LIMIT 1", (id_celu,))
        partia_w_celu = cursor.fetchone()

        data_transferu = datetime.now().strftime('%Y%m%d')
        czas_transferu = datetime.now().strftime('%H%M%S')

        if partia_w_celu:
            if partia_w_celu['typ_surowca'] == typ_surowca_zrodla:
                nowa_waga = float(partia_w_celu['waga_aktualna_kg']) + waga_kg
                cursor.execute("UPDATE partie_surowca SET waga_aktualna_kg = %s WHERE id = %s", (nowa_waga, partia_w_celu['id']))
            else:
                # Archiwizuj starą partię z celu
                cursor.execute("UPDATE partie_surowca SET id_sprzetu = NULL, status_partii = 'Archiwalna' WHERE id = %s", (partia_w_celu['id'],))
                
                # Oblicz nową wagę i stwórz opis
                nowa_waga = float(partia_w_celu['waga_aktualna_kg']) + waga_kg
                pochodzenie_opis = f"Mieszanina z partii ID {partia_w_celu['id']} i transferu z Apollo (Partia ID: {partia_w_apollo['id']})."
                unikalny_kod = f"MIX-{data_transferu}_{czas_transferu}-{zrodlo_nazwa}-{cel_nazwa}"
                
                # Stwórz nową partię "Mieszanina"
                cursor.execute("""
                    INSERT INTO partie_surowca (unikalny_kod, nazwa_partii, typ_surowca, waga_aktualna_kg, waga_poczatkowa_kg, id_sprzetu, zrodlo_pochodzenia, pochodzenie_opis, status_partii, typ_transformacji)
                    VALUES (%s, %s, 'Mieszanina', %s, %s, %s, 'apollo', %s, 'Surowy w reaktorze', 'MIESZANIE')
                """, (unikalny_kod, unikalny_kod, nowa_waga, nowa_waga, id_celu, pochodzenie_opis))
                nowa_partia_id = cursor.lastrowid

                # Zapisz składniki w nowej tabeli
                skladniki = [
                    (nowa_partia_id, partia_w_celu['id'], partia_w_celu['waga_aktualna_kg']),
                    (nowa_partia_id, partia_w_apollo['id'], waga_kg)
                ]
                cursor.executemany("""
                    INSERT INTO partie_skladniki (id_partii_wynikowej, id_partii_skladowej, waga_skladowa_kg)
                    VALUES (%s, %s, %s)
                """, skladniki)
        else:
            # Tworzenie nowej partii w pustym urządzeniu
            pochodzenie_opis = f"Roztankowanie z {zrodlo_nazwa} w ramach operacji ID: {id_operacji}"
            unikalny_kod = f"{typ_surowca_zrodla.replace(' ', '_')}-{data_transferu}_{czas_transferu}-{zrodlo_nazwa}-{cel_nazwa}"
            
            cursor.execute("""
                INSERT INTO partie_surowca (unikalny_kod, nazwa_partii, typ_surowca, waga_aktualna_kg, waga_poczatkowa_kg, id_sprzetu, 
                zrodlo_pochodzenia, pochodzenie_opis, status_partii, data_utworzenia, typ_transformacji)
                VALUES (%s, %s, %s, %s, %s, %s, 'apollo', %s, 'Surowy w reaktorze', NOW(), 'TRANSFER')
            """, (unikalny_kod, unikalny_kod, typ_surowca_zrodla, waga_kg, waga_kg, id_celu, pochodzenie_opis))
            nowa_partia_id = cursor.lastrowid
            
            # Powiąż nową partię z partią w Apollo
            cursor.execute("""
                INSERT INTO partie_skladniki (id_partii_wynikowej, id_partii_skladowej, waga_skladowa_kg)
                VALUES (%s, %s, %s)
            """, (nowa_partia_id, partia_w_apollo['id'], waga_kg))

        # 5. Zaktualizuj wagę partii w Apollo
        nowa_waga_apollo = float(partia_w_apollo['waga_aktualna_kg']) - waga_kg
        cursor.execute("UPDATE partie_surowca SET waga_aktualna_kg = %s WHERE id = %s", (nowa_waga_apollo, partia_w_apollo['id']))

        conn.commit()
        return jsonify({'success': True, 'message': f'Operacja {id_operacji} zakończona.'})

    except (ValueError, KeyError) as e:
        if conn and conn.is_connected(): conn.rollback()
        return jsonify({'error': str(e)}), 400
    except mysql.connector.Error as err:
        if conn and conn.is_connected(): conn.rollback()
        return jsonify({'error': f'Błąd bazy danych: {err}'}), 500
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if conn and conn.is_connected(): conn.close() 

@bp.route('/apollo-transfer/anuluj', methods=['POST'])
def anuluj_apollo_transfer():
    """Anuluje aktywny transfer, zwalnia zasoby i przywraca stany sprzętu."""
    data = request.get_json()
    if not data or 'id_operacji' not in data:
        return jsonify({'error': 'Brak wymaganego pola: id_operacji'}), 400

    id_operacji = data['id_operacji']
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Pobierz dane operacji
        cursor.execute("""
            SELECT id, status_operacji, id_sprzetu_zrodlowego, id_sprzetu_docelowego 
            FROM operacje_log WHERE id = %s
        """, (id_operacji,))
        operacja = cursor.fetchone()

        if not operacja:
            return jsonify({'error': 'Nie znaleziono operacji'}), 404
        if operacja['status_operacji'] != 'aktywna':
            return jsonify({'error': f"Nie można anulować operacji, która nie jest aktywna (status: {operacja['status_operacji']})"}), 409

        # 1. Zmień status operacji na 'anulowana'
        cursor.execute("UPDATE operacje_log SET status_operacji = 'anulowana' WHERE id = %s", (id_operacji,))

        # 2. Zwolnij zasoby (znajdź i zamknij zawory)
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
            cursor.execute(sql_zamknij_zawory, zawory_do_zamkniecia)

        # 3. Przywróć stan sprzętu (źródła i celu) do 'Gotowy'
        id_zrodla = operacja['id_sprzetu_zrodlowego']
        id_celu = operacja['id_sprzetu_docelowego']
        cursor.execute("UPDATE sprzet SET stan_sprzetu = 'Gotowy' WHERE id = %s", (id_celu))
        cursor.execute("UPDATE sprzet SET stan_sprzetu = 'Zatankowany' WHERE id = %s", (id_zrodla))
        conn.commit()

        return jsonify({'success': True, 'message': f'Operacja {id_operacji} została anulowana.'})

    except mysql.connector.Error as err:
        if conn and conn.is_connected(): conn.rollback()
        return jsonify({'error': f'Błąd bazy danych: {err}'}), 500
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if conn and conn.is_connected(): conn.close() 