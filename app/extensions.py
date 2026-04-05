"""
extensions.py – Inicializace Flask rozšíření.

Instance db (SQLAlchemy) a login_manager (Flask-Login) se vytváří zde
bez vazby na konkrétní aplikaci. Propojení s aplikací proběhne
až v __init__.py pomocí db.init_app(app) a login_manager.init_app(app).
Tento vzor zabraňuje cyklickým importům.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()
