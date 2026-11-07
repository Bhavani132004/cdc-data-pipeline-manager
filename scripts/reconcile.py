"""
Data Quality and Reconciliation Engine for CDC Data Pipeline.
Validates database integrity, event accounting, version consistency, and quarantine traceability.
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List

# Add parent directory to sys.path so it runs standalone
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import AppConfig
from src.database import (
    DatabaseManager,
    CurrentCustomer,
    CustomerHistory,
    RejectedRecord,
    PipelineRun,
    ProcessedFile,
)
from sqlalchemy import func, select


class ReconciliationChecker:
    """Performs deep data quality and integrity checks against the CDC database."""

    def __init__(self, config: AppConfig, db_manager: DatabaseManager):
        self.config = config
        self.db = db_manager

    def run_checks(self) -> Dict[str, Any]:
        results: List[Dict[str, Any]] = []

        with self.db.session_scope() as session:
            # Check 1: Unique customer IDs in current_customers
            total_cust = session.query(func.count(CurrentCustomer.customer_id)).scalar() or 0
            distinct_cust = session.query(func.count(func.distinct(CurrentCustomer.customer_id))).scalar() or 0
            c1_pass = total_cust == distinct_cust
            results.append({
                "check_name": "Unique Customer IDs",
                "status": "PASS" if c1_pass else "FAIL",
                "details": f"Total rows: {total_cust}, Distinct customer IDs: {distinct_cust}",
                "passed": c1_pass,
            })

            # Check 2: Unique event IDs in customer_history
            total_hist = session.query(func.count(CustomerHistory.event_id)).scalar() or 0
            distinct_hist = session.query(func.count(func.distinct(CustomerHistory.event_id))).scalar() or 0
            c2_pass = total_hist == distinct_hist
            results.append({
                "check_name": "Unique Historical Event IDs",
                "status": "PASS" if c2_pass else "FAIL",
                "details": f"Total historical events: {total_hist}, Distinct event IDs: {distinct_hist}",
                "passed": c2_pass,
            })

            # Check 3: Current State Version Consistency
            # For each current customer, their version should equal the max applied version in customer_history
            version_mismatches = 0
            all_customers = session.query(CurrentCustomer).all()
            for cust in all_customers:
                max_ver = (
                    session.query(func.max(CustomerHistory.version))
                    .filter(CustomerHistory.customer_id == cust.customer_id)
                    .filter(CustomerHistory.event_status == "APPLIED")
                    .scalar()
                )
                if max_ver is not None and cust.version != max_ver:
                    version_mismatches += 1

            c3_pass = version_mismatches == 0
            results.append({
                "check_name": "Current State Version Consistency",
                "status": "PASS" if c3_pass else "FAIL",
                "details": f"Version mismatches between current state and applied history: {version_mismatches}",
                "passed": c3_pass,
            })

            # Check 4: Deletion Status Accuracy
            # If the last applied event was DELETE, is_deleted must be True; if INSERT/UPDATE, False
            deletion_mismatches = 0
            for cust in all_customers:
                last_hist = (
                    session.query(CustomerHistory)
                    .filter(CustomerHistory.event_id == cust.last_event_id)
                    .first()
                )
                if last_hist:
                    expected_deleted = (last_hist.operation == "DELETE")
                    if cust.is_deleted != expected_deleted:
                        deletion_mismatches += 1

            c4_pass = deletion_mismatches == 0
            results.append({
                "check_name": "Soft-Deletion State Integrity",
                "status": "PASS" if c4_pass else "FAIL",
                "details": f"Customers with mismatched deletion flag: {deletion_mismatches}",
                "passed": c4_pass,
            })

            # Check 5: Quarantine Traceability
            # Every rejected record must have a non-empty rejection reason and original payload
            invalid_rejections = (
                session.query(func.count(RejectedRecord.reject_id))
                .filter(
                    (RejectedRecord.rejection_reason == None) |
                    (RejectedRecord.rejection_reason == "") |
                    (RejectedRecord.original_payload == None) |
                    (RejectedRecord.original_payload == "")
                )
                .scalar() or 0
            )
            c5_pass = invalid_rejections == 0
            results.append({
                "check_name": "Quarantine Audit Traceability",
                "status": "PASS" if c5_pass else "FAIL",
                "details": f"Rejected records missing reasons or payloads: {invalid_rejections}",
                "passed": c5_pass,
            })

            # Check 6: Pipeline Run Accounting Conservation
            # For each completed run: total_input == valid_count + duplicate_count + rejected_count
            accounting_failures = 0
            runs = session.query(PipelineRun).filter(PipelineRun.status == "COMPLETED").all()
            for r in runs:
                sum_parts = r.valid_count + r.duplicate_count + r.rejected_count
                if r.total_input != sum_parts:
                    accounting_failures += 1

            c6_pass = accounting_failures == 0
            results.append({
                "check_name": "Event Accounting Conservation (Input = Valid + Dup + Rej)",
                "status": "PASS" if c6_pass else "FAIL",
                "details": f"Runs failing exact event accounting: {accounting_failures} (out of {len(runs)} runs)",
                "passed": c6_pass,
            })

            # Check 7: Payload Hash Completeness
            missing_hashes = (
                session.query(func.count(CustomerHistory.event_id))
                .filter((CustomerHistory.payload_hash == None) | (CustomerHistory.payload_hash == ""))
                .scalar() or 0
            )
            c7_pass = missing_hashes == 0
            results.append({
                "check_name": "Payload Hash Cryptographic Integrity",
                "status": "PASS" if c7_pass else "FAIL",
                "details": f"Historical events missing SHA-256 payload hash: {missing_hashes}",
                "passed": c7_pass,
            })

        overall_pass = all(r["passed"] for r in results)

        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": "PASS" if overall_pass else "FAIL",
            "total_checks": len(results),
            "passed_checks": sum(1 for r in results if r["passed"]),
            "failed_checks": sum(1 for r in results if not r["passed"]),
            "checks": results,
        }

        return report

    def generate_markdown_report(self, report_data: Dict[str, Any]) -> str:
        lines = [
            "# CDC Pipeline Reconciliation & Data Quality Report",
            f"**Generated:** {report_data['timestamp']}  ",
            f"**Overall Status:** **`{report_data['overall_status']}`**  ",
            f"**Passed:** {report_data['passed_checks']}/{report_data['total_checks']} Checks",
            "",
            "## Data Quality Audit Results",
            "",
            "| Check Name | Status | Details |",
            "|---|:---:|---|",
        ]
        for c in report_data["checks"]:
            status_badge = "✅ PASS" if c["passed"] else "❌ FAIL"
            lines.append(f"| {c['check_name']} | {status_badge} | {c['details']} |")

        lines.extend([
            "",
            "## Summary of Rules Checked",
            "1. **Unique Customer IDs**: Primary key uniqueness in `current_customers`.",
            "2. **Unique Historical Event IDs**: Strict uniqueness in `customer_history`.",
            "3. **Version Consistency**: Current state version matches highest applied version.",
            "4. **Soft Deletion State**: Flag matches last applied operation.",
            "5. **Quarantine Auditability**: Every rejected record retains raw payload and failure reason.",
            "6. **Event Accounting Conservation**: `total_input == valid_count + duplicate_count + rejected_count`.",
            "7. **Cryptographic Integrity**: SHA-256 payload hashes populated for all events.",
        ])

        return "\n".join(lines)


def run_reconciliation():
    config = AppConfig.load()
    db_manager = DatabaseManager(config.db_url)
    db_manager.init_db()
    checker = ReconciliationChecker(config, db_manager)
    report = checker.run_checks()

    # Save JSON report
    report_json_path = config.reports_dir / "reconciliation_report.json"
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    # Save Markdown report
    md_content = checker.generate_markdown_report(report)
    report_md_path = config.reports_dir / "reconciliation_report.md"
    with open(report_md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"\n--- RECONCILIATION RESULT: [{report['overall_status']}] ---")
    print(f"Passed {report['passed_checks']} of {report['total_checks']} checks.")
    for c in report["checks"]:
        print(f"  [{c['status']}] {c['check_name']}: {c['details']}")
    print(f"\nReports saved to:")
    print(f"  JSON: {report_json_path}")
    print(f"  MD:   {report_md_path}\n")

    return report["overall_status"] == "PASS"


if __name__ == "__main__":
    success = run_reconciliation()
    sys.exit(0 if success else 1)
