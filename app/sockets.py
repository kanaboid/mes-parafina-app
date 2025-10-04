# app/sockets.py

from app import socketio
from flask_socketio import emit
from tabulate import tabulate
from decimal import Decimal, InvalidOperation

from .extensions import db
from .models import Sprzet, OperacjeLog, HistoriaPomiarow, ApolloSesje, ApolloTracking
from .sensors import SensorService
from .apollo_service import ApolloService
from .dashboard_service import DashboardService
# import redis # Już niepotrzebne

# CAŁA FUNKCJA redis_listener JEST USUWANA

@socketio.on('connect')
def handle_connect():
    """Wykonywane, gdy klient (przeglądarka) nawiązuje połączenie."""
    print('Klient połączony!')
    emit('response', {'data': 'Połączono z serwerem. Witaj w konsoli administracyjnej!'})
    emit('response', {'data': 'Wpisz "help", aby zobaczyć dostępne komendy.'})

@socketio.on('disconnect')
def handle_disconnect():
    """Graceful handling when client disconnects"""
    print('Klient rozłączony - zamykanie połączenia...')

@socketio.on_error_default
def default_error_handler(e):
    """Obsługa błędów WebSocket"""
    print(f'WebSocket error: {e}')
    # Nie logujemy pełnego stacktrace dla timeoutów, bo są oczekiwane

@socketio.on('request_dashboard_update')
def handle_request_dashboard_update():
    """
    To zdarzenie jest wywoływane przez nasz wewnętrzny redis_listener.
    Dzięki temu `broadcast_dashboard_update` jest wykonywane w głównym
    wątku serwera, z poprawnym kontekstem.
    """
    print("--- SocketIO Server: Otrzymano żądanie odświeżenia od Redis Listener. Wywołuję broadcast. ---")
    broadcast_dashboard_update()

@socketio.on('command_from_client')
def handle_command(json_data):
    """Odbiera i przetwarza komendy od klienta."""
    command_string = json_data.get('data', '').strip()
    if not command_string:
        return

    parts = command_string.split()
    command = parts[0].lower()
    args = parts[1:]

    print(f"Otrzymano komendę: '{command}' z argumentami: {args}")

    if command == 'show-temp':
        handle_show_temp(args)
    elif command == 'set-temp':
        handle_set_temp(args)
    elif command == 'set-current-temp':
        handle_set_current_temp(args)
    elif command == 'clear-measurements':
        handle_clear_measurements(args)
    elif command == 'help':
        handle_help()
    else:
        emit('response', {'data': f"Błąd: Nieznana komenda '{command}'.", 'is_error': True})

def handle_help():
    """Wysyła do klienta listę dostępnych komend."""
    help_text = """
Dostępne komendy:
-----------------
  show-temp [sprzet1] [sprzet2] ...
    Opis: Wyświetla temperatury dla podanego sprzętu.
    Flagi:
      --reaktory    : Pokaż tylko reaktory.
      (brak flag)   : Pokaż reaktory, apollo i beczki.

  set-temp <temp> <sprzet1> ...
    Opis: Ustawia temp. AKTUALNĄ i DOCELOWĄ.
    Flagi:
      --reaktory    : Zastosuj do wszystkich reaktorów.
      --all         : Zastosuj do wszystkich reaktorów, apollo i beczek.
      
  set-current-temp <temp> <sprzet1> ...
    Opis: Ustawia TYLKO temp. AKTUALNĄ (np. po tankowaniu).
    Flagi:
      --reaktory    : Zastosuj do wszystkich reaktorów.
      --all         : Zastosuj do wszystkich reaktorów, apollo i beczek.

  clear-measurements --confirm
    Opis: Czyści całą historię pomiarów. Wymaga potwierdzenia flagą.
"""
    emit('response', {'data': help_text})

def handle_show_temp(args):
    """Logika dla komendy show-temp."""
    try:
        equipment_to_show = args
        if not equipment_to_show:
            equipment_to_show = db.session.execute(db.select(Sprzet.nazwa_unikalna).where(Sprzet.typ_sprzetu.in_(['reaktor', 'apollo', 'beczka_brudna', 'beczka_czysta']))).scalars().all()
        elif "--reaktory" in equipment_to_show:
            equipment_to_show = db.session.execute(db.select(Sprzet.nazwa_unikalna).where(Sprzet.typ_sprzetu == 'reaktor')).scalars().all()

        if not equipment_to_show: return emit('response', {'data': "Nie znaleziono sprzętu do wyświetlenia."})

        temperatures_data = SensorService.get_temperatures_for_multiple(equipment_to_show)
        if not temperatures_data: return emit('response', {'data': "Nie znaleziono danych dla podanego sprzętu."})

        headers = ["Nazwa Sprzętu", "Aktualna", "Docelowa"]
        table_data = [[item['nazwa'], f"{item['aktualna']}°C" if item['aktualna'] is not None else "B/D", f"{item['docelowa']}°C" if item['docelowa'] is not None else "B/D"] for item in temperatures_data]
        formatted_table = tabulate(table_data, headers=headers, tablefmt="presto")
        emit('response', {'data': formatted_table})
    except Exception as e:
        emit('response', {'data': f"Wystąpił błąd serwera: {e}", 'is_error': True})

def handle_set_temp(args):
    """Logika dla komendy set-temp."""
    try:
        if len(args) < 2: return emit('response', {'data': 'Użycie: set-temp <temperatura> <sprzet1> ... lub --reaktory/--all', 'is_error': True})
        try: temperatura = Decimal(args[0])
        except InvalidOperation: return emit('response', {'data': f"Błąd: Nieprawidłowa wartość temperatury: '{args[0]}'.", 'is_error': True})

        equipment_to_update = args[1:]
        if "--reaktory" in equipment_to_update:
            equipment_to_update = db.session.execute(db.select(Sprzet.nazwa_unikalna).where(Sprzet.typ_sprzetu == 'reaktor')).scalars().all()
        elif "--all" in equipment_to_update:
            equipment_to_update = db.session.execute(db.select(Sprzet.nazwa_unikalna).where(Sprzet.typ_sprzetu.in_(['reaktor', 'apollo', 'beczka_brudna', 'beczka_czysta']))).scalars().all()

        if not equipment_to_update: return emit('response', {'data': "Błąd: Nie podano sprzętu do aktualizacji.", 'is_error': True})

        emit('response', {'data': f"Próba ustawienia temperatury (akt. i docel.) {temperatura}°C dla: {', '.join(equipment_to_update)}..."})
        updated = SensorService.set_temperature_for_multiple(equipment_to_update, temperatura)

        if updated:
            emit('response', {'data': f"Sukces!\nZaktualizowano temperaturę dla: {', '.join(updated)}"})
            broadcast_dashboard_update()
        else:
            emit('response', {'data': "Nie udało się zaktualizować żadnego sprzętu.", 'is_error': True})
    except Exception as e:
        emit('response', {'data': f"Wystąpił błąd serwera: {e}", 'is_error': True})

def handle_set_current_temp(args):
    """Logika dla komendy set-current-temp."""
    try:
        if len(args) < 2: return emit('response', {'data': 'Użycie: set-current-temp <temperatura> <sprzet1> ... lub --reaktory/--all', 'is_error': True})
        try: temperatura = Decimal(args[0])
        except InvalidOperation: return emit('response', {'data': f"Błąd: Nieprawidłowa wartość temperatury: '{args[0]}'.", 'is_error': True})
        
        equipment_to_update = args[1:]
        if "--reaktory" in equipment_to_update:
            equipment_to_update = db.session.execute(db.select(Sprzet.nazwa_unikalna).where(Sprzet.typ_sprzetu == 'reaktor')).scalars().all()
        elif "--all" in equipment_to_update:
            equipment_to_update = db.session.execute(db.select(Sprzet.nazwa_unikalna).where(Sprzet.typ_sprzetu.in_(['reaktor', 'apollo', 'beczka_brudna', 'beczka_czysta']))).scalars().all()
            
        if not equipment_to_update: return emit('response', {'data': "Błąd: Nie podano sprzętu do aktualizacji.", 'is_error': True})
        
        emit('response', {'data': f"Próba ustawienia TYLKO temp. aktualnej na {temperatura}°C dla: {', '.join(equipment_to_update)}..."})
        updated = SensorService.set_current_temperature(equipment_to_update, temperatura)
        
        if updated:
            emit('response', {'data': f"Sukces!\nUstawiono `temperatura_aktualna` na {temperatura}°C dla: {', '.join(updated)}"})
            broadcast_dashboard_update()
        else:
            emit('response', {'data': "Nie udało się zaktualizować żadnego sprzętu.", 'is_error': True})
    except Exception as e:
        emit('response', {'data': f"Wystąpił błąd serwera: {e}", 'is_error': True})

def handle_clear_measurements(args):
    """Logika dla komendy clear-measurements."""
    try:
        if not args or args[0] != '--confirm':
            return emit('response', {'data': 'BŁĄD: Wymagane potwierdzenie flagą --confirm', 'is_error': True})
        
        emit('response', {'data': 'Rozpoczynam czyszczenie `historia_pomiarow`...'})
        db.session.query(HistoriaPomiarow).delete()
        db.session.commit()
        emit('response', {'data': 'Sukces! Tabela `historia_pomiarow` została wyczyszczona.'})
        broadcast_dashboard_update()
    except Exception as e:
        db.session.rollback()
        emit('response', {'data': f'Błąd podczas czyszczenia tabeli: {str(e)}', 'is_error': True})

# --- FUNKCJE BROADCAST ---

def broadcast_dashboard_update():
    """Pobiera najnowszy stan dashboardu i rozgłasza go do wszystkich podłączonych klientów."""
    print("Broadcasting dashboard update to all clients...")
    try:
        dashboard_data = DashboardService.get_main_dashboard_data()
        socketio.emit('dashboard_update', dashboard_data)
    except Exception as e:
        print(f"Błąd podczas broadcastu aktualizacji dashboardu: {e}")

# --- PRZYWRÓCONA FUNKCJA ---
def broadcast_apollo_update():
    """
    Pobiera najnowszy stan urządzeń Apollo oraz aktywnych transferów
    i rozgłasza go do klientów na stronie /operacje-apollo.
    """
    print("Broadcasting Apollo-only update to all clients...")
    try:
        sprzet_apollo_q = db.select(Sprzet).filter_by(typ_sprzetu='apollo')
        apollo_devices = db.session.execute(sprzet_apollo_q).scalars().all()
        
        updated_apollo_list = []
        for apollo in apollo_devices:
            stan = ApolloService.get_stan_apollo(apollo.id)
            if stan:
                updated_apollo_list.append(stan)
        
        active_transfers_q = db.select(OperacjeLog).filter_by(
            status_operacji='aktywna',
            typ_operacji='ROZTANKOWANIE_APOLLO'
        )
        active_transfers = db.session.execute(active_transfers_q).scalars().all()
        
        updated_transfers_list = [{
            'id': op.id,
            'opis': op.opis,
            'czas_rozpoczecia': op.czas_rozpoczecia.strftime('%Y-%m-%d %H:%M:%S') if op.czas_rozpoczecia else None
        } for op in active_transfers]

        socketio.emit('apollo_update', {
            'apollo_list': updated_apollo_list,
            'active_transfers': updated_transfers_list
        })
    except Exception as e:
        print(f"Błąd podczas broadcastu aktualizacji Apollo: {e}")