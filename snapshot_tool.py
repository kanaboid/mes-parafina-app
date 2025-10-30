# snapshot_tool.py
import os
import base64
import yaml
from datetime import datetime, timezone

# --- KONFIGURACJA ---
# Zdefiniuj tutaj, jak ma działać skrypt.

# 1. Katalogi do automatycznego skanowania w poszukiwaniu plików .py
DIRECTORIES_TO_SCAN = [
    'app/',
    'alembic/'
    
]

# 2. Pliki, które ZAWSZE mają być dołączone (nawet jeśli są poza skanowanymi katalogami)
ALWAYS_INCLUDE = [
    'DOKUMENTACJA.md',
    'backup_restore_point.sql',
    'run.py',
    'manage.py',
    'requirements.txt',
    'celery_app.py',
    'migrate.ps1',
    'test_batch_management.py'
]

# 3. Wzorce plików lub folderów do WYKLUCZENIA podczas automatycznego skanowania.
#    Skrypt zignoruje każdy plik/folder, którego nazwa zaczyna się od jednego z tych wzorców.
EXCLUDE_PATTERNS = [
    'test_',          # Ignoruj pliki testowe, np. test_sensors.py
    '__pycache__',    # Ignoruj cache Pythona
    'migrations/',    # Zazwyczaj nie potrzebujemy historii migracji w snapshocie
    'instance/' ,      # Folder instancji Flaska
    'cykle_api.py',
    'alembic/versions',
    'snapshot_tool.py'
]

OUTPUT_FILENAME = 'mes_context.yml'


def collect_files_to_include() -> list[str]:
    """Przeszukuje katalogi i tworzy finalną listę plików do dołączenia."""
    
    files_to_process = set()

    for file_path in ALWAYS_INCLUDE:
        if os.path.exists(file_path):
            files_to_process.add(file_path.replace('\\', '/'))
        else:
            print(f"     ! OSTRZEŻENIE: Plik '{file_path}' z listy ALWAYS_INCLUDE nie istnieje.")

    for directory in DIRECTORIES_TO_SCAN:
        for root, dirs, files in os.walk(directory):
            # Normalizuj ścieżkę roota dla spójnego porównywania
            normalized_root = root.replace('\\', '/') + '/'
            
            # --- ZMIENIONA LOGIKA WYKLUCZANIA ---
            # Sprawdź, czy cała ścieżka do folderu pasuje do wzorca wykluczenia
            dirs[:] = [
                d for d in dirs 
                if not any(
                    (normalized_root + d).startswith(pattern) or d.startswith(pattern)
                    for pattern in EXCLUDE_PATTERNS
                )
            ]
            
            for filename in files:
                full_path = (normalized_root + filename)
                
                # Sprawdź, czy pełna ścieżka pliku lub sama nazwa pliku pasuje do wzorca
                if any(full_path.startswith(pattern) or filename.startswith(pattern) for pattern in EXCLUDE_PATTERNS):
                    continue
                
                if filename.endswith('.py'):
                    files_to_process.add(full_path)
                # elif filename.endswith('.js'):
                #     files_to_process.add(full_path)
    return sorted(list(files_to_process))


def create_snapshot():
    """Główna funkcja, która tworzy plik YAML z pełnym kontekstem projektu."""
    
    print("Rozpoczynam tworzenie snapshotu kontekstu...")

    snapshot_data = {
        'project_snapshot': {
            'metadata': {
                'project_name': 'MES Parafina',
                'version': '1.1', # Zwiększona wersja
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
    
    files_to_include = collect_files_to_include()
    print(f"\nZnaleziono {len(files_to_include)} plików do dołączenia.")

    for file_path in files_to_include:
        print(f"  -> Przetwarzam plik: {file_path}")
        try:
            with open(file_path, 'rb') as f:
                content_bytes = f.read()
                content_base64 = base64.b64encode(content_bytes).decode('ascii')
                
                snapshot_data['project_snapshot']['source_files_base64'].append({
                    'path': file_path,
                    'content': content_base64
                })
        except Exception as e:
            print(f"     ! BŁĄD: Nie udało się przetworzyć pliku {file_path}. Błąd: {e}")

    try:
        with open(OUTPUT_FILENAME, 'w', encoding='utf-8') as f:
            yaml.dump(snapshot_data, f, sort_keys=False, width=120, allow_unicode=True)
        print(f"\nSukces! Snapshot został zapisany do pliku: {OUTPUT_FILENAME}")
    except Exception as e:
        print(f"\nBłąd podczas zapisywania pliku YAML: {e}")


if __name__ == '__main__':
    if not os.path.exists('DOKUMENTACJA.md'):
        print("Brak pliku DOKUMENTACJA.md! Upewnij się, że go stworzyłeś.")
    if not os.path.exists('backup_restore_point.sql'):
        print("Brak pliku backup_restore_point.sql! Uruchom `mysqldump`.")
    
    create_snapshot()