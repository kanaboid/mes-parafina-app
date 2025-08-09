# app/models.py
from . import db # Importujemy obiekt `db` z __init__.py
import decimal
import datetime
from typing import Optional, List
from sqlalchemy.dialects.mysql import ENUM
from sqlalchemy import (
    DECIMAL, DateTime, ForeignKeyConstraint, Index, Integer, JSON, String,
    Table, Text, TIMESTAMP, text, VARCHAR, ForeignKey, func
)
from sqlalchemy.dialects.mysql import ENUM, TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship


# Definiujemy tabelę `sprzet` jako klasę Pythona
class Alarmy(db.Model):
    __tablename__ = 'alarmy'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    typ_alarmu: Mapped[str] = mapped_column(ENUM('TEMPERATURA', 'CISNIENIE', 'POZIOM', 'SYSTEM'))
    nazwa_sprzetu: Mapped[str] = mapped_column(VARCHAR(100))
    wartosc: Mapped[decimal.Decimal] = mapped_column(DECIMAL(10, 2))
    limit_przekroczenia: Mapped[decimal.Decimal] = mapped_column(DECIMAL(10, 2))
    czas_wystapienia: Mapped[datetime.datetime] = mapped_column(DateTime)
    status_alarmu: Mapped[Optional[str]] = mapped_column(ENUM('AKTYWNY', 'POTWIERDZONY', 'ZAKONCZONY'), server_default=text("'AKTYWNY'"))
    czas_potwierdzenia: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    czas_zakonczenia: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    komentarz: Mapped[Optional[str]] = mapped_column(Text)


class PathfinderTestHistory(db.Model):
    __tablename__ = 'pathfinder_test_history'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    test_type: Mapped[str] = mapped_column(VARCHAR(50))
    start_point: Mapped[Optional[str]] = mapped_column(VARCHAR(100))
    end_point: Mapped[Optional[str]] = mapped_column(VARCHAR(100))
    test_parameters: Mapped[Optional[dict]] = mapped_column(JSON)
    result: Mapped[Optional[dict]] = mapped_column(JSON)
    success: Mapped[Optional[int]] = mapped_column(TINYINT(1))
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('CURRENT_TIMESTAMP'))


class Sprzet(db.Model):
    __tablename__ = 'sprzet'
    __table_args__ = (
        Index('nazwa_unikalna', 'nazwa_unikalna', unique=True),
        {'comment': 'Lista całego sprzętu produkcyjnego i magazynowego'}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uwagi_serwisowe: Mapped[Optional[str]] = mapped_column(Text)
    nazwa_unikalna: Mapped[str] = mapped_column(VARCHAR(20), comment='Np. R1, FZ, B1b, B7c')
    typ_sprzetu: Mapped[Optional[str]] = mapped_column(ENUM('reaktor', 'filtr', 'beczka_brudna', 'beczka_czysta', 'apollo', 'magazyn', 'cysterna', 'mauzer'))
    pojemnosc_kg: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(10, 2))
    stan_sprzetu: Mapped[Optional[str]] = mapped_column(VARCHAR(50), comment='Np. Pusty, W koło, Przelew, Dmuchanie filtra')
    temperatura_aktualna: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(5, 2))
    cisnienie_aktualne: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(5, 2))
    poziom_aktualny_procent: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(5, 2))
    ostatnia_aktualizacja: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    temperatura_max: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(5, 2), server_default=text("'120.00'"))
    cisnienie_max: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(5, 2), server_default=text("'6.00'"))
    id_partii_surowca: Mapped[Optional[int]] = mapped_column(Integer)
    temperatura_docelowa: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(5, 2), comment='Temperatura zadana przez operatora')
    szybkosc_topnienia_kg_h: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(10, 2), server_default=text("'1000.00'"), comment='Szacowana szybkość topnienia surowca w kg na godzinę')

    apollo_sesje: Mapped[List['ApolloSesje']] = relationship('ApolloSesje', back_populates='sprzet')
    historia_pomiarow: Mapped[List['HistoriaPomiarow']] = relationship('HistoriaPomiarow', back_populates='sprzet')
    operator_temperatures: Mapped[List['OperatorTemperatures']] = relationship('OperatorTemperatures', back_populates='sprzet')
    partie_surowca: Mapped[List['PartieSurowca']] = relationship('PartieSurowca', back_populates='sprzet')
    porty_sprzetu: Mapped[List['PortySprzetu']] = relationship('PortySprzetu', back_populates='sprzet')
    operacje_docelowe: Mapped[List['OperacjeLog']] = relationship(foreign_keys='OperacjeLog.id_sprzetu_docelowego', back_populates='sprzet_docelowy')
    operacje_zrodlowe: Mapped[List['OperacjeLog']] = relationship(foreign_keys='OperacjeLog.id_sprzetu_zrodlowego', back_populates='sprzet_zrodlowy')
    active_mix: Mapped[Optional['TankMixes']] = relationship(back_populates='tank')
def __repr__(self):
        # Ta metoda pomaga w debugowaniu, ładnie wyświetlając obiekt
        return f"<Sprzet id={self.id} nazwa='{self.nazwa_unikalna}'>"

class Statusy(db.Model):
    __tablename__ = 'statusy'
    __table_args__ = (
        Index('nazwa_statusu', 'nazwa_statusu', unique=True),
        {'comment': 'Słownik możliwych statusów partii surowca'}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nazwa_statusu: Mapped[str] = mapped_column(VARCHAR(50), comment='Np. Surowy, Filtrowany, Dobielony, Wydmuch')

    partie_statusy: Mapped[List['PartieStatusy']] = relationship('PartieStatusy', back_populates='statusy')


class StatusyPartii(db.Model):
    __tablename__ = 'statusy_partii'
    __table_args__ = (
        Index('nazwa_statusu', 'nazwa_statusu', unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nazwa_statusu: Mapped[str] = mapped_column(String(50))
    opis: Mapped[Optional[str]] = mapped_column(Text)


class TypySurowca(db.Model):
    __tablename__ = 'typy_surowca'
    __table_args__ = (
        Index('nazwa', 'nazwa', unique=True),
        {'comment': 'Słownik typów surowca'}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nazwa: Mapped[str] = mapped_column(VARCHAR(50))
    opis: Mapped[Optional[str]] = mapped_column(VARCHAR(255))


class WezlyRurociagu(db.Model):
    __tablename__ = 'wezly_rurociagu'
    __table_args__ = (
        Index('nazwa_wezla', 'nazwa_wezla', unique=True),
        {'comment': 'Punkty łączeniowe w rurociągu (trójniki, kolektory)'}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nazwa_wezla: Mapped[str] = mapped_column(VARCHAR(50))

    segmenty: Mapped[List['Segmenty']] = relationship('Segmenty', foreign_keys='[Segmenty.id_wezla_koncowego]', back_populates='wezly_rurociagu')
    segmenty_: Mapped[List['Segmenty']] = relationship('Segmenty', foreign_keys='[Segmenty.id_wezla_startowego]', back_populates='wezly_rurociagu_')


class Zawory(db.Model):
    __tablename__ = 'zawory'
    __table_args__ = (
        Index('nazwa_zaworu', 'nazwa_zaworu', unique=True),
        {'comment': 'Lista zaworów sterujących przepływem'}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stan: Mapped[str] = mapped_column(ENUM('OTWARTY', 'ZAMKNIETY'), server_default=text("'ZAMKNIETY'"))
    nazwa_zaworu: Mapped[Optional[str]] = mapped_column(String(80, 'utf8mb4_unicode_ci'))

    segmenty: Mapped[List['Segmenty']] = relationship('Segmenty', back_populates='zawory')


class ApolloSesje(db.Model):
    __tablename__ = 'apollo_sesje'
    __table_args__ = (
        ForeignKeyConstraint(['id_sprzetu'], ['sprzet.id'], name='apollo_sesje_ibfk_1'),
        Index('id_sprzetu', 'id_sprzetu')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_sprzetu: Mapped[int] = mapped_column(Integer)
    typ_surowca: Mapped[str] = mapped_column(String(255, 'utf8mb4_unicode_ci'))
    status_sesji: Mapped[str] = mapped_column(ENUM('aktywna', 'zakonczona'), server_default=text("'aktywna'"))
    czas_rozpoczecia: Mapped[datetime.datetime] = mapped_column(DateTime)
    czas_zakonczenia: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    rozpoczeta_przez: Mapped[Optional[str]] = mapped_column(String(255, 'utf8mb4_unicode_ci'))
    uwagi: Mapped[Optional[str]] = mapped_column(Text(collation='utf8mb4_unicode_ci'))

    sprzet: Mapped['Sprzet'] = relationship('Sprzet', back_populates='apollo_sesje')
    operacje_log: Mapped[List['OperacjeLog']] = relationship('OperacjeLog', back_populates='apollo_sesje')
    apollo_tracking: Mapped[List['ApolloTracking']] = relationship('ApolloTracking', back_populates='apollo_sesje')


class HistoriaPomiarow(db.Model):
    __tablename__ = 'historia_pomiarow'
    __table_args__ = (
        ForeignKeyConstraint(['id_sprzetu'], ['sprzet.id'], name='historia_pomiarow_ibfk_1'),
        Index('idx_historia_sprzet_czas', 'id_sprzetu', 'czas_pomiaru')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_sprzetu: Mapped[int] = mapped_column(Integer)
    czas_pomiaru: Mapped[datetime.datetime] = mapped_column(DateTime)
    temperatura: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(5, 2))
    cisnienie: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(5, 2))

    sprzet: Mapped['Sprzet'] = relationship('Sprzet', back_populates='historia_pomiarow')


class OperatorTemperatures(db.Model):
    __tablename__ = 'operator_temperatures'
    __table_args__ = (
        ForeignKeyConstraint(['id_sprzetu'], ['sprzet.id'], name='operator_temperatures_ibfk_1'),
        Index('id_sprzetu', 'id_sprzetu')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_sprzetu: Mapped[int] = mapped_column(Integer)
    temperatura: Mapped[decimal.Decimal] = mapped_column(DECIMAL(5, 2))
    czas_ustawienia: Mapped[datetime.datetime] = mapped_column(DateTime)

    sprzet: Mapped['Sprzet'] = relationship('Sprzet', back_populates='operator_temperatures')


class PartieSurowca(db.Model):
    __tablename__ = 'partie_surowca'
    __table_args__ = (
        ForeignKeyConstraint(['id_sprzetu'], ['sprzet.id'], ondelete='SET NULL', name='partie_surowca_ibfk_1'),
        Index('id_sprzetu', 'id_sprzetu'),
        Index('idx_etap_procesu', 'etap_procesu'),
        Index('idx_typ_transformacji', 'typ_transformacji'),
        Index('nazwa_partii', 'nazwa_partii', unique=True),
        Index('unikalny_kod', 'unikalny_kod', unique=True),
        {'comment': 'Każdy wiersz to unikalna partia produkcyjna surowca'}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unikalny_kod: Mapped[str] = mapped_column(VARCHAR(50), comment='Identyfikator partii, np. T10-20231027-1430-APOLLO')
    zrodlo_pochodzenia: Mapped[str] = mapped_column(ENUM('apollo', 'cysterna'))
    waga_poczatkowa_kg: Mapped[decimal.Decimal] = mapped_column(DECIMAL(10, 2))
    nazwa_partii: Mapped[str] = mapped_column(VARCHAR(100))
    status_partii: Mapped[str] = mapped_column(ENUM('W magazynie brudnym', 'Surowy w reaktorze', 'Budowanie placka', 'Przelewanie', 'Filtrowanie', 'Oczekiwanie na ocenę', 'Do ponownej filtracji', 'Dobielanie', 'Gotowy do wysłania', 'W magazynie czystym', 'Archiwalna'))
    typ_surowca: Mapped[Optional[str]] = mapped_column(VARCHAR(50))
    waga_aktualna_kg: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(10, 2))
    data_utworzenia: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))
    id_sprzetu: Mapped[Optional[int]] = mapped_column(Integer)
    rodzaj_surowca: Mapped[Optional[str]] = mapped_column(VARCHAR(50))
    id_aktualnego_sprzetu: Mapped[Optional[int]] = mapped_column(Integer)
    aktualny_etap_procesu: Mapped[Optional[str]] = mapped_column(ENUM('surowy', 'placek', 'przelew', 'w_kole', 'ocena_probki', 'dmuchanie', 'gotowy', 'wydmuch'), server_default=text("'surowy'"))
    numer_cyklu_aktualnego: Mapped[Optional[int]] = mapped_column(Integer, server_default=text("'0'"))
    czas_rozpoczecia_etapu: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    planowany_czas_zakonczenia: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    id_aktualnego_filtra: Mapped[Optional[str]] = mapped_column(VARCHAR(10))
    reaktor_docelowy: Mapped[Optional[str]] = mapped_column(VARCHAR(10))
    ilosc_cykli_filtracyjnych: Mapped[Optional[int]] = mapped_column(Integer, server_default=text("'0'"))
    historia_operacji: Mapped[Optional[dict]] = mapped_column(JSON)
    typ_transformacji: Mapped[Optional[str]] = mapped_column(ENUM('NOWA', 'TRANSFER', 'FILTRACJA', 'MIESZANIE', 'DZIELENIE'), server_default=text("'NOWA'"))
    etap_procesu: Mapped[Optional[str]] = mapped_column(ENUM('SUROWA', 'W_PROCESIE', 'FILTROWANA', 'GOTOWA', 'ZATWIERDZONA', 'ODRZUCONA'), server_default=text("'SUROWA'"))
    pochodzenie_opis: Mapped[Optional[str]] = mapped_column(Text)
    data_ostatniej_modyfikacji: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    utworzona_przez: Mapped[Optional[str]] = mapped_column(VARCHAR(100))
    certyfikat_jakosci: Mapped[Optional[str]] = mapped_column(Text)
    uwagi_operatora: Mapped[Optional[str]] = mapped_column(Text)

    sprzet: Mapped[Optional['Sprzet']] = relationship('Sprzet', back_populates='partie_surowca')
    cykle_filtracyjne: Mapped[List['CykleFiltracyjne']] = relationship('CykleFiltracyjne', back_populates='partie_surowca')
    operacje_log: Mapped[List['OperacjeLog']] = relationship('OperacjeLog', back_populates='partie_surowca')
    partie_probki: Mapped[List['PartieProbki']] = relationship('PartieProbki', back_populates='partie_surowca')
    partie_skladniki: Mapped[List['PartieSkladniki']] = relationship('PartieSkladniki', foreign_keys='[PartieSkladniki.id_partii_skladowej]', back_populates='partie_surowca')
    partie_skladniki_: Mapped[List['PartieSkladniki']] = relationship('PartieSkladniki', foreign_keys='[PartieSkladniki.id_partii_wynikowej]', back_populates='partie_surowca_')
    partie_statusy: Mapped[List['PartieStatusy']] = relationship('PartieStatusy', back_populates='partie_surowca')
    partie_historia: Mapped[List['PartieHistoria']] = relationship('PartieHistoria', back_populates='partie_surowca')
    partie_powiazania: Mapped[List['PartiePowiazania']] = relationship('PartiePowiazania', foreign_keys='[PartiePowiazania.partia_docelowa_id]', back_populates='partia_docelowa')
    partie_powiazania_: Mapped[List['PartiePowiazania']] = relationship('PartiePowiazania', foreign_keys='[PartiePowiazania.partia_zrodlowa_id]', back_populates='partia_zrodlowa')
    probki_ocena: Mapped[List['ProbkiOcena']] = relationship('ProbkiOcena', back_populates='partie_surowca')


class PortySprzetu(db.Model):
    __tablename__ = 'porty_sprzetu'
    __table_args__ = (
        ForeignKeyConstraint(['id_sprzetu'], ['sprzet.id'], ondelete='CASCADE', name='porty_sprzetu_ibfk_1'),
        Index('id_sprzetu', 'id_sprzetu'),
        Index('nazwa_portu', 'nazwa_portu', unique=True),
        {'comment': 'Punkty wejściowe/wyjściowe na sprzęcie (reaktorach, filtrach)'}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_sprzetu: Mapped[int] = mapped_column(Integer)
    nazwa_portu: Mapped[str] = mapped_column(VARCHAR(50))
    typ_portu: Mapped[str] = mapped_column(ENUM('IN', 'OUT'))

    sprzet: Mapped['Sprzet'] = relationship('Sprzet', back_populates='porty_sprzetu')
    segmenty: Mapped[List['Segmenty']] = relationship('Segmenty', foreign_keys='[Segmenty.id_portu_koncowego]', back_populates='porty_sprzetu')
    segmenty_: Mapped[List['Segmenty']] = relationship('Segmenty', foreign_keys='[Segmenty.id_portu_startowego]', back_populates='porty_sprzetu_')


class CykleFiltracyjne(db.Model):
    __tablename__ = 'cykle_filtracyjne'
    __table_args__ = (
        ForeignKeyConstraint(['id_partii'], ['partie_surowca.id'], ondelete='CASCADE', name='cykle_filtracyjne_ibfk_1'),
        Index('idx_filtr_czas', 'id_filtra', 'czas_rozpoczecia'),
        Index('idx_partia_cykl', 'id_partii', 'numer_cyklu'),
        {'comment': 'Historia wszystkich cykli filtracyjnych dla każdej partii'}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_partii: Mapped[Optional[int]] = mapped_column(Integer)
    numer_cyklu: Mapped[Optional[int]] = mapped_column(Integer)
    typ_cyklu: Mapped[Optional[str]] = mapped_column(ENUM('placek', 'filtracja', 'dmuchanie'))
    id_filtra: Mapped[Optional[str]] = mapped_column(VARCHAR(10))
    reaktor_startowy: Mapped[Optional[str]] = mapped_column(VARCHAR(10))
    reaktor_docelowy: Mapped[Optional[str]] = mapped_column(VARCHAR(10))
    czas_rozpoczecia: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    czas_zakonczenia: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    czas_trwania_minut: Mapped[Optional[int]] = mapped_column(Integer)
    wynik_oceny: Mapped[Optional[str]] = mapped_column(ENUM('pozytywna', 'negatywna', 'oczekuje'))
    komentarz: Mapped[Optional[str]] = mapped_column(Text)

    partie_surowca: Mapped[Optional['PartieSurowca']] = relationship('PartieSurowca', back_populates='cykle_filtracyjne')
    probki_ocena: Mapped[List['ProbkiOcena']] = relationship('ProbkiOcena', back_populates='cykle_filtracyjne')


class OperacjeLog(db.Model):
    __tablename__ = 'operacje_log'
    __table_args__ = (
        ForeignKeyConstraint(['id_apollo_sesji'], ['apollo_sesje.id'], name='fk_operacje_log_apollo_sesje'),
        ForeignKeyConstraint(['id_partii_surowca'], ['partie_surowca.id'], ondelete='SET NULL', name='operacje_log_ibfk_1'),
        ForeignKeyConstraint(['id_sprzetu_docelowego'], ['sprzet.id'], ondelete='SET NULL', name='operacje_log_ibfk_3'),
        ForeignKeyConstraint(['id_sprzetu_zrodlowego'], ['sprzet.id'], ondelete='SET NULL', name='operacje_log_ibfk_2'),
        Index('fk_operacje_log_apollo_sesje', 'id_apollo_sesji'),
        Index('id_partii_surowca', 'id_partii_surowca'),
        Index('id_sprzetu_docelowego', 'id_sprzetu_docelowego'),
        Index('id_sprzetu_zrodlowego', 'id_sprzetu_zrodlowego'),
        {'comment': 'Log wszystkich zdarzeń i operacji w procesie'}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    typ_operacji: Mapped[str] = mapped_column(VARCHAR(50), comment='Np. TRANSFER, DODANIE_ZIEMI, FILTRACJA_KOŁO')
    czas_rozpoczecia: Mapped[datetime.datetime] = mapped_column(DateTime)
    status_operacji: Mapped[str] = mapped_column(ENUM('aktywna', 'zakonczona', 'wstrzymana', 'anulowana'), server_default=text("'aktywna'"))
    id_partii_surowca: Mapped[Optional[int]] = mapped_column(Integer)
    id_sprzetu_zrodlowego: Mapped[Optional[int]] = mapped_column(Integer)
    id_sprzetu_docelowego: Mapped[Optional[int]] = mapped_column(Integer)
    id_apollo_sesji: Mapped[Optional[int]] = mapped_column(Integer)
    czas_zakonczenia: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    ostatnia_modyfikacja: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    zmodyfikowane_przez: Mapped[Optional[str]] = mapped_column(String(255, 'utf8mb4_unicode_ci'))
    uwagi: Mapped[Optional[str]] = mapped_column(Text(collation='utf8mb4_unicode_ci'))
    ilosc_kg: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(10, 2))
    opis: Mapped[Optional[str]] = mapped_column(Text)
    punkt_startowy: Mapped[Optional[str]] = mapped_column(VARCHAR(50))
    punkt_docelowy: Mapped[Optional[str]] = mapped_column(VARCHAR(50))

    apollo_sesje: Mapped[Optional['ApolloSesje']] = relationship('ApolloSesje', back_populates='operacje_log')
    partie_surowca: Mapped[Optional['PartieSurowca']] = relationship('PartieSurowca', back_populates='operacje_log')
    sprzet_docelowy: Mapped[Optional['Sprzet']] = relationship(foreign_keys=[id_sprzetu_docelowego], back_populates='operacje_docelowe')
    sprzet_zrodlowy: Mapped[Optional['Sprzet']] = relationship(foreign_keys=[id_sprzetu_zrodlowego], back_populates='operacje_zrodlowe')
    segmenty: Mapped[List['Segmenty']] = relationship('Segmenty', secondary='log_uzyte_segmenty', back_populates='operacje_log')
    apollo_tracking: Mapped[List['ApolloTracking']] = relationship('ApolloTracking', back_populates='operacje_log')
    partie_historia: Mapped[List['PartieHistoria']] = relationship('PartieHistoria', back_populates='operacje_log')
    partie_powiazania: Mapped[List['PartiePowiazania']] = relationship('PartiePowiazania', back_populates='operacje_log')


class PartieProbki(db.Model):
    __tablename__ = 'partie_probki'
    __table_args__ = (
        ForeignKeyConstraint(['id_partii_surowca'], ['partie_surowca.id'], ondelete='CASCADE', name='partie_probki_ibfk_1'),
        Index('idx_data_pobrania', 'data_pobrania'),
        Index('idx_numer_probki', 'numer_probki'),
        Index('idx_partia', 'id_partii_surowca'),
        Index('idx_status', 'status_probki'),
        Index('numer_probki', 'numer_probki', unique=True)
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_partii_surowca: Mapped[int] = mapped_column(Integer)
    numer_probki: Mapped[str] = mapped_column(VARCHAR(50))
    data_pobrania: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))
    pobrana_przez: Mapped[Optional[str]] = mapped_column(VARCHAR(100))
    lokalizacja_pobrania: Mapped[Optional[str]] = mapped_column(VARCHAR(100))
    typ_probki: Mapped[Optional[str]] = mapped_column(ENUM('RUTYNOWA', 'KONTROLNA', 'REKLAMACYJNA', 'WALIDACYJNA'), server_default=text("'RUTYNOWA'"))
    status_probki: Mapped[Optional[str]] = mapped_column(ENUM('POBRANA', 'W_ANALIZIE', 'ZATWIERDZONA', 'ODRZUCONA'), server_default=text("'POBRANA'"))
    wyniki_analizy: Mapped[Optional[dict]] = mapped_column(JSON)
    data_analizy: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    analizowana_przez: Mapped[Optional[str]] = mapped_column(VARCHAR(100))
    uwagi: Mapped[Optional[str]] = mapped_column(Text)

    partie_surowca: Mapped['PartieSurowca'] = relationship('PartieSurowca', back_populates='partie_probki')


class PartieSkladniki(db.Model):
    __tablename__ = 'partie_skladniki'
    __table_args__ = (
        ForeignKeyConstraint(['id_partii_skladowej'], ['partie_surowca.id'], ondelete='RESTRICT', name='fk_partia_skladowa'),
        ForeignKeyConstraint(['id_partii_wynikowej'], ['partie_surowca.id'], ondelete='CASCADE', name='fk_partia_wynikowa'),
        Index('idx_partia_skladowa', 'id_partii_skladowej'),
        Index('idx_partia_wynikowa', 'id_partii_wynikowej'),
        {'comment': 'Tabela łącząca partie-mieszaniny z ich składnikami.'}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_partii_wynikowej: Mapped[int] = mapped_column(Integer)
    id_partii_skladowej: Mapped[int] = mapped_column(Integer)
    waga_skladowa_kg: Mapped[decimal.Decimal] = mapped_column(DECIMAL(10, 2))
    data_dodania: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))

    partie_surowca: Mapped['PartieSurowca'] = relationship('PartieSurowca', foreign_keys=[id_partii_skladowej], back_populates='partie_skladniki')
    partie_surowca_: Mapped['PartieSurowca'] = relationship('PartieSurowca', foreign_keys=[id_partii_wynikowej], back_populates='partie_skladniki_')


class PartieStatusy(db.Model):
    __tablename__ = 'partie_statusy'
    __table_args__ = (
        ForeignKeyConstraint(['id_partii'], ['partie_surowca.id'], ondelete='CASCADE', name='partie_statusy_ibfk_1'),
        ForeignKeyConstraint(['id_statusu'], ['statusy.id'], ondelete='CASCADE', name='partie_statusy_ibfk_2'),
        Index('id_statusu', 'id_statusu'),
        {'comment': 'Przypisuje wiele statusów do jednej partii'}
    )

    id_partii: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_statusu: Mapped[int] = mapped_column(Integer, primary_key=True)
    data_nadania: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))

    partie_surowca: Mapped['PartieSurowca'] = relationship('PartieSurowca', back_populates='partie_statusy')
    statusy: Mapped['Statusy'] = relationship('Statusy', back_populates='partie_statusy')


class Segmenty(db.Model):
    __tablename__ = 'segmenty'
    __table_args__ = (
        ForeignKeyConstraint(['id_portu_koncowego'], ['porty_sprzetu.id'], name='segmenty_ibfk_3'),
        ForeignKeyConstraint(['id_portu_startowego'], ['porty_sprzetu.id'], name='segmenty_ibfk_1'),
        ForeignKeyConstraint(['id_wezla_koncowego'], ['wezly_rurociagu.id'], name='segmenty_ibfk_4'),
        ForeignKeyConstraint(['id_wezla_startowego'], ['wezly_rurociagu.id'], name='segmenty_ibfk_2'),
        ForeignKeyConstraint(['id_zaworu'], ['zawory.id'], name='segmenty_ibfk_5'),
        Index('id_portu_koncowego', 'id_portu_koncowego'),
        Index('id_portu_startowego', 'id_portu_startowego'),
        Index('id_wezla_koncowego', 'id_wezla_koncowego'),
        Index('id_wezla_startowego', 'id_wezla_startowego'),
        Index('id_zaworu', 'id_zaworu'),
        Index('nazwa_segmentu', 'nazwa_segmentu', unique=True),
        {'comment': 'Definiuje fizyczne połączenia (krawędzie grafu)'}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nazwa_segmentu: Mapped[str] = mapped_column(VARCHAR(100))
    id_zaworu: Mapped[int] = mapped_column(Integer)
    id_portu_startowego: Mapped[Optional[int]] = mapped_column(Integer)
    id_wezla_startowego: Mapped[Optional[int]] = mapped_column(Integer)
    id_portu_koncowego: Mapped[Optional[int]] = mapped_column(Integer)
    id_wezla_koncowego: Mapped[Optional[int]] = mapped_column(Integer)

    operacje_log: Mapped[List['OperacjeLog']] = relationship('OperacjeLog', secondary='log_uzyte_segmenty', back_populates='segmenty')
    porty_sprzetu: Mapped[Optional['PortySprzetu']] = relationship('PortySprzetu', foreign_keys=[id_portu_koncowego], back_populates='segmenty')
    porty_sprzetu_: Mapped[Optional['PortySprzetu']] = relationship('PortySprzetu', foreign_keys=[id_portu_startowego], back_populates='segmenty_')
    wezly_rurociagu: Mapped[Optional['WezlyRurociagu']] = relationship('WezlyRurociagu', foreign_keys=[id_wezla_koncowego], back_populates='segmenty')
    wezly_rurociagu_: Mapped[Optional['WezlyRurociagu']] = relationship('WezlyRurociagu', foreign_keys=[id_wezla_startowego], back_populates='segmenty_')
    zawory: Mapped['Zawory'] = relationship('Zawory', back_populates='segmenty')


class ApolloTracking(db.Model):
    __tablename__ = 'apollo_tracking'
    __table_args__ = (
        ForeignKeyConstraint(['id_operacji_log'], ['operacje_log.id'], name='apollo_tracking_ibfk_2'),
        ForeignKeyConstraint(['id_sesji'], ['apollo_sesje.id'], name='apollo_tracking_ibfk_1'),
        Index('id_operacji_log', 'id_operacji_log'),
        Index('id_sesji', 'id_sesji')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_sesji: Mapped[int] = mapped_column(Integer)
    typ_zdarzenia: Mapped[str] = mapped_column(ENUM('DODANIE_SUROWCA', 'TRANSFER_WYJSCIOWY', 'KOREKTA_RECZNA'))
    waga_kg: Mapped[decimal.Decimal] = mapped_column(DECIMAL(10, 2))
    czas_zdarzenia: Mapped[datetime.datetime] = mapped_column(DateTime)
    id_operacji_log: Mapped[Optional[int]] = mapped_column(Integer)
    operator: Mapped[Optional[str]] = mapped_column(String(255, 'utf8mb4_unicode_ci'))
    uwagi: Mapped[Optional[str]] = mapped_column(Text(collation='utf8mb4_unicode_ci'))

    operacje_log: Mapped[Optional['OperacjeLog']] = relationship('OperacjeLog', back_populates='apollo_tracking')
    apollo_sesje: Mapped['ApolloSesje'] = relationship('ApolloSesje', back_populates='apollo_tracking')


t_log_uzyte_segmenty = db.Table(
    'log_uzyte_segmenty', db.Model.metadata,
    db.Column('id_operacji_log', Integer, primary_key=True, nullable=False),
    db.Column('id_segmentu', Integer, primary_key=True, nullable=False),
    ForeignKeyConstraint(['id_operacji_log'], ['operacje_log.id'], ondelete='CASCADE', name='log_uzyte_segmenty_ibfk_1'),
    ForeignKeyConstraint(['id_segmentu'], ['segmenty.id'], name='log_uzyte_segmenty_ibfk_2'),
    Index('id_segmentu', 'id_segmentu'),
    comment='Zapisuje, które segmenty były używane w danej operacji z logu'
)


class PartieHistoria(db.Model):
    __tablename__ = 'partie_historia'
    __table_args__ = (
        ForeignKeyConstraint(['id_operacji_log'], ['operacje_log.id'], ondelete='SET NULL', name='partie_historia_ibfk_2'),
        ForeignKeyConstraint(['id_partii_surowca'], ['partie_surowca.id'], ondelete='CASCADE', name='partie_historia_ibfk_1'),
        Index('id_operacji_log', 'id_operacji_log'),
        Index('idx_data_operacji', 'data_operacji'),
        Index('idx_partia', 'id_partii_surowca'),
        Index('idx_typ_operacji', 'typ_operacji')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_partii_surowca: Mapped[int] = mapped_column(Integer)
    typ_operacji: Mapped[str] = mapped_column(ENUM('UTWORZENIE', 'TRANSFER', 'FILTRACJA', 'MIESZANIE', 'DZIELENIE', 'ZMIANA_STANU', 'POBOR_PROBKI', 'ZATWIERDZENIE'))
    data_operacji: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))
    operator: Mapped[Optional[str]] = mapped_column(VARCHAR(100))
    lokalizacja_przed: Mapped[Optional[str]] = mapped_column(VARCHAR(100))
    lokalizacja_po: Mapped[Optional[str]] = mapped_column(VARCHAR(100))
    waga_przed: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(10, 3))
    waga_po: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(10, 3))
    parametry_operacji: Mapped[Optional[dict]] = mapped_column(JSON)
    opis_operacji: Mapped[Optional[str]] = mapped_column(Text)
    id_operacji_log: Mapped[Optional[int]] = mapped_column(Integer)

    operacje_log: Mapped[Optional['OperacjeLog']] = relationship('OperacjeLog', back_populates='partie_historia')
    partie_surowca: Mapped['PartieSurowca'] = relationship('PartieSurowca', back_populates='partie_historia')


class PartiePowiazania(db.Model):
    __tablename__ = 'partie_powiazania'
    __table_args__ = (
        ForeignKeyConstraint(['id_operacji_log'], ['operacje_log.id'], ondelete='SET NULL', name='partie_powiazania_ibfk_3'),
        ForeignKeyConstraint(['partia_docelowa_id'], ['partie_surowca.id'], ondelete='CASCADE', name='partie_powiazania_ibfk_2'),
        ForeignKeyConstraint(['partia_zrodlowa_id'], ['partie_surowca.id'], ondelete='CASCADE', name='partie_powiazania_ibfk_1'),
        Index('id_operacji_log', 'id_operacji_log'),
        Index('idx_partia_docelowa', 'partia_docelowa_id'),
        Index('idx_partia_zrodlowa', 'partia_zrodlowa_id'),
        Index('idx_typ_powiazania', 'typ_powiazania')
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    partia_zrodlowa_id: Mapped[int] = mapped_column(Integer)
    partia_docelowa_id: Mapped[int] = mapped_column(Integer)
    typ_powiazania: Mapped[str] = mapped_column(ENUM('DZIELENIE', 'LACZENIE', 'TRANSFORMACJA'))
    procent_udzialu: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(5, 2))
    data_powiazania: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))
    id_operacji_log: Mapped[Optional[int]] = mapped_column(Integer)
    uwagi: Mapped[Optional[str]] = mapped_column(Text)

    operacje_log: Mapped[Optional['OperacjeLog']] = relationship('OperacjeLog', back_populates='partie_powiazania')
    partia_docelowa: Mapped['PartieSurowca'] = relationship('PartieSurowca', foreign_keys=[partia_docelowa_id], back_populates='partie_powiazania')
    partia_zrodlowa: Mapped['PartieSurowca'] = relationship('PartieSurowca', foreign_keys=[partia_zrodlowa_id], back_populates='partie_powiazania_')


class ProbkiOcena(db.Model):
    __tablename__ = 'probki_ocena'
    __table_args__ = (
        ForeignKeyConstraint(['id_cyklu_filtracyjnego'], ['cykle_filtracyjne.id'], ondelete='CASCADE', name='probki_ocena_ibfk_2'),
        ForeignKeyConstraint(['id_partii'], ['partie_surowca.id'], ondelete='CASCADE', name='probki_ocena_ibfk_1'),
        Index('id_cyklu_filtracyjnego', 'id_cyklu_filtracyjnego'),
        Index('idx_partia_czas', 'id_partii', 'czas_pobrania'),
        {'comment': 'Rejestr próbek i ich ocen podczas procesu filtracji'}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_partii: Mapped[int] = mapped_column(Integer)
    id_cyklu_filtracyjnego: Mapped[int] = mapped_column(Integer)
    czas_pobrania: Mapped[datetime.datetime] = mapped_column(DateTime)
    czas_oceny: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    wynik_oceny: Mapped[Optional[str]] = mapped_column(ENUM('pozytywna', 'negatywna', 'oczekuje'), server_default=text("'oczekuje'"))
    ocena_koloru: Mapped[Optional[str]] = mapped_column(VARCHAR(50))
    decyzja: Mapped[Optional[str]] = mapped_column(ENUM('kontynuuj_filtracje', 'wyslij_do_magazynu', 'dodaj_ziemie'))
    operator_oceniajacy: Mapped[Optional[str]] = mapped_column(VARCHAR(100))
    uwagi: Mapped[Optional[str]] = mapped_column(Text)

    cykle_filtracyjne: Mapped['CykleFiltracyjne'] = relationship('CykleFiltracyjne', back_populates='probki_ocena')
    partie_surowca: Mapped['PartieSurowca'] = relationship('PartieSurowca', back_populates='probki_ocena')

    
class Batches(db.Model):
    __tablename__ = 'batches'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unique_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    material_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_type: Mapped[str] = mapped_column(ENUM('CYS', 'APOLLO'), nullable=False)
    source_name: Mapped[str] = mapped_column(String(50), nullable=False)
    initial_quantity: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(10, 2), nullable=False)
    current_quantity: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(10, 2), nullable=False)
    creation_date: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    status: Mapped[str] = mapped_column(ENUM('ACTIVE', 'DEPLETED', 'ARCHIVED'), default='ACTIVE')

class TankMixes(db.Model):
    __tablename__ = 'tank_mixes'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    unique_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    tank_id: Mapped[int] = mapped_column(ForeignKey('sprzet.id'), nullable=False)
    creation_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    status: Mapped[str] = mapped_column(ENUM('ACTIVE', 'ARCHIVED'), default='ACTIVE')

    # Relacja do sprzętu (zbiornika)
    tank: Mapped['Sprzet'] = relationship(back_populates='active_mix')
    # Relacja do składników
    components: Mapped[List['MixComponents']] = relationship(back_populates='mix')

class MixComponents(db.Model):
    __tablename__ = 'mix_components'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mix_id: Mapped[int] = mapped_column(ForeignKey('tank_mixes.id'), nullable=False)
    batch_id: Mapped[int] = mapped_column(ForeignKey('batches.id'), nullable=False)
    quantity_in_mix: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(10, 2), nullable=False)
    date_added: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relacje
    mix: Mapped['TankMixes'] = relationship(back_populates='components')
    batch: Mapped['Batches'] = relationship() # Prosta relacja jednokierunkowa