# manage.py
import click
from app import create_app
from app.sensors import SensorService
from app.extensions import db
from tabulate import tabulate

# Tworzymy instancję aplikacji, aby mieć dostęp do jej kontekstu
# Jest to konieczne, aby SensorService mógł korzystać z `db.session`
app = create_app()

@app.cli.command("set-temp")
@click.argument("temperatura", type=float)
@click.argument("sprzety", nargs=-1)
def set_temp_command(temperatura, sprzety):
    """
    Ustawia temperaturę dla podanego sprzętu.

    Przykład użycia:
    flask set-temp 85.5 R1 R2 FZ1
    flask set-temp 60.0 -- --wszystkie-reaktory
    """
    equipment_to_update = list(sprzety)

    # Opcja specjalna do aktualizacji wszystkich reaktorów
    if "--all" in equipment_to_update:
        # W przyszłości można to przenieść do serwisu, ale dla prostoty jest tutaj
        from app.models import Sprzet
        with app.app_context():
            equipment_to_update = db.session.execute(
                db.select(Sprzet.nazwa_unikalna).where(Sprzet.typ_sprzetu.in_(['reaktor', 'apollo', 'beczka_brudna', 'beczka_czysta']))
            ).scalars().all()

    if not equipment_to_update:
        click.echo("Błąd: Nie podano żadnego sprzętu do aktualizacji.")
        return

    click.echo(f"Próba ustawienia temperatury {temperatura}°C dla sprzętu: {', '.join(equipment_to_update)}...")
    
    # Wywołujemy naszą nową metodę serwisową w kontekście aplikacji
    with app.app_context():
        updated = SensorService.set_temperature_for_multiple(equipment_to_update, temperatura)

    if updated:
        click.echo(click.style("Sukces!", fg="green"))
        click.echo(f"Zaktualizowano temperaturę dla: {', '.join(updated)}")
    else:
        click.echo(click.style("Nie udało się zaktualizować żadnego sprzętu.", fg="yellow"))

@app.cli.command("show-temp")
@click.argument("sprzety", nargs=-1)
def show_temp_command(sprzety):
    """
    Wyświetla aktualną i docelową temperaturę dla podanego sprzętu.

    Przykład użycia:
    flask show-temp R1 R2
    flask show-temp -- --wszystkie-reaktory
    flask show-temp
    """
    equipment_to_show = list(sprzety)

    # Domyślnie, jeśli nie podano argumentów, pokaż wszystkie reaktory i apollo
    if not equipment_to_show:
        from app.models import Sprzet
        with app.app_context():
            equipment_to_show = db.session.execute(
                db.select(Sprzet.nazwa_unikalna).where(Sprzet.typ_sprzetu.in_(['reaktor', 'apollo', 'beczka_brudna', 'beczka_czysta']))
            ).scalars().all()
    
    # Obsługa flagi --wszystkie-reaktory
    elif "--wszystkie-reaktory" in equipment_to_show:
        from app.models import Sprzet
        with app.app_context():
            equipment_to_show = db.session.execute(
                db.select(Sprzet.nazwa_unikalna).where(Sprzet.typ_sprzetu == 'reaktor')
            ).scalars().all()

    if not equipment_to_show:
        click.echo("Nie znaleziono sprzętu do wyświetlenia.")
        return

    # Wywołaj metodę serwisową
    with app.app_context():
        temperatures_data = SensorService.get_temperatures_for_multiple(equipment_to_show)

    if not temperatures_data:
        click.echo("Nie znaleziono danych dla podanego sprzętu.")
        return

    # Przygotuj dane do tabeli
    headers = ["Nazwa Sprzętu", "Temperatura Aktualna", "Temperatura Docelowa"]
    table_data = [
        [
            item['nazwa'],
            f"{item['aktualna']} °C" if item['aktualna'] is not None else "Brak danych",
            f"{item['docelowa']} °C" if item['docelowa'] is not None else "Brak danych"
        ]
        for item in temperatures_data
    ]

    # Wyświetl sformatowaną tabelę
    click.echo(tabulate(table_data, headers=headers, tablefmt="grid"))