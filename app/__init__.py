"""
__init__.py – Application Factory pro Flask aplikaci FitLife.

Funkce create_app() vytvoří a nakonfiguruje instanci Flask aplikace,
inicializuje rozšíření (SQLAlchemy, Flask-Login) a zaregistruje všechny blueprinty.
Tento vzor umožňuje snadné testování s různými konfiguracemi.
"""

from flask import Flask
from .extensions import db, login_manager


def create_app(test_config=None):
    """Vytvoří a vrátí nakonfigurovanou Flask aplikaci.

    Args:
        test_config: Slovník s testovací konfigurací (např. SQLite in-memory).
                     Pokud je None, načte se produkční konfigurace z config.py.
    """
    app = Flask(__name__)

    if test_config is not None:
        app.config.update(test_config)
    else:
        app.config.from_object("config.Config")

    # Inicializace rozšíření s aplikací
    db.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Pro přístup se musíš přihlásit."
    login_manager.login_message_category = "warning"

    # Callback pro Flask-Login – načte uživatele podle ID uloženého v session
    from . import models
    @login_manager.user_loader
    def load_user(user_id):
        """Flask-Login volá tuto funkci při každém požadavku pro načtení přihlášeného uživatele."""
        return models.User.query.get(int(user_id))

    # Registrace blueprintů (modulů) – každý modul obsluhuje svou část URL
    from .routes.main import main_bp
    from .routes.auth import auth_bp
    from .routes.exercises import exercises_bp
    from .routes.sablony import sablony_bp
    from .routes.trenink import trenink_bp
    from .routes.history import historie_bp
    from .routes.statistics import statistiky_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(exercises_bp)
    app.register_blueprint(sablony_bp)
    app.register_blueprint(trenink_bp)
    app.register_blueprint(historie_bp)
    app.register_blueprint(statistiky_bp)

    return app
