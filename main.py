"""
Main Application Entry Point for CDC Data Pipeline Manager.
Supports both Desktop GUI and Command-Line Interface (CLI).
"""
import sys
from pathlib import Path

# Ensure package roots are in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from cli import run_cli

if __name__ == "__main__":
    run_cli()
