# app/sprzet_routes.py

from flask import Blueprint, jsonify, request, current_app
from .sprzet_service import SprzetService
from .sockets import broadcast_dashboard_update # Będziemy od razu odświeżać dashboard
from .db import get_db_connection
from .apollo_service import ApolloService
from .sensors import SensorService
import mysql.connector
from decimal import Decimal, InvalidOperation

def get_sensor_service():
    """Pobiera instancję serwisu SensorService z kontekstu aplikacji."""
    return current_app.extensions['sensor_service']

sprzet_bp = Blueprint('sprzet', __name__, url_prefix='/api/sprzet')

@sprzet_bp.route('/<int:sprzet_id>/palnik', methods=['POST'])
def set_burner_status_endpoint(sprzet_id):
    """
    Endpoint API do zmiany statusu palnika.
    Oczekuje JSON: {"status": "WLACZONY" | "WYLACZONY"}
    """
    data = request.get_json()
    if not data or 'status' not in data:
        return jsonify({'error': 'Brak wymaganego pola "status" w ciele żądania.'}), 400

    try:
        nowy_status = data['status'].upper()
        
        # Wywołanie logiki z serwisu
        SprzetService.set_burner_status(sprzet_id, nowy_status)
        
        # Po udanej zmianie, wyślij aktualizację do wszystkich klientów na dashboardzie
        broadcast_dashboard_update()
        
        return jsonify({'message': f'Pomyślnie zmieniono status palnika dla sprzętu ID {sprzet_id} na {nowy_status}.'}), 200

    except ValueError as e:
        return jsonify({'error': str(e)}), 400 # Błędy walidacji (np. zły status)
    except Exception as e:
        # Ogólne błędy serwera
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Wystąpił nieoczekiwany błąd serwera: {e}'}), 500

@sprzet_bp.route('/', methods=['GET'], endpoint='api_get_sprzet_sprzet')
def get_sprzet():
    """Zwraca listę całego sprzętu WRAZ z informacją o znajdującej się w nim partii."""
    
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

@sprzet_bp.route('/filtry', methods=['GET'])
def get_filtry():
    """Zwraca listę filtrów."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nazwa_unikalna FROM sprzet WHERE typ_sprzetu = 'filtr'")
    filtry = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(filtry)

@sprzet_bp.route('/pomiary', methods=['GET'])
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

@sprzet_bp.route('/<int:sprzet_id>/temperatura', methods=['POST'])
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
    
@sprzet_bp.route('/beczki-brudne', methods=['GET'])
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

@sprzet_bp.route('/reaktory-puste', methods=['GET'])
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

@sprzet_bp.route('/reaktory-z-surowcem', methods=['GET'])
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

@sprzet_bp.route('/dostepne-zrodla', methods=['GET'])
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

@sprzet_bp.route('/dostepne-cele', methods=['GET'])
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
            WHERE s.typ_sprzetu IN ('reaktor', 'beczka_brudna', 'beczka_czysta')
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
@sprzet_bp.route('/stan-partii', methods=['GET'])
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
                    from .routes import get_base_components_recursive
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

@sprzet_bp.route('/<int:sprzet_id>/rozpocznij-podgrzewanie', methods=['POST'])
def start_heating_endpoint(sprzet_id):
    """
    Endpoint API do rozpoczynania procesu podgrzewania.
    Oczekuje JSON: {"start_temperature": "75.5"}
    """
    data = request.get_json()
    if not data or 'start_temperature' not in data:
        return jsonify({'error': 'Brak wymaganego pola "start_temperature".'}), 400

    try:
        start_temp = Decimal(data['start_temperature'])
        
        # Wywołanie logiki z serwisu
        result = SprzetService.start_heating_process(sprzet_id, start_temp)
        
        # Po udanej operacji, wyślij aktualizację do wszystkich na dashboardzie
        broadcast_dashboard_update()
        
        return jsonify({
            'message': f'Rozpoczęto podgrzewanie dla sprzętu ID {sprzet_id}.',
            'data': result
        }), 200

    except InvalidOperation:
        return jsonify({'error': 'Nieprawidłowy format temperatury.'}), 400
    except ValueError as e:
        return jsonify({'error': str(e)}), 400 # Błędy walidacji z serwisu
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Wystąpił błąd serwera: {e}'}), 500

@sprzet_bp.route('/<int:sprzet_id>/simulation-params', methods=['POST'])
def set_simulation_params_endpoint(sprzet_id):
    """
    Endpoint API do zmiany parametrów symulacji (prędkości grzania/chłodzenia).
    Oczekuje JSON: {"szybkosc_grzania": "0.5", "szybkosc_chlodzenia": "0.1"}
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Brak danych w ciele żądania.'}), 400

    try:
        # Pobieramy i walidujemy dane wejściowe
        szybkosc_grzania = Decimal(data['szybkosc_grzania']) if 'szybkosc_grzania' in data else None
        szybkosc_chlodzenia = Decimal(data['szybkosc_chlodzenia']) if 'szybkosc_chlodzenia' in data else None

        if szybkosc_grzania is None or szybkosc_chlodzenia is None:
            return jsonify({'error': 'Wymagane są pola "szybkosc_grzania" i "szybkosc_chlodzenia".'}), 400

        # Wywołanie logiki z serwisu
        SprzetService.set_simulation_params(sprzet_id, szybkosc_grzania, szybkosc_chlodzenia)
        
        # Odśwież dashboard
        broadcast_dashboard_update()
        
        return jsonify({'message': f'Pomyślnie zaktualizowano parametry symulacji dla sprzętu ID {sprzet_id}.'}), 200

    except InvalidOperation:
        return jsonify({'error': 'Nieprawidłowy format liczby.'}), 400
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Wystąpił błąd serwera: {e}'}), 500

@sprzet_bp.route('/<int:sprzet_id>/simulation-params', methods=['GET'])
def get_simulation_params_endpoint(sprzet_id):
    """
    Endpoint API do pobierania parametrów symulacji (prędkości grzania/chłodzenia).
    """
    try:
        params = SprzetService.get_simulation_params(sprzet_id)
        # Konwertuj Decimal na string, aby zapewnić serializację do JSON
        params['szybkosc_grzania'] = str(params['szybkosc_grzania']) if params['szybkosc_grzania'] is not None else None
        params['szybkosc_chlodzenia'] = str(params['szybkosc_chlodzenia']) if params['szybkosc_chlodzenia'] is not None else None
        return jsonify(params), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Wystąpił błąd serwera: {e}'}), 500