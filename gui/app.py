"""
Main Desktop Application Window and Navigation Manager.
CDC Data Pipeline Manager - Modern CustomTkinter Desktop Dashboard.
"""
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import tkinter as tk
import customtkinter as ctk

from .theme import (
    BG_DARK,
    SIDEBAR_BG,
    CARD_BG,
    CARD_HOVER,
    BORDER_COLOR,
    TEXT_MAIN,
    TEXT_MUTED,
    ACCENT_BLUE,
    FONT_TITLE,
    FONT_SUBTITLE,
    FONT_BODY,
    FONT_BODY_BOLD,
)
from .dashboard import DashboardPage
from .pipeline_page import PipelinePage
from .current_state_page import CurrentStatePage
from .history_page import HistoryPage
from .quarantine_page import QuarantinePage
from .analytics_page import AnalyticsPage
from .settings_page import SettingsPage

from src.config import AppConfig
from src.database import DatabaseManager


class CDCDataPipelineApp(ctk.CTk):
    """Primary application frame and page router."""

    def __init__(self, config: AppConfig = None):
        super().__init__()

        # Appearance configuration
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.title("CDC Data Pipeline Manager")
        self.geometry("1180x760")
        self.minsize(1000, 650)
        self.configure(fg_color=BG_DARK)

        self.config = config or AppConfig.load()
        self.db_manager = DatabaseManager(self.config.db_url, echo=self.config.db_echo)
        self.db_manager.init_db()

        self._build_layout()
        self._navigate("dashboard")

    def _build_layout(self):
        # Master grid layout: 2 columns (Sidebar, Main Content)
        self.grid_columnconfigure(0, weight=0, minsize=240)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. Sidebar Frame
        self.sidebar = ctk.CTkFrame(
            self,
            fg_color=SIDEBAR_BG,
            corner_radius=0,
            border_width=1,
            border_color=BORDER_COLOR,
            width=240,
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        # Logo / App Title in Sidebar
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.pack(fill="x", padx=18, pady=(24, 28))

        lbl_logo = ctk.CTkLabel(
            logo_frame,
            text="⚡ CDC MANAGER",
            font=FONT_TITLE,
            text_color=ACCENT_BLUE,
            anchor="w",
        )
        lbl_logo.pack(anchor="w")

        lbl_sub = ctk.CTkLabel(
            logo_frame,
            text="Change Data Capture Pipeline",
            font=(FONT_BODY[0], 9),
            text_color=TEXT_MUTED,
            anchor="w",
        )
        lbl_sub.pack(anchor="w")

        # Navigation Buttons
        self.nav_buttons = {}
        pages = [
            ("dashboard", "📊  Dashboard"),
            ("pipeline", "▶  Run Pipeline"),
            ("current_state", "👥  Current State"),
            ("history", "📜  Audit History"),
            ("quarantine", "🛡  Quarantine"),
            ("analytics", "📈  Analytics & Reports"),
            ("settings", "⚙  Settings"),
        ]

        for page_id, text in pages:
            btn = ctk.CTkButton(
                self.sidebar,
                text=text,
                font=FONT_BODY_BOLD,
                anchor="w",
                height=42,
                fg_color="transparent",
                hover_color=CARD_HOVER,
                text_color=TEXT_MUTED,
                corner_radius=6,
                command=lambda pid=page_id: self._navigate(pid),
            )
            btn.pack(fill="x", padx=14, pady=3)
            self.nav_buttons[page_id] = btn

        # Bottom System Info Badge
        bottom_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom_frame.pack(side="bottom", fill="x", padx=16, pady=16)

        lbl_status_indicator = ctk.CTkLabel(
            bottom_frame,
            text="● Engine Active (SQLite)",
            font=(FONT_BODY[0], 9),
            text_color="#10B981",
            anchor="w",
        )
        lbl_status_indicator.pack(anchor="w")

        lbl_version = ctk.CTkLabel(
            bottom_frame,
            text="v1.0.0 | Production",
            font=(FONT_BODY[0], 9),
            text_color=TEXT_MUTED,
            anchor="w",
        )
        lbl_version.pack(anchor="w")

        # 2. Main Content Frame
        self.content_area = ctk.CTkFrame(self, fg_color=BG_DARK, corner_radius=0)
        self.content_area.grid(row=0, column=1, sticky="nsew")

        # Cache initialized page instances
        self.pages = {
            "dashboard": DashboardPage(self.content_area, self.db_manager, on_navigate=self._navigate),
            "pipeline": PipelinePage(self.content_area, self.config, self.db_manager),
            "current_state": CurrentStatePage(self.content_area, self.db_manager),
            "history": HistoryPage(self.content_area, self.db_manager),
            "quarantine": QuarantinePage(self.content_area, self.db_manager),
            "analytics": AnalyticsPage(self.content_area, self.db_manager),
            "settings": SettingsPage(self.content_area, self.config, self.db_manager),
        }

    def _navigate(self, page_id: str):
        """Switches visible view to specified page."""
        for pid, btn in self.nav_buttons.items():
            if pid == page_id:
                btn.configure(fg_color=CARD_BG, text_color=TEXT_MAIN)
            else:
                btn.configure(fg_color="transparent", text_color=TEXT_MUTED)

        # Hide all pages
        for page in self.pages.values():
            page.pack_forget()

        # Show target page and refresh if supported
        target_page = self.pages.get(page_id)
        if target_page:
            target_page.pack(fill="both", expand=True)
            if hasattr(target_page, "refresh_data"):
                target_page.refresh_data()
            elif hasattr(target_page, "refresh_table"):
                target_page.refresh_table()
            elif hasattr(target_page, "refresh_all"):
                target_page.refresh_all()


def launch_gui():
    """Initializes and runs the desktop interface."""
    app = CDCDataPipelineApp()
    app.mainloop()


if __name__ == "__main__":
    launch_gui()
