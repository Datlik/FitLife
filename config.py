import os

class Config:
    """Výchozí konfigurace (Základní)."""
    SECRET_KEY = "dev-secret-change-in-production"
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://student31:spsnet@dbs.spskladno.cz/vyuka31"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
class TestConfig(Config):
    """Konfigurace pro testy."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
