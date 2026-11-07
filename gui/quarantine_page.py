"""
Quarantine Page for CDC Data Pipeline Desktop Application.
Presents rejected anomalies, schema violations, and conflicting payloads with audit traceability.
"""
from tkinter import filedialog, messagebox
from pathlib import Path
import customtkinter as ctk

from .theme import (
    CARD_BG,
    BORDER_COLOR,
    TEXT_MAIN,
    TEXT_MUTED,
    ACCENT_RED,
    ACCENT_BLUE,
    FONT_TITLE,
    FONT_BODY,
    FONT_BODY_BOLD,
)
from .components import ModernTreeview
from src.database import DatabaseManager
from src.reporting import ReportingService


class QuarantinePage(ctk.CTkFrame):
    """View and export quarantined records."""

    def __init__(self, master, db_manager: DatabaseManager, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.db = db_manager
        self.reporting = ReportingService(db_manager)

        self._build_ui()
        self.refresh_table()

    def _build_ui(self):
        # Header Row
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=24, pady=(20, 14))

        title = ctk.CTkLabel(header_frame, text="Quarantine & Rejections Audit", font=FONT_TITLE, text_color=TEXT_MAIN)
        title.pack(side="left")

        # Toolbar
        toolbar = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        toolbar.pack(fill="x", padx=24, pady=(0, 14))

        tool_inner = ctk.CTkFrame(toolbar, fg_color="transparent")
        tool_inner.pack(fill="x", padx=16, pady=12)

        # Search
        self.entry_search = ctk.CTkEntry(
            tool_inner,
            placeholder_text="Search by Event ID, Customer ID, Reason, or File...",
            font=FONT_BODY,
            fg_color="#181924",
            border_color=BORDER_COLOR,
            text_color=TEXT_MAIN,
            width=360,
            height=32,
        )
        self.entry_search.pack(side="left", padx=(0, 10))
        self.entry_search.bind("<Return>", lambda e: self.refresh_table())

        btn_search = ctk.CTkButton(
            tool_inner,
            text="Filter",
            width=80,
            height=32,
            font=FONT_BODY_BOLD,
            fg_color=ACCENT_BLUE,
            command=self.refresh_table,
        )
        btn_search.pack(side="left", padx=(0, 10))

        btn_refresh = ctk.CTkButton(
            tool_inner,
            text="↻ Refresh",
            width=90,
            height=32,
            font=FONT_BODY,
            fg_color=CARD_BG,
            hover_color=BORDER_COLOR,
            border_width=1,
            border_color=BORDER_COLOR,
            command=self.refresh_table,
        )
        btn_refresh.pack(side="left", padx=(0, 10))

        btn_export = ctk.CTkButton(
            tool_inner,
            text="⤓ Export CSV",
            width=110,
            height=32,
            font=FONT_BODY_BOLD,
            fg_color=ACCENT_RED,
            hover_color="#DC2626",
            command=self._on_export_csv,
        )
        btn_export.pack(side="right")

        # Table View
        columns = [
            ("reject_id", "ID", 50),
            ("event_id", "Event ID", 110),
            ("customer_id", "Customer ID", 110),
            ("rejection_reason", "Rejection Reason", 240),
            ("original_payload", "Original Raw Payload", 280),
            ("source_file", "Source File", 140),
            ("rejected_at", "Rejected Timestamp", 160),
        ]
        self.table = ModernTreeview(self, columns=columns)
        self.table.pack(fill="both", expand=True, padx=24, pady=(0, 20))

    def refresh_table(self):
        search = self.entry_search.get().strip() or None
        records = self.reporting.get_quarantine(search=search, limit=2000)

        rows = []
        for r in records:
            rows.append([
                r["reject_id"],
                r["event_id"] or "-",
                r["customer_id"] or "-",
                r["rejection_reason"],
                r["original_payload"],
                r["source_file"],
                r["rejected_at"][:19].replace("T", " "),
            ])
        self.table.insert_rows(rows)

    def _on_export_csv(self):
        f = filedialog.asksaveasfilename(
            title="Export Quarantined Rejections",
            defaultextension=".csv",
            initialfile="rejected_records.csv",
            filetypes=[("CSV Files", "*.csv")],
        )
        if f:
            count = self.reporting.export_table_to_csv("rejected_records", Path(f))
            messagebox.showinfo("Export Complete", f"Successfully exported {count:,} quarantined records to:\n{f}")
