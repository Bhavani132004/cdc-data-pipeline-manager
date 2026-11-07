"""
Core CDC Pipeline Orchestrator.
Coordinates Ingestion, Validation, Deduplication, Transformation, State Management, and Persistence.
"""
import uuid
import json
import logging
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List, Set
from datetime import datetime, timezone

from sqlalchemy import select

from .config import AppConfig
from .database import (
    DatabaseManager,
    CurrentCustomer,
    CustomerHistory,
    RejectedRecord,
    PipelineRun,
    ProcessedFile,
)
from .ingestion import read_records, compute_file_hash, count_file_records
from .validation import validate_record
from .deduplication import compute_payload_hash, DeduplicationManager
from .transformation import resolve_cdc_transition, current_utc_iso
from .metrics import PipelineMetrics
from .logger import setup_logger


class CDCPipeline:
    """
    Production-grade CDC Data Pipeline with state tracking, idempotency,
    out-of-order resolution, and quarantine capabilities.
    """

    def __init__(self, config: Optional[AppConfig] = None, db_manager: Optional[DatabaseManager] = None):
        self.config = config or AppConfig.load()
        self.db_manager = db_manager or DatabaseManager(self.config.db_url, echo=self.config.db_echo)
        self.logger = setup_logger(
            name="cdc_pipeline",
            log_dir=self.config.logs_dir,
            log_level=self.config.log_level,
        )
        self.db_manager.init_db()

    def run(
        self,
        filepath: Path,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> PipelineMetrics:
        """
        Executes end-to-end CDC pipeline processing on the given input file.
        """
        filepath = Path(filepath).resolve()
        run_id = f"run_{uuid.uuid4().hex[:10]}"
        metrics = PipelineMetrics(run_id=run_id, source_file=str(filepath.name))

        def notify(stage: str, pct: float):
            if progress_callback:
                try:
                    progress_callback(stage, min(1.0, max(0.0, pct)))
                except Exception:
                    pass

        self.logger.info(f"Starting CDC Pipeline Run [{run_id}] for input: {filepath}")
        notify("Initializing pipeline", 0.05)

        if not filepath.exists():
            err = f"Input file not found: {filepath}"
            self.logger.error(err)
            metrics.finish(status="FAILED", error_message=err)
            self._record_pipeline_run(metrics)
            return metrics

        # Empty file check
        if filepath.stat().st_size == 0:
            self.logger.warning(f"File {filepath} is empty (0 bytes).")
            metrics.finish(status="COMPLETED")
            self._record_pipeline_run(metrics)
            notify("Completed (Empty File)", 1.0)
            return metrics

        # Compute file hash for idempotency tracking
        file_hash = compute_file_hash(filepath)
        total_estimated = count_file_records(filepath)
        self.logger.info(f"File hash: {file_hash} | Estimated records: {total_estimated}")
        notify("Validating file integrity", 0.10)

        # Pre-load known event IDs for deduplication
        with self.db_manager.session_scope() as session:
            existing_events_tuples = session.query(
                CustomerHistory.event_id, CustomerHistory.payload_hash
            ).all()
            dedup_manager = DeduplicationManager(dict(existing_events_tuples))

            # Pre-load current customers into memory cache for blazing fast lookups
            all_customers = session.query(CurrentCustomer).all()
            current_customers_cache: Dict[str, Dict[str, Any]] = {
                c.customer_id: c.to_dict() for c in all_customers
            }

        records_processed = 0
        all_quarantine_rows: List[Dict[str, Any]] = []

        try:
            for batch_index, raw_batch in enumerate(
                read_records(filepath, batch_size=self.config.batch_size)
            ):
                metrics.total_input += len(raw_batch)
                notify(
                    f"Processing batch {batch_index + 1} ({metrics.total_input}/{total_estimated})",
                    0.15 + (0.75 * (records_processed / max(1, total_estimated))),
                )

                history_to_insert: List[Dict[str, Any]] = []
                rejected_to_insert: List[Dict[str, Any]] = []
                customers_to_upsert: Dict[str, Dict[str, Any]] = {}

                for raw_record in raw_batch:
                    records_processed += 1
                    # 1. Validation
                    val_res = validate_record(raw_record)
                    if not val_res.is_valid:
                        metrics.rejected_count += 1
                        rejected_entry = {
                            "event_id": raw_record.get("event_id") if isinstance(raw_record, dict) else None,
                            "customer_id": raw_record.get("customer_id") if isinstance(raw_record, dict) else None,
                            "source_file": filepath.name,
                            "run_id": run_id,
                            "rejection_reason": val_res.rejection_reason,
                            "original_payload": val_res.raw_payload,
                            "rejected_at": current_utc_iso(),
                        }
                        rejected_to_insert.append(rejected_entry)
                        all_quarantine_rows.append(rejected_entry)
                        continue

                    sanitized = val_res.sanitized_record
                    payload_hash = compute_payload_hash(sanitized)
                    event_id = sanitized["event_id"]
                    cust_id = sanitized["customer_id"]

                    # 2. Deduplication check
                    dedup_status, dedup_msg = dedup_manager.check_event(event_id, payload_hash)
                    if dedup_status == "EXACT_DUPLICATE":
                        metrics.duplicate_count += 1
                        continue
                    elif dedup_status == "CONFLICTING_EVENT_ID":
                        metrics.rejected_count += 1
                        rejected_entry = {
                            "event_id": event_id,
                            "customer_id": cust_id,
                            "source_file": filepath.name,
                            "run_id": run_id,
                            "rejection_reason": dedup_msg,
                            "original_payload": val_res.raw_payload,
                            "rejected_at": current_utc_iso(),
                        }
                        rejected_to_insert.append(rejected_entry)
                        all_quarantine_rows.append(rejected_entry)
                        continue

                    # 3. CDC State Resolution
                    curr_cust_state = current_customers_cache.get(cust_id)
                    decision = resolve_cdc_transition(sanitized, curr_cust_state)

                    if decision.action == "REJECT":
                        metrics.rejected_count += 1
                        rejected_entry = {
                            "event_id": event_id,
                            "customer_id": cust_id,
                            "source_file": filepath.name,
                            "run_id": run_id,
                            "rejection_reason": decision.rejection_reason,
                            "original_payload": val_res.raw_payload,
                            "rejected_at": current_utc_iso(),
                        }
                        rejected_to_insert.append(rejected_entry)
                        all_quarantine_rows.append(rejected_entry)
                        continue

                    # Record valid historical event
                    metrics.valid_count += 1
                    if decision.is_late_event:
                        metrics.late_event_count += 1

                    history_to_insert.append({
                        "event_id": event_id,
                        "customer_id": cust_id,
                        "operation": sanitized["operation"],
                        "name": sanitized.get("name"),
                        "city": sanitized.get("city"),
                        "salary": sanitized.get("salary"),
                        "version": sanitized["version"],
                        "event_timestamp": sanitized["event_timestamp"],
                        "source_file": filepath.name,
                        "run_id": run_id,
                        "processed_at": current_utc_iso(),
                        "event_status": decision.event_status,
                        "payload_hash": payload_hash,
                    })

                    # Apply state transition to current_customers
                    now_iso = current_utc_iso()
                    if decision.action == "INSERT_CURRENT":
                        metrics.inserted_count += 1
                        updated_state = {
                            "customer_id": cust_id,
                            "name": sanitized["name"],
                            "city": sanitized["city"],
                            "salary": sanitized["salary"],
                            "version": sanitized["version"],
                            "is_deleted": False,
                            "last_event_id": event_id,
                            "last_event_timestamp": sanitized["event_timestamp"],
                            "updated_at": now_iso,
                        }
                        current_customers_cache[cust_id] = updated_state
                        customers_to_upsert[cust_id] = updated_state

                    elif decision.action == "UPDATE_CURRENT":
                        metrics.updated_count += 1
                        updated_state = {
                            "customer_id": cust_id,
                            "name": sanitized["name"],
                            "city": sanitized["city"],
                            "salary": sanitized["salary"],
                            "version": sanitized["version"],
                            "is_deleted": False,
                            "last_event_id": event_id,
                            "last_event_timestamp": sanitized["event_timestamp"],
                            "updated_at": now_iso,
                        }
                        current_customers_cache[cust_id] = updated_state
                        customers_to_upsert[cust_id] = updated_state

                    elif decision.action == "DELETE_CURRENT":
                        metrics.deleted_count += 1
                        existing_rec = current_customers_cache[cust_id]
                        updated_state = {
                            "customer_id": cust_id,
                            "name": existing_rec["name"],
                            "city": existing_rec["city"],
                            "salary": existing_rec["salary"],
                            "version": sanitized["version"],
                            "is_deleted": True,
                            "last_event_id": event_id,
                            "last_event_timestamp": sanitized["event_timestamp"],
                            "updated_at": now_iso,
                        }
                        current_customers_cache[cust_id] = updated_state
                        customers_to_upsert[cust_id] = updated_state

                    elif decision.action == "SUPERSEDED":
                        # Current customer state is not altered; history record preserves the event
                        pass

                # Persist batch within transaction
                self._persist_batch(
                    history_to_insert=history_to_insert,
                    rejected_to_insert=rejected_to_insert,
                    customers_to_upsert=customers_to_upsert,
                )

            # Export quarantine records to CSV if any were rejected
            if all_quarantine_rows:
                self._export_quarantine_file(run_id, all_quarantine_rows)

            metrics.finish(status="COMPLETED")
            self._record_pipeline_run(metrics)
            self._record_processed_file(filepath.name, file_hash, run_id, "COMPLETED")
            notify("Pipeline Completed Successfully", 1.0)
            self.logger.info(
                f"Pipeline run [{run_id}] completed: "
                f"total={metrics.total_input}, valid={metrics.valid_count}, "
                f"ins={metrics.inserted_count}, upd={metrics.updated_count}, del={metrics.deleted_count}, "
                f"dup={metrics.duplicate_count}, rej={metrics.rejected_count}, late={metrics.late_event_count} "
                f"in {metrics.execution_time_seconds}s"
            )

        except Exception as e:
            self.logger.exception(f"Pipeline run [{run_id}] failed: {str(e)}")
            metrics.finish(status="FAILED", error_message=str(e))
            self._record_pipeline_run(metrics)
            self._record_processed_file(filepath.name, file_hash, run_id, "FAILED")
            notify("Pipeline Failed", 1.0)
            raise

        return metrics

    def _persist_batch(
        self,
        history_to_insert: List[Dict[str, Any]],
        rejected_to_insert: List[Dict[str, Any]],
        customers_to_upsert: Dict[str, Dict[str, Any]],
    ) -> None:
        """Executes atomic batch write to SQLite."""
        with self.db_manager.session_scope() as session:
            # 1. Bulk insert history
            if history_to_insert:
                session.bulk_insert_mappings(CustomerHistory, history_to_insert)

            # 2. Bulk insert rejections
            if rejected_to_insert:
                session.bulk_insert_mappings(RejectedRecord, rejected_to_insert)

            # 3. Upsert current customers
            for cust_id, cust_data in customers_to_upsert.items():
                existing = session.get(CurrentCustomer, cust_id)
                if existing:
                    existing.name = cust_data["name"]
                    existing.city = cust_data["city"]
                    existing.salary = cust_data["salary"]
                    existing.version = cust_data["version"]
                    existing.is_deleted = cust_data["is_deleted"]
                    existing.last_event_id = cust_data["last_event_id"]
                    existing.last_event_timestamp = cust_data["last_event_timestamp"]
                    existing.updated_at = cust_data["updated_at"]
                else:
                    new_cust = CurrentCustomer(**cust_data)
                    session.add(new_cust)

    def _record_pipeline_run(self, metrics: PipelineMetrics) -> None:
        """Persists run metadata into pipeline_runs table."""
        with self.db_manager.session_scope() as session:
            run_row = PipelineRun(
                run_id=metrics.run_id,
                source_file=metrics.source_file,
                start_time=metrics.start_time,
                end_time=metrics.end_time,
                status=metrics.status,
                total_input=metrics.total_input,
                valid_count=metrics.valid_count,
                inserted_count=metrics.inserted_count,
                updated_count=metrics.updated_count,
                deleted_count=metrics.deleted_count,
                duplicate_count=metrics.duplicate_count,
                rejected_count=metrics.rejected_count,
                late_event_count=metrics.late_event_count,
                error_message=metrics.error_message,
                execution_time_seconds=metrics.execution_time_seconds,
            )
            session.merge(run_row)

    def _record_processed_file(
        self,
        source_file: str,
        file_hash: str,
        run_id: str,
        status: str,
    ) -> None:
        """Registers the file hash in processed_files table."""
        with self.db_manager.session_scope() as session:
            existing = session.get(ProcessedFile, source_file)
            if existing:
                existing.file_hash = file_hash
                existing.processed_at = current_utc_iso()
                existing.processing_status = status
            else:
                session.add(ProcessedFile(
                    source_file=source_file,
                    file_hash=file_hash,
                    first_run_id=run_id,
                    processed_at=current_utc_iso(),
                    processing_status=status,
                ))

    def _export_quarantine_file(self, run_id: str, rows: List[Dict[str, Any]]) -> None:
        """Saves quarantined records to a CSV file in quarantine directory."""
        import pandas as pd
        q_dir = self.config.quarantine_dir
        q_dir.mkdir(parents=True, exist_ok=True)
        q_path = q_dir / f"{run_id}_quarantine.csv"
        df = pd.DataFrame(rows)
        df.to_csv(q_path, index=False)
        self.logger.info(f"Exported {len(rows)} quarantined records to {q_path}")
