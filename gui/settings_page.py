"""
Settings Page for CDC Data Pipeline Desktop Application.
Displays and manages paths, batch size configs, database resets, and application information.
"""
import sys
import sqlite3
from pathlib import Path
from tkinter import messagebox
import customtkinter as ctk

from .theme import (
    CARD_BG,
    BORDER_COLOR,
    TEXT_MAIN,
    TEXT_MUTED,
    ACCENT_BLUE,
    ACCENT_RED,
    ACCENT_GREEN,
    FONT_TITLE,
    FONT_SUBTITLE,
    FONT_BODY,
    FONT_BODY_BOLD,
)
from src.config import AppConfig
from src.database import DatabaseManager
from scripts.generate_data import generate_cdc_events, save_dataset


class SettingsPage(ctk.CTkFrame):
    """Configuration management, directory paths, and database reset tools."""

    def __init__(self, master, config: AppConfig, db_manager: DatabaseManager, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.config = config
        self.db = db_manager

        self._build_ui()

    def _build_ui(self):
        # Header Row
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=24, pady=(20, 14))

        title = ctk.CTkLabel(header_frame, text="Pipeline Settings & Diagnostics", font=FONT_TITLE, text_color=TEXT_MAIN)
        title.pack(side="left")

        # Scrollable container for settings
        container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        # Card 1: Storage Paths
        card_paths = ctk.CTkFrame(container, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        card_paths.pack(fill="x", pady=(0, 16))

        lbl_paths = ctk.CTkLabel(card_paths, text="STORAGE & DIRECTORIES", font=FONT_SUBTITLE, text_color=TEXT_MAIN)
        lbl_paths.pack(anchor="w", padx=20, pady=(16, 12))

        paths_info = [
            ("Database Path:", str(self.config.db_path)),
            ("Input Directory:", str(self.config.input_dir)),
            ("Output Directory:", str(self.config.output_dir)),
            ("Quarantine Directory:", str(self.config.quarantine_dir)),
            ("Logs Directory:", str(self.config.logs_dir)),
            ("Reports Directory:", str(self.config.reports_dir)),
        ]

        for label_text, val in paths_info:
            row = ctk.CTkFrame(card_paths, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=3)
            ctk.CTkLabel(row, text=label_text, font=FONT_BODY_BOLD, text_color=TEXT_MAIN, width=160, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=val, font=FONT_BODY, text_color=TEXT_MUTED, anchor="w").pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(card_paths, text="", height=8).pack()

        # Card 2: Pipeline Tuning
        card_tuning = ctk.CTkFrame(container, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        card_tuning.pack(fill="x", pady=(0, 16))

        lbl_tune = ctk.CTkLabel(card_tuning, text="PERFORMANCE & BATCH SETTINGS", font=FONT_SUBTITLE, text_color=TEXT_MAIN)
        lbl_tune.pack(anchor="w", padx=20, pady=(16, 12))

        batch_row = ctk.CTkFrame(card_tuning, fg_color="transparent")
        batch_row.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(batch_row, text="Chunk Batch Size:", font=FONT_BODY_BOLD, text_color=TEXT_MAIN, width=160, anchor="w").pack(side="left")

        self.entry_batch = ctk.CTkEntry(
            batch_row,
            width=120,
            height=32,
            font=FONT_BODY,
            fg_color="#181924",
            border_color=BORDER_COLOR,
            text_color=TEXT_MAIN,
        )
        self.entry_batch.insert(0, str(self.config.batch_size))
        self.entry_batch.pack(side="left", padx=(0, 10))

        btn_save = ctk.CTkButton(
            batch_row,
            text="Save Settings",
            width=110,
            height=32,
            font=FONT_BODY_BOLD,
            fg_color=ACCENT_BLUE,
            command=self._on_save_settings,
        )
        btn_save.pack(side="left")

        ctk.CTkLabel(card_tuning, text="", height=8).pack()

        # Card 3: Administrative & Demo Tools
        card_admin = ctk.CTkFrame(container, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        card_admin.pack(fill="x", pady=(0, 16))

        lbl_admin = ctk.CTkLabel(card_admin, text="ADMINISTRATIVE & DEMO TOOLS", font=FONT_SUBTITLE, text_color=TEXT_MAIN)
        lbl_admin.pack(anchor="w", padx=20, pady=(16, 12))

        btn_box = ctk.CTkFrame(card_admin, fg_color="transparent")
        btn_box.pack(fill="x", padx=20, pady=(0, 16))

        btn_demo = ctk.CTkButton(
            btn_box,
            text="↻ Reset Database & Seed Demo Data",
            font=FONT_BODY_BOLD,
            fg_color=ACCENT_RED,
            hover_color="#DC2626",
            command=self._on_reset_database,
        )
        btn_demo.pack(side="left", padx=(0, 12))

        btn_gen100 = ctk.CTkButton(
            btn_box,
            text="+ Generate 1,000 Records",
            font=FONT_BODY_BOLD,
            fg_color=CARD_BG,
            hover_color=BORDER_COLOR,
            border_width=1,
            border_color=BORDER_COLOR,
            text_color=TEXT_MAIN,
            command=lambda: self._on_generate_sample(1000),
        )
        btn_gen100.pack(side="left")

        # Card 4: Application Diagnostics & Version Info
        card_diag = ctk.CTkFrame(container, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        card_diag.pack(fill="x", pady=(0, 20))

        lbl_diag = ctk.CTkLabel(card_diag, text="APPLICATION DIAGNOSTICS", font=FONT_SUBTITLE, text_color=TEXT_MAIN)
        lbl_diag.pack(anchor="w", padx=20, pady=(16, 12))

        diag_items = [
            ("Application Title:", "CDC Data Pipeline Manager v1.0.0"),
            ("Python Runtime:", sys.version.split()[0]),
            ("SQLite Backend Version:", sqlite3.sqlite_version),
            ("Platform Operating System:", sys.platform),
            ("Execution Mode:", "Frozen Executable" if getattr(sys, "frozen", False) else "Source Development"),
        ]

        for k, v in diag_items:
            row = ctk.CTkFrame(card_diag, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=3)
            ctk.CTkLabel(row, text=k, font=FONT_BODY_BOLD, text_color=TEXT_MAIN, width=200, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=v, font=FONT_BODY, text_color=TEXT_MUTED, anchor="w").pack(side="left")

        ctk.CTkLabel(card_diag, text="", height=8).pack()

    def _on_save_settings(self):
        try:
            new_batch = int(self.entry_batch.get().strip())
            if new_batch <= 0:
                raise ValueError("Batch size must be positive")
            self.config.batch_size = new_batch
            self.config.save_settings()
            messagebox.showinfo("Settings Saved", f"Batch size updated to {new_batch:,}.")
        except Exception as e:
            messagebox.showerror("Invalid Input", f"Please enter a valid positive integer:\n{str(e)}")

    def _on_reset_database(self):
        confirm = messagebox.askyesno(
            "Confirm Database Reset",
            "Are you sure you want to completely reset the SQLite database?\n"
            "This drops all current customers, history, quarantine, and run logs, and seeds fresh starter demo events.",
        )
        if confirm:
            self.db.reset_db()
            events, exp = generate_cdc_events(record_count=50, seed=42, include_edge_cases=True)
            save_dataset(events, exp, self.config.input_dir, base_name="customer_events")
            messagebox.showinfo("Database Reset", "Database successfully reset and seeded with fresh demo events!")

    def _on_generate_sample(self, count: int):
        events, exp = generate_cdc_events(record_count=count, seed=123, include_edge_cases=True)
        csv_file, _, _ = save_dataset(events, exp, self.config.input_dir, base_name=f"customer_events_{count}")
        messagebox.showinfo("Dataset Generated", f"Successfully generated {count:,} events at:\n{csv_file}")
