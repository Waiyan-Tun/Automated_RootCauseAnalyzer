import os
import json
from datetime import datetime, timedelta, time, date
import numpy as np
import pandas as pd
import base64
from io import BytesIO
import webbrowser
from PyQt5.QtWidgets import (
    QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QGroupBox, QMessageBox, QTableWidget, 
    QTableWidgetItem, QDialog, QFileDialog, QTextEdit, QCheckBox, QProgressDialog, QScrollArea, QSizePolicy, QHeaderView, 
    QDialogButtonBox, QGridLayout, QLineEdit, QApplication
)
from PyQt5.QtCore import Qt, QDate, QDateTime, QTime, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QPixmap
from sqlalchemy import create_engine, inspect, text
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from app_state import AppState, log
from db_credentials import ConfigTab
from data_tab import DataTab
from app_config_tab import AppConfigTab
from analysis_utils import analyze_row_with_path
from data_utils import safe_to_datetime, strip_dataframe  
from dialogs import PreviewDialog

class AnalysisWorker(QThread):
    progress = pyqtSignal(int)
    log_signal = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, selected, parent=None):
        super().__init__(parent)
        self.selected = selected

    def run(self):
        try:
            analyzed_dfs = {}
            total_rows = sum(len(AppState.retrieved_dfs.get(station, pd.DataFrame())) for station, _ in self.selected)
            current_progress = 0
            for station, model in self.selected:
                if self.isInterruptionRequested():
                    self.log_signal.emit("Analysis canceled")
                    return
                if station not in AppState.rules:
                    continue
                try:
                    rule_list = AppState.rules[station]["models"][model]["rules"]
                    rule = rule_list[0] if isinstance(rule_list, list) else rule_list
                except KeyError:
                    continue
                df = AppState.retrieved_dfs.get(station, pd.DataFrame()).copy()
                if df.empty:
                    continue
                self.log_signal.emit(f"Analyzing station: {station}, model: {model}, rows: {len(df)}")
                if "Result" not in df.columns:
                    df["Result"] = ""
                preds = []
                causes = []
                paths = []
                for _, row in df.iterrows():
                    if self.isInterruptionRequested():
                        self.log_signal.emit("Analysis canceled")
                        return
                    pred, cause, path = analyze_row_with_path(row, rule)
                    preds.append(pred)
                    causes.append(cause)
                    paths.append(path)
                    current_progress += 1
                    self.progress.emit(current_progress * 100 // total_rows if total_rows > 0 else 0)
                df["Prediction"] = preds
                df["Root_Cause"] = causes
                df["Match_Path"] = paths
                analyzed_dfs[station] = df
                self.log_signal.emit(f"Completed analysis for {station}")
            self.finished.emit(analyzed_dfs)
        except Exception as e:
            self.error.emit(str(e))

class AutoRunWorker(QThread):
    log_signal = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config

    def run(self):
        try:
            self.log_signal.emit("Starting auto-run... App will close automatically after completion.")

            host = self.config.get("host")
            port = self.config.get("port") or "3306"
            user = self.config.get("user")
            password = self.config.get("password")
            db = self.config.get("database")
            if not all([host, user, db]):
                self.log_signal.emit("Incomplete configuration for auto-run")
                return
            try:
                conn_str = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}"
                AppState.engine = create_engine(conn_str)
                AppState.selected_database = db
                self.log_signal.emit(f"Auto-connected to database {db} on {host}:{port}")
            except Exception as e:
                self.log_signal.emit(f"Auto-connect failed: {e}")
                return

            # Auto Refresh tables
            try:
                insp = inspect(AppState.engine)
                tables = insp.get_table_names()
                selected_tables = self.config.get("selected_tables", tables)  
                AppState.selected_tables = selected_tables
                self.log_signal.emit(f"Auto-selected tables: {selected_tables}")
            except Exception as e:
                self.log_signal.emit(f"Error refreshing tables in auto-run: {e}")
                return

            # Date setup
            date_str = self.config.get("date_setup")
            every = self.config.get("every", 7)
            if date_str:
                end_date = datetime.strptime(date_str, "%Y/%m/%d").date()
                from_date = end_date - timedelta(days=every)
                to_date = end_date
                dt_from = datetime.combine(from_date, time(8, 0, 0)).strftime('%Y-%m-%d %H:%M:%S') #standard start time of a operation day
                dt_to = datetime.combine(to_date, time(7, 59, 59)).strftime('%Y-%m-%d %H:%M:%S')#standard end time of a operation day
            else:
                current = datetime.now()
                end_date = current.date()
                from_date = end_date - timedelta(days=every)
                to_date = end_date
                dt_from = datetime.combine(from_date, time(8, 0, 0)).strftime('%Y-%m-%d %H:%M:%S')
                dt_to = datetime.combine(to_date, time(7, 59, 59)).strftime('%Y-%m-%d %H:%M:%S')

            state = self.config.get("state", "Auto") if self.config.get("apply_state", True) else None
            AppState.state = state
            self.log_signal.emit(f"Auto-retrieving data: state={state if state else 'None'}, from={dt_from}, to={dt_to}")

            #Retrieve data
            dfs = {}
            for table in AppState.selected_tables:
                if self.isInterruptionRequested():
                    self.log_signal.emit("Auto-run canceled")
                    return
                base_query = f"SELECT * FROM `{table}`"
                conditions = []
                params = {}
                if state:
                    conditions.append("State = :state")
                    params['state'] = state
                conditions.append("Date_Time BETWEEN :from_dt AND :to_dt")
                params['from_dt'] = dt_from
                params['to_dt'] = dt_to
                if conditions:
                    query = base_query + " WHERE " + " AND ".join(conditions)
                else:
                    query = base_query
                try:
                    df = pd.read_sql_query(text(query), AppState.engine, params=params)
                    self.log_signal.emit(f"Auto-retrieved {len(df)} rows from {table}")
                except Exception as e:
                    self.log_signal.emit(f"Retrieve failed for {table} in auto-run: {e}")
                    df = pd.DataFrame()
                df = strip_dataframe(df)
                dfs[table] = df
            AppState.retrieved_dfs = dfs
            self.log_signal.emit("Auto-data retrieval completed.")

            # Select stations and models
            selected = []
            for station in AppState.selected_tables:
                if station in AppState.rules:
                    models = list(AppState.rules[station].get("models", {}).keys())
                    if models:
                        model = models[0]  # Select first model
                        selected.append((station, model))

            if not selected:
                self.log_signal.emit("No stations with models for auto-analysis")
                return

            # Run analysis
            self.log_signal.emit("Starting auto-analysis...")
            analyzed_dfs = {}
            for station, model in selected:
                if self.isInterruptionRequested():
                    self.log_signal.emit("Auto-run canceled")
                    return
                if station not in AppState.rules:
                    continue
                try:
                    rule_list = AppState.rules[station]["models"][model]["rules"]
                    rule = rule_list[0] if isinstance(rule_list, list) else rule_list
                except KeyError:
                    continue
                df = AppState.retrieved_dfs.get(station, pd.DataFrame()).copy()
                if df.empty:
                    continue
                self.log_signal.emit(f"Analyzing {station}, model {model}, rows {len(df)}")
                if "Result" not in df.columns:
                    df["Result"] = ""
                preds = []
                causes = []
                paths = []
                for _, row in df.iterrows():
                    if self.isInterruptionRequested():
                        self.log_signal.emit("Auto-run canceled")
                        return
                    pred, cause, path = analyze_row_with_path(row, rule)
                    preds.append(pred)
                    causes.append(cause)
                    paths.append(path)
                df["Prediction"] = preds
                df["Root_Cause"] = causes
                df["Match_Path"] = paths
                analyzed_dfs[station] = df
                self.log_signal.emit(f"Completed analysis for {station}")
            AppState.analyzed_dfs = analyzed_dfs
            self.log_signal.emit("Auto-analysis completed.")

            # Update the date setup after auto-run completed
            date_str = self.config.get("date_setup")
            if date_str:
                end_date = datetime.strptime(date_str, "%Y/%m/%d").date()
                new_end_date = end_date + timedelta(days=every)
                self.config["date_setup"] = new_end_date.strftime("%Y/%m/%d")
                with open("JSON_Files/app_config.json", "w") as f:
                    json.dump(self.config, f)
                self.log_signal.emit(f"Updated config date to {self.config['date_setup']}")

            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

class RuleAnalyzerApp(QTabWidget): #GUI HERE
    def __init__(self):
        super().__init__()
        self.auto_running = False
        self.setWindowTitle("RCA")
        self.resize(1400, 900)
        self.setMinimumSize(1000, 700)

        # Initialize tabs
        self.db_credentials = ConfigTab(app=self, parent=self)
        self.addTab(self.db_credentials, "Database Configuration")
        self.data_tab = DataTab(app=self, parent=self)
        self.addTab(self.data_tab, "Data Selection")
        self.analyze_tab = QWidget()
        self.addTab(self.analyze_tab, "Analysis")
        self.log_tab = QWidget()
        self.addTab(self.log_tab, "Log")
        self.app_config_tab = AppConfigTab(self)
        self.addTab(self.app_config_tab, "App Configuration")

        self.build_analyze_tab()
        self.build_log_tab()

        AppState.log_signal.log_updated.connect(self.update_log)
        self.set_style()
        self.load_app_config()

        if not self.auto_running:
            self.show()

    def load_app_config(self):
        if os.path.exists("JSON_Files/app_config.json"):
            try:
                with open("JSON_Files/app_config.json", "r") as f:
                    config = json.load(f)
                self.db_credentials.host.setText(config.get("host", "localhost"))
                self.db_credentials.port.setText(config.get("port", "3306"))
                self.db_credentials.user.setText(config.get("user", "root"))
                self.db_credentials.password.setText(config.get("password", ""))
                self.app_config_tab.host.setText(config.get("host", "localhost"))
                self.app_config_tab.port.setText(config.get("port", "3306"))
                self.app_config_tab.user.setText(config.get("user", "root"))
                self.app_config_tab.password.setText(config.get("password", ""))
                self.app_config_tab.database.setText(config.get("database", ""))
                self.app_config_tab.auto_save_path.setText(config.get("auto_save_path", ""))
                self.app_config_tab.html_filename.setText(config.get("html_filename", ""))
                self.app_config_tab.html_title.setText(config.get("html_title", "Report Title"))
                self.app_config_tab.every.setValue(config.get("every", 7))
                date_str = config.get("date_setup")
                if date_str:
                    self.app_config_tab.date_setup.setDate(QDate.fromString(date_str, "yyyy/MM/dd"))
                self.app_config_tab.auto_run_chk.setChecked(config.get("auto_run", False))
                self.app_config_tab.selected_tables = config.get("selected_tables", [])
                self.app_config_tab.include_week_chk.setChecked(config.get("include_week_no", True))
                self.app_config_tab.tables_label.setText(f"{len(self.app_config_tab.selected_tables)} tables selected" if self.app_config_tab.selected_tables else "No tables selected")
                self.auto_save_path.setText(config.get("auto_save_path", ""))
                self.auto_save_chk.setChecked(True)
            except Exception as e:
                log(f"Failed to load app_config.json: {e}", "ERROR")

    def perform_auto_run(self, config):
        self.config = config
        #minimal log window only for auto run
        self.log_dlg = QDialog()
        self.log_dlg.setWindowTitle("Auto-Run Log")
        layout = QVBoxLayout()
        
        #Warning label
        warning_label = QLabel("Do not turn off the program")
        warning_label.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 16px; margin-bottom: 10px;")
        warning_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(warning_label)
        
        self.auto_log_text = QTextEdit()
        self.auto_log_text.setReadOnly(True)
        self.auto_log_text.setStyleSheet("font-family: 'Courier New', monospace; font-size: 12px; padding: 6px;")
        layout.addWidget(self.auto_log_text)
        self.log_dlg.setLayout(layout)
        self.log_dlg.resize(600, 400)
        self.log_dlg.show()

        def update_auto_log():
            self.auto_log_text.setText("\n".join(AppState.logs))
            self.auto_log_text.verticalScrollBar().setValue(self.auto_log_text.verticalScrollBar().maximum())
            QApplication.processEvents()

        AppState.log_signal.log_updated.connect(update_auto_log)
        update_auto_log()  

        self.auto_worker = AutoRunWorker(config)
        self.auto_worker.log_signal.connect(lambda msg: log(msg))
        self.auto_worker.finished.connect(self.handle_auto_finished)
        self.auto_worker.error.connect(lambda err: (log(f"Auto-run error: {err}", "ERROR"), QTimer.singleShot(5000, lambda: (self.log_dlg.close(), QApplication.quit())) ))
        self.auto_worker.start()

    def handle_auto_finished(self):
        self.auto_save_chk.setChecked(True)
        self.auto_save_path.setText(self.config.get("auto_save_path", ""))
        self.auto_open_html_report()
        log("Auto-run completed. Closing in 15 seconds...")
        QTimer.singleShot(15000, lambda: (self.log_dlg.close(), QApplication.quit()))

    def run_analysis(self):
        selected = []
        for row in range(self.tables_table.rowCount()):
            chk_item = self.tables_table.item(row, 0)
            if chk_item and chk_item.checkState() == Qt.Checked:
                station = self.tables_table.item(row, 1).text()
                model_combo = self.tables_table.cellWidget(row, 2)
                if model_combo:
                    model = model_combo.currentText()
                    selected.append((station, model))

        if not selected:
            QMessageBox.warning(self, "Warning", "No stations selected for analysis.")
            return

        total_rows = sum(len(AppState.retrieved_dfs.get(station, pd.DataFrame())) for station, _ in selected)
        if total_rows == 0:
            QMessageBox.information(self, "Info", "No data to analyze.")
            return

        self.prog = QProgressDialog("Analyzing...", "Cancel", 0, 100, self)
        self.prog.setWindowModality(Qt.WindowModal)
        self.prog.setMinimumDuration(0)
        default_size = self.prog.size()
        self.prog.resize(int(default_size.width() * 2.0), int(default_size.height() * 2.0))
        self.prog.setMinimumSize(500, 150)

        self.worker = AnalysisWorker(selected)
        self.worker.progress.connect(self.prog.setValue)
        self.worker.log_signal.connect(lambda msg: log(msg))
        self.worker.finished.connect(self.handle_analysis_finished)
        self.worker.error.connect(lambda err: (log(f"Analysis error: {err}", "ERROR"), self.prog.close()))
        self.prog.canceled.connect(self.worker.requestInterruption)
        self.worker.start()
        self.prog.show()

    def handle_analysis_finished(self, analyzed_dfs):
        AppState.analyzed_dfs = analyzed_dfs
        log("Analysis completed")
        msg = QMessageBox(self)
        msg.setIconPixmap(QPixmap("src/Success.svg").scaled(100, 100, Qt.KeepAspectRatio))
        msg.setText("Analysis completed. See results in the browser.")
        msg.setWindowTitle("Finished")
        msg.exec_()
        self.auto_open_html_report()
        
    def currentChanged(self, index):
        super().currentChanged(index)
        if index == 2:
            self.update_for_new_data()
        elif index == 3:
            self.update_log()

    def build_log_tab(self):
        layout = QVBoxLayout(self.log_tab)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setToolTip('View application logs')
        layout.addWidget(self.log_text, 1)
        btn = QPushButton("Download Log")
        btn.setToolTip('Save logs to a text file')
        btn.setMinimumHeight(40)
        btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        btn.clicked.connect(self.download_log)
        layout.addWidget(btn)
        self.update_log()

    def update_log(self):
        self.log_text.setText("\n".join(AppState.logs))

    def download_log(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Log", "app_log.txt", "Text File (*.txt)")
        if path:
            try:
                with open(path, "w") as f:
                    f.write("\n".join(AppState.logs))
                log(f"Log saved to {path}")
                QMessageBox.information(self, "Saved", f"Log saved to {path}")
            except Exception as e:
                log(f"Failed to save log: {e}", "ERROR")
                QMessageBox.critical(self, "Error", f"Failed to save log: {e}")

    def set_style(self):
        style = """
        /* Global Styles */
        QWidget {
            font-family: Arial, sans-serif;
            font-size: 13px;
            background-color: #ffffff;
            color: #1f2a44;
        }

        /* Input Fields */
        QLineEdit, QComboBox, QDateTimeEdit, QDateEdit, QSpinBox {
            padding: 8px;
            border: 1px solid #e2e8f0;
            border-radius: 5px;
            background-color: #f8fafc;
            color: #1f2a44;
            font-size: 13px;
            min-height: 30px;
            min-width: 200px; /* Ensure fields have sufficient length */
        }
        QLineEdit:focus, QComboBox:focus, QDateTimeEdit:focus, QDateEdit:focus, QSpinBox:focus {
            border: 2px solid #6366f1;
            background-color: #ffffff;
            outline: none;
        }
        QLineEdit::placeholder {
            color: #94a3b8;
            font-style: normal;
        }
        QComboBox {
            padding-right: 20px;
            min-width: 250px; /* Increased width for combo boxes */
        }
        QComboBox::drop-down {
            border: none;
            width: 20px;
        }
        QComboBox::down-arrow {
            image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIGZpbGw9Im5vbmUiIHZpZXdCb3g9IjAgMCAyNCAyNCIgc3Ryb2tlPSIjOTRhM2I4IiBzdHJva2Utd2lkdGg9IjEuNSI+CiAgPHBhdGggc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIiBkPSJNNiA5bDYgNiA2LTYiIC8+Cjwvc3ZnPg==);
            width: 10px;
            height: 10px;
        }
        QComboBox:hover {
            background-color: #f1f5f9;
        }

        /* Buttons */
        QPushButton {
            padding: 8px 16px; /* Reduced padding for smaller buttons */
            border-radius: 6px;
            background-color: #258f98; /* Changed default button color */
            color: #ffffff;
            font-weight: 500;
            border: none;
            font-size: 13px;
            min-height: 36px; /* Reduced button height */
            min-width: 100px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        QPushButton:hover {
            background-color: #3aa5ad; /* Lighter hover color for new default */
        }
        QPushButton:pressed {
            background-color: #1d6f78; /* Darker pressed color for new default */
        }
        QPushButton#start_analyze {
            font-weight: 600;
            background-color: #82e600; /* Keep Start Analysis color unchanged */
            padding: 10px 20px;
            min-width: 120px;
        }
        QPushButton#start_analyze:hover {
            background-color: #34d399;
        }
        QPushButton[text="Cancel"] {
            background-color: #ef4444; /* Keep Cancel color unchanged */
            min-width: 80px;
        }
        QPushButton[text="Cancel"]:hover {
            background-color: #f87171;
        }
        QPushButton:disabled {
            background-color: #d1d5db;
            color: #9ca3af;
        }

        /* GroupBox */
        QGroupBox {
            border: none;
            border-radius: 5px;
            background-color: #f8fafc;
            padding: 10px;
            margin-top: 12px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 6px 10px;
            color: #1f2a44;
            font-weight: 600;
            font-size: 15px;
        }

        /* Tabs */
        QTabWidget::pane {
            border: none;
            border-radius: 5px;
            background-color: #ffffff;
            padding-top: 8px;
        }
        QTabBar::tab {
            padding: 10px 20px;
            margin: 0 2px;
            border-radius: 6px 6px 0 0;
            background-color: #f1f5f9;
            color: #1f2a44;
            font-size: 13px;
            min-width: 100px;
        }
        QTabBar::tab:selected {
            background-color: #258f98;
            color: #ffffff;
        }
        QTabBar::tab:hover {
            background-color: #e0e7ff;
        }

        /* Tables */
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
        QHeaderView {
            min-width: 0px;
        }

        /* TextEdit */
        QTextEdit {
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 5px;
            color: #1f2a44;
            font-size: 12px;
            padding: 6px;
        }

        /* ScrollArea */
        QScrollArea {
            background-color: #ffffff;
            border: none;
            border-radius: 5px;
        }

        /* ListWidget */
        QListWidget {
            background-color: #f8fafc;
            border: 1px solid #000000;
            border-radius: 5px;
            color: #1f2a44;
            font-size: 12px;
            padding: 4px;
        }
        QListWidget::item {
            padding: 6px;
        }
        QListWidget::item:selected {
            background-color: #e0e7ff;
            color: #1f2a44;
        }

        /* ProgressDialog */
        QProgressDialog {
            background-color: #ffffff;
            border: none;
            border-radius: 5px;
            color: #1f2a44;
            font-size: 13px;
        }

        /* MessageBox */
        QMessageBox {
            background-color: #ffffff;
            color: #1f2a44;
            border: none;
            border-radius: 5px;
        }
        QMessageBox QPushButton {
            background-color: #258f98; /* Apply new default color to message box buttons */
            color: #ffffff;
            padding: 8px 14px;
            border-radius: 5px;
            font-size: 13px;
            min-height: 36px;
            min-width: 90px;
        }
        QMessageBox QPushButton:hover {
            background-color: #3aa5ad; /* Hover for message box buttons */
        }
        """
        QApplication.instance().setStyleSheet(style)

    def build_analyze_tab(self):
        outer = QVBoxLayout(self.analyze_tab)
        outer.setSpacing(10)
        outer.setContentsMargins(12, 12, 12, 12)
        ctrl_group = QGroupBox("Analysis Controls")
        ctrl_grid = QGridLayout(ctrl_group)
        ctrl_grid.setSpacing(10)
        ctrl_grid.setContentsMargins(12, 12, 12, 12)

        self.data_info_label = QTextEdit()
        self.data_info_label.setReadOnly(True)
        self.data_info_label.setToolTip('Summary of retrieved data')
        self.data_info_label.setMinimumHeight(100)
        ctrl_grid.addWidget(QLabel("Data Summary"), 0, 0)
        ctrl_grid.addWidget(self.data_info_label, 0, 1, 1, 2)

        self.tables_table = QTableWidget()
        self.tables_table.setColumnCount(3)
        self.tables_table.setHorizontalHeaderLabels(["Select", "Station", "Model"])
        self.tables_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.tables_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tables_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tables_table.setColumnWidth(0, 50)
        self.tables_table.setToolTip('Select stations and models for analysis')
        self.tables_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tables_table.setMinimumHeight(200)
        ctrl_grid.addWidget(self.tables_table, 1, 0, 1, 3)

        self.start_analyze_btn = QPushButton("Start Analysis")
        self.start_analyze_btn.setObjectName("start_analyze")
        self.start_analyze_btn.setMinimumHeight(40)
        self.start_analyze_btn.clicked.connect(self.run_analysis)
        ctrl_grid.addWidget(self.start_analyze_btn, 2, 0, 1, 3)

        self.auto_save_chk = QCheckBox("Auto-save HTML report")
        self.auto_save_chk.setChecked(True)
        ctrl_grid.addWidget(self.auto_save_chk, 3, 0)

        self.auto_save_path = QLineEdit()
        self.auto_save_path.setPlaceholderText("Select folder for auto-save...")
        ctrl_grid.addWidget(self.auto_save_path, 3, 1)

        browse_btn = QPushButton("Browse")
        browse_btn.setMinimumHeight(40)
        browse_btn.clicked.connect(lambda: self.auto_save_path.setText(QFileDialog.getExistingDirectory(self, "Select Folder")))
        ctrl_grid.addWidget(browse_btn, 3, 2)

        self.save_report_btn = QPushButton("Save HTML Report")
        self.save_report_btn.setMinimumHeight(40)
        self.save_report_btn.clicked.connect(self.save_html_report)
        ctrl_grid.addWidget(self.save_report_btn, 4, 0, 1, 3)

        ctrl_grid.setColumnStretch(1, 1)
        outer.addWidget(ctrl_group)
        outer.addStretch(1)

    def _plot_ok_ng_combined(self, ax, start_str_no_hour, end_str_no_hour):
        stations = AppState.selected_tables
        ok_counts = []
        ng_counts = []
        labels = []
        overall_start = pd.Timestamp.max
        overall_end = pd.Timestamp.min
        for station in stations:
            df = AppState.retrieved_dfs.get(station)
            if df is None:
                continue
            counts = df.get("Result", pd.Series()).astype(str).str.upper().value_counts()
            ok_counts.append(counts.get('OK', 0))
            ng_counts.append(counts.get('NG', 0))
            labels.append(station)
            if 'Date_Time' in df:
                dt = safe_to_datetime(df['Date_Time']).dropna()
                if not dt.empty:
                    overall_start = min(overall_start, dt.min())
                    overall_end = max(overall_end, dt.max())
        
        bar_width = 0.35
        x = np.arange(len(labels))
        ax.bar(x - bar_width/2, ok_counts, bar_width, color='#6366f1', label='OK')
        ax.bar(x + bar_width/2, ng_counts, bar_width, color='#ef4444', label='NG')
        
        max_height = max(np.array(ok_counts) + np.array(ng_counts))
        for i, count in enumerate(ok_counts):
            if count > 0:
                ax.text(i - bar_width/2, count + max_height * 0.02, str(count), ha='center', va='bottom', color='#1f2a44', fontweight='medium', fontsize=8)
        for i, count in enumerate(ng_counts):
            if count > 0:
                ax.text(i + bar_width/2, count + max_height * 0.02, str(count), ha='center', va='bottom', color='#1f2a44', fontweight='medium', fontsize=8)
        
        ax.set_ylim(0, max_height * 1.1)
        ax.set_title(f"OK vs NG by Stations", fontsize=10, fontweight='medium')
        ax.set_xlabel("Stations", fontsize=8)
        ax.set_ylabel("Count", fontsize=8)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=6)
        ax.legend(loc='upper right', bbox_to_anchor=(1.15, 1.0), fontsize=8)
        ax.grid(True, axis='y', linestyle='--', alpha=0.7, color='#e2e8f0')
        ax.tick_params(axis='both', which='major', labelsize=9)

    def _plot_ng_percentage(self, ax, start_str_no_hour, end_str_no_hour):
        stations = AppState.selected_tables
        percentages = []
        labels = []
        for station in stations:
            df = AppState.retrieved_dfs.get(station)
            if df is None:
                continue
            counts = df.get("Result", pd.Series()).astype(str).str.upper().value_counts()
            ok = counts.get('OK', 0)
            ng = counts.get('NG', 0)
            total = ok + ng
            perc = (ng / total * 100) if total > 0 else 0
            percentages.append(perc)
            labels.append(station)
        if not labels:
            ax.text(0.5, 0.5, "No data available", ha='center', va='center', fontsize=10)
            ax.set_title(f"NG Percentage by Station", fontsize=10, fontweight='medium')
            return
        bars = ax.bar(np.arange(len(labels)), percentages, color='#ef4444')
        ax.set_title(f"NG Percentage by Station", fontsize=10, fontweight='medium')
        ax.set_xlabel("Stations", fontsize=8)
        ax.set_ylabel("NG %", fontsize=8)
        max_height = max(percentages, default=0) + 5
        ax.set_ylim(0, max_height)
        ax.set_xticks(np.arange(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=6)
        ax.grid(True, axis='y', linestyle='--', alpha=0.7, color='#e2e8f0')
        ax.tick_params(axis='both', which='major', labelsize=9)
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2, height + max_height * 0.02, f"{height:.1f}%", ha='center', va='bottom', color='#1f2a44', fontweight='medium', fontsize=8)

    def _plot_ok_ng_pie(self, ax, start_str_no_hour, end_str_no_hour):
        stations = AppState.selected_tables
        max_ng = -1
        max_ng_station = None
        total_ok = 0
        total_ng = 0

        # Find the station with the most NG because the Units Under Testing go from one table to another in my case.
        for station in stations:
            df = AppState.retrieved_dfs.get(station)
            if df is None:
                continue
            counts = df.get("Result", pd.Series()).astype(str).str.upper().value_counts()
            ng_count = counts.get('NG', 0)
            if ng_count > max_ng:
                max_ng = ng_count
                max_ng_station = station
                total_ok = counts.get('OK', 0)
                total_ng = ng_count

        if max_ng_station is None:
            ax.text(0.5, 0.5, "No data available", ha='center', va='center', fontsize=10)
            ax.set_title(f"Total OK vs NG", fontsize=10, fontweight='medium')
            ax.set_facecolor('#f8fafc')
            return

        labels = ['OK', 'NG']
        sizes = [total_ok, total_ng]
        colors = ['#6366f1', '#ef4444']
        explode = (0.1, 0)
        total = total_ok + total_ng
        if total > 0:
            wedges, texts, autotexts = ax.pie(sizes, explode=explode, labels=labels, colors=colors, autopct=lambda p: f'{p:.1f}%', shadow=False, startangle=90, textprops={'fontsize': 8})
            ax.axis('equal')
            ax.set_title(f"Total OK vs NG ", fontsize=10, fontweight='medium')
            ax.set_facecolor('#f8fafc')
        else:
            ax.text(0.5, 0.5, "No data available", ha='center', va='center', fontsize=10)
            ax.set_title(f"Total OK vs NG ", fontsize=10, fontweight='medium')
            ax.set_facecolor('#f8fafc')

    def _plot_ng_rate_by_time(self, ax, start_str_no_hour, end_str_no_hour):
        # Find the station with the most NG because the Units Under Testing go from one table to another in my case.
        stations = AppState.selected_tables
        max_ng = -1
        max_ng_station = None
        for station in stations:
            df = AppState.retrieved_dfs.get(station)
            if df is None:
                continue
            counts = df.get("Result", pd.Series()).astype(str).str.upper().value_counts()
            ng_count = counts.get('NG', 0)
            if ng_count > max_ng:
                max_ng = ng_count
                max_ng_station = station

        if max_ng_station is None or max_ng == 0:
            ax.text(0.5, 0.5, "No NG data available", ha='center', va='center', fontsize=10)
            ax.set_title("NG Rate by Time", fontsize=10, fontweight='medium')
            ax.set_facecolor('#f8fafc')
            return

        # Use data from the station with the highest NG count
        df = AppState.retrieved_dfs.get(max_ng_station)
        if df is None or 'Date_Time' not in df or df.empty:
            ax.text(0.5, 0.5, "No data available", ha='center', va='center', fontsize=10)
            ax.set_title("NG Rate by Time", fontsize=10, fontweight='medium')
            ax.set_facecolor('#f8fafc')
            return

        df = df.copy()
        df['Date_Time'] = safe_to_datetime(df['Date_Time'])
        df = df.dropna(subset=['Date_Time'])
        df['Result'] = df.get('Result', pd.Series()).astype(str).str.upper()

        # Calculate time span
        time_span = pd.Timestamp(end_str_no_hour) - pd.Timestamp(start_str_no_hour)
        days = time_span.days

        # Determine time interval based on time frame
        if days <= 1:
            freq = '4H'
            time_format = '%Y-%m-%d %H:%M'
            rotation = 45
        elif days <= 10:
            freq = 'D'
            time_format = '%Y-%m-%d'
            rotation = 45
        elif days <= 30:
            freq = 'W'
            time_format = '%Y-%m-%d'
            rotation = 45
        else:
            freq = 'M'
            time_format = '%Y-%m'
            rotation = 45

        # Resample by time
        df.set_index('Date_Time', inplace=True)
        total_counts = df.resample(freq).size()
        ng_counts = df[df['Result'] == 'NG'].resample(freq).size()
        ng_rate = (ng_counts / total_counts * 100).fillna(0)

        if ng_rate.empty:
            ax.text(0.5, 0.5, "No NG data available", ha='center', va='center', fontsize=10)
            ax.set_title("NG Rate by Time", fontsize=10, fontweight='medium')
            ax.set_facecolor('#f8fafc')
            return

        #Plot
        ax.plot(ng_rate.index, ng_rate.values, color='#ef4444', linewidth=2)
        ax.set_title(f"NG Rate by Time ({max_ng_station})", fontsize=10, fontweight='medium')
        ax.set_xlabel("Time", fontsize=8)
        ax.set_ylabel("NG Rate (%)", fontsize=8)
        ax.grid(True, linestyle='--', alpha=0.7, color='#e2e8f0')
        max_rate = max(ng_rate.max() * 1.1, 5)
        ax.set_ylim(0, max_rate)
        ax.set_xticks(ng_rate.index)
        ax.set_xticklabels(ng_rate.index.strftime(time_format), rotation=rotation, ha='right', fontsize=6)
        ax.set_facecolor('#f8fafc')
        ax.tick_params(axis='both', which='major', labelsize=9)

        # Add NG count labels for NG rate by Time as I want to show clearly
        for i, (idx, rate) in enumerate(zip(ng_rate.index, ng_rate.values)):
            count = ng_counts.get(idx, 0)
            if count > 0:  # Only show labels for non-zero counts
                ax.text(idx, rate + max_rate * 0.02, str(int(count)), 
                        ha='center', va='bottom', color='#1f2a44', 
                        fontweight='medium', fontsize=6)

    def _plot_root_cause_for_station(self, ax, station):
        df = AppState.analyzed_dfs.get(station)
        if df is None or df.empty:
            ax.text(0.5, 0.5, f"No data for {station}", ha='center', va='center', fontsize=8)
            ax.set_title(f"Top 5 Root Causes for {station}", fontsize=8, fontweight='medium')
            ax.set_facecolor('#f8fafc')
            return
        ng = df[df["Prediction"].str.upper() == "NG"]
        if ng.empty:
            ax.text(0.5, 0.5, f"No NG data for {station}", ha='center', va='center', fontsize=8)
            ax.set_title(f"Top 5 Root Causes for {station}", fontsize=8, fontweight='medium')
            ax.set_facecolor('#f8fafc')
            return
        counts = ng["Root_Cause"].value_counts()
        if counts.empty:
            ax.text(0.5, 0.5, "No root causes", ha='center', va='center', fontsize=8)
            ax.set_title(f"Top 5 Root Causes for {station}", fontsize=8, fontweight='medium')
            ax.set_facecolor('#f8fafc')
            return
        counts = counts.sort_values(ascending=False).head(5)
        bars = ax.bar(np.arange(len(counts)), counts.values, color='#ef4444')
        ax.set_title(f"Top 5 Root Causes for {station}", fontsize=8, fontweight='medium')
        ax.set_xlabel("Root Cause", fontsize=6)
        ax.set_ylabel("Count", fontsize=6)
        ax.set_xticks(np.arange(len(counts)))
        ax.set_xticklabels(counts.index, rotation=45, ha='right', fontsize=5)
        ax.grid(True, axis='y', linestyle='--', alpha=0.7, color='#e2e8f0')
        ax.tick_params(axis='both', which='major', labelsize=8)
        ax.set_facecolor('#f8fafc')
        max_height = counts.max()
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width()/2, height + max_height * 0.02, str(int(height)), 
                        ha='center', va='bottom', color='#1f2a44', fontweight='medium', fontsize=6)
        ax.set_ylim(0, max_height * 1.1)

    def update_for_new_data(self):
        stations = AppState.selected_tables  
        self.tables_table.setRowCount(len(stations))
        for row, station in enumerate(stations):
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk_item.setCheckState(Qt.Checked)
            self.tables_table.setItem(row, 0, chk_item)
            self.tables_table.setItem(row, 1, QTableWidgetItem(station))
            model_combo = QComboBox()
            if station in AppState.rules:
                models = list(AppState.rules[station].get("models", {}).keys())
                model_combo.addItems(models)
            self.tables_table.setCellWidget(row, 2, model_combo)
        summary = []
        for station, df in AppState.retrieved_dfs.items():
            summary.append(f"{station}: {len(df)} rows")
        self.data_info_label.setPlainText("\n".join(summary) if summary else "No data loaded")

    def view_full_data(self):
        if not AppState.retrieved_dfs:
            QMessageBox.information(self, "Info", "No data retrieved.")
            return
        dlg = PreviewDialog(self)
        dlg.set_data(AppState.retrieved_dfs)
        dlg.exec_()

    def _get_embedded_logo(self):
        """Load local logo as base64; fallback to URL if missing."""
        logo_path = os.path.join(os.getcwd(), 'src', 'Valeo_Logo.svg.png')
        if os.path.exists(logo_path):
            try:
                with open(logo_path, 'rb') as f:
                    logo_data = base64.b64encode(f.read()).decode('utf-8')
                return f'data:image/png;base64,{logo_data}'
            except Exception as e:
                log(f"Failed to encode local logo: {e}", "WARN")
        
        return 'https://upload.wikimedia.org/wikipedia/commons/thumb/2/2b/Valeo_Logo.svg/2560px-Valeo_Logo.svg.png'

    def auto_open_html_report(self):
        overall_start = pd.Timestamp.max
        overall_end = pd.Timestamp.min
        for df in AppState.retrieved_dfs.values():
            if 'Date_Time' in df:
                dt = safe_to_datetime(df['Date_Time']).dropna()
                if not dt.empty:
                    overall_start = min(overall_start, dt.min())
                    overall_end = max(overall_end, dt.max())
        start_str_with_hour = overall_start.strftime('%Y-%m-%d %H:%M:%S') if overall_start != pd.Timestamp.max else 'N/A'
        end_str_with_hour = overall_end.strftime('%Y-%m-%d %H:%M:%S') if overall_end != pd.Timestamp.min else 'N/A'
        start_str_no_hour = overall_start.strftime('%Y-%m-%d') if overall_start != pd.Timestamp.max else 'N/A'
        end_str_no_hour = overall_end.strftime('%Y-%m-%d') if overall_end != pd.Timestamp.min else 'N/A'
        end_date = overall_end.date() if overall_end != pd.Timestamp.min else datetime.now().date()
        start_date = overall_start.date() if overall_start != pd.Timestamp.max else datetime.now().date()
        
        week_no = start_date.isocalendar()[1]
        include_week = self.app_config_tab.include_week_chk.isChecked()
        
        custom_filename = self.app_config_tab.html_filename.text().strip()
        custom_title = self.app_config_tab.html_title.text().strip()
        
        if custom_filename:
            if include_week:
                default_filename = f"{custom_filename}_Week_{week_no}.html"
            else:
                default_filename = f"{custom_filename}.html"
        else:
            if include_week:
                default_filename = f"Report_Week_{week_no}.html"
            else:
                default_filename = f"Report.html"
            
        if not custom_title:
            custom_title = "Report Title"
        if include_week:
            custom_title += f" - Week {week_no}"
        
        auto_save_path = self.app_config_tab.auto_save_path.text().strip()
        if auto_save_path:
            path = os.path.join(auto_save_path, default_filename)
        else:
            path = default_filename
        try:
            self.setCursor(Qt.WaitCursor)
            log(f"Generating HTML report: {path}")

            # Embed logo for offline-capable
            logo_src = self._get_embedded_logo()

            # Find station with max NG for KPIs as the Units Under Testing go from one table to another in my case.
            max_ng = -1
            max_ng_station = None
            total_ok = 0
            total_ng = 0
            total_units = 0
            ng_perc = 0.0
            for station in AppState.selected_tables:
                df = AppState.retrieved_dfs.get(station)
                if df is None:
                    continue
                counts = df.get("Result", pd.Series()).astype(str).str.upper().value_counts()
                ng_count = counts.get('NG', 0)
                if ng_count > max_ng:
                    max_ng = ng_count
                    max_ng_station = station
                    total_ok = counts.get('OK', 0)
                    total_ng = ng_count
                    total_units = len(df)
                    ng_perc = (total_ng / total_units * 100) if total_units > 0 else 0.0

            html_content = [
            '<html>',
            '<head>',
            '<style>',
            'body { font-family: Helvetica, sans-serif; margin: 0; background-color: #f3f4f6; color: #111827; zoom: 75%; }',
            '.header { background-color: #82e600; color: #414141; padding: 19px; text-align: center; }',
            'h1 { margin: 0; font-size: 24px; font-weight: bold; }',
            '.logo { float: right; width: 113px; height: 113px; object-fit: contain; margin: 8px; }',
            'h2 { color: #111827; font-size: 18px; font-weight: 600; margin: 23px 0 11px; }',
            'p { font-size: 12px; line-height: 1.7; margin: 9px 0; }',
            '.container { max-width: 1050px; margin: 23px auto; padding: 23px; background-color: #ffffff; border-radius: 9px; box-shadow: 0 5px 12px rgba(0,0,0,0.1); overflow: hidden; }',
            '.troubleshooting { width: 100%; font-size: 12px; border-collapse: collapse; text-align: center; margin: 19px 0; }',
            '.troubleshooting th, .troubleshooting td { padding: 11px; border: 1px solid #d1d5db; vertical-align: top; }',
            '.troubleshooting th { background-color: #e5e7eb; color: #111827; font-weight: bold; font-size: 12px; }',
            '.troubleshooting td { font-size: 11px; }',
            '.troubleshooting td:nth-child(3), .troubleshooting td:nth-child(4) { text-align: left; padding-left: 15px; }',
            '.troubleshooting tr:nth-child(even) { background-color: #e6f3ff; }',
            '.troubleshooting tr:nth-child(odd) { background-color: #ffffff; }',
            '.troubleshooting tr:hover { background-color: #f9fafb; }',
            '.troubleshooting ul { margin: 4px 0; padding-left: 15px; list-style-type: disc; }',
            '.troubleshooting li { font-size: 11px; margin-bottom: 4px; color: #374151; line-height: 1.4; }',
            '.image-container { text-align: center; margin: 23px 0; }',
            '.grid-container { display: grid; grid-template-columns: repeat(3, 1fr); gap: 38px; margin: 45px 0; align-items: end; }',
            '.summary-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 19px; margin: 45px 0; align-items: end; }',
            '.grid-item { text-align: center; display: flex; flex-direction: column; justify-content: flex-end; position: relative; }',
            '.grid-item::before { content: ""; position: absolute; top: 0; left: 0; right: 0; bottom: 0; border: 0px solid #e2e8f0; border-radius: 6px; z-index: 0; }',
            'img { max-width: 100%; height: auto; border: 2px solid #d1d5db; border-radius: 8px; box-shadow: 0 3px 6px rgba(0,0,0,0.1); position: relative; z-index: 1; }',
            '.caption { font-size: 15px; color: #4b5563; font-style: italic; margin-top: 5px; font-weight: 500; position: relative; z-index: 1; }',
            '.info-list { display: grid; grid-template-columns: auto 1fr; gap: 8px 15px; max-width: 450px; margin: 15px 0; font-size: 12px; border: 1px solid #d1d5db; padding: 11px; border-radius: 6px; background-color: #f8fafc; }',
            '.info-list dt { font-weight: bold; text-align: right; color: #4b5563; }',
            '.info-list dd { margin: 0; color: #111827; }',
            '.kpi-container { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 23px 0; }',
            '.kpi-card { background-color: #f8fafc; padding: 15px; border-radius: 6px; text-align: center; box-shadow: 0 2px 3px rgba(0,0,0,0.1); }',
            '.kpi-card h3 { font-size: 14px; margin-bottom: 8px; color: #4b5563; }',
            '.kpi-card p { font-size: 18px; font-weight: bold; margin: 0; }',
            '.blue { background-color: #6366f1; color: #f8fafc; }',
            '.red { background-color: #ef4444; color: #f8fafc; }',
            '.green { background-color: #82e600; color: #f8fafc; }',
            '</style>',
            '</head>',
            '<body>',
            '<div class="header">',
            f'<h1>{custom_title}</h1>',
            '</div>',
            '<div class="container">',
            f'<img src="{logo_src}" class="logo" alt="Valeo Logo">',
            '<dl class="info-list">',
            f'<dt>Generated:</dt><dd>{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</dd>',
            f'<dt>Stations:</dt><dd>{", ".join(AppState.selected_tables)}</dd>',
            f'<dt>Analyzed Stations:</dt><dd>{", ".join(AppState.analyzed_dfs.keys())}</dd>',
            f'<dt>State:</dt><dd>{AppState.state}</dd>',
            f'<dt>From:</dt><dd>{start_str_with_hour}</dd>',
            f'<dt>To:</dt><dd>{end_str_with_hour}</dd>',
            '</dl>',
        ]

            # KPI cards
            html_content.append('<div class="kpi-container">')
            html_content.append('<div class="kpi-card">')
            html_content.append('<h3>Total Units</h3>')
            html_content.append(f'<p class="green">{total_units}</p>')
            html_content.append('</div>')
            html_content.append('<div class="kpi-card">')
            html_content.append('<h3>Total OK</h3>')
            html_content.append(f'<p class="blue">{total_ok}</p>')
            html_content.append('</div>')
            html_content.append('<div class="kpi-card">')
            html_content.append('<h3>Total NG</h3>')
            html_content.append(f'<p class="red">{total_ng}</p>')
            html_content.append('</div>')
            html_content.append('<div class="kpi-card">')
            html_content.append('<h3>NG Percentage</h3>')
            html_content.append(f'<p class="red">{ng_perc:.1f}%</p>')
            html_content.append('</div>')
            html_content.append('</div>')

            # Summary visuals in grid
            html_content.append('<div class="summary-grid">')

            # OK vs NG Bar Chart
            fig = Figure(figsize=(5, 3))
            ax = fig.add_subplot(111)
            self._plot_ok_ng_combined(ax, start_str_no_hour, end_str_no_hour)
            buf = BytesIO()
            fig.savefig(buf, format='png', bbox_inches='tight', dpi=100)
            buf.seek(0)
            img_data = base64.b64encode(buf.read()).decode('utf-8')
            html_content.append('<div class="grid-item">')
            html_content.append(f'<img src="data:image/png;base64,{img_data}" alt="OK vs NG">')
            html_content.append(f'<div class="caption">OK vs NG Results by All Stations</div>')
            html_content.append('</div>')
            plt.close(fig)

            # NG Percentage Bar Chart
            fig = Figure(figsize=(5, 3))
            ax = fig.add_subplot(111)
            self._plot_ng_percentage(ax, start_str_no_hour, end_str_no_hour)
            buf = BytesIO()
            fig.savefig(buf, format='png', bbox_inches='tight', dpi=100)
            buf.seek(0)
            img_data = base64.b64encode(buf.read()).decode('utf-8')
            html_content.append('<div class="grid-item">')
            html_content.append(f'<img src="data:image/png;base64,{img_data}" alt="NG Percentage">')
            html_content.append(f'<div class="caption">NG Percentage by Station</div>')
            html_content.append('</div>')
            plt.close(fig)

            # Overall OK vs NG Pie Chart
            fig = Figure(figsize=(5, 3))
            ax = fig.add_subplot(111)
            self._plot_ok_ng_pie(ax, start_str_no_hour, end_str_no_hour)
            buf = BytesIO()
            fig.savefig(buf, format='png', bbox_inches='tight', dpi=100)
            buf.seek(0)
            img_data = base64.b64encode(buf.read()).decode('utf-8')
            html_content.append('<div class="grid-item">')
            html_content.append(f'<img src="data:image/png;base64,{img_data}" alt="Overall OK vs NG Pie">')
            html_content.append(f'<div class="caption">Overall OK vs NG Distribution</div>')
            html_content.append('</div>')
            plt.close(fig)

            # NG Rate by Time Plot
            fig = Figure(figsize=(5, 3))
            ax = fig.add_subplot(111)
            self._plot_ng_rate_by_time(ax, start_str_no_hour, end_str_no_hour)
            buf = BytesIO()
            fig.savefig(buf, format='png', bbox_inches='tight', dpi=100)
            buf.seek(0)
            img_data = base64.b64encode(buf.read()).decode('utf-8')
            html_content.append('<div class="grid-item">')
            html_content.append(f'<img src="data:image/png;base64,{img_data}" alt="NG Rate by Time">')
            html_content.append(f'<div class="caption">NG Rate by Time</div>')
            html_content.append('</div>')
            plt.close(fig)

            html_content.append('</div>')

            # Root cause images in grid
            html_content.append('<div class="grid-container">')
            for station in AppState.analyzed_dfs:
                fig = Figure(figsize=(3.5, 2.2))
                ax = fig.add_subplot(111)
                self._plot_root_cause_for_station(ax, station)
                buf = BytesIO()
                fig.savefig(buf, format='png', bbox_inches='tight', dpi=100)
                buf.seek(0)
                img_data = base64.b64encode(buf.read()).decode('utf-8')
                html_content.append('<div class="grid-item">')
                html_content.append(f'<img src="data:image/png;base64,{img_data}" alt="Top 5 Root Causes for {station}">')
                html_content.append(f'<div class="caption">Top 5 Root Causes for NG in {station}</div>')
                html_content.append('</div>')
                plt.close(fig)
            html_content.append('</div>')

            # Troubleshooting table with split columns
            html_content.append('<h2>Troubleshooting Methods</h2>')
            data = []
            # Use the total_ng from KPI card
            for station, df in AppState.analyzed_dfs.items():
                ng = df[df["Prediction"].str.upper() == "NG"]
                if ng.empty:
                    continue
                cause_counts = ng["Root_Cause"].value_counts()
                for cause, count in cause_counts.items():
                    methods_list = AppState.troubleshooting.get(station, {}).get(str(cause), [])
                    percentage = (count / total_ng * 100) if total_ng > 0 else 0
                    data.append([station, cause, methods_list, count, percentage])

            # Sort by count (descending) and limit to top 10
            data = sorted(data, key=lambda x: x[3], reverse=True)[:10]

            if data:
                html_content.append('<table class="troubleshooting">')
                html_content.append('<tr><th>Station</th><th>Root Cause</th><th>Possible Problem</th><th>Solution</th><th>Count</th><th>Percentage</th></tr>')
                for row in data:
                    station, cause, methods_list, count, percentage = row
                    html_content.append('<tr>')
                    html_content.append(f'<td>{station}</td>')
                    html_content.append(f'<td>{cause}</td>')
                
                #Possible Problem and Solution
                    if methods_list and len(methods_list) > 0:
                    #ul for problems
                        problems_html = '<ul>'
                        for method in methods_list:
                            if isinstance(method, dict):
                                problem = method.get('Possible Problem', 'N/A')
                                problems_html += f'<li>{problem}</li>'
                            else:
                                problems_html += f'<li>{method}</li>'
                        problems_html += '</ul>'
                        html_content.append(f'<td>{problems_html}</td>')
                    
                    #ul for solutions
                        solutions_html = '<ul>'
                        for method in methods_list:
                            if isinstance(method, dict):
                                solution = method.get('Solution', 'N/A')
                                solutions_html += f'<li>{solution}</li>'
                            else:
                                solutions_html += f'<li>{method}</li>'
                        solutions_html += '</ul>'
                        html_content.append(f'<td>{solutions_html}</td>')
                    else:
                        html_content.append('<td>No methods defined</td>')
                        html_content.append('<td>No methods defined</td>')
                
                    html_content.append(f'<td>{count}</td>')
                    html_content.append(f'<td>{percentage:.1f}%</td>')
                    html_content.append('</tr>')
                html_content.append('</table>')
            else:
                html_content.append("<p>No troubleshooting data available.</p>")

            html_content.append("</div>")
            html_content.append("</body></html>")

            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(html_content))

            try:
                webbrowser.open('file://' + os.path.realpath(path))
            except Exception as e:
                log(f"Failed to open browser: {e}", "WARN")
            log(f"HTML report saved at {path}")
        except Exception as e:
            log(f"Auto-open HTML report error: {e}", "ERROR")
            if not self.auto_running:
                QMessageBox.critical(self, "Error", str(e))
        finally:
            self.unsetCursor()

    def save_html_report(self):
        if not AppState.analyzed_dfs:
            QMessageBox.information(self, "Info", "Run analysis first.")
            return

        #Format dialog
        format_dlg = QDialog(self)
        format_dlg.setWindowTitle("Export Options")
        layout = QVBoxLayout()
        
        include_data_chk = QCheckBox("Include Analyzed Tables")
        include_data_chk.setToolTip('Include analyzed data tables in the export')
        layout.addWidget(include_data_chk)
        
        format_combo = QComboBox()
        format_combo.addItems(["CSV", "XLSX"])
        format_combo.setToolTip('Choose the format for exported tables')
        layout.addWidget(QLabel("Table Export Format:"))
        layout.addWidget(format_combo)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(format_dlg.accept)
        buttons.rejected.connect(format_dlg.reject)
        layout.addWidget(buttons)
        
        format_dlg.setLayout(layout)
        if format_dlg.exec_() != QDialog.Accepted:
            return
        
        include_data = include_data_chk.isChecked()
        export_format = format_combo.currentText().lower()

        overall_start = pd.Timestamp.max
        overall_end = pd.Timestamp.min
        for df in AppState.retrieved_dfs.values():
            if 'Date_Time' in df:
                dt = safe_to_datetime(df['Date_Time']).dropna()
                if not dt.empty:
                    overall_start = min(overall_start, dt.min())
                    overall_end = max(overall_end, dt.max())
        start_str_with_hour = overall_start.strftime('%Y-%m-%d %H:%M:%S') if overall_start != pd.Timestamp.max else 'N/A'
        end_str_with_hour = overall_end.strftime('%Y-%m-%d %H:%M:%S') if overall_end != pd.Timestamp.min else 'N/A'
        start_str_no_hour = overall_start.strftime('%Y-%m-%d') if overall_start != pd.Timestamp.max else 'N/A'
        end_str_no_hour = overall_end.strftime('%Y-%m-%d') if overall_end != pd.Timestamp.min else 'N/A'
        end_date = overall_end.date() if overall_end != pd.Timestamp.min else datetime.now().date()
        start_date = overall_start.date() if overall_start != pd.Timestamp.max else datetime.now().date()
        
        week_no = start_date.isocalendar()[1]
        include_week = self.app_config_tab.include_week_chk.isChecked()
        
        custom_filename = self.app_config_tab.html_filename.text().strip()
        custom_title = self.app_config_tab.html_title.text().strip()
        
        if custom_filename:
            if include_week:
                default_filename = f"{custom_filename}_Week_{week_no}.html"
            else:
                default_filename = f"{custom_filename}.html"
        else:
            if include_week:
                default_filename = f"Report_Week_{week_no}.html"
            else:
                default_filename = f"Report.html"
            
        if not custom_title:
            custom_title = "Report Title"
        if include_week:
            custom_title += f" - Week {week_no}"
            
        path, _ = QFileDialog.getSaveFileName(self, "Save HTML Report", default_filename, "HTML File (*.html)")
        if not path:
            return
        try:
            self.setCursor(Qt.WaitCursor)

            # Embed logo for offline-capable
            logo_src = self._get_embedded_logo()

            # Use station with max NG for KPIs
            max_ng = -1
            max_ng_station = None
            total_ok = 0
            total_ng = 0
            total_units = 0
            ng_perc = 0.0
            for station in AppState.selected_tables:
                df = AppState.retrieved_dfs.get(station)
                if df is None:
                    continue
                counts = df.get("Result", pd.Series()).astype(str).str.upper().value_counts()
                ng_count = counts.get('NG', 0)
                if ng_count > max_ng:
                    max_ng = ng_count
                    max_ng_station = station
                    total_ok = counts.get('OK', 0)
                    total_ng = ng_count
                    total_units = len(df)
                    ng_perc = (total_ng / total_units * 100) if total_units > 0 else 0.0

            html_content = [
                '<html>',
                '<head>',
                '<style>',
                'body { font-family: Helvetica, sans-serif; margin: 0; background-color: #f3f4f6; color: #111827; zoom: 75%; }',
                '.header { background-color: #82e600; color: #414141; padding: 19px; text-align: center; }',
                'h1 { margin: 0; font-size: 24px; font-weight: bold; }',
                '.logo { float: right; width: 113px; height: 113px; object-fit: contain; margin: 8px; }',
                'h2 { color: #111827; font-size: 18px; font-weight: 600; margin: 23px 0 11px; }',
                'p { font-size: 12px; line-height: 1.7; margin: 9px 0; }',
                '.container { max-width: 1050px; margin: 23px auto; padding: 23px; background-color: #ffffff; border-radius: 9px; box-shadow: 0 5px 12px rgba(0,0,0,0.1); overflow: hidden; }',
                '.troubleshooting { width: 100%; font-size: 12px; border-collapse: collapse; text-align: center; margin: 19px 0; }',
                '.troubleshooting th, .troubleshooting td { padding: 11px; border: 1px solid #d1d5db; vertical-align: top; }',
                '.troubleshooting th { background-color: #e5e7eb; color: #111827; font-weight: bold; font-size: 12px; }',
                '.troubleshooting td { font-size: 11px; }',
                '.troubleshooting td:nth-child(3), .troubleshooting td:nth-child(4) { text-align: left; padding-left: 15px; }',
                '.troubleshooting tr:nth-child(even) { background-color: #e6f3ff; }',
                '.troubleshooting tr:nth-child(odd) { background-color: #ffffff; }',
                '.troubleshooting tr:hover { background-color: #f9fafb; }',
                '.troubleshooting ul { margin: 4px 0; padding-left: 15px; list-style-type: disc; }',
                '.troubleshooting li { font-size: 11px; margin-bottom: 4px; color: #374151; line-height: 1.4; }',
                '.image-container { text-align: center; margin: 23px 0; }',
                '.grid-container { display: grid; grid-template-columns: repeat(3, 1fr); gap: 38px; margin: 45px 0; align-items: end; }',
                '.summary-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 19px; margin: 45px 0; align-items: end; }',
                '.grid-item { text-align: center; display: flex; flex-direction: column; justify-content: flex-end; position: relative; }',
                '.grid-item::before { content: ""; position: absolute; top: 0; left: 0; right: 0; bottom: 0; border: 0px solid #e2e8f0; border-radius: 6px; z-index: 0; }',
                'img { max-width: 100%; height: auto; border: 2px solid #d1d5db; border-radius: 8px; box-shadow: 0 3px 6px rgba(0,0,0,0.1); position: relative; z-index: 1; }',
                '.caption { font-size: 15px; color: #4b5563; font-style: italic; margin-top: 5px; font-weight: 500; position: relative; z-index: 1; }',
                '.info-list { display: grid; grid-template-columns: auto 1fr; gap: 8px 15px; max-width: 450px; margin: 15px 0; font-size: 12px; border: 1px solid #d1d5db; padding: 11px; border-radius: 6px; background-color: #f8fafc; }',
                '.info-list dt { font-weight: bold; text-align: right; color: #4b5563; }',
                '.info-list dd { margin: 0; color: #111827; }',
                '.kpi-container { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 23px 0; }',
                '.kpi-card { background-color: #f8fafc; padding: 15px; border-radius: 6px; text-align: center; box-shadow: 0 2px 3px rgba(0,0,0,0.1); }',
                '.kpi-card h3 { font-size: 14px; margin-bottom: 8px; color: #4b5563; }',
                '.kpi-card p { font-size: 18px; font-weight: bold; margin: 0; }',
                '.blue { background-color: #6366f1; color: #f8fafc; }',
                '.red { background-color: #ef4444; color: #f8fafc; }',
                '.green { background-color: #82e600; color: #f8fafc; }',
                '</style>',
                '</head>',
                '<body>',
                '<div class="header">',
                f'<h1>{custom_title}</h1>',
                '</div>',
                '<div class="container">',
                f'<img src="{logo_src}" class="logo" alt="Valeo Logo">',
                '<dl class="info-list">',
                f'<dt>Generated:</dt><dd>{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</dd>',
                f'<dt>Stations:</dt><dd>{", ".join(AppState.selected_tables)}</dd>',
                f'<dt>Analyzed Stations:</dt><dd>{", ".join(AppState.analyzed_dfs.keys())}</dd>',
                f'<dt>State:</dt><dd>{AppState.state}</dd>',
                f'<dt>From:</dt><dd>{start_str_with_hour}</dd>',
                f'<dt>To:</dt><dd>{end_str_with_hour}</dd>',
                '</dl>',
        ]

            # KPI cards
            html_content.append('<div class="kpi-container">')
            html_content.append('<div class="kpi-card">')
            html_content.append('<h3>Total Units</h3>')
            html_content.append(f'<p class="green">{total_units}</p>')
            html_content.append('</div>')
            html_content.append('<div class="kpi-card">')
            html_content.append('<h3>Total OK</h3>')
            html_content.append(f'<p class="blue">{total_ok}</p>')
            html_content.append('</div>')
            html_content.append('<div class="kpi-card">')
            html_content.append('<h3>Total NG</h3>')
            html_content.append(f'<p class="red">{total_ng}</p>')
            html_content.append('</div>')
            html_content.append('<div class="kpi-card">')
            html_content.append('<h3>NG Percentage</h3>')
            html_content.append(f'<p class="red">{ng_perc:.1f}%</p>')
            html_content.append('</div>')
            html_content.append('</div>')

            # Summary visuals in grid
            html_content.append('<div class="summary-grid">')

            # OK vs NG Bar Chart
            fig = Figure(figsize=(5, 3))
            ax = fig.add_subplot(111)
            self._plot_ok_ng_combined(ax, start_str_no_hour, end_str_no_hour)
            buf = BytesIO()
            fig.savefig(buf, format='png', bbox_inches='tight', dpi=100)
            buf.seek(0)
            img_data = base64.b64encode(buf.read()).decode('utf-8')
            html_content.append('<div class="grid-item">')
            html_content.append(f'<img src="data:image/png;base64,{img_data}" alt="OK vs NG">')
            html_content.append(f'<div class="caption">OK vs NG Results by All Stations</div>')
            html_content.append('</div>')
            plt.close(fig)

            # NG Percentage Bar Chart
            fig = Figure(figsize=(5, 3))
            ax = fig.add_subplot(111)
            self._plot_ng_percentage(ax, start_str_no_hour, end_str_no_hour)
            buf = BytesIO()
            fig.savefig(buf, format='png', bbox_inches='tight', dpi=100)
            buf.seek(0)
            img_data = base64.b64encode(buf.read()).decode('utf-8')
            html_content.append('<div class="grid-item">')
            html_content.append(f'<img src="data:image/png;base64,{img_data}" alt="NG Percentage">')
            html_content.append(f'<div class="caption">NG Percentage by Station</div>')
            html_content.append('</div>')
            plt.close(fig)

            # Overall OK vs NG Pie Chart
            fig = Figure(figsize=(5, 3))
            ax = fig.add_subplot(111)
            self._plot_ok_ng_pie(ax, start_str_no_hour, end_str_no_hour)
            buf = BytesIO()
            fig.savefig(buf, format='png', bbox_inches='tight', dpi=100)
            buf.seek(0)
            img_data = base64.b64encode(buf.read()).decode('utf-8')
            html_content.append('<div class="grid-item">')
            html_content.append(f'<img src="data:image/png;base64,{img_data}" alt="Overall OK vs NG Pie">')
            html_content.append(f'<div class="caption">Overall OK vs NG Distribution</div>')
            html_content.append('</div>')
            plt.close(fig)

            # NG Rate by Time Plot
            fig = Figure(figsize=(5, 3))
            ax = fig.add_subplot(111)
            self._plot_ng_rate_by_time(ax, start_str_no_hour, end_str_no_hour)
            buf = BytesIO()
            fig.savefig(buf, format='png', bbox_inches='tight', dpi=100)
            buf.seek(0)
            img_data = base64.b64encode(buf.read()).decode('utf-8')
            html_content.append('<div class="grid-item">')
            html_content.append(f'<img src="data:image/png;base64,{img_data}" alt="NG Rate by Time">')
            html_content.append(f'<div class="caption">NG Rate by Time</div>')
            html_content.append('</div>')
            plt.close(fig)

            html_content.append('</div>')

            # Root cause images in grid
            html_content.append('<div class="grid-container">')
            for station in AppState.analyzed_dfs:
                fig = Figure(figsize=(3.5, 2.2))
                ax = fig.add_subplot(111)
                self._plot_root_cause_for_station(ax, station)
                buf = BytesIO()
                fig.savefig(buf, format='png', bbox_inches='tight', dpi=100)
                buf.seek(0)
                img_data = base64.b64encode(buf.read()).decode('utf-8')
                html_content.append('<div class="grid-item">')
                html_content.append(f'<img src="data:image/png;base64,{img_data}" alt="Top 5 Root Causes for {station}">')
                html_content.append(f'<div class="caption">Top 5 Root Causes for NG in {station}</div>')
                html_content.append('</div>')
                plt.close(fig)
            html_content.append('</div>')

            # Troubleshooting table with split columns
            html_content.append('<h2>Troubleshooting Methods</h2>')
            data = []
            # Use the total_ng from KPI card
            for station, df in AppState.analyzed_dfs.items():
                ng = df[df["Prediction"].str.upper() == "NG"]
                if ng.empty:
                    continue
                cause_counts = ng["Root_Cause"].value_counts()
                for cause, count in cause_counts.items():
                    methods_list = AppState.troubleshooting.get(station, {}).get(str(cause), [])
                    percentage = (count / total_ng * 100) if total_ng > 0 else 0
                    data.append([station, cause, methods_list, count, percentage])

            # Sort by count (descending) and limit to top 10
            data = sorted(data, key=lambda x: x[3], reverse=True)[:10]

            if data:
                html_content.append('<table class="troubleshooting">')
                html_content.append('<tr><th>Station</th><th>Root Cause</th><th>Possible Problem</th><th>Solution</th><th>Count</th><th>Percentage</th></tr>')
                for row in data:
                    station, cause, methods_list, count, percentage = row
                    html_content.append('<tr>')
                    html_content.append(f'<td>{station}</td>')
                    html_content.append(f'<td>{cause}</td>')
                
                # Split Possible Problem and Solution
                    if methods_list and len(methods_list) > 0:
                    #ul for problems
                        problems_html = '<ul>'
                        for method in methods_list:
                            if isinstance(method, dict):
                                problem = method.get('Possible Problem', 'N/A')
                                problems_html += f'<li>{problem}</li>'
                            else:
                                problems_html += f'<li>{method}</li>'
                        problems_html += '</ul>'
                        html_content.append(f'<td>{problems_html}</td>')
                    
                    # ul for solutions
                        solutions_html = '<ul>'
                        for method in methods_list:
                            if isinstance(method, dict):
                                solution = method.get('Solution', 'N/A')
                                solutions_html += f'<li>{solution}</li>'
                            else:
                                solutions_html += f'<li>{method}</li>'
                        solutions_html += '</ul>'
                        html_content.append(f'<td>{solutions_html}</td>')
                    else:
                        html_content.append('<td>No methods defined</td>')
                        html_content.append('<td>No methods defined</td>')
                
                    html_content.append(f'<td>{count}</td>')
                    html_content.append(f'<td>{percentage:.1f}%</td>')
                    html_content.append('</tr>')
                html_content.append('</table>')
            else:
                html_content.append("<p>No troubleshooting data available.</p>")

            html_content.append("</div>")
            html_content.append("</body></html>")

            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(html_content))

            # Save retrieved tables if include tables checked ( both analyzed and non-analyzed)
            if include_data:
                dir_path = os.path.dirname(path)
                for station, df in AppState.analyzed_dfs.items():
                    file_path = os.path.join(dir_path, f"{station}.{export_format}")
                    try:
                        if export_format == 'csv':
                            df.to_csv(file_path, index=False)
                        elif export_format == 'xlsx':
                            df.to_excel(file_path, index=False)
                        log(f"Saved analyzed data for {station} to {file_path}")
                    except Exception as e:
                        log(f"Failed to save analyzed data for {station}: {e}", "ERROR")
                # Save retrieved tables that were not analyzed
                for station, df in AppState.retrieved_dfs.items():
                    if station not in AppState.analyzed_dfs:
                        file_path = os.path.join(dir_path, f"{station}.{export_format}")
                        try:
                            if export_format == 'csv':
                                df.to_csv(file_path, index=False)
                            elif export_format == 'xlsx':
                                df.to_excel(file_path, index=False)
                            log(f"Saved retrieved data for {station} to {file_path}")
                        except Exception as e:
                            log(f"Failed to save retrieved data for {station}: {e}", "ERROR")

            try:
                webbrowser.open('file://' + os.path.realpath(path))
            except Exception as e:
                log(f"Failed to open browser: {e}", "WARN")
            log(f"HTML report saved at {path}")
        except Exception as e:
            log(f"Save HTML report error: {e}", "ERROR")
            if not self.auto_running:
                QMessageBox.critical(self, "Error", str(e))
        finally:
            self.unsetCursor()