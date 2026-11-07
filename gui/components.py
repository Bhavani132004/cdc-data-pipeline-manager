"""
Reusable GUI Components and Widgets for CDC Data Pipeline.
"""
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from typing import List, Tuple, Optional, Callable, Dict, Any

from .theme import (
    CARD_BG,
    TEXT_MAIN,
    TEXT_MUTED,
    BORDER_COLOR,
    ACCENT_BLUE,
    FONT_FAMILY,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_METRIC_VAL,
    FONT_METRIC_LABEL,
)


class StatCard(ctk.CTkFrame):
    """Modern dashboard metric KPI card."""

    def __init__(
        self,
        master,
        title: str,
        value: str,
        subtext: str = "",
        accent_color: str = ACCENT_BLUE,
        width: int = 180,
        height: int = 100,
        **kwargs,
    ):
        super().__init__(
            master,
            fg_color=CARD_BG,
            corner_radius=8,
            border_width=1,
            border_color=BORDER_COLOR,
            width=width,
            height=height,
            **kwargs,
        )
        self.pack_propagate(False)

        # Title
        self.lbl_title = ctk.CTkLabel(
            self,
            text=title.upper(),
            font=FONT_METRIC_LABEL,
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self.lbl_title.pack(fill="x", padx=14, pady=(12, 0))

        # Big Metric Value
        self.lbl_val = ctk.CTkLabel(
            self,
            text=value,
            font=FONT_METRIC_VAL,
            text_color=accent_color,
            anchor="w",
        )
        self.lbl_val.pack(fill="x", padx=14, pady=(2, 0))

        # Subtext
        self.lbl_sub = ctk.CTkLabel(
            self,
            text=subtext,
            font=(FONT_FAMILY, 9),
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self.lbl_sub.pack(fill="x", padx=14, pady=(0, 8))

    def update_value(self, new_value: str, new_subtext: Optional[str] = None):
        self.lbl_val.configure(text=new_value)
        if new_subtext is not None:
            self.lbl_sub.configure(text=new_subtext)


class ModernTreeview(ctk.CTkFrame):
    """Wraps ttk.Treeview with styled dark theme and scrollbars."""

    def __init__(
        self,
        master,
        columns: List[Tuple[str, str, int]],  # (col_id, header_text, width)
        show_tree: bool = False,
        **kwargs,
    ):
        super().__init__(master, fg_color=CARD_BG, corner_radius=6, **kwargs)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background="#1E202E",
            foreground="#E2E8F0",
            fieldbackground="#1E202E",
            rowheight=26,
            font=(FONT_FAMILY, 10),
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background="#181924",
            foreground="#94A3B8",
            font=(FONT_FAMILY, 10, "bold"),
            borderwidth=0,
            relief="flat",
        )
        style.map(
            "Treeview.Heading",
            background=[("active", "#26293B")],
            foreground=[("active", "#FFFFFF")],
        )
        style.map(
            "Treeview",
            background=[("selected", ACCENT_BLUE)],
            foreground=[("selected", "#FFFFFF")],
        )

        col_ids = [c[0] for c in columns]
        self.tree = ttk.Treeview(
            self,
            columns=col_ids,
            show="headings" if not show_tree else "tree headings",
            selectmode="browse",
            style="Treeview",
        )

        # Scrollbars
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=self.vsb.set, xscrollcommand=self.hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew", padx=(2, 0), pady=(2, 0))
        self.vsb.grid(row=0, column=1, sticky="ns")
        self.hsb.grid(row=1, column=0, sticky="ew")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Setup column headers
        for col_id, header, width in columns:
            self.tree.heading(col_id, text=header, anchor="w")
            self.tree.column(col_id, width=width, minwidth=40, anchor="w")

    def clear(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

    def insert_rows(self, rows: List[List[Any]]):
        self.clear()
        for r in rows:
            self.tree.insert("", "end", values=r)
