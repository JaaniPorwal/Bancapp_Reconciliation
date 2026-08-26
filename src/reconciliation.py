import pandas as pd
import numpy as np
import re
from collections import defaultdict
from datetime import datetime

def normalize_reference(ref):
    if pd.isna(ref): return ""
    s = str(ref).upper().strip()
    s = re.sub(r'^(UPI|IMPS|NEFT|RTGS|NACH|CARD)/', '', s)
    s = re.sub(r'SETTLE/|SETTLEMENT\s+|PART\s+', '', s) # FIX #2: Added PART\s+
    s = re.sub(r'/M\d+.*$', '', s)
    s = re.sub(r'PREV\s+CYCLE', '', s)
    s = re.sub(r'-P\d+$', '', s) # FIX #2: Strip -P1, -P2 suffixes
    s = re.sub(r'\s+', '', s)
    return s

def extract_date_from_narration(narration):
    match = re.search(r'(\d{4}-\d{2}-\d{2})', str(narration))
    return match.group(1) if match else None

def preprocess_data(internal_df, bank_df):
    internal_df = internal_df.copy()
    internal_df['amount_paise'] = (internal_df['amount'].astype(float) * 100).round().astype(int)
    internal_df['norm_ref'] = internal_df['payment_ref'].apply(normalize_reference)
    internal_df['is_consumed'] = False
    
    bank_df = bank_df.copy()
    bank_df['amount_paise'] = (bank_df['amount'].astype(float) * 100).round().astype(int)
    bank_df['norm_narration'] = bank_df['narration'].apply(normalize_reference)
    bank_df['is_consumed'] = False
    bank_df['extracted_batch'] = bank_df['narration'].str.extract(r'(BATCH[A-Z0-9]+)', expand=False).fillna('')
    bank_df['narration_date'] = bank_df['narration'].apply(extract_date_from_narration)
    
    return internal_df, bank_df

def run_matching_passes(internal_df, bank_df, start_counter=1):
    match_groups = []
    group_id_counter = start_counter # FIX #3: Accept start counter
    
    def create_group(int_indices, bank_indices, method, status, variance=0):
        nonlocal group_id_counter
        mg_id = f"MG{str(group_id_counter).zfill(5)}"
        group_id_counter += 1
        
        int_ids = [internal_df.loc[i, 'txn_id'] for i in int_indices]
        bank_ids = [bank_df.loc[i, 'line_id'] for i in bank_indices]
        int_amts = [internal_df.loc[i, 'amount'] for i in int_indices]
        bank_amts = [bank_df.loc[i, 'amount'] for i in bank_indices]
        
        group = {
            'match_group_id': mg_id, 'cardinality': f"{len(int_indices)}:{len(bank_indices)}",
            'match_method': method, 'status': status, 'variance_paise': variance,
            'internal_txn_ids': int_ids, 'bank_line_ids': bank_ids,
            'internal_amounts': int_amts, 'bank_amounts': bank_amts
        }
        match_groups.append(group)
        internal_df.loc[list(int_indices), 'is_consumed'] = True
        bank_df.loc[list(bank_indices), 'is_consumed'] = True

    avail_int = internal_df[~internal_df['is_consumed']].index
    avail_bank = bank_df[~bank_df['is_consumed']].index

    # PASS 1: Exact 1:1
    bank_lookup = defaultdict(list)
    for idx in avail_bank:
        key = (bank_df.loc[idx, 'norm_narration'], bank_df.loc[idx, 'amount_paise'])
        bank_lookup[key].append(idx)

    for idx in avail_int:
        if internal_df.loc[idx, 'is_consumed']: continue
        ref = internal_df.loc[idx, 'norm_ref']
        amt = internal_df.loc[idx, 'amount_paise']
        if not ref: continue
        
        candidates = bank_lookup.get((ref, amt), [])
        valid_candidates = [b_idx for b_idx in candidates if not bank_df.loc[b_idx, 'is_consumed']]
        if len(valid_candidates) == 1:
            create_group([idx], valid_candidates, "Exact 1:1 (Ref+Amt)", "MATCHED")

    avail_int = internal_df[~internal_df['is_consumed']].index
    avail_bank = bank_df[~bank_df['is_consumed']].index

    # PASS 2: N:1 Batch
    int_by_batch = defaultdict(list)
    for idx in avail_int:
        batch = internal_df.loc[idx, 'batch_id']
        if pd.notna(batch) and str(batch).strip() != '':
            int_by_batch[str(batch).strip()].append(idx)

    for batch_id, int_indices in int_by_batch.items():
        bank_matches = [b_idx for b_idx in avail_bank if batch_id in bank_df.loc[b_idx, 'extracted_batch'] and not bank_df.loc[b_idx, 'is_consumed']]
        if len(bank_matches) == 1:
            b_idx = bank_matches[0]
            int_sum = internal_df.loc[int_indices, 'amount_paise'].sum()
            bank_amt = bank_df.loc[b_idx, 'amount_paise']
            variance = bank_amt - int_sum
            create_group(int_indices, bank_matches, f"N:1 Batch ({batch_id})", "MATCHED" if variance == 0 else "PARTIAL_MATCH", variance)

    avail_int = internal_df[~internal_df['is_consumed']].index
    avail_bank = bank_df[~bank_df['is_consumed']].index

    # PASS 3: 1:N Partial (Now works because of regex fix)
    bank_by_ref = defaultdict(list)
    for idx in avail_bank:
        ref = bank_df.loc[idx, 'norm_narration']
        if ref: bank_by_ref[ref].append(idx)

    for ref, bank_indices in bank_by_ref.items():
        valid_bank = [b for b in bank_indices if not bank_df.loc[b, 'is_consumed']]
        if len(valid_bank) <= 1: continue 
        
        int_matches = [i for i in avail_int if internal_df.loc[i, 'norm_ref'] == ref and not internal_df.loc[i, 'is_consumed']]
        if len(int_matches) == 1:
            i_idx = int_matches[0]
            bank_sum = bank_df.loc[valid_bank, 'amount_paise'].sum()
            int_amt = internal_df.loc[i_idx, 'amount_paise']
            if bank_sum == int_amt:
                create_group([i_idx], valid_bank, "1:N Partial Settlement", "MATCHED", 0)

    avail_int = internal_df[~internal_df['is_consumed']].index
    avail_bank = bank_df[~bank_df['is_consumed']].index

    # PASS 4: N:M Net Settlements
    net_bank_groups = defaultdict(list)
    for idx in avail_bank:
        if 'NET SETTLEMENT' in str(bank_df.loc[idx, 'narration']).upper():
            merch_match = re.search(r'(M\d+)', str(bank_df.loc[idx, 'narration']).upper())
            narr_date = bank_df.loc[idx, 'narration_date']
            if merch_match and narr_date:
                net_bank_groups[(merch_match.group(1), narr_date)].append(idx)

    for (merch_id, narr_date), bank_indices in net_bank_groups.items():
        valid_bank = [b for b in bank_indices if not bank_df.loc[b, 'is_consumed']]
        if not valid_bank: continue
        int_candidates = [i for i in avail_int if internal_df.loc[i, 'merchant_id'] == merch_id and str(internal_df.loc[i, 'txn_date'])[:10] == narr_date and not internal_df.loc[i, 'is_consumed']]
        if not int_candidates: continue
        if bank_df.loc[valid_bank, 'amount_paise'].sum() == internal_df.loc[int_candidates, 'amount_paise'].sum():
            create_group(int_candidates, valid_bank, f"N:M Net Settlement ({merch_id})", "MATCHED")

    return match_groups, internal_df, bank_df, group_id_counter # FIX #3: Return updated counter

def classify_exceptions(internal_df, bank_df, month, reference_date):
    exceptions = []
    avail_int = internal_df[~internal_df['is_consumed']]
    avail_bank = bank_df[~bank_df['is_consumed']]
    
    # FIX #4: Better Self-Netting Logic
    for merch in avail_int['merchant_id'].unique():
        merch_txns = avail_int[avail_int['merchant_id'] == merch]
        sales = merch_txns[merch_txns['txn_type'] == 'SALE']
        reversals = merch_txns[merch_txns['txn_type'].isin(['REVERSAL', 'REFUND'])]
        
        for _, rev in reversals.iterrows():
            matching_sale = sales[sales['amount_paise'] == abs(rev['amount_paise'])]
            if len(matching_sale) > 0:
                sale_idx = matching_sale.index[0]
                for idx in [sale_idx, rev.name]:
                    exceptions.append({
                        'id': internal_df.loc[idx, 'txn_id'], 'type': 'internal',
                        'exception_category': 'INTERNAL_SELF_NETTING', 'amount': internal_df.loc[idx, 'amount'],
                        'variance': 0, 'ageing_days': 0, 'recommended_action': 'Auto-netted.',
                        'month': month, 'status': 'EXCEPTION'
                    })
                    internal_df.loc[idx, 'is_consumed'] = True

    avail_bank = bank_df[~bank_df['is_consumed']]
    dup_refs = avail_bank[avail_bank.duplicated(subset=['norm_narration', 'amount_paise'], keep=False)]
    for idx in dup_refs.index:
        exceptions.append({'id': bank_df.loc[idx, 'line_id'], 'type': 'bank', 'exception_category': 'DUPLICATE_BANK_CREDIT', 'amount': bank_df.loc[idx, 'amount'], 'variance': 0, 'ageing_days': 0, 'recommended_action': 'Investigate.', 'month': month, 'status': 'EXCEPTION'})
        bank_df.loc[idx, 'is_consumed'] = True

    avail_bank = bank_df[~bank_df['is_consumed']]
    for idx in avail_bank.index:
        exceptions.append({'id': bank_df.loc[idx, 'line_id'], 'type': 'bank', 'exception_category': 'ORPHAN_BANK_CREDIT', 'amount': bank_df.loc[idx, 'amount'], 'variance': 0, 'ageing_days': 0, 'recommended_action': 'Check ledger.', 'month': month, 'status': 'EXCEPTION'})

    avail_int = internal_df[~internal_df['is_consumed']]
    for idx in avail_int.index:
        days = (reference_date - pd.to_datetime(internal_df.loc[idx, 'txn_date'])).days
        category = 'GENUINE_EXCEPTION' if days > 45 else 'SETTLEMENT_LAG'
        exceptions.append({'id': internal_df.loc[idx, 'txn_id'], 'type': 'internal', 'exception_category': category, 'amount': internal_df.loc[idx, 'amount'], 'variance': 0, 'ageing_days': days, 'recommended_action': 'Monitor' if days <= 45 else 'Escalate', 'month': month, 'status': 'OPEN' if days <= 45 else 'EXCEPTION'})

    return exceptions

def execute_reconciliation(dataframes):
    ref_date = pd.to_datetime('2026-06-30')
    
    int_may, bank_may = preprocess_data(dataframes['internal_may'], dataframes['bank_may'])
    may_groups, int_may, bank_may, counter = run_matching_passes(int_may, bank_may, start_counter=1)
    
    may_backlog = int_may[~int_may['is_consumed']].copy()
    backlog_details = [{'txn_id': int_may.loc[idx, 'txn_id'], 'amount': int_may.loc[idx, 'amount'], 'status': 'OPEN_CARRY_FORWARD', 'classification': 'PENDING_REVIEW'} for idx in may_backlog.index]

    int_jun, bank_jun = preprocess_data(dataframes['internal_jun'], dataframes['bank_jun'])
    
    backlog_groups = []
    for idx in may_backlog.index:
        ref = may_backlog.loc[idx, 'norm_ref']
        amt = may_backlog.loc[idx, 'amount_paise']
        match_jun_bank = bank_jun[(bank_jun['norm_narration'] == ref) & (bank_jun['amount_paise'] == amt) & (bank_jun['is_consumed'] == False) & (bank_jun['narration'].str.contains('PREV CYCLE', case=False, na=False))]
        if len(match_jun_bank) >= 1:
            b_idx = match_jun_bank.index[0]
            backlog_groups.append({'match_group_id': f"BL{str(len(backlog_groups)+1).zfill(5)}", 'cardinality': '1:1', 'match_method': 'Backlog Cleared', 'status': 'MATCHED', 'variance_paise': 0, 'internal_txn_ids': [int_may.loc[idx, 'txn_id']], 'bank_line_ids': [bank_jun.loc[b_idx, 'line_id']], 'internal_amounts': [int_may.loc[idx, 'amount']], 'bank_amounts': [bank_jun.loc[b_idx, 'amount']]})
            int_may.loc[idx, 'is_consumed'] = True
            bank_jun.loc[b_idx, 'is_consumed'] = True
            for d in backlog_details:
                if d['txn_id'] == int_may.loc[idx, 'txn_id']: 
                    d['status'] = 'CLEARED_IN_JUNE'
        d['classification'] = 'CLEARED'

    jun_groups, int_jun, bank_jun, counter = run_matching_passes(int_jun, bank_jun, start_counter=counter) # FIX #3: Pass counter
    
    may_exceptions = classify_exceptions(int_may, bank_may, 'May', ref_date)
    jun_exceptions = classify_exceptions(int_jun, bank_jun, 'June', ref_date)
    
    # FIX #5: Add classification to backlog details
    for d in backlog_details:
        if d['status'] == 'OPEN_CARRY_FORWARD':
            exc_match = [e for e in may_exceptions if e['id'] == d['txn_id']]
            if exc_match: d['classification'] = exc_match[0]['exception_category']

    return {
        'match_groups': may_groups + backlog_groups + jun_groups,
        'exceptions': may_exceptions + jun_exceptions,
        'backlog_details': backlog_details,
        'may_backlog_cleared': len(backlog_groups),
        'int_may': int_may, 'bank_may': bank_may, 'int_jun': int_jun, 'bank_jun': bank_jun
    }