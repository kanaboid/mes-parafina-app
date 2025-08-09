# app/batch_management_service.py
from . import db
from .models import Batches
from datetime import datetime

class BatchManagementService:
    @staticmethod
    def create_raw_material_batch(material_type, source_type, source_name, quantity, operator):
        # Na razie nic nie robimy
        pass