"""
Reporting and Export Module for CDC Data Pipeline.
Generates CSV/JSON exports, analytical summaries, and tabular data queries.
"""
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd
from sqlalchemy import select, func, desc

from .config import AppConfig
from .database import (
    DatabaseManager,
    CurrentCustomer,
    CustomerHistory,
    RejectedRecord,
    PipelineRun,
)


class ReportingService:
    """Provides querying, aggregation, and export functionality."""

    def __init__(self, db_manager: DatabaseManager, config: Optional[AppConfig] = None):
        self.db = db_manager
        self.config = config or AppConfig.load()

    def get_current_customers(
        self,
        search: Optional[str] = None,
        city_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        with self.db.session_scope() as session:
            query = session.query(CurrentCustomer)
            if search:
                term = f"%{search.strip()}%"
                query = query.filter(
                    (CurrentCustomer.customer_id.ilike(term)) |
                    (CurrentCustomer.name.ilike(term)) |
                    (CurrentCustomer.city.ilike(term))
                )
            if city_filter and city_filter != "ALL":
                query = query.filter(CurrentCustomer.city == city_filter)
            if status_filter == "ACTIVE":
                query = query.filter(CurrentCustomer.is_deleted == False)
            elif status_filter == "DELETED":
                query = query.filter(CurrentCustomer.is_deleted == True)

            query = query.order_by(CurrentCustomer.customer_id).limit(limit).offset(offset)
            return [c.to_dict() for c in query.all()]

    def get_unique_cities(self) -> List[str]:
        with self.db.session_scope() as session:
            rows = session.query(CurrentCustomer.city).distinct().order_by(CurrentCustomer.city).all()
            return [r[0] for r in rows if r[0]]

    def get_history(
        self,
        search: Optional[str] = None,
        operation_filter: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        with self.db.session_scope() as session:
            query = session.query(CustomerHistory)
            if search:
                term = f"%{search.strip()}%"
                query = query.filter(
                    (CustomerHistory.customer_id.ilike(term)) |
                    (CustomerHistory.event_id.ilike(term)) |
                    (CustomerHistory.source_file.ilike(term))
                )
            if operation_filter and operation_filter != "ALL":
                query = query.filter(CustomerHistory.operation == operation_filter.upper())

            query = query.order_by(CustomerHistory.processed_at.desc()).limit(limit).offset(offset)
            return [h.to_dict() for h in query.all()]

    def get_quarantine(
        self,
        search: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        with self.db.session_scope() as session:
            query = session.query(RejectedRecord)
            if search:
                term = f"%{search.strip()}%"
                query = query.filter(
                    (RejectedRecord.customer_id.ilike(term)) |
                    (RejectedRecord.event_id.ilike(term)) |
                    (RejectedRecord.rejection_reason.ilike(term)) |
                    (RejectedRecord.source_file.ilike(term))
                )
            query = query.order_by(RejectedRecord.rejected_at.desc()).limit(limit).offset(offset)
            return [r.to_dict() for r in query.all()]

    def get_pipeline_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.db.session_scope() as session:
            query = session.query(PipelineRun).order_by(PipelineRun.start_time.desc()).limit(limit)
            return [r.to_dict() for r in query.all()]

    def get_analytics_data(self) -> Dict[str, Any]:
        with self.db.session_scope() as session:
            # Operation counts in history
            op_counts = dict(
                session.query(CustomerHistory.operation, func.count(CustomerHistory.event_id))
                .group_by(CustomerHistory.operation)
                .all()
            )

            # Valid vs Rejected
            valid_count = session.query(func.count(CustomerHistory.event_id)).scalar() or 0
            rejected_count = session.query(func.count(RejectedRecord.reject_id)).scalar() or 0

            # Totals across runs
            sum_duplicates = session.query(func.sum(PipelineRun.duplicate_count)).scalar() or 0
            sum_late = session.query(func.sum(PipelineRun.late_event_count)).scalar() or 0

            # Recent runs performance
            recent_runs = (
                session.query(PipelineRun)
                .order_by(PipelineRun.start_time.asc())
                .limit(10)
                .all()
            )
            run_labels = [r.run_id[-6:] for r in recent_runs]
            run_durations = [r.execution_time_seconds for r in recent_runs]
            run_inputs = [r.total_input for r in recent_runs]

            return {
                "operations": {
                    "INSERT": op_counts.get("INSERT", 0),
                    "UPDATE": op_counts.get("UPDATE", 0),
                    "DELETE": op_counts.get("DELETE", 0),
                },
                "valid_count": valid_count,
                "rejected_count": rejected_count,
                "duplicate_count": sum_duplicates,
                "late_event_count": sum_late,
                "recent_runs": {
                    "labels": run_labels,
                    "durations": run_durations,
                    "inputs": run_inputs,
                },
            }

    def export_table_to_csv(self, table_name: str, destination_path: Path) -> int:
        """Exports an entire table to a CSV file. Returns row count exported."""
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        with self.db.session_scope() as session:
            if table_name == "current_customers":
                records = [c.to_dict() for c in session.query(CurrentCustomer).all()]
            elif table_name == "customer_history":
                records = [h.to_dict() for h in session.query(CustomerHistory).all()]
            elif table_name == "rejected_records":
                records = [r.to_dict() for r in session.query(RejectedRecord).all()]
            elif table_name == "pipeline_runs":
                records = [pr.to_dict() for pr in session.query(PipelineRun).all()]
            else:
                raise ValueError(f"Unknown table: {table_name}")

        df = pd.DataFrame(records)
        df.to_csv(destination_path, index=False)
        return len(df)
