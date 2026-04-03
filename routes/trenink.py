from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from models import db, WorkoutHistory, WorkoutSet, WorkoutTemplate, Exercise
from datetime import datetime

trenink_bp = Blueprint("trenink", __name__)

@trenink_bp.route("/trenink")
@login_required
def index():
    # Zkusíme najít aktuálně probíhající trénink
    active_workout = WorkoutHistory.query.filter_by(user_id=current_user.id, status="active").first()
    
    if not active_workout:
        # Pokud žádný neběží, ukážeme startovací obrazovku
        my_templates = WorkoutTemplate.query.filter_by(user_id=current_user.id).all()
        return render_template("trenink.html", workout=None, templates=my_templates)

    # Pokud trénink BĚŽÍ, vytáhneme všechny jeho série
    sets = WorkoutSet.query.filter_by(workout_id=active_workout.id).all()
    
    # Seskupíme série podle cviků (abychom v HTML mohli vypsat bloky)
    # Používáme dictionary, kde klíč je objekt Cvik a hodnota je seznam jeho Sérií
    exercises_in_workout = {}
    for s in sets:
        if s.exercise not in exercises_in_workout:
            exercises_in_workout[s.exercise] = []
        # Prázdné "placeholder" série (reps=0, weight=0) nebudeme do seznamu přidávat
        if s.reps > 0 or s.weight > 0:
            exercises_in_workout[s.exercise].append(s)

    # Potřebujeme všechny cviky pro dropdown "Přidat další cvik"
    predefined = Exercise.query.filter_by(user_id=None).all()
    mine = Exercise.query.filter_by(user_id=current_user.id).all()
    all_exercises = predefined + mine

    return render_template("trenink.html", 
                           workout=active_workout, 
                           exercises_in_workout=exercises_in_workout,
                           all_exercises=all_exercises)

@trenink_bp.route("/trenink/start", methods=["POST"])
@trenink_bp.route("/trenink/start/<int:template_id>", methods=["POST"])
@login_required
def start(template_id=None):
    if request.form.get("_csrf_token") != session.get("_csrf_token"):
        flash("Neplatný požadavek.", "error")
        return redirect(url_for("trenink.index"))
        
    # Blueprint pravidlo: Zrušit předchozí aktivní trénink, pokud existuje
    old_active = WorkoutHistory.query.filter_by(user_id=current_user.id, status="active").first()
    if old_active:
        old_active.status = "cancelled"
        old_active.end_time = datetime.utcnow()
        flash("Předchozí nedokončený trénink byl zrušen.", "warning")
        
    # Založení nového tréninku
    new_workout = WorkoutHistory(user_id=current_user.id, status="active", start_time=datetime.utcnow())
    db.session.add(new_workout)
    db.session.flush() # Tímto získáme ID nového tréninku před commitem!
    
    # --- UPRAVENÁ ČÁST: Povoluje start i z globální šablony ---
    if template_id:
        tpl = WorkoutTemplate.query.get(template_id)
        # ZMĚNA: Povolíme start, pokud je šablona moje (current_user.id) NEBO globální (None)
        if tpl and (tpl.user_id == current_user.id or tpl.user_id is None):
            for ex in tpl.exercises:
                dummy_set = WorkoutSet(workout_id=new_workout.id, exercise_id=ex.id, reps=0, weight=0, intensity=1)
                db.session.add(dummy_set)
    # --- KONEC UPRAVENÉ ČÁSTI ---
                
    db.session.commit()
    flash("Trénink zahájen! Ať to roste.", "success")
    return redirect(url_for("trenink.index"))

@trenink_bp.route("/trenink/pridat_cvik", methods=["POST"])
@login_required
def pridat_cvik():
    # Toto přidá prázdný blok cviku do běžícího tréninku
    active_workout = WorkoutHistory.query.filter_by(user_id=current_user.id, status="active").first()
    exercise_id = request.form.get("exercise_id")
    
    if active_workout and exercise_id:
        dummy_set = WorkoutSet(workout_id=active_workout.id, exercise_id=exercise_id, reps=0, weight=0, intensity=1)
        db.session.add(dummy_set)
        db.session.commit()
        
    # Magie! Přesměrujeme přesně na ID toho cviku, ať stránka odskroluje dolů
    return redirect(url_for("trenink.index") + f"#cvik-{exercise_id}")

@trenink_bp.route("/trenink/pridat_serii", methods=["POST"])
@login_required
def pridat_serii():
    active_workout = WorkoutHistory.query.filter_by(user_id=current_user.id, status="active").first()
    if not active_workout:
        return redirect(url_for("trenink.index"))

    exercise_id = request.form.get("exercise_id")
    reps = int(request.form.get("reps", 0))
    weight = float(request.form.get("weight", 0.0))
    intensity = int(request.form.get("intensity", 5))

    new_set = WorkoutSet(workout_id=active_workout.id, exercise_id=exercise_id, reps=reps, weight=weight, intensity=intensity)
    db.session.add(new_set)
    db.session.commit()

    # Návrat na kotvu cviku = No-JS Hack v praxi!
    return redirect(url_for("trenink.index") + f"#cvik-{exercise_id}")

@trenink_bp.route("/trenink/dokoncit", methods=["POST"])
@login_required
def dokoncit():
    active_workout = WorkoutHistory.query.filter_by(user_id=current_user.id, status="active").first()
    if not active_workout:
        return redirect(url_for("trenink.index"))

    # Výpočet celkového času
    active_workout.end_time = datetime.utcnow()
    duration_delta = active_workout.end_time - active_workout.start_time
    active_workout.duration = int(duration_delta.total_seconds() / 60) # Převedeno na minuty

    # Výpočet celkového objemu (Tonnage: reps * weight)
    sets = WorkoutSet.query.filter_by(workout_id=active_workout.id).all()
    total_vol = sum(s.reps * s.weight for s in sets)
    
    active_workout.total_volume = total_vol
    active_workout.status = "finished"
    
    # Smažeme z databáze všechny "dummy" série (ty, co měly reps=0 a weight=0)
    for s in sets:
        if s.reps == 0 and s.weight == 0:
            db.session.delete(s)

    db.session.commit()
    flash(f"Skvělá práce! Trénink dokončen. Čas: {active_workout.duration} min, Objem: {total_vol} kg.", "success")
    return redirect(url_for("index")) # Pošleme ho zpět na Dashboard