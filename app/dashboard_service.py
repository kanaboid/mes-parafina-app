# app/dashboard_service.py

from .extensions import db
from .models import Sprzet, PartieSurowca, Alarmy
from sqlalchemy import func
from app.batch_management_service import BatchManagementService
from collections import defaultdict


class DashboardService:

    @staticmethod
    def get_main_dashboard_data():
        """
        Agreguje wszystkie dane potrzebne do wyświetlenia głównego dashboardu.
        """
        
        # 1. Pobierz dane o reaktorach z ich partiami (nowy system mieszanin)
        # To zapytanie jest bardziej złożone, więc użyjemy ORM
        reaktory_q = db.select(Sprzet).where(Sprzet.typ_sprzetu == 'reaktor').order_by(Sprzet.nazwa_unikalna)
        reaktory = db.session.execute(reaktory_q).scalars().all()
        reaktory_w_procesie_data = []
        reaktory_puste_data = []

        for reaktor in reaktory:
            reaktor_data = {
                "id": reaktor.id,
                "nazwa": reaktor.nazwa_unikalna,
                "stan_sprzetu": reaktor.stan_sprzetu,
                "temperatura_aktualna": float(reaktor.temperatura_aktualna) if reaktor.temperatura_aktualna else None,
                "temperatura_docelowa": float(reaktor.temperatura_docelowa) if reaktor.temperatura_docelowa else None,
                "cisnienie_aktualne": float(reaktor.cisnienie_aktualne) if reaktor.cisnienie_aktualne else None,
                "stan_palnika": reaktor.stan_palnika,
                "partia": None # Domyślnie brak partii
            }

            if reaktor.active_mix: # Jeśli jest aktywna mieszanina, reaktor jest "w procesie"
                mix = reaktor.active_mix
                composition = BatchManagementService.get_mix_composition(mix.id)
                waga_kg = composition.get('total_weight', 0)

                reaktor_data["partia"] = {
                    "id": mix.id, # Przekazujemy ID mieszaniny
                    "kod": mix.unique_code,
                    "typ": f"MIX ({len(composition.get('components', []))} składników)",
                    "waga_kg": float(waga_kg)
                }
                reaktory_w_procesie_data.append(reaktor_data)
            else: # Jeśli nie ma aktywnej mieszaniny, reaktor jest "pusty"
                reaktory_puste_data.append(reaktor_data)

        # 2. Pobierz dane o beczkach brudnych i czystych
        beczki_q = db.select(Sprzet).where(Sprzet.typ_sprzetu.in_(['beczka_brudna', 'beczka_czysta'])).order_by(Sprzet.nazwa_unikalna)
        beczki = db.session.execute(beczki_q).scalars().all()
        beczki_brudne_data = []
        beczki_czyste_data = []
        
        stock_summary = defaultdict(lambda: {'brudny': Decimal('0.0'), 'czysty': Decimal('0.0')})

        for beczka in beczki_brudne_data:
            if beczka.get('partia'):
                # Używamy `main_composition` z `TankMixes`, jeśli istnieje i jest słownikiem
                composition = beczka['partia'].get('sklad') # Zakładając, że `sklad` zawiera `summary_by_material`
                if composition:
                     for material_info in composition:
                        mat_type = material_info['material_type']
                        mat_quantity = Decimal(material_info['total_quantity'])
                        stock_summary[mat_type]['brudny'] += mat_quantity

        # Agregacja dla beczek czystych
        for beczka in beczki_czyste_data:
            if beczka.get('partia'):
                composition = beczka['partia'].get('sklad')
                if composition:
                    for material_info in composition:
                        mat_type = material_info['material_type']
                        mat_quantity = Decimal(material_info['total_quantity'])
                        stock_summary[mat_type]['czysty'] += mat_quantity
        
        # Konwertuj defaultdict na zwykłą listę słowników dla JSON
        stock_summary_list = [
            {'material_type': k, 'dirty_stock_kg': float(v['brudny']), 'clean_stock_kg': float(v['czysty'])}
            for k, v in stock_summary.items()
        ]


        # 3. Pobierz aktywne, niepotwierdzone alarmy
        alarmy_q = db.select(Alarmy).where(Alarmy.status_alarmu == 'AKTYWNY').order_by(Alarmy.czas_wystapienia.desc()).limit(5)
        alarmy = db.session.execute(alarmy_q).scalars().all()
        alarmy_data = [{
            "id": a.id,
            "typ": a.typ_alarmu,
            "sprzet": a.nazwa_sprzetu,
            "wartosc": float(a.wartosc),
            "limit": float(a.limit_przekroczenia),
            "czas": a.czas_wystapienia.isoformat() + 'Z' # Dodajemy Z dla UTC
        } for a in alarmy]

        return {
            "reaktory_w_procesie": reaktory_w_procesie_data, # Zmieniona nazwa klucza
            "reaktory_puste": reaktory_puste_data,       # Nowy klucz
            "beczki_brudne": beczki_brudne_data,
            "beczki_czyste": beczki_czyste_data,
            "alarmy": alarmy_data,
            "stock_summary": stock_summary_list
        }