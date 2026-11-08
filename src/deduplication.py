"""
Deduplication and Payload Hashing Module for CDC Data Pipeline.
Calculates deterministic payload hashes and detects identical or conflicting duplicate events.
"""
import hashlib
from typing import Dict, Any, Optional, Tuple


def compute_payload_hash(record: Dict[str, Any]) -> str:
    """
    Computes a deterministic SHA-256 hash of the canonical event representation.
    Ensures identical business events produce identical hashes.
    """
    customer_id = str(record.get("customer_id") or "").strip()
    operation = str(record.get("operation") or "").strip().upper()
    name = str(record.get("name") or "").strip()
    city = str(record.get("city") or "").strip()
    salary = f"{float(record['salary']):.2f}" if record.get("salary") is not None and record.get("salary") != "" else ""
    version = str(record.get("version") or "").strip()
    timestamp = str(record.get("event_timestamp") or "").strip()

    canonical_str = f"{customer_id}|{operation}|{name}|{city}|{salary}|{version}|{timestamp}"
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


class DeduplicationManager:
    """
    Tracks seen event IDs and payload hashes in-memory and against the database.
    """

    def __init__(self, existing_events: Optional[Dict[str, str]] = None):
        # existing_events maps event_id -> payload_hash
        self.seen_events: Dict[str, str] = dict(existing_events) if existing_events else {}

    def check_event(self, event_id: str, payload_hash: str) -> Tuple[str, Optional[str]]:
        """
        Checks an event against known events.
        Returns:
            status: 'NEW', 'EXACT_DUPLICATE', or 'CONFLICTING_EVENT_ID'
            message: explanation if duplicate or conflicting
        """
        if event_id not in self.seen_events:
            self.seen_events[event_id] = payload_hash
            return "NEW", None

        existing_hash = self.seen_events[event_id]
        if existing_hash == payload_hash:
            return "EXACT_DUPLICATE", f"Duplicate event_id '{event_id}' with identical payload skipped."
        else:
            return "CONFLICTING_EVENT_ID", (
                f"Conflicting payload for event_id '{event_id}': "
                f"existing hash {existing_hash[:8]} vs incoming {payload_hash[:8]}"
            )

    def register(self, event_id: str, payload_hash: str) -> None:
        """Registers a newly accepted event ID and payload hash."""
        self.seen_events[event_id] = payload_hash

