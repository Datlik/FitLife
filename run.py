"""
run.py – Vstupní bod webové aplikace FitLife.
"""

from app import create_app
from app.extensions import db

# Vytvoření aplikace pomocí Application Factory
app = create_app()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
