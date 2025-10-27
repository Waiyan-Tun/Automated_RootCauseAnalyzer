from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QGridLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QComboBox, QMessageBox, QSizePolicy
)
from PyQt5.QtCore import Qt
from sqlalchemy import create_engine, text
import os
from app_state import AppState, log

class ConfigTab(QWidget):
    def __init__(self, app=None, parent=None):
        super().__init__(parent)
        self.app = app
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        gb = QGroupBox('Database Connection')
        gbl = QGridLayout()
        gbl.setSpacing(12)
        gbl.setContentsMargins(16, 16, 16, 16)

        # Host
        gbl.addWidget(QLabel('Host'), 0, 0)
        self.host = QLineEdit('localhost')
        self.host.setPlaceholderText('Enter host (e.g., localhost)')
        self.host.setToolTip('Enter the database server host address')
        self.host.setMinimumWidth(300)
        gbl.addWidget(self.host, 0, 1)

        # Port number
        gbl.addWidget(QLabel('Port'), 1, 0)
        self.port = QLineEdit('3306')
        self.port.setPlaceholderText('Enter port')
        self.port.setToolTip('Enter the database port')
        gbl.addWidget(self.port, 1, 1)

        # Username
        gbl.addWidget(QLabel('User'), 2, 0)
        self.user = QLineEdit('root')
        self.user.setPlaceholderText('Enter username')
        self.user.setToolTip('Enter the database username')
        gbl.addWidget(self.user, 2, 1)

        # Password 
        gbl.addWidget(QLabel('Password'), 3, 0)
        self.password = QLineEdit('')
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText('Enter password')
        self.password.setToolTip('Enter the database password')
        gbl.addWidget(self.password, 3, 1)

        # Buttons + database selection
        btn_row = QHBoxLayout()
        self.connect_btn = QPushButton('Connect to Server')
        self.connect_btn.setToolTip('Connect to the database server')
        self.connect_btn.setMinimumHeight(40)
        self.connect_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        btn_row.addWidget(self.connect_btn)
        self.db_combo = QComboBox()
        self.db_combo.setMinimumWidth(250)
        self.db_combo.setToolTip('Select a database from the server')
        btn_row.addWidget(self.db_combo)
        self.use_db_btn = QPushButton('Use Database')
        self.use_db_btn.setToolTip('Use the selected database')
        self.use_db_btn.setMinimumHeight(40)
        self.use_db_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        btn_row.addWidget(self.use_db_btn)
        btn_row.addStretch(1)
        gbl.addLayout(btn_row, 4, 0, 1, 2)

        gbl.setColumnStretch(1, 1)
        gb.setLayout(gbl)
        layout.addWidget(gb)
        layout.addStretch(1)
        self.setLayout(layout)

        self.connect_btn.clicked.connect(self.connect_server)
        self.use_db_btn.clicked.connect(self.use_db)

    def connect_server(self):
        host = self.host.text().strip()
        port = self.port.text().strip() or '3306'
        user = self.user.text().strip()
        password = self.password.text()
        try:
            self.setCursor(Qt.WaitCursor)
            conn_str = f"mysql+pymysql://{user}:{password}@{host}:{port}/"
            engine = create_engine(conn_str)
            conn = engine.connect()
            databases = [row[0] for row in conn.execute(text('SHOW DATABASES')).fetchall()]
            conn.close()
            AppState.engine = engine
            self.db_combo.clear()
            self.db_combo.addItems(databases)
            log(f"Connected to {host}:{port}, found databases: {databases}")
            QMessageBox.information(self, 'Connected', f'Connected to server {host}:{port}')
        except Exception as e:
            log(f"MySQL connect failed: {e}", 'WARN')
            sqlite_files = [f for f in os.listdir('.') if f.endswith('.sqlite') or f.endswith('.db')]
            if sqlite_files:
                self.db_combo.clear()
                self.db_combo.addItems(sqlite_files)
                QMessageBox.information(self, 'Fallback', 'MySQL connect failed. Found sqlite files in folder.')
            else:
                QMessageBox.critical(self, 'Error', f'Could not connect: {e}')
        finally:
            self.unsetCursor()

    def use_db(self):
        db = self.db_combo.currentText()
        if not db:
            QMessageBox.warning(self, 'No DB', 'Please select a database')
            return
        if AppState.engine and str(AppState.engine.url.drivername).startswith('mysql'):
            host = self.host.text().strip()
            port = self.port.text().strip() or '3306'
            user = self.user.text().strip()
            password = self.password.text()
            conn_str = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}"
            AppState.engine = create_engine(conn_str)
            AppState.selected_database = db
            log(f"Using database {db}")
            QMessageBox.information(self, 'DB Selected', f'Using database {db}')
            if self.app:
                self.app.setCurrentIndex(1)
                self.app.data_tab.refresh_tables()
            else:
                log("Could not find RuleAnalyzerApp instance", "ERROR")
                QMessageBox.critical(self, 'Error', 'Internal error: Could not access Data Selection tab')
        else:
            AppState.selected_database = db
            conn_str = f"sqlite:///{db}"
            AppState.engine = create_engine(conn_str)
            log(f"Using sqlite DB {db}")
            QMessageBox.information(self, 'DB Selected', f'Using sqlite DB {db}')
            if self.app:
                self.app.setCurrentIndex(1)
                self.app.data_tab.refresh_tables()
            else:
                log("Could not find RuleAnalyzerApp instance", "ERROR")
                QMessageBox.critical(self, 'Error', 'Internal error: Could not access Data Selection tab')