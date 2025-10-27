from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QGridLayout, QLabel, QLineEdit, QPushButton, QFileDialog, QCheckBox, QMessageBox, QSpinBox, QDateEdit, QSizePolicy,
    QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea, QDialog, QDialogButtonBox, QComboBox
)
from PyQt5.QtCore import QDate, Qt
import json
from app_state import log
from sqlalchemy import create_engine, inspect

class AppConfigTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        gb = QGroupBox('App Configuration')
        gbl = QGridLayout()
        gbl.setSpacing(12)
        gbl.setContentsMargins(16, 16, 16, 16)

        # Initialize fields --- Hide UI
        self.host = QLineEdit('localhost')
        self.port = QLineEdit('3306')
        self.user = QLineEdit('root')
        self.password = QLineEdit('')
        self.password.setEchoMode(QLineEdit.Password)

        #input
        gbl.addWidget(QLabel('Database'), 0, 0)
        self.database = QLineEdit()
        self.database.setPlaceholderText('Enter database name')
        self.database.setToolTip('Enter the database name')
        gbl.addWidget(self.database, 0, 1)

        # State is Testing Condition
        gbl.addWidget(QLabel('State'), 1, 0)
        self.state_combo = QComboBox()
        self.state_combo.addItems(['Auto', 'Rework', 'Single']) # Testing Condition 
        self.state_combo.setToolTip('Select state for data retrieval')
        gbl.addWidget(self.state_combo, 1, 1)
        self.apply_state_chk = QCheckBox('Apply State Filter')
        self.apply_state_chk.setChecked(True)
        self.apply_state_chk.setToolTip('If checked, apply the state filter during auto-run')
        gbl.addWidget(self.apply_state_chk, 1, 2)

        # Auto-save folder path
        gbl.addWidget(QLabel('Auto-save HTML report to'), 2, 0)
        self.auto_save_path = QLineEdit()
        self.auto_save_path.setPlaceholderText('Select folder...')
        gbl.addWidget(self.auto_save_path, 2, 1)
        browse_btn = QPushButton("Browse")
        browse_btn.setMinimumHeight(40)
        browse_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        browse_btn.clicked.connect(self.browse_auto_save_folder)
        gbl.addWidget(browse_btn, 2, 2)

        # HTML Report File Name
        gbl.addWidget(QLabel('HTML Report File Name'), 3, 0)
        self.html_filename = QLineEdit()
        self.html_filename.setPlaceholderText('Enter report filename (without .html)')
        self.html_filename.setToolTip('Enter the filename for the HTML report (without extension)')
        gbl.addWidget(self.html_filename, 3, 1, 1, 2)

        # HTML Report Title
        gbl.addWidget(QLabel('HTML Report Title'), 4, 0)
        self.html_title = QLineEdit()
        self.html_title.setPlaceholderText('Enter report title')
        self.html_title.setToolTip('Enter the title that will appear in the HTML report')
        gbl.addWidget(self.html_title, 4, 1, 1, 2)

        # Include week number checkbox
        self.include_week_chk = QCheckBox('Include Week Number in Report Name and Title')
        self.include_week_chk.setToolTip('If checked, append "Week X" to filename and title')
        gbl.addWidget(self.include_week_chk, 5, 0, 1, 3)

        # Every -- number of days the script will trace back for date range of data retrieval
        gbl.addWidget(QLabel('Every (Days)'), 6, 0)
        self.every = QSpinBox()
        self.every.setMinimum(1)
        self.every.setMaximum(365)
        self.every.setValue(7)
        self.every.setToolTip('Number of days back to retrieve data')
        gbl.addWidget(self.every, 6, 1)

        # Date setup - End date of data retrieval
        gbl.addWidget(QLabel('Date To Generate Report'), 7, 0)
        self.date_setup = QDateEdit(QDate.currentDate())
        self.date_setup.setCalendarPopup(True)
        self.date_setup.setToolTip('Set the date for data retrieval (retrieves last N days ending the day before, where N is Every)')
        gbl.addWidget(self.date_setup, 7, 1)

        # Table selection from database
        gbl.addWidget(QLabel('Tables'), 8, 0)
        self.fetch_tables_btn = QPushButton('Fetch Tables')
        self.fetch_tables_btn.setMinimumHeight(40)
        self.fetch_tables_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.fetch_tables_btn.clicked.connect(self.fetch_tables)
        gbl.addWidget(self.fetch_tables_btn, 8, 1)

        self.tables_label = QLabel("No tables selected")
        gbl.addWidget(self.tables_label, 9, 0, 1, 3)

        # Auto-run checkbox 
        self.auto_run_chk = QCheckBox('Run automatically on startup')
        self.auto_run_chk.setToolTip('If checked, the app will load config and run analysis automatically on startup')
        gbl.addWidget(self.auto_run_chk, 10, 0, 1, 3)

        # Save config setting button
        self.save_btn = QPushButton('Save Configuration')
        self.save_btn.setMinimumHeight(40)
        self.save_btn.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        self.save_btn.clicked.connect(self.save_config)
        gbl.addWidget(self.save_btn, 11, 0, 1, 3)

        gbl.setColumnStretch(1, 1)
        gbl.setColumnStretch(2, 0)
        gb.setLayout(gbl)
        layout.addWidget(gb)
        layout.addStretch(1)
        self.setLayout(layout)
        self.selected_tables = [] 

        self.load_config()

    def load_config(self):
        try:
            with open("JSON_Files/app_config.json", "r") as f:
                config = json.load(f)
            self.host.setText(config.get("host", "localhost"))
            self.port.setText(config.get("port", "3306"))
            self.user.setText(config.get("user", "root"))
            self.password.setText(config.get("password", ""))
            self.database.setText(config.get("database", ""))
            self.auto_save_path.setText(config.get("auto_save_path", ""))
            self.html_filename.setText(config.get("html_filename", ""))
            self.html_title.setText(config.get("html_title", ""))
            self.every.setValue(config.get("every", 7))
            date_str = config.get("date_setup", QDate.currentDate().toString("yyyy/MM/dd"))
            self.date_setup.setDate(QDate.fromString(date_str, "yyyy/MM/dd"))
            self.auto_run_chk.setChecked(config.get("auto_run", False))
            self.include_week_chk.setChecked(config.get("include_week_no", False))
            self.selected_tables = config.get("selected_tables", [])
            self.tables_label.setText(f"{len(self.selected_tables)} tables selected" if self.selected_tables else "No tables selected")
            state = config.get("state", "Auto")
            self.state_combo.setCurrentText(state)
            apply_state = config.get("apply_state", True)
            self.apply_state_chk.setChecked(apply_state)
        except FileNotFoundError:
            pass
        except Exception as e:
            log(f"Failed to load config: {e}", "ERROR")

    def browse_auto_save_folder(self):
        dir_ = QFileDialog.getExistingDirectory(self, "Select Folder")
        if dir_:
            self.auto_save_path.setText(dir_)

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
            log(f"Fetched {len(tables)} tables from database {db}")

            # dialog for table selection
            dialog = QDialog(self)
            dialog.setWindowTitle("Select Tables")
            dlg_layout = QVBoxLayout()

            tables_table = QTableWidget()
            tables_table.setColumnCount(2)
            tables_table.setHorizontalHeaderLabels(["Select", "Table"])
            tables_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
            tables_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
            tables_table.horizontalHeader().setStretchLastSection(True)
            tables_table.setColumnWidth(0, 50)
            tables_table.setToolTip('Select tables for auto-run')
            tables_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            tables_table.setMinimumHeight(200)
            tables_table.setRowCount(len(tables))

            for row, table in enumerate(tables):
                item = QTableWidgetItem()
                item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                item.setCheckState(Qt.Checked if table in self.selected_tables else Qt.Unchecked)
                tables_table.setItem(row, 0, item)
                tables_table.setItem(row, 1, QTableWidgetItem(table))

            table_scroll_area = QScrollArea()
            table_scroll_area.setWidget(tables_table)
            table_scroll_area.setWidgetResizable(True)
            table_scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            dlg_layout.addWidget(table_scroll_area)

            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            dlg_layout.addWidget(buttons)

            dialog.setLayout(dlg_layout)
            dialog.resize(500, 400)

            if dialog.exec_() == QDialog.Accepted:
                selected = []
                for row in range(tables_table.rowCount()):
                    item = tables_table.item(row, 0)
                    if item and item.checkState() == Qt.Checked:
                        table = tables_table.item(row, 1).text()
                        selected.append(table)
                self.selected_tables = selected
                self.tables_label.setText(f"{len(self.selected_tables)} tables selected" if self.selected_tables else "No tables selected")
        except Exception as e:
            log(f"Failed to fetch tables: {e}", "ERROR")
            QMessageBox.critical(self, "Error", f"Failed to fetch tables: {e}")

    def save_config(self):
        config = {
            "host": self.host.text().strip(),
            "port": self.port.text().strip(),
            "user": self.user.text().strip(),
            "password": self.password.text(),
            "database": self.database.text().strip(),
            "auto_save_path": self.auto_save_path.text().strip(),
            "html_filename": self.html_filename.text().strip(),
            "html_title": self.html_title.text().strip(),
            "every": self.every.value(),
            "date_setup": self.date_setup.date().toString("yyyy/MM/dd"),
            "auto_run": self.auto_run_chk.isChecked(),
            "include_week_no": self.include_week_chk.isChecked(),
            "selected_tables": self.selected_tables,
            "state": self.state_combo.currentText(),
            "apply_state": self.apply_state_chk.isChecked(),
        }
        try:
            with open("JSON_Files/app_config.json", "w") as f:
                json.dump(config, f, indent=4)
            log("Configuration saved")
            QMessageBox.information(self, "Saved", "Configuration saved successfully.")
        except Exception as e:
            log(f"Failed to save configuration: {e}", "ERROR")
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {e}")