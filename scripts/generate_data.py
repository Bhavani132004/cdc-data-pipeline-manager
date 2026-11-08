"""
Synthetic CDC Event Generator.
Produces deterministic, reproducible datasets with all edge cases for pipeline testing and benchmarks.
"""
import random
import json
import csv
import argparse
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Tuple

CITIES = [
    "New York", "San Francisco", "Austin", "Chicago", "Seattle",
    "Boston", "Denver", "Atlanta", "Miami", "Dallas",
]

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer",
    "Michael", "Linda", "William", "Elizabeth", "David", "Barbara",
    "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones",
    "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
    "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
]


def generate_cdc_events(
    record_count: int = 50,
    seed: int = 42,
    include_edge_cases: bool = True,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Generates realistic CDC event streams with controlled edge cases.
    Returns:
        events: list of event dictionaries
        expected_summary: expected counts for validation
    """
    random.seed(seed)
    base_time = datetime(2026, 11, 1, 10, 0, 0, tzinfo=timezone.utc)

    events: List[Dict[str, Any]] = []
    customer_state: Dict[str, Dict[str, Any]] = {}
    
    expected = {
        "total_generated": 0,
        "inserts": 0,
        "updates": 0,
        "deletes": 0,
        "exact_duplicates": 0,
        "conflicting_duplicates": 0,
        "out_of_order": 0,
        "invalid_schema_or_values": 0,
        "unknown_references": 0,
    }

    event_counter = 1
    cust_counter = 1000

    def get_event_id() -> str:
        nonlocal event_counter
        eid = f"EVT-{event_counter:07d}"
        event_counter += 1
        return eid

    # Step 1: Generate initial INSERTs
    initial_customers = max(5, int(record_count * 0.5))
    for _ in range(initial_customers):
        cid = f"CUST-{cust_counter:05d}"
        cust_counter += 1
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        city = random.choice(CITIES)
        salary = round(random.uniform(45000.0, 150000.0), 2)
        ver = 1
        ts = (base_time + timedelta(minutes=random.randint(1, 100))).isoformat()
        eid = get_event_id()

        evt = {
            "event_id": eid,
            "customer_id": cid,
            "operation": "INSERT",
            "name": name,
            "city": city,
            "salary": salary,
            "version": ver,
            "event_timestamp": ts,
        }
        events.append(evt)
        customer_state[cid] = {
            "name": name, "city": city, "salary": salary, "version": ver, "is_deleted": False, "ts": ts
        }
        expected["inserts"] += 1

    # Step 2: Generate realistic lifecycle events (UPDATE, DELETE)
    remaining = record_count - len(events)
    existing_cids = list(customer_state.keys())

    for _ in range(max(0, remaining)):
        cid = random.choice(existing_cids)
        cinfo = customer_state[cid]

        # Choose operation: 70% update, 30% delete
        op = "DELETE" if random.random() < 0.25 and not cinfo["is_deleted"] else "UPDATE"
        new_ver = cinfo["version"] + 1
        new_ts = (base_time + timedelta(minutes=random.randint(200, 1000))).isoformat()
        eid = get_event_id()

        if op == "UPDATE":
            # Update salary or city
            new_salary = round(cinfo["salary"] * random.uniform(1.05, 1.25), 2)
            new_city = random.choice(CITIES) if random.random() < 0.3 else cinfo["city"]
            evt = {
                "event_id": eid,
                "customer_id": cid,
                "operation": "UPDATE",
                "name": cinfo["name"],
                "city": new_city,
                "salary": new_salary,
                "version": new_ver,
                "event_timestamp": new_ts,
            }
            events.append(evt)
            cinfo["salary"] = new_salary
            cinfo["city"] = new_city
            cinfo["version"] = new_ver
            cinfo["ts"] = new_ts
            expected["updates"] += 1
        else:
            evt = {
                "event_id": eid,
                "customer_id": cid,
                "operation": "DELETE",
                "name": cinfo["name"],
                "city": cinfo["city"],
                "salary": cinfo["salary"],
                "version": new_ver,
                "event_timestamp": new_ts,
            }
            events.append(evt)
            cinfo["is_deleted"] = True
            cinfo["version"] = new_ver
            cinfo["ts"] = new_ts
            expected["deletes"] += 1

    # Step 3: Inject controlled edge cases if requested
    if include_edge_cases and len(events) >= 10:
        # A. Exact duplicate: duplicate an existing event identically
        dup_target = dict(events[2])
        events.append(dup_target)
        expected["exact_duplicates"] += 1

        # B. Conflicting duplicate: duplicate an event_id with different payload
        conflict_target = dict(events[3])
        conflict_dup = dict(conflict_target)
        conflict_dup["name"] = "Conflicting Name " + str(random.randint(100, 999))
        conflict_dup["salary"] = 999999.0
        events.append(conflict_dup)
        expected["conflicting_duplicates"] += 1

        # C. Out-of-order / late event: version 1 after version 2 has occurred
        late_target_cid = existing_cids[0]
        events.append({
            "event_id": get_event_id(),
            "customer_id": late_target_cid,
            "operation": "UPDATE",
            "name": customer_state[late_target_cid]["name"],
            "city": "Late City",
            "salary": 50000.0,
            "version": 1,  # Lower than current version
            "event_timestamp": (base_time - timedelta(days=1)).isoformat(),
        })
        expected["out_of_order"] += 1

        # D. Invalid operation
        events.append({
            "event_id": get_event_id(),
            "customer_id": existing_cids[1],
            "operation": "ARCHIVE_INVALID",
            "name": "Invalid Op Person",
            "city": "Austin",
            "salary": 60000.0,
            "version": 5,
            "event_timestamp": base_time.isoformat(),
        })
        expected["invalid_schema_or_values"] += 1

        # E. Negative salary
        events.append({
            "event_id": get_event_id(),
            "customer_id": existing_cids[2],
            "operation": "UPDATE",
            "name": customer_state[existing_cids[2]]["name"],
            "city": "Austin",
            "salary": -5000.0,
            "version": 10,
            "event_timestamp": base_time.isoformat(),
        })
        expected["invalid_schema_or_values"] += 1

        # F. Missing required field (missing customer_id)
        events.append({
            "event_id": get_event_id(),
            "customer_id": "",
            "operation": "INSERT",
            "name": "No ID Person",
            "city": "Denver",
            "salary": 75000.0,
            "version": 1,
            "event_timestamp": base_time.isoformat(),
        })
        expected["invalid_schema_or_values"] += 1

        # G. Missing event_id
        events.append({
            "event_id": "",
            "customer_id": "CUST-99999",
            "operation": "INSERT",
            "name": "No Event ID",
            "city": "Denver",
            "salary": 75000.0,
            "version": 1,
            "event_timestamp": base_time.isoformat(),
        })
        expected["invalid_schema_or_values"] += 1

        # H. Unknown reference (UPDATE on non-existent customer)
        events.append({
            "event_id": get_event_id(),
            "customer_id": "CUST-NONEXISTENT-999",
            "operation": "UPDATE",
            "name": "Ghost Customer",
            "city": "Seattle",
            "salary": 80000.0,
            "version": 1,
            "event_timestamp": base_time.isoformat(),
        })
        expected["unknown_references"] += 1

    expected["total_generated"] = len(events)
    return events, expected


def save_dataset(
    events: List[Dict[str, Any]],
    expected: Dict[str, Any],
    output_dir: Path,
    base_name: str = "customer_events",
) -> Tuple[Path, Path, Path]:
    """Saves generated dataset to CSV, JSON, and expected results summary."""
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / f"{base_name}.csv"
    json_path = output_dir / f"{base_name}.json"
    expected_path = output_dir / f"{base_name}_expected_results.json"

    # Write CSV
    if events:
        fieldnames = ["event_id", "customer_id", "operation", "name", "city", "salary", "version", "event_timestamp"]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(events)
    else:
        # Empty CSV
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            pass

    # Write JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2)

    # Write Expected Results
    with open(expected_path, "w", encoding="utf-8") as f:
        json.dump(expected, f, indent=2)

    return csv_path, json_path, expected_path


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic CDC test data.")
    parser.add_argument("--count", type=int, default=50, help="Number of records to generate.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility.")
    parser.add_argument("--outdir", type=str, default="data/input", help="Output directory.")
    parser.add_argument("--name", type=str, default="customer_events", help="Base file name.")
    args = parser.parse_args()

    out_path = Path(args.outdir)
    events, expected = generate_cdc_events(
        record_count=args.count,
        seed=args.seed,
        include_edge_cases=True,
    )
    csv_file, json_file, exp_file = save_dataset(events, expected, out_path, args.name)
    print(f"Generated {len(events)} events.")
    print(f"  CSV:      {csv_file}")
    print(f"  JSON:     {json_file}")
    print(f"  Expected: {exp_file}")


if __name__ == "__main__":
    main()

