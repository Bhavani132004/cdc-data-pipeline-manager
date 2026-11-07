"""
Analytics and Reports Page for CDC Data Pipeline Desktop Application.
Features Matplotlib data visualizations, execution history table, and reconciliation triggers.
"""
from tkinter import messagebox
from pathlib import Path
import customtkinter as ctk
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from .theme import (
    CARD_BG,
    BORDER_COLOR,
    TEXT_MAIN,
    TEXT_MUTED,
    ACCENT_BLUE,
    ACCENT_GREEN,
    ACCENT_RED,
    ACCENT_AMBER,
    FONT_TITLE,
    FONT_SUBTITLE,
    FONT_BODY,
    FONT_BODY_BOLD,
)
from .components import ModernTreeview
from src.database import DatabaseManager
from src.reporting import ReportingService
from scripts.reconcile import ReconciliationChecker
from src.config import AppConfig


class AnalyticsPage(ctk.CTkFrame):
    """Visual metrics, historical execution logs, and data quality reports."""

    def __init__(self, master, db_manager: DatabaseManager, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.db = db_manager
        self.reporting = ReportingService(db_manager)
        self.config = AppConfig.load()

        self._build_ui()
        self.refresh_all()

    def _build_ui(self):
        # Header Row
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=24, pady=(20, 14))

        title = ctk.CTkLabel(header_frame, text="Analytics & Quality Monitoring", font=FONT_TITLE, text_color=TEXT_MAIN)
        title.pack(side="left")

        btn_reconcile = ctk.CTkButton(
            header_frame,
            text="✓ Run Reconciliation Check",
            font=FONT_BODY_BOLD,
            fg_color=CARD_BG,
            hover_color=BORDER_COLOR,
            border_width=1,
            border_color=ACCENT_GREEN,
            text_color=ACCENT_GREEN,
            command=self._on_run_reconciliation,
        )
        btn_reconcile.pack(side="right", padx=(10, 0))

        btn_refresh = ctk.CTkButton(
            header_frame,
            text="↻ Refresh Analytics",
            font=FONT_BODY,
            fg_color=CARD_BG,
            hover_color=BORDER_COLOR,
            border_width=1,
            border_color=BORDER_COLOR,
            command=self.refresh_all,
        )
        btn_refresh.pack(side="right")

        # Top Charts Container (2 Matplotlib Subplots)
        self.charts_card = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR, height=280)
        self.charts_card.pack(fill="x", padx=24, pady=(0, 16))
        self.charts_card.pack_propagate(False)

        # Matplotlib Figure with dark styling
        self.fig = Figure(figsize=(9, 2.7), dpi=100, facecolor=CARD_BG)
        self.ax1 = self.fig.add_subplot(121)
        self.ax2 = self.fig.add_subplot(122)
        self.fig.tight_layout(pad=3.0)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.charts_card)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=12, pady=10)

        # Bottom: Pipeline Execution History Table
        history_card = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        history_card.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        lbl_hist_title = ctk.CTkLabel(
            history_card,
            text="PIPELINE EXECUTION RUN HISTORY",
            font=FONT_SUBTITLE,
            text_color=TEXT_MAIN,
        )
        lbl_hist_title.pack(anchor="w", padx=20, pady=(16, 10))

        columns = [
            ("run_id", "Run ID", 110),
            ("source_file", "Source File", 140),
            ("status", "Status", 90),
            ("total_input", "Total Input", 80),
            ("inserted_count", "Inserts", 70),
            ("updated_count", "Updates", 70),
            ("deleted_count", "Deletes", 70),
            ("duplicate_count", "Duplicates", 80),
            ("rejected_count", "Rejected", 80),
            ("late_event_count", "Late", 60),
            ("execution_time", "Time (s)", 80),
            ("start_time", "Execution Time", 150),
        ]
        self.table_runs = ModernTreeview(history_card, columns=columns)
        self.table_runs.pack(fill="both", expand=True, padx=20, pady=(0, 16))

    def refresh_all(self):
        self._refresh_charts()
        self._refresh_runs_table()

    def _refresh_charts(self):
        data = self.reporting.get_analytics_data()

        # Reset axes
        self.ax1.clear()
        self.ax2.clear()

        self.ax1.set_facecolor("#181924")
        self.ax2.set_facecolor("#181924")

        # Chart 1: Operation Distribution Bar
        ops = ["INSERT", "UPDATE", "DELETE"]
        counts = [data["operations"]["INSERT"], data["operations"]["UPDATE"], data["operations"]["DELETE"]]
        colors = [ACCENT_BLUE, ACCENT_GREEN, ACCENT_RED]

        bars = self.ax1.bar(ops, counts, color=colors, width=0.5)
        self.ax1.set_title("Historical Operations Breakdown", color=TEXT_MAIN, fontsize=10, fontweight="bold")
        self.ax1.tick_params(colors=TEXT_MUTED, labelsize=9)
        self.ax1.grid(axis="y", color="#2E3248", linestyle="--", alpha=0.6)
        for spine in self.ax1.spines.values():
            spine.set_color("#2E3248")

        # Annotate bar values
        for bar in bars:
            height = bar.get_height()
            self.ax1.annotate(
                f"{height:,}",
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                color=TEXT_MAIN,
                fontsize=8,
            )

        # Chart 2: Outcome Breakdown (Valid vs Rejected vs Duplicates)
        categories = ["Valid Events", "Rejected", "Duplicates"]
        cat_counts = [data["valid_count"], data["rejected_count"], data["duplicate_count"]]
        cat_colors = [ACCENT_GREEN, ACCENT_RED, ACCENT_AMBER]

        # Don't plot pie if all 0
        if sum(cat_counts) > 0:
            wedges, texts, autotexts = self.ax2.pie(
                cat_counts,
                labels=categories,
                colors=cat_colors,
                autopct="%1.1f%%",
                startangle=140,
                textprops={"color": TEXT_MAIN, "fontsize": 8},
            )
            for autotext in autotexts:
                autotext.set_color("#FFFFFF")
                autotext.set_weight("bold")
            self.ax2.set_title("Event Quality & Ingestion Outcomes", color=TEXT_MAIN, fontsize=10, fontweight="bold")
        else:
            self.ax2.text(0.5, 0.5, "No Data Available Yet", ha="center", va="center", color=TEXT_MUTED)
            self.ax2.set_title("Event Quality Outcomes", color=TEXT_MAIN, fontsize=10, fontweight="bold")

        self.fig.tight_layout(pad=2.0)
        self.canvas.draw()

    def _refresh_runs_table(self):
        runs = self.reporting.get_pipeline_runs(limit=100)
        rows = []
        for r in runs:
            rows.append([
                r["run_id"],
                r["source_file"],
                r["status"],
                f"{r['total_input']:,}",
                f"{r['inserted_count']:,}",
                f"{r['updated_count']:,}",
                f"{r['deleted_count']:,}",
                f"{r['duplicate_count']:,}",
                f"{r['rejected_count']:,}",
                f"{r['late_event_count']:,}",
                f"{r['execution_time_seconds']:.3f}",
                r["start_time"][:19].replace("T", " "),
            ])
        self.table_runs.insert_rows(rows)

    def _on_run_reconciliation(self):
        checker = ReconciliationChecker(self.config, self.db)
        report = checker.run_checks()
        status = report["overall_status"]
        msg = f"Reconciliation Status: {status}\n\n"
        msg += f"Passed Checks: {report['passed_checks']}/{report['total_checks']}\n\n"
        for c in report["checks"]:
            badge = "[PASS]" if c["passed"] else "[FAIL]"
            msg += f"{badge} {c['check_name']}: {c['details']}\n"

        if status == "PASS":
            messagebox.showinfo("Reconciliation Audit Succeeded", msg)
        else:
            messagebox.showwarning("Reconciliation Audit Warning", msg)
        self.refresh_all()
