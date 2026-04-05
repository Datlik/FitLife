from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app.models import db, WorkoutHistory, WorkoutSet

historie_bp = Blueprint("historie", __name__)

@historie_bp.route("/historie")
@login_required
def index():
    # Vytáhneme všechny DOKONČENÉ tréninky a seřadíme je od nejnovějšího (desc)
    workouts = WorkoutHistory.query.filter_by(
        user_id=current_user.id, 
        status="finished"
    ).order_by(WorkoutHistory.end_time.desc()).all()

    # Spočítáme počet sérií pro každý trénink (jak jsi chtěl v Blueprintu)
    workout_stats = {}
    for w in workouts:
        sets_count = WorkoutSet.query.filter_by(workout_id=w.id).count()
        workout_stats[w.id] = sets_count

    return render_template("historie.html", workouts=workouts, stats=workout_stats, detail_mode=False)

@historie_bp.route("/historie/<int:workout_id>")
@login_required
def detail(workout_id):
    # Detail konkrétního tréninku
    workout = WorkoutHistory.query.get_or_404(workout_id)

    # Bezpečnost: Nikdo nesmí vidět cizí tréninky
    if workout.user_id != current_user.id:
        flash("K tomuto tréninku nemáš přístup.", "error")
        return redirect(url_for("historie.index"))

    # Vytáhneme a seskupíme série podle cviků (stejně jako u aktivního tréninku)
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
    if request.form.get("_csrf_token") != session.get("_csrf_token"):
        flash("Neplatný požadavek.", "error")
        return redirect(url_for("historie.index"))

    workout = WorkoutHistory.query.get_or_404(workout_id)

    if workout.user_id != current_user.id:
        flash("Nemůžeš smazat cizí trénink.", "error")
        return redirect(url_for("historie.index"))

    # POUČENÍ Z MINULA: Nejdřív smažeme všechny série (Papíry)!
    WorkoutSet.query.filter_by(workout_id=workout.id).delete()
    
    # Až pak můžeme smazat samotný trénink (Složku)
    db.session.delete(workout)
    db.session.commit()

    flash("Trénink byl úspěšně smazán z historie.", "info")
    return redirect(url_for("historie.index"))