"""
auth.py – Modul pro autentizaci a autorizaci uživatelů.

Obsahuje registraci, přihlášení, odhlášení, smazání účtu
a context processor, který do všech šablon vkládá data pro sidebar
(streak, heatmapa, ostatní tréninky, CSRF token).
"""

from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from app.models import db, User, Exercise, WorkoutTemplate, WorkoutHistory, WorkoutSet
import secrets

auth_bp = Blueprint("auth", __name__)


def generate_csrf_token():
    """Vygeneruje CSRF token a uloží ho do session. Pokud už existuje, vrátí stávající."""
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]


def validate_csrf(token):
    """Porovná CSRF token z formuláře s tokenem uloženým v session."""
    return token == session.get("_csrf_token")


@auth_bp.app_context_processor
def inject_sidebar_data():
    """Context processor – vkládá globální data do všech Jinja šablon.

    Pro nepřihlášené uživatele vrací pouze CSRF token.
    Pro přihlášené uživatele navíc spočítá:
    - weekly_workouts: počet tréninků za posledních 7 dní
    - total_sets: celkový počet sérií v historii
    - recent_workouts: poslední 3 tréninky pro sidebar
    - workout_streak: kolik týdnů v řadě uživatel cvičil
    - heatmap_data: pole 7 dnů s příznakem aktivity (pro kalendář)
    - get_icon: funkce pro načtení SVG ikon ze složky icons/
    """
    if not current_user.is_authenticated:
        return dict(csrf_token=generate_csrf_token)
    
    from datetime import datetime, timedelta, timezone
    
    def utcnow():
        """Vrátí naive UTC čas kompatibilní s MySQL."""
        return datetime.now(timezone.utc).replace(tzinfo=None)
    
    # 1. Tréninky za poslední týden
    seven_days_ago = utcnow() - timedelta(days=7)
    weekly_workouts = WorkoutHistory.query.filter(
        WorkoutHistory.user_id == current_user.id,
        WorkoutHistory.status == 'finished',
        WorkoutHistory.end_time >= seven_days_ago
    ).count()

    # 2. Celkový počet sérií (přes JOIN s workout_history)
    total_sets = WorkoutSet.query.join(WorkoutHistory).filter(
        WorkoutHistory.user_id == current_user.id,
        WorkoutHistory.status == 'finished'
    ).count()

    # 3. Poslední 3 tréninky pro zobrazení v pravém panelu
    recent_workouts = WorkoutHistory.query.filter_by(
        user_id=current_user.id, 
        status="finished"
    ).order_by(WorkoutHistory.end_time.desc()).limit(3).all()

    # 4. Výpočet Streak (počet po sobě jdoucích týdnů cvičení)
    all_finished = WorkoutHistory.query.filter_by(
        user_id=current_user.id, 
        status="finished"
    ).order_by(WorkoutHistory.end_time.desc()).all()
    
    workout_streak = 0
    if all_finished:
        now = utcnow()
        current_year, current_week, _ = now.isocalendar()
        
        # Převedeme data na unikátní dvojice (rok, číslo_týdne) a seřadíme sestupně
        workout_weeks = sorted(list(set([
            (w.end_time.isocalendar()[0], w.end_time.isocalendar()[1]) 
            for w in all_finished if w.end_time
        ])), reverse=True)
        
        if workout_weeks:
            latest_year, latest_week = workout_weeks[0]
            
            # Je poslední trénink v tomto nebo minulém týdnu?
            is_recent_enough = False
            if latest_year == current_year and latest_week == current_week:
                is_recent_enough = True
            elif latest_year == current_year and latest_week == current_week - 1:
                is_recent_enough = True
            elif latest_year == current_year - 1 and current_week == 1 and latest_week >= 52:
                is_recent_enough = True  # Přechod přes Nový rok
                
            if is_recent_enough:
                workout_streak = 1
                prev_year, prev_week = latest_year, latest_week
                
                # Procházíme zbývající týdny a počítáme po sobě jdoucí
                for yr, wk in workout_weeks[1:]:
                    is_consecutive = False
                    if yr == prev_year and wk == prev_week - 1:
                        is_consecutive = True
                    elif yr == prev_year - 1 and prev_week == 1 and wk >= 52:
                        is_consecutive = True  # Přechod přes Nový rok
                        
                    if is_consecutive:
                        workout_streak += 1
                        prev_year, prev_week = yr, wk
                    else:
                        break  # Přerušení série

    def get_icon(filename):
        """Načte obsah SVG souboru ze složky icons/ pro inline vložení do HTML."""
        import os
        filepath = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'icons', filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception:
                pass
        return ""

    # 5. Heatmapa aktivity (posledních 7 dnů)
    heatmap_data = []
    today = utcnow().date()
    
    seven_days_workouts = WorkoutHistory.query.filter(
        WorkoutHistory.user_id == current_user.id,
        WorkoutHistory.status == 'finished',
        WorkoutHistory.end_time >= utcnow() - timedelta(days=7)
    ).all()
    
    # Množina dat, ve kterých uživatel cvičil
    active_dates = set([w.end_time.date() for w in seven_days_workouts if w.end_time])

    # Sestavíme pole 7 dnů od nejstaršího po dnešek
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        days_cz = ["Po", "Út", "St", "Čt", "Pá", "So", "Ne"]
        heatmap_data.append({
            'label': f"{days_cz[day.weekday()]} {day.strftime('%d.%m.')}",
            'active': day in active_dates
        })

    return dict(
        csrf_token=generate_csrf_token,
        weekly_workouts=weekly_workouts,
        total_sets=total_sets,
        recent_workouts=recent_workouts,
        workout_streak=workout_streak,
        get_icon=get_icon,
        heatmap_data=heatmap_data
    )


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Zpracuje registraci nového uživatele.

    Validuje e-mail, sílu hesla (min. 8 znaků), shodu hesel
    a unikátnost e-mailu. Po úspěchu automaticky přihlásí.
    """
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    error = None

    if request.method == "POST":
        if not validate_csrf(request.form.get("_csrf_token")):
            error = "Neplatný CSRF token."
        else:
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            confirm = request.form.get("confirm_password", "")

            if not email or not password:
                error = "E-mail a heslo jsou povinné."
            elif len(password) < 8:
                error = "Heslo musí mít alespoň 8 znaků."
            elif password != confirm:
                error = "Hesla se neshodují."
            elif User.query.filter_by(email=email).first():
                error = "Tento e-mail je již zaregistrován."
            else:
                user = User(email=email)
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                login_user(user)
                flash("Registrace proběhla úspěšně!", "success")
                return redirect(url_for("main.index"))

    return render_template("auth/register.html", error=error)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Zpracuje přihlášení uživatele. Podporuje redirect na původní stránku přes ?next= parametr."""
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    error = None

    if request.method == "POST":
        if not validate_csrf(request.form.get("_csrf_token")):
            error = "Neplatný CSRF token."
        else:
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = User.query.filter_by(email=email).first()

            if not user or not user.check_password(password):
                error = "Nesprávný e-mail nebo heslo."
            else:
                login_user(user)
                flash("Přihlášení proběhlo úspěšně.", "success")
                # Flask-Login uloží původní URL do ?next=, přesměrujeme tam
                next_page = request.args.get("next")
                return redirect(next_page or url_for("main.index"))

    return render_template("auth/login.html", error=error)


@auth_bp.route("/delete-account", methods=["POST"])
@login_required
def delete_account():
    """Smaže účet přihlášeného uživatele a všechna jeho data.

    Kaskádové mazání v pořadí: série → tréninky → šablony → cviky → uživatel.
    Po smazání se uživatel automaticky odhlásí.
    """
    if not validate_csrf(request.form.get("_csrf_token")):
        flash("Neplatný CSRF token.", "error")
        return redirect(url_for("main.index"))

    user = User.query.get(current_user.id)

    # 1. Smazat všechny série v trénincích uživatele
    WorkoutSet.query.filter(WorkoutSet.workout.has(user_id=user.id)).delete(synchronize_session=False)

    # 2. Smazat historii tréninků
    WorkoutHistory.query.filter_by(user_id=user.id).delete()

    # 3. Odpojit cviky ze šablon (M:N vazba) a smazat šablony
    templates = WorkoutTemplate.query.filter_by(user_id=user.id).all()
    for tpl in templates:
        tpl.exercises.clear()  # Vyčistí spojovací tabulku template_exercises
        db.session.delete(tpl)

    # 4. Smazat vlastní cviky
    WorkoutSet.query.filter(WorkoutSet.exercise.has(user_id=user.id)).delete(synchronize_session=False)
    Exercise.query.filter_by(user_id=user.id).delete()

    # 5. Odhlásit a smazat uživatele
    logout_user()
    db.session.delete(user)
    db.session.commit()

    flash("Účet a všechna související data byla úspěšně smazána.", "info")
    return redirect(url_for("main.index"))


@auth_bp.route("/logout")
@login_required
def logout():
    """Odhlásí uživatele a přesměruje na hlavní stránku."""
    logout_user()
    flash("Byl jsi odhlášen.", "info")
    return redirect(url_for("main.index"))
