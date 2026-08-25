# Bancapp Financial Reconciliation Engine

A deterministic, rule-based financial reconciliation pipeline designed to automate the matching of internal ledger transactions against bank settlement files. Built for the Bancapp Automation Data Analyst assignment.

## 🚀 How to Run
1. Ensure Python 3.11+ is installed.
2. Install dependencies: `pip install pandas numpy`
3. Run the pipeline: `python run_reconciliation.py`
4. View outputs in the `/output` directory. (The dashboard is generated automatically).

## 📁 Project Structure
- `src/validation.py`: Input data validation and integrity checks.
- `src/reconciliation.py`: The core multi-pass matching engine.
- `generate_dashboard.py`: Generates the HTML summary report.
- `data/`: Input CSV files (May and June).
- `output/`: Generated reconciliation, exception, and control reports.
- `docs/WRITEUP.md`: Detailed technical design and business logic decisions.

## 📊 Key Features
- **Multi-Pass Matching:** 1:1, N:1 (Batch), 1:N (Partial), N:M (Net Settlement).
- **Strict Controls:** Prevents double-consumption of transactions.
- **Rolling Backlog:** Automatically clears previous month's unmatched items using "PREV CYCLE" bank lines.
- **Financial Precision:** Uses integer paise to eliminate floating-point errors.