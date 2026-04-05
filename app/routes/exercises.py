from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import db, Exercise
from app.models import db, Exercise, WorkoutSet, WorkoutTemplate

exercises_bp = Blueprint("exercises", __name__)

@exercises_bp.route("/cviky", methods=["GET", "POST"])
@login_required
def cviky():
    if request.method == "POST":
        # Zpracování formuláře pro nový vlastní cvik
        name = request.form.get("name", "").strip()
        muscle = request.form.get("primary_muscle")
        equipment = request.form.get("equipment")

        if not name:
            flash("Název cviku je povinný.", "error")
            return redirect(url_for("exercises.cviky") + "#moje-cviky")

        # Vytvoření nového cviku s vazbou na aktuálního uživatele
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

    # GET request: Načtení dat pro zobrazení
    # user_id == None znamená předdefinovaný globální cvik (od admina)
    predefined_exercises = Exercise.query.filter_by(user_id=None, is_deleted=False).all()
    # Cviky patřící pouze přihlášenému uživateli
    my_exercises = Exercise.query.filter_by(user_id=current_user.id, is_deleted=False).all()

    return render_template("exercises.html", 
                           predefined=predefined_exercises, 
                           my_exercises=my_exercises)

from flask import session # Ujisti se, že nahoře importuješ session pro CSRF kontrolu

@exercises_bp.route("/cviky/smazat/<int:exercise_id>", methods=["POST"])
@login_required
def smazat_cvik(exercise_id):
    if request.form.get("_csrf_token") != session.get("_csrf_token"):
        flash("Neplatný požadavek (CSRF).", "error")
        return redirect(url_for("exercises.cviky") + "#moje-cviky")

    exercise = Exercise.query.get_or_404(exercise_id)
    
    # Bezpečnostní kontrola!
    # Globální cviky (user_id is None) smí mazat pouze admin přes PyQt aplikaci.
    if exercise.user_id is None:
        flash("Globální cviky lze mazat pouze přes administrátorskou aplikaci.", "error")
        return redirect(url_for("exercises.cviky") + "#moje-cviky")

    if exercise.user_id != current_user.id:
        flash("Nemůžeš smazat cvik, který ti nepatří!", "error")
        return redirect(url_for("exercises.cviky") + "#moje-cviky")
        
    # KROK 1 (NOVÉ): Najdeme všechny ŠABLONY, které tento cvik obsahují, a odstraníme ho z nich
    templates_with_exercise = WorkoutTemplate.query.filter(WorkoutTemplate.exercises.contains(exercise)).all()
    for tpl in templates_with_exercise:
        tpl.exercises.remove(exercise)
    
    # KROK 2: Místo smazání cviku mu jen nastavíme příznak is_deleted, aby zůstal v historii
    name = exercise.name
    exercise.is_deleted = True
    db.session.commit()
    
    flash(f"Cvik '{name}' byl úspěšně odstraněn ze šablon a knihovny, ale zůstane ve tvé historii.", "info")
    return redirect(url_for("exercises.cviky") + "#moje-cviky")