# test_calibration_service.py
import unittest
import os
from decimal import Decimal
from datetime import datetime, timezone
# Ustaw zmienną środowiskową przed importem app, aby pominąć SocketIO w testach
os.environ['ALEMBIC_MIGRATION_MODE'] = '1'
from app import create_app, db
from app.config import TestConfig
from app.models import Sprzet, TankCalibrationPoint
from app.calibration_service import CalibrationService
from sqlalchemy import text


class TestCalibrationService(unittest.TestCase):
    def setUp(self):
        """Uruchamiane przed każdym testem, czyści bazę danych."""
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
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
        """Tworzy dane testowe: zbiorniki i punkty kalibracyjne."""
        # Utwórz zbiorniki testowe
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
        self.tank3 = Sprzet(
            id=3,
            nazwa_unikalna='B2A',
            typ_sprzetu='beczka_czysta',
            ipomiar_device_id='device-003',
            pojemnosc_tony=None  # Bez pojemności
        )
        
        db.session.add_all([self.tank1, self.tank2, self.tank3])
        db.session.commit()
        
        # Utwórz punkty kalibracyjne dla tank1 (na podstawie b8c.csv)
        # Przykładowe dane: 1T->262cm, 2T->263cm, 3T->265cm
        calibration_points_tank1 = [
            TankCalibrationPoint(
                id_sprzetu=1,
                odczyt_mm=Decimal('2620'),  # 262 cm
                waga_tony=Decimal('1.0')
            ),
            TankCalibrationPoint(
                id_sprzetu=1,
                odczyt_mm=Decimal('2630'),  # 263 cm
                waga_tony=Decimal('2.0')
            ),
            TankCalibrationPoint(
                id_sprzetu=1,
                odczyt_mm=Decimal('2650'),  # 265 cm
                waga_tony=Decimal('3.0')
            ),
            TankCalibrationPoint(
                id_sprzetu=1,
                odczyt_mm=Decimal('5200'),  # 520 cm (78.4T z pliku)
                waga_tony=Decimal('78.4')
            ),
        ]
        
        # Utwórz punkty kalibracyjne dla tank2 (prostsze dane)
        calibration_points_tank2 = [
            TankCalibrationPoint(
                id_sprzetu=2,
                odczyt_mm=Decimal('1000'),  # 100 cm
                waga_tony=Decimal('1.0')
            ),
            TankCalibrationPoint(
                id_sprzetu=2,
                odczyt_mm=Decimal('2000'),  # 200 cm
                waga_tony=Decimal('2.0')
            ),
            TankCalibrationPoint(
                id_sprzetu=2,
                odczyt_mm=Decimal('3000'),  # 300 cm
                waga_tony=Decimal('3.0')
            ),
        ]
        
        db.session.add_all(calibration_points_tank1 + calibration_points_tank2)
        db.session.commit()

    def test_01_convert_mm_to_tonnes_exact_match(self):
        """Test konwersji z dokładnym dopasowaniem punktu kalibracyjnego."""
        result = CalibrationService.convert_mm_to_tonnes(1, Decimal('2620'))
        self.assertIsNotNone(result)
        self.assertEqual(result, Decimal('1.0'))

    def test_02_convert_mm_to_tonnes_linear_interpolation(self):
        """Test interpolacji liniowej między punktami kalibracyjnymi."""
        # Odczyt 264cm (2640mm) jest między 263cm (2T) a 265cm (3T)
        # Oczekiwany wynik: 2 + (3-2) * (2640-2630) / (2650-2630) = 2 + 10/20 = 2.5T
        result = CalibrationService.convert_mm_to_tonnes(1, Decimal('2640'))
        self.assertIsNotNone(result)
        self.assertAlmostEqual(float(result), 2.5, places=2)

    def test_03_convert_mm_to_tonnes_no_calibration_returns_none(self):
        """Test zwracania None gdy zbiornik nie ma kalibracji."""
        result = CalibrationService.convert_mm_to_tonnes(3, Decimal('1000'))
        self.assertIsNone(result)

    def test_04_convert_mm_to_tonnes_below_range(self):
        """Test obsługi odczytu poniżej zakresu kalibracji."""
        # Odczyt poniżej pierwszego punktu (2620mm = 1T)
        result = CalibrationService.convert_mm_to_tonnes(1, Decimal('2500'))
        # Zgodnie z implementacją: jeśli pierwszy punkt ma wagę <= 0.1T, zwraca tę wagę, w przeciwnym razie None
        # W naszym przypadku pierwszy punkt to 1T, więc powinien zwrócić None
        self.assertIsNone(result)

    def test_05_convert_mm_to_tonnes_above_range_within_capacity(self):
        """Test obsługi odczytu powyżej zakresu ale w pojemności zbiornika."""
        # Odczyt powyżej ostatniego punktu (5200mm = 78.4T)
        # Ostatni punkt ma wagę 78.4T, która jest równa pojemności zbiornika (78.4T)
        # Zgodnie z implementacją: jeśli max_waga >= pojemnosc_tony, zwraca max_waga
        result = CalibrationService.convert_mm_to_tonnes(1, Decimal('5300'))
        # Powinien zwrócić wartość z ostatniego punktu (78.4T) bo max_waga == pojemnosc_tony
        self.assertIsNotNone(result)
        self.assertEqual(result, Decimal('78.4'))

    def test_06_convert_mm_to_tonnes_above_capacity_returns_none(self):
        """Test że odczyt powyżej pojemności zwraca None."""
        # Odczyt powyżej pojemności (78.4T)
        result = CalibrationService.convert_mm_to_tonnes(1, Decimal('6000'))
        # Powinien zwrócić None bo brak danych kalibracyjnych dla tego zakresu
        self.assertIsNone(result)

    def test_07_get_calibration_points(self):
        """Test pobierania wszystkich punktów kalibracyjnych dla zbiornika."""
        points = CalibrationService.get_calibration_points(1)
        self.assertEqual(len(points), 4)
        self.assertEqual(points[0]['tona'], 1.0)
        self.assertEqual(points[0]['cm'], 262.0)
        self.assertEqual(points[0]['mm'], 2620.0)

    def test_08_get_calibration_points_empty(self):
        """Test pobierania punktów dla zbiornika bez kalibracji."""
        points = CalibrationService.get_calibration_points(3)
        self.assertEqual(len(points), 0)

    def test_09_add_calibration_point(self):
        """Test dodawania nowego punktu kalibracyjnego."""
        point = CalibrationService.add_calibration_point(
            sprzet_id=3,
            odczyt_mm=Decimal('1500'),
            waga_tony=Decimal('5.0')
        )
        db.session.commit()
        
        self.assertIsNotNone(point.id)
        self.assertEqual(point.id_sprzetu, 3)
        self.assertEqual(point.odczyt_mm, Decimal('1500'))
        self.assertEqual(point.waga_tony, Decimal('5.0'))
        
        # Sprawdź czy punkt został zapisany
        points = CalibrationService.get_calibration_points(3)
        self.assertEqual(len(points), 1)

    def test_10_add_calibration_point_duplicate_updates_existing(self):
        """Test że dodanie punktu z tym samym odczyt_mm aktualizuje istniejący."""
        # Dodaj pierwszy punkt
        point1 = CalibrationService.add_calibration_point(
            sprzet_id=3,
            odczyt_mm=Decimal('1500'),
            waga_tony=Decimal('5.0')
        )
        db.session.commit()
        
        # Dodaj punkt z tym samym odczyt_mm ale inną wagą
        point2 = CalibrationService.add_calibration_point(
            sprzet_id=3,
            odczyt_mm=Decimal('1500'),
            waga_tony=Decimal('6.0')
        )
        db.session.commit()
        
        # Powinien być ten sam punkt, ale zaktualizowany
        self.assertEqual(point1.id, point2.id)
        self.assertEqual(point2.waga_tony, Decimal('6.0'))
        
        # Sprawdź że jest tylko jeden punkt
        points = CalibrationService.get_calibration_points(3)
        self.assertEqual(len(points), 1)

    def test_11_update_calibration_point(self):
        """Test aktualizacji istniejącego punktu kalibracyjnego."""
        # Utwórz punkt
        point = CalibrationService.add_calibration_point(
            sprzet_id=3,
            odczyt_mm=Decimal('1500'),
            waga_tony=Decimal('5.0')
        )
        db.session.commit()
        point_id = point.id
        
        # Aktualizuj punkt
        success = CalibrationService.update_calibration_point(
            point_id=point_id,
            odczyt_mm=Decimal('1600'),
            waga_tony=Decimal('6.0')
        )
        db.session.commit()
        
        self.assertTrue(success)
        
        # Sprawdź zmiany
        updated_point = db.session.get(TankCalibrationPoint, point_id)
        self.assertEqual(updated_point.odczyt_mm, Decimal('1600'))
        self.assertEqual(updated_point.waga_tony, Decimal('6.0'))

    def test_12_update_calibration_point_nonexistent_returns_false(self):
        """Test aktualizacji nieistniejącego punktu."""
        success = CalibrationService.update_calibration_point(
            point_id=99999,
            odczyt_mm=Decimal('1500'),
            waga_tony=Decimal('5.0')
        )
        self.assertFalse(success)

    def test_13_delete_calibration_point(self):
        """Test usuwania punktu kalibracyjnego."""
        # Utwórz punkt
        point = CalibrationService.add_calibration_point(
            sprzet_id=3,
            odczyt_mm=Decimal('1500'),
            waga_tony=Decimal('5.0')
        )
        db.session.commit()
        point_id = point.id
        
        # Usuń punkt
        success = CalibrationService.delete_calibration_point(point_id)
        db.session.commit()
        
        self.assertTrue(success)
        
        # Sprawdź że punkt został usunięty
        deleted_point = db.session.get(TankCalibrationPoint, point_id)
        self.assertIsNone(deleted_point)

    def test_14_delete_calibration_point_nonexistent_returns_false(self):
        """Test usuwania nieistniejącego punktu."""
        success = CalibrationService.delete_calibration_point(99999)
        self.assertFalse(success)

    def test_15_has_calibration(self):
        """Test sprawdzania czy zbiornik ma kalibrację."""
        self.assertTrue(CalibrationService.has_calibration(1))
        self.assertTrue(CalibrationService.has_calibration(2))
        self.assertFalse(CalibrationService.has_calibration(3))

    def test_16_bulk_update_calibration_points(self):
        """Test masowej aktualizacji punktów kalibracyjnych."""
        points_data = [
            {'tona': 1, 'cm': 100},
            {'tona': 2, 'cm': 200},
            {'tona': 3, 'cm': 300},
        ]
        
        result = CalibrationService.bulk_update_calibration_points(
            sprzet_id=3,
            points_data=points_data,
            pojemnosc_tony=Decimal('50.0')
        )
        db.session.commit()
        
        self.assertEqual(result['created'], 3)
        self.assertEqual(result['updated'], 0)
        self.assertEqual(result['total'], 3)
        
        # Sprawdź czy punkty zostały utworzone
        points = CalibrationService.get_calibration_points(3)
        self.assertEqual(len(points), 3)
        
        # Sprawdź czy pojemność została ustawiona
        tank = db.session.get(Sprzet, 3)
        self.assertEqual(tank.pojemnosc_tony, Decimal('50.0'))

    def test_17_bulk_update_calibration_points_updates_existing(self):
        """Test że bulk_update aktualizuje istniejące punkty."""
        # Najpierw utwórz punkt dla 1T
        CalibrationService.add_calibration_point(
            sprzet_id=3,
            odczyt_mm=Decimal('1000'),
            waga_tony=Decimal('1.0')
        )
        db.session.commit()
        
        # Teraz bulk update z nową wartością dla 1T
        points_data = [
            {'tona': 1, 'cm': 150},  # Zmieniona wartość
            {'tona': 2, 'cm': 200},
        ]
        
        result = CalibrationService.bulk_update_calibration_points(
            sprzet_id=3,
            points_data=points_data,
            pojemnosc_tony=None
        )
        db.session.commit()
        
        self.assertEqual(result['created'], 1)  # Tylko 2T jest nowy
        self.assertEqual(result['updated'], 1)  # 1T został zaktualizowany
        
        # Sprawdź czy wartość została zaktualizowana
        points = CalibrationService.get_calibration_points(3)
        point_1t = next((p for p in points if p['tona'] == 1.0), None)
        self.assertIsNotNone(point_1t)
        self.assertEqual(point_1t['cm'], 150.0)

    def test_18_bulk_update_calibration_points_skips_empty_values(self):
        """Test że bulk_update pomija puste wartości (cm <= 0)."""
        points_data = [
            {'tona': 1, 'cm': 100},
            {'tona': 2, 'cm': 0},  # Pusta wartość
            {'tona': 3, 'cm': -10},  # Ujemna wartość
            {'tona': 4, 'cm': 200},
        ]
        
        result = CalibrationService.bulk_update_calibration_points(
            sprzet_id=3,
            points_data=points_data,
            pojemnosc_tony=None
        )
        db.session.commit()
        
        # Powinny być tylko 2 punkty (1T i 4T)
        points = CalibrationService.get_calibration_points(3)
        self.assertEqual(len(points), 2)

    def test_19_convert_mm_to_tonnes_different_tanks_independent(self):
        """Test że różne zbiorniki mają niezależne kalibracje."""
        # Tank1: 2620mm = 1T
        result1 = CalibrationService.convert_mm_to_tonnes(1, Decimal('2620'))
        self.assertEqual(result1, Decimal('1.0'))
        
        # Tank2: 1000mm = 1T (inna kalibracja)
        result2 = CalibrationService.convert_mm_to_tonnes(2, Decimal('1000'))
        self.assertEqual(result2, Decimal('1.0'))
        
        # Sprawdź że ten sam odczyt mm daje różne tony dla różnych zbiorników
        # 2000mm dla tank1 (między 1T a 2T) vs tank2 (między 1T a 2T)
        result1_2000 = CalibrationService.convert_mm_to_tonnes(1, Decimal('2000'))
        result2_2000 = CalibrationService.convert_mm_to_tonnes(2, Decimal('2000'))
        # Powinny być różne bo różne kalibracje
        self.assertIsNotNone(result1_2000)
        self.assertIsNotNone(result2_2000)
        # Tank1 ma większy zakres (2620-2650mm dla 1-3T), więc 2000mm będzie poniżej zakresu
        # Tank2 ma zakres (1000-3000mm dla 1-3T), więc 2000mm będzie interpolowane
        # Więc result2_2000 powinien być między 1T a 2T
        self.assertGreater(result2_2000, Decimal('1.0'))
        self.assertLess(result2_2000, Decimal('2.0'))

    def test_20_convert_mm_to_tonnes_interpolation_edge_cases(self):
        """Test interpolacji dla przypadków brzegowych."""
        # Test interpolacji gdy odczyt jest bardzo blisko punktu
        result = CalibrationService.convert_mm_to_tonnes(1, Decimal('2621'))
        self.assertIsNotNone(result)
        self.assertGreater(result, Decimal('1.0'))
        self.assertLess(result, Decimal('2.0'))

    def test_21_convert_mm_to_tonnes_uses_tank_capacity_from_pojemnosc_tony(self):
        """Test że konwersja używa pojemnosc_tony do ograniczenia zakresu."""
        # Tank2 ma pojemność 50T, ale kalibracja tylko do 3T (3000mm)
        # Odczyt powyżej zakresu kalibracji (4000mm)
        # Zgodnie z implementacją: jeśli max_waga (3T) < pojemnosc_tony (50T), zwraca None
        result = CalibrationService.convert_mm_to_tonnes(2, Decimal('4000'))
        # Powinien zwrócić None bo max_waga (3T) < pojemnosc_tony (50T)
        self.assertIsNone(result)

    def test_22_convert_mm_to_tonnes_uses_tank_capacity_from_pojemnosc_kg(self):
        """Test że konwersja używa pojemnosc_kg/1000 jeśli pojemnosc_tony nie jest ustawiona."""
        # Tank3 nie ma pojemnosc_tony, ale możemy ustawić pojemnosc_kg
        tank3 = db.session.get(Sprzet, 3)
        tank3.pojemnosc_kg = Decimal('30000')  # 30 ton
        db.session.commit()
        
        # Dodaj kalibrację tylko do 10T
        CalibrationService.add_calibration_point(
            sprzet_id=3,
            odczyt_mm=Decimal('1000'),
            waga_tony=Decimal('10.0')
        )
        db.session.commit()
        
        # Odczyt powyżej zakresu kalibracji
        result = CalibrationService.convert_mm_to_tonnes(3, Decimal('2000'))
        # Powinien zwrócić None bo brak danych dla tego zakresu
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
