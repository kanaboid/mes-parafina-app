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

from .extensions import db
from .models import * #Sprzet, PartieSurowca, PortySprzetu, Segmenty, Zawory, OperacjeLog, t_log_uzyte_segmenty
from app.sockets import broadcast_apollo_update

# Utworzenie nowego Blueprintu dla operacji
bp = Blueprint('operations', __name__, url_prefix='/api/operations')

def get_pathfinder():
    """Pobiera instancję serwisu PathFinder z kontekstu aplikacji."""
    return current_app.extensions['pathfinder']

# Endpoint do tworzenia nowej partii przez tankowanie



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
        partia_query = db.select(PartieSurowca).join(PartieSurowca.sprzet).join(Sprzet.porty_sprzetu).where(PortySprzetu.nazwa_portu == start_point)
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
        if operacja.partie_surowca and operacja.id_sprzetu_zrodlowego and operacja.id_sprzetu_docelowego and operacja.id_sprzetu_zrodlowego != operacja.id_sprzetu_docelowego:
            sprzet_docelowy = operacja.sprzet_docelowy
            sprzet_zrodlowy = operacja.sprzet_zrodlowy
            
            if sprzet_docelowy and sprzet_zrodlowy:
                operacja.partie_surowca.id_sprzetu = sprzet_docelowy.id
                sprzet_docelowy.stan_sprzetu = 'Zatankowany'
                sprzet_zrodlowy.stan_sprzetu = 'Pusty'

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
        broadcast_apollo_update()

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
        cursor.execute("SELECT * FROM partie_surowca WHERE id_sprzetu = %s LIMIT 1", (id_celu,))
        partia_w_celu = cursor.fetchone()

        # Stworzenie "wirtualnej" partii dla dostawy
        unikalny_kod_dostawy = f"{typ_surowca_dostawy.replace(' ', '_')}-{dt.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}-DOSTAWA"
        cursor.execute("""
            INSERT INTO partie_surowca (unikalny_kod, nazwa_partii, typ_surowca, waga_aktualna_kg, waga_poczatkowa_kg, id_sprzetu, zrodlo_pochodzenia, pochodzenie_opis, status_partii, data_utworzenia)
            VALUES (%s, %s, %s, %s, %s, NULL, 'cysterna', %s, 'Archiwalna', NOW())
        """, (unikalny_kod_dostawy, unikalny_kod_dostawy, typ_surowca_dostawy, waga_kg, waga_kg, opis_operacji))
        id_partii_z_dostawy = cursor.lastrowid

        if partia_w_celu:
            # Mieszanie z istniejącą partią
            # 1. Archiwizuj starą partię w celu
            cursor.execute("UPDATE partie_surowca SET id_sprzetu = NULL, status_partii = 'Archiwalna' WHERE id = %s", (partia_w_celu['id'],))
            
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
                INSERT INTO partie_surowca (unikalny_kod, nazwa_partii, typ_surowca, waga_aktualna_kg, waga_poczatkowa_kg, id_sprzetu, status_partii, typ_transformacji)
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
            cursor.execute("UPDATE partie_surowca SET id_sprzetu = %s, status_partii = 'Surowy w reaktorze' WHERE id = %s", (id_celu, id_partii_z_dostawy))

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