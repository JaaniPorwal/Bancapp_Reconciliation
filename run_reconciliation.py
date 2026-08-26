import time
import pandas as pd
import os
from src.validation import validate_all_inputs
from src.reconciliation import execute_reconciliation
from generate_dashboard import generate_html_dashboard # FIX #6: Wire in dashboard

def generate_outputs(results):
    os.makedirs("output", exist_ok=True)
    flat_reco = []
    
    for group in results['match_groups']:
        int_ids = group['internal_txn_ids']
        bank_ids = group['bank_line_ids']
        int_amts = group['internal_amounts']
        bank_amts = group['bank_amounts']
        for i, (i_id, i_amt) in enumerate(zip(int_ids, int_amts)):
            flat_reco.append({
                'match_group_id': group['match_group_id'], 'cardinality': group['cardinality'],
                'match_method': group['match_method'], 'status': group['status'],
                'variance_inr': group['variance_paise'] / 100.0, # FIX: Consistent units
                'internal_txn_id': i_id, 'internal_amount': i_amt,
                'bank_line_id': ", ".join(bank_ids), 'bank_amount': ", ".join([str(b) for b in bank_amts])
            })

    for exc in results['exceptions']:
        flat_reco.append({
            'match_group_id': '', 'cardinality': '', 'match_method': 'Exception Classification',
            'status': exc['status'], 'variance_inr': 0,
            'internal_txn_id': exc['id'] if exc['type'] == 'internal' else '',
            'internal_amount': exc['amount'] if exc['type'] == 'internal' else 0,
            'bank_line_id': exc['id'] if exc['type'] == 'bank' else '',
            'bank_amount': exc['amount'] if exc['type'] == 'bank' else 0
        })
    pd.DataFrame(flat_reco).to_csv("output/reconciliation_output.csv", index=False)
    pd.DataFrame(results['exceptions']).to_csv("output/exception_report.csv", index=False)
    pd.DataFrame(results['backlog_details']).to_csv("output/backlog_report.csv", index=False) # FIX #5: Now has classification
    
    def get_month_stats(int_df, bank_df, month):
        matched_int = int_df[int_df['is_consumed']]
        matched_bank = bank_df[bank_df['is_consumed']]
        return [
            {'month': month, 'metric': 'Total Internal Txns', 'count': len(int_df), 'amount_inr': int_df['amount'].sum()},
            {'month': month, 'metric': 'Total Bank Lines', 'count': len(bank_df), 'amount_inr': bank_df['amount'].sum()},
            {'month': month, 'metric': 'Matched Internal', 'count': len(matched_int), 'amount_inr': matched_int['amount'].sum()},
            {'month': month, 'metric': 'Matched Bank', 'count': len(matched_bank), 'amount_inr': matched_bank['amount'].sum()},
        ]
    summary = get_month_stats(results['int_may'], results['bank_may'], 'May')
    summary += get_month_stats(results['int_jun'], results['bank_jun'], 'June')
    summary.append({'month': 'Overall', 'metric': 'May Backlog Cleared in June', 'count': results['may_backlog_cleared'], 'amount_inr': 0})
    pd.DataFrame(summary).to_csv("output/summary_control_report.csv", index=False)

def main():
    os.makedirs("output", exist_ok=True) # FIX #1: Prevent crash on clean run
    print("Starting Bancapp Reconciliation Pipeline...")
    start_time = time.perf_counter()
    
    print("Validating inputs...")
    dataframes, validation_report = validate_all_inputs("data")
    validation_report.to_csv("output/input_validation_report.csv", index=False)
    if len(dataframes) < 4:
        print("ERROR: Not all input files could be loaded."); return
        
    print("Running reconciliation engine...")
    results = execute_reconciliation(dataframes)
    
    print("Generating output reports...")
    generate_outputs(results)
    
    print("Generating dashboard...")
    generate_html_dashboard() # FIX #6: Auto-generate dashboard
    
    end_time = time.perf_counter()
    print(f"\n✅ Reconciliation completed in {end_time - start_time:.4f} seconds")

if __name__ == "__main__":
    main()