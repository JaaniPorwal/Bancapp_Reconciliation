# Take-Home Assignment --- Data Analyst (Reconciliation)

**Time budget: 4 hours maximum.** We would rather see a sharp, partially
complete submission with clear reasoning than a padded one. Note your
actual time spent in the write-up.

## Context

You are given settlement data for a payments business for two
consecutive months:

  -----------------------------------------------------------------------
  File                                Description
  ----------------------------------- -----------------------------------
  `internal_txns_may2026.csv`         Internal transaction ledger, May
                                      2026

  `bank_stmt_may2026.csv`             Bank settlement statement
                                      (credits), May 2026

  `internal_txns_jun2026.csv`         Internal transaction ledger, June
                                      2026

  `bank_stmt_jun2026.csv`             Bank settlement statement
                                      (credits), June 2026
  -----------------------------------------------------------------------

Every successful internal transaction should eventually be represented
in the bank statement --- but not always one-to-one, not always in the
same month, not always with a clean reference, and not always exactly
once.

### Data notes

-   `payment_ref` is the internal reference. Bank narrations usually
    contain it, but the format is not guaranteed.
-   `batch_id`, where present, indicates transactions settled together
    as one batch.
-   `txn_type` can be SALE, REFUND, or REVERSAL. Refunds and reversals
    carry negative amounts.
-   Amounts are in INR.
-   Assume the bank statement contains only credits relevant to this
    business.

## Task 1 --- Month 1 Reconciliation (May)

Reconcile May internal transactions against the May bank statement.

Your matching logic must correctly handle **all cardinalities present in
the data**:

-   **1:1** --- one transaction to one bank line
-   **1:N** --- one transaction settled in multiple partial credits
-   **N:1** --- multiple transactions settled in one batch
-   **N:M** --- multiple transactions and bank lines where the net
    amount matches

Watch for:

-   References that don't match exactly.
-   Bank lines that could match the same internal transaction more than
    once.
-   Amount mismatches.
-   Groups where amounts don't tie exactly.
-   Duplicate/repeated credits.

A matched record must never be consumed twice. Explain how your logic
prevents this.

## Task 2 --- Month 2 Reconciliation With Backlog (June)

Reconcile June, but carry forward May's unmatched items as an **opening
backlog**.

The June output must distinguish:

1.  June transactions settled in June.
2.  May backlog cleared in June.
3.  Items still open at the end of June.

For open items, classify them as either:

-   **Likely Settlement Lag** --- expected to settle later.
-   **Genuine Exception** --- requires investigation.

State the rule used for this classification.

## Task 3 --- Exception Analysis

Produce an exception report covering both months.

Every unmatched or imperfectly matched item should have one clear
category, such as:

-   Duplicate credit
-   Short settlement
-   Orphan credit
-   Unsettled transaction
-   Internal self-netting pair
-   Reference/amount mismatch
-   Other investigation required

Show **count, value and ageing** for the exceptions.

## Task 4 --- Output Format Design

For each cardinality (**1:1, 1:N, N:1, N:M**), briefly explain the best
output format for:

1.  An operations user handling exceptions.
2.  An auditor checking the reconciliation.

Discuss the trade-off between a flat match table and a **match-group /
parent-child structure**.

## Required Reconciliation Status

Each final reconciliation result should have one of these statuses:

-   **MATCHED** --- fully reconciled.
-   **PARTIAL_MATCH** --- related records found, but the amount is not
    fully settled.
-   **OPEN** --- no final settlement found yet.
-   **EXCEPTION** --- duplicate, orphan, invalid data, processing issue,
    or other investigation case.

For multi-record matches, use a common **`match_group_id`** so all
records belonging to the same reconciliation can be traced together.
Also include the **cardinality** (1:1, 1:N, N:1, N:M).

## Required Output Files

Generate the following:

1.  **`reconciliation_output.csv`**
    -   Internal/bank references
    -   `match_group_id`
    -   Cardinality
    -   Internal amount
    -   Bank amount
    -   Variance
    -   Reconciliation status
    -   Match method/comments
2.  **`exception_report.csv`**
    -   Exception category
    -   Related transaction/bank reference
    -   Amount
    -   Variance
    -   Ageing
    -   Recommended action
3.  **`backlog_report.csv`**
    -   May opening backlog
    -   Items cleared in June
    -   Items still open at June month-end
    -   Lag vs genuine exception classification
4.  **`input_validation_report.csv`**
    -   File/read errors
    -   Missing required columns
    -   Invalid/missing values
    -   Other input issues

A simple **summary/control report** may also be generated showing total,
matched, partial, open, backlog-cleared and exception counts/values for
May and June.

## Input Reading / Validation

Handle errors while reading the input files.

Check basic items such as:

-   File can be read.
-   Required columns exist.
-   Dates and amounts are valid.
-   Required identifiers are not missing.

Do not silently ignore invalid input. Record such issues in
`input_validation_report.csv`.

## Deliverables

1.  **Code / workbook** --- Python or SQL file, runnable and reproducible.
2.  **Reconciliation output files** listed above.
3.  **Summary write-up (max 2 pages)** covering:
    -   Monthly reconciliation results.
    -   Matching methodology and pass order.
    -   How duplicate/redundant matching was prevented.
    -   May backlog carried into June.
    -   Lag-vs-exception rule.
    -   Exception summary.
    -   Output format design.
    -   Actual time spent.

    ## ADD- ON
    - Dashboard / HTML Report

        Generate a simple reconciliation_dashboard.html showing May and June reconciliation summary, including MATCHED, PARTIAL_MATCH, OPEN, EXCEPTION, backlog, and ageing.

        The dashboard should be generated from the reconciliation output and display key counts, amounts, and exception categories.

## Rules

-   Any tools/languages are allowed, including AI assistants.
-   You must be able to explain your logic in the follow-up discussion.
-   Numbers must be reproducible from your code/workbook.
-   State assumptions clearly.
-   Focus on correctness, control and clear reasoning rather than visual
    polish.
