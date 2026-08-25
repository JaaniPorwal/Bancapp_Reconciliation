# Bancapp Assignment: Technical Write-up
**Candidate:** Janvi Porwal  
**Time Spent:** [INSERT YOUR ACTUAL TIME HERE, e.g., 4 hours 15 minutes]  
**Execution Time:** ~1.5 seconds  

## 1. Executive Summary
This solution implements a deterministic, rule-based financial reconciliation engine. Rather than using black-box algorithms, it uses a prioritized, multi-pass rule engine. This ensures 100% auditability and prevents false-positive matches, which is critical in BFSI environments like Bancapp's Reconsyde platform.

## 2. Core Design Decisions

### A. Multi-Pass Deterministic Matching
The engine processes matches in order of highest certainty:
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
Records failing all passes are classified into actionable categories:
- **DUPLICATE_BANK_CREDIT:** Multiple identical bank credits.
- **ORPHAN_BANK_CREDIT:** Bank credits with no internal ledger entry.
- **INTERNAL_SELF_NETTING:** Internal SALE and REVERSAL transactions netting to zero.
- **SETTLEMENT_LAG:** Unsettled items <= 45 days old (Monitor next cycle).
- **GENUINE_EXCEPTION:** Unsettled items > 45 days old (Escalate to Ops).

## 4. Auditability
Every match is assigned a unique `match_group_id`. An auditor can trace any bank line back to the specific internal transactions, the matching rule applied, and the variance (reported in consistent INR units).