#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skrypt do rozszerzenia bazy danych o tabele i kolumny dla cykli filtracyjnych
"""

import mysql.connector
from app.config import Config
import sys

def get_connection():
    """Utworzenie połączenia z bazą danych"""
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB,
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Błąd połączenia z bazą danych: {err}")
        return None

def execute_migration():
    """Wykonanie migracji bazy danych"""
    
    # SQL do rozszerzenia tabeli partie_surowca
    alter_queries = [
        """
        ALTER TABLE partie_surowca 
        ADD COLUMN aktualny_etap_procesu ENUM(
            'surowy', 'placek', 'przelew', 'w_kole', 
            'ocena_probki', 'dmuchanie', 'gotowy', 'wydmuch'
        ) DEFAULT 'surowy' AFTER status_partii
        """,
        """
        ALTER TABLE partie_surowca 
        ADD COLUMN numer_cyklu_aktualnego INT DEFAULT 0 AFTER aktualny_etap_procesu
        """,
        """
        ALTER TABLE partie_surowca 
        ADD COLUMN czas_rozpoczecia_etapu DATETIME NULL AFTER numer_cyklu_aktualnego
        """,
        """
        ALTER TABLE partie_surowca 
        ADD COLUMN planowany_czas_zakonczenia DATETIME NULL AFTER czas_rozpoczecia_etapu
        """,
        """
        ALTER TABLE partie_surowca 
        ADD COLUMN id_aktualnego_filtra VARCHAR(10) NULL AFTER planowany_czas_zakonczenia
        """,
        """
        ALTER TABLE partie_surowca 
        ADD COLUMN reaktor_docelowy VARCHAR(10) NULL AFTER id_aktualnego_filtra
        """
    ]
    
    # SQL do utworzenia nowych tabel
    create_tables = [
        """
        CREATE TABLE cykle_filtracyjne (
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
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci 
        COMMENT='Historia wszystkich cykli filtracyjnych dla każdej partii'
        """,
        """
        CREATE TABLE probki_ocena (
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
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci 
        COMMENT='Rejestr próbek i ich ocen podczas procesu filtracji'
        """
    ]
    
    conn = get_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    
    try:
        print("🔄 Rozpoczynam migrację bazy danych...")
        
        # Rozszerzenie tabeli partie_surowca
        print("\n📊 Rozszerzam tabelę partie_surowca...")
        for i, query in enumerate(alter_queries, 1):
            try:
                cursor.execute(query)
                print(f"  ✅ Kolumna {i}/6 dodana pomyślnie")
            except mysql.connector.Error as err:
                if "Duplicate column name" in str(err):
                    print(f"  ⚠️  Kolumna {i}/6 już istnieje - pomijam")
                else:
                    print(f"  ❌ Błąd dodawania kolumny {i}/6: {err}")
                    return False
        
        # Tworzenie nowych tabel
        print("\n🆕 Tworzę nowe tabele...")
        for i, query in enumerate(create_tables, 1):
            try:
                cursor.execute(query)
                print(f"  ✅ Tabela {i}/2 utworzona pomyślnie")
            except mysql.connector.Error as err:
                if "already exists" in str(err):
                    print(f"  ⚠️  Tabela {i}/2 już istnieje - pomijam")
                else:
                    print(f"  ❌ Błąd tworzenia tabeli {i}/2: {err}")
                    return False
        
        # Zatwierdzenie zmian
        conn.commit()
        print("\n🎉 Migracja zakończona pomyślnie!")
        return True
        
    except Exception as e:
        print(f"\n❌ Błąd podczas migracji: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    print("=== MIGRACJA BAZY DANYCH MES PARAFINA ===")
    print("Rozszerzenie o tabele dla cykli filtracyjnych\n")
    
    # Pytanie o potwierdzenie
    response = input("Czy na pewno chcesz wykonać migrację? (tak/nie): ").lower().strip()
    
    if response in ['tak', 'yes', 'y', 't']:
        success = execute_migration()
        if success:
            print("\n✅ Baza danych została pomyślnie zaktualizowana!")
            sys.exit(0)
        else:
            print("\n❌ Migracja nie powiodła się!")
            sys.exit(1)
    else:
        print("Migracja anulowana.")
        sys.exit(0)
