"""
history.py – Modul pro prohlížení a správu historie tréninků.

Umožňuje zobrazit seznam dokončených tréninků, detail konkrétního tréninku
a smazat trénink z historie (s kaskádovým smazáním sérií).
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app.models import db, WorkoutHistory, WorkoutSet

historie_bp = Blueprint("historie", __name__)


@historie_bp.route("/historie")
@login_required
def index():
    """Zobrazí seznam všech dokončených tréninků seřazených od nejnovějšího.

    Pro každý trénink spočítá počet odcvičených sérií pro zobrazení ve statistice.
    """
    workouts = WorkoutHistory.query.filter_by(
        user_id=current_user.id,
        status="finished"
    ).order_by(WorkoutHistory.end_time.desc()).all()

    # Slovník {workout_id: počet_sérií} pro zobrazení v šabloně
    workout_stats = {}
    for w in workouts:
        sets_count = WorkoutSet.query.filter_by(workout_id=w.id).count()
        workout_stats[w.id] = sets_count

    return render_template("historie.html", workouts=workouts, stats=workout_stats, detail_mode=False)


@historie_bp.route("/historie/<int:workout_id>")
@login_required
def detail(workout_id):
    """Zobrazí detail konkrétního tréninku se všemi sériemi seskupenými podle cviků.

    Obsahuje bezpečnostní kontrolu – uživatel může vidět pouze své vlastní tréninky.
    """
    workout = WorkoutHistory.query.get_or_404(workout_id)

    if workout.user_id != current_user.id:
        flash("K tomuto tréninku nemáš přístup.", "error")
        return redirect(url_for("historie.index"))

    # Seskupíme série podle cviku do slovníku {Exercise: [WorkoutSet, ...]}
    sets = WorkoutSet.query.filter_by(workout_id=workout.id).all()
    exercises_in_workout = {}
    for s in sets:
        if s.exercise not in exercises_in_workout:
            exercises_in_workout[s.exercise] = []
        exercises_in_workout[s.exercise].append(s)

    return render_template("historie.html", workout=workout, exercises=exercises_in_workout, detail_mode=True)


@historie_bp.route("/historie/smazat/<int:workout_id>", methods=["POST"])
@login_required
def smazat(workout_id):
    """Smaže trénink z historie. Díky cascade='all, delete-orphan' se automaticky smažou i série."""
    if request.form.get("_csrf_token") != session.get("_csrf_token"):
        flash("Neplatný požadavek.", "error")
        return redirect(url_for("historie.index"))

    workout = WorkoutHistory.query.get_or_404(workout_id)

    if workout.user_id != current_user.id:
        flash("Nemůžeš smazat cizí trénink.", "error")
        return redirect(url_for("historie.index"))

    # SQLAlchemy cascade="all, delete-orphan" na modelu automaticky smaže i série
    db.session.delete(workout)
    db.session.commit()

    flash("Trénink byl úspěšně smazán z historie.", "info")
    return redirect(url_for("historie.index"))