# app/ipomiar_service.py
import requests
from datetime import datetime
from decimal import Decimal, InvalidOperation
from flask import current_app
import json

class IPomiarService:
    """
    Serwis do komunikacji z publicznym API iPomiar.pl w celu odczytu
    danych z czujników poziomu.
    """
    @staticmethod
    def get_latest_distance(device_id: str) -> Decimal | None:
        """
        Pobiera najnowszy pomiar odległości dla danego urządzenia.

        :param device_id: Unikalny identyfikator urządzenia z iPomiar.pl.
        :return: Wartość odległości jako Decimal, lub None w przypadku błędu lub braku danych.
        """
        if not device_id:
            return None

        base_url = current_app.config.get('IPOMIAR_API_BASE_URL')
        today_str = datetime.now().strftime('%Y-%m-%d')
        url = f"{base_url}/devices/{device_id}/data?date={today_str}"

        try:
            response = requests.get(url, timeout=10) # Timeout na 10 sekund
            response.raise_for_status()  # Rzuci błędem dla statusów 4xx/5xx

            data = response.json()

            if not data or not isinstance(data, list):
                # API zwróciło pustą listę lub niepoprawny format
                return None

            # Ostatni pomiar na liście jest najnowszym
            latest_measurement = data[-1]
            
            distance_str = latest_measurement.get("DISTANCE")
            if distance_str is None:
                return None

            distance_cm = Decimal(distance_str)
            distance_mm = distance_cm * 10
            return distance_mm

        except requests.exceptions.RequestException as e:
            # Błąd sieciowy, timeout, błąd HTTP itp.
            current_app.logger.error(f"Błąd komunikacji z API iPomiar dla urządzenia {device_id}: {e}")
            return None
        except (json.JSONDecodeError, InvalidOperation, KeyError) as e:
            # Błąd parsowania danych lub nieoczekiwany format
            current_app.logger.error(f"Błąd przetwarzania odpowiedzi z iPomiar dla urządzenia {device_id}: {e}")
            return None