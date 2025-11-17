# app/workflow_routes.py
from flask import Blueprint, jsonify, request
from decimal import Decimal, InvalidOperation
from .workflow_service import WorkflowService
from .extensions import db

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