# Bancapp Assignment: Technical Write-up

**Candidate:** Janvi Porwal  
**Time Spent:** 3 hours 30 minutes  
**Execution Time:** ~1.5 seconds  

## 1. Executive Summary
This solution implements a deterministic, rule-based financial reconciliation engine. Rather than using black-box algorithms, it uses a prioritized, multi-pass rule engine. This ensures 100% auditability and prevents false-positive matches, which is critical in BFSI environments like Bancapp's Reconsyde platform.

## 2. Core Design Decisions

### A. Multi-Pass Deterministic Matching
The engine processes matches in order of highest certainty to prevent false positives:
1. **Pass 1: Exact 1:1** (Normalized Reference + Exact Amount).
2. **Pass 2: N:1 Batch Settlements** (Groups internal transactions by `batch_id` to match a single bank line, allowing for minor variances due to bank charges).
3. **Pass 3: 1:N Partial Settlements** (Aggregates multiple bank lines sharing a reference—stripping 'PART' and '-P1' suffixes—to match a single internal transaction).
4. **Pass 4: N:M Net Settlements** (Matches "NET SETTLEMENT" bank lines to the sum of unconsumed internal transactions for a specific merchant/date).

### B. Strict Consumption Control
To prevent double-counting, the engine maintains `is_consumed` flags. Once a record is assigned to a `match_group_id`, it is locked. The `match_group_id` counter is threaded across months to prevent May/June ID collisions.

### C. Integer Paise Conversion
All amounts are converted to integer paise (`amount * 100`) before matching. This eliminates floating-point precision errors (e.g., `100.10` becoming `100.0999999`).

### D. Rolling Backlog (May → June)
The system handles settlement lag. Unsettled May transactions are carried forward. During June processing, the engine specifically looks for bank lines tagged "PREV CYCLE" to clear the May backlog before processing fresh June transactions.

## 3. Exception Management & Ageing
Records failing all passes are classified into actionable categories based on a 45-day ageing threshold:
- **DUPLICATE_BANK_CREDIT:** Multiple identical bank credits.
- **ORPHAN_BANK_CREDIT:** Bank credits with no internal ledger entry.
- **INTERNAL_SELF_NETTING:** Internal SALE and REVERSAL transactions netting to zero.
- **SETTLEMENT_LAG:** Unsettled items <= 45 days old (Monitor next cycle).
- **GENUINE_EXCEPTION:** Unsettled items > 45 days old (Escalate to Ops).

## 4. Auditability
Every match is assigned a unique `match_group_id`. An auditor can trace any bank line back to the specific internal transactions, the matching rule applied, and the variance (reported in consistent INR units).

## 5. Output Format Design (Task 4)

### Flat Table vs. Parent-Child Structure
For this assignment, I chose a **hybrid approach** that serves both operational and audit needs:

**Flat Table (`reconciliation_output.csv`):**
- **Best for:** Operations team filtering and daily triage.
- **Why:** Ops users need to quickly filter by `status` (EXCEPTION, OPEN, MATCHED) and `exception_category` without navigating nested structures.
- **Trade-off:** Some redundancy (e.g., `match_group_id` repeated for each row in an N:1 group), but this enables easy Excel filtering and pivot tables.

**Parent-Child Structure (via `match_group_id`):**
- **Best for:** Auditors and reconciliation verification.
- **Why:** An auditor can trace a single `match_group_id` (e.g., MG00176) and see all internal transactions, all bank lines, the total amounts, and the cardinality (e.g., 7:1 for batch settlements). This proves every rupee ties out at the group level.

### Cardinality-Specific Output Considerations
- **1:1 Matches:** Simple flat row is sufficient (internal_txn_id ↔ bank_line_id).
- **1:N Partial Settlements:** Bank line IDs are comma-separated in a single row for readability.
- **N:1 Batch Settlements:** Internal transaction IDs are listed in multiple rows sharing the same `match_group_id`, allowing auditors to verify the batch total.
- **N:M Net Settlements:** Both sides use comma-separated lists, with `match_group_id` as the primary traceability key.

This design balances **operational efficiency** (flat, filterable CSV) with **audit compliance** (traceable via match_group_id).