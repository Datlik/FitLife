"""
trenink.py – Modul pro správu aktivního tréninku.

Obsahuje routy pro zahájení, průběh a dokončení tréninku.
Uživatel může přidávat/odebírat cviky a zapisovat série (váha, opakování, intenzita).
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app.models import db, WorkoutHistory, WorkoutSet, WorkoutTemplate, Exercise
from datetime import datetime, timezone


def utcnow():
    """Vrátí aktuální UTC čas bez časové zóny (naive), kompatibilní s MySQL."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


trenink_bp = Blueprint("trenink", __name__)


@trenink_bp.route("/trenink")
@login_required
def index():
    """Zobrazí stránku tréninku – buď startovací obrazovku, nebo probíhající trénink.

    Pokud uživatel nemá žádný aktivní trénink, zobrazí se mu možnost
    zahájit nový (prázdný nebo ze šablony). Pokud trénink běží,
    zobrazí se přehled cviků, zapsaných sérií a formulář pro přidání dalších.
    """
    active_workout = WorkoutHistory.query.filter_by(user_id=current_user.id, status="active").first()

    if not active_workout:
        my_templates = WorkoutTemplate.query.filter_by(user_id=current_user.id).all()
        return render_template("trenink.html", workout=None, templates=my_templates)

    # Vytáhneme všechny série a seskupíme je podle cviku do slovníku {Exercise: [WorkoutSet, ...]}
    sets = WorkoutSet.query.filter_by(workout_id=active_workout.id).all()
    exercises_in_workout = {}
    for s in sets:
        if s.exercise not in exercises_in_workout:
            exercises_in_workout[s.exercise] = []
        # Dummy série (reps=0, weight=0) slouží jen jako placeholder pro zobrazení bloku
        if s.reps > 0 or s.weight > 0:
            exercises_in_workout[s.exercise].append(s)

    # Načteme všechny nesmazané cviky pro dropdown "Přidat další cvik"
    predefined = Exercise.query.filter_by(user_id=None, is_deleted=False).all()
    mine = Exercise.query.filter_by(user_id=current_user.id, is_deleted=False).all()
    all_exercises = predefined + mine

    return render_template("trenink.html",
                           workout=active_workout,
                           exercises_in_workout=exercises_in_workout,
                           all_exercises=all_exercises)


@trenink_bp.route("/trenink/start", methods=["POST"])
@trenink_bp.route("/trenink/start/<int:template_id>", methods=["POST"])
@login_required
def start(template_id=None):
    """Zahájí nový trénink. Volitelně předvyplní cviky ze šablony.

    Pokud už existuje rozpracovaný trénink, automaticky ho zruší (status='cancelled').
    Při startu ze šablony se pro každý cvik vytvoří dummy série (reps=0, weight=0),
    aby se v UI zobrazil prázdný blok připravený k vyplnění.
    """
    if request.form.get("_csrf_token") != session.get("_csrf_token"):
        flash("Neplatný požadavek.", "error")
        return redirect(url_for("trenink.index"))

    # Zrušíme případný předchozí nedokončený trénink
    old_active = WorkoutHistory.query.filter_by(user_id=current_user.id, status="active").first()
    if old_active:
        old_active.status = "cancelled"
        old_active.end_time = utcnow()
        flash("Předchozí nedokončený trénink byl zrušen.", "warning")

    # Založíme nový záznam v tabulce workout_history
    new_workout = WorkoutHistory(user_id=current_user.id, status="active", start_time=utcnow())
    db.session.add(new_workout)
    db.session.flush()  # flush() nám přiřadí ID ještě před commit()

    # Pokud se startuje ze šablony, předvyplníme cviky jako dummy série
    if template_id:
        tpl = WorkoutTemplate.query.get(template_id)
        if tpl and (tpl.user_id == current_user.id or tpl.user_id is None):
            for ex in tpl.exercises:
                dummy_set = WorkoutSet(workout_id=new_workout.id, exercise_id=ex.id, reps=0, weight=0, intensity=1)
                db.session.add(dummy_set)

    db.session.commit()
    flash("Trénink zahájen! Ať to roste.", "success")
    return redirect(url_for("trenink.index"))


@trenink_bp.route("/trenink/pridat_cvik", methods=["POST"])
@login_required
def pridat_cvik():
    """Přidá nový cvik do probíhajícího tréninku jako prázdný blok (dummy série)."""
    if request.form.get("_csrf_token") != session.get("_csrf_token"):
        flash("Neplatný požadavek.", "error")
        return redirect(url_for("trenink.index"))

    active_workout = WorkoutHistory.query.filter_by(user_id=current_user.id, status="active").first()
    exercise_id = request.form.get("exercise_id")

    if active_workout and exercise_id:
        dummy_set = WorkoutSet(workout_id=active_workout.id, exercise_id=exercise_id, reps=0, weight=0, intensity=1)
        db.session.add(dummy_set)
        db.session.commit()

    # Přesměrování na HTML kotvu cviku, aby stránka odskrolovala na správné místo
    return redirect(url_for("trenink.index") + f"#cvik-{exercise_id}")


@trenink_bp.route("/trenink/odebrat_cvik", methods=["POST"])
@login_required
def odebrat_cvik():
    """Odebere cvik (a všechny jeho série) z probíhajícího tréninku."""
    if request.form.get("_csrf_token") != session.get("_csrf_token"):
        flash("Neplatný požadavek.", "error")
        return redirect(url_for("trenink.index"))

    active_workout = WorkoutHistory.query.filter_by(user_id=current_user.id, status="active").first()
    exercise_id = request.form.get("exercise_id")

    if active_workout and exercise_id:
        WorkoutSet.query.filter_by(workout_id=active_workout.id, exercise_id=exercise_id).delete()
        db.session.commit()
        flash("Cvik byl odebrán z tréninku.", "info")

    return redirect(url_for("trenink.index"))


@trenink_bp.route("/trenink/pridat_serii", methods=["POST"])
@login_required
def pridat_serii():
    """Zapíše novou sérii (váha, opakování, intenzita) k danému cviku v aktivním tréninku."""
    if request.form.get("_csrf_token") != session.get("_csrf_token"):
        flash("Neplatný požadavek.", "error")
        return redirect(url_for("trenink.index"))

    active_workout = WorkoutHistory.query.filter_by(user_id=current_user.id, status="active").first()
    if not active_workout:
        return redirect(url_for("trenink.index"))

    exercise_id = request.form.get("exercise_id")

    # Ošetření neplatných vstupů (např. písmena místo čísel)
    try:
        reps = int(request.form.get("reps", 0))
        weight = float(request.form.get("weight", 0.0))
        intensity = int(request.form.get("intensity", 5))
    except (ValueError, TypeError):
        flash("Neplatné hodnoty. Zadej čísla.", "error")
        return redirect(url_for("trenink.index") + f"#cvik-{exercise_id}")

    new_set = WorkoutSet(workout_id=active_workout.id, exercise_id=exercise_id, reps=reps, weight=weight, intensity=intensity)
    db.session.add(new_set)
    db.session.commit()

    return redirect(url_for("trenink.index") + f"#cvik-{exercise_id}")


@trenink_bp.route("/trenink/dokoncit", methods=["POST"])
@login_required
def dokoncit():
    """Ukončí aktivní trénink – vypočítá dobu trvání, celkový objem a odstraní dummy série.

    Celkový objem (tonnage) = suma(reps * weight) přes všechny série.
    Dummy série (reps=0, weight=0) se po dokončení smažou, protože sloužily
    jen jako vizuální placeholder pro zobrazení bloku cviku.
    """
    active_workout = WorkoutHistory.query.filter_by(user_id=current_user.id, status="active").first()
    if not active_workout:
        return redirect(url_for("trenink.index"))

    # Výpočet doby trvání v minutách
    active_workout.end_time = utcnow()
    duration_delta = active_workout.end_time - active_workout.start_time
    active_workout.duration = int(duration_delta.total_seconds() / 60)

    # Výpočet celkového objemu (tonnage)
    sets = WorkoutSet.query.filter_by(workout_id=active_workout.id).all()
    total_vol = sum(s.reps * s.weight for s in sets)

    active_workout.total_volume = total_vol
    active_workout.status = "finished"

    # Vyčištění dummy sérií z databáze
    for s in sets:
        if s.reps == 0 and s.weight == 0:
            db.session.delete(s)

    db.session.commit()
    flash(f"Skvělá práce! Trénink dokončen. Čas: {active_workout.duration} min, Objem: {total_vol} kg.", "success")
    return redirect(url_for("main.index"))