# app/migration_routes.py
from flask import Blueprint, jsonify, request
from .db import get_db_connection
import mysql.connector

migration_bp = Blueprint('migration', __name__, url_prefix='/admin')

@migration_bp.route('/migrate/cykle-filtracyjne', methods=['POST'])
def migrate_cykle_filtracyjne():
    """Endpoint do wykonania migracji bazy danych"""
    
    # Sprawdzenie hasła administratora (dla bezpieczeństwa)
    admin_password = request.json.get('admin_password')
    if admin_password != 'admin123':  # Zmień na bezpieczne hasło
        return jsonify({'error': 'Nieprawidłowe hasło administratora'}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Lista zapytań do wykonania
        queries = [
            # Rozszerzenie tabeli partie_surowca
            """ALTER TABLE partie_surowca 
               ADD COLUMN aktualny_etap_procesu ENUM(
                   'surowy', 'placek', 'przelew', 'w_kole', 
                   'ocena_probki', 'dmuchanie', 'gotowy', 'wydmuch'
               ) DEFAULT 'surowy' AFTER status_partii""",
            
            """ALTER TABLE partie_surowca 
               ADD COLUMN numer_cyklu_aktualnego INT DEFAULT 0 AFTER aktualny_etap_procesu""",
            
            """ALTER TABLE partie_surowca 
               ADD COLUMN czas_rozpoczecia_etapu DATETIME NULL AFTER numer_cyklu_aktualnego""",
            
            """ALTER TABLE partie_surowca 
               ADD COLUMN planowany_czas_zakonczenia DATETIME NULL AFTER czas_rozpoczecia_etapu""",
            
            """ALTER TABLE partie_surowca 
               ADD COLUMN id_aktualnego_filtra VARCHAR(10) NULL AFTER planowany_czas_zakonczenia""",
            
            """ALTER TABLE partie_surowca 
               ADD COLUMN reaktor_docelowy VARCHAR(10) NULL AFTER id_aktualnego_filtra""",
            
            # Nowe tabele
            """CREATE TABLE cykle_filtracyjne (
                id INT PRIMARY KEY AUTO_INCREMENT,
                id_partii INT,
                numer_cyklu INT,
                typ_cyklu ENUM('placek', 'filtracja', 'dmuchanie'),
                id_filtra VARCHAR(10),
                reaktor_startowy VARCHAR(10),
                reaktor_docelowy VARCHAR(10),
                czas_rozpoczecia DATETIME,
                czas_zakonczenia DATETIME,
                czas_trwania_minut INT,
                wynik_oceny ENUM('pozytywna', 'negatywna', 'oczekuje'),
                komentarz TEXT,
                FOREIGN KEY (id_partii) REFERENCES partie_surowca(id) ON DELETE CASCADE,
                INDEX idx_partia_cykl (id_partii, numer_cyklu),
                INDEX idx_filtr_czas (id_filtra, czas_rozpoczecia)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
            
            """CREATE TABLE probki_ocena (
                id INT PRIMARY KEY AUTO_INCREMENT,
                id_partii INT NOT NULL,
                id_cyklu_filtracyjnego INT NOT NULL,
                czas_pobrania DATETIME NOT NULL,
                czas_oceny DATETIME NULL,
                wynik_oceny ENUM('pozytywna', 'negatywna', 'oczekuje') DEFAULT 'oczekuje',
                ocena_koloru VARCHAR(50) NULL,
                decyzja ENUM('kontynuuj_filtracje', 'wyslij_do_magazynu', 'dodaj_ziemie') NULL,
                operator_oceniajacy VARCHAR(100) NULL,
                uwagi TEXT NULL,
                FOREIGN KEY (id_partii) REFERENCES partie_surowca(id) ON DELETE CASCADE,
                FOREIGN KEY (id_cyklu_filtracyjnego) REFERENCES cykle_filtracyjne(id) ON DELETE CASCADE,
                INDEX idx_partia_czas (id_partii, czas_pobrania)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"""
        ]
        
        results = []
        for i, query in enumerate(queries):
            try:
                cursor.execute(query)
                results.append(f"Query {i+1}: SUCCESS")
            except mysql.connector.Error as err:
                if "Duplicate column name" in str(err) or "already exists" in str(err):
                    results.append(f"Query {i+1}: SKIPPED (already exists)")
                else:
                    results.append(f"Query {i+1}: ERROR - {err}")
        
        conn.commit()
        return jsonify({
            'success': True,
            'message': 'Migracja wykonana pomyślnie',
            'results': results
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'Błąd migracji: {str(e)}'}), 500
    finally:
        cursor.close()
        conn.close()
