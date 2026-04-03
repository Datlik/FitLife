from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

# --- Spojovací tabulka: WorkoutTemplate <-> Exercise ---
template_exercises = db.Table(
    "template_exercises",
    db.Column("template_id", db.Integer, db.ForeignKey("workout_template.id"), nullable=False),
    db.Column("exercise_id", db.Integer, db.ForeignKey("exercise.id"), nullable=False),
    db.Column("position", db.Integer, nullable=False, default=0),
)


class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    # Vztahy
    exercises = db.relationship("Exercise", backref="owner", lazy=True,
                                foreign_keys="Exercise.user_id", cascade="all, delete-orphan")
    templates = db.relationship("WorkoutTemplate", backref="owner", lazy=True, cascade="all, delete-orphan")
    workouts = db.relationship("WorkoutHistory", backref="owner", lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.email}>"


class Exercise(db.Model):
    __tablename__ = "exercise"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    equipment = db.Column(db.String(50), nullable=True)
    primary_muscle = db.Column(db.String(50), nullable=True)
    is_custom = db.Column(db.Boolean, default=False, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

    # NULL = cvik vytvořený adminem přes PyQt app
    # user_id = cvik vytvořený přihlášeným uživatelem na webu (is_custom = True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    # Vztahy
    sets = db.relationship("WorkoutSet", backref="exercise", lazy=True)

    def __repr__(self):
        return f"<Exercise {self.name}>"


class WorkoutTemplate(db.Model):
    __tablename__ = "workout_template"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)  # NULL = globální šablona, jinak vlastní
    is_public = db.Column(db.Boolean, default=False, nullable=False)

    # Many-to-many přes template_exercises
    exercises = db.relationship("Exercise", secondary=template_exercises, lazy=True)

    def __repr__(self):
        return f"<WorkoutTemplate {self.name}>"


class WorkoutHistory(db.Model):
    __tablename__ = "workout_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    end_time = db.Column(db.DateTime, nullable=True)
    duration = db.Column(db.Integer, nullable=True)          # v minutách
    total_volume = db.Column(db.Float, nullable=True)        # SUM(reps * weight)
    rating = db.Column(db.String(10), nullable=True)         # emoji
    status = db.Column(db.String(20), default="active", nullable=False)  # active / finished / cancelled

    # Vztahy
    sets = db.relationship("WorkoutSet", backref="workout", lazy=True,
                           cascade="all, delete-orphan")

    def __repr__(self):
        return f"<WorkoutHistory id={self.id} status={self.status}>"


class WorkoutSet(db.Model):
    __tablename__ = "workout_set"

    id = db.Column(db.Integer, primary_key=True)
    workout_id = db.Column(db.Integer, db.ForeignKey("workout_history.id"), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey("exercise.id"), nullable=False)
    reps = db.Column(db.Integer, nullable=False)
    weight = db.Column(db.Float, nullable=False)
    intensity = db.Column(db.Integer, nullable=False)        # 1–9

    def __repr__(self):
        return f"<WorkoutSet {self.reps}x{self.weight}kg @{self.intensity}>"
