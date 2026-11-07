"""
Logging Setup for CDC Data Pipeline.
Provides dual logging to file and standard output with consistent formatting.
"""
import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str = "cdc_pipeline",
    log_dir: Optional[Path] = None,
    log_level: str = "INFO",
    console_output: bool = True,
) -> logging.Logger:
    """Configures and returns a logger instance."""
    logger = logging.getLogger(name)
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)

    # Avoid duplicate handlers if setup_logger is called repeatedly
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | [%(name)s:%(funcName)s:%(lineno)d] | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        logger.addHandler(console_handler)

    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(
            filename=log_dir / "pipeline.log",
            encoding="utf-8",
            mode="a",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)

    return logger
