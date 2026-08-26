# 🏦 Bancapp Financial Reconciliation Engine

A production-grade, deterministic financial reconciliation pipeline designed to automate the matching of internal ledger transactions against bank settlement files. Built for Bancapp Automation's Data Analyst assignment.

## Key Metrics

| Metric | Value |
|--------|-------|
| **Total Internal Transactions** | 616 |
| **Total Bank Lines** | 502 |
| **Internal Transactions Matched** | 509 (82.6%) |
| **Bank Lines Matched** | 443 (88.2%) |
| **Total Exceptions** | 188 |
| **May Backlog Cleared** | 22 items |
| **Execution Time** | ~1.5 seconds |

## Features

- **Multi-Pass Matching Engine**: Handles all 4 reconciliation cardinalities (1:1, 1:N, N:1, N:M)
- **Strict Consumption Control**: Prevents double-matching with `is_consumed` flags
- **Rolling Backlog Management**: Automatically clears previous month's unmatched items
- **Financial Precision**: Integer paise conversion eliminates floating-point errors
- **Exception Classification**: Intelligent categorization (Settlement Lag vs. Genuine Exceptions)
- **Audit Trail**: Unique `match_group_id` for complete traceability
- **Interactive Dashboard**: Professional HTML visualization of reconciliation results

## Quick Start

### Prerequisites
- Python 3.11+
- pip (Python package manager)

### Installation

```bash
# Clone the repository
git clone https://github.com/JaaniPorwal/Bancapp_Reconciliation.git
cd Bancapp_Reconciliation

# Install dependencies
pip install pandas numpy
```

### Usage

```bash
# Run the complete reconciliation pipeline
python run_reconciliation.py
```

Outputs will be generated in the `/output` directory:
- `reconciliation_output.csv` — unified match results
- `exception_report.csv` — categorized exceptions
- `backlog_report.csv` — May backlog status
- `summary_control_report.csv` — monthly metrics
- `reconciliation_dashboard.html` — interactive visualization

## Project Structure

```
Bancapp_Reconciliation/
├── src/
│   ├── validation.py          # Input data validation & integrity checks
│   ├── reconciliation.py      # Core multi-pass matching engine
│   └── __init__.py
├── data/
│   ├── internal_txns_may2026.csv
│   ├── bank_stmt_may2026.csv
│   ├── internal_txns_jun2026.csv
│   └── bank_stmt_jun2026.csv
├── output/
│   ├── reconciliation_output.csv
│   ├── exception_report.csv
│   ├── backlog_report.csv
│   ├── summary_control_report.csv
│   └── reconciliation_dashboard.html
├── tests/
│   ├── test_validation.py
│   └── test_reconciliation.py
├── docs/
│   └── WRITEUP.md              # Technical design documentation
├── generate_dashboard.py       # HTML dashboard generator
├── run_reconciliation.py       # Main pipeline orchestrator
└── README.md
```

## Technical Architecture

### Multi-Pass Matching Strategy

The engine uses a deterministic, prioritized matching approach to ensure accuracy and prevent false positives:

1. **Pass 1: Exact 1:1 Match**
   - Normalized reference + exact amount (in paise)
   - Strips UPI/NEFT prefixes, merchant IDs, and settlement keywords

2. **Pass 2: N:1 Batch Settlements**
   - Groups internal transactions by `batch_id`
   - Matches against single bank line containing batch reference
   - Allows variance for bank charges (marked as PARTIAL_MATCH)

3. **Pass 3: 1:N Partial Settlements**
   - Aggregates multiple bank lines (e.g., PART SETTLEMENT P1, P2, P3)
   - Strips `-P1`, `-P2` suffixes for normalization
   - Matches to single internal transaction when sums equal

4. **Pass 4: N:M Net Settlements**
   - Identifies "NET SETTLEMENT" bank lines
   - Extracts merchant ID and date from narration
   - Matches multiple internal txns to multiple bank lines

### Exception Classification Logic

Unmatched items are classified based on **ageing analysis**:

- **Settlement Lag** (≤45 days): Monitor for next settlement cycle
- **Genuine Exception** (>45 days): Escalate to operations team
- **Duplicate Bank Credit**: Multiple identical credits detected
- **Orphan Bank Credit**: No corresponding internal transaction
- **Internal Self-Netting**: SALE + REVERSAL pairs that net to zero

## Dashboard Preview

The pipeline generates an interactive HTML dashboard summarizing match rates, exceptions, and cardinality breakdowns.

### **Dashboard Overview**
<img width="1502" height="576" alt="dashboard-overview" src="https://github.com/user-attachments/assets/f81b2fdd-7467-44da-99c2-596315fd3b11" />


### **Reconciliation Status Summary**
<img width="1471" height="362" alt="dashboard-status-summary" src="https://github.com/user-attachments/assets/05f7dea5-a305-42d9-86b5-ad1c6b30779e" />


### **Matching Cardinality Distribution**
<img width="1482" height="622" alt="dashboard-cardinality" src="https://github.com/user-attachments/assets/4fa78d21-3933-4a88-8a27-c675b0b41ef6" />


### **Exception Breakdown**
<img width="1467" height="515" alt="dashboard-exceptions" src="https://github.com/user-attachments/assets/d89c3a37-8861-43ea-83dc-c36b539085ca" />


> Open `output/reconciliation_dashboard.html` in a browser after running the pipeline to view the live, interactive version.

## Results & Performance

### Reconciliation Status Summary (Unified Output View)
| Status | Count | Share |
|--------|-------|-------|
| **Matched** | 481 | 69.0% |
| **Exception** | 120 | 17.2% |
| **Open** | 68 | 9.8% |
| **Partial Match** | 28 | 4.0% |

### Matching Cardinality Distribution (Matched Only)
| Ratio | Count | Share |
|-------|-------|-------|
| 1:1 | 362 | 71.1% |
| 7:1 | 35 | 6.9% |
| 5:1 | 30 | 5.9% |
| 6:1 | 30 | 5.9% |
| 8:1 | 24 | 4.7% |
| 5:2 | 10 | 2.0% |
| 1:3 | 7 | 1.4% |
| 1:2 | 7 | 1.4% |
| 4:1 | 4 | 0.8% |

### Exception Breakdown (Total: 188)
| Category | Count | Severity |
|----------|-------|----------|
| Settlement Lag | 68 | Warning |
| Orphan Bank Credit | 59 | Warning |
| Genuine Exception | 39 | Danger |
| Duplicate Bank Credit | 22 | Danger |

### Key Achievements
* Fixed critical 1:N regex bug (strips "PART" and "-P1" suffixes)

* Eliminated match_group_id collisions between May/June

* Added comprehensive test coverage for edge cases

* Matched 509 of 616 internal transactions (82.6%) with zero false positives

* Built reproducible pipeline (runs clean from scratch)

## Testing

```bash
# Run all tests
python -m pytest -q

# Expected output: All tests pass
```

Key test cases:
- Reference normalization (PART SETTLEMENT PRMAY-P2 → PRMAY)
- Input validation (missing columns, invalid dates/amounts)
- Consumption control (no double-matching)

## Design Decisions

### Why Multi-Pass Instead of Single Join?
In financial reconciliation, **certainty matters more than speed**. A multi-pass approach ensures:
- Simple 1:1 matches are consumed first
- Complex N:M matches don't accidentally capture records that belong to simpler matches
- Zero false positives (critical for audit compliance)

### Why Integer Paise Conversion?
Floating-point arithmetic causes precision errors:

```python
# Problem: 100.10 + 0.01 = 100.10999999999999
# Solution: Convert to paise → 10010 + 1 = 10011
```

This ensures exact matching with zero tolerance for rounding errors.

### Why Rolling Backlog?
Settlement dates ≠ transaction dates. May transactions may settle in June. The pipeline:
1. Carries forward unmatched May items
2. Prioritizes "PREV CYCLE" bank lines to clear backlog
3. Only then processes fresh June transactions

## Alignment with Bancapp's Reconsyde Platform

This solution mirrors Bancapp's product philosophy:
- **Integrate** → Multiple data sources (internal + bank)
- **Reconcile** → Multi-pass matching with strict controls
- **Analyze** → Exception categorization + ageing + dashboard

## License
This project is submitted for Bancapp Automation's Data Analyst assignment.

## Author

### **Janvi Porwal**

**B.Tech – Artificial Intelligence & Data Science**

**SVKM's NMIMS, Indore**

[LinkedIn](https://www.linkedin.com/in/janvi-porwal) · [GitHub](https://github.com/JaaniPorwal)

---
