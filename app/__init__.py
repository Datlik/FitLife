from flask import Flask
from .extensions import db, login_manager

def create_app(test_config=None):
    app = Flask(__name__)

    # --- Výchozí Konfigurace ---
    if test_config is not None:
        app.config.update(test_config)
    else:
        app.config.from_object("config.Config")

    # --- Až TEĎ se inicializují rozšíření ---
    db.init_app(app)
    
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Pro přístup se musíš přihlásit."
    login_manager.login_message_category = "warning"

    from . import models
    @login_manager.user_loader
    def load_user(user_id):
        return models.User.query.get(int(user_id))

    # --- Registrace blueprintů ---
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
