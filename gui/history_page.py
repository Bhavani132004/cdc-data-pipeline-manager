"""
History Page for CDC Data Pipeline Desktop Application.
Presents the complete immutable audit trail of processed CDC events.
"""
from tkinter import filedialog, messagebox
from pathlib import Path
import customtkinter as ctk

from .theme import (
    CARD_BG,
    BORDER_COLOR,
    TEXT_MAIN,
    TEXT_MUTED,
    ACCENT_BLUE,
    FONT_TITLE,
    FONT_BODY,
    FONT_BODY_BOLD,
)
from .components import ModernTreeview
from src.database import DatabaseManager
from src.reporting import ReportingService


class HistoryPage(ctk.CTkFrame):
    """Immutable CDC history audit view."""

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

        title = ctk.CTkLabel(header_frame, text="Event Audit History", font=FONT_TITLE, text_color=TEXT_MAIN)
        title.pack(side="left")

        # Toolbar
        toolbar = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        toolbar.pack(fill="x", padx=24, pady=(0, 14))

        tool_inner = ctk.CTkFrame(toolbar, fg_color="transparent")
        tool_inner.pack(fill="x", padx=16, pady=12)

        # Search
        self.entry_search = ctk.CTkEntry(
            tool_inner,
            placeholder_text="Search by Event ID, Customer ID, or File...",
            font=FONT_BODY,
            fg_color="#181924",
            border_color=BORDER_COLOR,
            text_color=TEXT_MAIN,
            width=300,
            height=32,
        )
        self.entry_search.pack(side="left", padx=(0, 10))
        self.entry_search.bind("<Return>", lambda e: self.refresh_table())

        # Operation filter
        self.op_var = ctk.StringVar(value="ALL")
        self.combo_op = ctk.CTkOptionMenu(
            tool_inner,
            values=["ALL", "INSERT", "UPDATE", "DELETE"],
            variable=self.op_var,
            command=lambda v: self.refresh_table(),
            width=120,
            height=32,
            fg_color="#181924",
            button_color=BORDER_COLOR,
            text_color=TEXT_MAIN,
        )
        self.combo_op.pack(side="left", padx=(0, 10))

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
            fg_color="#10B981",
            hover_color="#059669",
            command=self._on_export_csv,
        )
        btn_export.pack(side="right")

        # Table View
        columns = [
            ("event_id", "Event ID", 110),
            ("customer_id", "Customer ID", 110),
            ("operation", "Operation", 90),
            ("version", "Ver", 60),
            ("event_timestamp", "Event Timestamp", 180),
            ("event_status", "Status", 130),
            ("source_file", "Source File", 160),
            ("run_id", "Run ID", 110),
            ("payload_hash", "Payload Hash (SHA-256)", 180),
        ]
        self.table = ModernTreeview(self, columns=columns)
        self.table.pack(fill="both", expand=True, padx=24, pady=(0, 20))

    def refresh_table(self):
        search = self.entry_search.get().strip() or None
        op = self.op_var.get()

        records = self.reporting.get_history(
            search=search,
            operation_filter=op,
            limit=2000,
        )

        rows = []
        for r in records:
            short_hash = f"{r['payload_hash'][:16]}..." if r.get("payload_hash") else "-"
            rows.append([
                r["event_id"],
                r["customer_id"],
                r["operation"],
                r["version"],
                r["event_timestamp"][:19].replace("T", " "),
                r["event_status"],
                r["source_file"],
                r["run_id"],
                short_hash,
            ])
        self.table.insert_rows(rows)

    def _on_export_csv(self):
        f = filedialog.asksaveasfilename(
            title="Export Customer History",
            defaultextension=".csv",
            initialfile="customer_history.csv",
            filetypes=[("CSV Files", "*.csv")],
        )
        if f:
            count = self.reporting.export_table_to_csv("customer_history", Path(f))
            messagebox.showinfo("Export Complete", f"Successfully exported {count:,} history records to:\n{f}")

