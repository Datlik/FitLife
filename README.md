FitLife 1.0

FitLife je webová aplikace pro správu fitness tréninků, doplněná o desktopovou administrátorskou aplikaci v PyQt5.

---

Jak spustit

Nainstalujte potřebné balíčky z knihovna.txt:

    pip install -r knihovna.txt

nebo si stáhněte knihovny ručně (viz níže).

---

Co stáhnout

Pro spuštění run.py (webová stránka):
- Flask
- flask-sqlalchemy
- flask-login
- pymysql
- matplotlib

Admin app (spouští se otevřením složky admin a tam spustíte admin_app.py):
- pyqt5
- mysql-connector-python

Testy (do terminálu):
- stáhnout: pytest
- zadat toto do terminálu a proběhnou testy:

      python -m pytest test/test_app.py -v

---

Spuštění

1. Pro spuštění webové stránky běžte do run.py a spusťte ho. Tím se vám spustí stránka na http://127.0.0.1:5000

2. Až budete chtít zapnout admin app, běžte do složky admin a tam spusťte admin_app.py. Přihlašovací údaje jsou nastavené v databázi (musí mít is_admin = 1).

3. Testy jsou v složce test, spouští se příkazem výše.

---

Funkce programu

Webová aplikace (pro uživatele)
- Registrace a přihlášení uživatele
- Katalog cviků (globální od admina + vlastní)
- Šablony tréninků (tvorba plánů)
- Aktivní trénink (přidávání sérií v reálném čase)
- Historie tréninků s heatmapou aktivity
- Statistiky s grafy progrese váhy

Administrátorská aplikace (PyQt5 desktop)
- Správa uživatelů (mazání, úprava oprávnění)
- Správa globálních cviků (přidání, úprava, import z CSV)
- Správa globálních šablon

---

Seznam použitých knihoven

Web:
- Flask - webový framework
- Flask-SQLAlchemy - ORM pro práci s databází
- Flask-Login - správa přihlášení uživatelů
- PyMySQL - driver pro připojení k MySQL
- Matplotlib - generování grafů statistik

Admin:
- PyQt5 - desktopové GUI
- mysql-connector-python - přímé SQL dotazy do databáze

Testy:
- pytest- framework pro automatické testování

---

Autoři

- DJ
