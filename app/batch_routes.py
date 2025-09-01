# app/batch_routes.py

from flask import Blueprint, jsonify, request
from decimal import Decimal

from .extensions import db
from .models import *
from .batch_management_service import BatchManagementService


# Nowy Blueprint dla operacji na partiach
batch_bp = Blueprint('batches', __name__, url_prefix='/api/batches')

@batch_bp.route('/receive/from-tanker', methods=['POST'])
def receive_from_tanker():
    """
    Endpoint do rejestracji nowej Partii Pierwotnej z dostawy cysterną.
    """
    data = request.get_json()
    
    # Podstawowa walidacja danych wejściowych
    required_fields = ['material_type', 'source_name', 'quantity_kg']
    if not data or not all(field in data for field in required_fields):
        return jsonify({'status': 'error', 'message': 'Brak wymaganych pól: material_type, source_name, quantity_kg'}), 400

    try:
        quantity = Decimal(data['quantity_kg'])
        operator = data.get('operator', 'API_USER') # Domyślna wartość, jeśli nie podano

        # Wywołanie naszego serwisu
        result = BatchManagementService.create_raw_material_batch(
            material_type=data['material_type'],
            source_type='CYS', # Na stałe, bo to endpoint dla cystern
            source_name=data['source_name'],
            quantity=quantity,
            operator=operator
        )

        return jsonify({'status': 'success', 'data': result}), 201 # 201 Created

    except (ValueError, TypeError) as e:
        return jsonify({'status': 'error', 'message': f'Nieprawidłowe dane: {e}'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': f'Błąd serwera: {e}'}), 500


@batch_bp.route('/transfer/to-dirty-tank', methods=['POST'])
def transfer_to_dirty_tank():
    """
    Endpoint do tankowania Partii Pierwotnej do zbiornika brudnego.
    Wywołuje logikę, która tworzy/aktualizuje Mieszaninę.
    """
    data = request.get_json()
    required_fields = ['batch_id', 'tank_id']
    if not data or not all(field in data for field in required_fields):
        return jsonify({'status': 'error', 'message': 'Brak wymaganych pól: batch_id, tank_id'}), 400

    try:
        batch_id = int(data['batch_id'])
        tank_id = int(data['tank_id'])
        operator = data.get('operator', 'API_USER')

        # Wywołanie serwisu
        result = BatchManagementService.tank_into_dirty_tank(
            batch_id=batch_id,
            tank_id=tank_id,
            operator=operator
        )
        
        return jsonify({'status': 'success', 'data': result}), 200 # 200 OK

    except ValueError as e:
        # Ten błąd może być rzucony zarówno przez `int()` jak i przez nasz serwis
        return jsonify({'status': 'error', 'message': f'Nieprawidłowe dane lub stan: {e}'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': f'Błąd serwera: {e}'}), 500

@batch_bp.route('/transfer/tank-to-tank', methods=['POST'])
def transfer_between_dirty_tanks():
    """
    Endpoint do orkiestracji transferu między dwoma zbiornikami brudnymi.
    """
    data = request.get_json()
    required_fields = ['source_tank_id', 'destination_tank_id', 'quantity_kg']
    if not data or not all(field in data for field in required_fields):
        return jsonify({'status': 'error', 'message': 'Brak wymaganych pól: source_tank_id, destination_tank_id, quantity_kg'}), 400

    try:
        source_tank_id = int(data['source_tank_id'])
        destination_tank_id = int(data['destination_tank_id'])
        quantity = Decimal(data['quantity_kg'])
        operator = data.get('operator', 'API_USER')

        # Wywołanie serwisu, który zajmuje się całą logiką
        BatchManagementService.transfer_between_dirty_tanks(
            source_tank_id=source_tank_id,
            destination_tank_id=destination_tank_id,
            quantity_to_transfer=quantity,
            operator=operator
        )
        
        return jsonify({
            'status': 'success',
            'message': f'Pomyślnie przetransferowano {quantity} kg ze zbiornika {source_tank_id} do {destination_tank_id}.'
        }), 200

    except ValueError as e:
        return jsonify({'status': 'error', 'message': f'Nieprawidłowe dane lub stan: {e}'}), 400
    except Exception as e:
        # Serwis sam robi rollback, ale na wszelki wypadek
        db.session.rollback()
        return jsonify({'status': 'error', 'message': f'Błąd serwera: {e}'}), 500

@batch_bp.route('/receive/from-apollo', methods=['POST'])
def receive_from_apollo():
    """
    Endpoint do rejestracji nowej Partii Pierwotnej z wytopu w Apollo.
    """
    data = request.get_json()
    
    required_fields = ['material_type', 'source_name', 'quantity_kg']
    if not data or not all(field in data for field in required_fields):
        return jsonify({'status': 'error', 'message': 'Brak wymaganych pól: material_type, source_name, quantity_kg'}), 400

    try:
        quantity = Decimal(data['quantity_kg'])
        operator = data.get('operator', 'API_USER')

        # Wywołanie tej samej metody serwisu, ale z innym `source_type`
        result = BatchManagementService.create_raw_material_batch(
            material_type=data['material_type'],
            source_type='APOLLO', # Na stałe, bo to endpoint dla Apollo
            source_name=data['source_name'],
            quantity=quantity,
            operator=operator
        )

        return jsonify({'status': 'success', 'data': result}), 201

    except (ValueError, TypeError) as e:
        return jsonify({'status': 'error', 'message': f'Nieprawidłowe dane: {e}'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': f'Błąd serwera: {e}'}), 500

@batch_bp.route('/tanks/<int:tank_id>/status', methods=['GET'])
def get_tank_status(tank_id):
    """
    Zwraca szczegółowy status i skład mieszaniny dla danego zbiornika.
    """
    try:
        tank = db.session.get(Sprzet, tank_id)
        if not tank:
            return jsonify({'status': 'error', 'message': f'Zbiornik o ID {tank_id} nie został znaleziony.'}), 404

        # ZMIANA: Jawnie wyszukujemy mieszaninę na podstawie `active_mix_id`
        active_mix = db.session.get(TankMixes, tank.active_mix_id) if tank.active_mix_id else None
        
        if not active_mix:
            return jsonify({
                'status': 'success', 'tank_name': tank.nazwa_unikalna, 'is_empty': True,
                'data': {'total_weight': '0.00', 'components': []}
            }), 200

        composition = BatchManagementService.get_mix_composition(mix_id=active_mix.id)
        
        # 4. Sformatuj dane do JSON (Decimal nie jest domyślnie serializowalny)
        formatted_components = []
        for comp in composition['components']:
            formatted_components.append({
                'batch_id': comp['batch_id'],
                'batch_code': comp['batch_code'],
                'material_type': comp['material_type'],
                'quantity_in_mix': str(comp['quantity_in_mix']), # Konwersja na string
                'percentage': f"{comp['percentage']:.2f}" # Formatowanie do 2 miejsc po przecinku
            })

        return jsonify({
            'status': 'success',
            'tank_name': tank.nazwa_unikalna,
            'is_empty': False,
            'data': {
                'mix_id': active_mix.id,
                'mix_code': active_mix.unique_code,
                'total_weight': str(composition['total_weight']), # Konwersja na string
                'components': formatted_components
            }
        }), 200

    except Exception as e:
        # Nie robimy rollback, bo to operacja tylko do odczytu
        return jsonify({'status': 'error', 'message': f'Błąd serwera: {e}'}), 500

@batch_bp.route('/mixes/<int:mix_id>/composition', methods=['GET'])
def get_mix_composition_endpoint(mix_id):
    """
    Zwraca szczegółowy, dwupoziomowy skład dla danej mieszaniny.
    """
    try:
        composition_data = BatchManagementService.get_mix_composition(mix_id)
        if not composition_data:
            return jsonify({'error': f'Mieszanina o ID {mix_id} nie została znaleziona.'}), 404
        
        return jsonify(composition_data)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Błąd serwera: {e}'}), 500