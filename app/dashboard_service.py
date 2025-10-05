# app/dashboard_service.py

from .extensions import db
from .models import Sprzet, Alarmy, TankMixes, OperacjeLog
from .batch_management_service import BatchManagementService
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from decimal import Decimal
from collections import defaultdict

class DashboardService:

    @staticmethod
    def get_main_dashboard_data():
        """
        Agreguje wszystkie dane dla dashboardu. (Wersja 3: Poprawna konwersja na float)
        """
        
        sprzet_q = db.select(Sprzet).options(
            joinedload(Sprzet.active_mix)
        ).where(
            Sprzet.typ_sprzetu.in_(['reaktor', 'beczka_brudna', 'beczka_czysta'])
        ).order_by(Sprzet.typ_sprzetu, Sprzet.nazwa_unikalna)
        
        wszystkie_urzadzenia = db.session.execute(sprzet_q).scalars().unique().all()

        all_reactors_data = []
        beczki_brudne_data = []
        beczki_czyste_data = []

        for sprzet in wszystkie_urzadzenia:
            sprzet_data = {
                "id": sprzet.id,
                "nazwa": sprzet.nazwa_unikalna,
                "stan_sprzetu": sprzet.stan_sprzetu,
                "pojemnosc_kg": float(sprzet.pojemnosc_kg) if sprzet.pojemnosc_kg else None,
                "partia": None
            }
            if sprzet.typ_sprzetu == 'reaktor':
                sprzet_data.update({
                    "temperatura_aktualna": float(sprzet.temperatura_aktualna) if sprzet.temperatura_aktualna else None,
                    "temperatura_docelowa": float(sprzet.temperatura_docelowa) if sprzet.temperatura_docelowa else None,
                    "cisnienie_aktualne": float(sprzet.cisnienie_aktualne) if sprzet.cisnienie_aktualne else None,
                    "stan_palnika": sprzet.stan_palnika,
                    "temperatura_max": float(sprzet.temperatura_max or '120.0'),
                    "cisnienie_max": float(sprzet.cisnienie_max or '6.0')
                })

            if sprzet.active_mix:
                mix = sprzet.active_mix
                # get_mix_composition zwraca nam teraz spójne obiekty Decimal
                composition = BatchManagementService.get_mix_composition(mix.id)
                waga_kg = composition.get('total_weight', Decimal('0.0'))
                
                # Konwertujemy skład na floaty TUTAJ, tuż przed wysłaniem
                sklad_dla_api = [
                    {'material_type': item['material_type'], 'total_quantity': float(item['total_quantity'])}
                    for item in composition.get('summary_by_material', [])
                ]

                sprzet_data["partia"] = {
                    "id": mix.id,
                    "kod": mix.unique_code,
                    "waga_kg": float(waga_kg),
                    "sklad": sklad_dla_api,
                    "process_status": mix.process_status
                }
            
            if sprzet.typ_sprzetu == 'reaktor':
                all_reactors_data.append(sprzet_data)
            elif sprzet.typ_sprzetu == 'beczka_brudna':
                beczki_brudne_data.append(sprzet_data)
            elif sprzet.typ_sprzetu == 'beczka_czysta':
                beczki_czyste_data.append(sprzet_data)

        stock_summary = defaultdict(lambda: {'brudny': Decimal('0.0'), 'czysty': Decimal('0.0'), 'reaktory': Decimal('0.0')})

        for beczka in beczki_brudne_data:
            if beczka.get('partia') and beczka['partia'].get('sklad'):
                for material_info in beczka['partia']['sklad']:
                    mat_type = material_info['material_type']
                    mat_quantity = Decimal(str(material_info.get('total_quantity', '0.0'))) # Bezpieczna konwersja
                    stock_summary[mat_type]['brudny'] += mat_quantity

        for beczka in beczki_czyste_data:
            if beczka.get('partia') and beczka['partia'].get('sklad'):
                for material_info in beczka['partia']['sklad']:
                    mat_type = material_info['material_type']
                    mat_quantity = Decimal(str(material_info.get('total_quantity', '0.0'))) # Bezpieczna konwersja
                    stock_summary[mat_type]['czysty'] += mat_quantity
        
        # NOWA LOGIKA: Dodaj materiał z reaktorów do podsumowania
        for reaktor in all_reactors_data:
            if reaktor.get('partia') and reaktor['partia'].get('sklad'):
                for material_info in reaktor['partia']['sklad']:
                    mat_type = material_info['material_type']
                    mat_quantity = Decimal(str(material_info.get('total_quantity', '0.0'))) # Bezpieczna konwersja
                    stock_summary[mat_type]['reaktory'] += mat_quantity

        stock_summary_list = sorted([
            {
                'material_type': k, 
                'dirty_stock_kg': float(v['brudny']), 
                'clean_stock_kg': float(v['czysty']),
                'reactors_stock_kg': float(v['reaktory'])
            }
            for k, v in stock_summary.items()
        ], key=lambda x: x['material_type'])
        
        alarmy_q = db.select(Alarmy).where(Alarmy.status_alarmu == 'AKTYWNY').order_by(Alarmy.czas_wystapienia.desc()).limit(5)
        alarmy = db.session.execute(alarmy_q).scalars().all()
        alarmy_data = [{ "id": a.id, "typ": a.typ_alarmu, "sprzet": a.nazwa_sprzetu, "wartosc": float(a.wartosc), "limit": float(a.limit_przekroczenia), "czas": a.czas_wystapienia.isoformat() + 'Z' } for a in alarmy]

        # NOWA LOGIKA: Pobierz aktywne operacje
        active_ops_q = db.select(OperacjeLog).options(
            joinedload(OperacjeLog.sprzet_zrodlowy),
            joinedload(OperacjeLog.sprzet_docelowy)
        ).where(OperacjeLog.status_operacji == 'aktywna').order_by(OperacjeLog.czas_rozpoczecia.desc())
        
        active_ops = db.session.execute(active_ops_q).scalars().all()
        
        active_operations_data = [
            {
                "id": op.id,
                "opis": op.opis or "Transfer",
                "zrodlo": op.sprzet_zrodlowy.nazwa_unikalna if op.sprzet_zrodlowy else 'System',
                "cel": op.sprzet_docelowy.nazwa_unikalna if op.sprzet_docelowy else 'System',
                "czas_rozpoczecia": op.czas_rozpoczecia.isoformat() + 'Z' if op.czas_rozpoczecia else 'N/A'
            } for op in active_ops
        ]

        return {
            "all_reactors": all_reactors_data,
            "beczki_brudne": beczki_brudne_data,
            "beczki_czyste": beczki_czyste_data,
            "alarmy": alarmy_data,
            "stock_summary": stock_summary_list,
            "active_operations": active_operations_data
        }