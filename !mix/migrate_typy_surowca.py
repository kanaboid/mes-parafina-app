import mysql.connector
from app.config import Config

def create_typy_surowca_table():
    # Połącz z bazą danych
    connection = mysql.connector.connect(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DB
    )
    
    cursor = connection.cursor()
    
    try:
        # Tworzenie tabeli
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS `typy_surowca` (
          `id` int NOT NULL AUTO_INCREMENT,
          `nazwa` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
          `opis` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
          PRIMARY KEY (`id`),
          UNIQUE KEY `nazwa` (`nazwa`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Słownik typów surowca'
        """
        
        cursor.execute(create_table_sql)
        print("Tabela typy_surowca została utworzona")
        
        # Sprawdź czy tabela jest pusta
        cursor.execute("SELECT COUNT(*) FROM typy_surowca")
        count = cursor.fetchone()[0]
        
        if count == 0:
            # Wstawienie podstawowych typów surowca
            insert_sql = """
            INSERT INTO `typy_surowca` (`nazwa`, `opis`) VALUES
            ('T-10', 'Typ surowca T-10'),
            ('19', 'Typ surowca 19'),
            ('44', 'Typ surowca 44'),
            ('GC43', 'Typ surowca GC43'),
            ('GC42', 'Typ surowca GC42')
            """
            
            cursor.execute(insert_sql)
            connection.commit()
            print("Wstawiono podstawowe typy surowca")
        else:
            print(f"Tabela już zawiera {count} rekordów")
            
    except mysql.connector.Error as error:
        print(f"Błąd: {error}")
    finally:
        cursor.close()
        connection.close()

if __name__ == "__main__":
    create_typy_surowca_table()
