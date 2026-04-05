"""
admin_app.py – Desktopová administrátorská aplikace pro FitLife.

Tato aplikace běží samostatně mimo webový server. Používá PyQt5 pro GUI
a připojuje se přímo k MySQL databázi pomocí mysql-connector-python.

Funkce aplikace:
    - Přihlášení admina (ověření hesla přes werkzeug hash)
    - Správa uživatelů (úprava e-mailu, role, smazání účtu s kaskádou)
    - Správa globálních cviků (přidání, úprava, soft-delete, CSV import)
    - Správa globálních šablon (vytvoření s výběrem cviků, smazání)

Spuštění: python admin/admin_app.py
"""

import sys
import csv
import mysql.connector
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox,
                             QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
                             QComboBox, QDialog, QFormLayout,
                             QListWidget, QListWidgetItem, QAbstractItemView)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QIcon
import os
from werkzeug.security import check_password_hash

# --- Připojení k databázi (stejná DB jako webová aplikace) ---
DB_CONFIG = {
    "host": "dbs.spskladno.cz",
    "user": "student31",
    "password": "spsnet",
    "database": "vyuka31"
}

# --- Cesta k SVG ikonám (složka icons/ v kořenu projektu) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICONS_DIR = os.path.join(os.path.dirname(BASE_DIR), "icons")


def get_icon(name):
    """Načte ikonu ze složky icons/ podle názvu souboru (např. 'edit.svg')."""
    return QIcon(os.path.join(ICONS_DIR, name))



# DIALOGOVÁ OKNA PRO ÚPRAVY


class EditExerciseDialog(QDialog):
    """Vyskakovací okno pro úpravu existujícího cviku.

    Zobrazí formulář s předvyplněnými hodnotami (název, sval, vybavení).
    Po kliknutí na "Uložit" vrátí nové hodnoty přes metodu get_data().
    """

    def __init__(self, ex_id, name, muscle, equip, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Upravit cvik")
        self.setFixedSize(350, 200)
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # Textové pole pro název cviku (předvyplněné aktuálním názvem)
        self.input_name = QLineEdit(name)

        # Dropdowny pro výběr svalu a vybavení
        self.combo_muscle = QComboBox()
        self.combo_muscle.addItems(["Prsa", "Záda", "Nohy", "Ramena", "Biceps", "Triceps", "Břicho", "Lýtka", "Celé tělo"])
        self.combo_muscle.setCurrentText(muscle)

        self.combo_equip = QComboBox()
        self.combo_equip.addItems(["Velká činka", "Jednoručky", "Stroj", "Kladka", "Vlastní váha", "Osa", "Kettlebell"])
        self.combo_equip.setCurrentText(equip)

        form_layout.addRow("Název cviku:", self.input_name)
        form_layout.addRow("Hlavní sval:", self.combo_muscle)
        form_layout.addRow("Vybavení:", self.combo_equip)
        layout.addLayout(form_layout)

        # Tlačítka Uložit/Zrušit
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Uložit změny")
        self.btn_save.clicked.connect(self.accept)   # accept() zavře dialog s výsledkem QDialog.Accepted
        self.btn_cancel = QPushButton("Zrušit")
        self.btn_cancel.setObjectName("btn_cancel")
        self.btn_cancel.clicked.connect(self.reject)  # reject() zavře dialog s výsledkem QDialog.Rejected

        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

    def get_data(self):
        """Vrátí tuple (název, sval, vybavení) z formuláře."""
        return self.input_name.text().strip(), self.combo_muscle.currentText(), self.combo_equip.currentText()


class EditUserDialog(QDialog):
    """Vyskakovací okno pro úpravu e-mailu a role uživatele."""

    def __init__(self, user_id, email, is_admin, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Upravit uživatele")
        self.setFixedSize(350, 160)
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.input_email = QLineEdit(email)

        # Checkbox pro nastavení admin role
        from PyQt5.QtWidgets import QCheckBox
        self.cb_admin = QCheckBox("Administrátor")
        self.cb_admin.setChecked(bool(is_admin))

        form_layout.addRow("E-mail:", self.input_email)
        form_layout.addRow("Role:", self.cb_admin)
        layout.addLayout(form_layout)

        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Uložit změny")
        self.btn_save.clicked.connect(self.accept)
        self.btn_cancel = QPushButton("Zrušit")
        self.btn_cancel.setObjectName("btn_cancel")
        self.btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

    def get_data(self):
        """Vrátí tuple (email, is_admin) z formuláře. is_admin je 0 nebo 1."""
        return self.input_email.text().strip(), int(self.cb_admin.isChecked())



# HLAVNÍ OKNO ADMIN PANELU


class MainAdminWindow(QMainWindow):
    """Hlavní okno administrace se třemi záložkami (Uživatelé, Cviky, Šablony).

    Toto okno se zobrazí až po úspěšném přihlášení v LoginWindow.
    Veškerá komunikace s databází probíhá přes přímé SQL dotazy (mysql-connector),
    nikoliv přes ORM (SQLAlchemy), protože tato aplikace běží mimo Flask.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("FitLife - Admin Panel")
        self.setMinimumSize(950, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Nadpis okna
        header = QLabel("Admin")
        header.setFont(QFont("Arial", 20, QFont.Bold))
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("color: #8b5cf6; margin-bottom: 10px;")
        main_layout.addWidget(header)

        # Záložky (QTabWidget) – každá záložka je samostatný QWidget
        self.tabs = QTabWidget()
        self.tab_users = QWidget()
        self.tab_exercises = QWidget()
        self.tab_templates = QWidget()

        self.tabs.addTab(self.tab_users, "Správa uživatelů")
        self.tabs.addTab(self.tab_exercises, "Seznam cviků")
        self.tabs.addTab(self.tab_templates, "Správa šablon")
        main_layout.addWidget(self.tabs)

        # Sestavení UI pro každou záložku
        self.setup_exercises_tab()
        self.setup_users_tab()
        self.setup_templates_tab()

        # Načtení dat z databáze při startu
        self.load_exercises()
        self.load_users()
        self.load_templates()

    def get_db_connection(self):
        """Vytvoří a vrátí nové připojení k MySQL. Při chybě zobrazí dialog a vrátí None."""
        try:
            return mysql.connector.connect(**DB_CONFIG)
        except Exception as e:
            QMessageBox.critical(self, "Chyba databáze", f"Nelze se připojit k databázi:\n{e}")
            return None

    
    # ZÁLOŽKA: SPRÁVA UŽIVATELŮ
   

    def setup_users_tab(self):
        """Sestaví UI záložky uživatelů – tabulka + tlačítka Upravit/Smazat."""
        layout = QVBoxLayout(self.tab_users)

        # Tabulka se sloupci: ID, E-mail, Role
        self.table_users = QTableWidget()
        self.table_users.setColumnCount(3)
        self.table_users.setHorizontalHeaderLabels(["ID", "E-mail", "Role (Admin)"])
        self.table_users.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_users.setEditTriggers(QTableWidget.NoEditTriggers)  # Zakáže přímou editaci kliknutím
        self.table_users.setSelectionBehavior(QTableWidget.SelectRows)  # Výběr celého řádku
        layout.addWidget(self.table_users)

        # Tlačítka pod tabulkou
        btn_row_layout = QHBoxLayout()

        self.btn_edit_user = QPushButton(" Upravit e-mail")
        self.btn_edit_user.setIcon(get_icon("edit.svg"))
        self.btn_edit_user.setIconSize(QSize(18, 18))
        self.btn_edit_user.clicked.connect(self.edit_user)

        self.btn_delete_user = QPushButton(" Smazat (Ban)")
        self.btn_delete_user.setIcon(get_icon("delete.svg"))
        self.btn_delete_user.setIconSize(QSize(18, 18))
        self.btn_delete_user.setObjectName("btn_delete")
        self.btn_delete_user.clicked.connect(self.delete_user)

        btn_row_layout.addStretch()  # Odsadí tlačítka doprava
        btn_row_layout.addWidget(self.btn_edit_user)
        btn_row_layout.addWidget(self.btn_delete_user)
        layout.addLayout(btn_row_layout)

    def load_users(self):
        """Načte všechny uživatele z databáze a zobrazí je v tabulce."""
        conn = self.get_db_connection()
        if not conn: return
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, email, is_admin FROM user ORDER BY id")
            records = cursor.fetchall()

            self.table_users.setRowCount(0)  # Vyčistí tabulku
            for row_number, row_data in enumerate(records):
                self.table_users.insertRow(row_number)
                for column_number, data in enumerate(row_data):
                    # Sloupec is_admin (index 2) zobrazíme jako ANO/NE místo 0/1
                    val = "ANO" if column_number == 2 and data else ("NE" if column_number == 2 else str(data))
                    item = QTableWidgetItem(val)
                    if column_number == 2:
                        item.setTextAlignment(Qt.AlignCenter)
                    self.table_users.setItem(row_number, column_number, item)
        except Exception as e:
            QMessageBox.warning(self, "Chyba", f"Chyba při načítání uživatelů:\n{e}")
        finally:
            conn.close()

    def edit_user(self):
        """Otevře dialog pro úpravu vybraného uživatele (e-mail a admin role)."""
        selected_row = self.table_users.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Pozor", "Vyber uživatele k úpravě.")
            return

        # Načtení aktuálních hodnot z tabulky
        u_id = self.table_users.item(selected_row, 0).text()
        u_email = self.table_users.item(selected_row, 1).text()
        u_is_admin = 1 if self.table_users.item(selected_row, 2).text() == "ANO" else 0

        # Otevření dialogu s předvyplněnými hodnotami
        dialog = EditUserDialog(u_id, u_email, u_is_admin, self)
        if dialog.exec_() == QDialog.Accepted:
            new_email, new_is_admin = dialog.get_data()
            if not new_email: return

            conn = self.get_db_connection()
            if not conn: return
            try:
                cursor = conn.cursor()
                cursor.execute("UPDATE user SET email=%s, is_admin=%s WHERE id=%s", (new_email, new_is_admin, u_id))
                conn.commit()
                self.load_users()  # Znovu načte tabulku s aktualizovanými daty
            except Exception as e:
                QMessageBox.warning(self, "Chyba", f"Chyba při úpravě: {e}")
            finally:
                conn.close()

    def delete_user(self):
        """Smaže uživatele i všechna jeho data (kaskádové mazání).

        Pořadí mazání je důležité kvůli cizím klíčům v databázi:
        1. Série (workout_set) → 2. Tréninky (workout_history)
        3. Vazby šablona-cvik → 4. Šablony → 5. Cviky → 6. Uživatel
        """
        selected_row = self.table_users.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Pozor", "Vyber uživatele ke smazání.")
            return

        u_id = self.table_users.item(selected_row, 0).text()
        u_email = self.table_users.item(selected_row, 1).text()

        # Potvrzovací dialog – aby se nedalo smazat omylem
        reply = QMessageBox.question(self, 'Kritické varování!',
                                     f"Opravdu chceš TRVALE smazat uživatele '{u_email}'?\n\nTato akce smaže i všechny jeho tréninky, historii a šablony. Nelze to vzít zpět!",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            conn = self.get_db_connection()
            if not conn: return
            try:
                cursor = conn.cursor()

                # Kaskádové mazání – od nejhlubších vazeb po uživatele
                # 1. Smazat série v trénincích tohoto uživatele
                cursor.execute("DELETE FROM workout_set WHERE workout_id IN (SELECT id FROM workout_history WHERE user_id=%s)", (u_id,))
                # 2. Smazat tréninky
                cursor.execute("DELETE FROM workout_history WHERE user_id=%s", (u_id,))
                # 3. Smazat vazby cviků v šablonách tohoto uživatele
                cursor.execute("DELETE FROM template_exercises WHERE template_id IN (SELECT id FROM workout_template WHERE user_id=%s)", (u_id,))
                # 4. Smazat šablony
                cursor.execute("DELETE FROM workout_template WHERE user_id=%s", (u_id,))
                # 5. Smazat série s vlastními cviky uživatele a pak cviky samotné
                cursor.execute("DELETE FROM workout_set WHERE exercise_id IN (SELECT id FROM exercise WHERE user_id=%s)", (u_id,))
                cursor.execute("DELETE FROM exercise WHERE user_id=%s", (u_id,))
                # 6. Nakonec smazat samotného uživatele
                cursor.execute("DELETE FROM user WHERE id=%s", (u_id,))

                conn.commit()
                self.load_users()
                QMessageBox.information(self, "Smazáno", f"Uživatel '{u_email}' a veškerá jeho data byla vymazána.")
            except Exception as e:
                QMessageBox.critical(self, "Chyba", f"Při mazání došlo k chybě:\n{e}")
            finally:
                conn.close()

  
    # ZÁLOŽKA: SPRÁVA CVIKŮ
  

    def setup_exercises_tab(self):
        """Sestaví UI záložky cviků – tabulka, tlačítka a formulář pro přidání."""
        layout = QVBoxLayout(self.tab_exercises)

        # Tabulka globálních cviků
        self.table_exercises = QTableWidget()
        self.table_exercises.setColumnCount(4)
        self.table_exercises.setHorizontalHeaderLabels(["ID", "Název cviku", "Sval", "Vybavení"])
        self.table_exercises.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_exercises.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_exercises.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table_exercises)

        # Tlačítka Upravit/Smazat
        btn_row_layout = QHBoxLayout()
        self.btn_edit_ex = QPushButton(" Upravit vybraný cvik")
        self.btn_edit_ex.setIcon(get_icon("edit.svg"))
        self.btn_edit_ex.setIconSize(QSize(18, 18))
        self.btn_edit_ex.clicked.connect(self.edit_exercise)

        self.btn_delete_ex = QPushButton(" Smazat vybraný cvik")
        self.btn_delete_ex.setIcon(get_icon("delete.svg"))
        self.btn_delete_ex.setIconSize(QSize(18, 18))
        self.btn_delete_ex.setObjectName("btn_delete")
        self.btn_delete_ex.clicked.connect(self.delete_exercise)
        btn_row_layout.addStretch()
        btn_row_layout.addWidget(self.btn_edit_ex)
        btn_row_layout.addWidget(self.btn_delete_ex)
        layout.addLayout(btn_row_layout)

        # Formulář pro přidání nového cviku (inline – v jednom řádku)
        form_layout = QHBoxLayout()
        self.input_ex_name = QLineEdit()
        self.input_ex_name.setPlaceholderText("Název nového cviku")

        self.combo_ex_muscle = QComboBox()
        self.combo_ex_muscle.addItems(["Prsa", "Záda", "Nohy", "Ramena", "Biceps", "Triceps", "Břicho", "Lýtka", "Celé tělo"])

        self.combo_ex_equip = QComboBox()
        self.combo_ex_equip.addItems(["Velká činka", "Jednoručky", "Stroj", "Kladka", "Vlastní váha", "Osa", "Kettlebell"])

        self.btn_add_ex = QPushButton(" Přidat do databáze")
        self.btn_add_ex.setIcon(get_icon("add.svg"))
        self.btn_add_ex.setIconSize(QSize(18, 18))
        self.btn_add_ex.clicked.connect(self.add_exercise)

        self.btn_import_csv = QPushButton(" Importovat z CSV")
        self.btn_import_csv.setIcon(get_icon("import.svg"))
        self.btn_import_csv.setIconSize(QSize(18, 18))
        self.btn_import_csv.clicked.connect(self.import_from_csv)

        form_layout.addWidget(self.input_ex_name, stretch=2)
        form_layout.addWidget(self.combo_ex_muscle, stretch=1)
        form_layout.addWidget(self.combo_ex_equip, stretch=1)
        form_layout.addWidget(self.btn_add_ex)
        form_layout.addWidget(self.btn_import_csv)
        layout.addLayout(form_layout)

    def load_exercises(self):
        """Načte globální (admin) cviky z DB a zobrazí je v tabulce.

        Zobrazuje pouze cviky s user_id=NULL a is_deleted=0.
        """
        conn = self.get_db_connection()
        if not conn: return
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, primary_muscle, equipment FROM exercise WHERE user_id IS NULL AND is_deleted = 0 ORDER BY name")
            records = cursor.fetchall()
            self.table_exercises.setRowCount(0)
            for row_number, row_data in enumerate(records):
                self.table_exercises.insertRow(row_number)
                for column_number, data in enumerate(row_data):
                    item = QTableWidgetItem(str(data))
                    self.table_exercises.setItem(row_number, column_number, item)
        except Exception as e:
            QMessageBox.warning(self, "Chyba", f"Chyba při načítání cviků: {e}")
        finally:
            conn.close()

    def add_exercise(self):
        """Přidá nový globální cvik do databáze (is_custom=0, user_id=NULL)."""
        name = self.input_ex_name.text().strip()
        muscle = self.combo_ex_muscle.currentText()
        equip = self.combo_ex_equip.currentText()
        if not name:
            QMessageBox.warning(self, "Pozor", "Název cviku nesmí být prázdný!")
            return
        conn = self.get_db_connection()
        if not conn: return
        try:
            cursor = conn.cursor()
            sql = "INSERT INTO exercise (name, primary_muscle, equipment, is_custom) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql, (name, muscle, equip, 0))
            conn.commit()
            self.input_ex_name.clear()
            self.load_exercises()
            QMessageBox.information(self, "Hotovo", f"Cvik '{name}' byl přidán.")
        except Exception as e:
            QMessageBox.critical(self, "Chyba při ukládání", f"Nastala chyba: {str(e)}")
        finally:
            conn.close()

    def edit_exercise(self):
        """Otevře dialog pro úpravu vybraného cviku a uloží změny do DB."""
        selected_row = self.table_exercises.currentRow()
        if selected_row < 0: return

        # Načtení aktuálních hodnot z vybraného řádku tabulky
        ex_id = self.table_exercises.item(selected_row, 0).text()
        current_name = self.table_exercises.item(selected_row, 1).text()
        current_muscle = self.table_exercises.item(selected_row, 2).text()
        current_equip = self.table_exercises.item(selected_row, 3).text()

        dialog = EditExerciseDialog(ex_id, current_name, current_muscle, current_equip, self)
        if dialog.exec_() == QDialog.Accepted:
            new_name, new_muscle, new_equip = dialog.get_data()
            if not new_name: return
            conn = self.get_db_connection()
            if not conn: return
            try:
                cursor = conn.cursor()
                cursor.execute("UPDATE exercise SET name=%s, primary_muscle=%s, equipment=%s WHERE id=%s", (new_name, new_muscle, new_equip, ex_id))
                conn.commit()
                self.load_exercises()
            except Exception as e:
                pass
            finally:
                conn.close()

    def delete_exercise(self):
        """Soft-delete cviku – nastaví is_deleted=1 a odebere ho ze všech šablon.

        Cvik se nesmaže fyzicky, aby zůstal v historii tréninků uživatelů.
        """
        selected_row = self.table_exercises.currentRow()
        if selected_row < 0: return
        ex_id = self.table_exercises.item(selected_row, 0).text()
        ex_name = self.table_exercises.item(selected_row, 1).text()

        reply = QMessageBox.question(self, 'Potvrdit smazání', f"Opravdu smazat '{ex_name}'?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            conn = self.get_db_connection()
            if not conn: return
            try:
                cursor = conn.cursor()
                # Soft-delete: nastavíme příznak is_deleted místo fyzického smazání
                cursor.execute("UPDATE exercise SET is_deleted = 1 WHERE id = %s", (ex_id,))
                # Odebereme cvik ze všech šablon (spojovací tabulka template_exercises)
                cursor.execute("DELETE FROM template_exercises WHERE exercise_id = %s", (ex_id,))

                conn.commit()
                self.load_exercises()
                self.populate_exercise_list()  # Aktualizujeme i seznam pro tvorbu šablon
            except Exception as err:
                QMessageBox.critical(self, "Chyba", f"Chyba při mazání: {err}")
            finally:
                conn.close()

    def import_from_csv(self):
        """Hromadný import cviků z CSV souboru (formát: Název;Sval;Vybavení).

        Podporuje kódování UTF-8, Windows-1250 a ISO-8859-2 (časté v českém Excelu).
        Duplicitní cviky (stejný název) se automaticky přeskočí.
        """
        from PyQt5.QtWidgets import QFileDialog
        import os

        # Otevřeme systémový dialog pro výběr souboru
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Vyberte CSV soubor se cviky", "", "CSV soubory (*.csv);;Všechny soubory (*.*)"
        )

        if not file_path:
            return

        conn = self.get_db_connection()
        if not conn: return

        try:
            cursor = conn.cursor()
            added_count = 0
            skipped_count = 0

            # Zkusíme postupně různá kódování (české CSV z Excelu bývá v Windows-1250)
            encodings = ['utf-8', 'windows-1250', 'iso-8859-2']
            csv_data = None

            for enc in encodings:
                try:
                    with open(file_path, mode='r', encoding=enc) as f:
                        csv_data = f.readlines()
                        break  # Kódování je správné, pokračujeme
                except UnicodeDecodeError:
                    continue  # Špatné kódování, zkusíme další

            if csv_data is None:
                QMessageBox.critical(self, "Chyba", "Nepodařilo se rozpoznat kódování souboru.")
                return

            # Parsování CSV (oddělovač = středník, první řádek = hlavička)
            reader = csv.reader(csv_data, delimiter=';')
            header = next(reader)  # Přeskočíme hlavičku (Název;Sval;Vybavení)

            for row in reader:
                if len(row) < 3: continue  # Přeskočíme neúplné řádky
                name, muscle, equip = row[0].strip(), row[1].strip(), row[2].strip()

                # Kontrola duplicity – hledáme jen mezi admin cviky (user_id IS NULL)
                cursor.execute("SELECT id FROM exercise WHERE name = %s AND user_id IS NULL", (name,))
                if cursor.fetchone():
                    skipped_count += 1
                    continue

                # Vložení nového cviku
                cursor.execute(
                    "INSERT INTO exercise (name, primary_muscle, equipment, is_custom) VALUES (%s, %s, %s, %s)",
                    (name, muscle, equip, 0)
                )
                added_count += 1

            conn.commit()
            self.load_exercises()
            self.populate_exercise_list()

            QMessageBox.information(
                self, "Import dokončen",
                f"Úspěšně importováno: {added_count} cviků\n"
                f"Přeskočeno (duplicity): {skipped_count}"
            )

        except Exception as e:
            QMessageBox.critical(self, "Chyba při importu", f"Nastala chyba:\n{e}")
        finally:
            conn.close()


    # ZÁLOŽKA: SPRÁVA ŠABLON
  

    def setup_templates_tab(self):
        """Sestaví UI záložky šablon – tabulka existujících + formulář pro novou."""
        layout = QVBoxLayout(self.tab_templates)

        # Tabulka globálních šablon s počtem cviků
        self.table_templates = QTableWidget()
        self.table_templates.setColumnCount(3)
        self.table_templates.setHorizontalHeaderLabels(["ID", "Název admin šablony", "Počet cviků"])
        self.table_templates.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_templates.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_templates.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table_templates)

        # Tlačítko smazat
        btn_row_layout = QHBoxLayout()
        self.btn_delete_tpl = QPushButton(" Smazat vybranou šablonu")
        self.btn_delete_tpl.setIcon(get_icon("delete.svg"))
        self.btn_delete_tpl.setIconSize(QSize(18, 18))
        self.btn_delete_tpl.setObjectName("btn_delete")
        self.btn_delete_tpl.clicked.connect(self.delete_template)
        btn_row_layout.addStretch()
        btn_row_layout.addWidget(self.btn_delete_tpl)
        layout.addLayout(btn_row_layout)

        # Formulář: vlevo název + tlačítko, vpravo seznam cviků k výběru
        form_layout = QHBoxLayout()

        left_form = QVBoxLayout()
        self.input_tpl_name = QLineEdit()
        self.input_tpl_name.setPlaceholderText("Název nové šablony (např. Full Body)")
        self.btn_add_tpl = QPushButton(" Vytvořit globální šablonu")
        self.btn_add_tpl.setIcon(get_icon("add.svg"))
        self.btn_add_tpl.setIconSize(QSize(18, 18))
        self.btn_add_tpl.clicked.connect(self.add_template)

        left_form.addWidget(self.input_tpl_name)
        left_form.addWidget(self.btn_add_tpl)
        left_form.addStretch()

        # Seznam cviků s možností vybrat více položek (Multi-selection)
        self.list_exercises = QListWidget()
        self.list_exercises.setSelectionMode(QAbstractItemView.MultiSelection)
        self.populate_exercise_list()

        form_layout.addLayout(left_form, stretch=1)
        form_layout.addWidget(self.list_exercises, stretch=2)

        layout.addLayout(form_layout)

    def populate_exercise_list(self):
        """Naplní QListWidget všemi globálními nesmazanými cviky pro výběr do šablony."""
        self.list_exercises.clear()
        conn = self.get_db_connection()
        if not conn: return
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name FROM exercise WHERE user_id IS NULL AND is_deleted = 0 ORDER BY name")
            for ex_id, name in cursor.fetchall():
                item = QListWidgetItem(f"{name} (ID: {ex_id})")
                # Qt.UserRole = skryté data uvnitř položky (uživatel je nevidí, ale kód s nimi může pracovat)
                item.setData(Qt.UserRole, ex_id)
                self.list_exercises.addItem(item)
        except Exception as e:
            pass
        finally:
            conn.close()

    def load_templates(self):
        """Načte globální šablony (user_id IS NULL) s počtem cviků pomocí LEFT JOIN + GROUP BY."""
        conn = self.get_db_connection()
        if not conn: return
        try:
            cursor = conn.cursor()
            # LEFT JOIN: i šablony bez cviků se zobrazí (COUNT = 0)
            cursor.execute("""
                SELECT t.id, t.name, COUNT(te.exercise_id) 
                FROM workout_template t
                LEFT JOIN template_exercises te ON t.id = te.template_id
                WHERE t.user_id IS NULL
                GROUP BY t.id, t.name
            """)
            records = cursor.fetchall()
            self.table_templates.setRowCount(0)
            for row_number, row_data in enumerate(records):
                self.table_templates.insertRow(row_number)
                for column_number, data in enumerate(row_data):
                    item = QTableWidgetItem(str(data))
                    self.table_templates.setItem(row_number, column_number, item)
        except Exception as e:
            pass
        finally:
            conn.close()

    def add_template(self):
        """Vytvoří novou globální šablonu s vybranými cviky.

        1. Vloží záznam do workout_template (user_id=NULL = globální)
        2. Pro každý vybraný cvik vloží řádek do spojovací tabulky template_exercises
        """
        name = self.input_tpl_name.text().strip()
        selected_items = self.list_exercises.selectedItems()

        if not name:
            QMessageBox.warning(self, "Pozor", "Zadej název šablony.")
            return
        if not selected_items:
            QMessageBox.warning(self, "Pozor", "Musíš vybrat alespoň jeden cvik ze seznamu.")
            return

        conn = self.get_db_connection()
        if not conn: return
        try:
            cursor = conn.cursor()
            # 1. Vložíme šablonu
            cursor.execute("INSERT INTO workout_template (name, user_id) VALUES (%s, NULL)", (name,))
            template_id = cursor.lastrowid  # lastrowid = ID právě vloženého řádku (AUTO_INCREMENT)

            # 2. Vložíme vazby na cviky do spojovací tabulky (s pozicí pro zachování pořadí)
            for position, item in enumerate(selected_items):
                ex_id = item.data(Qt.UserRole)  # Načteme skryté ID cviku z položky seznamu
                cursor.execute(
                    "INSERT INTO template_exercises (template_id, exercise_id, position) VALUES (%s, %s, %s)",
                    (template_id, ex_id, position)
                )
            conn.commit()

            self.input_tpl_name.clear()
            self.list_exercises.clearSelection()
            self.load_templates()
            QMessageBox.information(self, "Úspěch", f"Globální šablona '{name}' byla přidána!")
        except Exception as e:
            QMessageBox.critical(self, "Chyba", f"Chyba při ukládání: {e}")
        finally:
            conn.close()

    def delete_template(self):
        """Smaže globální šablonu. Nejprve smaže vazby ve spojovací tabulce, pak samotnou šablonu."""
        selected_row = self.table_templates.currentRow()
        if selected_row < 0: return
        tpl_id = self.table_templates.item(selected_row, 0).text()
        tpl_name = self.table_templates.item(selected_row, 1).text()

        reply = QMessageBox.question(self, 'Smazat šablonu', f"Opravdu smazat globální šablonu '{tpl_name}'?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            conn = self.get_db_connection()
            if not conn: return
            try:
                cursor = conn.cursor()
                # Kaskáda: nejdřív smazat vazby (spojovací tabulka), pak šablonu
                cursor.execute("DELETE FROM template_exercises WHERE template_id = %s", (tpl_id,))
                cursor.execute("DELETE FROM workout_template WHERE id = %s", (tpl_id,))
                conn.commit()
                self.load_templates()
                self.populate_exercise_list()
            except Exception as e:
                QMessageBox.critical(self, "Chyba", str(e))
            finally:
                conn.close()


# PŘIHLAŠOVACÍ OKNO


class LoginWindow(QMainWindow):
    """Přihlašovací okno – vstupní bod admin aplikace.

    Ověří, že uživatel existuje v DB, má is_admin=1 a zadal správné heslo.
    Heslo se kontroluje přes werkzeug check_password_hash (stejný hash jako na webu).
    Po úspěšném přihlášení se otevře MainAdminWindow a login okno se zavře.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("FitLife Admin - Login")
        self.setFixedSize(400, 300)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(15)

        title = QLabel("Admin Login")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Pole pro e-mail a heslo
        self.input_user = QLineEdit()
        self.input_user.setPlaceholderText("Uživatelské jméno")
        layout.addWidget(self.input_user)

        self.input_pass = QLineEdit()
        self.input_pass.setPlaceholderText("Heslo")
        self.input_pass.setEchoMode(QLineEdit.Password)  # Skryje zadávané znaky
        layout.addWidget(self.input_pass)

        self.btn_login = QPushButton("Přihlásit se")
        self.btn_login.clicked.connect(self.handle_login)
        layout.addWidget(self.btn_login)

    def handle_login(self):
        """Zpracuje přihlašovací formulář – ověří e-mail, admin roli a heslo."""
        email = self.input_user.text().strip()
        password = self.input_pass.text()

        if not email or not password:
            QMessageBox.warning(self, "Chyba", "Zadejte e-mail i heslo!")
            return

        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor(dictionary=True)  # dictionary=True → výsledky jako dict místo tuple

            # Najdeme uživatele podle e-mailu
            cursor.execute("SELECT id, email, password_hash, is_admin FROM user WHERE email = %s", (email,))
            user = cursor.fetchone()
            conn.close()

            if user:
                # Kontrola admin oprávnění
                if not user['is_admin']:
                    QMessageBox.warning(self, "Přístup odepřen", "Tento účet nemá oprávnění k administraci.")
                    return

                # Kontrola hesla přes werkzeug (stejná funkce jako na webu)
                if check_password_hash(user['password_hash'], password):
                    # Přihlášení úspěšné – otevřeme hlavní okno a zavřeme login
                    self.main_window = MainAdminWindow()
                    self.main_window.show()
                    self.close()
                else:
                    QMessageBox.warning(self, "Chyba", "Špatné heslo!")
            else:
                QMessageBox.warning(self, "Chyba", "Uživatel s tímto e-mailem nebyl nalezen!")

        except Exception as e:
            QMessageBox.critical(self, "Chyba připojení", f"Nepodařilo se ověřit přihlášení:\n{e}")


# --- Spuštění aplikace ---
# QApplication = hlavní událostní smyčka PyQt5 (musí existovat právě jedna instance)
# sys.exit(app.exec_()) = spustí smyčku a po zavření okna ukončí proces
if __name__ == "__main__":
    app = QApplication(sys.argv)
    login_window = LoginWindow()
    login_window.show()
    sys.exit(app.exec_())