"""
Run Pipeline Page for CDC Data Pipeline Desktop Application.
Supports file browsing, background execution, real-time progress tracking, and execution summary.
"""
import threading
from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk

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
    FONT_FAMILY,
)
from src.config import AppConfig
from src.database import DatabaseManager
from src.pipeline import CDCPipeline


class PipelinePage(ctk.CTkFrame):
    """File ingestion and pipeline execution interface."""

    def __init__(self, master, config: AppConfig, db_manager: DatabaseManager, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.config = config
        self.db = db_manager
        self.pipeline = CDCPipeline(config=self.config, db_manager=self.db)
        self.is_running = False

        self._build_ui()

    def _build_ui(self):
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=24, pady=(20, 16))

        title = ctk.CTkLabel(header_frame, text="Execute CDC Pipeline", font=FONT_TITLE, text_color=TEXT_MAIN)
        title.pack(side="left")

        # Ingestion Config Card
        card_browse = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        card_browse.pack(fill="x", padx=24, pady=(0, 16))

        lbl_desc = ctk.CTkLabel(
            card_browse,
            text="Select a CSV or JSON file containing CDC events to ingest into the pipeline.",
            font=FONT_BODY,
            text_color=TEXT_MUTED,
        )
        lbl_desc.pack(anchor="w", padx=20, pady=(16, 12))

        # File picker row
        picker_row = ctk.CTkFrame(card_browse, fg_color="transparent")
        picker_row.pack(fill="x", padx=20, pady=(0, 16))

        self.entry_path = ctk.CTkEntry(
            picker_row,
            placeholder_text="Choose file path...",
            font=FONT_BODY,
            fg_color="#181924",
            border_color=BORDER_COLOR,
            text_color=TEXT_MAIN,
            height=36,
        )
        self.entry_path.pack(side="left", fill="x", expand=True, padx=(0, 10))

        # Default to customer_events.csv if present
        default_file = self.config.input_dir / "customer_events.csv"
        if default_file.exists():
            self.entry_path.insert(0, str(default_file))

        btn_browse = ctk.CTkButton(
            picker_row,
            text="Browse File",
            font=FONT_BODY_BOLD,
            width=110,
            height=36,
            fg_color=CARD_BG,
            hover_color=BORDER_COLOR,
            border_width=1,
            border_color=BORDER_COLOR,
            text_color=TEXT_MAIN,
            command=self._on_browse,
        )
        btn_browse.pack(side="left", padx=(0, 10))

        self.btn_run = ctk.CTkButton(
            picker_row,
            text="▶ Start Ingestion",
            font=FONT_BODY_BOLD,
            width=140,
            height=36,
            fg_color=ACCENT_BLUE,
            hover_color="#2563EB",
            text_color=TEXT_MAIN,
            command=self._on_start_pipeline,
        )
        self.btn_run.pack(side="left")

        # Progress Section Card
        self.card_progress = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        self.card_progress.pack(fill="x", padx=24, pady=(0, 16))

        self.lbl_stage = ctk.CTkLabel(
            self.card_progress,
            text="Pipeline Status: Ready",
            font=FONT_BODY_BOLD,
            text_color=TEXT_MAIN,
        )
        self.lbl_stage.pack(anchor="w", padx=20, pady=(16, 8))

        self.prog_bar = ctk.CTkProgressBar(
            self.card_progress,
            orientation="horizontal",
            height=12,
            progress_color=ACCENT_BLUE,
            fg_color="#181924",
        )
        self.prog_bar.pack(fill="x", padx=20, pady=(0, 16))
        self.prog_bar.set(0)

        # Execution Summary Results Card
        self.card_results = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        self.card_results.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        lbl_results_title = ctk.CTkLabel(
            self.card_results,
            text="EXECUTION RUN METRICS",
            font=FONT_SUBTITLE,
            text_color=TEXT_MAIN,
        )
        lbl_results_title.pack(anchor="w", padx=20, pady=(16, 12))

        # Results grid
        self.res_grid = ctk.CTkFrame(self.card_results, fg_color="transparent")
        self.res_grid.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        self.res_grid.grid_columnconfigure((0, 1, 2, 3), weight=1, pad=10)

        self.labels = {}
        fields = [
            ("run_id", "Run ID: -"),
            ("status", "Status: -"),
            ("total_input", "Total Ingested: -"),
            ("valid_count", "Valid Accepted: -"),
            ("inserted_count", "New Inserts: -"),
            ("updated_count", "Updates: -"),
            ("deleted_count", "Soft Deletions: -"),
            ("duplicate_count", "Duplicates Skipped: -"),
            ("rejected_count", "Quarantined Rejections: -"),
            ("late_event_count", "Late / Out-of-Order: -"),
            ("duration", "Execution Duration: -"),
            ("throughput", "Throughput: -"),
        ]

        for i, (key, text) in enumerate(fields):
            row = i // 4
            col = i % 4
            lbl = ctk.CTkLabel(self.res_grid, text=text, font=FONT_BODY, text_color=TEXT_MUTED, anchor="w")
            lbl.grid(row=row, column=col, sticky="w", pady=4)
            self.labels[key] = lbl

    def _on_browse(self):
        f = filedialog.askopenfilename(
            title="Select CDC Event File",
            initialdir=str(self.config.input_dir),
            filetypes=[("CSV & JSON Files", "*.csv *.json *.jsonl"), ("CSV Files", "*.csv"), ("JSON Files", "*.json *.jsonl"), ("All Files", "*.*")],
        )
        if f:
            self.entry_path.delete(0, "end")
            self.entry_path.insert(0, f)

    def _on_start_pipeline(self):
        if self.is_running:
            return

        filepath_str = self.entry_path.get().strip()
        if not filepath_str:
            messagebox.showwarning("Input Required", "Please select or enter an input file path.")
            return

        fpath = Path(filepath_str)
        if not fpath.exists():
            messagebox.showerror("File Not Found", f"Specified file does not exist:\n{fpath}")
            return

        self.is_running = True
        self.btn_run.configure(state="disabled", text="Running...")
        self.prog_bar.set(0)
        self.lbl_stage.configure(text="Pipeline Status: In progress...", text_color=ACCENT_BLUE)

        # Execute in background thread to prevent GUI freezing
        thread = threading.Thread(target=self._run_worker, args=(fpath,), daemon=True)
        thread.start()

    def _run_worker(self, fpath: Path):
        def progress_cb(stage: str, pct: float):
            self.after(0, lambda: self._update_progress(stage, pct))

        try:
            metrics = self.pipeline.run(fpath, progress_callback=progress_cb)
            self.after(0, lambda: self._on_success(metrics))
        except Exception as e:
            self.after(0, lambda: self._on_failure(str(e)))

    def _update_progress(self, stage: str, pct: float):
        self.prog_bar.set(pct)
        self.lbl_stage.configure(text=f"Pipeline Stage: {stage} ({int(pct * 100)}%)")

    def _on_success(self, metrics):
        self.is_running = False
        self.btn_run.configure(state="normal", text="▶ Start Ingestion")
        self.prog_bar.set(1.0)
        self.lbl_stage.configure(
            text=f"Pipeline Status: COMPLETED in {metrics.execution_time_seconds:.3f}s",
            text_color=ACCENT_GREEN,
        )

        self.labels["run_id"].configure(text=f"Run ID: {metrics.run_id}", text_color=TEXT_MAIN)
        self.labels["status"].configure(text=f"Status: {metrics.status}", text_color=ACCENT_GREEN)
        self.labels["total_input"].configure(text=f"Total Ingested: {metrics.total_input:,}")
        self.labels["valid_count"].configure(text=f"Valid Accepted: {metrics.valid_count:,}")
        self.labels["inserted_count"].configure(text=f"New Inserts: {metrics.inserted_count:,}")
        self.labels["updated_count"].configure(text=f"Updates: {metrics.updated_count:,}")
        self.labels["deleted_count"].configure(text=f"Soft Deletions: {metrics.deleted_count:,}")
        self.labels["duplicate_count"].configure(text=f"Duplicates Skipped: {metrics.duplicate_count:,}")
        self.labels["rejected_count"].configure(
            text=f"Quarantined Rejections: {metrics.rejected_count:,}",
            text_color=ACCENT_RED if metrics.rejected_count > 0 else TEXT_MUTED,
        )
        self.labels["late_event_count"].configure(text=f"Late / Out-of-Order: {metrics.late_event_count:,}")
        self.labels["duration"].configure(text=f"Duration: {metrics.execution_time_seconds:.3f}s")
        self.labels["throughput"].configure(text=f"Throughput: {metrics.throughput_records_per_sec:,.2f} rec/s")

    def _on_failure(self, err_msg: str):
        self.is_running = False
        self.btn_run.configure(state="normal", text="▶ Start Ingestion")
        self.lbl_stage.configure(text=f"Pipeline Status: FAILED - {err_msg}", text_color=ACCENT_RED)
        messagebox.showerror("Pipeline Failure", f"Pipeline encountered an error:\n{err_msg}")

