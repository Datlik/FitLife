"""
models.py – Definice databázových modelů (tabulek) aplikace FitLife.

Obsahuje 5 modelů a 1 spojovací tabulku:
- User: Registrovaní uživatelé s hashovanými hesly
- Exercise: Katalog cviků (globální od admina + vlastní od uživatelů)
- WorkoutTemplate: Tréninkové šablony/plány (M:N vazba s Exercise)
- WorkoutHistory: Záznamy o provedených trénincích
- WorkoutSet: Jednotlivé série (váha, opakování, intenzita)
- template_exercises: Spojovací tabulka pro M:N vazbu šablon a cviků
"""

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
from .extensions import db


# Spojovací tabulka M:N (WorkoutTemplate <-> Exercise)
template_exercises = db.Table(
    "template_exercises",
    db.Column("template_id", db.Integer, db.ForeignKey("workout_template.id"), nullable=False),
    db.Column("exercise_id", db.Integer, db.ForeignKey("exercise.id"), nullable=False),
    db.Column("position", db.Integer, nullable=False, default=0),
)


class User(UserMixin, db.Model):
    """Model uživatele. UserMixin přidává metody potřebné pro Flask-Login is_authenticated atd"""
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    exercises = db.relationship("Exercise", backref="owner", lazy=True,
                                foreign_keys="Exercise.user_id", cascade="all, delete-orphan")
    templates = db.relationship("WorkoutTemplate", backref="owner", lazy=True, cascade="all, delete-orphan")
    workouts = db.relationship("WorkoutHistory", backref="owner", lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        """Zašifruje heslo pomocí Werkzeug PBKDF2 a uloží hash."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Ověří zadané heslo proti uloženému hashi. Vrací True/False."""
        return check_password_hash(self.password_hash, password)


class Exercise(db.Model):
    """Model cviku. Pokud je user_id=NULL, jde o globální cvik vytvořený adminem."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    equipment = db.Column(db.String(50))
    primary_muscle = db.Column(db.String(50))
    is_custom = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)  # Soft-delete

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    sets = db.relationship("WorkoutSet", backref="exercise", lazy=True)


class WorkoutTemplate(db.Model):
    """Model tréninkové šablony. Pokud je user_id=NULL, jde o globální šablonu."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    is_public = db.Column(db.Boolean, default=False)

    # M:N vazba přes spojovací tabulku template_exercises
    exercises = db.relationship("Exercise", secondary=template_exercises, lazy=True)


class WorkoutHistory(db.Model):
    """Model záznamu o tréninku. Status může být: 'active', 'finished', 'cancelled'."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    start_time = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)
    end_time = db.Column(db.DateTime, nullable=True)
    duration = db.Column(db.Integer, nullable=True)       # Doba trvání v minutách
    total_volume = db.Column(db.Float, nullable=True)     # Celkový objem: SUM(reps * weight)
    rating = db.Column(db.String(10), nullable=True)
    status = db.Column(db.String(20), default="active", nullable=False)

    # cascade="all, delete-orphan": při smazání tréninku se automaticky smažou i série
    sets = db.relationship("WorkoutSet", backref="workout", lazy=True, cascade="all, delete-orphan")


class WorkoutSet(db.Model):
    """Model jedné série v tréninku – kolik opakování, s jakou váhou a intenzitou (RPE 1-9)."""
    id = db.Column(db.Integer, primary_key=True)
    workout_id = db.Column(db.Integer, db.ForeignKey("workout_history.id"), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey("exercise.id"), nullable=False)
    reps = db.Column(db.Integer, nullable=False)
    weight = db.Column(db.Float, nullable=False)
    intensity = db.Column(db.Integer, nullable=False)     # RPE stupnice 1-9
