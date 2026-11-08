"""
Schema and Business Rule Validation Module for CDC Data Pipeline.
Validates input record format, required fields, data types, and business constraints.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
import re

VALID_OPERATIONS = {"INSERT", "UPDATE", "DELETE"}


@dataclass
class ValidationResult:
    """Outcome of validating a single raw record."""
    is_valid: bool
    sanitized_record: Optional[Dict[str, Any]] = None
    rejection_reason: Optional[str] = None
    raw_payload: str = ""


def parse_iso_timestamp(ts_str: Any) -> Optional[str]:
    """Validates and normalizes timestamp to ISO-8601 string format."""
    if not ts_str:
        return None
    s = str(ts_str).strip()
    if not s:
        return None

    # Handle common formats
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.isoformat()
        except ValueError:
            continue
    try:
        # Fallback to fromisoformat
        # Handle trailing Z
        clean = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        return dt.isoformat()
    except Exception:
        return None


def validate_record(raw: Dict[str, Any]) -> ValidationResult:
    """
    Performs comprehensive schema and business rule validation on a raw dictionary record.
    Returns ValidationResult with normalized fields or specific rejection reason.
    """
    import json
    raw_payload_str = json.dumps(raw, default=str)

    if not isinstance(raw, dict):
        return ValidationResult(
            is_valid=False,
            rejection_reason="INVALID_SCHEMA: Record is not a valid JSON/dictionary object",
            raw_payload=raw_payload_str,
        )

    # 1. Check event_id
    raw_event_id = raw.get("event_id")
    if raw_event_id is None or str(raw_event_id).strip() == "":
        return ValidationResult(
            is_valid=False,
            rejection_reason="MISSING_EVENT_ID: Field 'event_id' is mandatory and non-empty",
            raw_payload=raw_payload_str,
        )
    event_id = str(raw_event_id).strip()

    # 2. Check customer_id
    raw_customer_id = raw.get("customer_id")
    if raw_customer_id is None or str(raw_customer_id).strip() == "":
        return ValidationResult(
            is_valid=False,
            rejection_reason="MISSING_CUSTOMER_ID: Field 'customer_id' is mandatory and non-empty",
            raw_payload=raw_payload_str,
        )
    customer_id = str(raw_customer_id).strip()

    # 3. Check operation
    raw_op = raw.get("operation")
    if raw_op is None or str(raw_op).strip() == "":
        return ValidationResult(
            is_valid=False,
            rejection_reason="INVALID_OPERATION: Operation field is missing",
            raw_payload=raw_payload_str,
        )
    operation = str(raw_op).strip().upper()
    if operation not in VALID_OPERATIONS:
        return ValidationResult(
            is_valid=False,
            rejection_reason=f"INVALID_OPERATION: Unknown operation '{raw_op}'. Must be INSERT, UPDATE, or DELETE",
            raw_payload=raw_payload_str,
        )

    # 4. Check version
    raw_version = raw.get("version")
    if raw_version is None or str(raw_version).strip() == "":
        return ValidationResult(
            is_valid=False,
            rejection_reason="INVALID_VERSION: Version field is missing",
            raw_payload=raw_payload_str,
        )
    try:
        version = int(raw_version)
        if version < 1:
            return ValidationResult(
                is_valid=False,
                rejection_reason=f"INVALID_VERSION: Version must be positive integer >= 1, got {raw_version}",
                raw_payload=raw_payload_str,
            )
    except (ValueError, TypeError):
        return ValidationResult(
            is_valid=False,
            rejection_reason=f"INVALID_VERSION: Version must be an integer, got '{raw_version}'",
            raw_payload=raw_payload_str,
        )

    # 5. Check event_timestamp
    raw_ts = raw.get("event_timestamp")
    normalized_ts = parse_iso_timestamp(raw_ts)
    if not normalized_ts:
        return ValidationResult(
            is_valid=False,
            rejection_reason=f"INVALID_TIMESTAMP: Unable to parse ISO-8601 timestamp '{raw_ts}'",
            raw_payload=raw_payload_str,
        )

    # 6. Operation-specific field validations
    sanitized = {
        "event_id": event_id,
        "customer_id": customer_id,
        "operation": operation,
        "version": version,
        "event_timestamp": normalized_ts,
    }

    if operation in ("INSERT", "UPDATE"):
        # Name validation
        raw_name = raw.get("name")
        if raw_name is None or str(raw_name).strip() == "":
            return ValidationResult(
                is_valid=False,
                rejection_reason="MISSING_NAME: Name is mandatory for INSERT and UPDATE operations",
                raw_payload=raw_payload_str,
            )
        sanitized["name"] = str(raw_name).strip()

        # City validation
        raw_city = raw.get("city")
        if raw_city is None or str(raw_city).strip() == "":
            return ValidationResult(
                is_valid=False,
                rejection_reason="MISSING_CITY: City is mandatory for INSERT and UPDATE operations",
                raw_payload=raw_payload_str,
            )
        sanitized["city"] = str(raw_city).strip().title()

        # Salary validation
        raw_salary = raw.get("salary")
        if raw_salary is None or str(raw_salary).strip() == "":
            return ValidationResult(
                is_valid=False,
                rejection_reason="MISSING_SALARY: Salary is mandatory for INSERT and UPDATE operations",
                raw_payload=raw_payload_str,
            )
        try:
            salary = float(raw_salary)
            if salary < 0:
                return ValidationResult(
                    is_valid=False,
                    rejection_reason=f"INVALID_SALARY: Salary cannot be negative, got {raw_salary}",
                    raw_payload=raw_payload_str,
                )
            sanitized["salary"] = round(salary, 2)
        except (ValueError, TypeError):
            return ValidationResult(
                is_valid=False,
                rejection_reason=f"INVALID_SALARY: Salary must be a valid numeric value, got '{raw_salary}'",
                raw_payload=raw_payload_str,
            )
    else:
        # DELETE operation
        # Name, city, salary are optional for DELETE
        sanitized["name"] = str(raw.get("name", "")).strip() or None
        sanitized["city"] = (str(raw.get("city", "")).strip().title()) if raw.get("city") else None
        raw_sal = raw.get("salary")
        if raw_sal is not None and str(raw_sal).strip() != "":
            try:
                sanitized["salary"] = round(float(raw_sal), 2)
            except Exception:
                sanitized["salary"] = None
        else:
            sanitized["salary"] = None

    return ValidationResult(
        is_valid=True,
        sanitized_record=sanitized,
        raw_payload=raw_payload_str,
    )

