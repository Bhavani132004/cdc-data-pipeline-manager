"""
Dashboard Page for CDC Data Pipeline Desktop Application.
Presents high-level metrics, system health, and latest execution status.
"""
import customtkinter as ctk
from typing import Optional, Callable

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
from .components import StatCard
from src.database import DatabaseManager


class DashboardPage(ctk.CTkFrame):
    """Main executive overview dashboard."""

    def __init__(self, master, db_manager: DatabaseManager, on_navigate: Optional[Callable[[str], None]] = None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.db = db_manager
        self.on_navigate = on_navigate

        self._build_ui()
        self.refresh_data()

    def _build_ui(self):
        # Header Row
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=24, pady=(20, 16))

        title = ctk.CTkLabel(
            header_frame,
            text="CDC Pipeline Overview",
            font=FONT_TITLE,
            text_color=TEXT_MAIN,
        )
        title.pack(side="left")

        btn_refresh = ctk.CTkButton(
            header_frame,
            text="↻ Refresh Data",
            width=110,
            height=32,
            fg_color=CARD_BG,
            hover_color=BORDER_COLOR,
            text_color=TEXT_MAIN,
            font=FONT_BODY,
            command=self.refresh_data,
        )
        btn_refresh.pack(side="right")

        # KPI Cards Grid
        self.cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.cards_frame.pack(fill="x", padx=24, pady=(0, 20))
        self.cards_frame.grid_columnconfigure((0, 1, 2, 3), weight=1, pad=12)

        self.card_active = StatCard(
            self.cards_frame,
            title="Active Customers",
            value="0",
            subtext="Current valid records",
            accent_color=ACCENT_GREEN,
        )
        self.card_active.grid(row=0, column=0, sticky="ew")

        self.card_history = StatCard(
            self.cards_frame,
            title="Historical Events",
            value="0",
            subtext="All audited CDC events",
            accent_color=ACCENT_BLUE,
        )
        self.card_history.grid(row=0, column=1, sticky="ew")

        self.card_rejected = StatCard(
            self.cards_frame,
            title="Rejected Records",
            value="0",
            subtext="Quarantined anomalies",
            accent_color=ACCENT_RED,
        )
        self.card_rejected.grid(row=0, column=2, sticky="ew")

        self.card_duplicates = StatCard(
            self.cards_frame,
            title="Duplicate Events",
            value="0",
            subtext="Idempotently skipped",
            accent_color=ACCENT_AMBER,
        )
        self.card_duplicates.grid(row=0, column=3, sticky="ew")

        # Lower Detail Panels
        lower_frame = ctk.CTkFrame(self, fg_color="transparent")
        lower_frame.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        lower_frame.grid_columnconfigure(0, weight=3, pad=16)
        lower_frame.grid_columnconfigure(1, weight=2, pad=16)
        lower_frame.grid_rowconfigure(0, weight=1)

        # Panel 1: Latest Pipeline Run Card
        self.panel_run = ctk.CTkFrame(
            lower_frame,
            fg_color=CARD_BG,
            corner_radius=8,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.panel_run.grid(row=0, column=0, sticky="nsew")

        lbl_run_title = ctk.CTkLabel(
            self.panel_run,
            text="LATEST EXECUTION STATUS",
            font=FONT_SUBTITLE,
            text_color=TEXT_MAIN,
        )
        lbl_run_title.pack(anchor="w", padx=20, pady=(16, 12))

        self.lbl_run_id = ctk.CTkLabel(self.panel_run, text="Run ID: None", font=FONT_BODY_BOLD, text_color=TEXT_MAIN)
        self.lbl_run_id.pack(anchor="w", padx=20, pady=2)

        self.lbl_run_status = ctk.CTkLabel(self.panel_run, text="Status: IDLE", font=FONT_BODY, text_color=TEXT_MUTED)
        self.lbl_run_status.pack(anchor="w", padx=20, pady=2)

        self.lbl_run_file = ctk.CTkLabel(self.panel_run, text="Source File: -", font=FONT_BODY, text_color=TEXT_MUTED)
        self.lbl_run_file.pack(anchor="w", padx=20, pady=2)

        self.lbl_run_input = ctk.CTkLabel(self.panel_run, text="Records Processed: -", font=FONT_BODY, text_color=TEXT_MUTED)
        self.lbl_run_input.pack(anchor="w", padx=20, pady=2)

        self.lbl_run_duration = ctk.CTkLabel(self.panel_run, text="Execution Time: -", font=FONT_BODY, text_color=TEXT_MUTED)
        self.lbl_run_duration.pack(anchor="w", padx=20, pady=2)

        # Quick Actions
        actions_box = ctk.CTkFrame(self.panel_run, fg_color="transparent")
        actions_box.pack(anchor="w", padx=20, pady=(20, 16))

        btn_run = ctk.CTkButton(
            actions_box,
            text="▶ Ingest New File",
            fg_color=ACCENT_BLUE,
            hover_color="#2563EB",
            font=FONT_BODY_BOLD,
            command=lambda: self.on_navigate("pipeline") if self.on_navigate else None,
        )
        btn_run.pack(side="left", padx=(0, 10))

        # Panel 2: System Health and Pipeline Metrics
        self.panel_health = ctk.CTkFrame(
            lower_frame,
            fg_color=CARD_BG,
            corner_radius=8,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.panel_health.grid(row=0, column=1, sticky="nsew")

        lbl_health_title = ctk.CTkLabel(
            self.panel_health,
            text="DATABASE INTEGRITY & HEALTH",
            font=FONT_SUBTITLE,
            text_color=TEXT_MAIN,
        )
        lbl_health_title.pack(anchor="w", padx=20, pady=(16, 12))

        self.lbl_h_deleted = ctk.CTkLabel(self.panel_health, text="Soft-Deleted Customers: 0", font=FONT_BODY, text_color=TEXT_MUTED)
        self.lbl_h_deleted.pack(anchor="w", padx=20, pady=4)

        self.lbl_h_late = ctk.CTkLabel(self.panel_health, text="Late-Arriving Events: 0", font=FONT_BODY, text_color=TEXT_MUTED)
        self.lbl_h_late.pack(anchor="w", padx=20, pady=4)

        self.lbl_h_total_input = ctk.CTkLabel(self.panel_health, text="Cumulative Events Input: 0", font=FONT_BODY, text_color=TEXT_MUTED)
        self.lbl_h_total_input.pack(anchor="w", padx=20, pady=4)

        btn_reconcile = ctk.CTkButton(
            self.panel_health,
            text="✓ Run Reconciliation Audit",
            fg_color=CARD_BG,
            hover_color=BORDER_COLOR,
            border_width=1,
            border_color=ACCENT_GREEN,
            text_color=ACCENT_GREEN,
            font=FONT_BODY_BOLD,
            command=lambda: self.on_navigate("analytics") if self.on_navigate else None,
        )
        btn_reconcile.pack(anchor="w", padx=20, pady=(20, 16))

    def refresh_data(self):
        """Fetches fresh data from SQLite and updates UI."""
        metrics = self.db.get_summary_metrics()

        self.card_active.update_value(f"{metrics['active_customers']:,}")
        self.card_history.update_value(f"{metrics['total_history']:,}")
        self.card_rejected.update_value(f"{metrics['total_rejected']:,}")
        self.card_duplicates.update_value(f"{metrics['total_duplicates']:,}")

        self.lbl_h_deleted.configure(text=f"Soft-Deleted Customers: {metrics['deleted_customers']:,}")
        self.lbl_h_late.configure(text=f"Late-Arriving Events: {metrics['total_late_events']:,}")
        self.lbl_h_total_input.configure(text=f"Cumulative Events Ingested: {metrics['total_input_all_runs']:,}")

        latest = metrics.get("latest_run")
        if latest:
            self.lbl_run_id.configure(text=f"Run ID: {latest['run_id']}")
            status_text = f"Status: {latest['status']}"
            color = ACCENT_GREEN if latest["status"] == "COMPLETED" else ACCENT_RED
            self.lbl_run_status.configure(text=status_text, text_color=color)
            self.lbl_run_file.configure(text=f"Source File: {latest['source_file']}")
            self.lbl_run_input.configure(
                text=f"Processed: {latest['total_input']:,} total ({latest['valid_count']:,} valid, {latest['rejected_count']:,} rejected)"
            )
            self.lbl_run_duration.configure(text=f"Execution Duration: {latest['execution_time_seconds']:.3f}s")
        else:
            self.lbl_run_id.configure(text="Run ID: None (No runs yet)")
            self.lbl_run_status.configure(text="Status: IDLE", text_color=TEXT_MUTED)

