# app/workflow_routes.py
from flask import Blueprint, jsonify, request, current_app
from decimal import Decimal, InvalidOperation
from .workflow_service import WorkflowService
from .extensions import db
from .models import OperacjeLog, Segmenty, Zawory, Sprzet

# Stworzenie Blueprintu dla przepływów pracy
workflow_bp = Blueprint('workflow', __name__, url_prefix='/api/workflow')

@workflow_bp.route('/mix/<int:mix_id>/assess', methods=['POST'])
def assess_mix_quality_endpoint(mix_id: int):
    """
    Endpoint API do oceny jakości mieszaniny.
    Oczekuje JSON: {"decision": "OK" | "ZLA", "operator": "nazwa_operatora", "reason": "opcjonalny_powod"}
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Brak danych w formacie JSON.'}), 400

    decision = data.get('decision')
    operator = data.get('operator')
    reason = data.get('reason')

    if not decision or not operator:
        return jsonify({'error': 'Pola "decision" oraz "operator" są wymagane.'}), 400

    try:
        # Serwis zwraca bezpośrednio obiekt `mix`
        updated_mix = WorkflowService.assess_mix_quality(
            mix_id=mix_id,
            decision=decision,
            operator=operator,
            reason=reason
        )
        return jsonify({
            'success': True,
            'message': f"Status mieszaniny ID {mix_id} został zmieniony na '{updated_mix.process_status}'.",
            'mix_id': updated_mix.id,
            'new_status': updated_mix.process_status
        }), 200
        
    except ValueError as e:
        # Błędy walidacji logiki biznesowej (np. zły stan, brak powodu)
        return jsonify({'error': str(e)}), 422 # 422 Unprocessable Entity
    except Exception as e:
        # Pozostałe, nieoczekiwane błędy serwera
        db.session.rollback()
        return jsonify({'error': f'Wystąpił nieoczekiwany błąd serwera: {str(e)}'}), 500


@workflow_bp.route('/mix/<int:mix_id>/add-bleach', methods=['POST'])
def add_bleaching_earth_endpoint(mix_id: int):
    """
    Endpoint API do rejestrowania dodania ziemi bielącej.
    Oczekuje JSON: {"bags_count": 5, "bag_weight": 25.0, "operator": "nazwa_operatora"}
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Brak danych w formacie JSON.'}), 400

    try:
        bags_count = int(data.get('bags_count'))
        # Używamy str(), aby uniknąć problemów z konwersją float -> Decimal
        bag_weight = Decimal(str(data.get('bag_weight')))
        operator = data.get('operator')
    except (TypeError, ValueError, InvalidOperation, AttributeError):
        return jsonify({'error': 'Pola "bags_count" i "bag_weight" muszą być poprawnymi liczbami.'}), 400

    if not operator or bags_count <= 0 or bag_weight <= 0:
        return jsonify({'error': 'Pola "operator", "bags_count" (>0) oraz "bag_weight" (>0) są wymagane.'}), 400

    try:
        # Serwis zwraca słownik z kluczami 'mix' i 'message'
        result = WorkflowService.add_bleaching_earth(
            mix_id=mix_id,
            bags_count=bags_count,
            bag_weight=bag_weight,
            operator=operator
        )
        updated_mix = result['mix']
        
        return jsonify({
            'success': True,
            'message': result['message'], # Używamy wiadomości zwróconej przez serwis
            'mix_id': updated_mix.id,
            'new_status': updated_mix.process_status,
            'total_bags': updated_mix.bleaching_earth_bags_total
        }), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 422
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Wystąpił nieoczekiwany błąd serwera: {str(e)}'}), 500

@workflow_bp.route('/mix/<int:mix_id>/start-filtration', methods=['POST'])
def start_filtration_endpoint(mix_id: int):
    """
    Rozpoczyna cykl filtracji dla mieszaniny. Pathfinder jest wywoływany na początku.
    Oczekuje JSON: {"start": "R1_OUT", "cel": "R5_IN"} oraz opcjonalnie:
    otwarte_zawory (lista; brak = pobranie z bazy), operator (brak = "GUI"), sprzet_posredni.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Brak danych w formacie JSON.'}), 400

    start_point = data.get('start')
    end_point = data.get('cel')
    open_valves_list = data.get('otwarte_zawory')
    operator = data.get('operator') or 'GUI'
    sprzet_posredni = data.get('sprzet_posredni')

    if not start_point or not end_point:
        return jsonify({
            'error': 'Wymagane pola: start, cel.'
        }), 400

    # Używamy wszystkich zaworów (trasę teoretycznie możliwą) – konflikt z innymi operacjami
    # jest sprawdzany osobno. Dzięki temu można uruchomić równoległą operację na innej trasie,
    # gdy zawory na trasie docelowej są zamknięte (np. po zakończeniu poprzedniej operacji).
    if not open_valves_list:
        open_valves_list = db.session.execute(db.select(Zawory.nazwa_zaworu)).scalars().all()

    try:
        pathfinder = current_app.extensions['pathfinder']
    except KeyError:
        return jsonify({'error': 'Pathfinder nie jest dostępny.'}), 500

    # Filtr wybierany automatycznie: tylko ten, który ma fizyczne połączenie z reaktorem docelowym (filtr_OUT → cel)
    if not sprzet_posredni:
        filtry = db.session.execute(
            db.select(Sprzet.nazwa_unikalna).where(Sprzet.typ_sprzetu == 'filtr').order_by(Sprzet.nazwa_unikalna)
        ).scalars().all()
        if not filtry:
            return jsonify({'error': 'Brak zdefiniowanego filtra w systemie. Operacje filtracji muszą przechodzić przez filtr.'}), 400
        sprzet_posredni = None
        for nazwa_filtra in filtry:
            filtr_out = f"{nazwa_filtra}_OUT"
            trasa_do_celu = pathfinder.find_path(filtr_out, end_point, open_valves_list)
            if trasa_do_celu:
                sprzet_posredni = nazwa_filtra
                break
        if not sprzet_posredni:
            return jsonify({
                'error': f'Żaden filtr ({", ".join(filtry)}) nie ma połączenia z reaktorem docelowym. Sprawdź topologię (wyjście filtra → reaktor).'
            }), 404

    # Trasa zawsze przez wybrany filtr: start → filtr_IN → filtr_OUT → cel
    posredni_in = f"{sprzet_posredni}_IN"
    posredni_out = f"{sprzet_posredni}_OUT"
    sciezka_1 = pathfinder.find_path(start_point, posredni_in, open_valves_list)
    if not sciezka_1:
        return jsonify({"error": f"Nie znaleziono ścieżki z {start_point} do {posredni_in}."}), 404
    sciezka_wewnetrzna = pathfinder.find_path(posredni_in, posredni_out, open_valves_list)
    if not sciezka_wewnetrzna:
        return jsonify({"error": f"Nie znaleziono ścieżki wewnętrznej w {sprzet_posredni}."}), 404
    sciezka_2 = pathfinder.find_path(posredni_out, end_point, open_valves_list)
    if not sciezka_2:
        return jsonify({"error": f"Nie znaleziono ścieżki z {posredni_out} do {end_point}."}), 404
    znaleziona_sciezka_nazwy = sciezka_1 + sciezka_wewnetrzna + sciezka_2

    # Sprawdź konflikty tras
    from sqlalchemy import select
    konflikt_query = db.select(Segmenty.nazwa_segmentu).join(Segmenty.operacje_log).where(
        OperacjeLog.status_operacji == 'aktywna',
        Segmenty.nazwa_segmentu.in_(znaleziona_sciezka_nazwy)
    )
    konflikty = db.session.execute(konflikt_query).scalars().all()
    if konflikty:
        return jsonify({
            "error": "Konflikt zasobów - trasa jest zajęta przez inną operację.",
            "zajete_segmenty": [k for k in konflikty]
        }), 409

    # Otwórz tylko zawory na trasie (jak w start_apollo_transfer), nie wszystkie
    zawory_na_trasie = set()
    for u, v, edge_data in pathfinder.graph.edges(data=True):
        if edge_data.get('segment_name') in znaleziona_sciezka_nazwy:
            zawory_na_trasie.add(edge_data['valve_name'])
    if zawory_na_trasie:
        db.session.execute(
            db.update(Zawory)
            .where(Zawory.nazwa_zaworu.in_(zawory_na_trasie))
            .values(stan='OTWARTY')
        )

    try:
        result = WorkflowService.start_filtration_cycle(
            mix_id=mix_id,
            operator=operator,
            segment_names=znaleziona_sciezka_nazwy,
            start_point=start_point,
            end_point=end_point,
        )
        return jsonify({
            'success': True,
            'message': f"Cykl filtracji ({result['typ_operacji']}) został rozpoczęty.",
            'mix_id': result['mix'].id,
            'new_status': result['mix'].process_status,
            'id_operacji': result['id_operacji'],
            'trasa': result['trasa'],
        }), 201
    except ValueError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 422
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Wystąpił nieoczekiwany błąd serwera: {str(e)}'}), 500


@workflow_bp.route('/reactors/load-batches', methods=['POST'])
def load_batches_to_reactor_endpoint():
    """
    Endpoint API do tworzenia nowej mieszaniny w reaktorze lub dodawania do istniejącej.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Brak danych w formacie JSON.'}), 400

    try:
        reactor_id = data['reactor_id']
        batches_to_load = data['batches']
        operator = data.get('operator', 'API_USER')

        # Wywołanie logiki serwisowej
        updated_mix, was_created = WorkflowService.load_batches_to_reactor(
            reactor_id=reactor_id,
            batches_to_load=batches_to_load,
            operator=operator
        )
        
        if was_created:
            message = f"Pomyślnie utworzono nową mieszaninę '{updated_mix.unique_code}' w reaktorze."
            status_code = 201 # Created
        else:
            message = f"Pomyślnie dodano partie do istniejącej mieszaniny '{updated_mix.unique_code}'."
            status_code = 200 # OK
        
        return jsonify({
            'success': True,
            'message': message,
            'was_created': was_created,
            'mix_id': updated_mix.id,
            'unique_code': updated_mix.unique_code
        }), status_code

    except (KeyError, TypeError):
        return jsonify({'error': 'Nieprawidłowy format danych. Wymagane pola: "reactor_id", "batches". Pole "operator" jest opcjonalne.'}), 400
    except ValueError as e:
        return jsonify({'error': str(e)}), 422
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Wystąpił nieoczekiwany błąd serwera: {str(e)}'}), 500 