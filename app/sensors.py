import random
import time
from datetime import datetime, timezone
from flask import current_app
from mysql.connector.errors import OperationalError
from .db import get_db_connection
from .extensions import db
from .models import Sprzet, OperatorTemperatures, HistoriaPomiarow
from decimal import Decimal
from .ipomiar_service import IPomiarService
from sqlalchemy import select

class SensorService:
    def __init__(self, app=None):
        self.app = app
        
       
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self.app = app
        # Don't load temperatures here - will do it in context
        
            
    @staticmethod
    def set_current_temperature(equipment_names, temperatura):
        """
        Ustawia TYLKO aktualną temperaturę dla listy sprzętów, np. po zatankowaniu.
        Nie zmienia temperatury docelowej.
        """
        if not equipment_names:
            return []

        try:
            # Używamy UPDATE, aby zmienić tylko te dwa pola
            stmt = db.update(Sprzet).where(
                Sprzet.nazwa_unikalna.in_(equipment_names)
            ).values(
                temperatura_aktualna=temperatura,
                ostatnia_aktualizacja=datetime.now(timezone.utc)
            )
            
            # `execute` zwraca obiekt result, z którego możemy odczytać, ile wierszy zmieniono
            result = db.session.execute(stmt)
            db.session.commit()
            
            print(f"Zaktualizowano `temperatura_aktualna` dla {result.rowcount} urządzeń.")
            
            # Zwracamy listę podanych nazw, aby potwierdzić, że polecenie zostało przyjęte
            # (nawet jeśli niektóre nazwy nie istniały w bazie)
            return equipment_names

        except Exception as e:
            db.session.rollback()
            print(f"Wystąpił błąd podczas ustawiania temperatury aktualnej: {e}")
            raise
    
    

    def _calculate_new_temperature(self, reaktor: Sprzet) -> Decimal:
        """
        Oblicza nową temperaturę dla reaktora na podstawie stanu palnika,
        prędkości grzania/chłodzenia i czasu, jaki upłynął.
        Emituje powiadomienie po osiągnięciu temperatury docelowej, ale NIE wyłącza palnika.
        """
        base_temperature = reaktor.temperatura_aktualna or Decimal('20.0')
        
        last_update_time = reaktor.ostatnia_aktualizacja or datetime.now(timezone.utc)
        if last_update_time.tzinfo is None:
            last_update_time = last_update_time.replace(tzinfo=timezone.utc)

        current_time = datetime.now(timezone.utc)
        minutes_passed = Decimal((current_time - last_update_time).total_seconds()) / Decimal(60)

        if minutes_passed <= 0:
            return base_temperature

        if reaktor.stan_palnika == 'WLACZONY':
            heating_speed = reaktor.szybkosc_grzania_c_na_minute or Decimal('0.5')
            target_temp = reaktor.temperatura_docelowa or Decimal('120.0')
            temp_increase = minutes_passed * heating_speed
            new_temperature = base_temperature + temp_increase

            # Sprawdź, czy cel został właśnie osiągnięty lub przekroczony
            if base_temperature < target_temp and new_temperature >= target_temp:
                # Ograniczamy temperaturę do docelowej, aby nie rosła w nieskończoność
                new_temperature = target_temp
                
                # Emituj jednorazowe zdarzenie Socket.IO o zakończeniu grzania
                from .sockets import socketio
                socketio.emit('heating_completed', {
                    'sprzet_id': reaktor.id, 
                    'nazwa': reaktor.nazwa_unikalna,
                    'message': f"Reaktor {reaktor.nazwa_unikalna} osiągnął temperaturę docelową {target_temp}°C."
                })
                print(f"INFO: Osiągnięto temperaturę docelową dla {reaktor.nazwa_unikalna}. Wysłano powiadomienie.")
            
            # Jeśli temperatura już jest powyżej celu, nie pozwól jej rosnąć dalej
            elif base_temperature >= target_temp:
                new_temperature = base_temperature

        else: # Palnik wyłączony lub nieznany stan
            cooling_speed = reaktor.szybkosc_chlodzenia_c_na_minute or Decimal('0.1')
            temp_decrease = minutes_passed * cooling_speed
            new_temperature = max(Decimal('20.0'), base_temperature - temp_decrease)

        return new_temperature

    def read_sensors(self):
        """
        Odczytuje i aktualizuje dane z czujników.
        - Odczytuje rzeczywisty poziom cieczy z API iPomiar.pl.
        - Symuluje zmiany temperatury dla reaktorów.
        - Zapisuje wszystkie pomiary do tabeli historia_pomiarow.
        """
        current_time = datetime.now(timezone.utc)
        print(f"\n--- SCHEDULER: Uruchamiam read_sensors o {current_time} ---")

        try:
            aktywny_sprzet_q = select(Sprzet).where(Sprzet.stan_sprzetu != 'Wyłączony')
            equipment_list = db.session.execute(aktywny_sprzet_q).scalars().all()
            
            pomiarowe_do_dodania = []
            
            for item in equipment_list:
                # Zmienne na nowe wartości z tego cyklu
                nowa_temperatura = item.temperatura_aktualna
                nowy_poziom_mm = None

                # 1. Odczytaj poziom z iPomiar, jeśli sprzęt jest skonfigurowany
                if item.ipomiar_device_id and item.poziom_pusty_mm is not None and item.poziom_pelny_mm is not None:
                    latest_distance = IPomiarService.get_latest_distance(item.ipomiar_device_id)
                    if latest_distance is not None:
                        nowy_poziom_mm = latest_distance # Zapisujemy surową wartość w mm
                        
                        zakres_pomiaru = item.poziom_pusty_mm - item.poziom_pelny_mm
                        if zakres_pomiaru > 0:
                            poziom_cieczy_mm = item.poziom_pusty_mm - latest_distance
                            poziom_procent = (poziom_cieczy_mm / zakres_pomiaru) * 100
                            item.poziom_aktualny_procent = round(max(Decimal('0.0'), min(Decimal('100.0'), poziom_procent)), 2)
                        else:
                             current_app.logger.warning(f"Nieprawidłowa konfiguracja czujnika dla {item.nazwa_unikalna}")

                # 2. Symuluj temperaturę dla reaktorów
                if item.typ_sprzetu == 'reaktor':
                    nowa_temperatura = self._calculate_new_temperature(item)
                
                nowe_cisnienie = self._simulate_pressure(item.typ_sprzetu)

                # 3. Zaktualizuj stan obiektu `Sprzet` w pamięci sesji
                item.temperatura_aktualna = nowa_temperatura
                item.cisnienie_aktualne = nowe_cisnienie
                item.ostatnia_aktualizacja = current_time
                
                # 4. Przygotuj wpis do `HistoriaPomiarow` ze wszystkimi danymi
                pomiar = HistoriaPomiarow(
                    id_sprzetu=item.id,
                    czas_pomiaru=current_time,
                    temperatura=nowa_temperatura,
                    cisnienie=nowe_cisnienie,
                    poziom_mm=nowy_poziom_mm  # Zapisujemy odczyt z iPomiar
                )
                pomiarowe_do_dodania.append(pomiar)

            if pomiarowe_do_dodania:
                db.session.add_all(pomiarowe_do_dodania)

            db.session.commit()
            print(f"[{current_time}] Pomiary (w tym poziomy) zapisane do bazy.")
            
        except Exception as e:
            db.session.rollback()
            print(f"Wystąpił błąd podczas odczytu czujników: {e}")
            import traceback
            traceback.print_exc()
            raise

    def _simulate_pressure(self, typ_sprzetu):
        if typ_sprzetu == 'filtr': return Decimal(str(round(random.uniform(4.0, 5.0), 2)))
        elif typ_sprzetu == 'reaktor': return Decimal(str(round(random.uniform(0.0, 2.0), 2)))
        return Decimal('0.0')

    @staticmethod
    def set_temperature_for_multiple(equipment_names, temperatura):
        """
        Ustawia hurtowo temperaturę docelową dla listy sprzętów.
        
        :param equipment_names: Lista stringów z nazwami unikalnymi sprzętów.
        :param temperatura: Nowa temperatura docelowa.
        :return: Lista nazw sprzętów, które udało się zaktualizować.
        """
        if not equipment_names:
            return []

        try:
            # Krok 1: Znajdź ID sprzętów na podstawie ich nazw
            sprzety_q = db.select(Sprzet).where(Sprzet.nazwa_unikalna.in_(equipment_names))
            sprzety_do_aktualizacji = db.session.execute(sprzety_q).scalars().all()

            if not sprzety_do_aktualizacji:
                print("Nie znaleziono żadnego sprzętu o podanych nazwach.")
                return []

            ids_do_aktualizacji = [s.id for s in sprzety_do_aktualizacji]
            nazwy_zaktualizowane = [s.nazwa_unikalna for s in sprzety_do_aktualizacji]
            current_time = datetime.now(timezone.utc)

            # Krok 2: Użyj `update` do masowej aktualizacji w tabeli `sprzet`
            stmt_sprzet = db.update(Sprzet).where(
                Sprzet.id.in_(ids_do_aktualizacji)
            ).values(
                temperatura_aktualna=temperatura,
                temperatura_docelowa=temperatura,
                ostatnia_aktualizacja=current_time
            )
            db.session.execute(stmt_sprzet)

            # Krok 3: Dodaj wpisy do historii `operator_temperatures`
            # Robimy to w pętli, ponieważ musimy dodać osobne wiersze
            nowe_wpisy_historii = []
            for sprzet_id in ids_do_aktualizacji:
                nowe_wpisy_historii.append(
                    OperatorTemperatures(id_sprzetu=sprzet_id, temperatura=temperatura, czas_ustawienia=current_time)
                )
            db.session.add_all(nowe_wpisy_historii)
            
            db.session.commit()
            return nazwy_zaktualizowane

        except Exception as e:
            db.session.rollback()
            print(f"Wystąpił błąd podczas masowej aktualizacji temperatury: {e}")
            raise

    @staticmethod
    def get_temperatures_for_multiple(equipment_names):
        """
        Pobiera aktualne i docelowe temperatury dla listy sprzętów.
        
        :param equipment_names: Lista stringów z nazwami unikalnymi sprzętów.
        :return: Lista słowników z danymi o temperaturze dla każdego znalezionego sprzętu.
        """
        if not equipment_names:
            return []

        try:
            # Używamy select() do wybrania konkretnych kolumn, co jest bardziej wydajne
            sprzety_q = db.select(
                Sprzet.nazwa_unikalna,
                Sprzet.temperatura_aktualna,
                Sprzet.temperatura_docelowa
            ).where(
                Sprzet.nazwa_unikalna.in_(equipment_names)
            )
            
            # .all() zwróci listę obiektów Row, które działają podobnie do słowników
            results = db.session.execute(sprzety_q).all()
            
            # Konwertujemy listę Row na listę słowników dla łatwiejszego użycia
            return [
                {
                    "nazwa": row.nazwa_unikalna,
                    "aktualna": row.temperatura_aktualna,
                    "docelowa": row.temperatura_docelowa
                } 
                for row in results
            ]
        except Exception as e:
            print(f"Wystąpił błąd podczas pobierania temperatur: {e}")
            raise

    @staticmethod
    def set_target_temperature(sprzet_id, temperatura):
        """
        Ustawia TYLKO temperaturę docelową dla pojedynczego sprzętu.
        
        :param sprzet_id: ID sprzętu w bazie danych
        :param temperatura: Nowa temperatura docelowa
        :return: True jeśli sukces, False jeśli błąd
        """
        try:
            # Sprawdź czy sprzęt istnieje
            sprzet = db.session.get(Sprzet, sprzet_id)
            if not sprzet:
                print(f"Sprzęt o ID {sprzet_id} nie istnieje")
                return False

            # Ustaw tylko temperaturę docelową
            sprzet.temperatura_docelowa = temperatura
            sprzet.ostatnia_aktualizacja = datetime.now(timezone.utc)
            
            # Dodaj wpis do historii
            nowy_wpis = OperatorTemperatures(
                id_sprzetu=sprzet_id, 
                temperatura=temperatura, 
                czas_ustawienia=datetime.now(timezone.utc)
            )
            db.session.add(nowy_wpis)
            
            db.session.commit()
            print(f"Ustawiono temperaturę docelową {temperatura}°C dla sprzętu ID {sprzet_id}")
            return True

        except Exception as e:
            db.session.rollback()
            print(f"Wystąpił błąd podczas ustawiania temperatury docelowej: {e}")
            return False

    @staticmethod
    def set_current_temperature_single(sprzet_id, temperatura):
        """
        Ustawia TYLKO temperaturę aktualną dla pojedynczego sprzętu.
        
        :param sprzet_id: ID sprzętu w bazie danych
        :param temperatura: Nowa temperatura aktualna
        :return: True jeśli sukces, False jeśli błąd
        """
        try:
            # Sprawdź czy sprzęt istnieje
            sprzet = db.session.get(Sprzet, sprzet_id)
            if not sprzet:
                print(f"Sprzęt o ID {sprzet_id} nie istnieje")
                return False

            # Ustaw tylko temperaturę aktualną
            sprzet.temperatura_aktualna = temperatura
            sprzet.ostatnia_aktualizacja = datetime.now(timezone.utc)
            
            # Dodaj wpis do historii
            nowy_wpis = OperatorTemperatures(
                id_sprzetu=sprzet_id, 
                temperatura=temperatura, 
                czas_ustawienia=datetime.now(timezone.utc)
            )
            db.session.add(nowy_wpis)
            
            db.session.commit()
            print(f"Ustawiono temperaturę aktualną {temperatura}°C dla sprzętu ID {sprzet_id}")
            return True

        except Exception as e:
            db.session.rollback()
            print(f"Wystąpił błąd podczas ustawiania temperatury aktualnej: {e}")
            return False