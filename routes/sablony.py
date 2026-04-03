from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from sqlalchemy import or_
from models import db, WorkoutTemplate, Exercise

sablony_bp = Blueprint("sablony", __name__)

@sablony_bp.route("/sablony", methods=["GET", "POST"])
@login_required
def index():
    def is_admin():
        return current_user.is_authenticated and current_user.is_admin

    if request.method == "POST":
        # 1. CSRF Ochrana
        if request.form.get("_csrf_token") != session.get("_csrf_token"):
            flash("Neplatný požadavek (CSRF).", "error")
            return redirect(url_for("sablony.index") + "#moje-sablony")

        # 2. Získání dat z formuláře
        name = request.form.get("name", "").strip()
        selected_exercise_ids = request.form.getlist("exercises")
        is_public = True if request.form.get("is_public") == "on" else False

        if not name:
            flash("Název šablony je povinný.", "error")
            return redirect(url_for("sablony.index") + "#moje-sablony")

        if not selected_exercise_ids:
            flash("Musíš vybrat alespoň jeden cvik do šablony.", "warning")
            return redirect(url_for("sablony.index") + "#moje-sablony")

        # 3. Vytvoření nové šablony
        new_template = WorkoutTemplate(name=name, user_id=current_user.id, is_public=is_public)

        # 4. Magie SQLAlchemy - připojení cviků (Many-to-Many relace)
        for ex_id in selected_exercise_ids:
            ex = Exercise.query.get(int(ex_id))
            if ex:
                new_template.exercises.append(ex)

        db.session.add(new_template)
        db.session.commit()

        flash(f"Šablona '{name}' byla úspěšně vytvořena!", "success")

        return redirect(url_for("sablony.index") + "#moje-sablony")

    # GET request: Načtení dat pro zobrazení
    # Rozdělíme šablony na globální (od admina) a vlastní (od uživatele)
    predefined_templates = WorkoutTemplate.query.filter_by(user_id=None).all()
    my_templates = WorkoutTemplate.query.filter_by(user_id=current_user.id).all()
    
    # NOVÉ: Komunitní šablony (veřejné a nejsou moje)
    community_templates = WorkoutTemplate.query.filter(
        WorkoutTemplate.is_public == True,
        WorkoutTemplate.user_id != current_user.id
    ).all()

    # Pro výběr do šablony potřebujeme nabídnout VŠECHNY dostupné cviky (předdefinované i vlastní)
    # A chceme jen ty, které nejsou smazané
    predefined_exercises = Exercise.query.filter_by(user_id=None, is_deleted=False).all()
    my_exercises = Exercise.query.filter_by(user_id=current_user.id, is_deleted=False).all()
    all_exercises = predefined_exercises + my_exercises

    return render_template("sablony.html", 
                           predefined=predefined_templates, 
                           my_templates=my_templates, 
                           community_templates=community_templates,
                           exercises=all_exercises)

@sablony_bp.route("/sablony/smazat/<int:template_id>", methods=["POST"])
@login_required
def smazat(template_id):
    if request.form.get("_csrf_token") != session.get("_csrf_token"):
        flash("Neplatný požadavek.", "error")
        return redirect(url_for("sablony.index"))

    template = WorkoutTemplate.query.get_or_404(template_id)
    is_admin = current_user.is_authenticated and current_user.is_admin

    # Bezpečnostní kontrola!
    # Globální šablony (user_id is None) smí mazat pouze admin přes PyQt aplikaci.
    # Na webu toto právo nemá nikdo, ani admin.
    if template.user_id is None:
        flash("Globální šablony lze mazat pouze přes administrátorskou aplikaci.", "error")
        return redirect(url_for("sablony.index"))
    
    if template.user_id != current_user.id:
        flash("Nemůžeš smazat šablonu, která ti nepatří!", "error")
        return redirect(url_for("sablony.index"))

    name = template.name
    db.session.delete(template)
    db.session.commit()

    flash(f"Šablona '{name}' byla smazána.", "info")
    return redirect(url_for("sablony.index") + "#moje-sablony")
@sablony_bp.route("/sablony/kopirovat/<int:template_id>", methods=["POST"])
@login_required
def kopirovat(template_id):
    if request.form.get("_csrf_token") != session.get("_csrf_token"):
        flash("Neplatný požadavek (CSRF).", "error")
        return redirect(url_for("sablony.index") + "#komunita")

    original = WorkoutTemplate.query.get_or_404(template_id)
    
    # Vytvoření kopie
    new_template = WorkoutTemplate(
        name=f"{original.name} (Z komunity)",
        user_id=current_user.id,
        is_public=False
    )
    
    # Přidání cviků do kopie
    for ex in original.exercises:
        new_template.exercises.append(ex)
        
    db.session.add(new_template)
    db.session.commit()
    
    flash(f"Šablona '{original.name}' byla zkopírována do tvých šablon.", "success")
    return redirect(url_for("sablony.index") + "#moje-sablony")
