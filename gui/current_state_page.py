"""
Current State Page for CDC Data Pipeline Desktop Application.
Presents the latest valid customer records with filtering, searching, and CSV export.
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


class CurrentStatePage(ctk.CTkFrame):
    """View and search latest current state of customers."""

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

        title = ctk.CTkLabel(header_frame, text="Current Customers State", font=FONT_TITLE, text_color=TEXT_MAIN)
        title.pack(side="left")

        # Top Control Toolbar (Search, Filter, Export, Refresh)
        toolbar = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        toolbar.pack(fill="x", padx=24, pady=(0, 14))

        tool_inner = ctk.CTkFrame(toolbar, fg_color="transparent")
        tool_inner.pack(fill="x", padx=16, pady=12)

        # Search box
        self.entry_search = ctk.CTkEntry(
            tool_inner,
            placeholder_text="Search by ID, Name, or City...",
            font=FONT_BODY,
            fg_color="#181924",
            border_color=BORDER_COLOR,
            text_color=TEXT_MAIN,
            width=260,
            height=32,
        )
        self.entry_search.pack(side="left", padx=(0, 10))
        self.entry_search.bind("<Return>", lambda e: self.refresh_table())

        # Status filter
        self.status_var = ctk.StringVar(value="ALL")
        self.combo_status = ctk.CTkOptionMenu(
            tool_inner,
            values=["ALL", "ACTIVE", "DELETED"],
            variable=self.status_var,
            command=lambda v: self.refresh_table(),
            width=110,
            height=32,
            fg_color="#181924",
            button_color=BORDER_COLOR,
            text_color=TEXT_MAIN,
        )
        self.combo_status.pack(side="left", padx=(0, 10))

        # City filter
        self.city_var = ctk.StringVar(value="ALL")
        self.combo_city = ctk.CTkOptionMenu(
            tool_inner,
            values=["ALL"],
            variable=self.city_var,
            command=lambda v: self.refresh_table(),
            width=140,
            height=32,
            fg_color="#181924",
            button_color=BORDER_COLOR,
            text_color=TEXT_MAIN,
        )
        self.combo_city.pack(side="left", padx=(0, 10))

        # Search Action
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

        # Refresh
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

        # CSV Export
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
            ("customer_id", "Customer ID", 120),
            ("name", "Customer Name", 180),
            ("city", "City", 120),
            ("salary", "Salary ($)", 100),
            ("version", "Version", 80),
            ("is_deleted", "Deleted?", 90),
            ("last_event_id", "Last Event ID", 120),
            ("updated_at", "Last Updated", 200),
        ]
        self.table = ModernTreeview(self, columns=columns)
        self.table.pack(fill="both", expand=True, padx=24, pady=(0, 20))

    def refresh_table(self):
        # Update cities dropdown
        cities = ["ALL"] + self.reporting.get_unique_cities()
        self.combo_city.configure(values=cities)

        search = self.entry_search.get().strip() or None
        city = self.city_var.get()
        status = self.status_var.get()

        records = self.reporting.get_current_customers(
            search=search,
            city_filter=city if city != "ALL" else None,
            status_filter=status,
            limit=2000,
        )

        rows = []
        for r in records:
            del_badge = "TRUE" if r["is_deleted"] else "FALSE"
            sal_str = f"${r['salary']:,.2f}"
            rows.append([
                r["customer_id"],
                r["name"],
                r["city"],
                sal_str,
                r["version"],
                del_badge,
                r["last_event_id"],
                r["updated_at"][:19].replace("T", " "),
            ])
        self.table.insert_rows(rows)

    def _on_export_csv(self):
        f = filedialog.asksaveasfilename(
            title="Export Current Customers State",
            defaultextension=".csv",
            initialfile="current_customers.csv",
            filetypes=[("CSV Files", "*.csv")],
        )
        if f:
            count = self.reporting.export_table_to_csv("current_customers", Path(f))
            messagebox.showinfo("Export Complete", f"Successfully exported {count:,} current customer records to:\n{f}")
