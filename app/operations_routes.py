# app/operations_routes.py
from flask import Blueprint, jsonify, request, current_app
from datetime import datetime as dt
from datetime import timezone
import mysql.connector
from .db import get_db_connection
from .pathfinder_service import PathFinder
from .apollo_service import ApolloService
import traceback
from decimal import Decimal
from .batch_management_service import BatchManagementService

from sqlalchemy.orm import joinedload
from .extensions import db
from .models import Sprzet, PortySprzetu, Segmenty, Zawory, OperacjeLog, t_log_uzyte_segmenty, ApolloSesje, ApolloTracking, PartieApollo, TankMixes, Batches, MixComponents
from app.sockets import broadcast_apollo_update, broadcast_dashboard_update

# Utworzenie nowego Blueprintu dla operacji
bp = Blueprint('operations', __name__, url_prefix='/api/operations')

def get_pathfinder():
    """Pobiera instancję serwisu PathFinder z kontekstu aplikacji."""
    print(f"DEBUG: get_pathfinder() called")
    print(f"DEBUG: current_app.extensions keys: {list(current_app.extensions.keys())}")
    
    if 'pathfinder' not in current_app.extensions:
        print(f"ERROR: 'pathfinder' not found in current_app.extensions")
        print(f"Available extensions: {list(current_app.extensions.keys())}")
        raise KeyError("'pathfinder' not found in current_app.extensions")
    
    pathfinder = current_app.extensions['pathfinder']
    print(f"DEBUG: pathfinder retrieved: {type(pathfinder)}")
    return pathfinder


def _apply_wydmuch_components_cleanup(mix):
    """
    Usuwa składniki material_type='WYDMUCH' i dodaje 20% ich masy proporcjonalnie do pozostałych.
    Bez filtration_cycles_count i is_wydmuch_mix – używane tam, gdzie te pola są ustawiane osobno.
    """
    komponenty = list(mix.components)
    wydmuch_komp = [c for c in komponenty if c.batch and c.batch.material_type == 'WYDMUCH']
    inne_komp = [c for c in komponenty if c not in wydmuch_komp]
    total_wydmuch = sum(c.quantity_in_mix for c in wydmuch_komp)
    total_inne = sum(c.quantity_in_mix for c in inne_komp)
    if total_wydmuch > 0 and total_inne > 0:
        odzysk = total_wydmuch * Decimal('0.20')
        for comp in inne_komp:
            prop = comp.quantity_in_mix / total_inne
            comp.quantity_in_mix += odzysk * prop
    for comp in wydmuch_komp:
        db.session.delete(comp)


def _apply_filtracja_na_placku_finish(mix):
    """
    Wykonuje logikę zakończenia FILTRACJA_NA_PLACKU / FILTRACJA_PLACEK_* na tank_mix:
    - is_wydmuch_mix = False
    - Usuwa składniki material_type='WYDMUCH', dodaje 20% ich masy proporcjonalnie do pozostałych.

    Licznik filtration_cycles_count zwiększaj osobno tylko przy operacji FILTRACJA_NA_PLACKU.
    """
    mix.is_wydmuch_mix = False
    _apply_wydmuch_components_cleanup(mix)


# Endpoint do tworzenia nowej partii przez tankowanie





@bp.route('/aktywne', methods=['GET'])
def get_aktywne_operacje():
    """Zwraca listę wszystkich operacji ze statusem 'aktywna' (WERSJA ORM)."""
    try:
        # Budujemy zapytanie
        query = db.select(OperacjeLog).filter_by(status_operacji='aktywna').order_by(OperacjeLog.czas_rozpoczecia.desc())
        
        # Wykonujemy zapytanie i pobieramy wszystkie wyniki
        aktywne_operacje = db.session.execute(query).scalars().all()

        # Przygotowujemy odpowiedź JSON
        # Musimy ręcznie zbudować słowniki, aby kontrolować format
        wynik_json = []
        for op in aktywne_operacje:
            wynik_json.append({
                'id': op.id,
                'typ_operacji': op.typ_operacji,
                'id_partii_surowca': op.id_partii_surowca,
                'czas_rozpoczecia': op.czas_rozpoczecia.strftime('%Y-%m-%d %H:%M:%S') if op.czas_rozpoczecia else None,
                'opis': op.opis
            })
        
        return jsonify(wynik_json)
    except Exception as e:
        # Lepsza obsługa błędów
        return jsonify({"status": "error", "message": f"Błąd serwera: {e}"}), 500




@bp.route('/apollo-transfer/start', methods=['POST'])
def start_apollo_transfer():
    """Rozpoczyna operację transferu z Apollo, blokując zasoby w `log_uzyte_segmenty`."""
    print(f"DEBUG: start_apollo_transfer() called")
    data = request.get_json()
    print(f"DEBUG: Received data: {data}")
    
    id_zrodla = data['id_zrodla']
    id_celu = data['id_celu']
    operator = data.get('operator', 'SYSTEM')
    print(f"DEBUG: id_zrodla={id_zrodla}, id_celu={id_celu}, operator={operator}")
    
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

        print(f"DEBUG: About to call get_pathfinder()")
        pathfinder = get_pathfinder()
        print(f"DEBUG: pathfinder retrieved successfully: {type(pathfinder)}")
        
        punkt_startowy = f"{zrodlo['nazwa_unikalna']}_OUT"
        punkt_docelowy = f"{cel['nazwa_unikalna']}_IN"
        print(f"DEBUG: punkt_startowy={punkt_startowy}, punkt_docelowy={punkt_docelowy}")
        
        print(f"DEBUG: Getting all valves from pathfinder graph")
        wszystkie_zawory = [edge_data['valve_name'] for _, _, edge_data in pathfinder.graph.edges(data=True)]
        print(f"DEBUG: Found {len(wszystkie_zawory)} valves")
        
        print(f"DEBUG: Calling pathfinder.find_path()")
        trasa_segmentow_nazwy = pathfinder.find_path(punkt_startowy, punkt_docelowy, wszystkie_zawory)
        print(f"DEBUG: pathfinder.find_path() returned: {trasa_segmentow_nazwy}")

        if not trasa_segmentow_nazwy:
            return jsonify({'message': f'Nie można znaleźć trasy z {punkt_startowy} do {punkt_docelowy}'}), 404
            
        placeholders_konflikt = ', '.join(['%s'] * len(trasa_segmentow_nazwy))
        sql_konflikt = f"SELECT s.nazwa_segmentu FROM log_uzyte_segmenty lus JOIN operacje_log ol ON lus.id_operacji_log = ol.id JOIN segmenty s ON lus.id_segmentu = s.id WHERE ol.status_operacji = 'aktywna' AND s.nazwa_segmentu IN ({placeholders_konflikt})"
        read_cursor.execute(sql_konflikt, trasa_segmentow_nazwy)
        konflikty = read_cursor.fetchall()

        if konflikty:
            nazwy_zajetych = [k['nazwa_segmentu'] for k in konflikty]
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
        broadcast_apollo_update()

        return jsonify({'message': 'Transfer rozpoczęty pomyślnie.','id_operacji': operacja_id}), 201

    except mysql.connector.Error as err:
        import traceback; traceback.print_exc()
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
    """
    Kończy operację transferu z Apollo (WERSJA ORM z pełną integracją BatchService).
    Loguje transfer w Apollo, tworzy partię pierwotną i tankuje ją do celu.
    """
    data = request.get_json()
    try:
        id_operacji = int(data['id_operacji'])
        waga_kg = Decimal(data['waga_kg'])
        operator = data.get('operator', 'SYSTEM')

        operacja = db.session.get(OperacjeLog, id_operacji)
        if not operacja or operacja.status_operacji != 'aktywna':
            raise ValueError('Nie znaleziono aktywnej operacji o podanym ID.')

        id_apollo = operacja.id_sprzetu_zrodlowego
        id_celu = operacja.id_sprzetu_docelowego
        
        sesja = db.session.execute(
            db.select(ApolloSesje).filter_by(id_sprzetu=id_apollo, status_sesji='aktywna')
        ).scalar_one_or_none()
        if not sesja:
            raise ValueError('Nie znaleziono aktywnej sesji dla danego Apollo.')

        # --- KROK 1: Aktualizacja stanu Apollo ---
        tracking_transfer = ApolloTracking(
            id_sesji=sesja.id, typ_zdarzenia='TRANSFER_WYJSCIOWY', waga_kg=waga_kg,
            czas_zdarzenia=dt.now(timezone.utc), id_operacji_log=operacja.id, operator=operator
        )
        db.session.add(tracking_transfer)

        # --- KROK 2: Stworzenie partii pierwotnej i zatankowanie jej do celu ---
        apollo_sprzet = db.session.get(Sprzet, id_apollo)
        
        # 2a. Stwórz wirtualną partię pierwotną dla tego transferu
        batch_result = BatchManagementService.create_raw_material_batch(
            material_type=sesja.typ_surowca,
            source_type='APOLLO',
            source_name=apollo_sprzet.nazwa_unikalna,
            quantity=waga_kg,
            operator=operator
        )
        nowy_batch_id = batch_result['batch_id']
        
        # 2b. Zatankuj tę nową partię do zbiornika docelowego.
        #    Ta metoda zajmie się całą logiką tworzenia/aktualizacji mieszaniny.
        BatchManagementService.tank_into_dirty_tank(
            batch_id=nowy_batch_id,
            tank_id=id_celu,
            operator=operator
        )

        # --- KROK 3: Zakończenie logistyki operacji ---
        operacja.status_operacji = 'zakonczona'
        operacja.czas_zakonczenia = dt.now(timezone.utc)
        operacja.ilosc_kg = waga_kg
        operacja.zmodyfikowane_przez = operator
        operacja.id_apollo_sesji = sesja.id
        
        # Przypisz ID nowo utworzonej partii do logu operacji
        # (Możemy to zrobić, choć Batches nie ma bezpośredniej relacji z OperacjeLog)
        operacja.opis = f"Transfer z {apollo_sprzet.nazwa_unikalna} do zbiornika ID {id_celu}. Utworzono partię pierwotną ID: {nowy_batch_id}."
        
        zawory_do_zamkniecia_nazwy = [seg.zawory.nazwa_zaworu for seg in operacja.segmenty if seg.zawory]
        if zawory_do_zamkniecia_nazwy:
            stmt = db.update(Zawory).where(
                Zawory.nazwa_zaworu.in_(zawory_do_zamkniecia_nazwy)
            ).values(stan='ZAMKNIETY')
            db.session.execute(stmt)

        if operacja.sprzet_zrodlowy:
            operacja.sprzet_zrodlowy.stan_sprzetu = 'Gotowy'
        if operacja.sprzet_docelowy:
            operacja.sprzet_docelowy.stan_sprzetu = 'Zatankowany'
        
        # Zamiast ręcznie zarządzać PartiąSurowca, pozwalamy, aby BatchManagementService to robił.
        # Usuwamy starą logikę:
        # partia_w_apollo = db.session.execute(...).scalar_one_or_none()
        # if partia_w_apollo:
        #     partia_w_apollo.waga_aktualna_kg -= waga_kg
        
        db.session.commit()
        broadcast_apollo_update()
        return jsonify({'success': True, 'message': f'Operacja {id_operacji} zakończona. Utworzono i zatankowano partię.'})

    except (ValueError, KeyError) as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Błąd serwera: {str(e)}'}), 500

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
        broadcast_dashboard_update()

        return jsonify({'success': True, 'message': f'Operacja {id_operacji} została anulowana.'})

    except mysql.connector.Error as err:
        if conn and conn.is_connected(): conn.rollback()
        return jsonify({'error': f'Błąd bazy danych: {err}'}), 500
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'write_cursor' in locals() and write_cursor: write_cursor.close()
        if conn and conn.is_connected(): conn.close() 

@bp.route('/roztankuj-cysterne/start', methods=['POST'])
def start_cysterna_transfer():
    """
    Rozpoczyna operację roztankowania cysterny.
    (Wersja zmodyfikowana, aby działać jak oryginalna 'start_apollo_transfer')
    """
    data = request.get_json()
    required_fields = ['id_cysterny', 'id_celu']
    if not data or not all(k in data for k in required_fields):
        return jsonify({'message': 'Brak wymaganych danych: id_cysterny, id_celu'}), 400

    id_cysterny = data['id_cysterny']
    id_celu = data['id_celu']
    operator = data.get('operator', 'SYSTEM')
    # ZMIANA 1: Przywrócono pobieranie flagi 'force' (chociaż w tej logice nie jest używana do stanu celu)
    force = data.get('force', False)

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id, nazwa_unikalna, typ_sprzetu, stan_sprzetu FROM sprzet WHERE id IN (%s, %s)", (id_cysterny, id_celu))
        sprzety = {s['id']: s for s in cursor.fetchall()}
        zrodlo = sprzety.get(int(id_cysterny))
        cel = sprzety.get(int(id_celu))

        # Walidacja specyficzna dla Cysterny
        if not zrodlo or zrodlo['typ_sprzetu'].lower() != 'cysterna':
            return jsonify({'message': 'Nieprawidłowe źródło. Oczekiwano urządzenia typu "cysterna".'}), 400
        if not cel or cel['typ_sprzetu'].lower() not in ['reaktor', 'beczka_brudna', 'zbiornik', 'beczka_czysta']:
            return jsonify({'message': 'Nieprawidłowy cel. Oczekiwano reaktora, beczki brudnej, beczki czystej lub zbiornika.'}), 400
        
        # ZMIANA 2: Zamiast blokować, tylko drukujemy ostrzeżenie (tak jak w oryginalnym start_apollo_transfer)
        if cel['stan_sprzetu'] != 'Pusty':
            print(f"OSTRZEŻENIE: Cel operacji {cel['nazwa_unikalna']} nie jest pusty (stan: {cel['stan_sprzetu']}). Operacja będzie kontynuowana.")
            # Nie zwracamy błędu, pozwalamy na dalsze wykonanie kodu.

        pathfinder = get_pathfinder()
        punkt_startowy = f"{zrodlo['nazwa_unikalna']}_OUT"
        punkt_docelowy = f"{cel['nazwa_unikalna']}_IN"
        
        wszystkie_zawory = [edge_data['valve_name'] for _, _, edge_data in pathfinder.graph.edges(data=True) if 'valve_name' in edge_data]
        trasa_segmentow_nazwy = pathfinder.find_path(punkt_startowy, punkt_docelowy, wszystkie_zawory)

        if not trasa_segmentow_nazwy:
            return jsonify({'message': f'Nie można znaleźć trasy z {punkt_startowy} do {punkt_docelowy}'}), 404

        placeholders_konflikt = ', '.join(['%s'] * len(trasa_segmentow_nazwy))
        sql_konflikt = f"SELECT s.nazwa_segmentu FROM log_uzyte_segmenty lus JOIN operacje_log ol ON lus.id_operacji_log = ol.id JOIN segmenty s ON lus.id_segmentu = s.id WHERE ol.status_operacji = 'aktywna' AND s.nazwa_segmentu IN ({placeholders_konflikt})"
        cursor.execute(sql_konflikt, trasa_segmentow_nazwy)
        konflikty = cursor.fetchall()
        
        # ZMIANA 3: Logika konfliktu, która była oryginalnie w start_apollo_transfer
        # Uwaga: ta logika jest trochę dziwna, bo 'force' nie jest tutaj używane
        if konflikty:
            nazwy_zajetych = [k['nazwa_segmentu'] for k in konflikty]
            return jsonify({
                'message': 'Konflikt zasobów - niektóre segmenty są używane.',
                'zajete_segmenty': nazwy_zajetych
            }), 409

        write_cursor = conn.cursor()

        zawory_do_otwarcia = set()
        for segment_name in trasa_segmentow_nazwy:
            for u, v, d in pathfinder.graph.edges(data=True):
                if d.get('segment_name') == segment_name and 'valve_name' in d:
                    zawory_do_otwarcia.add(d['valve_name'])
                    break
        if zawory_do_otwarcia:
            placeholders_zawory = ', '.join(['%s'] * len(zawory_do_otwarcia))
            sql_zawory = f"UPDATE zawory SET stan = 'OTWARTY' WHERE nazwa_zaworu IN ({placeholders_zawory})"
            write_cursor.execute(sql_zawory, list(zawory_do_otwarcia))

        typ_operacji = 'ROZTANKOWANIE_CYSTERNY'
        opis_operacji = f"Transfer z {zrodlo['nazwa_unikalna']} do {cel['nazwa_unikalna']}"

        sql_log = "INSERT INTO operacje_log (typ_operacji, id_sprzetu_zrodlowego, id_sprzetu_docelowego, status_operacji, czas_rozpoczecia, opis, punkt_startowy, punkt_docelowy, zmodyfikowane_przez) VALUES (%s, %s, %s, 'aktywna', NOW(), %s, %s, %s, %s)"
        write_cursor.execute(sql_log, (typ_operacji, id_cysterny, id_celu, opis_operacji, punkt_startowy, punkt_docelowy, operator))
        operacja_id = write_cursor.lastrowid

        placeholders_segmenty = ', '.join(['%s'] * len(trasa_segmentow_nazwy))
        sql_id_segmentow = f"SELECT id FROM segmenty WHERE nazwa_segmentu IN ({placeholders_segmenty})"
        cursor.execute(sql_id_segmentow, trasa_segmentow_nazwy)
        id_segmentow = [row['id'] for row in cursor.fetchall()]
        sql_blokada = "INSERT INTO log_uzyte_segmenty (id_operacji_log, id_segmentu) VALUES (%s, %s)"
        dane_do_blokady = [(operacja_id, id_seg) for id_seg in id_segmentow]
        write_cursor.executemany(sql_blokada, dane_do_blokady)

        write_cursor.execute("UPDATE sprzet SET stan_sprzetu = 'W transferze' WHERE id = %s", (id_cysterny,))
        write_cursor.execute("UPDATE sprzet SET stan_sprzetu = 'W transferze' WHERE id = %s", (id_celu,))
        
        conn.commit()
        return jsonify({'message': 'Roztankowanie cysterny rozpoczęte pomyślnie.', 'id_operacji': operacja_id}), 201

    except mysql.connector.Error as err:
        if conn: conn.rollback()
        return jsonify({'message': f'Błąd bazy danych: {str(err)}'}), 500
    except Exception as e:
        if conn: conn.rollback()
        traceback.print_exc()
        return jsonify({'message': f'Błąd aplikacji: {str(e)}'}), 500
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'write_cursor' in locals() and write_cursor: write_cursor.close()
        if conn and conn.is_connected(): conn.close()

@bp.route('/roztankuj-cysterne/zakoncz', methods=['POST'])
def end_cysterna_transfer():
    """
    Kończy operację roztankowania cysterny i zarządza partiami surowca.
    Wymaga: id_operacji, waga_netto_kg, typ_surowca, nr_rejestracyjny, nr_dokumentu_dostawy, nazwa_dostawcy.
    """
    data = request.get_json()
    required_fields = ['id_operacji', 'waga_netto_kg', 'typ_surowca', 'nr_rejestracyjny', 'nr_dokumentu_dostawy', 'nazwa_dostawcy']
    if not data or not all(k in data for k in required_fields):
        return jsonify({'message': 'Brak wszystkich wymaganych danych.'}), 400

    try:
        id_operacji = int(data['id_operacji'])
        waga_kg = float(data['waga_netto_kg'])
        typ_surowca_dostawy = data['typ_surowca']
    except (ValueError, TypeError):
        return jsonify({'message': 'Nieprawidłowy format danych.'}), 400

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM operacje_log WHERE id = %s AND status_operacji = 'aktywna'", (id_operacji,))
        operacja = cursor.fetchone()
        if not operacja:
            return jsonify({'message': 'Nie znaleziono aktywnej operacji o podanym ID.'}), 404

        id_cysterny = operacja['id_sprzetu_zrodlowego']
        id_celu = operacja['id_sprzetu_docelowego']
        
        # Aktualizacja logu operacji
        opis_operacji = (f"Dostawca: {data['nazwa_dostawcy']}, "
                         f"Pojazd: {data['nr_rejestracyjny']}, "
                         f"Dokument: {data['nr_dokumentu_dostawy']}, "
                         f"Surowiec: {typ_surowca_dostawy}, "
                         f"Waga: {waga_kg} kg")
        cursor.execute("UPDATE operacje_log SET status_operacji = 'zakonczona', czas_zakonczenia = NOW(), ilosc_kg = %s, opis = %s WHERE id = %s", (waga_kg, opis_operacji, id_operacji))

        # Zwolnienie zasobów (zawory)
        sql_znajdz_zawory = "SELECT DISTINCT z.nazwa_zaworu FROM zawory z JOIN segmenty s ON z.id = s.id_zaworu JOIN log_uzyte_segmenty lus ON s.id = lus.id_segmentu WHERE lus.id_operacji_log = %s"
        cursor.execute(sql_znajdz_zawory, (id_operacji,))
        zawory_do_zamkniecia = [row['nazwa_zaworu'] for row in cursor.fetchall()]
        if zawory_do_zamkniecia:
            placeholders = ', '.join(['%s'] * len(zawory_do_zamkniecia))
            sql_zamknij_zawory = f"UPDATE zawory SET stan = 'ZAMKNIETY' WHERE nazwa_zaworu IN ({placeholders})"
            cursor.execute(sql_zamknij_zawory, zawory_do_zamkniecia)
        
        # ZARZĄDZANIE PARTIAMI - analogicznie do /apollo-transfer/end
        cursor.execute("SELECT * FROM partie_apollo WHERE id_sprzetu = %s LIMIT 1", (id_celu,))
        partia_w_celu = cursor.fetchone()

        # Stworzenie "wirtualnej" partii dla dostawy
        unikalny_kod_dostawy = f"{typ_surowca_dostawy.replace(' ', '_')}-{dt.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}-DOSTAWA"
        cursor.execute("""
            INSERT INTO partie_apollo (unikalny_kod, nazwa_partii, typ_surowca, waga_aktualna_kg, waga_poczatkowa_kg, id_sprzetu, zrodlo_pochodzenia, pochodzenie_opis, status_partii, data_utworzenia)
            VALUES (%s, %s, %s, %s, %s, NULL, 'cysterna', %s, 'Archiwalna', NOW())
        """, (unikalny_kod_dostawy, unikalny_kod_dostawy, typ_surowca_dostawy, waga_kg, waga_kg, opis_operacji))
        id_partii_z_dostawy = cursor.lastrowid

        if partia_w_celu:
            # Mieszanie z istniejącą partią
            # 1. Archiwizuj starą partię w celu
            cursor.execute("UPDATE partie_apollo SET id_sprzetu = NULL, status_partii = 'Archiwalna' WHERE id = %s", (partia_w_celu['id'],))
            
            # 2. Utwórz nowy typ mieszaniny
            typ_surowca_w_celu = partia_w_celu['typ_surowca']
            skladniki_typow = set()
            if typ_surowca_w_celu.startswith('MIX('):
                istniejace_typy = typ_surowca_w_celu[4:-1].split(',')
                skladniki_typow.update(t.strip() for t in istniejace_typy)
            else:
                skladniki_typow.add(typ_surowca_w_celu)
            skladniki_typow.add(typ_surowca_dostawy)
            nowy_typ_mieszaniny = f"MIX({', '.join(sorted(list(skladniki_typow)))})"
            
            # 3. Utwórz nową partię wynikową (mieszaninę)
            nowa_waga = float(partia_w_celu['waga_aktualna_kg']) + waga_kg
            unikalny_kod_mix = f"MIX-{dt.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            cursor.execute("""
                INSERT INTO partie_apollo (unikalny_kod, nazwa_partii, typ_surowca, waga_aktualna_kg, waga_poczatkowa_kg, id_sprzetu, status_partii, typ_transformacji)
                VALUES (%s, %s, %s, %s, %s, %s, 'Surowy w reaktorze', 'MIESZANIE')
            """, (unikalny_kod_mix, unikalny_kod_mix, nowy_typ_mieszaniny, nowa_waga, nowa_waga, id_celu))
            id_nowej_partii = cursor.lastrowid

            # 4. Zapisz składniki w `partie_skladniki`
            skladniki = [
                (id_nowej_partii, partia_w_celu['id'], partia_w_celu['waga_aktualna_kg']),
                (id_nowej_partii, id_partii_z_dostawy, waga_kg)
            ]
            cursor.executemany("INSERT INTO partie_skladniki (id_partii_wynikowej, id_partii_skladowej, waga_skladowa_kg) VALUES (%s, %s, %s)", skladniki)
        else:
            # Cel jest pusty, więc po prostu "przenosimy" partię z dostawy do celu
            cursor.execute("UPDATE partie_apollo SET id_sprzetu = %s, status_partii = 'Surowy w reaktorze' WHERE id = %s", (id_celu, id_partii_z_dostawy))

        # Aktualizacja stanu sprzętu
        cursor.execute("UPDATE sprzet SET stan_sprzetu = 'Pusty' WHERE id = %s", (id_cysterny,))
        cursor.execute("UPDATE sprzet SET stan_sprzetu = 'Zatankowany' WHERE id = %s", (id_celu,))
        
        conn.commit()
        return jsonify({'message': 'Operacja zakończona pomyślnie. Utworzono i przetworzono nową partię surowca.'}), 200

    except mysql.connector.Error as err:
        if conn: conn.rollback()
        # Dodaj więcej szczegółów do logu błędu
        traceback.print_exc()
        return jsonify({'message': f'Błąd bazy danych: {str(err)}'}), 500
    except Exception as e:
        if conn: conn.rollback()
        traceback.print_exc()
        return jsonify({'message': f'Wystąpił nieoczekiwany błąd: {str(e)}'}), 500
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

@bp.route('/roztankuj-cysterne/anuluj', methods=['POST'])

def anuluj_cysterna_transfer():
    """
    Anuluje aktywną operację roztankowania cysterny.
    Wymaga: id_operacji.
    """
    data = request.get_json()
    if not data or 'id_operacji' not in data:
        return jsonify({'error': 'Brak wymaganego pola: id_operacji'}), 400

    id_operacji = data['id_operacji']
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM operacje_log WHERE id = %s AND status_operacji = 'aktywna'", (id_operacji,))
        operacja = cursor.fetchone()
        if not operacja:
            return jsonify({'error': 'Nie znaleziono aktywnej operacji o podanym ID.'}), 404

        write_cursor = conn.cursor()
        write_cursor.execute("UPDATE operacje_log SET status_operacji = 'anulowana', czas_zakonczenia = NOW() WHERE id = %s", (id_operacji,))

        # Zwolnij zasoby (zamknij zawory)
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

        # Przywróć stan sprzętu do 'Pusty'
        id_zrodla = operacja['id_sprzetu_zrodlowego']
        id_celu = operacja['id_sprzetu_docelowego']
        write_cursor.execute("UPDATE sprzet SET stan_sprzetu = 'Pusty' WHERE id = %s", (id_zrodla,))
        write_cursor.execute("UPDATE sprzet SET stan_sprzetu = 'Pusty' WHERE id = %s", (id_celu,))

        conn.commit()
        return jsonify({'success': True, 'message': f'Operacja {id_operacji} została anulowana.'})

    except mysql.connector.Error as err:
        if conn: conn.rollback()
        return jsonify({'error': f'Błąd bazy danych: {err}'}), 500
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'write_cursor' in locals() and write_cursor: write_cursor.close()
        if conn and conn.is_connected(): conn.close()


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

    # --- Logika PathFinder (teraz kompletna) ---
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
        # Jeśli nie ma punktu pośredniego, szukamy jednej, ciągłej ścieżki.
        znaleziona_sciezka_nazwy = pathfinder.find_path(start_point, end_point, open_valves_list)

    if not znaleziona_sciezka_nazwy:
        return jsonify({
            "status": "error",
            "message": f"Nie znaleziono kompletnej ścieżki z {start_point} do {end_point}."
        }), 404

    # --- Logika interakcji z bazą danych (WERSJA ORM) ---
    try:
        # Krok 1: Znajdź partię w reaktorze startowym
        partia_query = db.select(PartieApollo).join(PartieApollo.sprzet).join(Sprzet.porty_sprzetu).where(PortySprzetu.nazwa_portu == start_point)
        partia = db.session.execute(partia_query).scalar_one_or_none()

        if not partia:
            return jsonify({"status": "error", "message": f"W urządzeniu startowym ({start_point}) nie znaleziono żadnej partii."}), 404
        
        # Krok 2: Sprawdź konflikty
        konflikt_query = db.select(Segmenty.nazwa_segmentu).join(Segmenty.operacje_log).where(
            OperacjeLog.status_operacji == 'aktywna',
            Segmenty.nazwa_segmentu.in_(znaleziona_sciezka_nazwy)
        )
        konflikty = db.session.execute(konflikt_query).scalars().all()

        if konflikty:
            return jsonify({
                "status": "error", "message": "Konflikt zasobów.",
                "zajete_segmenty": konflikty
            }), 409

        # Krok 3: Uruchomienie operacji w jednej transakcji
        db.session.execute(
            db.update(Zawory)
            .where(Zawory.nazwa_zaworu.in_(open_valves_list))
            .values(stan='OTWARTY')
        )

        opis_operacji = f"Operacja {typ_operacji} z {start_point} do {end_point}"
        nowa_operacja = OperacjeLog(
            typ_operacji=typ_operacji,
            id_partii_surowca=partia.id,
            status_operacji='aktywna',
            czas_rozpoczecia=dt.now(timezone.utc),
            opis=opis_operacji,
            punkt_startowy=start_point,
            punkt_docelowy=end_point
        )
        db.session.add(nowa_operacja)

        segmenty_trasy_query = db.select(Segmenty).where(Segmenty.nazwa_segmentu.in_(znaleziona_sciezka_nazwy))
        segmenty_trasy = db.session.execute(segmenty_trasy_query).scalars().all()
        
        nowa_operacja.segmenty = segmenty_trasy

        db.session.commit()
        
        return jsonify({
            "status": "success",
            "message": "Operacja została pomyślnie rozpoczęta.",
            "id_operacji": nowa_operacja.id,
            "trasa": {
                "start": start_point,
                "cel": end_point,
                "uzyte_segmenty": znaleziona_sciezka_nazwy
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Błąd wewnętrzny serwera: {str(e)}"}), 500


@bp.route('/zakoncz', methods=['POST'])
def zakoncz_operacje():
    dane = request.get_json()
    if not dane or 'id_operacji' not in dane:
        return jsonify({"status": "error", "message": "Brak wymaganego pola: id_operacji."}), 400

    id_operacji = dane['id_operacji']
    try:
        # Krok 1: Znajdź operację w bazie za pomocą SQLAlchemy
        operacja = db.session.get(OperacjeLog, id_operacji)

        if not operacja:
            return jsonify({"status": "error", "message": f"Operacja o ID {id_operacji} nie istnieje."}), 404
        if operacja.status_operacji != 'aktywna':
            return jsonify({
                "status": "error", 
                "message": f"Nie można zakończyć operacji, która nie jest aktywna (status: {operacja.status_operacji})."
            }), 409

        # Krok 2: Zmień status operacji
        operacja.status_operacji = 'zakonczona'
        operacja.czas_zakonczenia = dt.now(timezone.utc) # Używamy aliasu `dt`

        # Krok 3: Znajdź i zamknij zawory (korzystając z relacji)
        zawory_do_zamkniecia_nazwy = []
        if operacja.segmenty:
            zawory_do_zamkniecia_nazwy = [segment.zawory.nazwa_zaworu for segment in operacja.segmenty if segment.zawory]
            for segment in operacja.segmenty:
                if segment.zawory:
                    segment.zawory.stan = 'ZAMKNIETY'
        
        # Krok 4: Aktualizacja lokalizacji partii i stanu sprzętu
        if operacja.partie_apollo and operacja.id_sprzetu_zrodlowego and operacja.id_sprzetu_docelowego and operacja.id_sprzetu_zrodlowego != operacja.id_sprzetu_docelowego:
            sprzet_docelowy = operacja.sprzet_docelowy
            sprzet_zrodlowy = operacja.sprzet_zrodlowy
            
            if sprzet_docelowy and sprzet_zrodlowy:
                operacja.partie_apollo.id_sprzetu = sprzet_docelowy.id
                sprzet_docelowy.stan_sprzetu = 'Zatankowany'
                sprzet_zrodlowy.stan_sprzetu = 'Pusty'

        # Krok 4b: Aktualizacja TankMixes przy zakończeniu filtracji (flow reaktorowy)
        FILTRACJA_TYPY = ('FILTRACJA_PLACEK_KOLO', 'FILTRACJA_PLACEK_PRZELEW', 'FILTRACJA_PRZELEW', 'FILTRACJA_KOLO', 'FILTRACJA_WYDMUCH', 'FILTRACJA_NA_PLACKU')
        if operacja.typ_operacji in FILTRACJA_TYPY:
            mix = None
            if operacja.id_tank_mix:
                mix = db.session.get(TankMixes, operacja.id_tank_mix)
            if not mix and operacja.id_sprzetu_zrodlowego:
                reaktor = db.session.get(Sprzet, operacja.id_sprzetu_zrodlowego)
                if reaktor and reaktor.active_mix_id:
                    mix = db.session.get(TankMixes, reaktor.active_mix_id)
            if mix:
                next_status = {
                    'FILTRACJA_PLACEK_KOLO': 'FILTRACJA_PRZELEW',
                    'FILTRACJA_PLACEK_PRZELEW': 'FILTRACJA_KOLO',
                    'FILTRACJA_PRZELEW': 'FILTRACJA_PRZELEW_PRZERWANE',
                    'FILTRACJA_KOLO': 'OCZEKUJE_NA_OCENE',
                    'FILTRACJA_WYDMUCH': 'FILTRACJA_PRZELEW',
                    'FILTRACJA_NA_PLACKU': 'FILTRACJA_KOLO',
                }.get(mix.process_status)
                if next_status:
                    mix.process_status = next_status
                    if operacja.typ_operacji == 'FILTRACJA_WYDMUCH':
                        mix.is_wydmuch_mix = False
                    if operacja.typ_operacji in ('FILTRACJA_NA_PLACKU', 'FILTRACJA_PLACEK_KOLO', 'FILTRACJA_PLACEK_PRZELEW'):
                        _apply_filtracja_na_placku_finish(mix)
                    if operacja.typ_operacji == 'FILTRACJA_NA_PLACKU':
                        mix.filtration_cycles_count = (mix.filtration_cycles_count or 0) + 1
                # Jeśli cel ≠ źródło – przenieś mieszaninę do reaktora docelowego (tylko gdy nie przerwano przelewu)
                if (
                    next_status != 'FILTRACJA_PRZELEW_PRZERWANE'
                    and operacja.id_sprzetu_zrodlowego is not None
                    and operacja.id_sprzetu_docelowego is not None
                    and operacja.id_sprzetu_zrodlowego != operacja.id_sprzetu_docelowego
                ):
                    mix.tank_id = operacja.id_sprzetu_docelowego
                    sprzet_zrodlowy = db.session.get(Sprzet, operacja.id_sprzetu_zrodlowego)
                    sprzet_docelowy = db.session.get(Sprzet, operacja.id_sprzetu_docelowego)
                    if sprzet_zrodlowy and sprzet_zrodlowy.active_mix_id == mix.id:
                        sprzet_zrodlowy.active_mix_id = None
                    if sprzet_docelowy:
                        sprzet_docelowy.active_mix_id = mix.id

        # Krok 5: Zatwierdź transakcję
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": f"Operacja o ID {id_operacji} została pomyślnie zakończona.",
            "zamkniete_zawory": zawory_do_zamkniecia_nazwy
        }), 200
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Błąd wewnętrzny serwera: {str(e)}"}), 500


@bp.route('/przelew-destinations', methods=['GET'])
def przelew_destinations():
    """
    Zwraca listę reaktorów będących możliwymi celami FILTRACJA_PRZELEW:
    - puste (brak aktywnego mixa), różne od źródła,
    - z fizycznie możliwą trasą: z filtra używanego w bieżącej operacji (FZ_OUT → cel)
    lub pełna trasa źródło → filtr → cel. Używane są wszystkie zawory („teoretyczna”
    możliwość trasy), żeby trasa nie była zablokowana przez stan bieżącej operacji.
    Query: id_operacji (wymagane).
    """
    id_operacji = request.args.get('id_operacji', type=int)
    if not id_operacji:
        return jsonify({"status": "error", "message": "Brak parametru id_operacji."}), 400

    try:
        from sqlalchemy.orm import joinedload
        operacja = db.session.execute(
            db.select(OperacjeLog).options(joinedload(OperacjeLog.segmenty)).where(OperacjeLog.id == id_operacji)
        ).unique().scalar_one_or_none()
        if not operacja:
            return jsonify({"status": "error", "message": f"Operacja o ID {id_operacji} nie istnieje."}), 404
        id_zrodla = operacja.id_sprzetu_zrodlowego
        if not id_zrodla and operacja.id_tank_mix:
            mix = db.session.get(TankMixes, operacja.id_tank_mix)
            if mix:
                id_zrodla = mix.tank_id
        if not id_zrodla:
            return jsonify({"status": "error", "message": "Nie można ustalić reaktora źródłowego."}), 404

        tank_zrodlo = db.session.get(Sprzet, id_zrodla)
        nazwa_zrodla = tank_zrodlo.nazwa_unikalna if tank_zrodlo else None
        if not nazwa_zrodla:
            return jsonify({"status": "error", "message": "Brak nazwy reaktora źródłowego."}), 404

        # Wszystkie zawory jako „otwarte” – szukamy tras teoretycznie możliwych (nie blokowanych przez bieżącą operację)
        all_valves = db.session.execute(db.select(Zawory.nazwa_zaworu)).scalars().all()
        open_valves_list = [v[0] if isinstance(v, (list, tuple)) else v for v in (all_valves or [])]

        pathfinder = get_pathfinder()
        wszystkie_filtry = db.session.execute(
            db.select(Sprzet.nazwa_unikalna).where(Sprzet.typ_sprzetu == 'filtr').order_by(Sprzet.nazwa_unikalna)
        ).scalars().all()
        if not wszystkie_filtry:
            return jsonify({"destinations": [], "message": "Brak filtra w systemie."}), 200

        # Filtr(y) z bieżącej operacji (segmenty operacji → porty → sprzęt typu filtr)
        port_ids = set()
        for seg in (operacja.segmenty or []):
            if getattr(seg, 'id_portu_startowego', None):
                port_ids.add(seg.id_portu_startowego)
            if getattr(seg, 'id_portu_koncowego', None):
                port_ids.add(seg.id_portu_koncowego)
        filtry_z_operacji = []
        if port_ids:
            raw = db.session.execute(
                db.select(Sprzet.nazwa_unikalna)
                .join(PortySprzetu, PortySprzetu.id_sprzetu == Sprzet.id)
                .where(PortySprzetu.id.in_(port_ids), Sprzet.typ_sprzetu == 'filtr')
                .distinct()
            ).scalars().all()
            filtry_z_operacji = [r[0] if isinstance(r, (list, tuple)) else r for r in raw]

        # Tylko reaktory puste (bez aktywnego mixa), inne niż źródło
        reaktory_puste_q = db.select(Sprzet).where(
            Sprzet.typ_sprzetu == 'reaktor',
            Sprzet.id != id_zrodla,
            Sprzet.active_mix_id.is_(None)
        ).order_by(Sprzet.nazwa_unikalna)
        reaktory_puste = db.session.execute(reaktory_puste_q).scalars().all()

        start_point = f"{nazwa_zrodla}_OUT"
        destinations = []
        for reaktor in reaktory_puste:
            nazwa_celu = reaktor.nazwa_unikalna
            end_point = f"{nazwa_celu}_IN"
            added = False
            if filtry_z_operacji:
                # Tylko trasa z filtra bieżącej operacji (np. FZ_OUT → cel) – żaden inny filtr
                for nazwa_filtra in filtry_z_operacji:
                    trasa_do_celu = pathfinder.find_path(f"{nazwa_filtra}_OUT", end_point, open_valves_list)
                    if trasa_do_celu and len(trasa_do_celu) > 0:
                        destinations.append({"id": reaktor.id, "nazwa_unikalna": reaktor.nazwa_unikalna})
                        added = True
                        break
            else:
                # Brak filtra z operacji: fallback – pełna trasa źródło → dowolny filtr → cel
                for f in wszystkie_filtry:
                    nazwa_filtra = f[0] if isinstance(f, (list, tuple)) else f
                    posredni_in = f"{nazwa_filtra}_IN"
                    posredni_out = f"{nazwa_filtra}_OUT"
                    sciezka_1 = pathfinder.find_path(start_point, posredni_in, open_valves_list)
                    sciezka_wewnetrzna = pathfinder.find_path(posredni_in, posredni_out, open_valves_list)
                    sciezka_2 = pathfinder.find_path(posredni_out, end_point, open_valves_list)
                    if sciezka_1 and sciezka_wewnetrzna and sciezka_2:
                        destinations.append({"id": reaktor.id, "nazwa_unikalna": reaktor.nazwa_unikalna})
                        break

        return jsonify({"destinations": destinations}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route('/start-filtration-destinations', methods=['GET'])
def start_filtration_destinations():
    """
    Zwraca listę reaktorów będących możliwymi celami dla "Start filtracji":
    - ten sam reaktor (koło), jeśli istnieje trasa źródło → filtr → źródło,
    - inne reaktory tylko puste i z trasą źródło → filtr → cel.
    Używane są wszystkie zawory (trasę teoretycznie możliwą).
    Query: id_reaktora_zrodlowego (wymagane).
    """
    id_zrodla = request.args.get('id_reaktora_zrodlowego', type=int)
    if not id_zrodla:
        return jsonify({"status": "error", "message": "Brak parametru id_reaktora_zrodlowego."}), 400

    try:
        tank_zrodlo = db.session.get(Sprzet, id_zrodla)
        if not tank_zrodlo or tank_zrodlo.typ_sprzetu != 'reaktor':
            return jsonify({"status": "error", "message": "Nieprawidłowy reaktor źródłowy."}), 404
        nazwa_zrodla = tank_zrodlo.nazwa_unikalna
        start_point = f"{nazwa_zrodla}_OUT"
        end_point_same = f"{nazwa_zrodla}_IN"

        all_valves = db.session.execute(db.select(Zawory.nazwa_zaworu)).scalars().all()
        open_valves_list = [v[0] if isinstance(v, (list, tuple)) else v for v in (all_valves or [])]

        pathfinder = get_pathfinder()
        wszystkie_filtry = db.session.execute(
            db.select(Sprzet.nazwa_unikalna).where(Sprzet.typ_sprzetu == 'filtr').order_by(Sprzet.nazwa_unikalna)
        ).scalars().all()
        if not wszystkie_filtry:
            return jsonify({"destinations": [], "message": "Brak filtra w systemie."}), 200

        destinations = []

        # Ten sam reaktor (koło): źródło → filtr → źródło
        for f in wszystkie_filtry:
            nazwa_filtra = f[0] if isinstance(f, (list, tuple)) else f
            posredni_in = f"{nazwa_filtra}_IN"
            posredni_out = f"{nazwa_filtra}_OUT"
            sciezka_1 = pathfinder.find_path(start_point, posredni_in, open_valves_list)
            sciezka_wewnetrzna = pathfinder.find_path(posredni_in, posredni_out, open_valves_list)
            sciezka_2 = pathfinder.find_path(posredni_out, end_point_same, open_valves_list)
            if sciezka_1 and sciezka_wewnetrzna and sciezka_2:
                destinations.append({"id": tank_zrodlo.id, "nazwa_unikalna": nazwa_zrodla, "is_same_reactor": True})
                break

        # Inne reaktory: tylko puste, z trasą źródło → filtr → cel
        reaktory_puste_q = db.select(Sprzet).where(
            Sprzet.typ_sprzetu == 'reaktor',
            Sprzet.id != id_zrodla,
            Sprzet.active_mix_id.is_(None)
        ).order_by(Sprzet.nazwa_unikalna)
        reaktory_puste = db.session.execute(reaktory_puste_q).scalars().all()

        for reaktor in reaktory_puste:
            nazwa_celu = reaktor.nazwa_unikalna
            end_point = f"{nazwa_celu}_IN"
            for f in wszystkie_filtry:
                nazwa_filtra = f[0] if isinstance(f, (list, tuple)) else f
                posredni_in = f"{nazwa_filtra}_IN"
                posredni_out = f"{nazwa_filtra}_OUT"
                sciezka_1 = pathfinder.find_path(start_point, posredni_in, open_valves_list)
                sciezka_wewnetrzna = pathfinder.find_path(posredni_in, posredni_out, open_valves_list)
                sciezka_2 = pathfinder.find_path(posredni_out, end_point, open_valves_list)
                if sciezka_1 and sciezka_wewnetrzna and sciezka_2:
                    destinations.append({"id": reaktor.id, "nazwa_unikalna": reaktor.nazwa_unikalna, "is_same_reactor": False})
                    break

        return jsonify({"destinations": destinations}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route('/continue-to-przelew', methods=['POST'])
def continue_to_przelew():
    """
    Kończy operację FILTRACJA_PLACEK_KOLO lub FILTRACJA_WYDMUCH i uruchamia FILTRACJA_PRZELEW
    (reaktor źródłowy → filtr → reaktor docelowy). Wymaga id_reaktora_docelowego.
    """
    dane = request.get_json()
    if not dane or 'id_operacji' not in dane or 'id_reaktora_docelowego' not in dane:
        return jsonify({
            "status": "error",
            "message": "Brak wymaganych pól: id_operacji, id_reaktora_docelowego."
        }), 400

    id_operacji = dane['id_operacji']
    id_reaktora_docelowego = int(dane['id_reaktora_docelowego'])
    operator = dane.get('operator', 'GUI')

    try:
        operacja = db.session.get(OperacjeLog, id_operacji)
        if not operacja:
            return jsonify({"status": "error", "message": f"Operacja o ID {id_operacji} nie istnieje."}), 404
        if operacja.status_operacji != 'aktywna':
            return jsonify({"status": "error", "message": "Operacja nie jest aktywna."}), 409
        if operacja.typ_operacji not in ('FILTRACJA_PLACEK_KOLO', 'FILTRACJA_WYDMUCH'):
            return jsonify({
                "status": "error",
                "message": f"Kontynuacja do FILTRACJA_PRZELEW tylko z operacji FILTRACJA_PLACEK_KOLO lub FILTRACJA_WYDMUCH (obecny: {operacja.typ_operacji})."
            }), 409

        mix = None
        if operacja.id_tank_mix:
            mix = db.session.get(TankMixes, operacja.id_tank_mix)
        if not mix and operacja.id_sprzetu_zrodlowego:
            reaktor = db.session.get(Sprzet, operacja.id_sprzetu_zrodlowego)
            if reaktor and reaktor.active_mix_id:
                mix = db.session.get(TankMixes, reaktor.active_mix_id)
        if not mix:
            return jsonify({"status": "error", "message": "Nie znaleziono mieszaniny dla tej operacji."}), 404

        # Dla FILTRACJA_PLACEK_KOLO: najpierw zakończ etap (is_wydmuch_mix, usunięcie WYDMUCH, 20% do pozostałych)
        if operacja.typ_operacji == 'FILTRACJA_PLACEK_KOLO':
            _apply_filtracja_na_placku_finish(mix)
        # Dla FILTRACJA_WYDMUCH: tylko usunięcie WYDMUCH + 20% do pozostałych, potem is_wydmuch_mix
        if operacja.typ_operacji == 'FILTRACJA_WYDMUCH':
            _apply_wydmuch_components_cleanup(mix)
            mix.is_wydmuch_mix = False

        id_zrodla = operacja.id_sprzetu_zrodlowego or mix.tank_id
        if id_zrodla == id_reaktora_docelowego:
            return jsonify({
                "status": "error",
                "message": "Reaktor docelowy musi być inny niż źródłowy (FILTRACJA_PRZELEW)."
            }), 400

        sprzet_docelowy = db.session.get(Sprzet, id_reaktora_docelowego)
        if not sprzet_docelowy or sprzet_docelowy.typ_sprzetu != 'reaktor':
            return jsonify({"status": "error", "message": "Nieprawidłowy reaktor docelowy."}), 400

        # 1. Zakończ FILTRACJA_PLACEK_KOLO
        operacja.status_operacji = 'zakonczona'
        operacja.czas_zakonczenia = dt.now(timezone.utc)
        if operacja.segmenty:
            for segment in operacja.segmenty:
                if segment.zawory:
                    segment.zawory.stan = 'ZAMKNIETY'

        mix.process_status = 'FILTRACJA_PRZELEW'
        tank_zrodlo = db.session.get(Sprzet, id_zrodla)
        nazwa_zrodla = tank_zrodlo.nazwa_unikalna if tank_zrodlo else None
        nazwa_celu = sprzet_docelowy.nazwa_unikalna
        start_point = f"{nazwa_zrodla}_OUT"
        end_point = f"{nazwa_celu}_IN"

        # Wszystkie zawory – trasę teoretycznie możliwą (zawory poprzedniej operacji są już zamknięte)
        all_valves = db.session.execute(db.select(Zawory.nazwa_zaworu)).scalars().all()
        open_valves_list = [v[0] if isinstance(v, (list, tuple)) else v for v in (all_valves or [])]

        pathfinder = get_pathfinder()
        filtry = db.session.execute(
            db.select(Sprzet.nazwa_unikalna).where(Sprzet.typ_sprzetu == 'filtr').order_by(Sprzet.nazwa_unikalna)
        ).scalars().all()
        if not filtry:
            db.session.rollback()
            return jsonify({"status": "error", "message": "Brak filtra w systemie."}), 400
        sprzet_posredni = None
        for nazwa_filtra in filtry:
            trasa_do_celu = pathfinder.find_path(f"{nazwa_filtra}_OUT", end_point, open_valves_list)
            if trasa_do_celu:
                sprzet_posredni = nazwa_filtra
                break
        if not sprzet_posredni:
            db.session.rollback()
            return jsonify({
                "status": "error",
                "message": f"Żaden filtr nie ma połączenia z reaktorem docelowym ({end_point})."
            }), 404

        posredni_in = f"{sprzet_posredni}_IN"
        posredni_out = f"{sprzet_posredni}_OUT"
        sciezka_1 = pathfinder.find_path(start_point, posredni_in, open_valves_list)
        if not sciezka_1:
            db.session.rollback()
            return jsonify({"status": "error", "message": f"Nie znaleziono ścieżki z {start_point} do {posredni_in}."}), 404
        sciezka_wewnetrzna = pathfinder.find_path(posredni_in, posredni_out, open_valves_list)
        if not sciezka_wewnetrzna:
            db.session.rollback()
            return jsonify({"status": "error", "message": f"Nie znaleziono ścieżki wewnętrznej w {sprzet_posredni}."}), 404
        sciezka_2 = pathfinder.find_path(posredni_out, end_point, open_valves_list)
        if not sciezka_2:
            db.session.rollback()
            return jsonify({"status": "error", "message": f"Nie znaleziono ścieżki z {posredni_out} do {end_point}."}), 404
        znaleziona_sciezka_nazwy = sciezka_1 + sciezka_wewnetrzna + sciezka_2

        konflikt_query = db.select(Segmenty.nazwa_segmentu).join(Segmenty.operacje_log).where(
            OperacjeLog.status_operacji == 'aktywna',
            Segmenty.nazwa_segmentu.in_(znaleziona_sciezka_nazwy)
        )
        konflikty = db.session.execute(konflikt_query).scalars().all()
        if konflikty:
            db.session.rollback()
            return jsonify({
                "status": "error",
                "message": "Konflikt zasobów - trasa zajęta przez inną operację.",
                "zajete_segmenty": [k for k in konflikty]
            }), 409

        zawory_na_trasie = set()
        for u, v, edge_data in pathfinder.graph.edges(data=True):
            if edge_data.get('segment_name') in znaleziona_sciezka_nazwy:
                zawory_na_trasie.add(edge_data['valve_name'])
        if zawory_na_trasie:
            db.session.execute(
                db.update(Zawory).where(Zawory.nazwa_zaworu.in_(zawory_na_trasie)).values(stan='OTWARTY')
            )

        nowa_operacja = OperacjeLog(
            typ_operacji='FILTRACJA_PRZELEW',
            id_tank_mix=mix.id,
            id_sprzetu_zrodlowego=id_zrodla,
            id_sprzetu_docelowego=id_reaktora_docelowego,
            status_operacji='aktywna',
            czas_rozpoczecia=dt.now(timezone.utc),
            opis=f"Operacja FILTRACJA_PRZELEW z {start_point} do {end_point}",
            punkt_startowy=start_point,
            punkt_docelowy=end_point,
            zmodyfikowane_przez=operator,
        )
        db.session.add(nowa_operacja)
        db.session.flush()
        segmenty_trasy = db.session.execute(
            db.select(Segmenty).where(Segmenty.nazwa_segmentu.in_(znaleziona_sciezka_nazwy))
        ).scalars().all()
        nowa_operacja.segmenty = list(segmenty_trasy)

        db.session.commit()
        try:
            broadcast_dashboard_update()
        except Exception:
            pass
        return jsonify({
            "status": "success",
            "message": "Zakończono FILTRACJA_PLACEK_KOLO i rozpoczęto FILTRACJA_PRZELEW.",
            "id_operacji": nowa_operacja.id,
        }), 200
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route('/continue-to-kolo', methods=['POST'])
def continue_to_kolo():
    """
    Kończy bieżącą operację FILTRACJA_PRZELEW lub FILTRACJA_PLACEK_PRZELEW
    i uruchamia następny etap: FILTRACJA_KOLO (rezerwując trasę przez filtr).
    """
    dane = request.get_json()
    if not dane or 'id_operacji' not in dane:
        return jsonify({"status": "error", "message": "Brak wymaganego pola: id_operacji."}), 400

    id_operacji = dane['id_operacji']
    operator = dane.get('operator', 'GUI')
    try:
        operacja = db.session.get(OperacjeLog, id_operacji)
        if not operacja:
            return jsonify({"status": "error", "message": f"Operacja o ID {id_operacji} nie istnieje."}), 404
        if operacja.status_operacji != 'aktywna':
            return jsonify({"status": "error", "message": "Operacja nie jest aktywna."}), 409
        if operacja.typ_operacji not in ('FILTRACJA_PRZELEW', 'FILTRACJA_PLACEK_PRZELEW', 'FILTRACJA_NA_PLACKU'):
            return jsonify({
                "status": "error",
                "message": f"Kontynuacja do FILTRACJA_KOLO tylko z operacji FILTRACJA_PRZELEW, FILTRACJA_PLACEK_PRZELEW lub FILTRACJA_NA_PLACKU (obecny: {operacja.typ_operacji})."
            }), 409

        mix = None
        if operacja.id_tank_mix:
            mix = db.session.get(TankMixes, operacja.id_tank_mix)
        if not mix and operacja.id_sprzetu_zrodlowego:
            reaktor = db.session.get(Sprzet, operacja.id_sprzetu_zrodlowego)
            if reaktor and reaktor.active_mix_id:
                mix = db.session.get(TankMixes, reaktor.active_mix_id)
        if not mix:
            return jsonify({"status": "error", "message": "Nie znaleziono mieszaniny dla tej operacji."}), 404

        # Dla FILTRACJA_NA_PLACKU i FILTRACJA_PLACEK_PRZELEW: najpierw zakończ etap (is_wydmuch_mix, usunięcie WYDMUCH, 20% do pozostałych)
        if operacja.typ_operacji in ('FILTRACJA_NA_PLACKU', 'FILTRACJA_PLACEK_PRZELEW'):
            _apply_filtracja_na_placku_finish(mix)
        if operacja.typ_operacji == 'FILTRACJA_NA_PLACKU':
            mix.filtration_cycles_count = (mix.filtration_cycles_count or 0) + 1

        # 1. Zakończ bieżącą operację: zamknij zawory, ustaw next_status, przenieś mix jeśli cel≠źródło
        operacja.status_operacji = 'zakonczona'
        operacja.czas_zakonczenia = dt.now(timezone.utc)
        if operacja.segmenty:
            for segment in operacja.segmenty:
                if segment.zawory:
                    segment.zawory.stan = 'ZAMKNIETY'

        # Po FILTRACJA_PRZELEW / FILTRACJA_PLACEK_PRZELEW / FILTRACJA_NA_PLACKU mix jest już w reaktorze docelowym
        next_status = {
            'FILTRACJA_PRZELEW': 'FILTRACJA_KOLO',
            'FILTRACJA_PLACEK_PRZELEW': 'FILTRACJA_KOLO',
            'FILTRACJA_NA_PLACKU': 'FILTRACJA_KOLO',
        }.get(operacja.typ_operacji)
        if next_status:
            mix.process_status = next_status
        if (
            operacja.id_sprzetu_zrodlowego is not None
            and operacja.id_sprzetu_docelowego is not None
            and operacja.id_sprzetu_zrodlowego != operacja.id_sprzetu_docelowego
        ):
            mix.tank_id = operacja.id_sprzetu_docelowego
            sprzet_zrodlowy = db.session.get(Sprzet, operacja.id_sprzetu_zrodlowego)
            sprzet_docelowy = db.session.get(Sprzet, operacja.id_sprzetu_docelowego)
            if sprzet_zrodlowy and sprzet_zrodlowy.active_mix_id == mix.id:
                sprzet_zrodlowy.active_mix_id = None
            if sprzet_docelowy:
                sprzet_docelowy.active_mix_id = mix.id

        # 2. Ustaw mix na etap FILTRACJA_KOLO i wyznacz trasę (reaktor → filtr → ten sam reaktor)
        mix.process_status = 'FILTRACJA_KOLO'
        tank = db.session.get(Sprzet, mix.tank_id)
        if not tank:
            db.session.rollback()
            return jsonify({"status": "error", "message": "Brak reaktora dla mieszaniny."}), 404
        nazwa = tank.nazwa_unikalna
        start_point = f"{nazwa}_OUT"
        end_point = f"{nazwa}_IN"

        # Wszystkie zawory – trasę teoretycznie możliwą (zawory poprzedniej operacji są już zamknięte)
        all_valves = db.session.execute(db.select(Zawory.nazwa_zaworu)).scalars().all()
        open_valves_list = [v[0] if isinstance(v, (list, tuple)) else v for v in (all_valves or [])]

        pathfinder = get_pathfinder()
        filtry = db.session.execute(
            db.select(Sprzet.nazwa_unikalna).where(Sprzet.typ_sprzetu == 'filtr').order_by(Sprzet.nazwa_unikalna)
        ).scalars().all()
        if not filtry:
            db.session.rollback()
            return jsonify({"status": "error", "message": "Brak filtra w systemie."}), 400
        sprzet_posredni = None
        for nazwa_filtra in filtry:
            trasa_do_celu = pathfinder.find_path(f"{nazwa_filtra}_OUT", end_point, open_valves_list)
            if trasa_do_celu:
                sprzet_posredni = nazwa_filtra
                break
        if not sprzet_posredni:
            db.session.rollback()
            return jsonify({
                "status": "error",
                "message": f"Żaden filtr nie ma połączenia z reaktorem docelowym ({end_point})."
            }), 404

        posredni_in = f"{sprzet_posredni}_IN"
        posredni_out = f"{sprzet_posredni}_OUT"
        sciezka_1 = pathfinder.find_path(start_point, posredni_in, open_valves_list)
        if not sciezka_1:
            db.session.rollback()
            return jsonify({"status": "error", "message": f"Nie znaleziono ścieżki z {start_point} do {posredni_in}."}), 404
        sciezka_wewnetrzna = pathfinder.find_path(posredni_in, posredni_out, open_valves_list)
        if not sciezka_wewnetrzna:
            db.session.rollback()
            return jsonify({"status": "error", "message": f"Nie znaleziono ścieżki wewnętrznej w {sprzet_posredni}."}), 404
        sciezka_2 = pathfinder.find_path(posredni_out, end_point, open_valves_list)
        if not sciezka_2:
            db.session.rollback()
            return jsonify({"status": "error", "message": f"Nie znaleziono ścieżki z {posredni_out} do {end_point}."}), 404
        znaleziona_sciezka_nazwy = sciezka_1 + sciezka_wewnetrzna + sciezka_2

        konflikt_query = db.select(Segmenty.nazwa_segmentu).join(Segmenty.operacje_log).where(
            OperacjeLog.status_operacji == 'aktywna',
            Segmenty.nazwa_segmentu.in_(znaleziona_sciezka_nazwy)
        )
        konflikty = db.session.execute(konflikt_query).scalars().all()
        if konflikty:
            db.session.rollback()
            return jsonify({
                "status": "error",
                "message": "Konflikt zasobów - trasa zajęta przez inną operację.",
                "zajete_segmenty": [k for k in konflikty]
            }), 409

        zawory_na_trasie = set()
        for u, v, edge_data in pathfinder.graph.edges(data=True):
            if edge_data.get('segment_name') in znaleziona_sciezka_nazwy:
                zawory_na_trasie.add(edge_data['valve_name'])
        if zawory_na_trasie:
            db.session.execute(
                db.update(Zawory).where(Zawory.nazwa_zaworu.in_(zawory_na_trasie)).values(stan='OTWARTY')
            )

        nowa_operacja = OperacjeLog(
            typ_operacji='FILTRACJA_KOLO',
            id_tank_mix=mix.id,
            id_sprzetu_zrodlowego=mix.tank_id,
            id_sprzetu_docelowego=mix.tank_id,
            status_operacji='aktywna',
            czas_rozpoczecia=dt.now(timezone.utc),
            opis=f"Operacja FILTRACJA_KOLO z {start_point} do {end_point}",
            punkt_startowy=start_point,
            punkt_docelowy=end_point,
            zmodyfikowane_przez=operator,
        )
        db.session.add(nowa_operacja)
        db.session.flush()
        segmenty_trasy = db.session.execute(
            db.select(Segmenty).where(Segmenty.nazwa_segmentu.in_(znaleziona_sciezka_nazwy))
        ).scalars().all()
        nowa_operacja.segmenty = list(segmenty_trasy)

        db.session.commit()
        try:
            broadcast_dashboard_update()
        except Exception:
            pass
        return jsonify({
            "status": "success",
            "message": "Zakończono poprzedni etap i rozpoczęto FILTRACJA_KOLO.",
            "id_operacji": nowa_operacja.id,
        }), 200
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route('/continue-to-ocena', methods=['POST'])
def continue_to_ocena():
    """
    Kończy operację FILTRACJA_KOLO i na podstawie wyniku oceny próbki ustawia
    mix.process_status na ZATWIERDZONA (tworzy operację FILTRACJA_KOLO_ZATWIERDZONA)
    lub DO_PONOWNEJ_FILTRACJI.
    """
    dane = request.get_json()
    if not dane or 'id_operacji' not in dane or 'wynik_oceny' not in dane:
        return jsonify({
            "status": "error",
            "message": "Brak wymaganych pól: id_operacji, wynik_oceny (OK lub DO_PONOWNEJ_FILTRACJI)."
        }), 400

    id_operacji = dane['id_operacji']
    wynik_oceny = (dane.get('wynik_oceny') or '').strip().upper()
    if wynik_oceny not in ('OK', 'DO_PONOWNEJ_FILTRACJI'):
        return jsonify({
            "status": "error",
            "message": "wynik_oceny musi być 'OK' lub 'DO_PONOWNEJ_FILTRACJI'."
        }), 400
    powod = dane.get('powod', '').strip() if dane.get('powod') else ''
    operator = dane.get('operator', 'GUI')

    try:
        operacja = db.session.get(OperacjeLog, id_operacji)
        if not operacja:
            return jsonify({"status": "error", "message": f"Operacja o ID {id_operacji} nie istnieje."}), 404
        if operacja.status_operacji != 'aktywna':
            return jsonify({"status": "error", "message": "Operacja nie jest aktywna."}), 409
        if operacja.typ_operacji != 'FILTRACJA_KOLO':
            return jsonify({
                "status": "error",
                "message": f"Ocena próbki tylko z operacji FILTRACJA_KOLO (obecny: {operacja.typ_operacji})."
            }), 409

        mix = None
        if operacja.id_tank_mix:
            mix = db.session.get(TankMixes, operacja.id_tank_mix)
        if not mix and operacja.id_sprzetu_zrodlowego:
            reaktor = db.session.get(Sprzet, operacja.id_sprzetu_zrodlowego)
            if reaktor and reaktor.active_mix_id:
                mix = db.session.get(TankMixes, reaktor.active_mix_id)
        if not mix:
            return jsonify({"status": "error", "message": "Nie znaleziono mieszaniny dla tej operacji."}), 404

        # 1. Zakończ FILTRACJA_KOLO: zamknij zawory. Segmenty przenosimy do nowej operacji
        # FILTRACJA_KOLO_ZATWIERDZONA, aby nadal blokowały trasę.
        operacja.status_operacji = 'zakonczona'
        operacja.czas_zakonczenia = dt.now(timezone.utc)
        segmenty_kola = list(operacja.segmenty) if operacja.segmenty else []
        if operacja.segmenty:
            for segment in operacja.segmenty:
                if segment.zawory:
                    segment.zawory.stan = 'ZAMKNIETY'
            # Zwolnij powiązanie segmentów z zakończoną operacją – przeniesiemy je do nowej
            operacja.segmenty = []

        if wynik_oceny == 'OK':
            mix.process_status = 'ZATWIERDZONA'
            tank_id = mix.tank_id
            nowa_operacja = OperacjeLog(
                typ_operacji='FILTRACJA_KOLO_ZATWIERDZONA',
                id_tank_mix=mix.id,
                id_sprzetu_zrodlowego=tank_id,
                id_sprzetu_docelowego=tank_id,
                status_operacji='aktywna',
                czas_rozpoczecia=dt.now(timezone.utc),
                opis='Ocena próbki: OK. Mieszanina zatwierdzona – możliwy przelew na magazyn.',
                zmodyfikowane_przez=operator,
            )
            db.session.add(nowa_operacja)
            # Przenieś segmenty trasy FILTRACJA_KOLO do nowej operacji, aby nadal blokowały trasę
            # oraz ponownie otwórz zawory na tej trasie (tak jak przy nowym uruchomieniu operacji).
            if segmenty_kola:
                nowa_operacja.segmenty = segmenty_kola
                for segment in segmenty_kola:
                    if segment.zawory:
                        segment.zawory.stan = 'OTWARTY'
            db.session.commit()
            try:
                broadcast_dashboard_update()
            except Exception:
                pass
            return jsonify({
                "status": "success",
                "message": "Ocena: OK. Mieszanina zatwierdzona. Możesz wybrać operację Na magazyn.",
                "process_status": "ZATWIERDZONA",
                "id_operacji": nowa_operacja.id,
            }), 200
        else:
            mix.process_status = 'DO_PONOWNEJ_FILTRACJI'
            log_ocena = OperacjeLog(
                typ_operacji='OCENA_JAKOSCI',
                id_tank_mix=mix.id,
                status_operacji='zakonczona',
                czas_rozpoczecia=dt.now(timezone.utc),
                czas_zakonczenia=dt.now(timezone.utc),
                opis=f"Ocena próbki: do ponownej filtracji. {powod}" if powod else "Ocena próbki: do ponownej filtracji.",
                zmodyfikowane_przez=operator,
            )
            db.session.add(log_ocena)

            # Utwórz nową operację FILTRACJA_KOLO_DO_PONOWNEJ, która blokuje trasę tak jak FILTRACJA_KOLO
            # i pozwala przejść do DMUCHANIE (ale bez możliwości NA_MAGAZYN).
            nowa_operacja = None
            tank_id = mix.tank_id
            if tank_id and segmenty_kola:
                nowa_operacja = OperacjeLog(
                    typ_operacji='FILTRACJA_KOLO_DO_PONOWNEJ',
                    id_tank_mix=mix.id,
                    id_sprzetu_zrodlowego=tank_id,
                    id_sprzetu_docelowego=tank_id,
                    status_operacji='aktywna',
                    czas_rozpoczecia=dt.now(timezone.utc),
                    opis='Ocena próbki: do ponownej filtracji – trasa zablokowana do DMUCHANIE.',
                    zmodyfikowane_przez=operator,
                )
                db.session.add(nowa_operacja)
                nowa_operacja.segmenty = segmenty_kola
                for segment in segmenty_kola:
                    if segment.zawory:
                        segment.zawory.stan = 'OTWARTY'

            db.session.commit()
            try:
                broadcast_dashboard_update()
            except Exception:
                pass
            return jsonify({
                "status": "success",
                "message": "Ocena: do ponownej filtracji. Status mieszaniny zaktualizowany.",
                "process_status": "DO_PONOWNEJ_FILTRACJI",
                "id_operacji": nowa_operacja.id if nowa_operacja else None,
            }), 200
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route('/continue-to-magazyn', methods=['POST'])
def continue_to_magazyn():
    """
    Przenosi mieszaninę z reaktora do wybranej beczki czystej, wyznacza nową trasę do celu
    i ustawia typ_operacji na NA_MAGAZYN. Operacja pozostaje aktywna (możliwość przejścia do DMUCHANIE).
    Wymaga id_operacji i id_beczki_czystej.
    """
    dane = request.get_json()
    if not dane or 'id_operacji' not in dane or 'id_beczki_czystej' not in dane:
        return jsonify({
            "status": "error",
            "message": "Brak wymaganych pól: id_operacji, id_beczki_czystej."
        }), 400

    id_operacji = int(dane['id_operacji'])
    id_beczki_czystej = int(dane['id_beczki_czystej'])
    operator = dane.get('operator', 'GUI')

    try:
        operacja = db.session.get(OperacjeLog, id_operacji)
        if not operacja:
            return jsonify({"status": "error", "message": f"Operacja o ID {id_operacji} nie istnieje."}), 404
        if operacja.status_operacji != 'aktywna':
            return jsonify({"status": "error", "message": "Operacja nie jest aktywna."}), 409
        if operacja.typ_operacji != 'FILTRACJA_KOLO_ZATWIERDZONA':
            return jsonify({
                "status": "error",
                "message": f"Kontynuacja na magazyn tylko z operacji FILTRACJA_KOLO_ZATWIERDZONA (obecny: {operacja.typ_operacji})."
            }), 409

        id_reaktora = operacja.id_sprzetu_zrodlowego
        if not id_reaktora:
            return jsonify({"status": "error", "message": "Operacja nie ma przypisanego reaktora źródłowego."}), 400

        reaktor = db.session.get(Sprzet, id_reaktora)
        if not reaktor or reaktor.typ_sprzetu != 'reaktor':
            return jsonify({"status": "error", "message": "Nieprawidłowy reaktor źródłowy operacji."}), 400
        if not reaktor.active_mix_id:
            return jsonify({"status": "error", "message": "W reaktorze źródłowym nie ma mieszaniny."}), 400

        beczka = db.session.get(Sprzet, id_beczki_czystej)
        if not beczka or beczka.typ_sprzetu != 'beczka_czysta':
            return jsonify({"status": "error", "message": "Wybrany cel nie jest beczką czystą."}), 400

        composition = BatchManagementService.get_mix_composition(reaktor.active_mix_id)
        total_weight = float(composition.get('total_weight', 0))
        if total_weight <= 0:
            return jsonify({"status": "error", "message": "Mieszanina w reaktorze ma zerową wagę."}), 400

        # Zamknij zawory i zwolnij starą trasę FILTRACJA_KOLO_ZATWIERDZONA (jak przy zakończeniu operacji),
        # zanim wyznaczymy nową trasę NA_MAGAZYN.
        if operacja.segmenty:
            for segment in operacja.segmenty:
                if segment.zawory:
                    segment.zawory.stan = 'ZAMKNIETY'
            operacja.segmenty = []

        # Wyznaczenie trasy: reaktor_OUT → beczka_IN (wszystkie zawory otwarte)
        start_point = f"{reaktor.nazwa_unikalna}_OUT"
        end_point = f"{beczka.nazwa_unikalna}_IN"
        pathfinder = get_pathfinder()
        all_valves = db.session.execute(db.select(Zawory.nazwa_zaworu)).scalars().all()
        open_valves_list = [v[0] if isinstance(v, (list, tuple)) else v for v in (all_valves or [])]
        znaleziona_sciezka_nazwy = pathfinder.find_path(start_point, end_point, open_valves_list)
        if not znaleziona_sciezka_nazwy:
            return jsonify({
                "status": "error",
                "message": f"Nie znaleziono trasy z {reaktor.nazwa_unikalna} do {beczka.nazwa_unikalna}."
            }), 400

        # Konflikt: segmenty z nowej trasy używane przez INNE aktywne operacje (bieżąca jest aktualizowana – nie liczymy jej)
        konflikt_query = (
            db.select(Segmenty.nazwa_segmentu)
            .select_from(Segmenty)
            .join(t_log_uzyte_segmenty, Segmenty.id == t_log_uzyte_segmenty.c.id_segmentu)
            .join(OperacjeLog, t_log_uzyte_segmenty.c.id_operacji_log == OperacjeLog.id)
            .where(
                OperacjeLog.status_operacji == 'aktywna',
                OperacjeLog.id != id_operacji,
                Segmenty.nazwa_segmentu.in_(znaleziona_sciezka_nazwy),
            )
        )
        konflikty = db.session.execute(konflikt_query).scalars().all()
        if konflikty:
            return jsonify({
                "status": "error",
                "message": "Konflikt zasobów – segmenty trasy są używane przez inną operację.",
                "zajete_segmenty": [k[0] if isinstance(k, (list, tuple)) else k for k in konflikty]
            }), 409

        # Aktualizacja operacji: cel, nowa trasa, typ NA_MAGAZYN; operacja pozostaje aktywna
        operacja.id_sprzetu_docelowego = id_beczki_czystej
        operacja.typ_operacji = 'NA_MAGAZYN'
        operacja.opis = f"NA_MAGAZYN: {reaktor.nazwa_unikalna} → {beczka.nazwa_unikalna}"
        operacja.punkt_startowy = start_point
        operacja.punkt_docelowy = end_point

        segmenty_trasy = db.session.execute(
            db.select(Segmenty).where(Segmenty.nazwa_segmentu.in_(znaleziona_sciezka_nazwy))
        ).scalars().all()
        operacja.segmenty = list(segmenty_trasy)

        # Otwórz zawory na nowej trasie NA_MAGAZYN (reaktor → beczka),
        # tak jak przy normalnym uruchamianiu operacji transferu.
        zawory_na_trasie = set()
        for u, v, edge_data in pathfinder.graph.edges(data=True):
            if edge_data.get('segment_name') in znaleziona_sciezka_nazwy and 'valve_name' in edge_data:
                zawory_na_trasie.add(edge_data['valve_name'])
        if zawory_na_trasie:
            db.session.execute(
                db.update(Zawory).where(Zawory.nazwa_zaworu.in_(zawory_na_trasie)).values(stan='OTWARTY')
            )

        # Przelew mieszaniny
        BatchManagementService.transfer_between_dirty_tanks(
            source_tank_id=id_reaktora,
            destination_tank_id=id_beczki_czystej,
            quantity_to_transfer=Decimal(str(total_weight)),
            operator=operator,
        )
        db.session.commit()
        try:
            broadcast_dashboard_update()
        except Exception:
            pass
        return jsonify({
            "status": "success",
            "message": f"Mieszanina przelana do {beczka.nazwa_unikalna}. Operacja aktywna – możesz przejść do DMUCHANIE.",
        }), 200
    except ValueError as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route('/continue-to-dmuchanie', methods=['POST'])
def continue_to_dmuchanie():
    """
    Kończy operację NA_MAGAZYN i tworzy nową, osobną operację DMUCHANIE w operacje_log.
    Nowa operacja korzysta z tej samej trasy (segmenty) co zakończona NA_MAGAZYN – blokuje ją na czas dmuchania.
    """
    dane = request.get_json()
    if not dane or 'id_operacji' not in dane:
        return jsonify({"status": "error", "message": "Brak wymaganego pola: id_operacji."}), 400

    id_operacji = int(dane['id_operacji'])
    operator = dane.get('operator', 'GUI')

    try:
        operacja = db.session.execute(
            db.select(OperacjeLog).options(joinedload(OperacjeLog.segmenty)).where(OperacjeLog.id == id_operacji)
        ).unique().scalar_one_or_none()
        if not operacja:
            return jsonify({"status": "error", "message": f"Operacja o ID {id_operacji} nie istnieje."}), 404
        if operacja.status_operacji != 'aktywna':
            return jsonify({"status": "error", "message": "Operacja nie jest aktywna."}), 409
        if operacja.typ_operacji not in ('NA_MAGAZYN', 'FILTRACJA_KOLO_DO_PONOWNEJ'):
            return jsonify({
                "status": "error",
                "message": f"Przejście do DMUCHANIE tylko z operacji NA_MAGAZYN lub FILTRACJA_KOLO_DO_PONOWNEJ (obecny: {operacja.typ_operacji})."
            }), 409

        # Zakończenie operacji NA_MAGAZYN
        operacja.status_operacji = 'zakonczona'
        operacja.czas_zakonczenia = dt.now(timezone.utc)

        # Nowa operacja DMUCHANIE – ta sama trasa (źródło, cel, segmenty)
        zrodlo_nazwa = operacja.sprzet_zrodlowy.nazwa_unikalna if operacja.sprzet_zrodlowy else '—'
        cel_nazwa = operacja.sprzet_docelowy.nazwa_unikalna if operacja.sprzet_docelowy else '—'
        nowa_operacja = OperacjeLog(
            typ_operacji='DMUCHANIE',
            status_operacji='aktywna',
            czas_rozpoczecia=dt.now(timezone.utc),
            id_sprzetu_zrodlowego=operacja.id_sprzetu_zrodlowego,
            id_sprzetu_docelowego=operacja.id_sprzetu_docelowego,
            opis=f"DMUCHANIE: {zrodlo_nazwa} → {cel_nazwa}",
            punkt_startowy=operacja.punkt_startowy,
            punkt_docelowy=operacja.punkt_docelowy,
            zmodyfikowane_przez=operator,
        )
        db.session.add(nowa_operacja)
        db.session.flush()
        nowa_operacja.segmenty = list(operacja.segmenty)
        db.session.commit()
        try:
            broadcast_dashboard_update()
        except Exception:
            pass
        return jsonify({
            "status": "success",
            "message": "Operacja NA_MAGAZYN zakończona. Rozpoczęto operację DMUCHANIE (ta sama trasa).",
            "id_operacji_dmuchanie": nowa_operacja.id,
        }), 200
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route('/continue-to-dmuchanie-czyszczenie', methods=['POST'])
def continue_to_dmuchanie_czyszczenie():
    """
    Kończy operację NA_MAGAZYN lub FILTRACJA_KOLO_DO_PONOWNEJ i tworzy nową
    operację DMUCHANIE_CZYSZCZENIE z nową trasą do wskazanego sprzętu docelowego.
    Źródło DMUCHANIE_CZYSZCZENIE = sprzęt źródłowy zakończonej operacji.
    Body: { id_operacji, id_sprzetu_docelowego, operator? }
    """
    dane = request.get_json()
    if not dane or 'id_operacji' not in dane or 'id_sprzetu_docelowego' not in dane:
        return jsonify({"status": "error", "message": "Wymagane pola: id_operacji, id_sprzetu_docelowego."}), 400

    id_operacji = int(dane['id_operacji'])
    id_celu = int(dane['id_sprzetu_docelowego'])
    operator = dane.get('operator', 'GUI')

    try:
        operacja = db.session.execute(
            db.select(OperacjeLog).options(joinedload(OperacjeLog.segmenty)).where(OperacjeLog.id == id_operacji)
        ).unique().scalar_one_or_none()

        if not operacja:
            return jsonify({"status": "error", "message": f"Operacja o ID {id_operacji} nie istnieje."}), 404
        if operacja.status_operacji != 'aktywna':
            return jsonify({"status": "error", "message": "Operacja nie jest aktywna."}), 409
        if operacja.typ_operacji not in ('NA_MAGAZYN', 'FILTRACJA_KOLO_DO_PONOWNEJ'):
            return jsonify({"status": "error",
                            "message": f"Przejście do DMUCHANIE_CZYSZCZENIE tylko z NA_MAGAZYN lub FILTRACJA_KOLO_DO_PONOWNEJ (obecny: {operacja.typ_operacji})."}), 409

        cel = db.session.get(Sprzet, id_celu)
        if not cel:
            return jsonify({"status": "error", "message": f"Sprzęt docelowy o ID {id_celu} nie istnieje."}), 404

        zrodlo = db.session.get(Sprzet, operacja.id_sprzetu_zrodlowego) if operacja.id_sprzetu_zrodlowego else None
        if not zrodlo:
            return jsonify({"status": "error", "message": "Operacja nie ma przypisanego sprzętu źródłowego."}), 409

        # Zakończ poprzednią operację i zwolnij jej trasę
        if operacja.segmenty:
            for segment in operacja.segmenty:
                if segment.zawory:
                    segment.zawory.stan = 'ZAMKNIETY'
            operacja.segmenty = []
        operacja.status_operacji = 'zakonczona'
        operacja.czas_zakonczenia = dt.now(timezone.utc)
        db.session.flush()

        # Wyznacz nową trasę: źródło_OUT → cel_IN
        start_point = f"{zrodlo.nazwa_unikalna}_OUT"
        end_point = f"{cel.nazwa_unikalna}_IN"
        pathfinder = get_pathfinder()
        all_valves = db.session.execute(db.select(Zawory.nazwa_zaworu)).scalars().all()
        open_valves_list = [v[0] if isinstance(v, (list, tuple)) else v for v in (all_valves or [])]
        znaleziona_sciezka_nazwy = pathfinder.find_path(start_point, end_point, open_valves_list)

        if not znaleziona_sciezka_nazwy:
            return jsonify({"status": "error", "message": f"Nie znaleziono trasy od {start_point} do {end_point}."}), 409

        # Sprawdź konflikty z innymi aktywnymi operacjami
        konflikt_query = (
            db.select(Segmenty.nazwa_segmentu)
            .select_from(Segmenty)
            .join(t_log_uzyte_segmenty, Segmenty.id == t_log_uzyte_segmenty.c.id_segmentu)
            .join(OperacjeLog, t_log_uzyte_segmenty.c.id_operacji_log == OperacjeLog.id)
            .where(
                OperacjeLog.status_operacji == 'aktywna',
                Segmenty.nazwa_segmentu.in_(znaleziona_sciezka_nazwy),
            )
        )
        konflikty = db.session.execute(konflikt_query).all()
        if konflikty:
            return jsonify({
                "status": "error",
                "message": "Konflikt zasobów – segmenty nowej trasy są używane przez inną aktywną operację.",
                "zajete_segmenty": [k[0] if isinstance(k, (list, tuple)) else k for k in konflikty],
            }), 409

        # Zapisz ID mixa źródłowego do późniejszego użycia przy finish
        id_mix_zrodla = zrodlo.active_mix_id if zrodlo.active_mix_id else operacja.id_tank_mix

        nowa_operacja = OperacjeLog(
            typ_operacji='DMUCHANIE_CZYSZCZENIE',
            status_operacji='aktywna',
            czas_rozpoczecia=dt.now(timezone.utc),
            id_sprzetu_zrodlowego=zrodlo.id,
            id_sprzetu_docelowego=cel.id,
            id_tank_mix=id_mix_zrodla,
            opis=f"DMUCHANIE_CZYSZCZENIE: {zrodlo.nazwa_unikalna} → {cel.nazwa_unikalna}",
            punkt_startowy=start_point,
            punkt_docelowy=end_point,
            zmodyfikowane_przez=operator,
        )
        db.session.add(nowa_operacja)
        db.session.flush()

        segmenty_trasy = db.session.execute(
            db.select(Segmenty).where(Segmenty.nazwa_segmentu.in_(znaleziona_sciezka_nazwy))
        ).scalars().all()
        nowa_operacja.segmenty = list(segmenty_trasy)

        zawory_na_trasie = set()
        for u, v, edge_data in pathfinder.graph.edges(data=True):
            if edge_data.get('segment_name') in znaleziona_sciezka_nazwy and 'valve_name' in edge_data:
                zawory_na_trasie.add(edge_data['valve_name'])
        if zawory_na_trasie:
            db.session.execute(
                db.update(Zawory).where(Zawory.nazwa_zaworu.in_(zawory_na_trasie)).values(stan='OTWARTY')
            )

        db.session.commit()
        try:
            broadcast_dashboard_update()
        except Exception:
            pass
        return jsonify({
            "status": "success",
            "message": f"Operacja zakończona. Rozpoczęto DMUCHANIE_CZYSZCZENIE: {zrodlo.nazwa_unikalna} → {cel.nazwa_unikalna}.",
            "id_operacji_dmuchanie": nowa_operacja.id,
        }), 200
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------------------------------------------------------------------------
# DMUCHANIE_CZYSZCZENIE – destinations (reaktory do wyboru jako cel)
# ---------------------------------------------------------------------------
@bp.route('/dmuchanie-czyszczenie-destinations', methods=['GET'])
def dmuchanie_czyszczenie_destinations():
    """
    Zwraca listę reaktorów możliwych jako cel DMUCHANIE_CZYSZCZENIE:
    - wszystkie reaktory (puste i z mixem – wydmuch można dodać do istniejącego mixu),
    - z fizycznie możliwą trasą od filtra poprzedniej operacji (FZ_OUT → cel_IN).
    Gdy id_operacji: filtr z segmentów operacji. Gdy id_sprzetu_zrodlowego: użyj jako źródło.
    Query: id_operacji (zalecane) LUB id_sprzetu_zrodlowego.
    """
    id_operacji = request.args.get('id_operacji', type=int)
    id_zrodla = request.args.get('id_sprzetu_zrodlowego', type=int)
    if not id_operacji and not id_zrodla:
        return jsonify({"status": "error", "message": "Wymagany parametr: id_operacji lub id_sprzetu_zrodlowego."}), 400

    try:
        from sqlalchemy.orm import joinedload

        filtry_z_operacji = []

        if id_operacji:
            operacja = db.session.execute(
                db.select(OperacjeLog).options(joinedload(OperacjeLog.segmenty)).where(OperacjeLog.id == id_operacji)
            ).unique().scalar_one_or_none()
            if not operacja:
                return jsonify({"status": "error", "message": f"Operacja o ID {id_operacji} nie istnieje."}), 404
            # Filtr(y) z segmentów poprzedniej operacji
            port_ids = set()
            for seg in (operacja.segmenty or []):
                if getattr(seg, 'id_portu_startowego', None):
                    port_ids.add(seg.id_portu_startowego)
                if getattr(seg, 'id_portu_koncowego', None):
                    port_ids.add(seg.id_portu_koncowego)
            if port_ids:
                raw = db.session.execute(
                    db.select(Sprzet.nazwa_unikalna)
                    .join(PortySprzetu, PortySprzetu.id_sprzetu == Sprzet.id)
                    .where(PortySprzetu.id.in_(port_ids), Sprzet.typ_sprzetu == 'filtr')
                    .distinct()
                ).scalars().all()
                filtry_z_operacji = [r[0] if isinstance(r, (list, tuple)) else r for r in raw]

        all_valves = db.session.execute(db.select(Zawory.nazwa_zaworu)).scalars().all()
        open_valves_list = [v[0] if isinstance(v, (list, tuple)) else v for v in (all_valves or [])]
        pathfinder = get_pathfinder()
        wszystkie_filtry = db.session.execute(
            db.select(Sprzet.nazwa_unikalna).where(Sprzet.typ_sprzetu == 'filtr').order_by(Sprzet.nazwa_unikalna)
        ).scalars().all()
        if not wszystkie_filtry:
            return jsonify({"destinations": [], "message": "Brak filtra w systemie."}), 200

        # Wszystkie reaktory (puste i z mixem – wydmuch można dodać do istniejącego mixu)
        reaktory_q = db.select(Sprzet).where(Sprzet.typ_sprzetu == 'reaktor').order_by(Sprzet.nazwa_unikalna)
        reaktory = db.session.execute(reaktory_q).scalars().all()

        destinations = []
        for r in reaktory:
            end_point = f"{r.nazwa_unikalna}_IN"
            trasa_ok = False
            if filtry_z_operacji:
                for nazwa_filtra in filtry_z_operacji:
                    if pathfinder.find_path(f"{nazwa_filtra}_OUT", end_point, open_valves_list):
                        trasa_ok = True
                        break
            else:
                # Fallback: id_sprzetu_zrodlowego (np. filtr) lub dowolny filtr
                if id_zrodla:
                    zrodlo = db.session.get(Sprzet, id_zrodla)
                    if zrodlo and r.id != id_zrodla:
                        start_pt = f"{zrodlo.nazwa_unikalna}_OUT"
                        if pathfinder.find_path(start_pt, end_point, open_valves_list):
                            trasa_ok = True
                if not trasa_ok:
                    for f in wszystkie_filtry:
                        nazwa_filtra = f[0] if isinstance(f, (list, tuple)) else f
                        if pathfinder.find_path(f"{nazwa_filtra}_OUT", end_point, open_valves_list):
                            trasa_ok = True
                            break
            if trasa_ok:
                material_types_text = None
                if r.active_mix_id:
                    composition = BatchManagementService.get_mix_composition(r.active_mix_id)
                    material_types = [s['material_type'] for s in composition.get('summary_by_material', [])]
                    if material_types:
                        material_types_text = ' + '.join(material_types)
                destinations.append({
                    "id": r.id,
                    "nazwa_unikalna": r.nazwa_unikalna,
                    "is_empty": r.active_mix_id is None,
                    "material_types_text": material_types_text,
                })

        return jsonify({"destinations": destinations}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route('/dmuchanie-destinations', methods=['GET'])
def dmuchanie_destinations():
    """
    Zwraca listę możliwych celów dla operacji DMUCHANIE (zmiana celu).
    Query: id_operacji (wymagane). Źródło z operacji; cele: reaktory (w tym koło) + beczki czyste z trasą Pathfinder.
    """
    id_operacji = request.args.get('id_operacji', type=int)
    if not id_operacji:
        return jsonify({"status": "error", "message": "Brak parametru id_operacji."}), 400

    try:
        operacja = db.session.get(OperacjeLog, id_operacji)
        if not operacja or operacja.status_operacji != 'aktywna' or operacja.typ_operacji != 'DMUCHANIE':
            return jsonify({"status": "error", "message": "Nieprawidłowa lub nieaktywna operacja DMUCHANIE."}), 404
        id_zrodla = operacja.id_sprzetu_zrodlowego
        if not id_zrodla:
            return jsonify({"status": "error", "message": "Operacja nie ma źródła."}), 400

        tank_zrodlo = db.session.get(Sprzet, id_zrodla)
        if not tank_zrodlo:
            return jsonify({"status": "error", "message": "Nie znaleziono urządzenia źródłowego."}), 404
        nazwa_zrodla = tank_zrodlo.nazwa_unikalna
        start_point = f"{nazwa_zrodla}_OUT"

        all_valves = db.session.execute(db.select(Zawory.nazwa_zaworu)).scalars().all()
        open_valves_list = [v[0] if isinstance(v, (list, tuple)) else v for v in (all_valves or [])]
        pathfinder = get_pathfinder()

        destinations = []
        # Reaktory: ten sam (koło) + puste
        reaktory_q = db.select(Sprzet).where(Sprzet.typ_sprzetu == 'reaktor').order_by(Sprzet.nazwa_unikalna)
        reaktory = db.session.execute(reaktory_q).scalars().all()
        for r in reaktory:
            end_point = f"{r.nazwa_unikalna}_IN"
            if pathfinder.find_path(start_point, end_point, open_valves_list):
                destinations.append({"id": r.id, "nazwa_unikalna": r.nazwa_unikalna, "typ_sprzetu": "reaktor"})
        # Beczki czyste
        beczki_q = db.select(Sprzet).where(Sprzet.typ_sprzetu == 'beczka_czysta').order_by(Sprzet.nazwa_unikalna)
        beczki = db.session.execute(beczki_q).scalars().all()
        for b in beczki:
            end_point = f"{b.nazwa_unikalna}_IN"
            if pathfinder.find_path(start_point, end_point, open_valves_list):
                destinations.append({"id": b.id, "nazwa_unikalna": b.nazwa_unikalna, "typ_sprzetu": "beczka_czysta"})

        return jsonify({"destinations": destinations}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------------------------------------------------------------------------
# TRANSFER_TANK_TO_TANK – start
# ---------------------------------------------------------------------------
@bp.route('/start-transfer-tank-to-tank', methods=['POST'])
def start_transfer_tank_to_tank():
    """
    Tworzy nową operację TRANSFER_TANK_TO_TANK między dwoma zbiornikami.
    Wyznacza trasę PathFinder, blokuje segmenty i otwiera zawory.
    Ilość przelana jest podawana przy zakończeniu operacji (finish).

    Body: { source_tank_id, destination_tank_id, operator? }
    """
    dane = request.get_json()
    if not dane:
        return jsonify({"status": "error", "message": "Brak danych JSON."}), 400

    try:
        source_tank_id = int(dane.get("source_tank_id"))
        destination_tank_id = int(dane.get("destination_tank_id"))
        operator = dane.get("operator", "GUI")
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Nieprawidłowe dane wejściowe."}), 400

    if not source_tank_id or not destination_tank_id:
        return jsonify({"status": "error", "message": "Wymagane pola: source_tank_id, destination_tank_id."}), 400

    try:
        zrodlo = db.session.get(Sprzet, source_tank_id)
        cel = db.session.get(Sprzet, destination_tank_id)
        if not zrodlo:
            return jsonify({"status": "error", "message": f"Zbiornik źródłowy o ID {source_tank_id} nie istnieje."}), 404
        if not cel:
            return jsonify({"status": "error", "message": f"Zbiornik docelowy o ID {destination_tank_id} nie istnieje."}), 404

        start_point = f"{zrodlo.nazwa_unikalna}_OUT"
        end_point = f"{cel.nazwa_unikalna}_IN"

        pathfinder = get_pathfinder()
        all_valves = db.session.execute(db.select(Zawory.nazwa_zaworu)).scalars().all()
        open_valves_list = [v[0] if isinstance(v, (list, tuple)) else v for v in (all_valves or [])]
        znaleziona_sciezka_nazwy = pathfinder.find_path(start_point, end_point, open_valves_list)

        if not znaleziona_sciezka_nazwy:
            return jsonify({
                "status": "error",
                "message": f"Nie znaleziono trasy od {start_point} do {end_point}.",
            }), 409

        konflikt_query = (
            db.select(Segmenty.nazwa_segmentu)
            .select_from(Segmenty)
            .join(t_log_uzyte_segmenty, Segmenty.id == t_log_uzyte_segmenty.c.id_segmentu)
            .join(OperacjeLog, t_log_uzyte_segmenty.c.id_operacji_log == OperacjeLog.id)
            .where(
                OperacjeLog.status_operacji == "aktywna",
                Segmenty.nazwa_segmentu.in_(znaleziona_sciezka_nazwy),
            )
        )
        konflikty = db.session.execute(konflikt_query).all()
        if konflikty:
            return jsonify({
                "status": "error",
                "message": "Konflikt zasobów – segmenty trasy są używane przez inną aktywną operację.",
                "zajete_segmenty": [k[0] if isinstance(k, (list, tuple)) else k for k in konflikty],
            }), 409

        nowa_operacja = OperacjeLog(
            typ_operacji="TRANSFER_TANK_TO_TANK",
            status_operacji="aktywna",
            czas_rozpoczecia=dt.now(timezone.utc),
            id_sprzetu_zrodlowego=zrodlo.id,
            id_sprzetu_docelowego=cel.id,
            opis=f"TRANSFER_TANK_TO_TANK: {zrodlo.nazwa_unikalna} → {cel.nazwa_unikalna}",
            punkt_startowy=start_point,
            punkt_docelowy=end_point,
            zmodyfikowane_przez=operator,
        )
        db.session.add(nowa_operacja)
        db.session.flush()

        segmenty_trasy = db.session.execute(
            db.select(Segmenty).where(Segmenty.nazwa_segmentu.in_(znaleziona_sciezka_nazwy))
        ).scalars().all()
        nowa_operacja.segmenty = list(segmenty_trasy)

        zawory_na_trasie = set()
        for u, v, edge_data in pathfinder.graph.edges(data=True):
            if edge_data.get("segment_name") in znaleziona_sciezka_nazwy and "valve_name" in edge_data:
                zawory_na_trasie.add(edge_data["valve_name"])
        if zawory_na_trasie:
            db.session.execute(
                db.update(Zawory).where(Zawory.nazwa_zaworu.in_(zawory_na_trasie)).values(stan="OTWARTY")
            )

        db.session.commit()
        try:
            broadcast_dashboard_update()
        except Exception:
            pass
        return jsonify({
            "status": "success",
            "message": f"Operacja TRANSFER_TANK_TO_TANK rozpoczęta: {zrodlo.nazwa_unikalna} → {cel.nazwa_unikalna}.",
            "id_operacji": nowa_operacja.id,
        }), 200
    except ValueError as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@bp.route('/dmuchanie-change-destination', methods=['POST'])
def dmuchanie_change_destination():
    """
    Zmienia cel aktywnej operacji DMUCHANIE i wyznacza nową trasę do wybranego celu.
    """
    dane = request.get_json()
    if not dane or 'id_operacji' not in dane or 'id_sprzetu_docelowego' not in dane:
        return jsonify({"status": "error", "message": "Brak wymaganych pól: id_operacji, id_sprzetu_docelowego."}), 400

    id_operacji = int(dane['id_operacji'])
    id_celu = int(dane['id_sprzetu_docelowego'])
    operator = dane.get('operator', 'GUI')

    try:
        operacja = db.session.get(OperacjeLog, id_operacji)
        if not operacja or operacja.status_operacji != 'aktywna' or operacja.typ_operacji != 'DMUCHANIE':
            return jsonify({"status": "error", "message": "Nieprawidłowa lub nieaktywna operacja DMUCHANIE."}), 404
        id_zrodla = operacja.id_sprzetu_zrodlowego
        if not id_zrodla:
            return jsonify({"status": "error", "message": "Operacja nie ma źródła."}), 400

        zrodlo = db.session.get(Sprzet, id_zrodla)
        cel = db.session.get(Sprzet, id_celu)
        if not zrodlo or not cel:
            return jsonify({"status": "error", "message": "Nieprawidłowe źródło lub cel."}), 404

        # 1) Zamknij zawory starej trasy i wyczyść segmenty
        if operacja.segmenty:
            for segment in operacja.segmenty:
                if segment.zawory:
                    segment.zawory.stan = 'ZAMKNIETY'
            operacja.segmenty = []
            db.session.flush()

        # 2) Wyznacz nową trasę źródło_OUT → cel_IN
        start_point = f"{zrodlo.nazwa_unikalna}_OUT"
        end_point = f"{cel.nazwa_unikalna}_IN"
        pathfinder = get_pathfinder()
        all_valves = db.session.execute(db.select(Zawory.nazwa_zaworu)).scalars().all()
        open_valves_list = [v[0] if isinstance(v, (list, tuple)) else v for v in (all_valves or [])]
        znaleziona_sciezka_nazwy = pathfinder.find_path(start_point, end_point, open_valves_list)
        if not znaleziona_sciezka_nazwy:
            return jsonify({"status": "error", "message": f"Nie znaleziono trasy do {cel.nazwa_unikalna}."}), 400

        # 3) Sprawdź konflikt z INNYMI operacjami (ta jest już bez segmentów)
        konflikt_query = (
            db.select(Segmenty.nazwa_segmentu)
            .select_from(Segmenty)
            .join(t_log_uzyte_segmenty, Segmenty.id == t_log_uzyte_segmenty.c.id_segmentu)
            .join(OperacjeLog, t_log_uzyte_segmenty.c.id_operacji_log == OperacjeLog.id)
            .where(
                OperacjeLog.status_operacji == 'aktywna',
                OperacjeLog.id != id_operacji,
                Segmenty.nazwa_segmentu.in_(znaleziona_sciezka_nazwy),
            )
        )
        konflikty = db.session.execute(konflikt_query).scalars().all()
        if konflikty:
            return jsonify({
                "status": "error",
                "message": "Konflikt zasobów – segmenty trasy są używane przez inną operację.",
                "zajete_segmenty": [k[0] if isinstance(k, (list, tuple)) else k for k in konflikty]
            }), 409

        # 4) Zapisz nowy cel, trasę i segmenty
        operacja.id_sprzetu_docelowego = id_celu
        operacja.punkt_docelowy = end_point
        operacja.opis = f"DMUCHANIE: {zrodlo.nazwa_unikalna} → {cel.nazwa_unikalna}"
        operacja.zmodyfikowane_przez = operator
        operacja.ostatnia_modyfikacja = dt.now(timezone.utc)

        segmenty_trasy = db.session.execute(
            db.select(Segmenty).where(Segmenty.nazwa_segmentu.in_(znaleziona_sciezka_nazwy))
        ).scalars().all()
        operacja.segmenty = list(segmenty_trasy)

        # 5) Otwórz zawory na nowej trasie DMUCHANIE
        zawory_na_trasie = set()
        for u, v, edge_data in pathfinder.graph.edges(data=True):
            if edge_data.get('segment_name') in znaleziona_sciezka_nazwy and 'valve_name' in edge_data:
                zawory_na_trasie.add(edge_data['valve_name'])
        if zawory_na_trasie:
            db.session.execute(
                db.update(Zawory).where(Zawory.nazwa_zaworu.in_(zawory_na_trasie)).values(stan='OTWARTY')
            )

        db.session.commit()
        try:
            broadcast_dashboard_update()
        except Exception:
            pass
        return jsonify({
            "status": "success",
            "message": f"Cel operacji DMUCHANIE ustawiony na {cel.nazwa_unikalna}.",
        }), 200
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------------------------------------------------------------------------
# FILTRACJA_NA_PLACKU – destinations (reaktory do wyboru jako cel)
# ---------------------------------------------------------------------------
@bp.route('/filtracja-na-placku-destinations', methods=['GET'])
def filtracja_na_placku_destinations():
    """
    Zwraca listę reaktorów możliwych jako cel FILTRACJA_NA_PLACKU:
    - puste (brak aktywnego mixa), różne od źródła,
    - z fizycznie możliwą trasą: źródło → filtr → cel (jak przelew-destinations).
    Query: id_sprzetu_zrodlowego (wymagane).
    """
    id_zrodla = request.args.get('id_sprzetu_zrodlowego', type=int)
    if not id_zrodla:
        return jsonify({"status": "error", "message": "Brak parametru id_sprzetu_zrodlowego."}), 400

    try:
        tank_zrodlo = db.session.get(Sprzet, id_zrodla)
        if not tank_zrodlo:
            return jsonify({"status": "error", "message": f"Sprzęt o ID {id_zrodla} nie istnieje."}), 404

        nazwa_zrodla = tank_zrodlo.nazwa_unikalna
        start_point = f"{nazwa_zrodla}_OUT"

        all_valves = db.session.execute(db.select(Zawory.nazwa_zaworu)).scalars().all()
        open_valves_list = [v[0] if isinstance(v, (list, tuple)) else v for v in (all_valves or [])]
        pathfinder = get_pathfinder()

        filtry = db.session.execute(
            db.select(Sprzet.nazwa_unikalna).where(Sprzet.typ_sprzetu == 'filtr').order_by(Sprzet.nazwa_unikalna)
        ).scalars().all()
        if not filtry:
            return jsonify({"destinations": [], "message": "Brak filtra w systemie."}), 200

        # Tylko reaktory puste (bez aktywnego mixa), inne niż źródło – jak przelew-destinations
        reaktory_puste = db.session.execute(
            db.select(Sprzet)
            .where(
                Sprzet.typ_sprzetu == 'reaktor',
                Sprzet.id != id_zrodla,
                Sprzet.active_mix_id.is_(None)
            )
            .order_by(Sprzet.nazwa_unikalna)
        ).scalars().all()

        destinations = []
        for r in reaktory_puste:
            end_point = f"{r.nazwa_unikalna}_IN"
            trasa_ok = False
            for nazwa_filtra in filtry:
                filtr_in = f"{nazwa_filtra}_IN"
                filtr_out = f"{nazwa_filtra}_OUT"
                s1 = pathfinder.find_path(start_point, filtr_in, open_valves_list)
                if not s1:
                    continue
                sw = pathfinder.find_path(filtr_in, filtr_out, open_valves_list)
                if not sw:
                    continue
                s2 = pathfinder.find_path(filtr_out, end_point, open_valves_list)
                if s2:
                    trasa_ok = True
                    break
            if trasa_ok:
                destinations.append({"id": r.id, "nazwa_unikalna": r.nazwa_unikalna})

        return jsonify({"destinations": destinations}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------------------------------------------------------------------------
# FILTRACJA_NA_PLACKU – start operacji
# ---------------------------------------------------------------------------
@bp.route('/start-filtracja-na-placku', methods=['POST'])
def start_filtracja_na_placku():
    """
    Rozpoczyna operację FILTRACJA_NA_PLACKU dla mieszaniny w reaktorze źródłowym.
    Dozwolone z każdego process_status OPRÓCZ 'DOBIELONY_OCZEKUJE'.
    Trasa: źródło_OUT → filtr_IN → filtr_OUT → cel_IN (jak FILTRACJA_PRZELEW).
    Body: { id_sprzetu_zrodlowego, id_sprzetu_docelowego, operator? }
    """
    dane = request.get_json()
    if not dane or 'id_sprzetu_zrodlowego' not in dane or 'id_sprzetu_docelowego' not in dane:
        return jsonify({"status": "error", "message": "Wymagane pola: id_sprzetu_zrodlowego, id_sprzetu_docelowego."}), 400

    id_zrodla = int(dane['id_sprzetu_zrodlowego'])
    id_celu = int(dane['id_sprzetu_docelowego'])
    operator = dane.get('operator', 'GUI')

    if id_zrodla == id_celu:
        return jsonify({"status": "error", "message": "Reaktor docelowy musi być inny niż źródłowy."}), 400

    try:
        reaktor_zrodlo = db.session.get(Sprzet, id_zrodla)
        reaktor_cel = db.session.get(Sprzet, id_celu)
        if not reaktor_zrodlo:
            return jsonify({"status": "error", "message": f"Sprzęt źródłowy o ID {id_zrodla} nie istnieje."}), 404
        if not reaktor_cel or reaktor_cel.typ_sprzetu != 'reaktor':
            return jsonify({"status": "error", "message": "Sprzęt docelowy musi być reaktorem."}), 400

        if not reaktor_zrodlo.active_mix_id:
            return jsonify({"status": "error", "message": "Reaktor źródłowy nie zawiera aktywnej mieszaniny."}), 409

        mix = db.session.get(TankMixes, reaktor_zrodlo.active_mix_id)
        if not mix:
            return jsonify({"status": "error", "message": "Nie znaleziono mieszaniny w reaktorze źródłowym."}), 404
        if mix.process_status == 'DOBIELONY_OCZEKUJE':
            return jsonify({
                "status": "error",
                "message": "FILTRACJA_NA_PLACKU niedozwolona dla mieszaniny w stanie DOBIELONY_OCZEKUJE."
            }), 409

        start_point = f"{reaktor_zrodlo.nazwa_unikalna}_OUT"
        end_point = f"{reaktor_cel.nazwa_unikalna}_IN"

        all_valves = db.session.execute(db.select(Zawory.nazwa_zaworu)).scalars().all()
        open_valves_list = [v[0] if isinstance(v, (list, tuple)) else v for v in (all_valves or [])]
        pathfinder = get_pathfinder()

        filtry = db.session.execute(
            db.select(Sprzet.nazwa_unikalna).where(Sprzet.typ_sprzetu == 'filtr').order_by(Sprzet.nazwa_unikalna)
        ).scalars().all()
        if not filtry:
            return jsonify({"status": "error", "message": "Brak filtra w systemie."}), 400

        sprzet_posredni = None
        sciezka_1 = sciezka_wewn = sciezka_2 = []
        for nazwa_filtra in filtry:
            posredni_in = f"{nazwa_filtra}_IN"
            posredni_out = f"{nazwa_filtra}_OUT"
            s1 = pathfinder.find_path(start_point, posredni_in, open_valves_list)
            if not s1:
                continue
            sw = pathfinder.find_path(posredni_in, posredni_out, open_valves_list)
            if not sw:
                continue
            s2 = pathfinder.find_path(posredni_out, end_point, open_valves_list)
            if s2:
                sprzet_posredni = nazwa_filtra
                sciezka_1, sciezka_wewn, sciezka_2 = s1, sw, s2
                break

        if not sprzet_posredni:
            return jsonify({
                "status": "error",
                "message": f"Żaden filtr nie ma połączenia ze ścieżką {start_point} → cel ({end_point})."
            }), 404

        znaleziona_sciezka_nazwy = sciezka_1 + sciezka_wewn + sciezka_2

        # Sprawdź konflikty z innymi aktywnymi operacjami
        konflikt_query = (
            db.select(Segmenty.nazwa_segmentu)
            .select_from(Segmenty)
            .join(t_log_uzyte_segmenty, Segmenty.id == t_log_uzyte_segmenty.c.id_segmentu)
            .join(OperacjeLog, t_log_uzyte_segmenty.c.id_operacji_log == OperacjeLog.id)
            .where(
                OperacjeLog.status_operacji == 'aktywna',
                Segmenty.nazwa_segmentu.in_(znaleziona_sciezka_nazwy),
            )
        )
        konflikty = db.session.execute(konflikt_query).all()
        if konflikty:
            return jsonify({
                "status": "error",
                "message": "Konflikt zasobów – segmenty trasy są używane przez inną aktywną operację.",
                "zajete_segmenty": [k[0] if isinstance(k, (list, tuple)) else k for k in konflikty],
            }), 409

        # Otwórz zawory na trasie
        zawory_na_trasie = set()
        for u, v, edge_data in pathfinder.graph.edges(data=True):
            if edge_data.get('segment_name') in znaleziona_sciezka_nazwy:
                zawory_na_trasie.add(edge_data.get('valve_name', ''))
        zawory_na_trasie.discard('')
        if zawory_na_trasie:
            db.session.execute(
                db.update(Zawory).where(Zawory.nazwa_zaworu.in_(zawory_na_trasie)).values(stan='OTWARTY')
            )

        mix.process_status = 'FILTRACJA_NA_PLACKU'

        nowa_operacja = OperacjeLog(
            typ_operacji='FILTRACJA_NA_PLACKU',
            id_tank_mix=mix.id,
            status_operacji='aktywna',
            czas_rozpoczecia=dt.now(timezone.utc),
            id_sprzetu_zrodlowego=reaktor_zrodlo.id,
            id_sprzetu_docelowego=reaktor_cel.id,
            opis=f"FILTRACJA_NA_PLACKU: {reaktor_zrodlo.nazwa_unikalna} → {sprzet_posredni} → {reaktor_cel.nazwa_unikalna}",
            punkt_startowy=start_point,
            punkt_docelowy=end_point,
            zmodyfikowane_przez=operator,
        )
        db.session.add(nowa_operacja)
        db.session.flush()

        segmenty_trasy = db.session.execute(
            db.select(Segmenty).where(Segmenty.nazwa_segmentu.in_(znaleziona_sciezka_nazwy))
        ).scalars().all()
        nowa_operacja.segmenty = list(segmenty_trasy)

        db.session.commit()
        try:
            broadcast_dashboard_update()
        except Exception:
            pass
        return jsonify({
            "status": "success",
            "message": f"Rozpoczęto FILTRACJA_NA_PLACKU: {reaktor_zrodlo.nazwa_unikalna} → {sprzet_posredni} → {reaktor_cel.nazwa_unikalna}.",
            "id_operacji": nowa_operacja.id,
            "filtr": sprzet_posredni,
        }), 200
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------------------------------------------------------------------------
# DMUCHANIE → DMUCHANIE_CZYSZCZENIE – konwersja aktywnej operacji
# ---------------------------------------------------------------------------
@bp.route('/convert-dmuchanie-to-czyszczenie', methods=['POST'])
def convert_dmuchanie_to_czyszczenie():
    """
    Konwertuje aktywną operację DMUCHANIE na DMUCHANIE_CZYSZCZENIE.
    Zamyka istniejącą operację DMUCHANIE (zawory, segmenty), wyznacza nową
    trasę do wskazanego reaktora docelowego i tworzy operację DMUCHANIE_CZYSZCZENIE.
    Body: { id_operacji, id_sprzetu_docelowego, operator? }
    """
    dane = request.get_json()
    if not dane or 'id_operacji' not in dane or 'id_sprzetu_docelowego' not in dane:
        return jsonify({"status": "error", "message": "Wymagane pola: id_operacji, id_sprzetu_docelowego."}), 400

    id_operacji = int(dane['id_operacji'])
    id_celu = int(dane['id_sprzetu_docelowego'])
    operator = dane.get('operator', 'GUI')

    try:
        operacja = db.session.execute(
            db.select(OperacjeLog).options(joinedload(OperacjeLog.segmenty)).where(OperacjeLog.id == id_operacji)
        ).unique().scalar_one_or_none()

        if not operacja:
            return jsonify({"status": "error", "message": f"Operacja o ID {id_operacji} nie istnieje."}), 404
        if operacja.status_operacji != 'aktywna':
            return jsonify({"status": "error", "message": "Operacja nie jest aktywna."}), 409
        if operacja.typ_operacji != 'DMUCHANIE':
            return jsonify({"status": "error",
                            "message": f"Konwersja możliwa tylko dla operacji DMUCHANIE (obecny: {operacja.typ_operacji})."}), 409

        cel = db.session.get(Sprzet, id_celu)
        if not cel:
            return jsonify({"status": "error", "message": f"Sprzęt docelowy o ID {id_celu} nie istnieje."}), 404
        if cel.typ_sprzetu != 'reaktor':
            return jsonify({"status": "error", "message": "Cel dla DMUCHANIE_CZYSZCZENIE musi być reaktorem."}), 400

        zrodlo = db.session.get(Sprzet, operacja.id_sprzetu_zrodlowego) if operacja.id_sprzetu_zrodlowego else None
        if not zrodlo:
            return jsonify({"status": "error", "message": "Operacja nie ma przypisanego sprzętu źródłowego."}), 409

        # Zamknij zawory i zwolnij segmenty aktywnego DMUCHANIE
        if operacja.segmenty:
            for segment in operacja.segmenty:
                if segment.zawory:
                    segment.zawory.stan = 'ZAMKNIETY'
            operacja.segmenty = []
        operacja.status_operacji = 'zakonczona'
        operacja.czas_zakonczenia = dt.now(timezone.utc)
        db.session.flush()

        # Wyznacz nową trasę: źródło_OUT → cel_IN
        start_point = f"{zrodlo.nazwa_unikalna}_OUT"
        end_point = f"{cel.nazwa_unikalna}_IN"
        pathfinder = get_pathfinder()
        all_valves = db.session.execute(db.select(Zawory.nazwa_zaworu)).scalars().all()
        open_valves_list = [v[0] if isinstance(v, (list, tuple)) else v for v in (all_valves or [])]
        znaleziona_sciezka_nazwy = pathfinder.find_path(start_point, end_point, open_valves_list)

        if not znaleziona_sciezka_nazwy:
            return jsonify({"status": "error", "message": f"Nie znaleziono trasy od {start_point} do {end_point}."}), 409

        # Sprawdź konflikty z innymi aktywnymi operacjami
        konflikt_query = (
            db.select(Segmenty.nazwa_segmentu)
            .select_from(Segmenty)
            .join(t_log_uzyte_segmenty, Segmenty.id == t_log_uzyte_segmenty.c.id_segmentu)
            .join(OperacjeLog, t_log_uzyte_segmenty.c.id_operacji_log == OperacjeLog.id)
            .where(
                OperacjeLog.status_operacji == 'aktywna',
                Segmenty.nazwa_segmentu.in_(znaleziona_sciezka_nazwy),
            )
        )
        konflikty = db.session.execute(konflikt_query).all()
        if konflikty:
            return jsonify({
                "status": "error",
                "message": "Konflikt zasobów – segmenty nowej trasy są używane przez inną aktywną operację.",
                "zajete_segmenty": [k[0] if isinstance(k, (list, tuple)) else k for k in konflikty],
            }), 409

        # ID mixa źródłowego do oznaczenia przy finish
        id_mix_zrodla = zrodlo.active_mix_id if zrodlo.active_mix_id else operacja.id_tank_mix

        nowa_operacja = OperacjeLog(
            typ_operacji='DMUCHANIE_CZYSZCZENIE',
            status_operacji='aktywna',
            czas_rozpoczecia=dt.now(timezone.utc),
            id_sprzetu_zrodlowego=zrodlo.id,
            id_sprzetu_docelowego=cel.id,
            id_tank_mix=id_mix_zrodla,
            opis=f"DMUCHANIE_CZYSZCZENIE: {zrodlo.nazwa_unikalna} → {cel.nazwa_unikalna}",
            punkt_startowy=start_point,
            punkt_docelowy=end_point,
            zmodyfikowane_przez=operator,
        )
        db.session.add(nowa_operacja)
        db.session.flush()

        segmenty_trasy = db.session.execute(
            db.select(Segmenty).where(Segmenty.nazwa_segmentu.in_(znaleziona_sciezka_nazwy))
        ).scalars().all()
        nowa_operacja.segmenty = list(segmenty_trasy)

        zawory_na_trasie = set()
        for u, v, edge_data in pathfinder.graph.edges(data=True):
            if edge_data.get('segment_name') in znaleziona_sciezka_nazwy and 'valve_name' in edge_data:
                zawory_na_trasie.add(edge_data['valve_name'])
        if zawory_na_trasie:
            db.session.execute(
                db.update(Zawory).where(Zawory.nazwa_zaworu.in_(zawory_na_trasie)).values(stan='OTWARTY')
            )

        db.session.commit()
        try:
            broadcast_dashboard_update()
        except Exception:
            pass
        return jsonify({
            "status": "success",
            "message": f"DMUCHANIE przekształcone w DMUCHANIE_CZYSZCZENIE: {zrodlo.nazwa_unikalna} → {cel.nazwa_unikalna}.",
            "id_operacji_czyszczenie": nowa_operacja.id,
        }), 200
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------------------------------------------------------------------------
# DMUCHANIE_CZYSZCZENIE – start
# ---------------------------------------------------------------------------
@bp.route('/start-dmuchanie-czyszczenie', methods=['POST'])
def start_dmuchanie_czyszczenie():
    """
    Tworzy nową operację DMUCHANIE_CZYSZCZENIE.
    Wyznacza trasę PathFinder, blokuje segmenty i otwiera zawory.
    Zapisuje ID aktywnego mixa źródła w id_tank_mix, aby finish mógł
    zidentyfikować partię do W-P-... nawet gdy źródło zostanie opróżnione.
    Body: { id_sprzetu_zrodlowego, id_sprzetu_docelowego, operator? }
    """
    dane = request.get_json()
    if not dane:
        return jsonify({"status": "error", "message": "Brak danych JSON."}), 400

    id_zrodla = dane.get('id_sprzetu_zrodlowego')
    id_celu = dane.get('id_sprzetu_docelowego')
    operator = dane.get('operator', 'GUI')

    if not id_zrodla or not id_celu:
        return jsonify({"status": "error", "message": "Wymagane pola: id_sprzetu_zrodlowego, id_sprzetu_docelowego."}), 400

    try:
        zrodlo = db.session.get(Sprzet, int(id_zrodla))
        cel = db.session.get(Sprzet, int(id_celu))
        if not zrodlo:
            return jsonify({"status": "error", "message": f"Sprzęt źródłowy o ID {id_zrodla} nie istnieje."}), 404
        if not cel:
            return jsonify({"status": "error", "message": f"Sprzęt docelowy o ID {id_celu} nie istnieje."}), 404

        start_point = f"{zrodlo.nazwa_unikalna}_OUT"
        end_point = f"{cel.nazwa_unikalna}_IN"

        pathfinder = get_pathfinder()
        all_valves = db.session.execute(db.select(Zawory.nazwa_zaworu)).scalars().all()
        open_valves_list = [v[0] if isinstance(v, (list, tuple)) else v for v in (all_valves or [])]
        znaleziona_sciezka_nazwy = pathfinder.find_path(start_point, end_point, open_valves_list)

        if not znaleziona_sciezka_nazwy:
            return jsonify({"status": "error", "message": f"Nie znaleziono trasy od {start_point} do {end_point}."}), 409

        konflikt_query = (
            db.select(Segmenty.nazwa_segmentu)
            .select_from(Segmenty)
            .join(t_log_uzyte_segmenty, Segmenty.id == t_log_uzyte_segmenty.c.id_segmentu)
            .join(OperacjeLog, t_log_uzyte_segmenty.c.id_operacji_log == OperacjeLog.id)
            .where(
                OperacjeLog.status_operacji == 'aktywna',
                Segmenty.nazwa_segmentu.in_(znaleziona_sciezka_nazwy),
            )
        )
        konflikty = db.session.execute(konflikt_query).all()
        if konflikty:
            return jsonify({
                "status": "error",
                "message": "Konflikt zasobów – segmenty trasy są używane przez inną aktywną operację.",
                "zajete_segmenty": [k[0] if isinstance(k, (list, tuple)) else k for k in konflikty],
            }), 409

        # Zapisz ID źródłowego mixa dla późniejszego użycia w finish
        id_mix_zrodla = zrodlo.active_mix_id if zrodlo.active_mix_id else None

        nowa_operacja = OperacjeLog(
            typ_operacji='DMUCHANIE_CZYSZCZENIE',
            status_operacji='aktywna',
            czas_rozpoczecia=dt.now(timezone.utc),
            id_sprzetu_zrodlowego=zrodlo.id,
            id_sprzetu_docelowego=cel.id,
            id_tank_mix=id_mix_zrodla,
            opis=f"DMUCHANIE_CZYSZCZENIE: {zrodlo.nazwa_unikalna} → {cel.nazwa_unikalna}",
            punkt_startowy=start_point,
            punkt_docelowy=end_point,
            zmodyfikowane_przez=operator,
        )
        db.session.add(nowa_operacja)
        db.session.flush()

        segmenty_trasy = db.session.execute(
            db.select(Segmenty).where(Segmenty.nazwa_segmentu.in_(znaleziona_sciezka_nazwy))
        ).scalars().all()
        nowa_operacja.segmenty = list(segmenty_trasy)

        zawory_na_trasie = set()
        for u, v, edge_data in pathfinder.graph.edges(data=True):
            if edge_data.get('segment_name') in znaleziona_sciezka_nazwy and 'valve_name' in edge_data:
                zawory_na_trasie.add(edge_data['valve_name'])
        if zawory_na_trasie:
            db.session.execute(
                db.update(Zawory).where(Zawory.nazwa_zaworu.in_(zawory_na_trasie)).values(stan='OTWARTY')
            )

        db.session.commit()
        try:
            broadcast_dashboard_update()
        except Exception:
            pass
        return jsonify({
            "status": "success",
            "message": f"Operacja DMUCHANIE_CZYSZCZENIE rozpoczęta: {zrodlo.nazwa_unikalna} → {cel.nazwa_unikalna}.",
            "id_operacji": nowa_operacja.id,
        }), 200
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------------------------------------------------------------------------
# DMUCHANIE_CZYSZCZENIE – finish
# ---------------------------------------------------------------------------
@bp.route('/finish-dmuchanie-czyszczenie', methods=['POST'])
def finish_dmuchanie_czyszczenie():
    """
    Kończy operację DMUCHANIE_CZYSZCZENIE:
    1. Tworzy partię pierwotną W-P-<source_batch_code> (500 kg).
    2. Stosuje ją do mixa w sprzęcie docelowym (lub tworzy nowy mix W-...).
    3. Ustawia is_wydmuch_mix=True na mixie docelowym.
    4. Zamyka zawory, zwalnia segmenty, kończy operację.
    Body: { id_operacji, operator? }
    """
    dane = request.get_json()
    if not dane or 'id_operacji' not in dane:
        return jsonify({"status": "error", "message": "Brak wymaganego pola: id_operacji."}), 400

    id_operacji = int(dane['id_operacji'])
    operator = dane.get('operator', 'GUI')

    try:
        operacja = db.session.execute(
            db.select(OperacjeLog)
            .options(joinedload(OperacjeLog.segmenty))
            .where(OperacjeLog.id == id_operacji)
        ).unique().scalar_one_or_none()

        if not operacja:
            return jsonify({"status": "error", "message": f"Operacja o ID {id_operacji} nie istnieje."}), 404
        if operacja.status_operacji != 'aktywna':
            return jsonify({"status": "error", "message": "Operacja nie jest aktywna."}), 409
        if operacja.typ_operacji != 'DMUCHANIE_CZYSZCZENIE':
            return jsonify({"status": "error", "message": f"Operacja nie jest typu DMUCHANIE_CZYSZCZENIE (obecny: {operacja.typ_operacji})."}), 409

        # Znajdź partię źródłową do nazwania W-P-...
        source_mix = None
        if operacja.id_tank_mix:
            source_mix = db.session.get(TankMixes, operacja.id_tank_mix)
        if not source_mix and operacja.id_sprzetu_zrodlowego:
            zrodlo_sprzet = db.session.get(Sprzet, operacja.id_sprzetu_zrodlowego)
            if zrodlo_sprzet and zrodlo_sprzet.active_mix_id:
                source_mix = db.session.get(TankMixes, zrodlo_sprzet.active_mix_id)

        if source_mix and source_mix.components:
            primary_component = max(
                (c for c in source_mix.components if (c.quantity_in_mix or 0) > 0),
                key=lambda c: c.quantity_in_mix or 0,
                default=None,
            )
            source_batch = db.session.get(Batches, primary_component.batch_id) if primary_component else None
            if source_batch:
                source_batch_code = source_batch.unique_code
                material_type = source_batch.material_type
            else:
                source_batch_code = f"OP{operacja.id}"
                material_type = 'WYDMUCH'
            source_mix_code = source_mix.unique_code
        else:
            source_batch_code = f"OP{operacja.id}"
            material_type = 'WYDMUCH'
            source_mix_code = f"OP{operacja.id}"

        # Utwórz partię W-P-...
        wydmuch_batch_result = BatchManagementService.create_wydmuch_batch(
            source_batch_code=source_batch_code,
            material_type=material_type,
        )
        wydmuch_batch_id = wydmuch_batch_result['batch_id']

        # Zastosuj do mixa w sprzęcie docelowym
        mix_result = BatchManagementService.apply_wydmuch_to_tank(
            dest_tank_id=operacja.id_sprzetu_docelowego,
            wydmuch_batch_id=wydmuch_batch_id,
            source_mix_unique_code=source_mix_code,
        )

        # Zamknij zawory i zwolnij segmenty
        if operacja.segmenty:
            for segment in operacja.segmenty:
                if segment.zawory:
                    segment.zawory.stan = 'ZAMKNIETY'
            operacja.segmenty = []

        operacja.status_operacji = 'zakonczona'
        operacja.czas_zakonczenia = dt.now(timezone.utc)
        operacja.zmodyfikowane_przez = operator

        db.session.commit()
        try:
            broadcast_dashboard_update()
        except Exception:
            pass
        return jsonify({
            "status": "success",
            "message": "Operacja DMUCHANIE_CZYSZCZENIE zakończona. Mix docelowy oznaczony jako wydmuch.",
            "wydmuch_batch_code": wydmuch_batch_result['unique_code'],
            "mix_id": mix_result['mix_id'],
            "created_new_mix": mix_result['created_new_mix'],
        }), 200
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------------------------------------------------------------------------
# DMUCHANIE_RUROCIAGU – start
# ---------------------------------------------------------------------------
@bp.route('/start-dmuchanie-rurociagu', methods=['POST'])
def start_dmuchanie_rurociagu():
    """
    Tworzy nową operację DMUCHANIE_RUROCIAGU dla dowolnej trasy w instalacji.
    Blokuje segmenty trasy i otwiera zawory. Bez wpływu na mixy/partie.
    Body: { id_sprzetu_zrodlowego, id_sprzetu_docelowego, operator? }
    """
    dane = request.get_json()
    if not dane:
        return jsonify({"status": "error", "message": "Brak danych JSON."}), 400

    id_zrodla = dane.get('id_sprzetu_zrodlowego')
    id_celu = dane.get('id_sprzetu_docelowego')
    operator = dane.get('operator', 'GUI')

    if not id_zrodla or not id_celu:
        return jsonify({"status": "error", "message": "Wymagane pola: id_sprzetu_zrodlowego, id_sprzetu_docelowego."}), 400

    try:
        zrodlo = db.session.get(Sprzet, int(id_zrodla))
        cel = db.session.get(Sprzet, int(id_celu))
        if not zrodlo:
            return jsonify({"status": "error", "message": f"Sprzęt źródłowy o ID {id_zrodla} nie istnieje."}), 404
        if not cel:
            return jsonify({"status": "error", "message": f"Sprzęt docelowy o ID {id_celu} nie istnieje."}), 404

        start_point = f"{zrodlo.nazwa_unikalna}_OUT"
        end_point = f"{cel.nazwa_unikalna}_IN"

        pathfinder = get_pathfinder()
        all_valves = db.session.execute(db.select(Zawory.nazwa_zaworu)).scalars().all()
        open_valves_list = [v[0] if isinstance(v, (list, tuple)) else v for v in (all_valves or [])]
        znaleziona_sciezka_nazwy = pathfinder.find_path(start_point, end_point, open_valves_list)

        if not znaleziona_sciezka_nazwy:
            return jsonify({"status": "error", "message": f"Nie znaleziono trasy od {start_point} do {end_point}."}), 409

        konflikt_query = (
            db.select(Segmenty.nazwa_segmentu)
            .select_from(Segmenty)
            .join(t_log_uzyte_segmenty, Segmenty.id == t_log_uzyte_segmenty.c.id_segmentu)
            .join(OperacjeLog, t_log_uzyte_segmenty.c.id_operacji_log == OperacjeLog.id)
            .where(
                OperacjeLog.status_operacji == 'aktywna',
                Segmenty.nazwa_segmentu.in_(znaleziona_sciezka_nazwy),
            )
        )
        konflikty = db.session.execute(konflikt_query).all()
        if konflikty:
            return jsonify({
                "status": "error",
                "message": "Konflikt zasobów – segmenty trasy są używane przez inną aktywną operację.",
                "zajete_segmenty": [k[0] if isinstance(k, (list, tuple)) else k for k in konflikty],
            }), 409

        nowa_operacja = OperacjeLog(
            typ_operacji='DMUCHANIE_RUROCIAGU',
            status_operacji='aktywna',
            czas_rozpoczecia=dt.now(timezone.utc),
            id_sprzetu_zrodlowego=zrodlo.id,
            id_sprzetu_docelowego=cel.id,
            opis=f"DMUCHANIE_RUROCIAGU: {zrodlo.nazwa_unikalna} → {cel.nazwa_unikalna}",
            punkt_startowy=start_point,
            punkt_docelowy=end_point,
            zmodyfikowane_przez=operator,
        )
        db.session.add(nowa_operacja)
        db.session.flush()

        segmenty_trasy = db.session.execute(
            db.select(Segmenty).where(Segmenty.nazwa_segmentu.in_(znaleziona_sciezka_nazwy))
        ).scalars().all()
        nowa_operacja.segmenty = list(segmenty_trasy)

        zawory_na_trasie = set()
        for u, v, edge_data in pathfinder.graph.edges(data=True):
            if edge_data.get('segment_name') in znaleziona_sciezka_nazwy and 'valve_name' in edge_data:
                zawory_na_trasie.add(edge_data['valve_name'])
        if zawory_na_trasie:
            db.session.execute(
                db.update(Zawory).where(Zawory.nazwa_zaworu.in_(zawory_na_trasie)).values(stan='OTWARTY')
            )

        db.session.commit()
        try:
            broadcast_dashboard_update()
        except Exception:
            pass
        return jsonify({
            "status": "success",
            "message": f"Operacja DMUCHANIE_RUROCIAGU rozpoczęta: {zrodlo.nazwa_unikalna} → {cel.nazwa_unikalna}.",
            "id_operacji": nowa_operacja.id,
        }), 200
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------------------------------------------------------------------------
# DMUCHANIE_RUROCIAGU – finish
# ---------------------------------------------------------------------------
@bp.route('/finish-dmuchanie-rurociagu', methods=['POST'])
def finish_dmuchanie_rurociagu():
    """
    Kończy operację DMUCHANIE_RUROCIAGU.
    Zamyka zawory, zwalnia segmenty trasy. Bez wpływu na mixy/partie.
    Body: { id_operacji, operator? }
    """
    dane = request.get_json()
    if not dane or 'id_operacji' not in dane:
        return jsonify({"status": "error", "message": "Brak wymaganego pola: id_operacji."}), 400

    id_operacji = int(dane['id_operacji'])
    operator = dane.get('operator', 'GUI')

    try:
        operacja = db.session.execute(
            db.select(OperacjeLog)
            .options(joinedload(OperacjeLog.segmenty))
            .where(OperacjeLog.id == id_operacji)
        ).unique().scalar_one_or_none()

        if not operacja:
            return jsonify({"status": "error", "message": f"Operacja o ID {id_operacji} nie istnieje."}), 404
        if operacja.status_operacji != 'aktywna':
            return jsonify({"status": "error", "message": "Operacja nie jest aktywna."}), 409
        if operacja.typ_operacji != 'DMUCHANIE_RUROCIAGU':
            return jsonify({"status": "error", "message": f"Operacja nie jest typu DMUCHANIE_RUROCIAGU (obecny: {operacja.typ_operacji})."}), 409

        if operacja.segmenty:
            for segment in operacja.segmenty:
                if segment.zawory:
                    segment.zawory.stan = 'ZAMKNIETY'
            operacja.segmenty = []

        operacja.status_operacji = 'zakonczona'
        operacja.czas_zakonczenia = dt.now(timezone.utc)
        operacja.zmodyfikowane_przez = operator

        db.session.commit()
        try:
            broadcast_dashboard_update()
        except Exception:
            pass
        return jsonify({
            "status": "success",
            "message": "Operacja DMUCHANIE_RUROCIAGU zakończona. Trasa zwolniona.",
        }), 200
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------------------------------------------------------------------------
# TRANSFER_TANK_TO_TANK – finish
# ---------------------------------------------------------------------------
@bp.route('/finish-transfer-tank-to-tank', methods=['POST'])
def finish_transfer_tank_to_tank():
    """
    Kończy operację TRANSFER_TANK_TO_TANK.
    Wykonuje transfer mieszaniny o podanej ilości (quantity_kg), następnie
    zamyka zawory i zwalnia segmenty trasy.

    Body: { id_operacji, quantity_kg, operator? }
    """
    dane = request.get_json()
    if not dane or "id_operacji" not in dane:
        return jsonify({"status": "error", "message": "Brak wymaganego pola: id_operacji."}), 400
    if "quantity_kg" not in dane:
        return jsonify({"status": "error", "message": "Brak wymaganego pola: quantity_kg (ilość przelana w kg)."}), 400

    try:
        id_operacji = int(dane["id_operacji"])
        quantity_kg = Decimal(str(dane["quantity_kg"]))
        operator = dane.get("operator", "GUI")
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Nieprawidłowa wartość id_operacji lub quantity_kg."}), 400

    if quantity_kg <= 0:
        return jsonify({"status": "error", "message": "Ilość przelana (quantity_kg) musi być większa od zera."}), 400

    try:
        operacja = db.session.execute(
            db.select(OperacjeLog)
            .options(joinedload(OperacjeLog.segmenty))
            .where(OperacjeLog.id == id_operacji)
        ).unique().scalar_one_or_none()

        if not operacja:
            return jsonify({"status": "error", "message": f"Operacja o ID {id_operacji} nie istnieje."}), 404
        if operacja.status_operacji != "aktywna":
            return jsonify({"status": "error", "message": "Operacja nie jest aktywna."}), 409
        if operacja.typ_operacji != "TRANSFER_TANK_TO_TANK":
            return jsonify({
                "status": "error",
                "message": f"Operacja nie jest typu TRANSFER_TANK_TO_TANK (obecny: {operacja.typ_operacji}).",
            }), 409

        # Najpierw: jeśli mix docelowy już ma tylko WYDMUCH, ustaw jego kod wg konwencji PRZELEJ (przed dodaniem payloadu)
        normalize_result = None
        dest_tank = db.session.get(Sprzet, operacja.id_sprzetu_docelowego)
        if dest_tank and dest_tank.active_mix_id:
            normalize_result = BatchManagementService.normalize_mix_code_if_only_wydmuch(
                dest_tank.active_mix_id, commit=True
            )

        # Potem: wykonaj transfer mieszaniny (dodanie payloadu do celu)
        BatchManagementService.transfer_between_dirty_tanks(
            source_tank_id=operacja.id_sprzetu_zrodlowego,
            destination_tank_id=operacja.id_sprzetu_docelowego,
            quantity_to_transfer=quantity_kg,
            operator=operator,
        )

        if operacja.segmenty:
            for segment in operacja.segmenty:
                if segment.zawory:
                    segment.zawory.stan = "ZAMKNIETY"
            operacja.segmenty = []

        operacja.status_operacji = "zakonczona"
        operacja.czas_zakonczenia = dt.now(timezone.utc)
        operacja.zmodyfikowane_przez = operator

        db.session.commit()
        try:
            broadcast_dashboard_update()
        except Exception:
            pass
        payload = {"status": "success", "message": "Operacja TRANSFER_TANK_TO_TANK zakończona. Trasa zwolniona."}
        if normalize_result:
            payload["normalize_mix_code"] = normalize_result
        return jsonify(payload), 200
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500