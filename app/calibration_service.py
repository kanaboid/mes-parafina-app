# app/calibration_service.py

from .extensions import db
from .models import TankCalibrationPoint, Sprzet
from sqlalchemy import select, func
from decimal import Decimal
from typing import Optional, List, Dict
from flask import current_app


class CalibrationService:
    """
    Serwis do zarządzania kalibracją zbiorników i konwersji mm -> tony.
    Wszystkie operacje działają per-zbiornik (wymagają sprzet_id).
    """
    
    @staticmethod
    def convert_mm_to_tonnes(sprzet_id: int, odczyt_mm: Decimal) -> Optional[Decimal]:
        """
        Konwertuje odczyt w mm na tony dla KONKRETNEGO zbiornika.
        Używa najbliższego punktu kalibracyjnego lub interpolacji liniowej.
        
        :param sprzet_id: ID zbiornika (Sprzet.id)
        :param odczyt_mm: Odczyt z czujnika w mm
        :return: Waga w tonach lub None jeśli brak kalibracji dla tego zbiornika
        """
        # Pobierz wszystkie punkty kalibracyjne TYLKO dla tego zbiornika
        points = db.session.execute(
            select(TankCalibrationPoint)
            .where(TankCalibrationPoint.id_sprzetu == sprzet_id)
            .order_by(TankCalibrationPoint.odczyt_mm)
        ).scalars().all()
        
        if not points:
            return None  # Brak kalibracji dla tego zbiornika
        
        # Sprawdź dokładne dopasowanie
        for point in points:
            if point.odczyt_mm == odczyt_mm:
                return point.waga_tony
        
        # Znajdź dwa najbliższe punkty do interpolacji
        point_lower = None
        point_upper = None
        
        for i, point in enumerate(points):
            if point.odczyt_mm < odczyt_mm:
                point_lower = point
            elif point.odczyt_mm > odczyt_mm:
                point_upper = point
                break
        
        # Interpolacja liniowa między punktami
        if point_lower and point_upper:
            # Wzór interpolacji liniowej: y = y1 + (y2 - y1) * (x - x1) / (x2 - x1)
            x = odczyt_mm
            x1 = point_lower.odczyt_mm
            x2 = point_upper.odczyt_mm
            y1 = point_lower.waga_tony
            y2 = point_upper.waga_tony
            
            if x2 - x1 == 0:
                return y1  # Unikaj dzielenia przez zero
            
            waga_tony = y1 + (y2 - y1) * (x - x1) / (x2 - x1)
            return round(waga_tony, 3)
        
        # Ekstrapolacja (poza zakresem) - ZABEZPIECZENIE
        # Sprawdź pojemność zbiornika
        sprzet = db.session.get(Sprzet, sprzet_id)
        pojemnosc_tony = None
        if sprzet:
            if sprzet.pojemnosc_tony:
                pojemnosc_tony = sprzet.pojemnosc_tony
            elif sprzet.pojemnosc_kg:
                pojemnosc_tony = sprzet.pojemnosc_kg / Decimal('1000')
        
        if odczyt_mm < points[0].odczyt_mm:
            # Poniżej zakresu - zwróć wartość z pierwszego punktu lub None
            return points[0].waga_tony if points[0].waga_tony <= Decimal('0.1') else None
        
        if odczyt_mm > points[-1].odczyt_mm:
            # Powyżej zakresu
            max_waga = points[-1].waga_tony
            if pojemnosc_tony and max_waga >= pojemnosc_tony:
                # Kalibracja sięga do pojemności - zwróć wartość z ostatniego punktu
                return max_waga
            else:
                # Brak danych kalibracyjnych dla tego zakresu
                return None
        
        return None
    
    @staticmethod
    def get_calibration_points(sprzet_id: int) -> List[Dict]:
        """
        Pobiera wszystkie punkty kalibracyjne dla KONKRETNEGO zbiornika.
        
        :param sprzet_id: ID zbiornika
        :return: Lista słowników z danymi punktów kalibracyjnych
        """
        points = db.session.execute(
            select(TankCalibrationPoint)
            .where(TankCalibrationPoint.id_sprzetu == sprzet_id)
            .order_by(TankCalibrationPoint.waga_tony)
        ).scalars().all()
        
        return [
            {
                'id': p.id,
                'tona': float(p.waga_tony),
                'cm': float(p.odczyt_mm / Decimal('10')),
                'mm': float(p.odczyt_mm),
                'data_kalibracji': p.data_kalibracji.isoformat() if p.data_kalibracji else None,
                'uwagi': p.uwagi
            }
            for p in points
        ]
    
    @staticmethod
    def add_calibration_point(sprzet_id: int, odczyt_mm: Decimal, waga_tony: Decimal, 
                             data_kalibracji=None, uwagi: Optional[str] = None) -> TankCalibrationPoint:
        """
        Dodaje punkt kalibracyjny dla KONKRETNEGO zbiornika.
        
        :param sprzet_id: ID zbiornika
        :param odczyt_mm: Odczyt w mm
        :param waga_tony: Waga w tonach
        :param data_kalibracji: Opcjonalna data kalibracji
        :param uwagi: Opcjonalne uwagi
        :return: Utworzony punkt kalibracyjny
        """
        # Sprawdź czy punkt już istnieje
        existing = db.session.execute(
            select(TankCalibrationPoint)
            .where(
                TankCalibrationPoint.id_sprzetu == sprzet_id,
                TankCalibrationPoint.odczyt_mm == odczyt_mm
            )
        ).scalar_one_or_none()
        
        if existing:
            # Aktualizuj istniejący punkt
            existing.waga_tony = waga_tony
            if data_kalibracji:
                existing.data_kalibracji = data_kalibracji
            if uwagi is not None:
                existing.uwagi = uwagi
            return existing
        
        # Utwórz nowy punkt
        point = TankCalibrationPoint(
            id_sprzetu=sprzet_id,
            odczyt_mm=odczyt_mm,
            waga_tony=waga_tony,
            data_kalibracji=data_kalibracji,
            uwagi=uwagi
        )
        db.session.add(point)
        return point
    
    @staticmethod
    def update_calibration_point(point_id: int, odczyt_mm: Decimal, waga_tony: Decimal,
                                data_kalibracji=None, uwagi: Optional[str] = None) -> bool:
        """
        Aktualizuje punkt kalibracyjny.
        
        :param point_id: ID punktu kalibracyjnego
        :param odczyt_mm: Nowy odczyt w mm
        :param waga_tony: Nowa waga w tonach
        :param data_kalibracji: Opcjonalna data kalibracji
        :param uwagi: Opcjonalne uwagi
        :return: True jeśli sukces, False jeśli punkt nie istnieje
        """
        point = db.session.get(TankCalibrationPoint, point_id)
        if not point:
            return False
        
        # Sprawdź czy nowy odczyt_mm nie koliduje z innym punktem dla tego samego zbiornika
        if point.odczyt_mm != odczyt_mm:
            existing = db.session.execute(
                select(TankCalibrationPoint)
                .where(
                    TankCalibrationPoint.id_sprzetu == point.id_sprzetu,
                    TankCalibrationPoint.odczyt_mm == odczyt_mm,
                    TankCalibrationPoint.id != point_id
                )
            ).scalar_one_or_none()
            
            if existing:
                return False  # Konflikt z istniejącym punktem
        
        point.odczyt_mm = odczyt_mm
        point.waga_tony = waga_tony
        if data_kalibracji:
            point.data_kalibracji = data_kalibracji
        if uwagi is not None:
            point.uwagi = uwagi
        
        return True
    
    @staticmethod
    def delete_calibration_point(point_id: int) -> bool:
        """
        Usuwa punkt kalibracyjny.
        
        :param point_id: ID punktu kalibracyjnego
        :return: True jeśli sukces, False jeśli punkt nie istnieje
        """
        point = db.session.get(TankCalibrationPoint, point_id)
        if not point:
            return False
        
        db.session.delete(point)
        return True
    
    @staticmethod
    def has_calibration(sprzet_id: int) -> bool:
        """
        Sprawdza, czy zbiornik ma jakiekolwiek punkty kalibracyjne.
        
        :param sprzet_id: ID zbiornika
        :return: True jeśli zbiornik ma kalibrację, False w przeciwnym razie
        """
        count = db.session.execute(
            select(func.count(TankCalibrationPoint.id))
            .where(TankCalibrationPoint.id_sprzetu == sprzet_id)
        ).scalar()
        
        return count > 0
    
    @staticmethod
    def bulk_update_calibration_points(sprzet_id: int, points_data: List[Dict], pojemnosc_tony: Optional[Decimal] = None) -> Dict:
        """
        Masowe dodanie/aktualizacja punktów kalibracyjnych (dla tabeli 1-90T).
        
        :param sprzet_id: ID zbiornika
        :param points_data: Lista słowników z danymi punktów [{"tona": 1, "cm": 262}, ...]
        :param pojemnosc_tony: Opcjonalna pojemność zbiornika do ustawienia
        :return: Słownik z wynikami operacji
        """
        updated_count = 0
        created_count = 0
        
        for point_data in points_data:
            tona = Decimal(str(point_data.get('tona', 0)))
            cm = Decimal(str(point_data.get('cm', 0)))
            
            if cm <= 0:  # Pomiń puste wartości
                continue
            
            odczyt_mm = cm * Decimal('10')
            waga_tony = tona
            
            # Szukaj istniejącego punktu po waga_tony (każda tona powinna mieć jeden punkt)
            existing = db.session.execute(
                select(TankCalibrationPoint)
                .where(
                    TankCalibrationPoint.id_sprzetu == sprzet_id,
                    TankCalibrationPoint.waga_tony == waga_tony
                )
            ).scalar_one_or_none()
            
            if existing:
                # Aktualizuj istniejący punkt
                existing.odczyt_mm = odczyt_mm
                updated_count += 1
            else:
                # Sprawdź czy istnieje punkt z tym samym odczyt_mm (konflikt)
                conflict = db.session.execute(
                    select(TankCalibrationPoint)
                    .where(
                        TankCalibrationPoint.id_sprzetu == sprzet_id,
                        TankCalibrationPoint.odczyt_mm == odczyt_mm
                    )
                ).scalar_one_or_none()
                
                if conflict:
                    # Aktualizuj istniejący punkt z tym samym odczyt_mm
                    conflict.waga_tony = waga_tony
                    updated_count += 1
                else:
                    # Utwórz nowy punkt
                    point = TankCalibrationPoint(
                        id_sprzetu=sprzet_id,
                        odczyt_mm=odczyt_mm,
                        waga_tony=waga_tony
                    )
                    db.session.add(point)
                    created_count += 1
        
        # Aktualizuj pojemność zbiornika jeśli podana
        if pojemnosc_tony is not None:
            sprzet = db.session.get(Sprzet, sprzet_id)
            if sprzet:
                sprzet.pojemnosc_tony = pojemnosc_tony
        
        return {
            'created': created_count,
            'updated': updated_count,
            'total': len(points_data)
        }
