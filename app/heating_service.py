# app/heating_service.py
from datetime import datetime, timezone
from .extensions import db
from .models import Sprzet, TankMixes, HistoriaPodgrzewania, MixComponents
from sqlalchemy import select, func
from decimal import Decimal

class HeatingService:
    @staticmethod
    def start_heating_log(reaktor: Sprzet, mix: TankMixes):
        """Tworzy nowy, niekompletny wpis w historii podgrzewania."""
        
        # Oblicz aktualną wagę wsadu
        total_weight = db.session.query(func.sum(MixComponents.quantity_in_mix)).filter_by(mix_id=mix.id).scalar() or Decimal('0.0')

        log_entry = HistoriaPodgrzewania(
            id_sprzetu=reaktor.id,
            id_mieszaniny=mix.id,
            czas_startu=datetime.now(timezone.utc),
            temp_startowa=reaktor.temperatura_aktualna,
            waga_wsadu=total_weight
            # temperatura_zewnetrzna zostanie dodana w przyszłości
        )
        db.session.add(log_entry)
        # Commit zostanie wykonany w serwisie nadrzędnym (SprzetService)

    @staticmethod
    def end_heating_log(reaktor: Sprzet):
        """Znajduje ostatni aktywny wpis i uzupełnia go o dane końcowe."""
        
        # Znajdź ostatni otwarty wpis dla tego reaktora
        log_entry_to_close = db.session.execute(
            select(HistoriaPodgrzewania)
            .filter_by(id_sprzetu=reaktor.id, czas_konca=None)
            .order_by(HistoriaPodgrzewania.czas_startu.desc())
        ).scalars().first()

        if log_entry_to_close:
            log_entry_to_close.czas_konca = datetime.now(timezone.utc)
            log_entry_to_close.temp_koncowa = reaktor.temperatura_aktualna
            # Commit zostanie wykonany w serwisie nadrzędnym (SprzetService)
        else:
            # Sytuacja, w której palnik jest wyłączany bez aktywnego logu
            # - nic nie rób, ewentualnie dodaj logowanie ostrzeżenia
            print(f"WARNING: Wyłączono palnik dla {reaktor.nazwa_unikalna}, ale nie znaleziono aktywnego cyklu grzania do zamknięcia.")