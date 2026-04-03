# app.py
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from models import db, User, Exercise, WorkoutTemplate, WorkoutHistory
from flask_login import current_user

# PŘIDEJ PARAMETR test_config=None
def create_app(test_config=None):
    app = Flask(__name__)

    # --- Výchozí Konfigurace ---
    app.config["SECRET_KEY"] = "dev-secret-change-in-production"
    app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://student31:spsnet@dbs.spskladno.cz/vyuka31"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # NOVÉ: Pokud je předána testovací konfigurace, přepíše tu výchozí
    if test_config is not None:
        app.config.update(test_config)

    # --- Až TEĎ se inicializují rozšíření ---
    db.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Pro přístup se musíš přihlásit."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # --- Registrace blueprintů ---
    from routes.auth import auth_bp
    app.register_blueprint(auth_bp)
    from routes.exercises import exercises_bp
    app.register_blueprint(exercises_bp)
    from routes.sablony import sablony_bp
    app.register_blueprint(sablony_bp)
    from routes.trenink import trenink_bp
    app.register_blueprint(trenink_bp)
    from routes.history import historie_bp
    app.register_blueprint(historie_bp)
    from routes.statistics import statistiky_bp
    app.register_blueprint(statistiky_bp)

    # --- Základní routy ---
    @app.route("/")
    def index():
        # Kolik je tam od admina
        predefined_count = Exercise.query.filter_by(user_id=None).count()
        
        templates_count = 0
        workouts_count = 0
        my_exercises_count = 0 # Výchozí nula pro nepřihlášené

        if current_user.is_authenticated:
            templates_count = WorkoutTemplate.query.filter_by(user_id=current_user.id).count()
            workouts_count = WorkoutHistory.query.filter_by(user_id=current_user.id, status="finished").count()
            # Kolik si jich vytvořil uživatel
            my_exercises_count = Exercise.query.filter_by(user_id=current_user.id).count()

        # Sečteme to dohromady pro hlavní velké číslo
        total_exercises = predefined_count + my_exercises_count

        return render_template("index.html", 
                               total_exercises=total_exercises,
                               my_exercises_count=my_exercises_count,
                               templates_count=templates_count,
                               workouts_count=workouts_count)
    return app

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(debug=True)
