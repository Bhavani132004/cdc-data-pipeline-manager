# CDC Pipeline Reconciliation & Data Quality Report
**Generated:** 2026-11-07T09:16:33.102835+00:00  
**Overall Status:** **`PASS`**  
**Passed:** 7/7 Checks

## Data Quality Audit Results

| Check Name | Status | Details |
|---|:---:|---|
| Unique Customer IDs | ✅ PASS | Total rows: 25, Distinct customer IDs: 25 |
| Unique Historical Event IDs | ✅ PASS | Total historical events: 45, Distinct event IDs: 45 |
| Current State Version Consistency | ✅ PASS | Version mismatches between current state and applied history: 0 |
| Soft-Deletion State Integrity | ✅ PASS | Customers with mismatched deletion flag: 0 |
| Quarantine Audit Traceability | ✅ PASS | Rejected records missing reasons or payloads: 0 |
| Event Accounting Conservation (Input = Valid + Dup + Rej) | ✅ PASS | Runs failing exact event accounting: 0 (out of 2 runs) |
| Payload Hash Cryptographic Integrity | ✅ PASS | Historical events missing SHA-256 payload hash: 0 |

## Summary of Rules Checked
1. **Unique Customer IDs**: Primary key uniqueness in `current_customers`.
2. **Unique Historical Event IDs**: Strict uniqueness in `customer_history`.
3. **Version Consistency**: Current state version matches highest applied version.
4. **Soft Deletion State**: Flag matches last applied operation.
5. **Quarantine Auditability**: Every rejected record retains raw payload and failure reason.
6. **Event Accounting Conservation**: `total_input == valid_count + duplicate_count + rejected_count`.
7. **Cryptographic Integrity**: SHA-256 payload hashes populated for all events.