"""
Transformation and State Resolution Module for CDC Data Pipeline.
Handles CDC business logic, state transitions, version ordering, and out-of-order tie breaking.
"""
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class StateDecision:
    """Represents the CDC engine's decision for a valid event."""
    action: str  # 'INSERT_CURRENT', 'UPDATE_CURRENT', 'DELETE_CURRENT', 'SUPERSEDED', 'REJECT'
    event_status: str  # 'APPLIED', 'SUPERSEDED_OUT_OF_ORDER', 'REJECTED'
    rejection_reason: Optional[str] = None
    is_late_event: bool = False


def current_utc_iso() -> str:
    """Returns current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def resolve_cdc_transition(
    incoming: Dict[str, Any],
    current_customer: Optional[Dict[str, Any]],
) -> StateDecision:
    """
    Evaluates CDC state transitions against existing customer current state.

    Tie-breaking policy for equal versions:
    1. Newer event_timestamp wins.
    2. If event_timestamp is identical, higher lexicographical event_id wins.
    """
    op = incoming["operation"]
    incoming_ver = incoming["version"]
    incoming_ts = incoming["event_timestamp"]
    incoming_id = incoming["event_id"]

    # Customer does not exist in current_customers
    if current_customer is None:
        if op == "INSERT":
            return StateDecision(action="INSERT_CURRENT", event_status="APPLIED")
        elif op == "UPDATE":
            return StateDecision(
                action="REJECT",
                event_status="REJECTED",
                rejection_reason="UNKNOWN_REFERENCE: Cannot UPDATE non-existent customer",
            )
        elif op == "DELETE":
            return StateDecision(
                action="REJECT",
                event_status="REJECTED",
                rejection_reason="UNKNOWN_REFERENCE: Cannot DELETE non-existent customer",
            )
        else:
            return StateDecision(
                action="REJECT",
                event_status="REJECTED",
                rejection_reason=f"UNKNOWN_OPERATION: {op}",
            )

    # Customer exists in current_customers
    curr_ver = current_customer["version"]
    curr_ts = current_customer["last_event_timestamp"]
    curr_event_id = current_customer["last_event_id"]
    is_deleted = current_customer["is_deleted"]

    # Handling INSERT on existing customer
    if op == "INSERT":
        if not is_deleted:
            return StateDecision(
                action="REJECT",
                event_status="REJECTED",
                rejection_reason=f"DUPLICATE_CUSTOMER: Active customer {incoming['customer_id']} already exists",
            )
        else:
            # Customer was previously soft-deleted. Re-insertion with higher version is permitted (re-activation)
            if incoming_ver > curr_ver:
                return StateDecision(action="UPDATE_CURRENT", event_status="APPLIED")
            else:
                return StateDecision(
                    action="SUPERSEDED",
                    event_status="SUPERSEDED_OUT_OF_ORDER",
                    is_late_event=True,
                )

    # Handling UPDATE on existing customer
    if op == "UPDATE":
        if is_deleted:
            return StateDecision(
                action="REJECT",
                event_status="REJECTED",
                rejection_reason=f"CUSTOMER_ALREADY_DELETED: Cannot UPDATE deleted customer {incoming['customer_id']}",
            )

        if incoming_ver > curr_ver:
            return StateDecision(action="UPDATE_CURRENT", event_status="APPLIED")
        elif incoming_ver < curr_ver:
            return StateDecision(
                action="SUPERSEDED",
                event_status="SUPERSEDED_OUT_OF_ORDER",
                is_late_event=True,
            )
        else:
            # Equal versions: deterministic tie-breaking policy
            if incoming_ts > curr_ts:
                return StateDecision(action="UPDATE_CURRENT", event_status="APPLIED")
            elif incoming_ts < curr_ts:
                return StateDecision(
                    action="SUPERSEDED",
                    event_status="SUPERSEDED_OUT_OF_ORDER",
                    is_late_event=True,
                )
            else:
                if incoming_id > curr_event_id:
                    return StateDecision(action="UPDATE_CURRENT", event_status="APPLIED")
                else:
                    return StateDecision(
                        action="SUPERSEDED",
                        event_status="SUPERSEDED_OUT_OF_ORDER",
                        is_late_event=True,
                    )

    # Handling DELETE on existing customer
    if op == "DELETE":
        if is_deleted:
            # Already deleted
            if incoming_ver > curr_ver:
                # Update deletion metadata if newer version
                return StateDecision(action="DELETE_CURRENT", event_status="APPLIED")
            else:
                return StateDecision(
                    action="SUPERSEDED",
                    event_status="SUPERSEDED_OUT_OF_ORDER",
                    is_late_event=True,
                )

        if incoming_ver > curr_ver:
            return StateDecision(action="DELETE_CURRENT", event_status="APPLIED")
        elif incoming_ver < curr_ver:
            return StateDecision(
                action="SUPERSEDED",
                event_status="SUPERSEDED_OUT_OF_ORDER",
                is_late_event=True,
            )
        else:
            # Equal versions tie breaking
            if incoming_ts > curr_ts:
                return StateDecision(action="DELETE_CURRENT", event_status="APPLIED")
            elif incoming_ts < curr_ts:
                return StateDecision(
                    action="SUPERSEDED",
                    event_status="SUPERSEDED_OUT_OF_ORDER",
                    is_late_event=True,
                )
            else:
                if incoming_id > curr_event_id:
                    return StateDecision(action="DELETE_CURRENT", event_status="APPLIED")
                else:
                    return StateDecision(
                        action="SUPERSEDED",
                        event_status="SUPERSEDED_OUT_OF_ORDER",
                        is_late_event=True,
                    )

    return StateDecision(
        action="REJECT",
        event_status="REJECTED",
        rejection_reason=f"UNHANDLED_OPERATION: {op}",
    )

