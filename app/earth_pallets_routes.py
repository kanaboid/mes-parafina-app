# app/earth_pallets_routes.py

from flask import Blueprint, jsonify, request, render_template
from .extensions import db
from .models import EarthPallets
from datetime import datetime
from sqlalchemy import func, desc
from decimal import Decimal
import re

bp = Blueprint('earth_pallets', __name__, url_prefix='/earth-pallets')


def get_next_lp():
    """
    Generuje kolejny numer LP.
    Logika: B1-B99, potem C1-C99, D1-D99, itd.
    """
    # Pobierz ostatni LP
    last_pallet = db.session.query(EarthPallets).order_by(desc(EarthPallets.id)).first()
    
    if not last_pallet:
        # Pierwsza paleta
        return "B1"
    
    # Parsuj ostatni LP (np. "B42" -> litera="B", numer=42)
    match = re.match(r'([A-Z])(\d+)', last_pallet.lp)
    if not match:
        # Fallback - jeśli format jest nieprawidłowy
        return "B1"
    
    letter, number = match.groups()
    number = int(number)
    
    # Jeśli numer < 99, zwiększ numer
    if number < 99:
        return f"{letter}{number + 1}"
    else:
        # Jeśli osiągnięto 99, przejdź do następnej litery
        next_letter = chr(ord(letter) + 1)
        return f"{next_letter}1"


@bp.route('/')
def index():
    """Strona główna z tabelą palet"""
    return render_template('earth_pallets.html')


@bp.route('/api/pallets', methods=['GET'])
def get_pallets():
    """Pobiera wszystkie palety (sortowane po ID od najnowszych)"""
    try:
        pallets = db.session.query(EarthPallets).order_by(desc(EarthPallets.id)).all()
        
        # Oblicz statystyki
        total_weight = db.session.query(func.sum(EarthPallets.waga)).scalar() or 0
        total_count = db.session.query(func.count(EarthPallets.id)).scalar() or 0
        
        return jsonify({
            'success': True,
            'pallets': [{
                'id': p.id,
                'lp': p.lp,
                'waga': float(p.waga),
                'zwazyl': p.zwazyl,
                'data_wazenia': p.data_wazenia.isoformat() + 'Z' if p.data_wazenia else None,
                'uwagi': p.uwagi
            } for p in pallets],
            'statistics': {
                'total_weight': float(total_weight),
                'total_count': total_count,
                'average_weight': float(total_weight / total_count) if total_count > 0 else 0
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/next-lp', methods=['GET'])
def next_lp():
    """Zwraca kolejny dostępny numer LP"""
    try:
        next_lp_number = get_next_lp()
        return jsonify({
            'success': True,
            'next_lp': next_lp_number
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/pallets', methods=['POST'])
def add_pallet():
    """Dodaje nową paletę"""
    try:
        data = request.get_json()
        
        # Walidacja danych
        if not data.get('waga'):
            return jsonify({'success': False, 'error': 'Waga jest wymagana'}), 400
        
        try:
            waga = float(data['waga'])
            if waga <= 0:
                return jsonify({'success': False, 'error': 'Waga musi być większa od 0'}), 400
        except ValueError:
            return jsonify({'success': False, 'error': 'Nieprawidłowa wartość wagi'}), 400
        
        # Użyj przekazanego LP lub wygeneruj nowy
        lp = data.get('lp') or get_next_lp()
        
        # Sprawdź czy LP już istnieje
        existing = db.session.query(EarthPallets).filter_by(lp=lp).first()
        if existing:
            return jsonify({'success': False, 'error': f'Paleta {lp} już istnieje'}), 400
        
        # Utwórz nową paletę
        new_pallet = EarthPallets(
            lp=lp,
            waga=Decimal(str(waga)),
            zwazyl=data.get('zwazyl', '').strip() or None,
            uwagi=data.get('uwagi', '').strip() or None
        )
        
        db.session.add(new_pallet)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Paleta {lp} została dodana pomyślnie',
            'pallet': {
                'id': new_pallet.id,
                'lp': new_pallet.lp,
                'waga': float(new_pallet.waga),
                'zwazyl': new_pallet.zwazyl,
                'data_wazenia': new_pallet.data_wazenia.isoformat() + 'Z',
                'uwagi': new_pallet.uwagi
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/pallets/<int:pallet_id>', methods=['PUT'])
def update_pallet(pallet_id):
    """Aktualizuje istniejącą paletę"""
    try:
        pallet = db.session.get(EarthPallets, pallet_id)
        if not pallet:
            return jsonify({'success': False, 'error': 'Paleta nie została znaleziona'}), 404
        
        data = request.get_json()
        
        # Aktualizuj tylko przekazane pola
        if 'waga' in data:
            try:
                waga = float(data['waga'])
                if waga <= 0:
                    return jsonify({'success': False, 'error': 'Waga musi być większa od 0'}), 400
                pallet.waga = Decimal(str(waga))
            except ValueError:
                return jsonify({'success': False, 'error': 'Nieprawidłowa wartość wagi'}), 400
        
        if 'zwazyl' in data:
            pallet.zwazyl = data['zwazyl'].strip() or None
        
        if 'uwagi' in data:
            pallet.uwagi = data['uwagi'].strip() or None
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Paleta {pallet.lp} została zaktualizowana',
            'pallet': {
                'id': pallet.id,
                'lp': pallet.lp,
                'waga': float(pallet.waga),
                'zwazyl': pallet.zwazyl,
                'data_wazenia': pallet.data_wazenia.isoformat() + 'Z',
                'uwagi': pallet.uwagi
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/pallets/<int:pallet_id>', methods=['DELETE'])
def delete_pallet(pallet_id):
    """Usuwa paletę (z ostrożnością - zalecane tylko dla błędnych wpisów)"""
    try:
        pallet = db.session.get(EarthPallets, pallet_id)
        if not pallet:
            return jsonify({'success': False, 'error': 'Paleta nie została znaleziona'}), 404
        
        lp = pallet.lp
        db.session.delete(pallet)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Paleta {lp} została usunięta'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

