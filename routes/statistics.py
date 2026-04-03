import matplotlib
matplotlib.use('Agg') # Kritické pro Flask! Kreslí grafy na pozadí bez GUI okna.
import matplotlib.pyplot as plt
import io
import base64
from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from models import db, WorkoutSet, WorkoutHistory, Exercise

statistiky_bp = Blueprint("statistiky", __name__)

@statistiky_bp.route("/statistiky", methods=["GET"])
@login_required
def index():
    # 1. Najdeme všechna ID cviků, které uživatel někdy cvičil (a má je v dokončených trénincích)
    performed_exercise_ids = db.session.query(WorkoutSet.exercise_id)\
        .join(WorkoutHistory)\
        .filter(WorkoutHistory.user_id == current_user.id, WorkoutHistory.status == 'finished')\
        .distinct().all()
    
    # Rozbalíme výsledek z databáze do obyčejného seznamu IDček
    performed_ids = [e[0] for e in performed_exercise_ids]
    
    # 2. Vytáhneme samotné objekty cviků pro náš <select> dropdown
    exercises = Exercise.query.filter(Exercise.id.in_(performed_ids)).all() if performed_ids else []

    # Zjistíme, co uživatel vybral z dropdownu (GET parametr z URL)
    selected_ex_id = request.args.get("exercise")
    
    plot_url = None
    pr_sets = []
    selected_ex = None

    if selected_ex_id:
        selected_ex = Exercise.query.get(selected_ex_id)
        
        # 3. Získáme všechny série vybraného cviku z dokončených tréninků
        sets = WorkoutSet.query.join(WorkoutHistory).filter(
            WorkoutHistory.user_id == current_user.id,
            WorkoutSet.exercise_id == selected_ex_id,
            WorkoutHistory.status == 'finished'
        ).order_by(WorkoutHistory.end_time).all()

        if sets:
            # Najdeme maximální zvednutou váhu pro každý den
            max_weights = {}
            for s in sets:
                date_str = s.workout.end_time.strftime('%d.%m.%Y')
                if date_str not in max_weights or s.weight > max_weights[date_str]:
                    max_weights[date_str] = s.weight
            
            dates = list(max_weights.keys())
            weights = list(max_weights.values())

            # --- KRESLENÍ GRAFU POMOCÍ MATPLOTLIB ---
            # Vytvoříme plátno přesně pro náš Dark Theme
            fig, ax = plt.subplots(figsize=(9, 4), facecolor='#0a0a0a')
            ax.set_facecolor('#0a0a0a')
            
            # Vykreslíme křivku s fialovými body
            ax.plot(dates, weights, marker='o', color='#8b5cf6', linewidth=2, markersize=8)
            # Nastylování os a mřížky pro prémiový vzhled
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

            # --- ULOŽENÍ DO BASE64 ---
            img = io.BytesIO()
            plt.savefig(img, format='png', bbox_inches='tight', transparent=True)
            img.seek(0)
            plot_url = base64.b64encode(img.getvalue()).decode('utf8')
            plt.close()

        # 4. Vyhledání maximálních výsledků (skutečné maximum váhy)
        # Nejdřív najdeme nejvyšší váhu, jakou uživatel kdy u tohoto cviku zvedl
        max_weight_query = db.session.query(db.func.max(WorkoutSet.weight)).join(WorkoutHistory).filter(
            WorkoutHistory.user_id == current_user.id,
            WorkoutSet.exercise_id == selected_ex_id,
            WorkoutHistory.status == 'finished'
        ).scalar()

        # Pak vytáhneme všechny série, kde této váhy dosáhl (seřazené od nejnovější)
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