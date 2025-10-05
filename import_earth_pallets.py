#!/usr/bin/env python3
"""
Skrypt do importu istniejących danych palet ze zużytą ziemią filtracyjną.
Użycie: python import_earth_pallets.py
"""

from app import create_app
from app.extensions import db
from app.models import EarthPallets
from decimal import Decimal

def import_pallets():
    """Importuje dane z CSV do bazy danych"""
    
    # Dane z arkusza kalkulacyjnego
    pallets_data = [
        ("B1", 820, ""),
        ("B2", 1000, ""),
        ("B3", 1000, ""),
        ("B4", 1000, ""),
        ("B5", 1100, ""),
        ("B6", 1100, ""),
        ("B7", 980, ""),
        ("B8", 960, ""),
        ("B9", 960, ""),
        ("B10", 840, ""),
        ("B11", 800, ""),
        ("B12", 800, ""),
        ("B13", 940, ""),
        ("B14", 860, ""),
        ("B15", 1060, ""),
        ("B16", 1040, ""),
        ("B17", 880, ""),
        ("B18", 1020, ""),
        ("B19", 980, ""),
        ("B20", 1000, ""),
        ("B21", 1020, ""),
        ("B22", 980, ""),
        ("B23", 1040, ""),
        ("B24", 1060, ""),
        ("B25", 700, ""),
        ("B26", 880, ""),
        ("B27", 840, ""),
        ("B28", 960, ""),
        ("B29", 1040, ""),
        ("B30", 980, ""),
        ("B31", 1000, ""),
        ("B32", 980, ""),
        ("B33", 920, ""),
        ("B34", 1100, ""),
        ("B35", 840, ""),
        ("B36", 960, ""),
        ("B37", 940, ""),
        ("B38", 860, ""),
        ("B39", 1200, ""),
        ("B40", 920, ""),
        ("B41", 820, ""),
        ("B42", 980, ""),
        ("B43", 840, ""),
        ("B44", 1060, ""),
        ("B45", 960, ""),
    ]
    
    app = create_app()
    
    with app.app_context():
        print("🚀 Rozpoczynam import palet ze zużytą ziemią...")
        print(f"📦 Liczba palet do zaimportowania: {len(pallets_data)}")
        
        # Sprawdź czy dane już istnieją
        existing_count = db.session.query(EarthPallets).count()
        if existing_count > 0:
            print(f"⚠️  UWAGA: W bazie już istnieją {existing_count} rekordów.")
            response = input("Czy kontynuować import? (spowoduje to dodanie duplikatów) [t/N]: ")
            if response.lower() != 't':
                print("❌ Import anulowany.")
                return
        
        success_count = 0
        error_count = 0
        
        for lp, waga, zwazyl in pallets_data:
            try:
                # Sprawdź czy paleta już istnieje
                existing = db.session.query(EarthPallets).filter_by(lp=lp).first()
                if existing:
                    print(f"⏩ Pomijam {lp} - już istnieje w bazie")
                    continue
                
                # Utwórz nowy rekord
                pallet = EarthPallets(
                    lp=lp,
                    waga=Decimal(str(waga)),
                    zwazyl=zwazyl if zwazyl.strip() else None
                )
                db.session.add(pallet)
                success_count += 1
                print(f"✅ Dodano paletę {lp} ({waga} kg)")
                
            except Exception as e:
                error_count += 1
                print(f"❌ Błąd przy dodawaniu {lp}: {str(e)}")
        
        # Zatwierdź zmiany
        try:
            db.session.commit()
            print(f"\n🎉 Import zakończony pomyślnie!")
            print(f"   ✅ Zaimportowano: {success_count} palet")
            if error_count > 0:
                print(f"   ❌ Błędy: {error_count}")
            
            # Pokaż statystyki
            total_pallets = db.session.query(EarthPallets).count()
            total_weight = db.session.query(db.func.sum(EarthPallets.waga)).scalar() or 0
            print(f"\n📊 Statystyki po imporcie:")
            print(f"   📦 Łączna liczba palet w bazie: {total_pallets}")
            print(f"   ⚖️  Łączna waga: {float(total_weight):.2f} kg")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Błąd podczas zatwierdzania zmian: {str(e)}")
            print("   Wszystkie zmiany zostały wycofane.")


if __name__ == '__main__':
    import_pallets()

