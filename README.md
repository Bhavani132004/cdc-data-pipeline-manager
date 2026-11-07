# CDC Data Pipeline Manager

> **Change Data Capture Pipeline with Historical Tracking, Duplicate Detection, Idempotent Processing, and Data Quality Monitoring**

A production-grade, autonomous Data Engineering pipeline designed to process high-throughput customer change streams (`INSERT`, `UPDATE`, `DELETE`), maintain authoritative state, preserve immutable historical audit trails, isolate data quality violations into quarantine, and provide real-time monitoring via a modern desktop dashboard and CLI.

---

## 1. Business Problem & Solution

Enterprise systems constantly receive operational updates from CRM, ERP, and customer microservices. In real-world data pipelines, event streams suffer from:
- **Duplicate records** resulting from network retries and distributed producer restarts.
- **Out-of-order and late-arriving events** caused by distributed network latency.
- **Malformed payloads, unexpected schema drifts, and negative values**.
- **Orphan updates or deletions** for non-existent customer entities.
- **Accidental reactivation** of soft-deleted customers by delayed events.

The **CDC Data Pipeline Manager** solves these challenges through deterministic version evaluation, cryptographic canonical payload hashing, atomic batch transactions, automated quarantine isolation, and an integrated reconciliation audit engine.

---

## 2. Key Features

- **Authoritative Current State Management**: Maintains `current_customers` with the latest attributes, state version, and soft-deletion flags.
- **Immutable Historical Audit Log**: Preserves all unique events in `customer_history` with provenance tracking (`run_id`, `source_file`, `payload_hash`, `event_status`).
- **Cryptographic Deduplication & Idempotency**: Identical events are safely skipped with zero state mutations; rerunning the exact same file produces 0 unintended side-effects.
- **Conflicting Event Quarantine**: Rejects duplicate event IDs with divergent payloads and routes them to `rejected_records`.
- **Deterministic Out-of-Order Resolution**: Primary ordering by record version, secondary tie-breaking by ISO-8601 timestamps and lexicographical ID sorting.
- **High-Throughput Streaming**: Chunked generator processing enables ingestion of **100,000+ records in ~42 seconds** (>2,300 records/sec) with memory usage under 300MB.
- **Automated Data Quality & Reconciliation Audit**: Performs 7 automated integrity checks, including conservation of event counts ($Input = Valid + Duplicates + Rejected$).
- **Modern Desktop GUI**: Built with CustomTkinter and embedded Matplotlib visual analytics.
- **Dual Execution Modes**: Seamlessly run via Desktop Dashboard or headless CLI.
- **Standalone Windows Executable**: Bundled with PyInstaller for zero-dependency deployment on Windows 10/11.

---

## 3. Technology Stack

- **Runtime:** Python 3.10 / 3.11 / 3.12
- **Database & ORM:** SQLite 3 with Write-Ahead Logging (WAL) and SQLAlchemy 2.0
- **Data Manipulation:** Pandas 2.x
- **Testing:** Pytest (23 automated test scenarios)
- **GUI Framework:** CustomTkinter + Matplotlib (TkAgg canvas backend)
- **Packaging:** PyInstaller 6.x
- **Monitoring:** Psutil process memory and CPU tracking

---

## 4. Architecture Overview

```
SOURCE DATA (CSV / JSON)
        │
        ▼
   DATA INGESTION (Chunked Streaming & SHA-256 File Checksum)
        │
        ▼
   SCHEMA & BUSINESS VALIDATION (Field Types, Salary >= 0, Operations)
        │
        ▼
   DEDUPLICATION & IDEMPOTENCY (Canonical SHA-256 Payload Hashing)
        │
        ▼
   VERSION & OUT-OF-ORDER CHECK (Version Evaluation & Tie-Breaking Policy)
        │
        ├────────────────────────┬────────────────────────┐
        ▼                        ▼                        ▼
  CURRENT STATE          AUDIT HISTORY            QUARANTINE
 (current_customers)   (customer_history)     (rejected_records)
```

---

## 5. Performance Benchmark Results

Empirically verified on Windows 10/11 (Python 3.10, SQLite WAL, batch size 5,000):

| Dataset Size | Wall-Clock Time | Ingestion Throughput | Peak Process RAM | Valid Events | Quarantined | Skipped Dups |
|---:|---:|---:|---:|---:|---:|---:|
| **1,000 records** | **0.379 s** | **2,636 records/sec** | 99.1 MB | 935 | 72 | 1 |
| **10,000 records** | **3.872 s** | **2,582 records/sec** | 125.1 MB | 9,402 | 605 | 1 |
| **100,000 records** | **42.032 s** | **2,379 records/sec** | 289.4 MB | 94,180 | 5,827 | 1 |

*All metrics are verified from actual pipeline execution runs.*

---

## 6. Installation & Setup

### Prerequisites
- Python 3.10+ installed on Windows, Linux, or macOS.

### Installation
```bash
# Clone or navigate to the project directory
cd cdc_data_pipeline

# Install required dependencies
pip install -r requirements.txt
```

---

## 7. Execution Instructions

### Running the Desktop GUI
Launch the visual interactive desktop application:
```bash
python main.py --gui
# or simply
python main.py
```

### Running the CLI
The command-line interface shares the exact same core pipeline modules:

```bash
# Ingest an external CSV or JSON file
python main.py --input data/input/customer_events.csv

# Generate 100,000 synthetic records with edge cases
python main.py --generate 100000

# Execute the 23 automated Pytest scenarios
python main.py --test

# Display database operational summary report
python main.py --report

# Reset database and seed fresh starter sample records
python main.py --reset-demo

# Run automated 7-point reconciliation and data quality audit
python main.py --reconcile

# Run performance benchmarks (1k, 10k, 100k records)
python main.py --benchmark
```

---

## 8. Automated Testing

The automated test suite verifies 23 distinct scenarios using isolated temporary SQLite databases:

```bash
pytest tests/ -v
```

### Test Coverage Checklist
1. `test_01_insert_operation` - Valid INSERT creates customer state and history record.
2. `test_02_update_operation` - Valid UPDATE modifies name, city, salary, version.
3. `test_03_delete_operation` - Soft deletion marks `is_deleted = True`.
4. `test_04_empty_input` - Gracefully handles empty (0 byte) files.
5. `test_05_missing_customer_id` - Quarantines records with missing customer ID.
6. `test_06_missing_event_id` - Quarantines records with missing event ID.
7. `test_07_invalid_operation` - Quarantines unsupported operations.
8. `test_08_invalid_salary` - Quarantines negative or non-numeric salaries.
9. `test_09_duplicate_event` - Idempotently skips identical duplicate events.
10. `test_10_conflicting_event_id` - Quarantines conflicting duplicate payloads.
11. `test_11_out_of_order_event` - Superseded older version preserved in history without mutating state.
12. `test_12_late_arriving_event` - Late event correctly categorized and tracked.
13. `test_13_update_before_insert` - Quarantines orphan UPDATE on non-existent customer.
14. `test_14_delete_before_older_update` - Prevents older updates from reactivating soft-deleted records.
15. `test_15_invalid_customer_reference` - Quarantines DELETE on non-existent customer.
16. `test_16_unexpected_schema` - Quarantines malformed dictionary records.
17. `test_17_same_file_rerun` - Idempotent rerun produces 0 mutations and counts duplicates.
18. `test_18_same_event_different_files` - Cross-file duplicate event skipped safely.
19. `test_19_partial_failure_and_retry` - Partial failures quarantined without corrupting valid rows.
20. `test_20_database_integrity` - Enforces NOT NULL and non-negative constraints.
21. `test_21_history_completeness` - Preserves all valid lifecycle transitions in audit log.
22. `test_22_current_state_correctness` - Verifies latest attributes and event pointers.
23. `test_23_large_dataset_execution` - Validates streaming batching over multi-thousand records.

---

## 9. Building the Windows Executable (.EXE)

The application can be packaged into a standalone Windows executable using PyInstaller.

### Automated Build Script
Run the provided Windows batch script:
```cmd
build_exe.bat
```

### Manual PyInstaller Command
```cmd
pyinstaller cdc_pipeline.spec --clean
```

The resulting binary will be created at:
```
dist/CDC_Data_Pipeline_Manager/CDC_Data_Pipeline_Manager.exe
```

---

## 10. Project Directory Structure

```
cdc_data_pipeline/
│
├── src/
│   ├── __init__.py
│   ├── config.py           # Path resolution & environment management
│   ├── logger.py           # Structured dual-handler logging
│   ├── database.py         # SQLAlchemy models & connection pooling
│   ├── ingestion.py        # Streaming CSV/JSON chunk reader
│   ├── validation.py       # Schema & business rule validators
│   ├── deduplication.py    # Canonical payload hashing & duplicate checker
│   ├── transformation.py   # State transitions & out-of-order tie breaking
│   ├── pipeline.py         # Transactional pipeline orchestrator
│   ├── metrics.py          # Real-time metrics & memory profiling
│   └── reporting.py        # Tabular queries & CSV export service
│
├── gui/
│   ├── __init__.py
│   ├── theme.py            # Professional modern dark theme palette
│   ├── components.py       # Reusable KPI cards & styled Treeviews
│   ├── app.py              # CustomTkinter master window & navigation
│   ├── dashboard.py        # Page 1: Executive KPI Dashboard
│   ├── pipeline_page.py    # Page 2: Run Pipeline & Live Progress
│   ├── current_state_page.py # Page 3: Current State View & CSV Export
│   ├── history_page.py     # Page 4: Complete Event Audit History
│   ├── quarantine_page.py  # Page 5: Quarantine & Anomaly Browser
│   ├── analytics_page.py   # Page 6: Matplotlib Analytics & Reconciliation
│   └── settings_page.py    # Page 7: Performance Tuning & DB Reset
│
├── tests/
│   ├── __init__.py
│   └── test_pipeline.py    # 23 automated Pytest test cases
│
├── data/
│   ├── input/              # Source CSV / JSON event files
│   ├── output/             # Exported CSV tables
│   └── quarantine/         # Run-specific quarantine CSV exports
│
├── database/               # Local persistent SQLite database file
├── reports/                # Benchmark, reconciliation, and summary reports
├── logs/                   # Rotating pipeline execution log files
├── scripts/
│   ├── generate_data.py    # Synthetic event stream generator
│   ├── reconcile.py        # 7-point reconciliation audit engine
│   └── benchmark.py        # Multi-scale performance benchmark suite
│
├── docs/
│   ├── data_dictionary.md  # Detailed schema, constraints, and business rules
│   ├── architecture.md     # Architecture diagram and processing flow
│   └── design_tradeoffs.md # Engineering decisions and cloud scalability
│
├── main.py                 # Primary entry point (GUI / CLI)
├── cli.py                  # CLI argument parser and commands
├── requirements.txt        # Python dependency manifest
├── pytest.ini              # Pytest configuration
├── build_exe.bat           # Windows binary build script
└── cdc_pipeline.spec       # PyInstaller packaging specification
```

---

## 11. Known Limitations & Future Roadmap

- **Single Node Engine**: Optimized for single-node machines using SQLite. For petabyte-scale distributed ingestion, the transformation logic maps directly to Apache Spark / Delta Lake or Apache Flink.
- **Synchronous Ingestion UI**: While GUI background threads prevent UI lockup during ingestion, future versions can incorporate a decoupled background worker service (Celery / RQ).
