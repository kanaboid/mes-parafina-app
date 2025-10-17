# test_workflow_routes.py
import unittest
import json
from app import create_app, db
from app.config import TestConfig
from app.models import Sprzet, TankMixes, OperacjeLog # Dodano OperacjeLog
from sqlalchemy import select, text
from decimal import Decimal
from datetime import datetime, timedelta, timezone # Dodano datetime

class TestWorkflowRoutes(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        with self.app.app_context():
            db.session.execute(text("SET FOREIGN_key_CHECKS=0"))
            for table in reversed(db.metadata.sorted_tables):
                db.session.execute(text(f'TRUNCATE TABLE {table.name}'))
            db.session.execute(text("SET FOREIGN_KEY_CHECKS=1"))
            db.session.commit()

    def tearDown(self):
        db.session.remove()
        self.app_context.pop()
    
    def _prepare_mix_for_assessment(self):
        reaktor = Sprzet(id=201, nazwa_unikalna='R1', typ_sprzetu='reaktor')
        mix = TankMixes(id=10, tank_id=reaktor.id, unique_code='MIX-TEST-ROUTE', process_status='OCZEKUJE_NA_OCENE')
        reaktor.active_mix_id = mix.id
        db.session.add_all([reaktor, mix])
        db.session.commit()
        return mix

    def _prepare_mix_for_bleaching(self, temp=Decimal('115.0'), status='PODGRZEWANY', is_wydmuch=False, initial_bags=0):
        reaktor = Sprzet(id=1, nazwa_unikalna='R1', typ_sprzetu='reaktor', temperatura_aktualna=temp)
        mix = TankMixes(id=10, tank=reaktor, unique_code='MIX-FOR-BLEACHING',
                        process_status=status, bleaching_earth_bags_total=initial_bags,
                        is_wydmuch_mix=is_wydmuch,
                        creation_date=datetime.now(timezone.utc) - timedelta(hours=1))
        reaktor.active_mix_id = mix.id
        db.session.add_all([reaktor, mix])
        db.session.commit()
        return mix

    # --- Testy dla /assess ---
    def test_assess_mix_ok_success(self):
        mix = self._prepare_mix_for_assessment()
        payload = {"decision": "OK", "operator": "API_USER"}
        response = self.client.post(f'/api/workflow/mix/{mix.id}/assess', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['new_status'], 'ZATWIERDZONA')

    def test_assess_mix_zla_with_reason_success(self):
        mix = self._prepare_mix_for_assessment()
        payload = {"decision": "ZLA", "operator": "API_USER", "reason": "Testowy powód"}
        response = self.client.post(f'/api/workflow/mix/{mix.id}/assess', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['new_status'], 'DO_PONOWNEJ_FILTRACJI')

    def test_assess_mix_missing_payload_fails(self):
        mix = self._prepare_mix_for_assessment()
        response = self.client.post(f'/api/workflow/mix/{mix.id}/assess', content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_assess_mix_in_wrong_state_fails_422(self):
        mix = self._prepare_mix_for_assessment()
        mix.process_status = 'ZATWIERDZONA'
        db.session.commit()
        payload = {"decision": "OK", "operator": "API_USER"}
        response = self.client.post(f'/api/workflow/mix/{mix.id}/assess', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 422)
        data = response.get_json()
        self.assertIn("Nie można ocenić mieszaniny", data['error'])

    # --- NOWE TESTY dla /add-bleach ---

    def test_add_bleaching_earth_success_api(self):
        """Testuje pomyślne dodanie ziemi bielącej przez API."""
        mix = self._prepare_mix_for_bleaching()
        payload = {"bags_count": 5, "bag_weight": 25.0, "operator": "API_USER"}
        
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

    def test_add_bleaching_earth_second_time_updates_api(self):
        """Testuje, czy drugie dobielenie przez API aktualizuje istniejący log."""
        mix = self._prepare_mix_for_bleaching(status='DOBIELONY_OCZEKUJE', initial_bags=4)
        initial_log = OperacjeLog(
            typ_operacji='DOBIELANIE', id_tank_mix=mix.id, status_operacji='zakonczona',
            czas_rozpoczecia=datetime.now(timezone.utc)-timedelta(minutes=10),
            ilosc_workow=4, ilosc_kg=Decimal('100.0')
        )
        db.session.add(initial_log)
        db.session.commit()
        
        payload = {"bags_count": 2, "bag_weight": 25.0, "operator": "API_USER"}
        response = self.client.post(
            f'/api/workflow/mix/{mix.id}/add-bleach',
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['total_bags'], 6)
        self.assertIn("Dodano kolejne 2 worków", data['message'])

        # Sprawdź, czy w bazie jest nadal tylko jeden log
        logs = db.session.execute(select(OperacjeLog)).scalars().all()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].ilosc_kg, Decimal('150.0'))

    def test_add_bleaching_earth_invalid_payload_fails_400(self):
        """Testuje błąd 400 dla niepoprawnych danych wejściowych."""
        mix = self._prepare_mix_for_bleaching()
        
        # Brak wagi worka
        bad_payload = {"bags_count": 5, "operator": "API_USER"}
        response = self.client.post(
            f'/api/workflow/mix/{mix.id}/add-bleach',
            data=json.dumps(bad_payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_add_bleaching_earth_exceeds_limit_fails_422(self):
        """Testuje błąd 422 (logiki biznesowej) przy przekroczeniu limitu wagi."""
        mix = self._prepare_mix_for_bleaching()
        payload = {"bags_count": 7, "bag_weight": 25.0, "operator": "API_USER"} # 175 kg

        response = self.client.post(
            f'/api/workflow/mix/{mix.id}/add-bleach',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 422)
        data = response.get_json()
        self.assertIn("przekracza maksymalny limit", data['error'])