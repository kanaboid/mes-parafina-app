# app/__init__.py

from flask import Flask
from .config import Config
from .pathfinder_service import PathFinder

# Tworzymy pustą instancję, która zostanie zainicjowana w create_app
pathfinder = PathFinder()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Inicjalizujemy serwis
    pathfinder.init_app(app)
    app.extensions = getattr(app, 'extensions', {})
    app.extensions['pathfinder'] = pathfinder

    # Rejestrujemy blueprinty
    from . import routes
    app.register_blueprint(routes.bp)

    @app.route('/hello')
    def hello():
        return "Witaj w aplikacji MES!"

    return app