# test_ipomiar_service.py
import unittest
import json
from decimal import Decimal
from unittest.mock import patch, MagicMock

import requests
from sqlalchemy import text

from app import create_app, db
from app.config import TestConfig
from app.ipomiar_service import IPomiarService

class TestIPomiarService(unittest.TestCase):
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

    def tearDown(self):
        """Uruchamiane po każdym teście."""
        db.session.remove()
        self.app_context.pop()

    @patch('app.ipomiar_service.requests.get')
    def test_01_get_latest_distance_success(self, mock_get):
        """
        Sprawdza scenariusz pomyślny: API zwraca poprawne dane,
        a serwis konwertuje je z cm na mm.
        """
        # --- Przygotowanie (Arrange) ---
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"Date": "2025-10-21 10:00:00", "DISTANCE": "150.5"},
            {"Date": "2025-10-21 10:05:00", "DISTANCE": "148.2"}
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # --- Działanie (Act) ---
        result = IPomiarService.get_latest_distance('test-device-id')

        # --- Asercje (Assert) ---
        self.assertIsInstance(result, Decimal)
        self.assertAlmostEqual(result, Decimal('1482.0'))
        
        # --- POPRAWKA: Używamy `assertIn` zamiast `assertTrue` z `endswith` ---
        # Sprawdzamy, czy kluczowy fragment URL znajduje się w wywołaniu, ignorując parametry query.
        self.assertIn('/devices/test-device-id/data', mock_get.call_args[0][0])


    @patch('app.ipomiar_service.requests.get')
    def test_02_get_latest_distance_empty_list_returns_none(self, mock_get):
        """Sprawdza, czy serwis zwraca None, gdy API odpowie pustą listą."""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_get.return_value = mock_response
        
        # Act
        result = IPomiarService.get_latest_distance('test-device-id')
        
        # Assert
        self.assertIsNone(result)

    @patch('app.ipomiar_service.requests.get')
    def test_03_get_latest_distance_http_error_returns_none(self, mock_get):
        """Sprawdza, czy błąd HTTP (np. 404, 500) jest obsługiwany i zwraca None."""
        # Arrange
        mock_response = MagicMock()
        # `raise_for_status` rzuci błędem, jeśli status code to 4xx lub 5xx
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
        mock_get.return_value = mock_response

        # Act
        result = IPomiarService.get_latest_distance('test-device-id')

        # Assert
        self.assertIsNone(result)

    @patch('app.ipomiar_service.requests.get')
    def test_04_get_latest_distance_network_error_returns_none(self, mock_get):
        """Sprawdza, czy błąd sieciowy (np. timeout) jest obsługiwany i zwraca None."""
        # Arrange
        # Symulujemy, że samo wywołanie `requests.get` rzuca błędem
        mock_get.side_effect = requests.exceptions.RequestException("Connection timed out")

        # Act
        result = IPomiarService.get_latest_distance('test-device-id')
        
        # Assert
        self.assertIsNone(result)
        
    @patch('app.ipomiar_service.requests.get')
    def test_05_get_latest_distance_malformed_json_returns_none(self, mock_get):
        """Sprawdza, czy błąd parsowania JSON jest obsługiwany i zwraca None."""
        # Arrange
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None # Dodajemy to dla spójności
        mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "doc", 0)
        mock_get.return_value = mock_response
        
        # Act
        result = IPomiarService.get_latest_distance('test-device-id')

        # Assert
        self.assertIsNone(result)
        
    @patch('app.ipomiar_service.requests.get')
    def test_06_get_latest_distance_missing_key_returns_none(self, mock_get):
        """Sprawdza, czy brak klucza 'DISTANCE' w odpowiedzi jest obsługiwany i zwraca None."""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = [{"Date": "2025-10-21 10:05:00", "Temperature": "25.0"}] # Brak klucza 'DISTANCE'
        mock_get.return_value = mock_response
        
        # Act
        result = IPomiarService.get_latest_distance('test-device-id')
        
        # Assert
        self.assertIsNone(result)
        
    @patch('app.ipomiar_service.requests.get')
    def test_07_get_latest_distance_invalid_value_returns_none(self, mock_get):
        """Sprawdza, czy nie-numeryczna wartość 'DISTANCE' jest obsługiwana i zwraca None."""
        # Arrange
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None # Dodajemy to dla spójności
        mock_response.json.return_value = [{"Date": "2025-10-21 10:05:00", "DISTANCE": "brak_odczytu"}]
        mock_get.return_value = mock_response
        
        # Act
        result = IPomiarService.get_latest_distance('test-device-id')

        # Assert
        self.assertIsNone(result)

    def test_08_get_latest_distance_with_no_device_id_returns_none(self):
        """Sprawdza, czy wywołanie funkcji z pustym device_id od razu zwraca None."""
        result = IPomiarService.get_latest_distance(None)
        self.assertIsNone(result)
        result = IPomiarService.get_latest_distance("")
        self.assertIsNone(result)