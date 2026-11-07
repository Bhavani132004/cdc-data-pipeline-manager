"""
Metrics and Instrumentation Module for CDC Data Pipeline.
Tracks performance, execution metrics, record counters, and memory utilization.
"""
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import psutil
import os


@dataclass
class PipelineMetrics:
    """Detailed operational metrics for a pipeline run."""
    run_id: str
    source_file: str
    start_time: str = ""
    end_time: Optional[str] = None
    status: str = "RUNNING"
    total_input: int = 0
    valid_count: int = 0
    inserted_count: int = 0
    updated_count: int = 0
    deleted_count: int = 0
    duplicate_count: int = 0
    rejected_count: int = 0
    late_event_count: int = 0
    error_message: Optional[str] = None
    execution_time_seconds: float = 0.0
    stage_durations: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        if not self.start_time:
            self.start_time = datetime.now(timezone.utc).isoformat()
        self._start_perf = time.perf_counter()

    def finish(self, status: str = "COMPLETED", error_message: Optional[str] = None) -> None:
        self.end_time = datetime.now(timezone.utc).isoformat()
        self.status = status
        self.error_message = error_message
        self.execution_time_seconds = round(time.perf_counter() - self._start_perf, 4)

    @property
    def throughput_records_per_sec(self) -> float:
        if self.execution_time_seconds > 0:
            return round(self.total_input / self.execution_time_seconds, 2)
        return 0.0

    @property
    def current_memory_mb(self) -> float:
        try:
            process = psutil.Process(os.getpid())
            return round(process.memory_info().rss / (1024 * 1024), 2)
        except Exception:
            return 0.0

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
            "throughput_records_per_sec": self.throughput_records_per_sec,
            "memory_usage_mb": self.current_memory_mb,
            "stage_durations": self.stage_durations,
        }
