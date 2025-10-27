from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QDialogButtonBox, QPushButton, QFileDialog, QHBoxLayout, QMessageBox, QHeaderView, QSizePolicy
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

class PreviewDialog(QDialog):
    def __init__(self, df, parent=None, allow_all_rows=True, title="Preview"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(1200, 800)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        self.table = QTableWidget(self)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)

        table = self.table
        table.setColumnCount(len(df.columns))
        table.setHorizontalHeaderLabels([str(c) for c in df.columns])
        
        max_rows = len(df)
        if not allow_all_rows:
            max_rows = min(500, len(df))
            self.warning_label = QLabel("(Preview truncated to 500 rows for performance)")
            layout.addWidget(self.warning_label)
        table.setRowCount(max_rows)
        for i in range(max_rows):
            row = df.iloc[i]
            for j, val in enumerate(row):
                table.setItem(i, j, QTableWidgetItem("" if pd.isna(val) else str(val)))

        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.resizeRowsToContents()
        layout.addWidget(table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok, self)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

class VisualDialog(QDialog):
    def __init__(self, title: str, plot_fn, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(1000, 700)
        vbox = QVBoxLayout(self)
        vbox.setSpacing(12)
        vbox.setContentsMargins(16, 16, 16, 16)

        self.canvas = FigureCanvas(Figure(tight_layout=True))
        vbox.addWidget(self.canvas, 1)
        self.ax = self.canvas.figure.add_subplot(111)

        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("Save Visual")
        self.save_btn.setToolTip("Save the visualization as an image or PDF")
        self.save_btn.clicked.connect(self.save_visual)
        btn_row.addStretch(1)
        btn_row.addWidget(self.save_btn)
        vbox.addLayout(btn_row)

        plot_fn(self.ax)
        self.canvas.draw()

    def save_visual(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Visual", "visual.png",
                                              "PNG Image (*.png);;JPEG Image (*.jpg);;PDF File (*.pdf)")
        if not path:
            return
        try:
            self.canvas.figure.savefig(path, bbox_inches="tight")
            QMessageBox.information(self, "Saved", f"Visual saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))