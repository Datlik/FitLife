"""
exercises.py – Modul pro správu katalogu cviků.

Umožňuje uživateli prohlížet předdefinované (globální) cviky,
vytvářet vlastní cviky a mazat je (soft-delete přes příznak is_deleted).
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app.models import db, Exercise, WorkoutSet, WorkoutTemplate

exercises_bp = Blueprint("exercises", __name__)


@exercises_bp.route("/cviky", methods=["GET", "POST"])
@login_required
def cviky():
    """Zobrazí katalog cviků a zpracuje formulář pro vytvoření nového vlastního cviku.

    GET: Načte předdefinované (admin) cviky a vlastní cviky uživatele.
    POST: Vytvoří nový cvik s vazbou na aktuálního uživatele (is_custom=True).
    """
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        muscle = request.form.get("primary_muscle")
        equipment = request.form.get("equipment")

        if not name:
            flash("Název cviku je povinný.", "error")
            return redirect(url_for("exercises.cviky") + "#moje-cviky")

        new_exercise = Exercise(
            name=name,
            primary_muscle=muscle,
            equipment=equipment,
            is_custom=True,
            user_id=current_user.id
        )

        db.session.add(new_exercise)
        db.session.commit()

        flash(f"Cvik '{name}' byl úspěšně přidán!", "success")
        return redirect(url_for("exercises.cviky") + "#moje-cviky")

    # GET: Globální cviky (user_id=None) a vlastní cviky aktuálního uživatele
    predefined_exercises = Exercise.query.filter_by(user_id=None, is_deleted=False).all()
    my_exercises = Exercise.query.filter_by(user_id=current_user.id, is_deleted=False).all()

    return render_template("exercises.html",
                           predefined=predefined_exercises,
                           my_exercises=my_exercises)


@exercises_bp.route("/cviky/smazat/<int:exercise_id>", methods=["POST"])
@login_required
def smazat_cvik(exercise_id):
    """Soft-delete cviku – nastaví příznak is_deleted=True místo fyzického smazání.

    Cvik zůstane v databázi kvůli zachování historie tréninků.
    Před smazáním se cvik odebere ze všech šablon, ve kterých figuruje.
    Globální cviky (od admina) nelze mazat přes web.
    """
    if request.form.get("_csrf_token") != session.get("_csrf_token"):
        flash("Neplatný požadavek (CSRF).", "error")
        return redirect(url_for("exercises.cviky") + "#moje-cviky")

    exercise = Exercise.query.get_or_404(exercise_id)

    # Globální cviky smí mazat pouze admin přes PyQt aplikaci
    if exercise.user_id is None:
        flash("Globální cviky lze mazat pouze přes administrátorskou aplikaci.", "error")
        return redirect(url_for("exercises.cviky") + "#moje-cviky")

    if exercise.user_id != current_user.id:
        flash("Nemůžeš smazat cvik, který ti nepatří!", "error")
        return redirect(url_for("exercises.cviky") + "#moje-cviky")

    # Odebereme cvik ze všech šablon (M:N vazba)
    templates_with_exercise = WorkoutTemplate.query.filter(WorkoutTemplate.exercises.contains(exercise)).all()
    for tpl in templates_with_exercise:
        tpl.exercises.remove(exercise)

    # Soft-delete: cvik zůstane v DB, ale nebude se zobrazovat v katalozích
    name = exercise.name
    exercise.is_deleted = True
    db.session.commit()

    flash(f"Cvik '{name}' byl úspěšně odstraněn ze šablon a knihovny, ale zůstane ve tvé historii.", "info")
    return redirect(url_for("exercises.cviky") + "#moje-cviky")