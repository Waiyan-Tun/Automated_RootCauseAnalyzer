import sys
import os
import json
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QGroupBox, QGridLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QCheckBox, QMessageBox, QSpinBox, QDateEdit,
    QSizePolicy, QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea, QDialog,
    QDialogButtonBox,QApplication, QHBoxLayout, QComboBox
)
from PyQt5.QtCore import QDate, Qt
from sqlalchemy import create_engine, inspect, text
from datetime import datetime

class TableSelectDialog(QDialog):
    def __init__(self, current_tables, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Tables")
        self.current_tables = current_tables
        self.available_tables = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # Search bar for tables
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search tables...")
        self.search_bar.textChanged.connect(self.filter_tables)
        layout.addWidget(self.search_bar)

        # Table widget
        self.tables_table = QTableWidget()
        self.tables_table.setColumnCount(2)
        self.tables_table.setHorizontalHeaderLabels(["Select", "Table"])
        self.tables_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.tables_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tables_table.setColumnWidth(0, 50)
        self.tables_table.setToolTip('Select tables for auto-run')
        self.tables_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tables_table.setMinimumHeight(200)
        self.tables_table.setAlternatingRowColors(True)

        table_scroll_area = QScrollArea()
        table_scroll_area.setWidget(self.tables_table)
        table_scroll_area.setWidgetResizable(True)
        table_scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(table_scroll_area)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def set_available_tables(self, tables):
        self.available_tables = tables
        self.filter_tables()

    def filter_tables(self):
        search_text = self.search_bar.text().lower()
        filtered_tables = [table for table in self.available_tables if search_text in table.lower()]
        self.tables_table.setRowCount(len(filtered_tables))
        for row, table in enumerate(filtered_tables):
            item = QTableWidgetItem()
            item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            item.setCheckState(Qt.Checked if table in self.current_tables else Qt.Unchecked)
            self.tables_table.setItem(row, 0, item)
            self.tables_table.setItem(row, 1, QTableWidgetItem(table))

    def get_selected_tables(self):
        selected = []
        for row in range(self.tables_table.rowCount()):
            item = self.tables_table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                table = self.tables_table.item(row, 1).text()
                selected.append(table)
        return selected

class ConfigApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Configuration Editor")
        self.resize(600, 650)
        self.config = {}
        self.selected_tables = []
        self.init_ui()
        self.load_config()
        self.set_style()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # App Configuration Group
        gb = QGroupBox("App Configuration")
        gbl = QGridLayout()
        gbl.setSpacing(8)
        gbl.setContentsMargins(12, 12, 12, 12)

        # Host
        gbl.addWidget(QLabel('Host'), 0, 0)
        self.host = QLineEdit('localhost')
        self.host.setPlaceholderText('Enter host (e.g., localhost)')
        self.host.setToolTip('Enter the database server host address')
        self.host.setMinimumWidth(300)
        gbl.addWidget(self.host, 0, 1, 1, 2)

        # Port
        gbl.addWidget(QLabel('Port'), 1, 0)
        self.port = QLineEdit('3306')
        self.port.setPlaceholderText('Enter port')
        self.port.setToolTip('Enter the database port')
        gbl.addWidget(self.port, 1, 1, 1, 2)

        # User
        gbl.addWidget(QLabel('User'), 2, 0)
        self.user = QLineEdit('root')
        self.user.setPlaceholderText('Enter username')
        self.user.setToolTip('Enter the database username')
        gbl.addWidget(self.user, 2, 1, 1, 2)

        # Password
        gbl.addWidget(QLabel('Password'), 3, 0)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText('Enter password')
        self.password.setToolTip('Enter the database password')
        gbl.addWidget(self.password, 3, 1, 1, 2)

        # Database
        gbl.addWidget(QLabel('Database'), 4, 0)
        self.database = QLineEdit()
        self.database.setPlaceholderText('Enter database name')
        self.database.setToolTip('Enter the database name')
        gbl.addWidget(self.database, 4, 1, 1, 2)

        # State selection
        gbl.addWidget(QLabel('State'), 5, 0)
        self.state_combo = QComboBox()
        self.state_combo.addItems(['Auto', 'Rework', 'Single'])
        self.state_combo.setToolTip('Select state for data retrieval')
        gbl.addWidget(self.state_combo, 5, 1)
        self.apply_state_chk = QCheckBox('Apply State Filter')
        self.apply_state_chk.setChecked(True)
        self.apply_state_chk.setToolTip('If checked, apply the state filter during auto-run')
        gbl.addWidget(self.apply_state_chk, 5, 2)

        # Test Connection
        test_btn = QPushButton("Test Connection")
        test_btn.setMinimumHeight(32)
        test_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        test_btn.clicked.connect(self.test_connection)
        gbl.addWidget(test_btn, 6, 1, 1, 2)

        # Auto-save folder
        gbl.addWidget(QLabel('Auto-save HTML report to'), 7, 0)
        self.auto_save_path = QLineEdit()
        self.auto_save_path.setPlaceholderText('Select folder...')
        self.auto_save_path.setToolTip('Folder to save HTML reports during auto-run')
        gbl.addWidget(self.auto_save_path, 7, 1)
        browse_btn = QPushButton("Browse")
        browse_btn.setMinimumHeight(32)
        browse_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        browse_btn.clicked.connect(self.browse_auto_save_folder)
        gbl.addWidget(browse_btn, 7, 2)

        # HTML Filename
        gbl.addWidget(QLabel('HTML Filename'), 8, 0)
        self.html_filename = QLineEdit('ROOT CAUSE ANALYSIS')
        self.html_filename.setPlaceholderText('Enter HTML filename')
        self.html_filename.setToolTip('Filename for the generated HTML report')
        gbl.addWidget(self.html_filename, 8, 1, 1, 2)

        # HTML Title
        gbl.addWidget(QLabel('HTML Title'), 9, 0)
        self.html_title = QLineEdit('ROOT CAUSE ANALYSIS')
        self.html_title.setPlaceholderText('Enter HTML title')
        self.html_title.setToolTip('Title for the generated HTML report')
        gbl.addWidget(self.html_title, 9, 1, 1, 2)

        # Include week number checkbox
        self.include_week_chk = QCheckBox('Include Week Number in Report Name and Title')
        self.include_week_chk.setToolTip('If checked, append "Week X" to filename and title')
        gbl.addWidget(self.include_week_chk, 10, 0, 1, 3)

        # Every
        gbl.addWidget(QLabel('Every (Days)'), 11, 0)
        self.every = QSpinBox()
        self.every.setMinimum(1)
        self.every.setMaximum(365)
        self.every.setValue(7)
        self.every.setToolTip('Number of days back to retrieve data')
        gbl.addWidget(self.every, 11, 1, 1, 2)

        # Date setup
        gbl.addWidget(QLabel('Date To Generate Report'), 12, 0)
        self.date_setup = QDateEdit(QDate.currentDate())
        self.date_setup.setCalendarPopup(True)
        self.date_setup.setToolTip('Set the date for data retrieval (retrieves last N days ending the day before, where N is Every)')
        gbl.addWidget(self.date_setup, 12, 1, 1, 2)

        # Table selection
        gbl.addWidget(QLabel('Tables'), 13, 0)
        self.fetch_tables_btn = QPushButton('Fetch Tables')
        self.fetch_tables_btn.setMinimumHeight(32)
        self.fetch_tables_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.fetch_tables_btn.clicked.connect(self.fetch_tables)
        gbl.addWidget(self.fetch_tables_btn, 13, 1, 1, 2)

        self.tables_label = QLabel("No tables selected")
        gbl.addWidget(self.tables_label, 14, 0, 1, 3)

        # Auto-run checkbox
        self.auto_run = QCheckBox('Run automatically on startup')
        self.auto_run.setToolTip('If checked, the app will load config and run analysis automatically on startup')
        gbl.addWidget(self.auto_run, 15, 0, 1, 3)

        # Button layout for Save and Exit
        button_layout = QHBoxLayout()
        save_btn = QPushButton('Save Configuration')
        save_btn.setMinimumHeight(32)
        save_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        save_btn.clicked.connect(self.save_config)
        button_layout.addWidget(save_btn)

        cancel_btn = QPushButton('Exit')
        cancel_btn.setMinimumHeight(32)
        cancel_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        cancel_btn.clicked.connect(self.close)
        button_layout.addWidget(cancel_btn)

        button_widget = QWidget()
        button_widget.setLayout(button_layout)
        gbl.addWidget(button_widget, 16, 0, 1, 3)

        gbl.setColumnStretch(1, 1)
        gbl.setColumnStretch(2, 0)
        gb.setLayout(gbl)
        main_layout.addWidget(gb)
        main_layout.addStretch(1)

    def set_style(self):
        style = """
        QWidget {
            font-family: Arial, sans-serif;
            font-size: 13px;
            background-color: #ffffff;
            color: #1f2a44;
        }
        QGroupBox {
            font-weight: bold;
            font-size: 14px;
            color: #1f2a44;
            border: 1px solid #e2e8f0;
            border-radius: 5px;
            margin-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 3px;
            color: #1f2a44;
        }
        QLineEdit, QSpinBox, QDateEdit {
            padding: 6px;
            border: 1px solid #e2e8f0;
            border-radius: 5px;
            background-color: #f8fafc;
            color: #1f2a44;
            min-height: 28px;
            min-width: 200px;
        }
        QLineEdit:focus, QSpinBox:focus, QDateEdit:focus {
            border: 2px solid #6366f1;
            background-color: #ffffff;
        }
        QLineEdit::placeholder {
            color: #94a3b8;
        }
        QPushButton {
            padding: 6px 12px;
            border-radius: 6px;
            background-color: #258f98;
            color: #ffffff;
            font-weight: 500;
            border: none;
            min-height: 32px;
            min-width: 100px;
        }
        QPushButton:hover {
            background-color: #3aa5ad;
        }
        QPushButton:pressed {
            background-color: #1d6f78;
        }
        QPushButton[text="Exit"] {
            background-color: #ef4444;
        }
        QPushButton[text="Exit"]:hover {
            background-color: #f87171;
        }
        QTableWidget {
            background-color: #ffffff;
            alternate-background-color: #f8fafc;
            gridline-color: #e2e8f0;
            border-radius: 5px;
            font-size: 12px;
            selection-background-color: #e0e7ff;
            selection-color: #1f2a44;
        }
        QTableWidget::item {
            padding: 6px;
        }
        QHeaderView::section {
            background-color: #f1f5f9;
            color: #1f2a44;
            padding: 6px;
            border: none;
            font-weight: 500;
            font-size: 12px;
        }
        QScrollArea {
            background-color: #ffffff;
            border: none;
            border-radius: 5px;
        }
        QLabel {
            color: #1f2a44;
        }
        QCheckBox {
            color: #1f2a44;
            spacing: 8px;
        }
        QCheckBox::indicator {
            width: 20px;
            height: 20px;
        }
        QCheckBox::indicator:unchecked {
            image: none;
            background-color: transparent;
            border: 2px solid #e2e8f0;
            border-radius: 4px;
        }
        QCheckBox::indicator:unchecked:hover {
            border: 2px solid #6366f1;
        }
        QCheckBox::indicator:checked {
            image: none;
            background-color: #258f98;
            border: 2px solid #258f98;
            border-radius: 4px;
        }
        QCheckBox::indicator:checked:hover {
            background-color: #3aa5ad;
            border: 2px solid #3aa5ad;
        }
        QDialog {
            background-color: #ffffff;
            color: #1f2a44;
        }
        """
        self.setStyleSheet(style)

    def load_config(self):
        config_path = "JSON_Files/app_config.json"
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    self.config = json.load(f)
                self.host.setText(self.config.get("host", "localhost"))
                self.port.setText(self.config.get("port", "3306"))
                self.user.setText(self.config.get("user", "root"))
                self.password.setText(self.config.get("password", ""))
                self.database.setText(self.config.get("database", ""))
                self.auto_save_path.setText(self.config.get("auto_save_path", ""))
                self.html_filename.setText(self.config.get("html_filename", "ROOT CAUSE ANALYSIS"))
                self.html_title.setText(self.config.get("html_title", "ROOT CAUSE ANALYSIS"))
                self.include_week_chk.setChecked(self.config.get("include_week_no", True))
                self.every.setValue(self.config.get("every", 7))
                date_str = self.config.get("date_setup")
                if date_str:
                    try:
                        self.date_setup.setDate(QDate.fromString(date_str, "yyyy/MM/dd"))
                    except:
                        self.date_setup.setDate(QDate.currentDate())
                auto_run_value = self.config.get("auto_run", False)
                self.auto_run.setChecked(bool(auto_run_value))
                self.selected_tables = self.config.get("selected_tables", [])
                self.tables_label.setText(f"{len(self.selected_tables)} tables selected" if self.selected_tables else "No tables selected")
                # New fields
                state = self.config.get("state", "Auto")
                self.state_combo.setCurrentText(state)
                apply_state = self.config.get("apply_state", True)
                self.apply_state_chk.setChecked(apply_state)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load config: {str(e)}")
        else:
            self.config = {}
            self.selected_tables = []
            self.tables_label.setText("No tables selected")

    def browse_auto_save_folder(self):
        dir_ = QFileDialog.getExistingDirectory(self, "Select Folder")
        if dir_:
            self.auto_save_path.setText(dir_)

    def test_connection(self):
        host = self.host.text().strip()
        port = self.port.text().strip() or '3306'
        user = self.user.text().strip()
        password = self.password.text()
        db = self.database.text().strip()
        if not all([host, user, db]):
            QMessageBox.warning(self, "Warning", "Please fill in host, user, and database.")
            return
        try:
            conn_str = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}"
            engine = create_engine(conn_str)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            QMessageBox.information(self, "Success", "Database connection successful!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to connect to database: {str(e)}")

    def fetch_tables(self):
        host = self.host.text().strip()
        port = self.port.text().strip() or '3306'
        user = self.user.text().strip()
        password = self.password.text()
        db = self.database.text().strip()
        if not all([host, user, db]):
            QMessageBox.warning(self, "Warning", "Please fill in host, user, and database.")
            return
        try:
            conn_str = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}"
            engine = create_engine(conn_str)
            insp = inspect(engine)
            tables = insp.get_table_names()

            dialog = TableSelectDialog(self.selected_tables, self)
            dialog.set_available_tables(tables)
            dialog.resize(500, 400)
            if dialog.exec_() == QDialog.Accepted:
                self.selected_tables = dialog.get_selected_tables()
                self.tables_label.setText(f"{len(self.selected_tables)} tables selected" if self.selected_tables else "No tables selected")
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Could not fetch tables from database: {str(e)}\nUsing current table list.")
            dialog = TableSelectDialog(self.selected_tables, self)
            dialog.set_available_tables(self.selected_tables)
            dialog.resize(500, 400)
            if dialog.exec_() == QDialog.Accepted:
                self.selected_tables = dialog.get_selected_tables()
                self.tables_label.setText(f"{len(self.selected_tables)} tables selected" if self.selected_tables else "No tables selected")

    def save_config(self):
        try:
            config = {
                "host": self.host.text().strip(),
                "port": self.port.text().strip(),
                "user": self.user.text().strip(),
                "password": self.password.text(),
                "database": self.database.text().strip(),
                "auto_save_path": self.auto_save_path.text().strip(),
                "html_filename": self.html_filename.text().strip(),
                "html_title": self.html_title.text().strip(),
                "include_week_no": self.include_week_chk.isChecked(),
                "every": self.every.value(),
                "date_setup": self.date_setup.date().toString("yyyy/MM/dd"),
                "auto_run": self.auto_run.isChecked(),
                "selected_tables": self.selected_tables,
                "state": self.state_combo.currentText(),
                "apply_state": self.apply_state_chk.isChecked()
            }
            # Validate inputs
            if not config["host"]:
                raise ValueError("Host cannot be empty")
            if not config["user"]:
                raise ValueError("User cannot be empty")
            if not config["database"]:
                raise ValueError("Database cannot be empty")
            if not config["html_filename"]:
                raise ValueError("HTML Filename cannot be empty")
            if not config["html_title"]:
                raise ValueError("HTML Title cannot be empty")
            if config["every"] < 1:
                raise ValueError("Every must be at least 1 day")
            if config["auto_save_path"] and not os.path.isdir(config["auto_save_path"]):
                raise ValueError("Auto-save path must be a valid directory")
            if config["auto_run"] and not config["selected_tables"]:
                raise ValueError("At least one table must be selected when auto-run is enabled")

            with open("JSON_Files/app_config.json", "w") as f:
                json.dump(config, f, indent=4)
            QMessageBox.information(self, "Success", "Configuration saved successfully")
            self.close()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save config: {str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ConfigApp()
    window.show()
    sys.exit(app.exec_())