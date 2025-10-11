# test_workflow_routes.py
import unittest
import json
from app import create_app, db
from app.config import TestConfig
from app.models import Sprzet, TankMixes
from sqlalchemy import text
from decimal import Decimal
from app.workflow_service import WorkflowService

class TestWorkflowRoutes(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        with self.app.app_context():
            db.session.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            for table in reversed(db.metadata.sorted_tables):
                db.session.execute(text(f'TRUNCATE TABLE {table.name}'))
            db.session.execute(text("SET FOREIGN_KEY_CHECKS=1"))
            db.session.commit()

    def tearDown(self):
        db.session.remove()
        self.app_context.pop()
    
    def _prepare_mix_for_assessment(self):
        tank = Sprzet(id=201, nazwa_unikalna='R1', typ_sprzetu='reaktor')
        mix = TankMixes(id=10, tank_id=tank.id, unique_code='MIX-TEST-ROUTE', process_status='OCZEKUJE_NA_OCENE')
        db.session.add_all([tank, mix])
        db.session.commit()
        return mix

    def test_assess_mix_ok_success(self):
        """Testuje pomyślne zatwierdzenie mieszaniny przez API."""
        mix = self._prepare_mix_for_assessment()
        payload = {"decision": "OK", "operator": "API_USER"}
        
        response = self.client.post(
            f'/api/workflow/mix/{mix.id}/assess',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['new_status'], 'ZATWIERDZONA')

    def test_assess_mix_zla_with_reason_success(self):
        """Testuje pomyślne odrzucenie mieszaniny przez API."""
        mix = self._prepare_mix_for_assessment()
        payload = {"decision": "ZLA", "operator": "API_USER", "reason": "Testowy powód"}
        
        response = self.client.post(
            f'/api/workflow/mix/{mix.id}/assess',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['new_status'], 'DO_PONOWNEJ_FILTRACJI')

    def test_assess_mix_missing_payload_fails(self):
        """Testuje błąd 400, gdy brakuje danych w żądaniu."""
        mix = self._prepare_mix_for_assessment()
        # Dodajemy nagłówek, aby poinformować serwer, że oczekuje on JSONa
        response = self.client.post(
            f'/api/workflow/mix/{mix.id}/assess',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_assess_mix_in_wrong_state_fails_422(self):
        """Testuje błąd 422, gdy mieszanina jest w złym stanie."""
        mix = self._prepare_mix_for_assessment()
        mix.process_status = 'ZATWIERDZONA'
        db.session.commit()
        
        payload = {"decision": "OK", "operator": "API_USER"}
        response = self.client.post(
            f'/api/workflow/mix/{mix.id}/assess',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 422)
        data = response.get_json()
        self.assertIn("Nie można ocenić mieszaniny", data['error'])

    def _prepare_mix_for_bleaching(self, temp=Decimal('115.0')):
        """Helper to create a mix ready for bleaching."""
        reaktor = Sprzet(
            id=1, nazwa_unikalna='R1', typ_sprzetu='reaktor', 
            temperatura_aktualna=temp
        )
        mix = TankMixes(
            id=10, tank=reaktor, unique_code='MIX-FOR-BLEACHING',
            process_status='PODGRZEWANY', bleaching_earth_bags_total=0
        )
        reaktor.active_mix_id = mix.id
        db.session.add_all([reaktor, mix])
        db.session.commit()
        return mix

    def test_add_bleaching_earth_success(self):
        """Testuje pomyślne zarejestrowanie dodania ziemi bielącej."""
        mix = self._prepare_mix_for_bleaching()
        
        updated_mix = WorkflowService.add_bleaching_earth(
            mix_id=mix.id,
            bags_count=5,
            operator='TEST_USER'
        )

        self.assertEqual(updated_mix.process_status, 'DOBIELONY_OCZEKUJE')
        self.assertEqual(updated_mix.bleaching_earth_bags_total, 5)
        
        log = db.session.execute(select(OperacjeLog).where(OperacjeLog.typ_operacji == 'DOBIELANIE')).scalar_one()
        self.assertIsNotNone(log)
        self.assertIn("Dodano 5 worków", log.opis)

    def test_add_bleaching_earth_accumulates_bags(self):
        """Testuje, czy kolejne dobielanie akumuluje liczbę worków."""
        mix = self._prepare_mix_for_bleaching()
        mix.bleaching_earth_bags_total = 3 # Ustawiamy stan początkowy
        db.session.commit()
        
        updated_mix = WorkflowService.add_bleaching_earth(
            mix_id=mix.id,
            bags_count=4,
            operator='TEST_USER'
        )
        self.assertEqual(updated_mix.bleaching_earth_bags_total, 7) # 3 + 4

    def test_add_bleaching_earth_too_cold_fails(self):
        """Testuje, czy próba dobielania przy zbyt niskiej temperaturze rzuca błąd."""
        mix = self._prepare_mix_for_bleaching(temp=Decimal('105.0'))
        
        with self.assertRaisesRegex(ValueError, "Zbyt niska temperatura reaktora"):
            WorkflowService.add_bleaching_earth(
                mix_id=mix.id,
                bags_count=5,
                operator='TEST_USER'
            )

    def test_add_bleaching_earth_wrong_status_fails(self):
        """Testuje, czy próba dobielania mieszaniny w złym stanie rzuca błąd."""
        mix = self._prepare_mix_for_bleaching()
        mix.process_status = 'SUROWY'
        db.session.commit()

        with self.assertRaisesRegex(ValueError, "Nie można dobielić mieszaniny"):
            WorkflowService.add_bleaching_earth(
                mix_id=mix.id,
                bags_count=5,
                operator='TEST_USER'
            )

    def _prepare_mix_for_bleaching(self, temp=Decimal('115.0')):
        """Helper to create a reactor and mix ready for bleaching."""
        reaktor = Sprzet(
            id=1, nazwa_unikalna='R1', typ_sprzetu='reaktor', 
            temperatura_aktualna=temp
        )
        mix = TankMixes(
            id=10, tank=reaktor, unique_code='MIX-FOR-BLEACHING',
            process_status='PODGRZEWANY', bleaching_earth_bags_total=0
        )
        reaktor.active_mix_id = mix.id
        db.session.add_all([reaktor, mix])
        db.session.commit()
        return mix

    def test_add_bleaching_earth_success(self):
        """Testuje pomyślne dodanie ziemi bielącej przez API."""
        mix = self._prepare_mix_for_bleaching()
        payload = {"bags_count": 5, "operator": "API_USER"}
        
        response = self.client.post(
            f'/api/workflow/mix/{mix.id}/add-bleach',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['new_status'], 'DOBIELONY_OCZEKUJE')
        self.assertEqual(data['total_bags'], 5)

    def test_add_bleaching_earth_missing_payload_fails(self):
        """Testuje błąd 400, gdy brakuje wymaganych pól w żądaniu."""
        mix = self._prepare_mix_for_bleaching()
        
        # Test bez pola 'bags_count'
        payload1 = {"operator": "API_USER"}
        response1 = self.client.post(
            f'/api/workflow/mix/{mix.id}/add-bleach',
            data=json.dumps(payload1),
            content_type='application/json'
        )
        self.assertEqual(response1.status_code, 400)

        # Test bez pola 'operator'
        payload2 = {"bags_count": 5}
        response2 = self.client.post(
            f'/api/workflow/mix/{mix.id}/add-bleach',
            data=json.dumps(payload2),
            content_type='application/json'
        )
        self.assertEqual(response2.status_code, 400)

    def test_add_bleaching_earth_too_cold_fails_422(self):
        """Testuje błąd 422 (logiki biznesowej), gdy reaktor jest za zimny."""
        mix = self._prepare_mix_for_bleaching(temp=Decimal('100.0')) # Poniżej progu 110°C
        payload = {"bags_count": 5, "operator": "API_USER"}

        response = self.client.post(
            f'/api/workflow/mix/{mix.id}/add-bleach',
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 422)
        data = response.get_json()
        self.assertIn("Zbyt niska temperatura reaktora", data['error'])