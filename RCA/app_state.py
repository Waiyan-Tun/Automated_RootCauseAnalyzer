from datetime import datetime
from PyQt5.QtCore import pyqtSignal, QObject

class LogSignal(QObject):
    log_updated = pyqtSignal()

class AppState:
    engine = None
    selected_database = None
    selected_tables = []
    retrieved_dfs = {}
    analyzed_dfs = {}
    rules = {}
    troubleshooting = {}
    logs = []
    log_signal = LogSignal()
    state = None

    @classmethod
    def append_log(cls, text):
        cls.logs.append(text)
        cls.log_signal.log_updated.emit()

def log(msg, level='INFO'):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    entry = f"[{ts}] {level}: {msg}"
    print(entry)
    AppState.append_log(entry)