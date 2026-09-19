"""Independent, read-only desktop dashboard for coding_tracker.py.

Run: python dashboard.py --data-dir "C:\\path\\to\\tracker-data"
Demo: python dashboard.py --demo
The tracker is deliberately never imported or started here.
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import QLocale, QSettings, QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDoubleSpinBox, QFileDialog, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QScrollArea, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from tracker_data import TrackerReader, demo_snapshot, duration

BG = "#101725"
PANEL = "#182236"
TEXT = "#edf2fa"
MUTED = "#aab8cf"
GREEN = "#64dfbb"
BLUE = "#799dff"
STYLE = f"""
QWidget {{ background: {BG}; color: {TEXT}; font-family: 'Segoe UI'; font-size: 13px; }}
QLabel {{ background: transparent; }}
QFrame#card {{ background: {PANEL}; border: 1px solid #2b3951; border-radius: 12px; }}
QLabel#title {{ font-size: 28px; font-weight: 700; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#metric {{ font-size: 27px; font-weight: 700; color: {GREEN}; }}
QPushButton, QComboBox, QDoubleSpinBox {{ background: #24334d; border: 1px solid #40516f;
    border-radius: 6px; padding: 8px 12px; min-height: 20px; }}
QPushButton:hover {{ background: #344967; }}
QTableWidget {{ background: {PANEL}; gridline-color: #2b3951; border: 0; }}
QHeaderView::section {{ background: #24334d; color: {MUTED}; padding: 9px; border: 0; }}
QProgressBar {{ border: 0; border-radius: 5px; background: #2b3951; height: 12px; }}
QProgressBar::chunk {{ background: {GREEN}; border-radius: 5px; }}
QScrollArea {{ border: 0; }}
"""


def label(text, name=None):
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    return widget


class Dashboard(QMainWindow):
    def __init__(self, folder=None, demo=False):
        super().__init__()
        self.demo = demo
        self.settings = QSettings("CodingTracker", "Dashboard")
        default = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
        self.folder = Path(folder or self.settings.value("data_dir", str(default)))
        self.reader = TrackerReader(self.folder)
        self.snapshot = None
        self.chart_key = None
        self.setWindowTitle("Coding Tracker · Dashboard" + (" · DEMO" if demo else ""))
        self.resize(1180, 900)
        self.setMinimumSize(900, 650)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root = QWidget()
        scroll.setWidget(root)
        self.setCentralWidget(scroll)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        header = QHBoxLayout()
        header.addWidget(label("Coding overview", "title"))
        header.addStretch()
        choose = QPushButton("Data folder")
        choose.clicked.connect(self.choose_folder)
        header.addWidget(choose)
        export = QPushButton("Export CSV")
        export.clicked.connect(self.export_csv)
        header.addWidget(export)
        layout.addLayout(header)
        self.source = label("", "muted")
        self.source.setWordWrap(True)
        self.source.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.source)
        self.status = label("", "muted")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        controls = QHBoxLayout()
        controls.addWidget(label("Period"))
        self.period = QComboBox()
        for n in (5, 7, 14, 30, 90):
            self.period.addItem(f"Last {n} days", n)
        self.period.currentIndexChanged.connect(self.render)
        controls.addWidget(self.period)
        controls.addStretch()
        controls.addWidget(label("Daily goal"))
        self.goal = QDoubleSpinBox()
        self.goal.setRange(0.25, 24)
        self.goal.setSingleStep(0.25)
        self.goal.setSuffix(" hours")
        self.goal.setValue(float(self.settings.value("goal", 3.0)))
        self.goal.valueChanged.connect(self.goal_changed)
        controls.addWidget(self.goal)
        layout.addLayout(controls)
        grid = QGridLayout()
        self.cards = []
        for i, title in enumerate(("TODAY · SAVED TIME", "PERIOD TOTAL", "AVERAGE / RECORDED DAY",
                                   "MAX · COMPLETED DAY", "MIN · COMPLETED DAY", "DAYS WITH CODING ACTIVITY")):
            frame = QFrame()
            frame.setObjectName("card")
            card = QVBoxLayout(frame)
            card.setContentsMargins(16, 15, 16, 15)
            caption = label(title, "muted")
            caption.setWordWrap(True)
            card.addWidget(caption)
            value = label("—", "metric")
            detail = label("", "muted")
            card.addWidget(value)
            card.addWidget(detail)
            self.cards.append((value, detail))
            grid.addWidget(frame, i // 3, i % 3)
        layout.addLayout(grid)
        self.goal_text = label("")
        layout.addWidget(self.goal_text)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        self.figure = Figure(figsize=(10, 3.8), facecolor=BG, layout="constrained")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumHeight(330)
        layout.addWidget(self.canvas)
        layout.addWidget(label("Daily history", "title"))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Date", "Coding time", "Record status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setMinimumHeight(220)
        layout.addWidget(self.table)
        note = label("Days without a record are shown as unknown, not zero. "
                     "The total and average include today's partial day. "
                     "MIN / MAX cover recorded days before today within the selected period.", "muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.timer = QTimer(self)
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        self.refresh()

    def choose_folder(self):
        selected = QFileDialog.getExistingDirectory(self, "Select the folder containing log.txt and last_session.json", str(self.folder))
        if selected:
            self.demo = False
            self.setWindowTitle("Coding Tracker · Dashboard")
            self.folder = Path(selected)
            self.settings.setValue("data_dir", selected)
            self.reader = TrackerReader(self.folder)
            self.chart_key = None
            self.refresh()

    def goal_changed(self):
        if not self.demo:
            self.settings.setValue("goal", self.goal.value())
        self.render()

    def refresh(self):
        self.snapshot = demo_snapshot() if self.demo else self.reader.read()
        self.source.setText("DEMO · Sample data, not actual measurements" if self.demo else f"Data: {self.folder}")
        saved = self.snapshot.saved_at
        stamp = datetime.fromtimestamp(saved).strftime("%d/%m/%Y %H:%M:%S") if saved else "unavailable"
        status = f"Last saved: {stamp} · Checking files every 5s."
        if not self.demo:
            status += " The original tracker saves periodically every 45 minutes; this timestamp does not confirm that it is running."
        if self.snapshot.warnings:
            status += "\n" + "\n".join(self.snapshot.warnings)
        self.status.setText(status)
        self.render()

    def render(self):
        if self.snapshot is None:
            return
        today = date.today()
        rows = self.snapshot.period(self.period.currentData())
        known = [(d, s) for d, s in rows if s is not None]
        completed = [(d, s) for d, s in known if d < today]
        total = sum(s for _, s in known)
        current = self.snapshot.days.get(today)
        best = max(completed, key=lambda item: item[1]) if completed else None
        least = min(completed, key=lambda item: item[1]) if completed else None
        metrics = [(duration(current), "Partial day" if current is not None else "No record for today"),
                   (duration(total) if known else "—", f"{len(known)} / {len(rows)} days with data"),
                   (duration(total / len(known)) if known else "—", "Includes recorded days with 0h"),
                   (duration(best[1]) if best else "—", best[0].strftime("%d/%m/%Y") if best else "No completed day"),
                   (duration(least[1]) if least else "—", least[0].strftime("%d/%m/%Y") if least else "No completed day"),
                   (str(sum(s > 0 for _, s in known)), "Within the selected period")]
        for (value, detail), (a, b) in zip(self.cards, metrics):
            value.setText(a)
            detail.setText(b)
        fraction = current / (self.goal.value() * 3600) if current is not None else 0
        self.progress.setValue(min(1000, int(fraction * 1000)))
        self.goal_text.setText(f"Today's goal: {duration(current)} / {duration(self.goal.value()*3600)}"
                               + (f" · {fraction:.0%}" if current is not None else " · No data available"))
        key = (tuple(rows), self.goal.value())
        if key == self.chart_key:
            return
        self.chart_key = key
        self.draw_charts(rows)
        self.table.setRowCount(len(rows))
        for i, (day, value) in enumerate(reversed(rows)):
            state = "No data" if value is None else ("Partial day" if day == today else "Recorded")
            for j, text in enumerate((day.strftime("%d/%m/%Y"), duration(value), state)):
                item = QTableWidgetItem(text)
                item.setForeground(QColor(MUTED if value is None else TEXT))
                self.table.setItem(i, j, item)

    def draw_charts(self, rows):
        self.figure.clear()
        daily, cumulative = self.figure.subplots(1, 2)
        for ax, title in ((daily, "Hours per day"), (cumulative, "Cumulative recorded time")):
            ax.set_facecolor(BG)
            ax.set_title(title, color=TEXT, loc="left", fontsize=11, pad=18)
            ax.tick_params(colors=MUTED, labelsize=8)
            for spine in ax.spines.values():
                spine.set_visible(False)
            ax.grid(axis="y", color="#2b3951", linewidth=0.6)
            ax.set_axisbelow(True)
            ax.set_ylabel("hours", color=MUTED, fontsize=9)
            step = max(1, (len(rows) + 5) // 6)
            ticks = list(range(0, len(rows), step))
            if len(rows)-1 not in ticks:
                ticks.append(len(rows)-1)
            ax.set_xticks(ticks, [rows[i][0].strftime("%d/%m") for i in ticks])
            ax.set_xlim(-0.7, len(rows)-0.3)
        x = list(range(len(rows)))
        values = [s / 3600 if s is not None else float("nan") for _, s in rows]
        daily.bar(x, values, color=[GREEN if d == date.today() else BLUE for d, _ in rows], width=0.6)
        for i, (_, s) in enumerate(rows):
            if s is None:
                daily.text(i, 0.025, "?", transform=daily.get_xaxis_transform(), color=MUTED, ha="center")
        daily.axhline(self.goal.value(), color=GREEN, linestyle="--", linewidth=1, label="Goal")
        daily.legend(facecolor=BG, labelcolor=MUTED, frameon=False, fontsize=8)
        daily.set_ylim(bottom=0, top=max([self.goal.value()] + [v for v in values if v == v]) * 1.25)
        if any(s is not None for _, s in rows):
            running = 0
            totals = []
            for _, s in rows:
                running += (s or 0) / 3600
                totals.append(running)
            cumulative.plot(x, totals, color=GREEN, linewidth=2)
            cumulative.fill_between(x, totals, color=GREEN, alpha=0.09)
            cumulative.set_ylim(bottom=0, top=max(1, running * 1.15))
        else:
            cumulative.text(0.5, 0.5, "No data available", transform=cumulative.transAxes,
                            color=MUTED, ha="center")
        self.canvas.draw_idle()

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export selected period", "coding_history.csv", "CSV (*.csv)")
        if not path:
            return
        # Protect the source files even if a different extension is typed.
        if Path(path).resolve() in {(self.folder / n).resolve() for n in
                                    ("log.txt", "last_session.json", "user_config.json", "console_log.txt")}:
            QMessageBox.warning(self, "Export", "Choose a file other than the tracker data files.")
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as file:
                writer = csv.writer(file)
                writer.writerow(["date", "seconds", "hours", "status", "demo"])
                for day, value in self.snapshot.period(self.period.currentData()):
                    writer.writerow([day.isoformat(), "" if value is None else value,
                                     "" if value is None else round(value / 3600, 6),
                                     "unknown" if value is None else "partial" if day == date.today() else "recorded",
                                     self.demo])
        except OSError as exc:
            QMessageBox.warning(self, "Export", f"Unable to save the CSV file ({type(exc).__name__}). Check the destination and file permissions.")
        else:
            QMessageBox.information(self, "Export", "The CSV file has been saved.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, help="Folder containing log.txt and last_session.json")
    parser.add_argument("--demo", action="store_true", help="Show clearly labelled example data")
    args = parser.parse_args()
    # Keep standard Qt dialogs and numeric controls in English on any OS locale.
    QLocale.setDefault(QLocale(QLocale.Language.English, QLocale.Country.UnitedKingdom))
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs)
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = Dashboard(args.data_dir, args.demo)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
