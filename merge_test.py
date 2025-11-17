# merge_test.py
from pathlib import Path

def merge_all_test_files(output_file="merged_all_tests.py"):
    """Łączy wszystkie pliki test_*.py w jeden plik bez modyfikacji."""
    
    current_dir = Path(".")
    test_files = sorted([f for f in current_dir.glob("test_*.py") if f.is_file()])
    
    if not test_files:
        print("Nie znaleziono żadnych plików test_*.py")
        return
    
    print(f"Znaleziono {len(test_files)} plików testowych:")
    for f in test_files:
        print(f"  - {f.name}")
    
    print(f"\nZapisywanie do: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as outfile:
        for test_file in test_files:
            print(f"Przetwarzanie: {test_file.name}")
            with open(test_file, 'r', encoding='utf-8') as infile:
                outfile.write(infile.read())
            outfile.write("\n")
    
    print(f"\n✓ Sukces! Połączono {len(test_files)} plików do {output_file}")
    print(f"  Rozmiar pliku wynikowego: {Path(output_file).stat().st_size / 1024:.2f} KB")

if __name__ == "__main__":
    import sys
    output_file = sys.argv[1] if len(sys.argv) > 1 else "merged_all_tests.py"
    merge_all_test_files(output_file)