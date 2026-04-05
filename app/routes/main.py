"""
main.py – Hlavní stránka aplikace (Dashboard).

Zobrazuje přehledové statistiky – počet cviků, šablon a odcvičených tréninků.
Pro nepřihlášené uživatele zobrazuje pouze veřejné informace.
"""

from flask import Blueprint, render_template
from flask_login import current_user
from app.models import Exercise, WorkoutTemplate, WorkoutHistory

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    """Vykreslí úvodní dashboard s přehledovými čísly.

    Nepřihlášený uživatel vidí pouze počet globálních cviků.
    Přihlášený uživatel vidí navíc své šablony, vlastní cviky a počet tréninků.
    """
    predefined_count = Exercise.query.filter_by(user_id=None).count()

    templates_count = 0
    workouts_count = 0
    my_exercises_count = 0

    if current_user.is_authenticated:
        templates_count = WorkoutTemplate.query.filter_by(user_id=current_user.id).count()
        workouts_count = WorkoutHistory.query.filter_by(user_id=current_user.id, status="finished").count()
        my_exercises_count = Exercise.query.filter_by(user_id=current_user.id).count()

    total_exercises = predefined_count + my_exercises_count

    return render_template("index.html",
                           total_exercises=total_exercises,
                           my_exercises_count=my_exercises_count,
                           templates_count=templates_count,
                           workouts_count=workouts_count)
