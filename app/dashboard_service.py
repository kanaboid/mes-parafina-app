# app/dashboard_service.py

from .extensions import db
from .models import Sprzet, Alarmy, TankMixes
from .batch_management_service import BatchManagementService
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from decimal import Decimal
from collections import defaultdict

class DashboardService:

    @staticmethod
    def get_main_dashboard_data(page=None, per_page=None, device_type_filter=None):
        """
        Agreguje dane dla dashboardu z opcjonalną paginacją i filtrowaniem.
        (Wersja 4: Dodana paginacja i filtrowanie)

        Args:
            page (int): Numer strony (domyślnie None - wszystkie dane)
            per_page (int): Liczba elementów na stronę (domyślnie None - wszystkie dane)
            device_type_filter (str): Filtr typu urządzeń ('reaktor', 'beczka_brudna', 'beczka_czysta', None - wszystkie)
        """
        
        # Zbuduj bazowe zapytanie
        sprzet_q = db.select(Sprzet).options(
            joinedload(Sprzet.active_mix)
        ).where(
            Sprzet.typ_sprzetu.in_(['reaktor', 'beczka_brudna', 'beczka_czysta'])
        ).order_by(Sprzet.typ_sprzetu, Sprzet.nazwa_unikalna)

        # Sprawdź czy potrzebna jest paginacja
        if page is not None and per_page is not None:
            # Użyj paginate dla SQLAlchemy 2.0
            paginated_result = db.paginate(sprzet_q, page=page, per_page=per_page)
            wszystkie_urzadzenia = paginated_result.items
            # Dodaj informacje o paginacji do odpowiedzi
            pagination_info = {
                'page': paginated_result.page,
                'per_page': paginated_result.per_page,
                'total': paginated_result.total,
                'pages': paginated_result.pages,
                'has_next': paginated_result.has_next,
                'has_prev': paginated_result.has_prev
            }
        else:
            # Pobierz wszystkie dane (stary sposób)
            wszystkie_urzadzenia = db.session.execute(sprzet_q).scalars().unique().all()
            pagination_info = None

        reaktory_w_procesie_data = []
        reaktory_puste_data = []
        beczki_brudne_data = []
        beczki_czyste_data = []

        for sprzet in wszystkie_urzadzenia:
            sprzet_data = {
                "id": sprzet.id,
                "nazwa": sprzet.nazwa_unikalna,
                "stan_sprzetu": sprzet.stan_sprzetu,
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
                if sprzet.active_mix:
                    reaktory_w_procesie_data.append(sprzet_data)
                else:
                    reaktory_puste_data.append(sprzet_data)
            elif sprzet.typ_sprzetu == 'beczka_brudna':
                beczki_brudne_data.append(sprzet_data)
            elif sprzet.typ_sprzetu == 'beczka_czysta':
                beczki_czyste_data.append(sprzet_data)

        stock_summary = defaultdict(lambda: {'brudny': Decimal('0.0'), 'czysty': Decimal('0.0')})

        for beczka in beczki_brudne_data:
            if beczka.get('partia') and beczka['partia'].get('sklad'):
                for material_info in beczka['partia']['sklad']:
                    mat_type = material_info['material_type']
                    mat_quantity = Decimal(material_info.get('total_quantity', '0.0'))
                    stock_summary[mat_type]['brudny'] += mat_quantity

        for beczka in beczki_czyste_data:
            if beczka.get('partia') and beczka['partia'].get('sklad'):
                for material_info in beczka['partia']['sklad']:
                    mat_type = material_info['material_type']
                    mat_quantity = Decimal(material_info.get('total_quantity', '0.0'))
                    stock_summary[mat_type]['czysty'] += mat_quantity
        
        stock_summary_list = sorted([
            {'material_type': k, 'dirty_stock_kg': float(v['brudny']), 'clean_stock_kg': float(v['czysty'])}
            for k, v in stock_summary.items()
        ], key=lambda x: x['material_type'])
        
        alarmy_q = db.select(Alarmy).where(Alarmy.status_alarmu == 'AKTYWNY').order_by(Alarmy.czas_wystapienia.desc()).limit(5)
        alarmy = db.session.execute(alarmy_q).scalars().all()
        alarmy_data = [{ "id": a.id, "typ": a.typ_alarmu, "sprzet": a.nazwa_sprzetu, "wartosc": float(a.wartosc), "limit": float(a.limit_przekroczenia), "czas": a.czas_wystapienia.isoformat() + 'Z' } for a in alarmy]

        result = {
            "reaktory_w_procesie": reaktory_w_procesie_data,
            "reaktory_puste": reaktory_puste_data,
            "beczki_brudne": beczki_brudne_data,
            "beczki_czyste": beczki_czyste_data,
            "alarmy": alarmy_data,
            "stock_summary": stock_summary_list
        }

        # Dodaj informacje o paginacji jeśli dostępne
        if pagination_info is not None:
            result["pagination"] = pagination_info

        return result