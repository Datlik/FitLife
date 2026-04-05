"""
config.py – Konfigurace Flask aplikace.

Obsahuje připojovací údaje k MySQL databázi a bezpečnostní klíč pro session.
V produkci by SECRET_KEY měl být uložen v proměnné prostředí, ne v kódu.
"""


class Config:
    """Hlavní konfigurační třída. Flask ji načítá přes app.config.from_object()."""
    SECRET_KEY = "tajny_klic_pro_session"
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://student31:spsnet@dbs.spskladno.cz/vyuka31"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
