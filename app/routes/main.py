from flask import Blueprint, render_template
from flask_login import current_user
from app.models import Exercise, WorkoutTemplate, WorkoutHistory

main_bp = Blueprint("main", __name__)

@main_bp.route("/")
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
