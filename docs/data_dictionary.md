# CDC Data Pipeline Manager - Data Dictionary

This document details the relational database schema, data types, primary and foreign keys, indexing strategies, constraints, and business rules for the **CDC Data Pipeline Manager**.

---

## 1. `current_customers`

Maintains the latest valid representation of each customer in the system. Rows in this table represent the authoritative current snapshot.

| Column Name | SQL Type | Nullable | Key / Index | Description | Business Rules & Constraints |
|---|---|---|---|---|---|
| `customer_id` | VARCHAR(64) | NO | PRIMARY KEY | Unique business identifier for a customer | Must be non-empty string. One row per customer. |
| `name` | VARCHAR(255) | NO | None | Full legal customer name | Mandatory for active customers. Cannot be blank. |
| `city` | VARCHAR(100) | NO | INDEX | Normalized customer location | Normalized to title case. Mandatory for active customers. |
| `salary` | REAL / FLOAT | NO | None | Customer annual compensation | Must be non-negative numeric value (`>= 0.00`). |
| `version` | INTEGER | NO | None | Current monotonically increasing state version | Must be `>= 1`. Only newer versions can overwrite current state. |
| `is_deleted` | BOOLEAN | NO | INDEX | Soft-deletion indicator flag | `0` = Active, `1` = Soft-deleted. Soft-deleted rows are retained for referential integrity. |
| `last_event_id` | VARCHAR(64) | NO | None | ID of the last applied event that set this state | Traceability to `customer_history.event_id`. |
| `last_event_timestamp`| VARCHAR(32) | NO | None | Source timestamp of the last applied event | ISO-8601 string. Used in tie-breaking resolution. |
| `updated_at` | VARCHAR(32) | NO | None | System timestamp of state modification | UTC ISO-8601 timestamp generated at ingestion time. |

---

## 2. `customer_history`

Preserves an immutable audit trail of every valid event processed by the CDC pipeline, including out-of-order events.

| Column Name | SQL Type | Nullable | Key / Index | Description | Business Rules & Constraints |
|---|---|---|---|---|---|
| `event_id` | VARCHAR(64) | NO | PRIMARY KEY / UNIQUE | Unique identifier for the CDC event | Uniquely identifies each event across all runs. Duplicate identical IDs are skipped; conflicting payloads quarantined. |
| `customer_id` | VARCHAR(64) | NO | INDEX | Targeted customer identifier | References customer being created, modified, or soft-deleted. |
| `operation` | VARCHAR(16) | NO | None | CDC operation type | Restricted to `INSERT`, `UPDATE`, `DELETE`. |
| `name` | VARCHAR(255) | YES | None | Customer name at time of event | Nullable for DELETE operations. |
| `city` | VARCHAR(100) | YES | None | Customer city at time of event | Nullable for DELETE operations. |
| `salary` | REAL / FLOAT | YES | None | Customer salary at time of event | Nullable for DELETE operations. |
| `version` | INTEGER | NO | None | Source record version | Integer `>= 1`. Indicates temporal progression. |
| `event_timestamp` | VARCHAR(32) | NO | INDEX | Source event creation timestamp | ISO-8601 format. Secondary ordering key. |
| `source_file` | VARCHAR(255) | NO | None | Originating file name | Audits source provenance. |
| `run_id` | VARCHAR(64) | NO | INDEX | Pipeline batch execution identifier | Links to `pipeline_runs.run_id`. |
| `processed_at` | VARCHAR(32) | NO | None | Timestamp when pipeline processed event | UTC ISO-8601 timestamp. |
| `event_status` | VARCHAR(32) | NO | None | Processing categorization status | `APPLIED` (mutated current state) or `SUPERSEDED_OUT_OF_ORDER` (recorded in history only). |
| `payload_hash` | VARCHAR(64) | NO | INDEX | Cryptographic SHA-256 canonical payload hash | Hash of canonical event string used for idempotency and duplicate detection. |

---

## 3. `rejected_records`

Quarantine table storing malformed, schema-violating, or conflicting records that could not be applied.

| Column Name | SQL Type | Nullable | Key / Index | Description | Business Rules & Constraints |
|---|---|---|---|---|---|
| `reject_id` | INTEGER | NO | PRIMARY KEY (AUTOINCREMENT) | Surrogate rejection sequence number | Monotonically increasing integer. |
| `event_id` | VARCHAR(64) | YES | INDEX | Event ID extracted from raw payload (if present)| Nullable if event_id was missing or unparseable. |
| `customer_id` | VARCHAR(64) | YES | INDEX | Customer ID extracted from payload (if present)| Nullable if customer_id was missing or unparseable. |
| `source_file` | VARCHAR(255) | NO | None | Source file containing rejected record | Provenance audit tracking. |
| `run_id` | VARCHAR(64) | NO | INDEX | Pipeline execution run identifier | Links to `pipeline_runs.run_id`. |
| `rejection_reason`| VARCHAR(255) | NO | None | Explicit reason code and failure description | Examples: `MISSING_CUSTOMER_ID`, `INVALID_SALARY`, `UNKNOWN_REFERENCE`, `CONFLICTING_EVENT_ID`. |
| `original_payload`| TEXT | NO | None | Verbatim serialized payload string | Complete raw JSON/string of the offending record for manual or automated replay. |
| `rejected_at` | VARCHAR(32) | NO | None | Timestamp of quarantine event | UTC ISO-8601 string. |

---

## 4. `pipeline_runs`

Operational metadata and performance metrics for every batch execution.

| Column Name | SQL Type | Nullable | Key / Index | Description |
|---|---|---|---|---|
| `run_id` | VARCHAR(64) | NO | PRIMARY KEY | Unique identifier for the pipeline execution run (e.g. `run_a1b2c3d4e5`). |
| `source_file` | VARCHAR(255) | NO | None | File name or stream identifier ingested. |
| `start_time` | VARCHAR(32) | NO | None | Pipeline start timestamp (UTC ISO-8601). |
| `end_time` | VARCHAR(32) | YES | None | Pipeline completion timestamp (UTC ISO-8601). |
| `status` | VARCHAR(32) | NO | None | Outcome: `RUNNING`, `COMPLETED`, `FAILED`. |
| `total_input` | INTEGER | NO | None | Total count of raw records read from source file. |
| `valid_count` | INTEGER | NO | None | Count of records that passed validation and were accepted. |
| `inserted_count` | INTEGER | NO | None | Number of new customers added to `current_customers`. |
| `updated_count` | INTEGER | NO | None | Number of existing customers updated in `current_customers`. |
| `deleted_count` | INTEGER | NO | None | Number of customers soft-deleted in `current_customers`. |
| `duplicate_count` | INTEGER | NO | None | Count of identical duplicate events skipped idempotently. |
| `rejected_count` | INTEGER | NO | None | Count of records quarantined into `rejected_records`. |
| `late_event_count`| INTEGER | NO | None | Count of out-of-order/late events preserved in history without mutating current state. |
| `error_message` | TEXT | YES | None | Stack trace or summary error if run failed. |
| `execution_time_seconds`| REAL | NO | None | Total wall-clock execution duration in seconds. |

---

## 5. `processed_files`

Registry of ingested files and SHA-256 cryptographic digests ensuring idempotent reprocessing.

| Column Name | SQL Type | Nullable | Key / Index | Description |
|---|---|---|---|---|
| `source_file` | VARCHAR(255) | NO | PRIMARY KEY | Base name of the input file. |
| `file_hash` | VARCHAR(64) | NO | INDEX | SHA-256 cryptographic checksum of complete file contents. |
| `first_run_id` | VARCHAR(64) | NO | None | Pipeline `run_id` when file was initially ingested. |
| `processed_at` | VARCHAR(32) | NO | None | UTC timestamp of last ingestion attempt. |
| `processing_status`| VARCHAR(32) | NO | None | Status of file processing (`COMPLETED` or `FAILED`). |

