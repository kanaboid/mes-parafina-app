#!/usr/bin/env python3
"""
Test script do weryfikacji działania connection pool.
Uruchom z: python test_connection_pool.py
"""

import os
import sys
import time
from datetime import datetime

# Dodaj ścieżkę do aplikacji
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from app.models import Sprzet
import os

# Wyłącz SocketIO dla testów jeśli powoduje problemy
os.environ['DISABLE_SOCKETIO'] = '1'

def test_connection_pool():
    """Testuje działanie connection pool."""
    print("🧪 TEST CONNECTION POOL")
    print("=" * 50)

    # Utwórz aplikację
    app = create_app()

    with app.app_context():
        # Sprawdź informacje o puli
        engine = db.engine
        pool = engine.pool

        print(f"📊 Pool Information:")
        print(f"   Pool size: {pool.size()}")
        print(f"   Pool checked in: {pool.checkedin()}")
        print(f"   Pool checked out: {pool.checkedout()}")
        print(f"   Pool overflow: {pool.overflow()}")
        print()

        # Test zapytań
        print("⚡ Testing queries...")
        start_time = time.time()

        # Symulacja wielu zapytań (jak w dashboard_service.py)
        test_queries = 50
        for i in range(test_queries):
            try:
                # Symulacja zapytania podobnego do tego z dashboard_service.py
                sprzet_q = db.select(Sprzet).where(
                    Sprzet.typ_sprzetu.in_(['reaktor', 'beczka_brudna', 'beczka_czysta'])
                ).limit(10)

                result = db.session.execute(sprzet_q).scalars().all()

                if i % 10 == 0:  # Log co 10 zapytań
                    print(f"   Query {i+1:2d}/{test_queries}: OK ({len(result)} results)")

            except Exception as e:
                print(f"   ❌ Query {i+1}: Error - {e}")
                return False

        end_time = time.time()
        total_time = end_time - start_time

        print()
        print("📈 Results:")
        print(f"   Total queries: {test_queries}")
        print(f"   Total time: {total_time:.3f}s")
        print(f"   Average time per query: {total_time/test_queries:.4f}s")
        print(f"   Queries per second: {test_queries/total_time:.2f}")

        # Sprawdź stan puli po testach
        print()
        print("🏁 Final Pool Status:")
        print(f"   Pool size: {pool.size()}")
        print(f"   Pool checked in: {pool.checkedin()}")
        print(f"   Pool checked out: {pool.checkedout()}")
        print(f"   Pool overflow: {pool.overflow()}")

        # Ocena wyników
        avg_time = total_time / test_queries
        if avg_time < 0.1:  # 100ms
            print()
            print("✅ TEST PASSED: Connection pool working efficiently!")
            return True
        else:
            print()
            print("⚠️  TEST WARNING: Queries are slower than expected")
            print("   Consider adjusting pool settings or checking database performance")
            return False

def test_pool_config():
    """Testuje konfigurację connection pool."""
    print("\n🔧 TEST POOL CONFIGURATION")
    print("=" * 50)

    app = create_app()

    with app.app_context():
        engine = db.engine

        print("Current pool configuration:")
        print(f"   Pool size: {engine.pool.size()}")
        print(f"   Pool timeout: {getattr(engine.pool, '_timeout', 'N/A')}")
        print(f"   Pool recycle: {getattr(engine.pool, '_recycle', 'N/A')}")
        print(f"   Pool pre_ping: {getattr(engine.pool, '_pre_ping', 'N/A')}")

        # Test pre_ping
        print("\nTesting pre_ping...")
        try:
            # Wykonaj proste zapytanie
            result = db.session.execute(db.text("SELECT 1")).scalar()
            print("   ✅ Pre_ping test passed")
        except Exception as e:
            print(f"   ❌ Pre_ping test failed: {e}")

if __name__ == "__main__":
    print(f"🚀 Connection Pool Test - {datetime.now()}")
    print(f"Environment: {os.environ.get('FLASK_ENV', 'development')}")
    print()

    try:
        # Test konfiguracji
        test_pool_config()

        # Test wydajności
        success = test_connection_pool()

        print()
        if success:
            print("🎉 ALL TESTS PASSED!")
            sys.exit(0)
        else:
            print("⚠️  SOME TESTS FAILED - Check configuration")
            sys.exit(1)

    except Exception as e:
        print(f"💥 TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
