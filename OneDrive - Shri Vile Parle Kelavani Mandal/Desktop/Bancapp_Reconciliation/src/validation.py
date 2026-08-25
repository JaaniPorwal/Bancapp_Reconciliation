from pathlib import Path
import pandas as pd


REQUIRED_COLUMNS = {
    "internal": [
        "txn_id",
        "txn_date",
        "channel",
        "merchant_id",
        "txn_type",
        "amount",
        "currency",
        "payment_ref",
        "batch_id",
        "status",
    ],
    "bank": [
        "line_id",
        "value_date",
        "narration",
        "dr_cr",
        "amount",
        "bank_ref",
    ],
}


def validate_file(file_path: str, file_type: str) -> tuple[pd.DataFrame | None, list[dict]]:
    """
    Read and validate one input CSV.

    Returns:
        dataframe: Loaded dataframe if the file can be read, otherwise None.
        issues: List of validation issues found.
    """

    issues = []
    path = Path(file_path)

    # ---------------------------------------------------------
    # 1. Check whether the file exists
    # ---------------------------------------------------------
    if not path.exists():
        issues.append({
            "file": path.name,
            "issue_type": "FILE_ERROR",
            "issue": "Input file does not exist.",
            "column": "",
            "row": "",
        })
        return None, issues

    # ---------------------------------------------------------
    # 2. Try to read the CSV
    # ---------------------------------------------------------
    try:
        df = pd.read_csv(path)
    except Exception as exc:
        issues.append({
            "file": path.name,
            "issue_type": "FILE_ERROR",
            "issue": f"Unable to read CSV: {exc}",
            "column": "",
            "row": "",
        })
        return None, issues

    # ---------------------------------------------------------
    # 3. Check required columns
    # ---------------------------------------------------------
    required_columns = REQUIRED_COLUMNS[file_type]

    missing_columns = [
        column for column in required_columns
        if column not in df.columns
    ]

    for column in missing_columns:
        issues.append({
            "file": path.name,
            "issue_type": "MISSING_COLUMN",
            "issue": f"Required column '{column}' is missing.",
            "column": column,
            "row": "",
        })

    # Stop further validation if essential columns are missing.
    if missing_columns:
        return df, issues

    # ---------------------------------------------------------
    # 4. Check required identifiers
    # ---------------------------------------------------------
    identifier_column = "txn_id" if file_type == "internal" else "line_id"

    missing_ids = df[identifier_column].isna()

    for index in df.index[missing_ids]:
        issues.append({
            "file": path.name,
            "issue_type": "MISSING_IDENTIFIER",
            "issue": f"Missing {identifier_column}.",
            "column": identifier_column,
            "row": index + 2,
        })

    # ---------------------------------------------------------
    # 5. Check dates
    # ---------------------------------------------------------
    date_column = "txn_date" if file_type == "internal" else "value_date"

    parsed_dates = pd.to_datetime(
        df[date_column],
        errors="coerce"
    )

    invalid_dates = parsed_dates.isna() & df[date_column].notna()

    for index in df.index[invalid_dates]:
        issues.append({
            "file": path.name,
            "issue_type": "INVALID_DATE",
            "issue": f"Invalid date value in '{date_column}'.",
            "column": date_column,
            "row": index + 2,
        })

    missing_dates = df[date_column].isna()

    for index in df.index[missing_dates]:
        issues.append({
            "file": path.name,
            "issue_type": "MISSING_DATE",
            "issue": f"Missing value in '{date_column}'.",
            "column": date_column,
            "row": index + 2,
        })

    # ---------------------------------------------------------
    # 6. Check amounts
    # ---------------------------------------------------------
    parsed_amounts = pd.to_numeric(
        df["amount"],
        errors="coerce"
    )

    invalid_amounts = parsed_amounts.isna() & df["amount"].notna()

    for index in df.index[invalid_amounts]:
        issues.append({
            "file": path.name,
            "issue_type": "INVALID_AMOUNT",
            "issue": "Amount is not numeric.",
            "column": "amount",
            "row": index + 2,
        })

    missing_amounts = df["amount"].isna()

    for index in df.index[missing_amounts]:
        issues.append({
            "file": path.name,
            "issue_type": "MISSING_AMOUNT",
            "issue": "Missing amount.",
            "column": "amount",
            "row": index + 2,
        })

    # ---------------------------------------------------------
    # 7. Check duplicate identifiers
    # ---------------------------------------------------------
    duplicate_ids = df[
        df[identifier_column].notna()
        & df[identifier_column].duplicated(keep=False)
    ]

    for index in duplicate_ids.index:
        duplicate_id = duplicate_ids.loc[index, identifier_column]

        issues.append({
            "file": path.name,
            "issue_type": "DUPLICATE_IDENTIFIER",
            "issue": (
                f"Duplicate {identifier_column}: "
                f"{duplicate_id}"
            ),
            "column": identifier_column,
            "row": index + 2,
        })

    return df, issues


def validate_all_inputs(data_dir: str) -> tuple[dict, pd.DataFrame]:
    """
    Validate all four Bancapp input files.

    Returns:
        dataframes: Dictionary containing successfully read dataframes.
        validation_report: Dataframe containing all validation issues.
    """

    data_path = Path(data_dir)

    files = {
        "internal_may": (
            data_path / "internal_txns_may2026.csv",
            "internal",
        ),
        "bank_may": (
            data_path / "bank_stmt_may2026.csv",
            "bank",
        ),
        "internal_jun": (
            data_path / "internal_txns_jun2026.csv",
            "internal",
        ),
        "bank_jun": (
            data_path / "bank_stmt_jun2026.csv",
            "bank",
        ),
    }

    dataframes = {}
    all_issues = []

    for name, (file_path, file_type) in files.items():
        df, issues = validate_file(
            str(file_path),
            file_type
        )

        if df is not None:
            dataframes[name] = df

        all_issues.extend(issues)

    validation_report = pd.DataFrame(
        all_issues,
        columns=[
            "file",
            "issue_type",
            "issue",
            "column",
            "row",
        ],
    )

    return dataframes, validation_report