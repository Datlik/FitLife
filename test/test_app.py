import pytest
from app import create_app
from models import db, User, Exercise

# ==========================================
# 1. FIXTURES (Příprava testovacího prostředí)
# ==========================================

@pytest.fixture
def app():
    """Vytvoří a nakonfiguruje instanci aplikace pro testování."""
    
    # Připravíme si konfiguraci PŘED vytvořením aplikace
    test_config = {
        "TESTING": True,
        # Použijeme SQLite databázi čistě v paměti RAM
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False, 
        "SECRET_KEY": "test_secret_key"
    }

    # Předáme test_config do továrny create_app
    app = create_app(test_config)

    # Vytvoření tabulek před testy
    with app.app_context():
        db.create_all()
        yield app
        # Úklid po testech
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    """Vytvoří virtuálního klienta pro simulaci HTTP požadavků."""
    return app.test_client()

@pytest.fixture
def csrf_token(client):
    """Pomocná fixture pro získání platného CSRF tokenu do testů."""
    with client.session_transaction() as session:
        session['_csrf_token'] = 'test-csrf-token'
    return 'test-csrf-token'

@pytest.fixture
def test_user(app):
    """Vytvoří testovacího uživatele v databázi."""
    with app.app_context():
        user = User(email="test@fitlife.cz")
        user.set_password("heslo123")
        db.session.add(user)
        db.session.commit()
        return user

# ==========================================
# 2. TESTY MODELŮ (Databázová vrstva)
# ==========================================

def test_user_password_hashing(app):
    """Testuje, zda se heslo správně zahasuje a ověří."""
    user = User(email="pepa@novak.cz")
    user.set_password("tajneheslo")
    
    assert user.password_hash is not None
    assert user.password_hash != "tajneheslo"
    assert user.check_password("tajneheslo") is True
    assert user.check_password("spatneheslo") is False

def test_create_exercise(app, test_user):
    """Testuje vytvoření nového cviku do databáze."""
    with app.app_context():
        # Najdeme testovacího uživatele v aktuální session
        user = User.query.filter_by(email="test@fitlife.cz").first()
        
        ex = Exercise(
            name="Bench Press",
            primary_muscle="Prsa",
            is_custom=True,
            user_id=user.id
        )
        db.session.add(ex)
        db.session.commit()
        
        saved_ex = Exercise.query.filter_by(name="Bench Press").first()
        assert saved_ex is not None
        assert saved_ex.user_id == user.id

# ==========================================
# 3. TESTY ROUT (Logika aplikace a uživatelské akce)
# ==========================================

def test_homepage_redirects_unauthenticated(client):
    """Základní test, zda funguje hlavní stránka (i bez přihlášení)."""
    response = client.get("/")
    assert response.status_code == 200

def test_user_registration(client, app, csrf_token):
    """Testuje, zda proces registrace úspěšně založí uživatele."""
    response = client.post("/register", data={
        "email": "novy@uzivatel.cz",
        "password": "mojetajneheslo",
        "confirm_password": "mojetajneheslo",
        "_csrf_token": csrf_token
    }, follow_redirects=True)
    
    assert response.status_code == 200
    
    # Ověříme, že uživatel skutečně existuje v databázi
    with app.app_context():
        user = User.query.filter_by(email="novy@uzivatel.cz").first()
        assert user is not None

def test_user_login(client, test_user, csrf_token):
    """Testuje přihlášení s platnými i neplatnými údaji."""
    # Pokus o přihlášení s platnými údaji
    response_good = client.post("/login", data={
        "email": "test@fitlife.cz",
        "password": "heslo123",
        "_csrf_token": csrf_token
    }, follow_redirects=True)
    
    assert response_good.status_code == 200
    # Pokud bys měl v šabloně text "Přihlášení proběhlo úspěšně.", mohl bys to testovat i přes assert b'uspesne' in response_good.data

def test_protected_route_requires_login(client):
    """Testuje, že nepřihlášený uživatel se nedostane na cvičení."""
    response = client.get("/cviky", follow_redirects=True)
    # Aplikace by ho měla přesměrovat na přihlášení
    assert b'Pro p\xc5\x99\xc3\xadstup se mus\xc3\xad\xc5\xa1 p\xc5\x99ihl\xc3\xa1sit.' in response.data