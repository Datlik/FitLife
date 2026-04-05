"""
statistics.py – Modul pro zobrazení statistik a grafů progrese.

Generuje graf vývoje maximální váhy u vybraného cviku pomocí knihovny Matplotlib.
Graf se vykreslí na serveru do PNG obrázku, převede se do base64
a pošle do šablony jako data URL (bez ukládání na disk).
"""

import matplotlib
matplotlib.use('Agg')  # Headless režim – kreslí grafy bez otevření GUI okna
import matplotlib.pyplot as plt
import io
import base64
from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from app.models import db, WorkoutSet, WorkoutHistory, Exercise

statistiky_bp = Blueprint("statistiky", __name__)


@statistiky_bp.route("/statistiky", methods=["GET"])
@login_required
def index():
    """Zobrazí stránku statistik s dropdownem cviků, grafem progrese a osobními rekordy.

    1. Najde všechny cviky, které uživatel někdy cvičil v dokončených trénincích.
    2. Po výběru cviku vykreslí graf max. váhy v čase.
    3. Zobrazí osobní rekord (maximální váhu) u vybraného cviku.
    """
    # Najdeme unikátní ID cviků, které uživatel někdy cvičil
    performed_exercise_ids = db.session.query(WorkoutSet.exercise_id)\
        .join(WorkoutHistory)\
        .filter(WorkoutHistory.user_id == current_user.id, WorkoutHistory.status == 'finished')\
        .distinct().all()

    performed_ids = [e[0] for e in performed_exercise_ids]
    exercises = Exercise.query.filter(Exercise.id.in_(performed_ids)).all() if performed_ids else []

    # GET parametr z URL – jaký cvik uživatel vybral v dropdownu
    selected_ex_id = request.args.get("exercise")

    plot_url = None
    pr_sets = []
    selected_ex = None

    if selected_ex_id:
        selected_ex = Exercise.query.get(selected_ex_id)

        # Všechny série vybraného cviku z dokončených tréninků (chronologicky)
        sets = WorkoutSet.query.join(WorkoutHistory).filter(
            WorkoutHistory.user_id == current_user.id,
            WorkoutSet.exercise_id == selected_ex_id,
            WorkoutHistory.status == 'finished'
        ).order_by(WorkoutHistory.end_time).all()

        if sets:
            # Pro každý den najdeme maximální zvednutou váhu
            max_weights = {}
            for s in sets:
                date_str = s.workout.end_time.strftime('%d.%m.%Y')
                if date_str not in max_weights or s.weight > max_weights[date_str]:
                    max_weights[date_str] = s.weight

            dates = list(max_weights.keys())
            weights = list(max_weights.values())

            # --- Vykreslení grafu v dark theme ---
            fig, ax = plt.subplots(figsize=(9, 4), facecolor='#0a0a0a')
            ax.set_facecolor('#0a0a0a')

            ax.plot(dates, weights, marker='o', color='#8b5cf6', linewidth=2, markersize=8)
            ax.tick_params(colors='#a3a3a3')
            ax.spines['bottom'].set_color('#333333')
            ax.spines['left'].set_color('#333333')
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.yaxis.grid(True, color='#1f1f1f', linestyle='--')

            ax.set_title(f'Progres max. váhy: {selected_ex.name}', color='white', pad=15)
            plt.ylabel('Váha (kg)', color='#a3a3a3')
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()

            # Uložení obrázku do paměti a převod na base64 string
            img = io.BytesIO()
            plt.savefig(img, format='png', bbox_inches='tight', transparent=True)
            img.seek(0)
            plot_url = base64.b64encode(img.getvalue()).decode('utf8')
            plt.close()

        # Osobní rekord – najdeme nejvyšší váhu a všechny série s touto váhou
        max_weight_query = db.session.query(db.func.max(WorkoutSet.weight)).join(WorkoutHistory).filter(
            WorkoutHistory.user_id == current_user.id,
            WorkoutSet.exercise_id == selected_ex_id,
            WorkoutHistory.status == 'finished'
        ).scalar()

        pr_sets = []
        if max_weight_query:
            pr_sets = WorkoutSet.query.join(WorkoutHistory).filter(
                WorkoutHistory.user_id == current_user.id,
                WorkoutSet.exercise_id == selected_ex_id,
                WorkoutSet.weight == max_weight_query,
                WorkoutHistory.status == 'finished'
            ).order_by(WorkoutHistory.end_time.desc()).all()

    return render_template("statistiky.html",
                           exercises=exercises,
                           selected_ex=selected_ex,
                           plot_url=plot_url,
                           pr_sets=pr_sets)