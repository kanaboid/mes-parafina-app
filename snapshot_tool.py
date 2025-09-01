# snapshot_tool.py
import os
import base64
import yaml
from datetime import datetime, timezone

# --- KONFIGURACJA ---
# Zdefiniuj, które pliki chcesz dołączyć do snapshotu.
# Dodaj tu wszystkie kluczowe pliki, nad którymi pracujemy.
FILES_TO_INCLUDE = [
    'DOKUMENTACJA.md',          # Nasz "Master Prompt"
    'backup_restore_point.sql',
    'app/config.py',
    'run.py',
    'app/extensions.py',
    'app/__init__.py',
    'app/models.py',
    'app/sockets.py',
    'app/routes.py',
    'app/sprzet_routes.py',
    'app/operations_routes.py',
    'app/batch_routes.py',
    'app/apollo_service.py',
    'app/batch_management_service.py',
    'app/dashboard_service.py',
    'app/sprzet_service.py',
    'app/sensors.py',
    'app/pathfinder_service.py',
    'app/templates/dashboard.html',
    'app/static/js/dashboard.js',
]

OUTPUT_FILENAME = 'mes_context.yml'

def create_snapshot():
    """Główna funkcja, która tworzy plik YAML z pełnym kontekstem projektu."""
    
    print("Rozpoczynam tworzenie snapshotu kontekstu...")

    # 1. Struktura danych w Pythonie, która zostanie przekonwertowana na YAML
    snapshot_data = {
        'project_snapshot': {
            'metadata': {
                'project_name': 'MES Parafina',
                'version': '1.0',
                'timestamp_utc': datetime.now(timezone.utc).isoformat()
            },
            'user_profile': {
                'role': 'Właściciel projektu / Główny deweloper',
                'technical_level': 'Zaawansowany (Python, Flask, SQLAlchemy, Docker)',
                'communication_style': 'Bezpośredni, techniczny, partnerski w podejmowaniu decyzji.',
                'main_goal': 'Zbudować nowoczesny, niezawodny i użyteczny system MES.'
            },
            'ai_profile': {
                'role': 'Starszy Inżynier Oprogramowania / Architekt Systemu',
                'tasks': ['Projektowanie architektury', 'Pisanie i refaktoryzacja kodu', 'Tworzenie testów (TDD)', 'Sugerowanie najlepszych praktyk', 'Aktualizacja dokumentacji'],
                'style': 'Proaktywny, partnerski, dzielenie pracy na małe kroki, wyjaśnianie decyzji.'
            },
            'source_files_base64': []
        }
    }

    # 2. Pętla przez pliki, kodowanie ich do Base64 i dodawanie do struktury
    for file_path in FILES_TO_INCLUDE:
        print(f"  -> Przetwarzam plik: {file_path}")
        if not os.path.exists(file_path):
            print(f"     ! OSTRZEŻENIE: Plik {file_path} nie został znaleziony. Pomijam.")
            continue
        
        try:
            with open(file_path, 'rb') as f:
                content_bytes = f.read()
                content_base64 = base64.b64encode(content_bytes).decode('ascii')
                
                snapshot_data['project_snapshot']['source_files_base64'].append({
                    'path': file_path.replace('\\', '/'), # Normalizacja ścieżek
                    'content': content_base64
                })
        except Exception as e:
            print(f"     ! BŁĄD: Nie udało się przetworzyć pliku {file_path}. Błąd: {e}")

    # 3. Zapisanie finalnej struktury do pliku YAML
    try:
        with open(OUTPUT_FILENAME, 'w', encoding='utf-8') as f:
            yaml.dump(snapshot_data, f, sort_keys=False, width=120)
        print(f"\nSukces! Snapshot został zapisany do pliku: {OUTPUT_FILENAME}")
    except Exception as e:
        print(f"\nBłąd podczas zapisywania pliku YAML: {e}")

if __name__ == '__main__':
    # Upewnij się, że masz aktualną dokumentację i backup bazy
    if not os.path.exists('DOKUMENTACJA.md'):
        print("Brak pliku DOKUMENTACJA.md! Upewnij się, że go stworzyłeś.")
    if not os.path.exists('backup_restore_point.sql'):
        print("Brak pliku backup_restore_point.sql! Uruchom `mysqldump`.")
    
    create_snapshot()