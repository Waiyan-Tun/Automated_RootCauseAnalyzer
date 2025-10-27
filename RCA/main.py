import sys
import os
import json
import traceback
from datetime import datetime, timedelta, date, time
from functools import partial
import itertools
import matplotlib.colors as mcolors
import base64
from io import BytesIO
import webbrowser
import numpy as np
import pandas as pd
import platform

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QThread, QDateTime, QObject, QTime, QDate, QTimer
from PyQt5.QtGui import QColor, QPixmap

from sqlalchemy import create_engine, inspect, text
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from app_state import AppState, log
from loaders import load_rules, load_troubleshooting
from rule_analyzer_app import RuleAnalyzerApp

if __name__ == "__main__":
    app = QApplication(sys.argv)
    AppState.rules = load_rules()
    AppState.troubleshooting = load_troubleshooting()
    win = RuleAnalyzerApp()

    # Check if auto-run from configuration
    auto_run = False
    config_path = "JSON_Files/app_config.json"
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            auto_run = config.get("auto_run", False)
        except Exception as e:
            log(f"Failed to load app_config.json: {e}", "ERROR")

    if auto_run:
        msg = QMessageBox()
        msg.setWindowTitle("Auto Run Confirmation")
        msg.setText("Do you want to run the analysis automatically?")
        msg.setIcon(QMessageBox.Question)
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)

        timer = QTimer()
        def on_timeout():
            msg.done(0)  # Close if no action within 3 minutes

        timer.singleShot(180000, on_timeout)  # 180 seconds timeout

        result = msg.exec_()

        if result == QMessageBox.Yes:
            win.auto_running = True
            win.perform_auto_run(config)
        elif result == QMessageBox.No:
            # Confirm close
            confirm_msg = QMessageBox()
            confirm_msg.setWindowTitle("Confirm")
            confirm_msg.setText("Are you sure to close the app?")
            confirm_msg.setIcon(QMessageBox.Question)
            confirm_msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            confirm_result = confirm_msg.exec_()
            if confirm_result == QMessageBox.Yes:
                sys.exit(0)
            else:
                win.show()
        else:
            sys.exit(0)
    else:
        win.show()

    sys.exit(app.exec_())
