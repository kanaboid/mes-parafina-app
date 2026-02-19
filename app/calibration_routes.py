# app/calibration_routes.py

from flask import Blueprint, jsonify, request, current_app
from .extensions import db
from .models import Sprzet, TankCalibrationPoint
from .calibration_service import CalibrationService
from decimal import Decimal
from datetime import datetime
import csv
import io

bp = Blueprint('calibration', __name__, url_prefix='/api/calibration')


@bp.route('/tank/<int:tank_id>/points', methods=['GET'])
def get_calibration_points(tank_id):
    """Pobiera wszystkie punkty kalibracyjne dla konkretnego zbiornika."""
    try:
        sprzet = db.session.get(Sprzet, tank_id)
        if not sprzet:
            return jsonify({'error': 'Zbiornik nie istnieje'}), 404
        
        points = CalibrationService.get_calibration_points(tank_id)
        pojemnosc_tony = float(sprzet.pojemnosc_tony) if sprzet.pojemnosc_tony else None
        
        return jsonify({
            'pojemnosc_tony': pojemnosc_tony,
            'points': points
        })
    except Exception as e:
        current_app.logger.error(f"Błąd podczas pobierania punktów kalibracyjnych: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/tank/<int:tank_id>/points', methods=['POST'])
def add_calibration_point(tank_id):
    """Dodaje punkt kalibracyjny dla konkretnego zbiornika."""
    try:
        sprzet = db.session.get(Sprzet, tank_id)
        if not sprzet:
            return jsonify({'error': 'Zbiornik nie istnieje'}), 404
        
        data = request.get_json()
        
        # Obsługa zarówno mm jak i cm
        if 'odczyt_cm' in data:
            odczyt_mm = Decimal(str(data['odczyt_cm'])) * Decimal('10')
        elif 'odczyt_mm' in data:
            odczyt_mm = Decimal(str(data['odczyt_mm']))
        else:
            return jsonify({'error': 'Brak odczytu (odczyt_mm lub odczyt_cm)'}), 400
        
        waga_tony = Decimal(str(data.get('waga_tony', 0)))
        if waga_tony <= 0:
            return jsonify({'error': 'Waga w tonach musi być dodatnia'}), 400
        
        data_kalibracji = None
        if 'data_kalibracji' in data:
            try:
                data_kalibracji = datetime.fromisoformat(data['data_kalibracji'].replace('Z', '+00:00'))
            except:
                pass
        
        uwagi = data.get('uwagi')
        
        point = CalibrationService.add_calibration_point(
            tank_id, odczyt_mm, waga_tony, data_kalibracji, uwagi
        )
        
        db.session.commit()
        
        return jsonify({
            'id': point.id,
            'tona': float(point.waga_tony),
            'cm': float(point.odczyt_mm / Decimal('10')),
            'mm': float(point.odczyt_mm),
            'message': 'Punkt kalibracyjny dodany pomyślnie'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Błąd podczas dodawania punktu kalibracyjnego: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/tank/<int:tank_id>/points/bulk', methods=['POST'])
def bulk_update_calibration_points(tank_id):
    """Masowe dodanie/aktualizacja punktów kalibracyjnych (dla tabeli 1-90T)."""
    try:
        sprzet = db.session.get(Sprzet, tank_id)
        if not sprzet:
            return jsonify({'error': 'Zbiornik nie istnieje'}), 404
        
        data = request.get_json()
        points_data = data.get('points', [])
        pojemnosc_tony = None
        
        if 'pojemnosc_tony' in data:
            pojemnosc_tony = Decimal(str(data['pojemnosc_tony']))
            if pojemnosc_tony > Decimal('90.0'):
                return jsonify({'error': 'Pojemność nie może przekraczać 90T'}), 400
        
        result = CalibrationService.bulk_update_calibration_points(tank_id, points_data, pojemnosc_tony)
        db.session.commit()
        
        return jsonify({
            'message': 'Punkty kalibracyjne zaktualizowane pomyślnie',
            'created': result['created'],
            'updated': result['updated'],
            'total': result['total']
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Błąd podczas masowej aktualizacji punktów kalibracyjnych: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/points/<int:point_id>', methods=['PUT'])
def update_calibration_point(point_id):
    """Aktualizuje punkt kalibracyjny."""
    try:
        point = db.session.get(TankCalibrationPoint, point_id)
        if not point:
            return jsonify({'error': 'Punkt kalibracyjny nie istnieje'}), 404
        
        data = request.get_json()
        
        # Obsługa zarówno mm jak i cm
        if 'odczyt_cm' in data:
            odczyt_mm = Decimal(str(data['odczyt_cm'])) * Decimal('10')
        elif 'odczyt_mm' in data:
            odczyt_mm = Decimal(str(data['odczyt_mm']))
        else:
            return jsonify({'error': 'Brak odczytu (odczyt_mm lub odczyt_cm)'}), 400
        
        waga_tony = Decimal(str(data.get('waga_tony', point.waga_tony)))
        if waga_tony <= 0:
            return jsonify({'error': 'Waga w tonach musi być dodatnia'}), 400
        
        data_kalibracji = None
        if 'data_kalibracji' in data:
            try:
                data_kalibracji = datetime.fromisoformat(data['data_kalibracji'].replace('Z', '+00:00'))
            except:
                pass
        
        uwagi = data.get('uwagi')
        
        success = CalibrationService.update_calibration_point(
            point_id, odczyt_mm, waga_tony, data_kalibracji, uwagi
        )
        
        if not success:
            return jsonify({'error': 'Nie można zaktualizować punktu (konflikt z istniejącym punktem)'}), 400
        
        db.session.commit()
        
        return jsonify({
            'message': 'Punkt kalibracyjny zaktualizowany pomyślnie'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Błąd podczas aktualizacji punktu kalibracyjnego: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/points/<int:point_id>', methods=['DELETE'])
def delete_calibration_point(point_id):
    """Usuwa punkt kalibracyjny."""
    try:
        success = CalibrationService.delete_calibration_point(point_id)
        
        if not success:
            return jsonify({'error': 'Punkt kalibracyjny nie istnieje'}), 404
        
        db.session.commit()
        
        return jsonify({'message': 'Punkt kalibracyjny usunięty pomyślnie'}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Błąd podczas usuwania punktu kalibracyjnego: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/tank/<int:tank_id>/test', methods=['POST'])
def test_conversion(tank_id):
    """Test konwersji dla podanego odczytu w mm."""
    try:
        sprzet = db.session.get(Sprzet, tank_id)
        if not sprzet:
            return jsonify({'error': 'Zbiornik nie istnieje'}), 404
        
        data = request.get_json()
        
        # Obsługa zarówno mm jak i cm
        if 'odczyt_cm' in data:
            odczyt_mm = Decimal(str(data['odczyt_cm'])) * Decimal('10')
        elif 'odczyt_mm' in data:
            odczyt_mm = Decimal(str(data['odczyt_mm']))
        else:
            return jsonify({'error': 'Brak odczytu (odczyt_mm lub odczyt_cm)'}), 400
        
        waga_tony = CalibrationService.convert_mm_to_tonnes(tank_id, odczyt_mm)
        
        # Sprawdź czy użyto interpolacji
        points = CalibrationService.get_calibration_points(tank_id)
        uzyto_interpolacji = False
        
        if points:
            for p in points:
                if abs(Decimal(str(p['mm'])) - odczyt_mm) < Decimal('0.01'):
                    break
            else:
                uzyto_interpolacji = True
        
        return jsonify({
            'odczyt_mm': float(odczyt_mm),
            'odczyt_cm': float(odczyt_mm / Decimal('10')),
            'waga_tony': float(waga_tony) if waga_tony else None,
            'uzyto_interpolacji': uzyto_interpolacji if waga_tony else False
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Błąd podczas testu konwersji: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/tanks', methods=['GET'])
def get_tanks_with_calibration():
    """Lista wszystkich zbiorników z informacją o kalibracji."""
    try:
        tanks = db.session.execute(
            db.select(Sprzet).where(Sprzet.ipomiar_device_id.isnot(None))
        ).scalars().all()
        
        result = []
        for tank in tanks:
            has_calibration = CalibrationService.has_calibration(tank.id)
            points_count = 0
            if has_calibration:
                points = CalibrationService.get_calibration_points(tank.id)
                points_count = len(points)
            
            result.append({
                'id': tank.id,
                'nazwa': tank.nazwa_unikalna,
                'ma_kalibracje': has_calibration,
                'liczba_punktow': points_count,
                'pojemnosc_tony': float(tank.pojemnosc_tony) if tank.pojemnosc_tony else None
            })
        
        return jsonify(result), 200
        
    except Exception as e:
        current_app.logger.error(f"Błąd podczas pobierania listy zbiorników: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/tank/<int:tank_id>/import-csv', methods=['POST'])
def import_calibration_csv(tank_id):
    """Import punktów kalibracyjnych z pliku CSV."""
    try:
        sprzet = db.session.get(Sprzet, tank_id)
        if not sprzet:
            return jsonify({'error': 'Zbiornik nie istnieje'}), 404
        
        if 'file' not in request.files:
            return jsonify({'error': 'Brak pliku CSV'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Brak pliku CSV'}), 400
        
        # Odczytaj plik CSV
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.DictReader(stream)
        
        points_data = []
        max_tona = Decimal('0')
        
        for row in csv_reader:
            # Obsługa różnych formatów nagłówków
            tona_key = None
            cm_key = None
            
            for key in row.keys():
                key_lower = key.lower().strip()
                if 'ton' in key_lower or 'tona' in key_lower:
                    tona_key = key
                elif 'cm' in key_lower:
                    cm_key = key
            
            if not tona_key or not cm_key:
                continue
            
            try:
                tona = Decimal(str(row[tona_key]).strip())
                cm = Decimal(str(row[cm_key]).strip())
                
                if tona > max_tona:
                    max_tona = tona
                
                points_data.append({
                    'tona': float(tona),
                    'cm': float(cm)
                })
            except (ValueError, KeyError) as e:
                current_app.logger.warning(f"Pominięto nieprawidłowy wiersz CSV: {row}, błąd: {e}")
                continue
        
        if not points_data:
            return jsonify({'error': 'Brak poprawnych danych w pliku CSV'}), 400
        
        # Ustaw pojemność na maksymalną wartość z CSV jeśli nie jest ustawiona
        pojemnosc_tony = None
        if not sprzet.pojemnosc_tony:
            pojemnosc_tony = max_tona
        
        result = CalibrationService.bulk_update_calibration_points(tank_id, points_data, pojemnosc_tony)
        db.session.commit()
        
        return jsonify({
            'message': 'Import zakończony pomyślnie',
            'created': result['created'],
            'updated': result['updated'],
            'total': result['total'],
            'pojemnosc_tony_ustawiona': float(pojemnosc_tony) if pojemnosc_tony else None
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Błąd podczas importu CSV: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/sprzet/<int:tank_id>/pojemnosc', methods=['PUT'])
def update_tank_capacity(tank_id):
    """Aktualizacja pojemności zbiornika."""
    try:
        sprzet = db.session.get(Sprzet, tank_id)
        if not sprzet:
            return jsonify({'error': 'Zbiornik nie istnieje'}), 404
        
        data = request.get_json()
        pojemnosc_tony = Decimal(str(data.get('pojemnosc_tony', 0)))
        
        if pojemnosc_tony > Decimal('90.0'):
            return jsonify({'error': 'Pojemność nie może przekraczać 90T'}), 400
        
        if pojemnosc_tony < Decimal('0'):
            return jsonify({'error': 'Pojemność nie może być ujemna'}), 400
        
        sprzet.pojemnosc_tony = pojemnosc_tony
        db.session.commit()
        
        return jsonify({
            'message': 'Pojemność zbiornika zaktualizowana pomyślnie',
            'pojemnosc_tony': float(pojemnosc_tony)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Błąd podczas aktualizacji pojemności: {e}")
        return jsonify({'error': str(e)}), 500
