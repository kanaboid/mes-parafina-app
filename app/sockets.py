# app/sockets.py

from app import socketio
from flask_socketio import emit
from tabulate import tabulate # <--- DODAJ IMPORT

# Importujemy nasze serwisy i modele, aby mieć do nich dostęp
from app.sensors import SensorService
from app.models import Sprzet
from app import db
from decimal import Decimal, InvalidOperation


@socketio.on('connect')
def handle_connect():
    """Wykonywane, gdy klient (przeglądarka) nawiązuje połączenie."""
    print('Klient połączony!')
    emit('response', {'data': 'Połączono z serwerem. Witaj w konsoli administracyjnej!'})
    emit('response', {'data': 'Wpisz "help", aby zobaczyć dostępne komendy.'})


@socketio.on('command_from_client') # <--- ZMIANA NAZWY ZDARZENIA
def handle_command(json_data):
    """Odbiera i przetwarza komendy od klienta."""
    command_string = json_data.get('data', '').strip()
    if not command_string:
        return

    parts = command_string.split()
    command = parts[0].lower()
    args = parts[1:]

    print(f"Otrzymano komendę: '{command}' z argumentami: {args}")

    # --- Router komend ---
    if command == 'show-temp':
        handle_show_temp(args)
    elif command == 'set-temp':
        handle_set_temp(args)
    elif command == 'help':
        handle_help()
    else:
        emit('response', {
            'data': f"Błąd: Nieznana komenda '{command}'. Wpisz 'help' po pomoc.",
            'is_error': True
        })

def handle_help():
    """Wysyła do klienta listę dostępnych komend."""
    help_text = """
Dostępne komendy:
  show-temp [sprzet1] [sprzet2] ...   - Wyświetla temperatury dla podanego sprzętu.
                                        Jeśli brak argumentów, pokazuje reaktory, apollo i beczki.
                                        Można użyć flagi -- reaktory.

  set-temp <temp> <sprzet1> ...        - Ustawia temperaturę dla podanego sprzętu. Można użyć flagi --reaktory lub --all.
"""
    emit('response', {'data': help_text})

def handle_show_temp(args):
    """Logika dla komendy show-temp."""
    try:
        equipment_to_show = args

        # Logika wyboru sprzętu, taka sama jak w manage.py
        if not equipment_to_show:
            equipment_to_show = db.session.execute(
                db.select(Sprzet.nazwa_unikalna).where(Sprzet.typ_sprzetu.in_(['reaktor', 'apollo', 'beczka_brudna', 'beczka_czysta']))
            ).scalars().all()
        elif "--reaktory" in equipment_to_show:
            equipment_to_show = db.session.execute(
                db.select(Sprzet.nazwa_unikalna).where(Sprzet.typ_sprzetu == 'reaktor')
            ).scalars().all()

        if not equipment_to_show:
            emit('response', {'data': "Nie znaleziono sprzętu do wyświetlenia."})
            return

        # Wywołanie serwisu
        temperatures_data = SensorService.get_temperatures_for_multiple(equipment_to_show)

        if not temperatures_data:
            emit('response', {'data': "Nie znaleziono danych dla podanego sprzętu."})
            return

        # Przygotowanie danych do tabeli
        headers = ["Nazwa Sprzętu", "Aktualna", "Docelowa"]
        table_data = [
            [
                item['nazwa'],
                f"{item['aktualna']}°C" if item['aktualna'] is not None else "B/D",
                f"{item['docelowa']}°C" if item['docelowa'] is not None else "B/D"
            ]
            for item in temperatures_data
        ]

        # Sformatuj tabelę jako string i odeślij do klienta
        formatted_table = tabulate(table_data, headers=headers, tablefmt="presto")
        emit('response', {'data': formatted_table})

    except Exception as e:
        print(f"Błąd podczas wykonywania show-temp: {e}")
        emit('response', {
            'data': f"Wystąpił błąd serwera: {e}",
            'is_error': True
        })

def handle_set_temp(args):
    """Logika dla komendy set-temp."""
    try:
        # 1. Walidacja argumentów
        if len(args) < 2:
            emit('response', {
                'data': 'Błąd: Niewystarczająca liczba argumentów.\nUżycie: set-temp <temperatura> <sprzet1> [sprzet2] ...',
                'is_error': True
            })
            return
        
        # 2. Parsowanie argumentów
        try:
            temperatura = Decimal(args[0])
        except InvalidOperation:
            emit('response', {
                'data': f"Błąd: Nieprawidłowa wartość temperatury: '{args[0]}'. Podaj liczbę.",
                'is_error': True
            })
            return

        equipment_to_update = args[1:]
        
        # 3. Obsługa flagi --wszystkie-reaktory
        if "--reaktory" in equipment_to_update:
            equipment_to_update = db.session.execute(
                db.select(Sprzet.nazwa_unikalna).where(Sprzet.typ_sprzetu == 'reaktor')
            ).scalars().all()
        elif "--all" in equipment_to_update:
            equipment_to_update = db.session.execute(
                db.select(Sprzet.nazwa_unikalna).where(Sprzet.typ_sprzetu.in_(['reaktor', 'apollo', 'beczka_brudna', 'beczka_czysta']))
            ).scalars().all()

        if not equipment_to_update:
            emit('response', {'data': "Błąd: Nie podano żadnego sprzętu do aktualizacji.", 'is_error': True})
            return

        # 4. Wywołanie serwisu
        emit('response', {'data': f"Próba ustawienia temperatury {temperatura}°C dla: {', '.join(equipment_to_update)}..."})
        
        updated = SensorService.set_temperature_for_multiple(equipment_to_update, temperatura)

        # 5. Wysłanie odpowiedzi zwrotnej
        if updated:
            emit('response', {
                'data': f"Sukces!\nZaktualizowano temperaturę dla: {', '.join(updated)}",
            })
        else:
            emit('response', {
                'data': "Nie udało się zaktualizować żadnego z podanych sprzętów (sprawdź nazwy).",
                'is_error': True
            })

    except Exception as e:
        print(f"Błąd podczas wykonywania set-temp: {e}")
        emit('response', {
            'data': f"Wystąpił krytyczny błąd serwera: {e}",
            'is_error': True
        })