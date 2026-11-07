"""
Database Models and Management for CDC Data Pipeline.
Uses SQLAlchemy 2.0 with SQLite backend, connection pooling, and optimized PRAGMAs.
"""
from datetime import datetime, timezone
from contextlib import contextmanager
from typing import Generator, Optional, List, Dict, Any
from pathlib import Path

from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    Float,
    Boolean,
    Text,
    Index,
    event,
    func,
    select,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.engine import Engine

Base = declarative_base()


class CurrentCustomer(Base):
    """Current state table containing the latest valid customer representation."""
    __tablename__ = "current_customers"

    customer_id = Column(String(64), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False, index=True)
    salary = Column(Float, nullable=False)
    version = Column(Integer, nullable=False)
    is_deleted = Column(Boolean, nullable=False, default=False, index=True)
    last_event_id = Column(String(64), nullable=False)
    last_event_timestamp = Column(String(32), nullable=False)
    updated_at = Column(String(32), nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "customer_id": self.customer_id,
            "name": self.name,
            "city": self.city,
            "salary": self.salary,
            "version": self.version,
            "is_deleted": self.is_deleted,
            "last_event_id": self.last_event_id,
            "last_event_timestamp": self.last_event_timestamp,
            "updated_at": self.updated_at,
        }


class CustomerHistory(Base):
    """Historical audit table preserving all unique events processed."""
    __tablename__ = "customer_history"

    event_id = Column(String(64), primary_key=True, index=True)
    customer_id = Column(String(64), nullable=False, index=True)
    operation = Column(String(16), nullable=False)
    name = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    salary = Column(Float, nullable=True)
    version = Column(Integer, nullable=False)
    event_timestamp = Column(String(32), nullable=False, index=True)
    source_file = Column(String(255), nullable=False)
    run_id = Column(String(64), nullable=False, index=True)
    processed_at = Column(String(32), nullable=False)
    event_status = Column(String(32), nullable=False)  # 'APPLIED', 'SUPERSEDED_OUT_OF_ORDER', 'DUPLICATE_SKIPPED'
    payload_hash = Column(String(64), nullable=False, index=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "customer_id": self.customer_id,
            "operation": self.operation,
            "name": self.name,
            "city": self.city,
            "salary": self.salary,
            "version": self.version,
            "event_timestamp": self.event_timestamp,
            "source_file": self.source_file,
            "run_id": self.run_id,
            "processed_at": self.processed_at,
            "event_status": self.event_status,
            "payload_hash": self.payload_hash,
        }


class RejectedRecord(Base):
    """Quarantine table storing invalid records and detailed rejection reasons."""
    __tablename__ = "rejected_records"

    reject_id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(64), nullable=True, index=True)
    customer_id = Column(String(64), nullable=True, index=True)
    source_file = Column(String(255), nullable=False)
    run_id = Column(String(64), nullable=False, index=True)
    rejection_reason = Column(String(255), nullable=False)
    original_payload = Column(Text, nullable=False)
    rejected_at = Column(String(32), nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reject_id": self.reject_id,
            "event_id": self.event_id,
            "customer_id": self.customer_id,
            "source_file": self.source_file,
            "run_id": self.run_id,
            "rejection_reason": self.rejection_reason,
            "original_payload": self.original_payload,
            "rejected_at": self.rejected_at,
        }


class PipelineRun(Base):
    """Metadata and execution metrics for every pipeline execution run."""
    __tablename__ = "pipeline_runs"

    run_id = Column(String(64), primary_key=True)
    source_file = Column(String(255), nullable=False)
    start_time = Column(String(32), nullable=False)
    end_time = Column(String(32), nullable=True)
    status = Column(String(32), nullable=False)  # 'RUNNING', 'COMPLETED', 'FAILED', 'PARTIAL_SUCCESS'
    total_input = Column(Integer, default=0)
    valid_count = Column(Integer, default=0)
    inserted_count = Column(Integer, default=0)
    updated_count = Column(Integer, default=0)
    deleted_count = Column(Integer, default=0)
    duplicate_count = Column(Integer, default=0)
    rejected_count = Column(Integer, default=0)
    late_event_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    execution_time_seconds = Column(Float, default=0.0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "source_file": self.source_file,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status,
            "total_input": self.total_input,
            "valid_count": self.valid_count,
            "inserted_count": self.inserted_count,
            "updated_count": self.updated_count,
            "deleted_count": self.deleted_count,
            "duplicate_count": self.duplicate_count,
            "rejected_count": self.rejected_count,
            "late_event_count": self.late_event_count,
            "error_message": self.error_message,
            "execution_time_seconds": self.execution_time_seconds,
        }


class ProcessedFile(Base):
    """Registry of processed files and cryptographic hashes for idempotency."""
    __tablename__ = "processed_files"

    source_file = Column(String(255), primary_key=True)
    file_hash = Column(String(64), nullable=False, index=True)
    first_run_id = Column(String(64), nullable=False)
    processed_at = Column(String(32), nullable=False)
    processing_status = Column(String(32), nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_file": self.source_file,
            "file_hash": self.file_hash,
            "first_run_id": self.first_run_id,
            "processed_at": self.processed_at,
            "processing_status": self.processing_status,
        }


# High-performance SQLite PRAGMAs
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode = WAL")
    cursor.execute("PRAGMA synchronous = NORMAL")
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("PRAGMA cache_size = -64000")
    cursor.close()


class DatabaseManager:
    """Manages database connection lifecycle, migrations, and transactions."""

    def __init__(self, db_url: str, echo: bool = False):
        self.db_url = db_url
        self.engine = create_engine(db_url, echo=echo, future=True)
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
            future=True,
        )

    def init_db(self) -> None:
        """Creates all database tables."""
        Base.metadata.create_all(self.engine)

    def reset_db(self) -> None:
        """Drops and recreates all database tables."""
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Provides a transactional scope around a series of operations."""
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_summary_metrics(self) -> Dict[str, Any]:
        """Calculates current high-level database metrics for dashboard."""
        with self.session_scope() as session:
            total_customers = session.query(func.count(CurrentCustomer.customer_id)).scalar() or 0
            active_customers = session.query(func.count(CurrentCustomer.customer_id)).filter(CurrentCustomer.is_deleted == False).scalar() or 0
            deleted_customers = session.query(func.count(CurrentCustomer.customer_id)).filter(CurrentCustomer.is_deleted == True).scalar() or 0
            total_history = session.query(func.count(CustomerHistory.event_id)).scalar() or 0
            total_rejected = session.query(func.count(RejectedRecord.reject_id)).scalar() or 0
            
            # Aggregate totals across pipeline runs
            sum_input = session.query(func.sum(PipelineRun.total_input)).scalar() or 0
            sum_duplicates = session.query(func.sum(PipelineRun.duplicate_count)).scalar() or 0
            sum_late = session.query(func.sum(PipelineRun.late_event_count)).scalar() or 0
            
            latest_run = session.query(PipelineRun).order_by(PipelineRun.start_time.desc()).first()
            
            return {
                "total_customers": total_customers,
                "active_customers": active_customers,
                "deleted_customers": deleted_customers,
                "total_history": total_history,
                "total_rejected": total_rejected,
                "total_input_all_runs": sum_input,
                "total_duplicates": sum_duplicates,
                "total_late_events": sum_late,
                "latest_run": latest_run.to_dict() if latest_run else None,
            }
