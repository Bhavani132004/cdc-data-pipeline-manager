"""
Automated Pytest Suite for CDC Data Pipeline.
Covers all 23 required test scenarios from Phase 9.
"""
import pytest
import json
import csv
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta

from src.config import AppConfig
from src.database import (
    DatabaseManager,
    CurrentCustomer,
    CustomerHistory,
    RejectedRecord,
    PipelineRun,
    ProcessedFile,
)
from src.pipeline import CDCPipeline
from scripts.generate_data import generate_cdc_events, save_dataset


@pytest.fixture
def test_env(tmp_path):
    """Provides an isolated test environment with temporary database and folders."""
    cfg = AppConfig(
        base_dir=tmp_path,
        db_path=tmp_path / "test_cdc.db",
        input_dir=tmp_path / "data" / "input",
        output_dir=tmp_path / "data" / "output",
        quarantine_dir=tmp_path / "data" / "quarantine",
        logs_dir=tmp_path / "logs",
        reports_dir=tmp_path / "reports",
        batch_size=500,
        db_echo=False,
    )
    cfg.ensure_directories()
    db_mgr = DatabaseManager(cfg.db_url)
    db_mgr.init_db()
    pipeline = CDCPipeline(config=cfg, db_manager=db_mgr)
    return cfg, db_mgr, pipeline


def create_csv(tmp_path: Path, rows: list, filename: str = "test.csv") -> Path:
    fpath = tmp_path / filename
    if not rows:
        fpath.touch()
        return fpath
    with open(fpath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return fpath


# 1. Test INSERT
def test_01_insert_operation(test_env, tmp_path):
    cfg, db_mgr, pipeline = test_env
    row = {
        "event_id": "EVT-100",
        "customer_id": "C-1",
        "operation": "INSERT",
        "name": "Alice Smith",
        "city": "Boston",
        "salary": "75000.00",
        "version": "1",
        "event_timestamp": "2026-11-01T10:00:00Z",
    }
    csv_file = create_csv(tmp_path, [row])
    metrics = pipeline.run(csv_file)

    assert metrics.inserted_count == 1
    assert metrics.valid_count == 1
    with db_mgr.session_scope() as session:
        cust = session.get(CurrentCustomer, "C-1")
        assert cust is not None
        assert cust.name == "Alice Smith"
        assert cust.salary == 75000.0
        assert cust.version == 1
        assert cust.is_deleted is False


# 2. Test UPDATE
def test_02_update_operation(test_env, tmp_path):
    cfg, db_mgr, pipeline = test_env
    rows = [
        {"event_id": "E-1", "customer_id": "C-2", "operation": "INSERT", "name": "Bob", "city": "NYC", "salary": "50000", "version": "1", "event_timestamp": "2026-11-01T10:00:00Z"},
        {"event_id": "E-2", "customer_id": "C-2", "operation": "UPDATE", "name": "Bob Vance", "city": "Austin", "salary": "60000", "version": "2", "event_timestamp": "2026-11-01T11:00:00Z"},
    ]
    csv_file = create_csv(tmp_path, rows)
    metrics = pipeline.run(csv_file)

    assert metrics.inserted_count == 1
    assert metrics.updated_count == 1
    with db_mgr.session_scope() as session:
        cust = session.get(CurrentCustomer, "C-2")
        assert cust.name == "Bob Vance"
        assert cust.city == "Austin"
        assert cust.salary == 60000.0
        assert cust.version == 2


# 3. Test DELETE (Soft Deletion)
def test_03_delete_operation(test_env, tmp_path):
    cfg, db_mgr, pipeline = test_env
    rows = [
        {"event_id": "E-1", "customer_id": "C-3", "operation": "INSERT", "name": "Charlie", "city": "Denver", "salary": "70000", "version": "1", "event_timestamp": "2026-11-01T10:00:00Z"},
        {"event_id": "E-2", "customer_id": "C-3", "operation": "DELETE", "name": "", "city": "", "salary": "", "version": "2", "event_timestamp": "2026-11-01T12:00:00Z"},
    ]
    csv_file = create_csv(tmp_path, rows)
    metrics = pipeline.run(csv_file)

    assert metrics.deleted_count == 1
    with db_mgr.session_scope() as session:
        cust = session.get(CurrentCustomer, "C-3")
        assert cust.is_deleted is True
        assert cust.version == 2


# 4. Test Empty Input
def test_04_empty_input(test_env, tmp_path):
    cfg, db_mgr, pipeline = test_env
    csv_file = create_csv(tmp_path, [], "empty.csv")
    metrics = pipeline.run(csv_file)

    assert metrics.total_input == 0
    assert metrics.status == "COMPLETED"


# 5. Test Missing Customer ID
def test_05_missing_customer_id(test_env, tmp_path):
    cfg, db_mgr, pipeline = test_env
    row = {"event_id": "E-5", "customer_id": "", "operation": "INSERT", "name": "No ID", "city": "NYC", "salary": "50000", "version": "1", "event_timestamp": "2026-11-01T10:00:00Z"}
    csv_file = create_csv(tmp_path, [row])
    metrics = pipeline.run(csv_file)

    assert metrics.rejected_count == 1
    with db_mgr.session_scope() as session:
        rejs = session.query(RejectedRecord).all()
        assert len(rejs) == 1
        assert "MISSING_CUSTOMER_ID" in rejs[0].rejection_reason


# 6. Test Missing Event ID
def test_06_missing_event_id(test_env, tmp_path):
    cfg, db_mgr, pipeline = test_env
    row = {"event_id": "", "customer_id": "C-6", "operation": "INSERT", "name": "No Event ID", "city": "NYC", "salary": "50000", "version": "1", "event_timestamp": "2026-11-01T10:00:00Z"}
    csv_file = create_csv(tmp_path, [row])
    metrics = pipeline.run(csv_file)

    assert metrics.rejected_count == 1
    with db_mgr.session_scope() as session:
        rejs = session.query(RejectedRecord).all()
        assert "MISSING_EVENT_ID" in rejs[0].rejection_reason


# 7. Test Invalid Operation
def test_07_invalid_operation(test_env, tmp_path):
    cfg, db_mgr, pipeline = test_env
    row = {"event_id": "E-7", "customer_id": "C-7", "operation": "PURGE", "name": "Dan", "city": "Miami", "salary": "50000", "version": "1", "event_timestamp": "2026-11-01T10:00:00Z"}
    csv_file = create_csv(tmp_path, [row])
    metrics = pipeline.run(csv_file)

    assert metrics.rejected_count == 1
    with db_mgr.session_scope() as session:
        rej = session.query(RejectedRecord).first()
        assert "INVALID_OPERATION" in rej.rejection_reason


# 8. Test Invalid Salary
def test_08_invalid_salary(test_env, tmp_path):
    cfg, db_mgr, pipeline = test_env
    row = {"event_id": "E-8", "customer_id": "C-8", "operation": "INSERT", "name": "Eve", "city": "Dallas", "salary": "-1000", "version": "1", "event_timestamp": "2026-11-01T10:00:00Z"}
    csv_file = create_csv(tmp_path, [row])
    metrics = pipeline.run(csv_file)

    assert metrics.rejected_count == 1
    with db_mgr.session_scope() as session:
        rej = session.query(RejectedRecord).first()
        assert "INVALID_SALARY" in rej.rejection_reason


# 9. Test Duplicate Event (Exact)
def test_09_duplicate_event(test_env, tmp_path):
    cfg, db_mgr, pipeline = test_env
    row = {"event_id": "E-9", "customer_id": "C-9", "operation": "INSERT", "name": "Frank", "city": "Chicago", "salary": "60000", "version": "1", "event_timestamp": "2026-11-01T10:00:00Z"}
    # Sent twice in same batch
    csv_file = create_csv(tmp_path, [row, dict(row)])
    metrics = pipeline.run(csv_file)

    assert metrics.inserted_count == 1
    assert metrics.duplicate_count == 1
    assert metrics.valid_count == 1


# 10. Test Conflicting Duplicate Event ID
def test_10_conflicting_event_id(test_env, tmp_path):
    cfg, db_mgr, pipeline = test_env
    row1 = {"event_id": "E-10", "customer_id": "C-10", "operation": "INSERT", "name": "Grace", "city": "Seattle", "salary": "70000", "version": "1", "event_timestamp": "2026-11-01T10:00:00Z"}
    row2 = {"event_id": "E-10", "customer_id": "C-10", "operation": "INSERT", "name": "Grace Conflicting", "city": "Seattle", "salary": "99999", "version": "1", "event_timestamp": "2026-11-01T10:00:00Z"}
    csv_file = create_csv(tmp_path, [row1, row2])
    metrics = pipeline.run(csv_file)

    assert metrics.inserted_count == 1
    assert metrics.rejected_count == 1
    with db_mgr.session_scope() as session:
        rej = session.query(RejectedRecord).first()
        assert "Conflicting payload" in rej.rejection_reason or "CONFLICTING_EVENT_ID" in rej.rejection_reason


# 11. Test Out-of-Order Event (Higher version arrives before lower version)
def test_11_out_of_order_event(test_env, tmp_path):
    cfg, db_mgr, pipeline = test_env
    # Version 2 arrives first, then version 1 arrives later
    rows = [
        {"event_id": "E-11A", "customer_id": "C-11", "operation": "INSERT", "name": "Henry", "city": "Austin", "salary": "80000", "version": "2", "event_timestamp": "2026-11-01T12:00:00Z"},
        {"event_id": "E-11B", "customer_id": "C-11", "operation": "UPDATE", "name": "Henry Older", "city": "Austin", "salary": "70000", "version": "1", "event_timestamp": "2026-11-01T10:00:00Z"},
    ]
    csv_file = create_csv(tmp_path, rows)
    metrics = pipeline.run(csv_file)

    assert metrics.inserted_count == 1
    assert metrics.late_event_count == 1
    with db_mgr.session_scope() as session:
        cust = session.get(CurrentCustomer, "C-11")
        # Current state retains version 2, never overwritten by version 1
        assert cust.version == 2
        assert cust.salary == 80000.0
        # History retains both events!
        hists = session.query(CustomerHistory).filter(CustomerHistory.customer_id == "C-11").all()
        assert len(hists) == 2


# 12. Test Late-Arriving Event
def test_12_late_arriving_event(test_env, tmp_path):
    cfg, db_mgr, pipeline = test_env
    # Run initial pipeline
    row1 = {"event_id": "E-12A", "customer_id": "C-12", "operation": "INSERT", "name": "Ian", "city": "Atlanta", "salary": "55000", "version": "5", "event_timestamp": "2026-11-01T15:00:00Z"}
    csv1 = create_csv(tmp_path, [row1], "file1.csv")
    pipeline.run(csv1)

    # Later file arrives with older event version 3
    row2 = {"event_id": "E-12B", "customer_id": "C-12", "operation": "UPDATE", "name": "Ian Late", "city": "Atlanta", "salary": "50000", "version": "3", "event_timestamp": "2026-11-01T11:00:00Z"}
    csv2 = create_csv(tmp_path, [row2], "file2.csv")
    metrics2 = pipeline.run(csv2)

    assert metrics2.late_event_count == 1
    with db_mgr.session_scope() as session:
        cust = session.get(CurrentCustomer, "C-12")
        assert cust.version == 5
        assert cust.salary == 55000.0


# 13. Test UPDATE Before INSERT (Unknown Reference)
def test_13_update_before_insert(test_env, tmp_path):
    cfg, db_mgr, pipeline = test_env
    row = {"event_id": "E-13", "customer_id": "C-13", "operation": "UPDATE", "name": "Jack", "city": "Denver", "salary": "60000", "version": "1", "event_timestamp": "2026-11-01T10:00:00Z"}
    csv_file = create_csv(tmp_path, [row])
    metrics = pipeline.run(csv_file)

    assert metrics.rejected_count == 1
    with db_mgr.session_scope() as session:
        assert session.get(CurrentCustomer, "C-13") is None
        rej = session.query(RejectedRecord).first()
        assert "UNKNOWN_REFERENCE" in rej.rejection_reason


# 14. Test DELETE Before Older UPDATE (Older update must not reactivate)
def test_14_delete_before_older_update(test_env, tmp_path):
    cfg, db_mgr, pipeline = test_env
    rows = [
        {"event_id": "E-14A", "customer_id": "C-14", "operation": "INSERT", "name": "Karen", "city": "NYC", "salary": "90000", "version": "1", "event_timestamp": "2026-11-01T10:00:00Z"},
        {"event_id": "E-14B", "customer_id": "C-14", "operation": "DELETE", "name": "", "city": "", "salary": "", "version": "3", "event_timestamp": "2026-11-01T12:00:00Z"},
        {"event_id": "E-14C", "customer_id": "C-14", "operation": "UPDATE", "name": "Karen Resurrection", "city": "NYC", "salary": "95000", "version": "2", "event_timestamp": "2026-11-01T11:00:00Z"},
    ]
    csv_file = create_csv(tmp_path, rows)
    metrics = pipeline.run(csv_file)

    with db_mgr.session_scope() as session:
        cust = session.get(CurrentCustomer, "C-14")
        assert cust.is_deleted is True
        assert cust.version == 3


# 15. Test Invalid Customer Reference (DELETE on unknown customer)
def test_15_invalid_customer_reference(test_env, tmp_path):
    cfg, db_mgr, pipeline = test_env
    row = {"event_id": "E-15", "customer_id": "C-UNKNOWN", "operation": "DELETE", "name": "", "city": "", "salary": "", "version": "1", "event_timestamp": "2026-11-01T10:00:00Z"}
    csv_file = create_csv(tmp_path, [row])
    metrics = pipeline.run(csv_file)

    assert metrics.rejected_count == 1
    with db_mgr.session_scope() as session:
        rej = session.query(RejectedRecord).first()
        assert "UNKNOWN_REFERENCE" in rej.rejection_reason


# 16. Test Unexpected Schema
def test_16_unexpected_schema(test_env, tmp_path):
    cfg, db_mgr, pipeline = test_env
    # Missing columns or malformed row
    row = {"random_column": "value", "another_col": "123"}
    csv_file = create_csv(tmp_path, [row])
    metrics = pipeline.run(csv_file)

    assert metrics.rejected_count == 1


# 17. Test Same File Rerun (Idempotency)
def test_17_same_file_rerun(test_env, tmp_path):
    cfg, db_mgr, pipeline = test_env
    row = {"event_id": "E-17", "customer_id": "C-17", "operation": "INSERT", "name": "Leo", "city": "Dallas", "salary": "72000", "version": "1", "event_timestamp": "2026-11-01T10:00:00Z"}
    csv_file = create_csv(tmp_path, [row], "idempotent.csv")

    # Run 1
    metrics1 = pipeline.run(csv_file)
    assert metrics1.inserted_count == 1
    assert metrics1.duplicate_count == 0

    # Run 2 on identical file
    metrics2 = pipeline.run(csv_file)
    assert metrics2.inserted_count == 0
    assert metrics2.duplicate_count == 1  # Handled safely as duplicate
    with db_mgr.session_scope() as session:
        custs = session.query(CurrentCustomer).filter(CurrentCustomer.customer_id == "C-17").all()
        assert len(custs) == 1
        hists = session.query(CustomerHistory).filter(CustomerHistory.customer_id == "C-17").all()
        assert len(hists) == 1


# 18. Test Same Event in Different Files
def test_18_same_event_different_files(test_env, tmp_path):
    cfg, db_mgr, pipeline = test_env
    row = {"event_id": "E-18", "customer_id": "C-18", "operation": "INSERT", "name": "Mona", "city": "Austin", "salary": "85000", "version": "1", "event_timestamp": "2026-11-01T10:00:00Z"}
    csv1 = create_csv(tmp_path, [row], "fileA.csv")
    csv2 = create_csv(tmp_path, [row], "fileB.csv")

    m1 = pipeline.run(csv1)
    assert m1.inserted_count == 1

    m2 = pipeline.run(csv2)
    assert m2.inserted_count == 0
    assert m2.duplicate_count == 1


# 19. Test Partial Failure and Retry
def test_19_partial_failure_and_retry(test_env, tmp_path):
    cfg, db_mgr, pipeline = test_env
    # Batch containing 1 valid and 1 invalid record
    rows = [
        {"event_id": "E-19A", "customer_id": "C-19", "operation": "INSERT", "name": "Nancy", "city": "Austin", "salary": "60000", "version": "1", "event_timestamp": "2026-11-01T10:00:00Z"},
        {"event_id": "E-19B", "customer_id": "C-19", "operation": "UPDATE", "name": "Nancy Bad", "city": "Austin", "salary": "-999", "version": "2", "event_timestamp": "2026-11-01T11:00:00Z"},
    ]
    csv_file = create_csv(tmp_path, rows)
    metrics = pipeline.run(csv_file)

    assert metrics.inserted_count == 1
    assert metrics.rejected_count == 1
    # Customer state is not corrupted
    with db_mgr.session_scope() as session:
        cust = session.get(CurrentCustomer, "C-19")
        assert cust.salary == 60000.0
        assert cust.version == 1


# 20. Test Database Integrity
def test_20_database_integrity(test_env, tmp_path):
    cfg, db_mgr, pipeline = test_env
    events, expected = generate_cdc_events(record_count=20, seed=42)
    csv_file = create_csv(tmp_path, events)
    pipeline.run(csv_file)

    with db_mgr.session_scope() as session:
        # Check non-null constraints
        customers = session.query(CurrentCustomer).all()
        for c in customers:
            assert c.customer_id is not None
            assert c.name is not None
            assert c.city is not None
            assert c.salary >= 0
            assert c.version >= 1


# 21. Test History Completeness
def test_21_history_completeness(test_env, tmp_path):
    cfg, db_mgr, pipeline = test_env
    rows = [
        {"event_id": "H-1", "customer_id": "CH-1", "operation": "INSERT", "name": "Oscar", "city": "Miami", "salary": "70000", "version": "1", "event_timestamp": "2026-11-01T10:00:00Z"},
        {"event_id": "H-2", "customer_id": "CH-1", "operation": "UPDATE", "name": "Oscar B", "city": "Miami", "salary": "75000", "version": "2", "event_timestamp": "2026-11-01T11:00:00Z"},
        {"event_id": "H-3", "customer_id": "CH-1", "operation": "DELETE", "name": "", "city": "", "salary": "", "version": "3", "event_timestamp": "2026-11-01T12:00:00Z"},
    ]
    csv_file = create_csv(tmp_path, rows)
    pipeline.run(csv_file)

    with db_mgr.session_scope() as session:
        hist_count = session.query(CustomerHistory).filter(CustomerHistory.customer_id == "CH-1").count()
        assert hist_count == 3


# 22. Test Current-State Correctness
def test_22_current_state_correctness(test_env, tmp_path):
    cfg, db_mgr, pipeline = test_env
    rows = [
        {"event_id": "CS-1", "customer_id": "C-22", "operation": "INSERT", "name": "Paul", "city": "Seattle", "salary": "60000", "version": "1", "event_timestamp": "2026-11-01T10:00:00Z"},
        {"event_id": "CS-2", "customer_id": "C-22", "operation": "UPDATE", "name": "Paul New", "city": "Denver", "salary": "80000", "version": "2", "event_timestamp": "2026-11-01T11:00:00Z"},
    ]
    csv_file = create_csv(tmp_path, rows)
    pipeline.run(csv_file)

    with db_mgr.session_scope() as session:
        cust = session.get(CurrentCustomer, "C-22")
        assert cust.name == "Paul New"
        assert cust.city == "Denver"
        assert cust.salary == 80000.0
        assert cust.version == 2
        assert cust.last_event_id == "CS-2"


# 23. Test Large Dataset Execution
def test_23_large_dataset_execution(test_env, tmp_path):
    cfg, db_mgr, pipeline = test_env
    # Test batching with 1,500 records
    events, expected = generate_cdc_events(record_count=1500, seed=99, include_edge_cases=True)
    csv_file = create_csv(tmp_path, events, "large_batch.csv")
    metrics = pipeline.run(csv_file)

    assert metrics.total_input == len(events)
    assert metrics.status == "COMPLETED"
    assert metrics.valid_count > 0

