"""
Command-Line Interface (CLI) for CDC Data Pipeline Manager.
Supports ingestion, synthetic data generation, automated testing, reconciliation, and reporting.
"""
import sys
import argparse
import subprocess
from pathlib import Path

from src.config import AppConfig
from src.database import DatabaseManager
from src.pipeline import CDCPipeline
from src.reporting import ReportingService
from scripts.generate_data import generate_cdc_events, save_dataset
from scripts.reconcile import ReconciliationChecker


def print_banner():
    banner = r"""
========================================================================
   CDC DATA PIPELINE MANAGER - Change Data Capture & Audit Engine
========================================================================
"""
    print(banner)


def handle_generate(count: int, config: AppConfig):
    print(f"[*] Generating {count:,} synthetic CDC event records...")
    events, expected = generate_cdc_events(
        record_count=count,
        seed=42,
        include_edge_cases=True,
    )
    csv_file, json_file, exp_file = save_dataset(
        events, expected, config.input_dir, base_name="customer_events"
    )
    print(f"[+] Successfully generated {len(events):,} events:")
    print(f"    - CSV:      {csv_file}")
    print(f"    - JSON:     {json_file}")
    print(f"    - Expected: {exp_file}")


def handle_input(filepath_str: str, config: AppConfig):
    filepath = Path(filepath_str)
    if not filepath.is_absolute():
        filepath = (config.base_dir / filepath).resolve()

    if not filepath.exists():
        print(f"[!] Error: File not found at {filepath}")
        sys.exit(1)

    print(f"[*] Executing CDC Pipeline on input file: {filepath}")
    pipeline = CDCPipeline(config=config)

    def on_progress(stage: str, pct: float):
        print(f"  --> [{int(pct * 100):3d}%] {stage}")

    metrics = pipeline.run(filepath, progress_callback=on_progress)

    print("\n" + "=" * 60)
    print(f"PIPELINE RUN SUMMARY: {metrics.run_id}")
    print("=" * 60)
    print(f"  Status:             {metrics.status}")
    print(f"  Source File:        {metrics.source_file}")
    print(f"  Total Input:        {metrics.total_input:,}")
    print(f"  Valid Events:       {metrics.valid_count:,}")
    print(f"  Inserted Customers: {metrics.inserted_count:,}")
    print(f"  Updated Customers:  {metrics.updated_count:,}")
    print(f"  Deleted Customers:  {metrics.deleted_count:,}")
    print(f"  Duplicate Events:   {metrics.duplicate_count:,}")
    print(f"  Rejected Records:   {metrics.rejected_count:,}")
    print(f"  Late-Arriving:      {metrics.late_event_count:,}")
    print(f"  Execution Duration: {metrics.execution_time_seconds:.3f} seconds")
    print(f"  Throughput:         {metrics.throughput_records_per_sec:,.2f} records/sec")
    print("=" * 60)
    if metrics.error_message:
        print(f"[!] Error message: {metrics.error_message}")


def handle_test(config: AppConfig):
    print("[*] Running Pytest test suite...")
    test_path = config.base_dir / "tests"
    cmd = [sys.executable, "-m", "pytest", str(test_path), "-v"]
    result = subprocess.run(cmd, cwd=str(config.base_dir))
    sys.exit(result.returncode)


def handle_report(config: AppConfig):
    print("[*] Generating Operational & Pipeline Summary Report...")
    db_mgr = DatabaseManager(config.db_url)
    db_mgr.init_db()
    reporting = ReportingService(db_mgr, config)
    metrics = db_mgr.get_summary_metrics()

    print("\n" + "=" * 60)
    print("CDC PIPELINE DATABASE SUMMARY")
    print("=" * 60)
    print(f"  Active Customers:        {metrics['active_customers']:,}")
    print(f"  Deleted Customers:       {metrics['deleted_customers']:,}")
    print(f"  Total Current Customers: {metrics['total_customers']:,}")
    print(f"  Total Historical Events: {metrics['total_history']:,}")
    print(f"  Total Rejected Records:  {metrics['total_rejected']:,}")
    print(f"  Total Duplicates Skipped:{metrics['total_duplicates']:,}")
    print(f"  Total Late Events:       {metrics['total_late_events']:,}")
    print("=" * 60)

    # Save summary report to reports/summary_report.md
    summary_file = config.reports_dir / "summary_report.md"
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write("# CDC Pipeline Database Summary Report\n\n")
        f.write(f"- **Active Customers:** {metrics['active_customers']:,}\n")
        f.write(f"- **Deleted Customers:** {metrics['deleted_customers']:,}\n")
        f.write(f"- **Total Current Records:** {metrics['total_customers']:,}\n")
        f.write(f"- **Total Historical Audit Events:** {metrics['total_history']:,}\n")
        f.write(f"- **Total Quarantined Rejections:** {metrics['total_rejected']:,}\n")
        f.write(f"- **Total Skipped Duplicates:** {metrics['total_duplicates']:,}\n")
    print(f"[+] Saved summary report to {summary_file}")


def handle_reset_demo(config: AppConfig):
    print("[*] Resetting database and generating fresh demo dataset...")
    db_mgr = DatabaseManager(config.db_url)
    db_mgr.reset_db()
    print("[+] Database tables cleared and re-initialized.")

    # Generate 50 sample events
    events, expected = generate_cdc_events(record_count=50, seed=42, include_edge_cases=True)
    csv_file, _, _ = save_dataset(events, expected, config.input_dir, base_name="customer_events")
    print(f"[+] Generated starter sample file: {csv_file}")

    # Run the pipeline on the sample file
    print("[*] Processing starter sample file through CDC pipeline...")
    pipeline = CDCPipeline(config=config, db_manager=db_mgr)
    metrics = pipeline.run(csv_file)
    print(f"[+] Demo pipeline executed successfully! Run ID: {metrics.run_id}")
    print(f"    - Input: {metrics.total_input} | Valid: {metrics.valid_count} | Duplicates: {metrics.duplicate_count} | Rejected: {metrics.rejected_count}")


def handle_reconcile(config: AppConfig):
    print("[*] Running automated reconciliation and data quality audit...")
    from scripts.reconcile import run_reconciliation
    success = run_reconciliation()
    sys.exit(0 if success else 1)


def handle_benchmark(config: AppConfig):
    print("[*] Running performance benchmark suite...")
    from scripts.benchmark import run_benchmarks
    run_benchmarks()


def run_cli():
    print_banner()
    config = AppConfig.load()

    parser = argparse.ArgumentParser(
        description="CDC Data Pipeline Manager - High-Performance CDC Processing Engine",
    )
    parser.add_argument("--input", type=str, help="Process a CSV or JSON input file.")
    parser.add_argument("--generate", type=int, nargs="?", const=100000, help="Generate synthetic CDC events (default 100,000).")
    parser.add_argument("--test", action="store_true", help="Execute automated test suite.")
    parser.add_argument("--report", action="store_true", help="Display operational metrics and export summary.")
    parser.add_argument("--reset-demo", action="store_true", help="Reset database and generate fresh starter demo dataset.")
    parser.add_argument("--reconcile", action="store_true", help="Execute reconciliation and data quality checks.")
    parser.add_argument("--benchmark", action="store_true", help="Run empirical performance benchmarks.")
    parser.add_argument("--gui", action="store_true", help="Launch the Desktop GUI application.")

    args = parser.parse_args()

    if args.generate:
        handle_generate(args.generate, config)
    elif args.input:
        handle_input(args.input, config)
    elif args.test:
        handle_test(config)
    elif args.report:
        handle_report(config)
    elif args.reset_demo:
        handle_reset_demo(config)
    elif args.reconcile:
        handle_reconcile(config)
    elif args.benchmark:
        handle_benchmark(config)
    elif args.gui or len(sys.argv) == 1:
        # Launch GUI if requested or if no arguments provided
        from gui.app import launch_gui
        launch_gui()
    else:
        parser.print_help()


if __name__ == "__main__":
    run_cli()
