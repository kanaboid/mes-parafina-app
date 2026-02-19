# test_calibration_routes.py
import unittest
import os
import json
import io
from decimal import Decimal
# Ustaw zmienną środowiskową przed importem app, aby pominąć SocketIO w testach
os.environ['ALEMBIC_MIGRATION_MODE'] = '1'
from app import create_app, db
from app.config import TestConfig
from app.models import Sprzet, TankCalibrationPoint
from sqlalchemy import text


class TestCalibrationRoutes(unittest.TestCase):
    def setUp(self):
        """Uruchamiane przed każdym testem, czyści bazę danych."""
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        
        with self.app.app_context():
            db.session.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            for table in reversed(db.metadata.sorted_tables):
                db.session.execute(text(f'TRUNCATE TABLE {table.name}'))
            db.session.execute(text("SET FOREIGN_KEY_CHECKS=1"))
            db.session.commit()
        
        self._setup_test_data()

    def tearDown(self):
        """Uruchamiane po każdym teście."""
        db.session.remove()
        self.app_context.pop()

    def _setup_test_data(self):
        """Tworzy dane testowe."""
        self.tank1 = Sprzet(
            id=1,
            nazwa_unikalna='B8C',
            typ_sprzetu='beczka_brudna',
            ipomiar_device_id='device-001',
            pojemnosc_tony=Decimal('78.4')
        )
        self.tank2 = Sprzet(
            id=2,
            nazwa_unikalna='R1',
            typ_sprzetu='reaktor',
            ipomiar_device_id='device-002',
            pojemnosc_tony=Decimal('50.0')
        )
        
        db.session.add_all([self.tank1, self.tank2])
        db.session.commit()

    def test_01_get_calibration_points(self):
        """Test GET /api/calibration/tank/<tank_id>/points"""
        # Dodaj punkt kalibracyjny
        point = TankCalibrationPoint(
            id_sprzetu=1,
            odczyt_mm=Decimal('2620'),
            waga_tony=Decimal('1.0')
        )
        db.session.add(point)
        db.session.commit()
        
        response = self.client.get('/api/calibration/tank/1/points')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('points', data)
        self.assertIn('pojemnosc_tony', data)
        self.assertEqual(len(data['points']), 1)
        self.assertEqual(data['points'][0]['tona'], 1.0)
        self.assertEqual(data['points'][0]['cm'], 262.0)

    def test_02_get_calibration_points_nonexistent_tank(self):
        """Test GET dla nieistniejącego zbiornika."""
        response = self.client.get('/api/calibration/tank/999/points')
        self.assertEqual(response.status_code, 404)

    def test_03_add_calibration_point_with_mm(self):
        """Test POST /api/calibration/tank/<tank_id>/points z odczyt_mm"""
        data = {
            'odczyt_mm': 2620.0,
            'waga_tony': 1.0
        }
        
        response = self.client.post(
            '/api/calibration/tank/1/points',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 201)
        result = json.loads(response.data)
        self.assertEqual(result['tona'], 1.0)
        self.assertEqual(result['cm'], 262.0)

    def test_04_add_calibration_point_with_cm(self):
        """Test POST z odczyt_cm (konwersja automatyczna)"""
        data = {
            'odczyt_cm': 262.0,
            'waga_tony': 1.0
        }
        
        response = self.client.post(
            '/api/calibration/tank/1/points',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 201)
        result = json.loads(response.data)
        self.assertEqual(result['cm'], 262.0)

    def test_05_add_calibration_point_missing_data(self):
        """Test POST bez wymaganych danych"""
        data = {'waga_tony': 1.0}  # Brak odczytu
        
        response = self.client.post(
            '/api/calibration/tank/1/points',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)

    def test_06_bulk_update_calibration_points(self):
        """Test POST /api/calibration/tank/<tank_id>/points/bulk"""
        data = {
            'points': [
                {'tona': 1, 'cm': 262},
                {'tona': 2, 'cm': 263},
                {'tona': 3, 'cm': 265}
            ],
            'pojemnosc_tony': 50.0
        }
        
        response = self.client.post(
            '/api/calibration/tank/1/points/bulk',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.data)
        self.assertEqual(result['created'], 3)
        
        # Sprawdź czy punkty zostały utworzone
        points_response = self.client.get('/api/calibration/tank/1/points')
        points_data = json.loads(points_response.data)
        self.assertEqual(len(points_data['points']), 3)

    def test_07_bulk_update_calibration_points_updates_existing(self):
        """Test że bulk_update aktualizuje istniejące punkty"""
        # Najpierw utwórz punkt
        point = TankCalibrationPoint(
            id_sprzetu=1,
            odczyt_mm=Decimal('2620'),
            waga_tony=Decimal('1.0')
        )
        db.session.add(point)
        db.session.commit()
        
        # Teraz bulk update
        data = {
            'points': [
                {'tona': 1, 'cm': 270},  # Zmieniona wartość
                {'tona': 2, 'cm': 280}
            ]
        }
        
        response = self.client.post(
            '/api/calibration/tank/1/points/bulk',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.data)
        self.assertEqual(result['created'], 1)
        self.assertEqual(result['updated'], 1)

    def test_08_update_calibration_point(self):
        """Test PUT /api/calibration/points/<point_id>"""
        # Utwórz punkt
        point = TankCalibrationPoint(
            id_sprzetu=1,
            odczyt_mm=Decimal('2620'),
            waga_tony=Decimal('1.0')
        )
        db.session.add(point)
        db.session.commit()
        point_id = point.id
        
        # Aktualizuj punkt
        data = {
            'odczyt_cm': 270.0,
            'waga_tony': 1.5
        }
        
        response = self.client.put(
            f'/api/calibration/points/{point_id}',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Sprawdź zmiany
        updated_point = db.session.get(TankCalibrationPoint, point_id)
        self.assertEqual(updated_point.odczyt_mm, Decimal('2700'))
        self.assertEqual(updated_point.waga_tony, Decimal('1.5'))

    def test_09_delete_calibration_point(self):
        """Test DELETE /api/calibration/points/<point_id>"""
        # Utwórz punkt
        point = TankCalibrationPoint(
            id_sprzetu=1,
            odczyt_mm=Decimal('2620'),
            waga_tony=Decimal('1.0')
        )
        db.session.add(point)
        db.session.commit()
        point_id = point.id
        
        # Usuń punkt
        response = self.client.delete(f'/api/calibration/points/{point_id}')
        self.assertEqual(response.status_code, 200)
        
        # Sprawdź że punkt został usunięty
        deleted_point = db.session.get(TankCalibrationPoint, point_id)
        self.assertIsNone(deleted_point)

    def test_10_delete_calibration_point_nonexistent(self):
        """Test DELETE nieistniejącego punktu"""
        response = self.client.delete('/api/calibration/points/99999')
        self.assertEqual(response.status_code, 404)

    def test_11_test_conversion(self):
        """Test POST /api/calibration/tank/<tank_id>/test"""
        # Dodaj punkty kalibracyjne
        points = [
            TankCalibrationPoint(id_sprzetu=1, odczyt_mm=Decimal('2620'), waga_tony=Decimal('1.0')),
            TankCalibrationPoint(id_sprzetu=1, odczyt_mm=Decimal('2630'), waga_tony=Decimal('2.0')),
            TankCalibrationPoint(id_sprzetu=1, odczyt_mm=Decimal('2650'), waga_tony=Decimal('3.0')),
        ]
        db.session.add_all(points)
        db.session.commit()
        
        # Test konwersji dla odczytu między punktami
        data = {'odczyt_cm': 264.0}
        
        response = self.client.post(
            '/api/calibration/tank/1/test',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.data)
        self.assertIsNotNone(result['waga_tony'])
        self.assertAlmostEqual(result['waga_tony'], 2.5, places=1)
        self.assertTrue(result['uzyto_interpolacji'])

    def test_12_test_conversion_exact_match(self):
        """Test konwersji z dokładnym dopasowaniem"""
        point = TankCalibrationPoint(
            id_sprzetu=1,
            odczyt_mm=Decimal('2620'),
            waga_tony=Decimal('1.0')
        )
        db.session.add(point)
        db.session.commit()
        
        data = {'odczyt_cm': 262.0}
        
        response = self.client.post(
            '/api/calibration/tank/1/test',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.data)
        self.assertEqual(result['waga_tony'], 1.0)
        self.assertFalse(result['uzyto_interpolacji'])

    def test_13_get_tanks_with_calibration(self):
        """Test GET /api/calibration/tanks"""
        # Dodaj kalibrację dla tank1
        point = TankCalibrationPoint(
            id_sprzetu=1,
            odczyt_mm=Decimal('2620'),
            waga_tony=Decimal('1.0')
        )
        db.session.add(point)
        db.session.commit()
        
        response = self.client.get('/api/calibration/tanks')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIsInstance(data, list)
        
        tank1_data = next((t for t in data if t['id'] == 1), None)
        self.assertIsNotNone(tank1_data)
        self.assertTrue(tank1_data['ma_kalibracje'])
        self.assertEqual(tank1_data['liczba_punktow'], 1)
        
        tank2_data = next((t for t in data if t['id'] == 2), None)
        self.assertIsNotNone(tank2_data)
        self.assertFalse(tank2_data['ma_kalibracje'])

    def test_14_update_tank_capacity(self):
        """Test PUT /api/calibration/sprzet/<tank_id>/pojemnosc"""
        data = {'pojemnosc_tony': 60.0}
        
        response = self.client.put(
            '/api/calibration/sprzet/1/pojemnosc',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Sprawdź zmianę
        tank = db.session.get(Sprzet, 1)
        self.assertEqual(tank.pojemnosc_tony, Decimal('60.0'))

    def test_15_update_tank_capacity_exceeds_max(self):
        """Test że pojemność > 90T jest odrzucana"""
        data = {'pojemnosc_tony': 100.0}
        
        response = self.client.put(
            '/api/calibration/sprzet/1/pojemnosc',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)

    def test_16_update_tank_capacity_nonexistent_tank(self):
        """Test aktualizacji pojemności nieistniejącego zbiornika"""
        data = {'pojemnosc_tony': 50.0}
        
        response = self.client.put(
            '/api/calibration/sprzet/999/pojemnosc',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 404)

    def test_17_import_calibration_csv(self):
        """Test POST /api/calibration/tank/<tank_id>/import-csv"""
        # Przygotuj dane CSV w pamięci
        csv_content = "Tony,CM\n1,262\n2,263\n3,265\n"
        
        response = self.client.post(
            '/api/calibration/tank/1/import-csv',
            data={
                'file': (io.BytesIO(csv_content.encode('utf-8')), 'test.csv')
            },
            content_type='multipart/form-data'
        )
        
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.data)
        self.assertEqual(result['created'], 3)
        
        # Sprawdź czy punkty zostały zaimportowane
        points_response = self.client.get('/api/calibration/tank/1/points')
        points_data = json.loads(points_response.data)
        self.assertEqual(len(points_data['points']), 3)

    def test_18_import_calibration_csv_missing_file(self):
        """Test importu CSV bez pliku"""
        response = self.client.post('/api/calibration/tank/1/import-csv')
        self.assertEqual(response.status_code, 400)

    def test_19_add_calibration_point_duplicate_odczyt_mm(self):
        """Test że duplikat odczyt_mm dla tego samego zbiornika jest aktualizowany"""
        # Dodaj pierwszy punkt
        data1 = {'odczyt_mm': 2620.0, 'waga_tony': 1.0}
        response1 = self.client.post(
            '/api/calibration/tank/1/points',
            data=json.dumps(data1),
            content_type='application/json'
        )
        self.assertEqual(response1.status_code, 201)
        
        # Spróbuj dodać punkt z tym samym odczyt_mm
        data2 = {'odczyt_mm': 2620.0, 'waga_tony': 2.0}
        response2 = self.client.post(
            '/api/calibration/tank/1/points',
            data=json.dumps(data2),
            content_type='application/json'
        )
        
        # Powinien zaktualizować istniejący punkt
        self.assertEqual(response2.status_code, 201)
        
        # Sprawdź że jest tylko jeden punkt z zaktualizowaną wagą
        points_response = self.client.get('/api/calibration/tank/1/points')
        points_data = json.loads(points_response.data)
        self.assertEqual(len(points_data['points']), 1)
        self.assertEqual(points_data['points'][0]['tona'], 2.0)


if __name__ == '__main__':
    unittest.main()
