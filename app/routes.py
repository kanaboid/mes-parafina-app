# app/routes.py

from flask import Blueprint, jsonify, request, current_app, render_template, g
from datetime import datetime, timedelta
from .sensors import SensorService  # Importujemy serwis czujników
import mysql.connector
import time
from .db import get_db_connection  # Importujemy funkcję do połączenia z bazą danych
from .pathfinder_service import PathFinder
from .apollo_service import ApolloService  # Importujemy serwis Apollo
from mysql.connector.errors import OperationalError
from decimal import Decimal

def get_pathfinder():
    if 'pathfinder' not in g:
        g.pathfinder = PathFinder(get_db_connection())
    return g.pathfinder

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

# --- DODAJ TĘ NOWĄ FUNKCJĘ ---
@bp.route('/operacje')
def show_operacje():
    """Wyświetla stronę z operacjami tankowania."""
    return render_template('operacje.html')

@bp.route('/operacje-apollo')
def show_operacje_apollo():
    """Wyświetla stronę do zarządzania transferami z Apollo."""
    return render_template('operacje_apollo.html')

@bp.route('/operacje-cysterny')
def operacje_cysterny():
    """Strona do zarządzania operacjami roztankowania cystern."""
    return render_template('operacje_cysterny.html')

@bp.route('/beczki')
def beczki():
    """Strona do zarządzania operacjami roztankowania cystern."""
    return render_template('beczki.html')
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
    cursor.execute("SELECT id, nazwa_unikalna FROM sprzet WHERE typ_sprzetu = 'filtr'")
    filtry = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(filtry)

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
        seg['zajety'] = seg.get('id_segmentu') in zajete_ids

    cursor.close()
    conn.close()
    return jsonify(segmenty)

@bp.route('/api/sprzet/pomiary', methods=['GET'])
def get_aktualne_pomiary_sprzetu():
    """
    Zwraca listę całego sprzętu wraz z jego aktualnymi odczytami temperatury i ciśnienia,
    bezpośrednio z tabeli `sprzet`.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Zapytanie jest teraz bardzo proste, ponieważ wszystkie potrzebne dane są w jednej tabeli.
    query = """
        SELECT
            id,
            nazwa_unikalna,
            typ_sprzetu,
            stan_sprzetu,
            temperatura_aktualna,
            cisnienie_aktualne,
            temperatura_docelowa,
            temperatura_max,
            cisnienie_max,
            ostatnia_aktualizacja
        FROM sprzet
        ORDER BY typ_sprzetu, nazwa_unikalna;
    """
    
    try:
        cursor.execute(query)
        sprzet_pomiary = cursor.fetchall()
        
        # Sformatuj datę ostatniej aktualizacji, aby była przyjazna dla formatu JSON
        for sprzet in sprzet_pomiary:
            if sprzet.get('ostatnia_aktualizacja'):
                sprzet['ostatnia_aktualizacja'] = sprzet.get('ostatnia_aktualizacja').strftime('%Y-%m-%d %H:%M:%S')
            
        return jsonify(sprzet_pomiary)
        
    except Exception as e:
        return jsonify({'error': f'Błąd bazy danych: {str(e)}'}), 500
        
    finally:
        cursor.close()
        conn.close()

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
            alarm['czas_wystapienia'] = alarm.get('czas_wystapienia').strftime('%Y-%m-%d %H:%M:%S')
        
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
            pomiar['czas_pomiaru'] = pomiar.get('czas_pomiaru').strftime('%Y-%m-%d %H:%M:%S')
            
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
    return render_template('filtry_scada.html')

# NOWY, ZAAWANSOWANY ENDPOINT DO MONITORINGU FILTRÓW
@bp.route('/api/filtry/status')
def get_filtry_status_scada():
    """
    Zwraca kompletny, szczegółowy status dla każdego filtra (FZ i FN)
    na potrzeby interfejsu SCADA. Zawiera:
    - Podstawowe dane i parametry (temperatura, ciśnienie).
    - Informacje o aktywnej operacji i przetwarzanej partii.
    - Planowany czas zakończenia operacji.
    - Listę partii oczekujących w kolejce (jeśli filtr jest wolny).
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 1. Pobierz podstawowe dane o filtrach, w tym ich parametry fizyczne
        cursor.execute("""
            SELECT 
                id, nazwa_unikalna, stan_sprzetu, typ_sprzetu,
                temperatura_aktualna, cisnienie_aktualne, poziom_aktualny_procent,
                temperatura_max, cisnienie_max, ostatnia_aktualizacja
            FROM sprzet 
            WHERE typ_sprzetu = 'filtr'
            ORDER BY nazwa_unikalna
        """)
        filtry = cursor.fetchall()
        
        # Słownik z definicjami czasów trwania operacji w minutach
        DURATIONS = {
            'Budowanie placka': 30, 'Filtrowanie w koło': 15, 'Przedmuchiwanie': 10,
            'Dmuchanie filtra': 45, 'Czyszczenie': 20, 'TRANSFER': 30, 'FILTRACJA': 30
        }

        # 2. Dla każdego filtra, wzbogać go o dane operacyjne
        for filtr in filtry:
            filtr['aktywna_operacja'] = None
            filtr['kolejka_oczekujacych'] = []
            
            # 2a. Sprawdź, czy filtr jest używany w jakiejś aktywnej operacji
            # Używamy złączenia z log_uzyte_segmenty, aby to ustalić
            cursor.execute("""
                SELECT
                    ol.id as id_operacji, ol.typ_operacji, ol.czas_rozpoczecia, ol.status_operacji,
                    ol.opis as opis_operacji,
                    ps.id as id_partii, ps.unikalny_kod, ps.nazwa_partii, ps.typ_surowca,
                    zrodlo.nazwa_unikalna AS sprzet_zrodlowy,
                    cel.nazwa_unikalna AS sprzet_docelowy
                FROM sprzet s
                JOIN porty_sprzetu ps_port ON s.id = ps_port.id_sprzetu
                JOIN segmenty seg ON ps_port.id = seg.id_portu_startowego OR ps_port.id = seg.id_portu_koncowego
                JOIN log_uzyte_segmenty lus ON seg.id = lus.id_segmentu
                JOIN operacje_log ol ON lus.id_operacji_log = ol.id
                LEFT JOIN partie_surowca ps ON ol.id_partii_surowca = ps.id
                LEFT JOIN sprzet zrodlo ON ol.id_sprzetu_zrodlowego = zrodlo.id
                LEFT JOIN sprzet cel ON ol.id_sprzetu_docelowego = cel.id
                WHERE ol.status_operacji = 'aktywna' AND s.id = %s
                LIMIT 1
            """, (filtr['id'],))
            
            aktywna_operacja = cursor.fetchone()
            
            if aktywna_operacja:
                filtr['aktywna_operacja'] = aktywna_operacja
                # Oblicz i dodaj planowany czas zakończenia
                typ_op = aktywna_operacja.get('typ_operacji')
                czas_start = aktywna_operacja.get('czas_rozpoczecia')
                if typ_op in DURATIONS and czas_start:
                    duration_minutes = DURATIONS[typ_op]
                    end_time = czas_start + timedelta(minutes=duration_minutes)
                    filtr['aktywna_operacja']['czas_zakonczenia_iso'] = end_time.isoformat()
                else:
                    filtr['aktywna_operacja']['czas_zakonczenia_iso'] = None
            else:
                # 2b. Jeśli filtr nie jest zajęty, sprawdź, czy ktoś na niego czeka
                # To są partie, które mają w polu `id_aktualnego_filtra` nazwę tego filtra
                cursor.execute("""
                    SELECT 
                        ps.id as id_partii, ps.unikalny_kod, ps.nazwa_partii,
                        ps.aktualny_etap_procesu, s.nazwa_unikalna as nazwa_reaktora
                    FROM partie_surowca ps
                    JOIN sprzet s ON ps.id_aktualnego_sprzetu = s.id
                    WHERE ps.id_aktualnego_filtra = %s AND ps.status_partii NOT IN ('Gotowy do wysłania', 'W magazynie czystym')
                    ORDER BY ps.czas_rozpoczecia_etapu ASC
                """, (filtr['nazwa_unikalna'],))
                filtr['kolejka_oczekujacych'] = cursor.fetchall()

        return jsonify(filtry)
        
    except Exception as e:
        # Zwróć błąd w formacie JSON dla łatwiejszego debugowania na froncie
        return jsonify({'error': f'Błąd po stronie serwera: {str(e)}'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# === NOWE API DLA ZARZĄDZANIA CYKLAMI FILTRACYJNYMI ===

@bp.route('/api/cykle-filtracyjne/<int:id_partii>')
def get_cykle_partii(id_partii):
    """Pobiera historię wszystkich cykli filtracyjnych dla danej partii."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT cf.*, 
                   ps.unikalny_kod, ps.typ_surowca, ps.nazwa_partii,
                   TIMESTAMPDIFF(MINUTE, cf.czas_rozpoczecia, cf.czas_zakonczenia) as rzeczywisty_czas_minut
            FROM cykle_filtracyjne cf
            JOIN partie_surowca ps ON cf.id_partii = ps.id
            WHERE cf.id_partii = %s
            ORDER BY cf.numer_cyklu, cf.czas_rozpoczecia
        """, (id_partii,))
        
        cykle = cursor.fetchall()
        return jsonify(cykle)
        
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/partie/aktualny-stan')
def get_partie_aktualny_stan():
    """Pobiera aktualny stan wszystkich partii w systemie z szczegółami procesu."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT ps.*,
                   s.nazwa_unikalna as nazwa_reaktora,
                   s.typ_sprzetu,
                   CASE 
                       WHEN ps.planowany_czas_zakonczenia IS NOT NULL 
                       THEN TIMESTAMPDIFF(MINUTE, NOW(), ps.planowany_czas_zakonczenia)
                       ELSE NULL
                   END as pozostale_minuty,
                   CASE 
                       WHEN ps.planowany_czas_zakonczenia IS NOT NULL AND NOW() > ps.planowany_czas_zakonczenia
                       THEN TRUE
                       ELSE FALSE
                   END as przekroczony_czas
            FROM partie_surowca ps
            LEFT JOIN sprzet s ON ps.id_aktualnego_sprzetu = s.id
            WHERE ps.status_partii NOT IN ('W magazynie czystym', 'Gotowy do wysłania')
            ORDER BY ps.czas_rozpoczecia_etapu DESC
        """)
        
        partie = cursor.fetchall()
        return jsonify(partie)
        
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/filtry/szczegolowy-status')
def get_filtry_szczegolowy_status():
    """Pobiera szczegółowy status filtrów z informacjami o partiach i cyklach."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Podstawowe informacje o filtrach
        cursor.execute("""
            SELECT id, nazwa_unikalna as nazwa_filtra, stan_sprzetu, typ_sprzetu
            FROM sprzet 
            WHERE typ_sprzetu = 'filtr'
            ORDER BY nazwa_unikalna
        """)
        filtry = cursor.fetchall()
        
        for filtr in filtry:
            # Sprawdź czy filtr ma aktywną operację
            cursor.execute("""
                SELECT ol.*, 
                       ps.unikalny_kod, ps.nazwa_partii, ps.typ_surowca,
                       ps.aktualny_etap_procesu, ps.numer_cyklu_aktualnego,
                       ps.czas_rozpoczecia_etapu, ps.planowany_czas_zakonczenia,
                       s_start.nazwa_unikalna as reaktor_startowy,
                       s_cel.nazwa_unikalna as reaktor_docelowy,
                       CASE 
                           WHEN ps.planowany_czas_zakonczenia IS NOT NULL 
                           THEN TIMESTAMPDIFF(MINUTE, NOW(), ps.planowany_czas_zakonczenia)
                           ELSE NULL
                       END as pozostale_minuty
                FROM operacje_log ol
                JOIN partie_surowca ps ON ol.id_partii_surowca = ps.id
                LEFT JOIN sprzet s_start ON ol.id_sprzetu_zrodlowego = s_start.id
                LEFT JOIN sprzet s_cel ON ol.id_sprzetu_docelowego = s_cel.id
                WHERE ol.status_operacji = 'aktywna' 
                AND ps.id_aktualnego_filtra = %s
                ORDER BY ol.czas_rozpoczecia DESC
                LIMIT 1
            """, (filtr['nazwa_filtra'],))
            
            aktywna_operacja = cursor.fetchone()
            filtr['aktywna_operacja'] = aktywna_operacja
            
            # Jeśli nie ma aktywnej operacji, sprawdź czy ktoś czeka na ten filtr
            if not aktywna_operacja:
                cursor.execute("""
                    SELECT ps.*, s.nazwa_unikalna as nazwa_reaktora
                    FROM partie_surowca ps
                    JOIN sprzet s ON ps.id_aktualnego_sprzetu = s.id
                    WHERE ps.id_aktualnego_filtra = %s 
                    AND ps.aktualny_etap_procesu IN ('surowy', 'gotowy')
                    ORDER BY ps.czas_rozpoczecia_etapu ASC
                    LIMIT 3
                """, (filtr['nazwa_filtra'],))
                
                filtr['kolejka_oczekujacych'] = cursor.fetchall()
            else:
                filtr['kolejka_oczekujacych'] = []
        
        return jsonify(filtry)
        
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/cykle/rozpocznij', methods=['POST'])
def rozpocznij_cykl_filtracyjny():
    """Rozpoczyna nowy cykl filtracyjny dla partii."""
    data = request.get_json()
    
    required_fields = ['id_partii', 'typ_cyklu', 'id_filtra', 'reaktor_startowy']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Brak wymaganych pól'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Pobierz aktualny numer cyklu partii
        cursor.execute("SELECT numer_cyklu_aktualnego FROM partie_surowca WHERE id = %s", (data['id_partii'],))
        result = cursor.fetchone()
        if not result:
            return jsonify({'error': 'Nie znaleziono partii'}), 404
        
        numer_cyklu = result[0] + 1
        
        # Oblicz planowany czas zakończenia
        durations = {
            'placek': 30,
            'filtracja': 15,
            'dmuchanie': 45
        }
        
        planowany_czas = datetime.now() + timedelta(minutes=durations.get(data['typ_cyklu'], 30))
        
        # Wstaw nowy cykl
        cursor.execute("""
            INSERT INTO cykle_filtracyjne 
            (id_partii, numer_cyklu, typ_cyklu, id_filtra, reaktor_startowy, 
             reaktor_docelowy, czas_rozpoczecia, wynik_oceny)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), 'oczekuje')
        """, (data['id_partii'], numer_cyklu, data['typ_cyklu'], data['id_filtra'], 
              data['reaktor_startowy'], data.get('reaktor_docelowy')))
        
        cykl_id = cursor.lastrowid
        
        # Aktualizuj partię
        etap_mapping = {
            'placek': 'placek',
            'filtracja': 'w_kole', 
            'dmuchanie': 'dmuchanie'
        }
        
        cursor.execute("""
            UPDATE partie_surowca 
            SET numer_cyklu_aktualnego = %s,
                aktualny_etap_procesu = %s,
                czas_rozpoczecia_etapu = NOW(),
                planowany_czas_zakonczenia = %s,
                id_aktualnego_filtra = %s,
                reaktor_docelowy = %s
            WHERE id = %s
        """, (numer_cyklu, etap_mapping[data['typ_cyklu']], planowany_czas,
              data['id_filtra'], data.get('reaktor_docelowy'), data['id_partii']))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Rozpoczęto cykl {data["typ_cyklu"]} dla partii',
            'cykl_id': cykl_id,
            'numer_cyklu': numer_cyklu
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'Błąd rozpoczynania cyklu: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/cykle/zakoncz', methods=['POST'])
def zakoncz_cykl_filtracyjny():
    """Kończy aktualny cykl filtracyjny i przechodzi do następnego etapu."""
    data = request.get_json()
    
    if 'id_partii' not in data:
        return jsonify({'error': 'Brak ID partii'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Pobierz aktualny stan partii
        cursor.execute("""
            SELECT * FROM partie_surowca WHERE id = %s
        """, (data['id_partii'],))
        
        partia = cursor.fetchone()
        if not partia:
            return jsonify({'error': 'Nie znaleziono partii'}), 404
        
        # Zakończ aktualny cykl
        cursor.execute("""
            UPDATE cykle_filtracyjne 
            SET czas_zakonczenia = NOW(),
                czas_trwania_minut = TIMESTAMPDIFF(MINUTE, czas_rozpoczecia, NOW()),
                wynik_oceny = %s,
                komentarz = %s
            WHERE id_partii = %s 
            AND numer_cyklu = %s 
            AND czas_zakonczenia IS NULL
        """, (data.get('wynik_oceny', 'oczekuje'), data.get('komentarz', ''),
              data['id_partii'], partia['numer_cyklu_aktualnego']))
        
        # Określ następny etap na podstawie aktualnego
        next_etap = 'gotowy'
        next_filtr = None
        
        if partia['aktualny_etap_procesu'] == 'placek':
            next_etap = 'przelew'
        elif partia['aktualny_etap_procesu'] == 'przelew':
            next_etap = 'w_kole'
        elif partia['aktualny_etap_procesu'] == 'w_kole':
            next_etap = 'ocena_probki'
        elif partia['aktualny_etap_procesu'] == 'dmuchanie':
            next_etap = 'gotowy'
            next_filtr = None
        
        # Aktualizuj partię
        cursor.execute("""
            UPDATE partie_surowca 
            SET aktualny_etap_procesu = %s,
                czas_rozpoczecia_etapu = NOW(),
                planowany_czas_zakonczenia = NULL,
                id_aktualnego_filtra = %s
            WHERE id = %s
        """, (next_etap, next_filtr, data['id_partii']))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Zakończono cykl. Partia przeszła do etapu: {next_etap}',
            'next_etap': next_etap
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'Błąd kończenia cyklu: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@bp.route('/cykle-monitor')
def cykle_monitor():
    """Serwuje stronę monitoringu cykli filtracyjnych."""
    return render_template('cykle_monitor.html')

# === ENDPOINTY API DLA AKTYWNYCH PARTII ===

@bp.route('/api/partie/aktywne', methods=['GET'])
def get_aktywne_partie():
    """
    Pobiera listę wszystkich aktywnych partii w systemie z pełnymi szczegółami:
    - Lokalizacja i status
    - Aktualny etap procesu
    - Czasy rozpoczęcia i planowanego zakończenia
    - Informacje o operacjach
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Główne zapytanie pobierające aktywne partie
        cursor.execute("""
            SELECT 
                ps.id,
                ps.unikalny_kod,
                ps.nazwa_partii,
                ps.typ_surowca,
                ps.zrodlo_pochodzenia,
                ps.waga_poczatkowa_kg,
                ps.waga_aktualna_kg,
                ps.data_utworzenia,
                ps.status_partii,
                ps.ilosc_cykli_filtracyjnych,
                
                -- Informacje o aktualnym sprzęcie
                s.id as id_sprzetu,
                s.nazwa_unikalna as nazwa_sprzetu,
                s.typ_sprzetu,
                s.stan_sprzetu,
                
                -- Informacje o aktywnej operacji (jeśli istnieje)
                ol.id as id_operacji,
                ol.typ_operacji,
                ol.status_operacji,
                ol.czas_rozpoczecia as czas_rozpoczecia_operacji,
                ol.opis as opis_operacji,
                ol.punkt_startowy,
                ol.punkt_docelowy,
                
                -- Obliczenia czasowe
                TIMESTAMPDIFF(MINUTE, ps.data_utworzenia, NOW()) as wiek_partii_minuty,
                CASE 
                    WHEN ol.czas_rozpoczecia IS NOT NULL 
                    THEN TIMESTAMPDIFF(MINUTE, ol.czas_rozpoczecia, NOW())
                    ELSE NULL
                END as czas_trwania_operacji_minuty
                
            FROM partie_surowca ps
            LEFT JOIN sprzet s ON ps.id_sprzetu = s.id
            LEFT JOIN operacje_log ol ON ps.id = ol.id_partii_surowca AND ol.status_operacji = 'aktywna'
            WHERE ps.status_partii NOT IN ('W magazynie czystym', 'Gotowy do wysłania')
            ORDER BY ps.data_utworzenia DESC
        """)
        
        partie = cursor.fetchall()
        
        # Wzbogacenie danych o dodatkowe informacje
        for partia in partie:
            # Dodaj informacje o statusach partii
            cursor.execute("""
                SELECT st.id, st.nazwa_statusu
                FROM partie_statusy ps
                JOIN statusy st ON ps.id_statusu = st.id
                WHERE ps.id_partii = %s
            """, (partia['id'],))
            partia['statusy'] = cursor.fetchall()
            
            # Dodaj historię ostatnich operacji
            cursor.execute("""
                SELECT 
                    ol.id,
                    ol.typ_operacji,
                    ol.status_operacji,
                    ol.czas_rozpoczecia,
                    ol.czas_zakonczenia,
                    ol.opis,
                    ol.punkt_startowy,
                    ol.punkt_docelowy,
                    TIMESTAMPDIFF(MINUTE, ol.czas_rozpoczecia, 
                        COALESCE(ol.czas_zakonczenia, NOW())) as czas_trwania_min
                FROM operacje_log ol
                WHERE ol.id_partii_surowca = %s
                ORDER BY ol.czas_rozpoczecia DESC
                LIMIT 5
            """, (partia['id'],))
            partia['historia_operacji'] = cursor.fetchall()
            
            # Formatuj daty dla JSON
            if partia['data_utworzenia']:
                partia['data_utworzenia'] = partia['data_utworzenia'].strftime('%Y-%m-%d %H:%M:%S')
            if partia['czas_rozpoczecia_operacji']:
                partia['czas_rozpoczecia_operacji'] = partia['czas_rozpoczecia_operacji'].strftime('%Y-%m-%d %H:%M:%S')
            
            # Formatuj daty w historii operacji
            for operacja in partia['historia_operacji']:
                if operacja['czas_rozpoczecia']:
                    operacja['czas_rozpoczecia'] = operacja['czas_rozpoczecia'].strftime('%Y-%m-%d %H:%M:%S')
                if operacja['czas_zakonczenia']:
                    operacja['czas_zakonczenia'] = operacja['czas_zakonczenia'].strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify(partie)
        
    except Exception as e:
        return jsonify({'error': f'Błąd pobierania aktywnych partii: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/partie/szczegoly/<int:partia_id>', methods=['GET'])
def get_szczegoly_partii(partia_id):
    """Pobiera szczegółowe informacje o konkretnej partii"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Podstawowe informacje o partii
        cursor.execute("""
            SELECT 
                ps.*,
                s.nazwa_unikalna as nazwa_sprzetu,
                s.typ_sprzetu,
                s.stan_sprzetu
            FROM partie_surowca ps
            LEFT JOIN sprzet s ON ps.id_sprzetu = s.id
            WHERE ps.id = %s
        """, (partia_id,))
        
        partia = cursor.fetchone()
        if not partia:
            return jsonify({'error': 'Partia nie znaleziona'}), 404
        
        # Pełna historia operacji
        cursor.execute("""
            SELECT 
                ol.*,
                s_start.nazwa_unikalna as nazwa_sprzetu_startowego,
                s_end.nazwa_unikalna as nazwa_sprzetu_docelowego,
                TIMESTAMPDIFF(MINUTE, ol.czas_rozpoczecia, 
                    COALESCE(ol.czas_zakonczenia, NOW())) as czas_trwania_min
            FROM operacje_log ol
            LEFT JOIN sprzet s_start ON ol.id_sprzetu_zrodlowego = s_start.id
            LEFT JOIN sprzet s_end ON ol.id_sprzetu_docelowego = s_end.id
            WHERE ol.id_partii_surowca = %s
            ORDER BY ol.czas_rozpoczecia DESC
        """, (partia_id,))
        
        partia['historia_operacji'] = cursor.fetchall()
        
        # Statusy partii
        cursor.execute("""
            SELECT st.id, st.nazwa_statusu
            FROM partie_statusy ps
            JOIN statusy st ON ps.id_statusu = st.id
            WHERE ps.id_partii = %s
        """, (partia_id,))
        partia['statusy'] = cursor.fetchall()
        
        # Cykle filtracyjne (jeśli istnieją)
        cursor.execute("""
            SELECT cf.*,
                   TIMESTAMPDIFF(MINUTE, cf.czas_rozpoczecia, cf.czas_zakonczenia) as rzeczywisty_czas_minut
            FROM cykle_filtracyjne cf
            WHERE cf.id_partii = %s
            ORDER BY cf.numer_cyklu DESC
        """, (partia_id,))
        partia['cykle_filtracyjne'] = cursor.fetchall()
        
        # Formatuj daty
        if partia['data_utworzenia']:
            partia['data_utworzenia'] = partia['data_utworzenia'].strftime('%Y-%m-%d %H:%M:%S')
        
        for operacja in partia['historia_operacji']:
            if operacja['czas_rozpoczecia']:
                operacja['czas_rozpoczecia'] = operacja['czas_rozpoczecia'].strftime('%Y-%m-%d %H:%M:%S')
            if operacja['czas_zakonczenia']:
                operacja['czas_zakonczenia'] = operacja['czas_zakonczenia'].strftime('%Y-%m-%d %H:%M:%S')
        
        for cykl in partia['cykle_filtracyjne']:
            if cykl['czas_rozpoczecia']:
                cykl['czas_rozpoczecia'] = cykl['czas_rozpoczecia'].strftime('%Y-%m-%d %H:%M:%S')
            if cykl['czas_zakonczenia']:
                cykl['czas_zakonczenia'] = cykl['czas_zakonczenia'].strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify(partia)
        
    except Exception as e:
        return jsonify({'error': f'Błąd pobierania szczegółów partii: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/partie/aktualizuj-status', methods=['POST'])
def aktualizuj_status_partii():
    """Aktualizuje status partii"""
    data = request.get_json()
    
    if not data or 'id_partii' not in data or 'nowy_status' not in data:
        return jsonify({'error': 'Brak wymaganych pól: id_partii, nowy_status'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Sprawdź czy partia istnieje
        cursor.execute("SELECT id FROM partie_surowca WHERE id = %s", (data['id_partii'],))
        if not cursor.fetchone():
            return jsonify({'error': 'Partia nie znaleziona'}), 404
        
        # Aktualizuj status
        cursor.execute("""
            UPDATE partie_surowca 
            SET status_partii = %s
            WHERE id = %s
        """, (data['nowy_status'], data['id_partii']))
        
        # Dodaj wpis do historii operacji
        cursor.execute("""
            INSERT INTO operacje_log 
            (typ_operacji, id_partii_surowca, status_operacji, czas_rozpoczecia, czas_zakonczenia, opis)
            VALUES ('ZMIANA_STATUSU', %s, 'zakonczona', NOW(), NOW(), %s)
        """, (data['id_partii'], f"Zmiana statusu na: {data['nowy_status']}"))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Status partii został zaktualizowany na: {data["nowy_status"]}'
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'Błąd aktualizacji statusu: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

# === KONIEC ENDPOINTÓW AKTYWNYCH PARTII ===

@bp.route('/aktywne-partie')
def show_aktywne_partie():
    """Serwuje stronę zarządzania aktywnymi partiami."""
    return render_template('aktywne_partie.html')

@bp.route('/api/typy-surowca', methods=['GET'])
def get_typy_surowca():
    """Zwraca listę dostępnych typów surowca"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT id, nazwa, opis FROM typy_surowca ORDER BY nazwa")
        typy = cursor.fetchall()
        return jsonify(typy)
    except Exception as e:
        return jsonify({'error': f'Błąd pobierania typów surowca: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/sprzet/beczki-brudne', methods=['GET'])
def get_beczki_brudne():
    """Zwraca listę beczek brudnych dostępnych do tankowania"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT id, nazwa_unikalna, stan_sprzetu
            FROM sprzet 
            WHERE typ_sprzetu = 'beczka_brudna'
            ORDER BY nazwa_unikalna
        """)
        beczki = cursor.fetchall()
        return jsonify(beczki)
    except Exception as e:
        return jsonify({'error': f'Błąd pobierania beczek: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/sprzet/reaktory-puste', methods=['GET'])
def get_reaktory_puste():
    """Zwraca listę reaktorów w stanie 'Pusty' dostępnych do tankowania"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT id, nazwa_unikalna, stan_sprzetu
            FROM sprzet 
            WHERE typ_sprzetu = 'reaktor' AND stan_sprzetu = 'Pusty'
            ORDER BY nazwa_unikalna
        """)
        reaktory = cursor.fetchall()
        return jsonify(reaktory)
    except Exception as e:
        return jsonify({'error': f'Błąd pobierania reaktorów: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/sprzet/reaktory-z-surowcem', methods=['GET'])
def get_reaktory_z_surowcem():
    """Zwraca listę reaktorów ze stanem innym niż 'Pusty' (zawierających surowiec)"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT id, nazwa_unikalna, stan_sprzetu
            FROM sprzet 
            WHERE typ_sprzetu = 'reaktor' AND stan_sprzetu != 'Pusty'
            ORDER BY nazwa_unikalna
        """)
        reaktory = cursor.fetchall()
        return jsonify(reaktory)
    except Exception as e:
        return jsonify({'error': f'Błąd pobierania reaktorów z surowcem: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/monitoring/parametry', methods=['GET'])
def get_parametry_sprzetu():
    """Zwraca aktualne temperatury i ciśnienia dla wszystkiego sprzętu."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                id,
                nazwa_unikalna,
                typ_sprzetu,
                stan_sprzetu,
                temperatura_aktualna,
                cisnienie_aktualne,
                poziom_aktualny_procent,
                temperatura_docelowa,
                temperatura_max,
                cisnienie_max,
                ostatnia_aktualizacja,
                CASE 
                    WHEN temperatura_aktualna > temperatura_max THEN 'PRZEKROCZENIE_TEMP'
                    WHEN cisnienie_aktualne > cisnienie_max THEN 'PRZEKROCZENIE_CISN'
                    WHEN temperatura_aktualna IS NULL OR cisnienie_aktualne IS NULL THEN 'BRAK_DANYCH'
                    ELSE 'OK'
                END as status_parametrow,
                CASE 
                    WHEN ostatnia_aktualizacja IS NULL THEN NULL
                    WHEN ostatnia_aktualizacja < NOW() - INTERVAL 5 MINUTE THEN 'NIEAKTUALNE'
                    ELSE 'AKTUALNE'
                END as status_danych
            FROM sprzet 
            ORDER BY typ_sprzetu, nazwa_unikalna
        """)
        
        sprzet_list = cursor.fetchall()
        
        # Formatuj daty do JSON
        for sprzet in sprzet_list:
            if sprzet.get('ostatnia_aktualizacja'):
                sprzet['ostatnia_aktualizacja'] = sprzet.get('ostatnia_aktualizacja').strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify(sprzet_list)
        
    except Exception as e:
        return jsonify({'error': f'Błąd pobierania parametrów sprzętu: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()


# ENDPOINT DO POBIERANIA PARAMETRÓW SPRZĘTU 
@bp.route('/api/monitoring/parametry/<int:sprzet_id>', methods=['GET'])
def get_parametry_konkretnego_sprzetu(sprzet_id):
    """Zwraca szczegółowe parametry dla konkretnego sprzętu."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                id,
                nazwa_unikalna,
                typ_sprzetu,
                stan_sprzetu,
                temperatura_aktualna,
                cisnienie_aktualne,
                poziom_aktualny_procent,
                temperatura_docelowa,
                temperatura_max,
                cisnienie_max,
                ostatnia_aktualizacja,
                pojemnosc_kg,
                id_partii_surowca,
                CASE 
                    WHEN temperatura_aktualna > temperatura_max THEN 'PRZEKROCZENIE_TEMP'
                    WHEN cisnienie_aktualne > cisnienie_max THEN 'PRZEKROCZENIE_CISN'
                    WHEN temperatura_aktualna IS NULL OR cisnienie_aktualne IS NULL THEN 'BRAK_DANYCH'
                    ELSE 'OK'
                END as status_parametrow,
                CASE 
                    WHEN ostatnia_aktualizacja IS NULL THEN NULL
                    WHEN ostatnia_aktualizacja < NOW() - INTERVAL 5 MINUTE THEN 'NIEAKTUALNE'
                    ELSE 'AKTUALNE'
                END as status_danych,
                TIMESTAMPDIFF(MINUTE, ostatnia_aktualizacja, NOW()) as minuty_od_aktualizacji
            FROM sprzet 
            WHERE id = %s
        """, (sprzet_id,))
        
        sprzet = cursor.fetchone()
        
        if not sprzet:
            return jsonify({'error': 'Sprzęt nie znaleziony'}), 404
        
        # Formatuj datę do JSON
        if sprzet.get('ostatnia_aktualizacja'):
            sprzet['ostatnia_aktualizacja'] = sprzet.get('ostatnia_aktualizacja').strftime('%Y-%m-%d %H:%M:%S')
        
        # Jeśli sprzęt ma partię, dodaj informacje o niej
        id_partii_surowca = sprzet.get('id_partii_surowca')
        if id_partii_surowca:
            cursor.execute("""
                SELECT unikalny_kod, typ_surowca, waga_aktualna_kg, status_partii
                FROM partie_surowca 
                WHERE id = %s
            """, (id_partii_surowca,))
            partia = cursor.fetchone()
            sprzet['partia'] = partia
        else:
            sprzet['partia'] = None
        
        return jsonify(sprzet)
        
    except Exception as e:
        return jsonify({'error': f'Błąd pobierania parametrów sprzętu: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/monitoring/alarmy-parametryczne', methods=['GET'])
def get_alarmy_parametryczne():
    """Zwraca listę sprzętu z przekroczonymi parametrami (temperatura/ciśnienie)."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                id,
                nazwa_unikalna,
                typ_sprzetu,
                temperatura_aktualna,
                cisnienie_aktualne,
                temperatura_max,
                cisnienie_max,
                ostatnia_aktualizacja,
                CASE 
                    WHEN temperatura_aktualna > temperatura_max THEN 'TEMPERATURA_PRZEKROCZONA'
                    WHEN cisnienie_aktualne > cisnienie_max THEN 'CISNIENIE_PRZEKROCZONE'
                    ELSE 'INNE'
                END as typ_alarmu,
                CASE 
                    WHEN temperatura_aktualna > temperatura_max THEN temperatura_aktualna - temperatura_max
                    WHEN cisnienie_aktualne > cisnienie_max THEN cisnienie_aktualne - cisnienie_max
                    ELSE 0
                END as przekroczenie_wartosci
            FROM sprzet 
            WHERE 
                (temperatura_aktualna > temperatura_max AND temperatura_aktualna IS NOT NULL)
                OR 
                (cisnienie_aktualne > cisnienie_max AND cisnienie_aktualne IS NOT NULL)
            ORDER BY przekroczenie_wartosci DESC
        """)
        
        alarmy = cursor.fetchall()
        
        # Formatuj daty do JSON
        for alarm in alarmy:
            if alarm.get('ostatnia_aktualizacja'):
                alarm['ostatnia_aktualizacja'] = alarm.get('ostatnia_aktualizacja').strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify(alarmy)
        
    except Exception as e:
        return jsonify({'error': f'Błąd pobierania alarmów parametrycznych: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@bp.route('/monitoring-parametry')
def show_monitoring_parametry():
    """Serwuje stronę monitoringu parametrów sprzętu."""
    return render_template('monitoring_parametry.html')


# ========================================
# ENDPOINTY API DLA SYSTEMU APOLLO
# ========================================

@bp.route('/api/apollo/stan/<int:id_sprzetu>', methods=['GET'])
def get_stan_apollo(id_sprzetu):
    """Pobiera aktualny stan Apollo z przewidywaniem dostępnej ilości"""
    try:
        stan = ApolloService.oblicz_aktualny_stan_apollo(id_sprzetu)
        return jsonify(stan)
    except Exception as e:
        return jsonify({'error': f'Błąd pobierania stanu Apollo: {str(e)}'}), 500

@bp.route('/api/apollo/rozpocznij-sesje', methods=['POST'])
def rozpocznij_sesje_apollo():
    """Rozpoczyna nową sesję wytapiania w Apollo"""
    data = request.get_json()
    
    required_fields = ['id_sprzetu', 'typ_surowca', 'waga_kg']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Brak wymaganych pól: id_sprzetu, typ_surowca, waga_kg'}), 400
    
    try:
        id_sesji = ApolloService.rozpocznij_sesje_apollo(
            data['id_sprzetu'], 
            data['typ_surowca'], 
            data['waga_kg'],
            data.get('operator')
        )
        
        return jsonify({
            'success': True,
            'message': f'Rozpoczęto nową sesję wytapiania w Apollo',
            'id_sesji': id_sesji
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Błąd rozpoczynania sesji: {str(e)}'}), 500

@bp.route('/api/apollo/dodaj-surowiec', methods=['POST'])
def dodaj_surowiec_apollo():
    """Dodaje kolejną porcję surowca stałego do Apollo"""
    data = request.get_json()
    
    required_fields = ['id_sprzetu', 'waga_kg']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Brak wymaganych pól: id_sprzetu, waga_kg'}), 400
    
    try:
        ApolloService.dodaj_surowiec_do_apollo(
            data['id_sprzetu'], 
            data['waga_kg'],
            data.get('operator')
        )
        
        return jsonify({
            'success': True,
            'message': f'Dodano {data["waga_kg"]}kg surowca do Apollo'
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Błąd dodawania surowca: {str(e)}'}), 500

@bp.route('/api/apollo/koryguj-stan', methods=['POST'])
def koryguj_stan_apollo():
    """Ręczna korekta stanu Apollo przez operatora"""
    data = request.get_json()
    
    required_fields = ['id_sprzetu', 'rzeczywista_waga_kg']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Brak wymaganych pól: id_sprzetu, rzeczywista_waga_kg'}), 400
    
    try:
        ApolloService.koryguj_stan_apollo(
            data['id_sprzetu'], 
            data['rzeczywista_waga_kg'],
            data.get('operator'),
            data.get('uwagi')
        )
        
        return jsonify({
            'success': True,
            'message': f'Skorygowano stan Apollo na {data["rzeczywista_waga_kg"]}kg'
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Błąd korekty stanu: {str(e)}'}), 500

@bp.route('/api/apollo/lista-stanow', methods=['GET'])
def get_lista_stanow_apollo():
    """Pobiera stany wszystkich Apollo w systemie"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Użycie LOWER() aby zapewnić brak wrażliwości na wielkość liter
        cursor.execute("SELECT id FROM sprzet WHERE LOWER(typ_sprzetu) = 'apollo'")
        apollo_ids = [row['id'] for row in cursor.fetchall()]
        
        lista_stanow = []
        for apollo_id in apollo_ids:
            try:
                stan = ApolloService.get_stan_apollo(apollo_id)
                if stan:
                    lista_stanow.append(stan)
            except Exception as e:
                print(f"Błąd przy pobieraniu stanu dla Apollo ID {apollo_id}: {e}")
                # Można dodać logowanie błędu, ale kontynuować dla innych
                continue
                
        return jsonify(lista_stanow)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/sprzet/dostepne-zrodla', methods=['GET'])
def get_dostepne_zrodla():
    """Zwraca listę dostępnych źródeł do transferu (Apollo + beczki brudne z zawartością)"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Apollo z aktywnymi sesjami
        apollo_query = """
            SELECT DISTINCT s.id, s.nazwa_unikalna, s.typ_sprzetu, 
                   'apollo' as kategoria_zrodla,
                   aps.typ_surowca,
                   'Aktywna sesja wytapiania' as opis_stanu
            FROM sprzet s
            JOIN apollo_sesje aps ON s.id = aps.id_sprzetu
            WHERE s.typ_sprzetu = 'apollo' AND aps.status_sesji = 'aktywna'
        """
        
        # Beczki brudne z partiami
        beczki_query = """
            SELECT DISTINCT s.id, s.nazwa_unikalna, s.typ_sprzetu,
                   'beczka_brudna' as kategoria_zrodla,
                   ps.typ_surowca,
                   CONCAT('Partia: ', ps.unikalny_kod, ' (', ps.waga_aktualna_kg, 'kg)') as opis_stanu
            FROM sprzet s
            JOIN partie_surowca ps ON s.id = ps.id_sprzetu
            WHERE s.typ_sprzetu = 'beczka_brudna' AND ps.status_partii NOT IN ('W magazynie czystym', 'Gotowy do wysłania')
        """
        
        # Reaktory z partiami
        reaktory_query = """
            SELECT DISTINCT s.id, s.nazwa_unikalna, s.typ_sprzetu,
                   'reaktor' as kategoria_zrodla,
                   ps.typ_surowca,
                   CONCAT('Partia: ', ps.unikalny_kod, ' (', ps.waga_aktualna_kg, 'kg)') as opis_stanu
            FROM sprzet s
            JOIN partie_surowca ps ON s.id = ps.id_sprzetu
            WHERE s.typ_sprzetu = 'reaktor' AND ps.status_partii NOT IN ('W magazynie czystym', 'Gotowy do wysłania')
        """
        
        cursor.execute(f"{apollo_query} UNION ALL {beczki_query} UNION ALL {reaktory_query} ORDER BY kategoria_zrodla, nazwa_unikalna")
        zrodla = cursor.fetchall()
        
        # Dla Apollo dodaj informacje o dostępnej ilości
        for zrodlo in zrodla:
            if zrodlo.get('kategoria_zrodla') == 'apollo':
                zrodlo_id = zrodlo.get('id')
                if zrodlo_id:
                    stan = ApolloService.oblicz_aktualny_stan_apollo(zrodlo_id)
                    zrodlo['dostepne_kg'] = stan.get('dostepne_kg')
                    zrodlo['opis_stanu'] = f"Dostępne: {stan.get('dostepne_kg')}kg {stan.get('typ_surowca')}"
        
        return jsonify(zrodla)
        
    except Exception as e:
        return jsonify({'error': f'Błąd pobierania źródeł: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/sprzet/dostepne-cele', methods=['GET'])
def get_dostepne_cele():
    """Zwraca listę wszystkich reaktorów i beczek brudnych jako potencjalnych celów transferu."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # LEFT JOIN z partiami, aby uzyskać informacje o zawartości
        query = """
            SELECT 
                s.id, 
                s.nazwa_unikalna, 
                s.typ_sprzetu, 
                s.stan_sprzetu,
                s.pojemnosc_kg,
                p.waga_aktualna_kg,
                p.typ_surowca
            FROM sprzet s
            LEFT JOIN partie_surowca p ON s.id = p.id_sprzetu
            WHERE s.typ_sprzetu IN ('reaktor', 'beczka_brudna')
            ORDER BY s.typ_sprzetu, s.nazwa_unikalna
        """
        cursor.execute(query)
        
        cele = cursor.fetchall()
        return jsonify(cele)
        
    except Exception as e:
        return jsonify({'error': f'Błąd pobierania celów: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()

@bp.route('/api/apollo/zakoncz-sesje', methods=['POST'])
def zakoncz_sesje_apollo():
    """Kończy aktywną sesję wytapiania w Apollo"""
    data = request.get_json()
    
    if not data or 'id_sprzetu' not in data:
        return jsonify({'error': 'Brak wymaganego pola: id_sprzetu'}), 400
    
    try:
        ApolloService.zakoncz_sesje_apollo(
            data['id_sprzetu'],
            data.get('operator')
        )
        
        return jsonify({
            'success': True,
            'message': f'Sesja dla Apollo ID {data["id_sprzetu"]} została zakończona.'
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Błąd kończenia sesji: {str(e)}'}), 500

@bp.route('/api/apollo/sesja/<int:id_sesji>/historia', methods=['GET'])
def get_historia_sesji_apollo(id_sesji):
    """Pobiera historię transferów dla danej sesji Apollo."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        sql = """
            SELECT 
                ol.czas_zakonczenia, 
                ol.ilosc_kg, 
                s.nazwa_unikalna as nazwa_celu
            FROM operacje_log ol
            LEFT JOIN sprzet s ON ol.id_sprzetu_docelowego = s.id
            WHERE ol.id_apollo_sesji = %s
              AND ol.typ_operacji = 'ROZTANKOWANIE_APOLLO'
              AND ol.status_operacji = 'zakonczona'
            ORDER BY ol.czas_zakonczenia DESC
        """
        cursor.execute(sql, (id_sesji,))
        historia = cursor.fetchall()
        
        # Formatowanie daty przed wysłaniem
        for row in historia:
            if row['czas_zakonczenia']:
                row['czas_zakonczenia'] = row['czas_zakonczenia'].strftime('%Y-%m-%d %H:%M:%S')

        return jsonify(historia)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

def get_base_components_recursive(partia_id, cursor):
    """
    Rekurencyjnie znajduje bazowe składniki dla danej partii, zwracając słownik:
    {'TYP_SUROWCA': waga, ...}
    """
    cursor.execute("SELECT id, typ_surowca, waga_poczatkowa_kg FROM partie_surowca WHERE id = %s", (partia_id,))
    partia_info = cursor.fetchone()

    if not partia_info:
        return {}

    # Jeśli partia nie jest mieszaniną, jest składnikiem bazowym. Zwróć jej typ i wagę.
    if not partia_info['typ_surowca'].startswith('MIX('):
        return { partia_info['typ_surowca']: float(partia_info['waga_poczatkowa_kg']) }

    # Partia jest mieszaniną, znajdź jej bezpośrednie składniki.
    query = """
        SELECT 
            ps.id_partii_skladowej,
            ps.waga_skladowa_kg,
            p.waga_poczatkowa_kg AS waga_calkowita_skladowej
        FROM partie_skladniki ps
        JOIN partie_surowca p ON ps.id_partii_skladowej = p.id
        WHERE ps.id_partii_wynikowej = %s;
    """
    cursor.execute(query, (partia_id,))
    direct_components = cursor.fetchall()
    
    final_composition_agg = {}

    for comp in direct_components:
        # Rekurencyjnie pobierz bazowe składniki dla każdego składnika
        child_base_components = get_base_components_recursive(comp['id_partii_skladowej'], cursor)
        
        weight_of_comp_used_in_mix = float(comp['waga_skladowa_kg'])
        total_initial_weight_of_child_batch = float(comp['waga_calkowita_skladowej'])

        if total_initial_weight_of_child_batch == 0:
            continue
            
        # Rozdziel wagę użytego składnika proporcjonalnie na jego bazowe komponenty
        for base_type, base_weight_in_child in child_base_components.items():
            proportion = base_weight_in_child / total_initial_weight_of_child_batch
            weight_contribution = proportion * weight_of_comp_used_in_mix
            final_composition_agg[base_type] = final_composition_agg.get(base_type, 0) + weight_contribution
            
    return final_composition_agg

@bp.route('/api/sprzet/stan-partii', methods=['GET'])
def get_stan_partii_w_sprzecie():
    """
    Zwraca stan całego sprzętu, który może przechowywać partie, 
    wraz z informacjami o aktualnie znajdującej się w nim partii.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Pobierz cały sprzęt, który nas interesuje, wraz z dołączonymi partiami
        query = """
            SELECT
                s.id, s.nazwa_unikalna, s.typ_sprzetu, s.stan_sprzetu,
                p.id AS partia_id, p.unikalny_kod, p.typ_surowca, p.waga_aktualna_kg
            FROM sprzet s
            LEFT JOIN partie_surowca p ON s.id = p.id_sprzetu
            WHERE s.typ_sprzetu IN ('reaktor', 'beczka_brudna', 'beczka_czysta')
            ORDER BY s.typ_sprzetu, s.nazwa_unikalna;
        """
        cursor.execute(query)
        wyniki = cursor.fetchall()
        
        # Przygotuj strukturę odpowiedzi
        odpowiedz = {
            'reaktory': [],
            'beczki_brudne': [],
            'beczki_czyste': []
        }

        for row in wyniki:
            sprzet_info = {
                'id': row['id'],
                'nazwa_unikalna': row['nazwa_unikalna'],
                'typ_sprzetu': row['typ_sprzetu'],
                'stan_sprzetu': row['stan_sprzetu'],
                'partia': None
            }
            if row['partia_id']:
                partia_info = {
                    'id': row['partia_id'],
                    'unikalny_kod': row['unikalny_kod'],
                    'typ_surowca': row['typ_surowca'],
                    'waga_aktualna_kg': float(row['waga_aktualna_kg']),
                    'sklad': None  # Domyślnie brak składu
                }

                # Jeśli partia jest mieszaniną, oblicz jej skład
                if partia_info['typ_surowca'].startswith('MIX('):
                    sklad_dict = get_base_components_recursive(partia_info['id'], cursor)
                    total_waga_skladu = sum(sklad_dict.values())
                    
                    if total_waga_skladu > 0:
                        sklad_list = []
                        for typ, waga in sklad_dict.items():
                            procent = (waga / total_waga_skladu) * 100
                            sklad_list.append({
                                'typ_surowca': typ,
                                'waga_kg': round(waga, 2),
                                'procent': round(procent, 2)
                            })
                        partia_info['sklad'] = sorted(sklad_list, key=lambda x: x['typ_surowca'])

                sprzet_info['partia'] = partia_info
            
            if row['typ_sprzetu'] == 'reaktor':
                odpowiedz['reaktory'].append(sprzet_info)
            elif row['typ_sprzetu'] == 'beczka_brudna':
                odpowiedz['beczki_brudne'].append(sprzet_info)
            elif row['typ_sprzetu'] == 'beczka_czysta':
                odpowiedz['beczki_czyste'].append(sprzet_info)

        return jsonify(odpowiedz)

    except mysql.connector.Error as err:
        return jsonify({'error': f'Błąd bazy danych: {err}'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@bp.route('/api/partie/<int:partia_id>/skladniki', methods=['GET'])
def get_skladniki_partii(partia_id):
    """Zwraca listę składników dla danej partii (mieszaniny)."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT 
                ps.id_partii_skladowej,
                p.unikalny_kod AS unikalny_kod_skladowej,
                ps.waga_skladowa_kg
            FROM partie_skladniki ps
            JOIN partie_surowca p ON ps.id_partii_skladowej = p.id
            WHERE ps.id_partii_wynikowej = %s
            ORDER BY ps.data_dodania;
        """
        cursor.execute(query, (partia_id,))
        skladniki = cursor.fetchall()

        # Konwersja Decimal na float dla JSON
        for s in skladniki:
            s['waga_skladowa_kg'] = float(s['waga_skladowa_kg'])

        return jsonify(skladniki)

    except mysql.connector.Error as err:
        return jsonify({'error': f'Błąd bazy danych: {err}'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@bp.route('/api/apollo/sesja/<int:sesja_id>/historia-zaladunku', methods=['GET'])
def get_historia_zaladunku_sesji(sesja_id):
    """Zwraca historię załadunków i korekt dla danej sesji Apollo."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT 
                typ_zdarzenia,
                waga_kg,
                czas_zdarzenia,
                operator,
                uwagi
            FROM apollo_tracking
            WHERE id_sesji = %s AND typ_zdarzenia IN ('DODANIE_SUROWCA', 'KOREKTA_RECZNA')
            ORDER BY czas_zdarzenia DESC;
        """
        cursor.execute(query, (sesja_id,))
        historia = cursor.fetchall()

        # Konwersja typów dla JSON
        for wpis in historia:
            if isinstance(wpis.get('czas_zdarzenia'), datetime):
                wpis['czas_zdarzenia'] = wpis['czas_zdarzenia'].isoformat()
            if isinstance(wpis.get('waga_kg'), Decimal):
                wpis['waga_kg'] = float(wpis['waga_kg'])

        return jsonify(historia)

    except mysql.connector.Error as err:
        return jsonify({'error': f'Błąd bazy danych: {err}'}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

