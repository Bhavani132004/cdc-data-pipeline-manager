"""
Configuration Module for CDC Data Pipeline.
Handles directory resolution for both source execution and PyInstaller frozen execution.
"""
import os
import sys
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional


def get_base_dir() -> Path:
    """
    Returns the persistent application base directory.
    If running as a frozen PyInstaller executable, uses the directory of the executable,
    NOT the temporary sys._MEIPASS extraction folder.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent.resolve()
    else:
        # Resolves to project root (parent of 'src')
        return Path(__file__).resolve().parent.parent


@dataclass
class AppConfig:
    """Application configuration container."""
    base_dir: Path
    db_path: Path
    input_dir: Path
    output_dir: Path
    quarantine_dir: Path
    logs_dir: Path
    reports_dir: Path
    batch_size: int = 5000
    db_echo: bool = False
    log_level: str = "INFO"

    @property
    def db_url(self) -> str:
        # SQLite URL with forward slashes
        clean_path = str(self.db_path).replace("\\", "/")
        return f"sqlite:///{clean_path}"

    def ensure_directories(self) -> None:
        """Create necessary directories if they do not exist."""
        for path in [
            self.db_path.parent,
            self.input_dir,
            self.output_dir,
            self.quarantine_dir,
            self.logs_dir,
            self.reports_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> dict:
        return {
            "base_dir": str(self.base_dir),
            "db_path": str(self.db_path),
            "input_dir": str(self.input_dir),
            "output_dir": str(self.output_dir),
            "quarantine_dir": str(self.quarantine_dir),
            "logs_dir": str(self.logs_dir),
            "reports_dir": str(self.reports_dir),
            "batch_size": self.batch_size,
            "db_echo": self.db_echo,
            "log_level": self.log_level,
        }

    def save_settings(self, settings_file: Optional[Path] = None) -> None:
        if settings_file is None:
            settings_file = self.base_dir / "config.json"
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump({
                "batch_size": self.batch_size,
                "log_level": self.log_level,
                "db_path": str(self.db_path),
            }, f, indent=2)

    @classmethod
    def load(cls, custom_base_dir: Optional[Path] = None) -> "AppConfig":
        base = custom_base_dir if custom_base_dir else get_base_dir()
        
        cfg = cls(
            base_dir=base,
            db_path=base / "database" / "cdc_pipeline.db",
            input_dir=base / "data" / "input",
            output_dir=base / "data" / "output",
            quarantine_dir=base / "data" / "quarantine",
            logs_dir=base / "logs",
            reports_dir=base / "reports",
            batch_size=5000,
            db_echo=False,
            log_level="INFO",
        )
        cfg.ensure_directories()

        # Check for user overrides
        settings_file = base / "config.json"
        if settings_file.exists():
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "batch_size" in data:
                        cfg.batch_size = int(data["batch_size"])
                    if "log_level" in data:
                        cfg.log_level = str(data["log_level"]).upper()
                    if "db_path" in data and data["db_path"]:
                        cfg.db_path = Path(data["db_path"])
            except Exception:
                pass  # Fallback to defaults

        return cfg
