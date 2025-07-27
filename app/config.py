    # app/config.py

import os
from dotenv import load_dotenv

load_dotenv()

# class Config:
#     # Klucz do zabezpieczeń Flaska, np. sesji. Na razie nieistotny, ale potrzebny.
#     SECRET_KEY = os.environ.get('SECRET_KEY') or 'trudne-do-zgadniecia-haslo'

#     # Dane do połączenia z bazą danych MySQL
#     MYSQL_HOST = '10.200.184.217'
#     MYSQL_USER = 'remote_user' # Zmień, jeśli masz innego użytkownika
#     MYSQL_PASSWORD = 'Radar123@@' # <-- WAŻNE: Wpisz swoje hasło
#     MYSQL_DB = 'mes_parafina_db'



# class Config:
#     # Klucz do zabezpieczeń Flaska, np. sesji. Na razie nieistotny, ale potrzebny.
#     SECRET_KEY = os.environ.get('SECRET_KEY') or 'trudne-do-zgadniecia-haslo'

#     # Dane do połączenia z bazą danych MySQL
#     MYSQL_HOST = 'localhost'
#     MYSQL_USER = 'root' # Zmień, jeśli masz innego użytkownika
#     MYSQL_PASSWORD = '' # <-- WAŻNE: Wpisz swoje hasło
#     MYSQL_DB = 'mes_parafina_db'

class Config:
    # Klucz do zabezpieczeń Flaska, np. sesji. Na razie nieistotny, ale potrzebny.
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'trudne-do-zgadniecia-haslo'

    # Dane do połączenia z bazą danych MySQL
    MYSQL_HOST = os.environ.get('MYSQLHOST')
    MYSQL_USER = os.environ.get('MYSQLUSER') # Zmień, jeśli masz innego użytkownika
    MYSQL_PASSWORD = os.environ.get('MYSQL_ROOT_PASSWORD') # <-- WAŻNE: Wpisz swoje hasło
    MYSQL_DB = 'mes_parafina_db'