# app/batch_routes.py

from flask import Blueprint, jsonify, request
from decimal import Decimal

from . import db
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