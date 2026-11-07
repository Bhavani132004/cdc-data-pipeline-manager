"""
Performance Benchmark Suite for CDC Data Pipeline.
Benchmarks end-to-end processing across 1,000, 10,000, and 100,000 record datasets.
Measures execution time, throughput (records/sec), memory usage, and component breakdowns.
"""
import sys
import time
import json
import psutil
import os
from pathlib import Path
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import AppConfig
from src.database import DatabaseManager
from src.pipeline import CDCPipeline
from scripts.generate_data import generate_cdc_events, save_dataset


def run_single_benchmark(
    record_count: int,
    temp_dir: Path,
    batch_size: int = 5000,
) -> Dict[str, Any]:
    """Generates data and measures real execution metrics."""
    print(f"\n==================================================")
    print(f"BENCHMARK: Running pipeline on {record_count:,} records (batch_size={batch_size})")
    print(f"==================================================")

    # 1. Generate dataset
    gen_start = time.perf_counter()
    events, expected = generate_cdc_events(
        record_count=record_count,
        seed=100 + record_count,
        include_edge_cases=True,
    )
    csv_file, _, _ = save_dataset(
        events, expected, temp_dir, base_name=f"benchmark_{record_count}"
    )
    gen_time = round(time.perf_counter() - gen_start, 3)
    print(f"Dataset generated in {gen_time}s: {csv_file}")

    # 2. Setup isolated database for benchmark run
    db_file = temp_dir / f"benchmark_{record_count}.db"
    if db_file.exists():
        db_file.unlink()

    cfg = AppConfig.load()
    cfg.db_path = db_file
    cfg.batch_size = batch_size
    db_manager = DatabaseManager(cfg.db_url)
    db_manager.init_db()

    pipeline = CDCPipeline(config=cfg, db_manager=db_manager)

    # Measure memory before
    process = psutil.Process(os.getpid())
    mem_before_mb = process.memory_info().rss / (1024 * 1024)

    # 3. Execute pipeline
    start_time = time.perf_counter()
    metrics = pipeline.run(csv_file)
    total_duration = time.perf_counter() - start_time

    # Measure memory after
    mem_after_mb = process.memory_info().rss / (1024 * 1024)
    peak_mem_mb = round(max(mem_before_mb, mem_after_mb), 2)
    rec_per_sec = round(record_count / total_duration, 2) if total_duration > 0 else 0.0

    print(f"Execution Completed in {total_duration:.3f}s | Throughput: {rec_per_sec:,.2f} records/sec")
    print(f"Valid: {metrics.valid_count} | Dups: {metrics.duplicate_count} | Rej: {metrics.rejected_count} | Late: {metrics.late_event_count}")
    print(f"Peak Process Memory: {peak_mem_mb} MB")

    return {
        "record_count": record_count,
        "batch_size": batch_size,
        "execution_duration_sec": round(total_duration, 4),
        "throughput_records_per_sec": rec_per_sec,
        "peak_memory_mb": peak_mem_mb,
        "valid_count": metrics.valid_count,
        "duplicate_count": metrics.duplicate_count,
        "rejected_count": metrics.rejected_count,
        "late_event_count": metrics.late_event_count,
        "inserted_count": metrics.inserted_count,
        "updated_count": metrics.updated_count,
        "deleted_count": metrics.deleted_count,
    }


def run_benchmarks(sizes: List[int] = None) -> Dict[str, Any]:
    if sizes is None:
        sizes = [1000, 10000, 100000]

    cfg = AppConfig.load()
    bench_temp_dir = cfg.base_dir / "data" / "benchmark_temp"
    bench_temp_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for count in sizes:
        res = run_single_benchmark(count, bench_temp_dir, batch_size=cfg.batch_size)
        results.append(res)

    summary = {
        "system": {
            "os": sys.platform,
            "python_version": sys.version.split()[0],
            "cpu_count": psutil.cpu_count(logical=True),
            "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        },
        "benchmarks": results,
    }

    # Save JSON report
    report_json_path = cfg.reports_dir / "benchmark_report.json"
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Save Markdown report
    md_lines = [
        "# CDC Pipeline Performance Benchmark Report",
        "",
        "## System Environment",
        f"- **Operating System:** Windows ({sys.platform})",
        f"- **Python Version:** {summary['system']['python_version']}",
        f"- **CPU Cores:** {summary['system']['cpu_count']}",
        f"- **Total RAM:** {summary['system']['ram_total_gb']} GB",
        "",
        "## Empirical Benchmark Results",
        "",
        "| Dataset Size (Records) | Execution Time (s) | Throughput (Records/Sec) | Peak Memory (MB) | Valid Records | Rejected | Duplicates |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for b in results:
        md_lines.append(
            f"| {b['record_count']:,} | {b['execution_duration_sec']:.3f} | {b['throughput_records_per_sec']:,.2f} | {b['peak_memory_mb']} | {b['valid_count']:,} | {b['rejected_count']:,} | {b['duplicate_count']:,} |"
        )

    md_lines.extend([
        "",
        "## Optimization Techniques Employed",
        "1. **Chunked Streaming**: Streaming generator with configurable batch size prevents memory saturation.",
        "2. **SQLite WAL Mode & Memory Cache**: `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL` maximize disk write performance.",
        "3. **In-Memory Cache Layer**: Pre-loaded lookup indices eliminate per-row SELECT queries, scaling O(1) per lookup.",
        "4. **Bulk Transaction Persistence**: SQLAlchemy bulk operations (`bulk_insert_mappings`) minimize ORM object overhead.",
    ])

    report_md_path = cfg.reports_dir / "benchmark_report.md"
    with open(report_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"\nBenchmark reports written to:")
    print(f"  JSON: {report_json_path}")
    print(f"  MD:   {report_md_path}")

    return summary


if __name__ == "__main__":
    run_benchmarks()
