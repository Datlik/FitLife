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

# --- PŘIPOJENÍ K DATABÁZI ---
DB_CONFIG = {
    "host": "dbs.spskladno.cz",
    "user": "student31",
    "password": "spsnet",
    "database": "vyuka31"
}

# --- CESTA K IKONÁM ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICONS_DIR = os.path.join(os.path.dirname(BASE_DIR), "icons")

def get_icon(name):
    return QIcon(os.path.join(ICONS_DIR, name))


# ==========================================
# DIALOGOVÁ OKNA PRO ÚPRAVY
# ==========================================
class EditExerciseDialog(QDialog):
    def __init__(self, ex_id, name, muscle, equip, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Upravit cvik")
        self.setFixedSize(350, 200)
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.input_name = QLineEdit(name)
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
        return self.input_name.text().strip(), self.combo_muscle.currentText(), self.combo_equip.currentText()

class EditUserDialog(QDialog):
    def __init__(self, user_id, email, is_admin, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Upravit uživatele")
        self.setFixedSize(350, 160) 
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.input_email = QLineEdit(email)
        self.check_admin = QListWidget() # Using a simple toggle logic or checkbox
        # Actually QCheckBox is better
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
        return self.input_email.text().strip(), int(self.cb_admin.isChecked())

# ==========================================
# HLAVNÍ OKNO ADMIN PANELU
# ==========================================
class MainAdminWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FitLife - Admin Panel")
        self.setMinimumSize(950, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        header = QLabel("Admin")
        header.setFont(QFont("Arial", 20, QFont.Bold))
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("color: #8b5cf6; margin-bottom: 10px;")
        main_layout.addWidget(header)


        self.tabs = QTabWidget()
        self.tab_users = QWidget()
        self.tab_exercises = QWidget()
        self.tab_templates = QWidget() 
        
        self.tabs.addTab(self.tab_users, "Správa uživatelů")
        self.tabs.addTab(self.tab_exercises, "Seznam cviků")
        self.tabs.addTab(self.tab_templates, "Správa šablon") 
        main_layout.addWidget(self.tabs)

        self.setup_exercises_tab()
        self.setup_users_tab()
        self.setup_templates_tab() 
        
        self.load_exercises()
        self.load_users()
        self.load_templates()

    def get_db_connection(self):
        try:
            return mysql.connector.connect(**DB_CONFIG)
        except Exception as e:
            QMessageBox.critical(self, "Chyba databáze", f"Nelze se připojit k databázi:\n{e}")
            return None

    # --- ZÁLOŽKA UŽIVATELŮ ---
    def setup_users_tab(self):
        layout = QVBoxLayout(self.tab_users)

        self.table_users = QTableWidget()
        self.table_users.setColumnCount(3) # ID, Email, Role
        self.table_users.setHorizontalHeaderLabels(["ID", "E-mail", "Role (Admin)"])
        self.table_users.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_users.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_users.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table_users)

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
        
        btn_row_layout.addStretch()
        btn_row_layout.addWidget(self.btn_edit_user)
        btn_row_layout.addWidget(self.btn_delete_user)
        layout.addLayout(btn_row_layout)

    def load_users(self):
        conn = self.get_db_connection()
        if not conn: return
        try:
            cursor = conn.cursor()
            # Čteme už jen ID a E-mail
            cursor.execute("SELECT id, email, is_admin FROM user ORDER BY id")
            records = cursor.fetchall()

            self.table_users.setRowCount(0)
            for row_number, row_data in enumerate(records):
                self.table_users.insertRow(row_number)
                for column_number, data in enumerate(row_data):
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
        selected_row = self.table_users.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Pozor", "Vyber uživatele k úpravě.")
            return

        u_id = self.table_users.item(selected_row, 0).text()
        u_email = self.table_users.item(selected_row, 1).text()
        u_is_admin = 1 if self.table_users.item(selected_row, 2).text() == "ANO" else 0

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
                self.load_users()
            except Exception as e:
                QMessageBox.warning(self, "Chyba", f"Chyba při úpravě: {e}")
            finally:
                conn.close()

    def delete_user(self):
        selected_row = self.table_users.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Pozor", "Vyber uživatele ke smazání.")
            return

        u_id = self.table_users.item(selected_row, 0).text()
        u_email = self.table_users.item(selected_row, 1).text()

        reply = QMessageBox.question(self, 'Kritické varování!', 
                                     f"Opravdu chceš TRVALE smazat uživatele '{u_email}'?\n\nTato akce smaže i všechny jeho tréninky, historii a šablony. Nelze to vzít zpět!",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            conn = self.get_db_connection()
            if not conn: return
            try:
                cursor = conn.cursor()
                
                # Kaskádové mazání
                cursor.execute("DELETE FROM workout_set WHERE workout_id IN (SELECT id FROM workout_history WHERE user_id=%s)", (u_id,))
                cursor.execute("DELETE FROM workout_history WHERE user_id=%s", (u_id,))
                cursor.execute("DELETE FROM template_exercises WHERE template_id IN (SELECT id FROM workout_template WHERE user_id=%s)", (u_id,))
                cursor.execute("DELETE FROM workout_template WHERE user_id=%s", (u_id,))
                cursor.execute("DELETE FROM workout_set WHERE exercise_id IN (SELECT id FROM exercise WHERE user_id=%s)", (u_id,))
                cursor.execute("DELETE FROM exercise WHERE user_id=%s", (u_id,))
                cursor.execute("DELETE FROM user WHERE id=%s", (u_id,))
                
                conn.commit()
                self.load_users()
                QMessageBox.information(self, "Smazáno", f"Uživatel '{u_email}' a veškerá jeho data byla vymazána.")
            except Exception as e:
                QMessageBox.critical(self, "Chyba", f"Při mazání došlo k chybě:\n{e}")
            finally:
                conn.close()

    # --- ZÁLOŽKA CVIKŮ ---
    def setup_exercises_tab(self):
        layout = QVBoxLayout(self.tab_exercises)

        self.table_exercises = QTableWidget()
        self.table_exercises.setColumnCount(4)
        self.table_exercises.setHorizontalHeaderLabels(["ID", "Název cviku", "Sval", "Vybavení"])
        self.table_exercises.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_exercises.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_exercises.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table_exercises)

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
            # Přidáme is_custom a pošleme tam 0 (False)
            sql = "INSERT INTO exercise (name, primary_muscle, equipment, is_custom) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql, (name, muscle, equip, 0))
            conn.commit()
            self.input_ex_name.clear()
            self.load_exercises()
            # Přidej info o úspěchu
            QMessageBox.information(self, "Hotovo", f"Cvik '{name}' byl přidán.")
        except Exception as e:
            # ZMĚNA: Tady uvidíš, co se databázi nelíbí!
            QMessageBox.critical(self, "Chyba při ukládání", f"Nastala chyba: {str(e)}")
        finally:
            conn.close()

    def edit_exercise(self):
        selected_row = self.table_exercises.currentRow()
        if selected_row < 0: return
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
                # Soft delete
                cursor.execute("UPDATE exercise SET is_deleted = 1 WHERE id = %s", (ex_id,))
                
                # Také je chceme případně odebrat ze všech globálních šablon, pokud dbáme na to samé co web
                cursor.execute("DELETE FROM template_exercises WHERE exercise_id = %s", (ex_id,))
                
                conn.commit()
                self.load_exercises()
                self.populate_exercise_list()
            except Exception as err:
                QMessageBox.critical(self, "Chyba", f"Chyba při mazání: {err}")
            finally:
                conn.close()

    def import_from_csv(self):
        from PyQt5.QtWidgets import QFileDialog
        import os

        # Otevřeme průzkumník pro výběr souboru
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
            
            # Zkusíme otevřít s UTF-8, pokud selže, zkusíme windows-1250 (časté v Excelu)
            encodings = ['utf-8', 'windows-1250', 'iso-8859-2']
            csv_data = None
            
            for enc in encodings:
                try:
                    with open(file_path, mode='r', encoding=enc) as f:
                        # Přečteme vše najednou, abychom ověřili kódování
                        csv_data = f.readlines()
                        break
                except UnicodeDecodeError:
                    continue
            
            if csv_data is None:
                QMessageBox.critical(self, "Chyba", "Nepodařilo se rozpoznat kódování souboru.")
                return

            # Použijeme csv.reader na řádky
            reader = csv.reader(csv_data, delimiter=';')
            header = next(reader) # Přeskočíme hlavičku (Název;Sval;Vybavení)

            for row in reader:
                if len(row) < 3: continue
                name, muscle, equip = row[0].strip(), row[1].strip(), row[2].strip()
                
                # Kontrola duplicity (koukáme jen na admin cviky)
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
            self.populate_exercise_list() # Aktualizujeme i seznam pro tvorbu šablon
            
            QMessageBox.information(
                self, "Import dokončen", 
                f"Úspěšně importováno: {added_count} cviků\n"
                f"Přeskočeno (duplicity): {skipped_count}"
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Chyba při importu", f"Nastala chyba:\n{e}")
        finally:
            conn.close()
# ==========================================
    # --- ZÁLOŽKA ŠABLON (NOVÉ) ---
    # ==========================================
    def setup_templates_tab(self):
        layout = QVBoxLayout(self.tab_templates)

        # Tabulka existujících šablon
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

        # Formulář pro přidání nové šablony
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

        # Seznam cviků (umožňuje vybrat více položek)
        self.list_exercises = QListWidget()
        self.list_exercises.setSelectionMode(QAbstractItemView.MultiSelection)
        self.populate_exercise_list() # Naplní seznam

        form_layout.addLayout(left_form, stretch=1)
        form_layout.addWidget(self.list_exercises, stretch=2)

        layout.addLayout(form_layout)

    def populate_exercise_list(self):
        """Vytáhne z DB všechny předdefinované cviky a vloží je do výběru pro šablonu."""
        self.list_exercises.clear()
        conn = self.get_db_connection()
        if not conn: return
        try:
            cursor = conn.cursor()
            # Do admin šablony dáváme jen předdefinované cviky, které nejsou smazané
            cursor.execute("SELECT id, name FROM exercise WHERE user_id IS NULL AND is_deleted = 0 ORDER BY name")
            for ex_id, name in cursor.fetchall():
                item = QListWidgetItem(f"{name} (ID: {ex_id})")
                item.setData(Qt.UserRole, ex_id) # Schováme si ID cviku do objektu na pozadí
                self.list_exercises.addItem(item)
        except Exception as e:
            pass
        finally:
            conn.close()

    def load_templates(self):
        conn = self.get_db_connection()
        if not conn: return
        try:
            cursor = conn.cursor()
            # Získáme šablony, které nemají user_id a spočítáme, kolik v nich je cviků
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
            # 1. Vložíme šablonu s user_id = NULL
            cursor.execute("INSERT INTO workout_template (name, user_id) VALUES (%s, NULL)", (name,))
            template_id = cursor.lastrowid # Tímto zjistíme IDčkou nově vytvořené šablony!
            
            # 2. Vložíme do spojovací tabulky všechny vybrané cviky
            for position, item in enumerate(selected_items):
                ex_id = item.data(Qt.UserRole)
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
                # Zase Kaskáda! Nejdřív smazat papíry (vazby na cviky), pak složku (šablonu)
                cursor.execute("DELETE FROM template_exercises WHERE template_id = %s", (tpl_id,))
                cursor.execute("DELETE FROM workout_template WHERE id = %s", (tpl_id,))
                conn.commit()
                self.load_templates()
                self.populate_exercise_list()
            except Exception as e:
                QMessageBox.critical(self, "Chyba", str(e))
            finally:
                conn.close()
# ==========================================
# LOGIN OKNO
# ==========================================
class LoginWindow(QMainWindow):
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

        self.input_user = QLineEdit()
        self.input_user.setPlaceholderText("Uživatelské jméno")
        layout.addWidget(self.input_user)

        self.input_pass = QLineEdit()
        self.input_pass.setPlaceholderText("Heslo")
        self.input_pass.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.input_pass)

        self.btn_login = QPushButton("Přihlásit se")
        self.btn_login.clicked.connect(self.handle_login)
        layout.addWidget(self.btn_login)

    def handle_login(self):
        email = self.input_user.text().strip()
        password = self.input_pass.text()

        if not email or not password:
            QMessageBox.warning(self, "Chyba", "Zadejte e-mail i heslo!")
            return

        try:
            # Připojíme se k DB pro ověření (použijeme DB_CONFIG)
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor(dictionary=True)
            
            # Najdeme uživatele podle e-mailu
            cursor.execute("SELECT id, email, password_hash, is_admin FROM user WHERE email = %s", (email,))
            user = cursor.fetchone()
            conn.close()

            if user:
                # 1. Kontrola, zda je to admin (is_admin == 1)
                if not user['is_admin']:
                    QMessageBox.warning(self, "Přístup odepřen", "Tento účet nemá oprávnění k administraci.")
                    return
                
                # 2. Kontrola hesla pomocí werkzeug
                if check_password_hash(user['password_hash'], password):
                    self.main_window = MainAdminWindow()
                    self.main_window.show()
                    self.close()
                else:
                    QMessageBox.warning(self, "Chyba", "Špatné heslo!")
            else:
                QMessageBox.warning(self, "Chyba", "Uživatel s tímto e-mailem nebyl nalezen!")

        except Exception as e:
            QMessageBox.critical(self, "Chyba připojení", f"Nepodařilo se ověřit přihlášení:\n{e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    login_window = LoginWindow()
    login_window.show()
    sys.exit(app.exec_())