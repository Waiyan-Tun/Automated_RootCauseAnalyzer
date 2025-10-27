from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QLabel, QPushButton, QHBoxLayout, QCheckBox, QComboBox, QListWidget, QListWidgetItem, QProgressDialog, QDialog, QTableWidget, QTableWidgetItem, QDialogButtonBox, QDateTimeEdit, QSizePolicy, QHeaderView, QMessageBox
)
from PyQt5.QtCore import Qt, QDateTime, QTime
import pandas as pd
from sqlalchemy import inspect, text
from app_state import AppState, log
from data_utils import safe_to_datetime, strip_dataframe

class DataTab(QWidget):
    def __init__(self, app=None, parent=None):
        super().__init__(parent)
        self.app = app
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        gb = QGroupBox('Data Selection')
        gbl = QVBoxLayout()
        gbl.setSpacing(12)
        gbl.setContentsMargins(16, 16, 16, 16)

        tables_label = QLabel('Tables')
        gbl.addWidget(tables_label)

        self.table_list = QListWidget()
        self.table_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table_list.setToolTip('Select tables to retrieve data from')
        self.table_list.setMinimumHeight(300)  
        self.table_list.setMaximumHeight(500) 
        gbl.addWidget(self.table_list, 1)

        ctrl_row = QHBoxLayout()
        self.select_all_chk = QCheckBox('Select All')
        self.select_all_chk.setChecked(True)
        self.select_all_chk.setToolTip('Select or deselect all tables')
        self.select_all_chk.stateChanged.connect(self.toggle_all_tables)
        ctrl_row.addWidget(self.select_all_chk)
        self.refresh_tables_btn = QPushButton('Refresh Tables')
        self.refresh_tables_btn.setToolTip('Refresh the list of available tables')
        self.refresh_tables_btn.setMinimumHeight(36)
        self.refresh_tables_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        ctrl_row.addWidget(self.refresh_tables_btn)
        ctrl_row.addStretch(1)
        gbl.addLayout(ctrl_row)

        filt_row = QHBoxLayout()
        filt_row.addWidget(QLabel('State'))
        self.state_combo = QComboBox()
        self.state_combo.addItems(['Auto', 'Rework', 'Single'])
        self.state_combo.setToolTip('Filter data by state')
        filt_row.addWidget(self.state_combo)
        self.apply_state_chk = QCheckBox('Apply')
        self.apply_state_chk.setChecked(True)
        self.apply_state_chk.setToolTip('Apply state filter')
        filt_row.addWidget(self.apply_state_chk)
        filt_row.addWidget(QLabel('From'))
        current = QDateTime.currentDateTime()
        from_dt = current.addDays(-7)
        from_dt.setTime(QTime(8, 0, 0))
        self.dt_from = QDateTimeEdit(from_dt)
        self.dt_from.setDisplayFormat('yyyy-MM-dd HH:mm:ss')
        self.dt_from.setCalendarPopup(True)
        self.dt_from.setToolTip('Select start date and time for data retrieval')
        filt_row.addWidget(self.dt_from)
        filt_row.addWidget(QLabel('To'))
        to_dt = current.addDays(-1)
        to_dt.setTime(QTime(7, 59, 59))
        self.dt_to = QDateTimeEdit(to_dt)
        self.dt_to.setDisplayFormat('yyyy-MM-dd HH:mm:ss')
        self.dt_to.setCalendarPopup(True)
        self.dt_to.setToolTip('Select end date and time for data retrieval')
        filt_row.addWidget(self.dt_to)
        filt_row.addStretch(1)
        gbl.addLayout(filt_row)

        self.retrieve_btn = QPushButton('Retrieve Data')
        self.retrieve_btn.setToolTip('Retrieve data for selected tables')
        self.retrieve_btn.setMinimumHeight(36)
        self.retrieve_btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        gbl.addWidget(self.retrieve_btn)

        gbl.addStretch(1)
        gb.setLayout(gbl)
        layout.addWidget(gb)
        layout.addStretch(1)
        self.setLayout(layout)

        self.refresh_tables_btn.clicked.connect(self.refresh_tables)
        self.retrieve_btn.clicked.connect(self.retrieve_data)

    def toggle_all_tables(self, state):
        for i in range(self.table_list.count()):
            item = self.table_list.item(i)
            item.setCheckState(Qt.Checked if state == Qt.Checked else Qt.Unchecked)

    def refresh_tables(self):
        try:
            self.setCursor(Qt.WaitCursor)
            insp = inspect(AppState.engine)
            tables = insp.get_table_names()
            self.table_list.clear()
            for t in tables:
                item = QListWidgetItem(t)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked)
                self.table_list.addItem(item)
            log(f"Found tables: {tables}")
            QMessageBox.information(self, 'Tables', f'Found {len(tables)} tables')
        except Exception as e:
            log(f"Error listing tables: {e}", "ERROR")
            QMessageBox.critical(self, 'Error', f'Unable to list tables: {e}')
        finally:
            self.unsetCursor()

    def retrieve_data(self):
        selected_tables = [self.table_list.item(i).text() for i in range(self.table_list.count()) if self.table_list.item(i).checkState() == Qt.Checked]
        if not selected_tables:
            QMessageBox.warning(self, 'No Tables', 'Please select at least one table')
            return
        state = self.state_combo.currentText() if self.apply_state_chk.isChecked() else None
        AppState.state = state
        dt_from = self.dt_from.dateTime().toString('yyyy-MM-dd HH:mm:ss')
        dt_to = self.dt_to.dateTime().toString('yyyy-MM-dd HH:mm:ss')
        log(f"Starting to retrieve data for selected tables: {selected_tables}, state: {state if state else 'None'}, from: {dt_from}, to: {dt_to}")

        self.prog = QProgressDialog("Retrieving data...", "Cancel", 0, len(selected_tables), self)
        self.prog.setWindowModality(Qt.WindowModal)
        self.prog.setMinimumDuration(0)
        default_size = self.prog.size()
        self.prog.resize(int(default_size.width() * 2.0), int(default_size.height() * 2.0))
        self.prog.setMinimumSize(500, 150)

        dfs = []
        canceled = False
        for idx, table in enumerate(selected_tables):
            if self.prog.wasCanceled():
                canceled = True
                break
            log(f"Retrieving data from table: {table}")
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
                self.setCursor(Qt.WaitCursor)
                df = pd.read_sql_query(text(query), AppState.engine, params=params)
            except Exception as e:
                try:
                    df = pd.read_sql_table(table, AppState.engine)
                    if state and 'State' in df.columns:
                        df = df[df['State'] == state]
                    if 'Date_Time' in df.columns:
                        df['Date_Time'] = pd.to_datetime(df['Date_Time'], errors='coerce')
                        df = df[(df['Date_Time'] >= pd.to_datetime(dt_from)) & (df['Date_Time'] <= pd.to_datetime(dt_to))]
                except Exception as e2:
                    log(f"Retrieve failed for {table}: {e} | {e2}", "ERROR")
                    QMessageBox.critical(self, 'Error', f'Failed to retrieve data for {table}: {e}\n{e2}')
                    self.prog.close()
                    return
            finally:
                self.unsetCursor()
            df = strip_dataframe(df)
            log(f"Retrieved {len(df)} rows from {table}")
            dfs.append(df)
            self.prog.setValue(idx + 1)
        self.prog.close()
        log("Data retrieval completed.")

        if canceled:
            log("Data retrieval canceled")
            return

        # data summary
        summary_dlg = QDialog(self)
        summary_layout = QVBoxLayout()
        summary_table = QTableWidget()
        summary_table.setColumnCount(5)
        summary_table.setHorizontalHeaderLabels(["Table", "Rows", "Columns", "Start Date", "End Date"])
        summary_table.setRowCount(len(selected_tables))
        for i, (tbl, df) in enumerate(zip(selected_tables, dfs)):
            rows = len(df)
            cols = len(df.columns)
            start = end = "N/A"
            if 'Date_Time' in df.columns:
                dt = safe_to_datetime(df['Date_Time'])
                if not pd.isna(dt.min()):
                    start = dt.min().strftime('%Y-%m-%d %H:%M:%S')
                if not pd.isna(dt.max()):
                    end = dt.max().strftime('%Y-%m-%d %H:%M:%S')
            summary_table.setItem(i, 0, QTableWidgetItem(tbl))
            summary_table.setItem(i, 1, QTableWidgetItem(str(rows)))
            summary_table.setItem(i, 2, QTableWidgetItem(str(cols)))
            summary_table.setItem(i, 3, QTableWidgetItem(start))
            summary_table.setItem(i, 4, QTableWidgetItem(end))
        summary_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        summary_layout.addWidget(summary_table)

        buttons = QDialogButtonBox()
        use_btn = buttons.addButton("Use Tables", QDialogButtonBox.AcceptRole)
        buttons.addButton("Cancel", QDialogButtonBox.RejectRole)
        buttons.accepted.connect(summary_dlg.accept)
        buttons.rejected.connect(summary_dlg.reject)
        summary_layout.addWidget(buttons)

        summary_dlg.setLayout(summary_layout)
        summary_dlg.setWindowTitle("Retrieved Tables Summary")
        summary_dlg.resize(900, 500)

        if summary_dlg.exec_() == QDialog.Accepted:
            AppState.retrieved_dfs = dict(zip(selected_tables, dfs))
            AppState.selected_tables = selected_tables
            log(f"User accepted retrieved data from {selected_tables}, total rows={sum(len(d) for d in dfs)}")
            if self.app:
                self.app.update_for_new_data()
                self.app.setCurrentIndex(2)
        else:
            log('User cancelled retrieved data preview')