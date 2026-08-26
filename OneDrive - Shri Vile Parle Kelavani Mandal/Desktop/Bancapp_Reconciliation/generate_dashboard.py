import os
import json
import html
from datetime import datetime

import pandas as pd


OUTPUT_DIR = "output"


def read_csv(name):
    path = os.path.join(OUTPUT_DIR, name)
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception as exc:
        print(f"Could not read {path}: {exc}")
        return pd.DataFrame()


def clean_value(value):
    if pd.isna(value):
        return ""
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.strftime("%Y-%m-%d")
    return value


def records_for_js(df):
    if df.empty:
        return []
    return [
        {str(k): clean_value(v) for k, v in row.items()}
        for row in df.to_dict(orient="records")
    ]


def find_col(df, candidates):
    lower = {str(c).lower(): c for c in df.columns}
    for candidate in candidates:
        if candidate.lower() in lower:
            return lower[candidate.lower()]
    for c in df.columns:
        lc = str(c).lower()
        if any(candidate.lower() in lc for candidate in candidates):
            return c
    return None


def numeric_sum(df, col):
    if df.empty or not col:
        return 0.0
    return pd.to_numeric(df[col], errors="coerce").fillna(0).sum()


def metric_from_summary(summary, keywords, value_col="count"):
    if summary.empty:
        return 0
    metric_col = find_col(summary, ["metric", "measure", "kpi"])
    val_col = find_col(summary, [value_col, "value", "amount", "total"])
    if not metric_col or not val_col:
        return 0
    mask = summary[metric_col].astype(str).str.lower().apply(
        lambda x: all(k.lower() in x for k in keywords)
    )
    vals = pd.to_numeric(summary.loc[mask, val_col], errors="coerce")
    return vals.sum() if not vals.empty else 0


def infer_month(df):
    if df.empty:
        return pd.Series(dtype="object")

    for candidate in ["month", "recon_month", "settlement_month"]:
        col = find_col(df, [candidate])
        if col:
            return df[col].astype(str).str[:3].str.upper()

    date_col = find_col(df, ["txn_date", "value_date", "transaction_date", "date"])
    if date_col:
        dates = pd.to_datetime(df[date_col], errors="coerce")
        return dates.dt.strftime("%b").str.upper()

    ref_col = find_col(df, ["internal_ref", "payment_ref", "txn_id", "transaction_ref"])
    if ref_col:
        s = df[ref_col].astype(str).str.upper()
        return s.str.extract(r"(MAY|JUN)", expand=False)

    return pd.Series(["ALL"] * len(df), index=df.index)


def build_month_summary(reco):
    if reco.empty:
        return []

    status_col = find_col(reco, ["status", "reconciliation_status"])
    amount_col = find_col(reco, ["internal_amount", "amount"])
    variance_col = find_col(reco, ["variance", "difference"])
    month_series = infer_month(reco)

    rows = []
    for month in ["MAY", "JUN"]:
        part = reco.loc[month_series == month]
        if part.empty:
            continue

        status_counts = {}
        if status_col:
            status_counts = (
                part[status_col].astype(str).value_counts().to_dict()
            )

        rows.append({
            "month": month.title(),
            "records": int(len(part)),
            "internal_amount": round(numeric_sum(part, amount_col), 2),
            "variance": round(numeric_sum(part, variance_col), 2),
            "matched": int(status_counts.get("MATCHED", 0)),
            "partial": int(status_counts.get("PARTIAL_MATCH", 0)),
            "open": int(status_counts.get("OPEN", 0)),
            "exception": int(status_counts.get("EXCEPTION", 0)),
        })
    return rows


def generate_html_dashboard():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    summary = read_csv("summary_control_report.csv")
    exception_df = read_csv("exception_report.csv")
    reco_df = read_csv("reconciliation_output.csv")
    backlog_df = read_csv("backlog_report.csv")
    validation_df = read_csv("input_validation_report.csv")

    status_col = find_col(reco_df, ["status", "reconciliation_status"])
    cardinality_col = find_col(reco_df, ["cardinality"])
    internal_amount_col = find_col(reco_df, ["internal_amount"])
    bank_amount_col = find_col(reco_df, ["bank_amount"])
    variance_col = find_col(reco_df, ["variance"])
    group_col = find_col(reco_df, ["match_group_id"])
    internal_ref_col = find_col(
        reco_df, ["internal_reference", "internal_ref", "payment_ref", "txn_id"]
    )
    bank_ref_col = find_col(
        reco_df, ["bank_reference", "bank_ref", "line_id"]
    )
    method_col = find_col(
        reco_df, ["match_method", "method", "comments", "match_method_comments"]
    )

    status_counts = {}
    if status_col:
        status_counts = reco_df[status_col].astype(str).value_counts().to_dict()

    cardinality_counts = {}
    if cardinality_col:
        cardinality_counts = (
            reco_df[cardinality_col]
            .astype(str)
            .value_counts()
            .sort_values(ascending=False)
            .to_dict()
        )

    exception_category_col = find_col(
        exception_df, ["exception_category", "category", "exception"]
    )
    exception_amount_col = find_col(exception_df, ["amount", "exception_amount"])
    exception_variance_col = find_col(exception_df, ["variance", "difference"])
    ageing_col = find_col(exception_df, ["ageing", "age", "age_days"])
    exception_counts = {}
    exception_values = {}
    if exception_category_col:
        exception_counts = (
            exception_df[exception_category_col]
            .astype(str)
            .value_counts()
            .to_dict()
        )
        if exception_amount_col:
            exception_values = (
                pd.to_numeric(exception_df[exception_amount_col], errors="coerce")
                .fillna(0)
                .groupby(exception_df[exception_category_col].astype(str))
                .sum()
                .round(2)
                .to_dict()
            )

    total_internal = metric_from_summary(summary, ["total", "internal", "txns"])
    total_bank = metric_from_summary(summary, ["total", "bank", "lines"])
    matched_internal = metric_from_summary(summary, ["matched", "internal"])
    matched_bank = metric_from_summary(summary, ["matched", "bank"])
    backlog_cleared = metric_from_summary(
        summary, ["may", "backlog", "cleared"], "count"
    )

    if not total_internal:
        total_internal = int(len(reco_df))
    if not total_bank:
        total_bank = int(
            reco_df[bank_ref_col].replace("", pd.NA).notna().sum()
            if bank_ref_col
            else 0
        )

    total_exceptions = len(exception_df)
    total_reco = len(reco_df)
    matched_rate = (
        (status_counts.get("MATCHED", 0) / total_reco) * 100
        if total_reco
        else 0
    )

    total_exception_value = numeric_sum(exception_df, exception_amount_col)
    total_variance = numeric_sum(reco_df, variance_col)

    month_summary = build_month_summary(reco_df)

    # Compact JSON used by the client-side dashboard.
    payload = {
        "status_counts": status_counts,
        "cardinality_counts": cardinality_counts,
        "exception_counts": exception_counts,
        "exception_values": exception_values,
        "status_records": records_for_js(reco_df),
        "exception_records": records_for_js(exception_df),
        "backlog_records": records_for_js(backlog_df),
        "validation_records": records_for_js(validation_df),
        "month_summary": month_summary,
    }

    def js(obj):
        return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")

    generated_at = datetime.now().strftime("%d %b %Y, %H:%M")

    # The HTML is deliberately self-contained: no external chart libraries,
    # no icon libraries, and no server is required.
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bancapp Reconciliation Console</title>
<style>
:root {{
    --bg: #f5f7fa;
    --surface: #ffffff;
    --surface-2: #f8fafc;
    --border: #dfe4ea;
    --text: #172033;
    --muted: #667085;
    --nav: #111827;
    --nav-muted: #a7b0bf;
    --nav-active: #ffffff;
    --accent: #2457c5;
    --accent-soft: #eaf0ff;
    --green: #16855b;
    --green-soft: #e9f7f0;
    --amber: #a96b00;
    --amber-soft: #fff5dc;
    --red: #b42318;
    --red-soft: #fff0ee;
    --blue: #2457c5;
    --blue-soft: #edf3ff;
    --shadow: 0 1px 2px rgba(16,24,40,.04);
}}
[data-theme="dark"] {{
    --bg: #0b1220;
    --surface: #111a2b;
    --surface-2: #162033;
    --border: #263249;
    --text: #edf2f7;
    --muted: #9aa7ba;
    --nav: #080e19;
    --nav-muted: #8995a8;
    --nav-active: #ffffff;
    --accent: #78a2ff;
    --accent-soft: #172a50;
    --green: #3ac58b;
    --green-soft: #123a2b;
    --amber: #f3b63f;
    --amber-soft: #3b2d10;
    --red: #ff766b;
    --red-soft: #3c1c1a;
    --blue: #78a2ff;
    --blue-soft: #172a50;
    --shadow: 0 1px 2px rgba(0,0,0,.25);
}}
* {{ box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}
body {{
    margin: 0;
    font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    font-size: 14px;
}}
button, input, select {{ font: inherit; }}
button {{ cursor: pointer; }}
.app {{ min-height: 100vh; }}
.sidebar {{
    position: fixed;
    inset: 0 auto 0 0;
    width: 248px;
    background: var(--nav);
    color: var(--nav-muted);
    border-right: 1px solid rgba(255,255,255,.06);
    display: flex;
    flex-direction: column;
    z-index: 20;
}}
.brand {{
    height: 76px;
    display: flex;
    align-items: center;
    padding: 0 24px;
    color: #fff;
    font-weight: 650;
    font-size: 18px;
    border-bottom: 1px solid rgba(255,255,255,.08);
}}
.nav {{ padding: 18px 12px; }}
.nav-section {{
    padding: 8px 12px 7px;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: .09em;
    color: #748096;
}}
.nav button {{
    width: 100%;
    border: 0;
    background: transparent;
    color: var(--nav-muted);
    text-align: left;
    padding: 11px 12px;
    border-radius: 5px;
    margin: 2px 0;
    font-size: 13px;
    font-weight: 500;
}}
.nav button:hover {{ background: rgba(255,255,255,.05); color: #fff; }}
.nav button.active {{
    background: #1d2a3e;
    color: #fff;
    box-shadow: inset 3px 0 0 #4d7ff2;
}}
.sidebar-bottom {{
    margin-top: auto;
    padding: 12px;
    border-top: 1px solid rgba(255,255,255,.08);
}}
.main {{
    margin-left: 248px;
    min-height: 100vh;
}}
.topbar {{
    height: 76px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 32px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 10;
}}
.topbar-title {{
    font-size: 15px;
    font-weight: 600;
}}
.topbar-subtitle {{
    color: var(--muted);
    font-size: 12px;
    margin-top: 3px;
}}
.toolbar {{ display: flex; align-items: center; gap: 8px; }}
.btn {{
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text);
    border-radius: 5px;
    padding: 8px 12px;
    font-size: 12px;
    font-weight: 550;
}}
.btn:hover {{ background: var(--surface-2); }}
.btn-primary {{ background: var(--accent); border-color: var(--accent); color: #fff; }}
.theme-toggle {{
    width: 40px;
    height: 40px;
    border: 1px solid var(--border);
    border-radius: 7px;
    background: var(--surface);
    color: var(--text);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    transition: border-color .15s ease, background .15s ease;
}}
.theme-toggle:hover {{
    border-color: var(--accent);
    background: var(--surface-2);
}}
.theme-toggle svg {{
    width: 18px;
    height: 18px;
    display: block;
}}
.content {{
    padding: 30px 32px 50px;
    max-width: 1600px;
}}
.view {{ display: none; }}
.view.active {{ display: block; }}
.page-heading {{
    margin-bottom: 22px;
}}
.page-heading h1 {{
    margin: 0 0 5px;
    font-size: 25px;
    letter-spacing: -.02em;
}}
.page-heading p {{
    margin: 0;
    color: var(--muted);
    font-size: 13px;
}}
.kpis {{
    display: grid;
    grid-template-columns: repeat(4, minmax(0,1fr));
    gap: 14px;
    margin-bottom: 18px;
}}
.kpi {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 7px;
    padding: 18px;
    box-shadow: var(--shadow);
}}
.kpi-label {{
    color: var(--muted);
    font-size: 10px;
    font-weight: 650;
    text-transform: uppercase;
    letter-spacing: .07em;
}}
.kpi-value {{
    margin-top: 8px;
    font-size: 25px;
    line-height: 1;
    font-weight: 650;
    letter-spacing: -.02em;
}}
.kpi-note {{
    margin-top: 8px;
    color: var(--muted);
    font-size: 11px;
}}
.grid-2 {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 16px;
}}
.overview-stack {{
    display: flex;
    flex-direction: column;
    gap: 16px;
    margin-bottom: 16px;
}}
.overview-stack .card {{
    width: 100%;
}}
.overview-stack .table-wrap {{
    max-height: none;
}}
.overview-stack .table-wrap table {{
    min-width: 0;
}}
.card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 7px;
    box-shadow: var(--shadow);
    overflow: hidden;
}}
.card-head {{
    padding: 17px 18px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
}}
.card-title {{ font-weight: 650; font-size: 14px; }}
.card-subtitle {{ color: var(--muted); font-size: 11px; margin-top: 4px; }}
.card-body {{ padding: 18px; }}
.bar-row {{
    display: grid;
    grid-template-columns: 145px 1fr 58px;
    align-items: center;
    gap: 10px;
    margin: 13px 0;
}}
.bar-label {{ color: var(--muted); font-size: 12px; }}
.bar-track {{
    height: 7px;
    background: var(--surface-2);
    border-radius: 10px;
    overflow: hidden;
}}
.bar-fill {{ height: 100%; border-radius: inherit; background: var(--accent); }}
.bar-value {{ text-align: right; font-size: 12px; font-weight: 600; }}
.status-MATCHED .bar-fill {{ background: var(--green); }}
.status-PARTIAL_MATCH .bar-fill {{ background: var(--amber); }}
.status-OPEN .bar-fill {{ background: var(--blue); }}
.status-EXCEPTION .bar-fill {{ background: var(--red); }}
.table-wrap {{
    overflow: auto;
    max-height: 540px;
}}
table {{ width: 100%; border-collapse: collapse; min-width: 760px; }}
th {{
    position: sticky;
    top: 0;
    background: var(--surface-2);
    color: var(--muted);
    text-align: left;
    padding: 10px 14px;
    border-bottom: 1px solid var(--border);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: .06em;
    white-space: nowrap;
}}
td {{
    padding: 10px 14px;
    border-bottom: 1px solid var(--border);
    font-size: 12px;
    vertical-align: top;
}}
tr:hover td {{ background: var(--surface-2); }}
.badge {{
    display: inline-flex;
    align-items: center;
    border-radius: 4px;
    padding: 4px 7px;
    font-size: 10px;
    font-weight: 650;
    white-space: nowrap;
}}
.badge-matched {{ color: var(--green); background: var(--green-soft); }}
.badge-partial {{ color: var(--amber); background: var(--amber-soft); }}
.badge-open {{ color: var(--blue); background: var(--blue-soft); }}
.badge-exception {{ color: var(--red); background: var(--red-soft); }}
.badge-neutral {{ color: var(--muted); background: var(--surface-2); }}
.controls {{
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 12px;
}}
.controls input, .controls select {{
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text);
    border-radius: 5px;
    padding: 8px 10px;
    min-width: 170px;
    outline: none;
}}
.controls input:focus, .controls select:focus {{ border-color: var(--accent); }}
.stat-line {{
    display: grid;
    grid-template-columns: repeat(3,1fr);
    gap: 10px;
    margin-bottom: 16px;
}}
.mini-stat {{
    border: 1px solid var(--border);
    background: var(--surface-2);
    border-radius: 6px;
    padding: 12px;
}}
.mini-stat span {{ display:block; color:var(--muted); font-size:10px; text-transform:uppercase; letter-spacing:.06em; }}
.mini-stat strong {{ display:block; margin-top:5px; font-size:17px; }}
.note {{
    border-left: 3px solid var(--accent);
    background: var(--accent-soft);
    padding: 12px 14px;
    color: var(--text);
    font-size: 12px;
    line-height: 1.55;
    margin-bottom: 16px;
}}
.method-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
}}
.method {{
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 14px;
    background: var(--surface-2);
}}
.method strong {{ display:block; margin-bottom:6px; }}
.method span {{ color:var(--muted); font-size:11px; line-height:1.45; }}
.empty {{
    padding: 28px;
    color: var(--muted);
    text-align: center;
}}
.footer {{
    color: var(--muted);
    font-size: 11px;
    padding-top: 22px;
}}
@media (max-width: 1100px) {{
    .kpis {{ grid-template-columns: repeat(2,1fr); }}
    .grid-2 {{ grid-template-columns: 1fr; }}
    .method-grid {{ grid-template-columns: repeat(2,1fr); }}
}}
@media (max-width: 760px) {{
    .sidebar {{ position: static; width: 100%; height: auto; }}
    .brand {{ height: 62px; }}
    .sidebar-bottom {{ display:none; }}
    .main {{ margin-left:0; }}
    .topbar {{ position:static; height:auto; padding:16px; gap:12px; }}
    .content {{ padding:20px 16px; }}
    .kpis {{ grid-template-columns: 1fr; }}
    .method-grid {{ grid-template-columns: 1fr; }}
}}
</style>
</head>

<body>
<div class="app">
    <aside class="sidebar">
        <div class="brand">Bancapp Console</div>
        <nav class="nav">
            <div class="nav-section">Reconciliation</div>
            <button class="nav-link active" data-view="overview">Overview</button>
            <button class="nav-link" data-view="transactions">Transactions</button>
            <button class="nav-link" data-view="exceptions">Exceptions</button>
            <button class="nav-link" data-view="backlog">Backlog</button>

            <div class="nav-section" style="margin-top:12px;">Controls</div>
            <button class="nav-link" data-view="validation">Input Validation</button>
            <button class="nav-link" data-view="reports">Reports & Methodology</button>
        </nav>
        <div class="sidebar-bottom">
            <div style="font-size:11px;line-height:1.5;color:#748096;">
                Generated locally from reconciliation output files.<br>
                {html.escape(generated_at)}
            </div>
        </div>
    </aside>

    <main class="main">
        <header class="topbar">
            <div>
                <div class="topbar-title" id="topbarTitle">Reconciliation Overview</div>
                <div class="topbar-subtitle">May and June 2026 settlement cycles</div>
            </div>
            <div class="toolbar">
                <button class="theme-toggle" id="themeBtn" type="button"
                        aria-label="Switch colour theme" title="Switch colour theme">
                    <span id="themeIcon" aria-hidden="true"></span>
                </button>
            </div>
        </header>

        <section class="content">

            <div class="view active" id="view-overview">
                <div class="page-heading">
                    <h1>Reconciliation Overview</h1>
                    <p>Control view of settlement matching, exceptions, backlog and input quality.</p>
                </div>

                <div class="kpis">
                    <div class="kpi">
                        <div class="kpi-label">Internal transactions</div>
                        <div class="kpi-value">{int(total_internal)}</div>
                        <div class="kpi-note">May and June input population</div>
                    </div>
                    <div class="kpi">
                        <div class="kpi-label">Bank statement lines</div>
                        <div class="kpi-value">{int(total_bank)}</div>
                        <div class="kpi-note">Credit lines available for matching</div>
                    </div>
                    <div class="kpi">
                        <div class="kpi-label">Matched internal</div>
                        <div class="kpi-value" style="color:var(--green)">{int(matched_internal)}</div>
                        <div class="kpi-note">{matched_rate:.1f}% of reconciliation rows marked MATCHED</div>
                    </div>
                    <div class="kpi">
                        <div class="kpi-label">Exceptions</div>
                        <div class="kpi-value" style="color:var(--red)">{int(total_exceptions)}</div>
                        <div class="kpi-note">Exception report records</div>
                    </div>
                    <div class="kpi">
                        <div class="kpi-label">Matched bank lines</div>
                        <div class="kpi-value" style="color:var(--green)">{int(matched_bank)}</div>
                        <div class="kpi-note">Bank-side records reconciled</div>
                    </div>
                    <div class="kpi">
                        <div class="kpi-label">Backlog cleared</div>
                        <div class="kpi-value" style="color:var(--green)">{int(backlog_cleared)}</div>
                        <div class="kpi-note">May backlog cleared in June</div>
                    </div>
                    <div class="kpi">
                        <div class="kpi-label">Exception value</div>
                        <div class="kpi-value">₹{total_exception_value:,.2f}</div>
                        <div class="kpi-note">Sum of amounts in exception report</div>
                    </div>
                    <div class="kpi">
                        <div class="kpi-label">Net variance</div>
                        <div class="kpi-value">₹{total_variance:,.2f}</div>
                        <div class="kpi-note">Sum of reconciliation variances</div>
                    </div>
                </div>

                <div class="overview-stack">
                    <div class="card">
                        <div class="card-head">
                            <div>
                                <div class="card-title">Reconciliation status</div>
                                <div class="card-subtitle">Final status assigned to each reconciliation record</div>
                            </div>
                        </div>
                        <div class="card-body" id="statusChart"></div>
                    </div>

                    <div class="card">
                        <div class="card-head">
                            <div>
                                <div class="card-title">Matching cardinality</div>
                                <div class="card-subtitle">How internal and bank records were grouped</div>
                            </div>
                        </div>
                        <div class="card-body" id="cardinalityChart"></div>
                    </div>
                </div>

                <div class="overview-stack">
                    <div class="card">
                        <div class="card-head">
                            <div>
                                <div class="card-title">Monthly control summary</div>
                                <div class="card-subtitle">May versus June reconciliation controls</div>
                            </div>
                        </div>
                        <div class="table-wrap">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Month</th>
                                        <th>Records</th>
                                        <th>Internal amount</th>
                                        <th>Variance</th>
                                        <th>Matched</th>
                                        <th>Partial</th>
                                        <th>Open</th>
                                        <th>Exception</th>
                                    </tr>
                                </thead>
                                <tbody id="monthSummary"></tbody>
                            </table>
                        </div>
                    </div>

                    <div class="card">
                        <div class="card-head">
                            <div>
                                <div class="card-title">Exception categories</div>
                                <div class="card-subtitle">Count and value requiring operational attention</div>
                            </div>
                        </div>
                        <div class="table-wrap">
                            <table>
                                <thead>
                                    <tr><th>Category</th><th>Count</th><th>Value</th></tr>
                                </thead>
                                <tbody id="exceptionSummary"></tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>

            <div class="view" id="view-transactions">
                <div class="page-heading">
                    <h1>Transactions</h1>
                    <p>Trace individual reconciliation rows, match groups, cardinality and variance.</p>
                </div>
                <div class="controls">
                    <input id="txnSearch" placeholder="Search reference or match group">
                    <select id="txnStatus">
                        <option value="">All statuses</option>
                        <option>MATCHED</option>
                        <option>PARTIAL_MATCH</option>
                        <option>OPEN</option>
                        <option>EXCEPTION</option>
                    </select>
                    <select id="txnCardinality"><option value="">All cardinalities</option></select>
                </div>
                <div class="card">
                    <div class="table-wrap">
                        <table>
                            <thead>
                                <tr>
                                    <th>Internal reference</th>
                                    <th>Bank reference</th>
                                    <th>Match group</th>
                                    <th>Cardinality</th>
                                    <th>Internal amount</th>
                                    <th>Bank amount</th>
                                    <th>Variance</th>
                                    <th>Status</th>
                                    <th>Method / comments</th>
                                </tr>
                            </thead>
                            <tbody id="transactionTable"></tbody>
                        </table>
                    </div>
                </div>
            </div>

            <div class="view" id="view-exceptions">
                <div class="page-heading">
                    <h1>Exceptions</h1>
                    <p>Every unmatched or imperfectly matched item should be traceable to a category and action.</p>
                </div>
                <div class="stat-line">
                    <div class="mini-stat"><span>Exception records</span><strong>{total_exceptions}</strong></div>
                    <div class="mini-stat"><span>Exception value</span><strong>₹{total_exception_value:,.2f}</strong></div>
                    <div class="mini-stat"><span>Ageing basis</span><strong>As supplied in report</strong></div>
                </div>
                <div class="card">
                    <div class="table-wrap">
                        <table>
                            <thead>
                                <tr>
                                    <th>Category</th>
                                    <th>Reference</th>
                                    <th>Amount</th>
                                    <th>Variance</th>
                                    <th>Ageing</th>
                                    <th>Recommended action</th>
                                </tr>
                            </thead>
                            <tbody id="exceptionTable"></tbody>
                        </table>
                    </div>
                </div>
            </div>

            <div class="view" id="view-backlog">
                <div class="page-heading">
                    <h1>Backlog</h1>
                    <p>May unmatched items carried into June and their final June status.</p>
                </div>
                <div class="note">
                    Opening backlog is treated separately from June-originated transactions. The dashboard
                    does not infer a lag classification that is not present in the backlog output.
                </div>
                <div class="card">
                    <div class="table-wrap">
                        <table>
                            <thead id="backlogHead"></thead>
                            <tbody id="backlogTable"></tbody>
                        </table>
                    </div>
                </div>
            </div>

            <div class="view" id="view-validation">
                <div class="page-heading">
                    <h1>Input Validation</h1>
                    <p>Read errors, schema issues, invalid values and missing identifiers recorded during ingestion.</p>
                </div>
                <div class="card">
                    <div class="table-wrap">
                        <table>
                            <thead id="validationHead"></thead>
                            <tbody id="validationTable"></tbody>
                        </table>
                    </div>
                </div>
            </div>

            <div class="view" id="view-reports">
                <div class="page-heading">
                    <h1>Reports & Methodology</h1>
                    <p>Reconciliation controls and downloadable deliverables.</p>
                </div>

                <div class="grid-2">
                    <div class="card">
                        <div class="card-head">
                            <div>
                                <div class="card-title">Matching pass order</div>
                                <div class="card-subtitle">Use the same sequence in the technical explanation</div>
                            </div>
                        </div>
                        <div class="card-body">
                            <div class="method-grid">
                                <div class="method"><strong>1:1</strong><span>Reference and amount based direct matches.</span></div>
                                <div class="method"><strong>1:N</strong><span>One internal transaction reconciled to multiple bank credits.</span></div>
                                <div class="method"><strong>N:1</strong><span>Multiple internal transactions reconciled to one bank settlement.</span></div>
                                <div class="method"><strong>N:M</strong><span>Multiple internal and bank records matched where net amounts tie.</span></div>
                            </div>
                            <div class="note" style="margin-top:14px;margin-bottom:0;">
                                Matched records must be consumed only once. The implementation should maintain
                                separate used-internal and used-bank identifier sets and assign a shared match_group_id
                                to every multi-record match.
                            </div>
                        </div>
                    </div>

                    <div class="card">
                        <div class="card-head">
                            <div>
                                <div class="card-title">Required deliverables</div>
                                <div class="card-subtitle">Files produced by the reconciliation pipeline</div>
                            </div>
                        </div>
                        <div class="card-body">
                            <div style="display:grid;gap:8px;">
                                <a class="btn" href="reconciliation_output.csv" download>Reconciliation output</a>
                                <a class="btn" href="exception_report.csv" download>Exception report</a>
                                <a class="btn" href="backlog_report.csv" download>Backlog report</a>
                                <a class="btn" href="input_validation_report.csv" download>Input validation report</a>
                                <a class="btn" href="summary_control_report.csv" download>Summary / control report</a>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="card">
                    <div class="card-head">
                        <div>
                            <div class="card-title">Control interpretation</div>
                            <div class="card-subtitle">Definitions used in the assignment</div>
                        </div>
                    </div>
                    <div class="card-body">
                        <div class="method-grid">
                            <div class="method"><strong>MATCHED</strong><span>Internal and bank amounts fully reconcile.</span></div>
                            <div class="method"><strong>PARTIAL_MATCH</strong><span>Related records exist, but the full amount is not settled.</span></div>
                            <div class="method"><strong>OPEN</strong><span>No final settlement has been found yet.</span></div>
                            <div class="method"><strong>EXCEPTION</strong><span>Duplicate, orphan, invalid input or investigation case.</span></div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="footer">
                Dashboard generated from local CSV outputs. Generated at {html.escape(generated_at)}.
            </div>
        </section>
    </main>
</div>

<script>
const DATA = {js(payload)};

function money(value) {{
    const n = Number(value);
    if (!Number.isFinite(n)) return "";
    return "₹" + n.toLocaleString("en-IN", {{minimumFractionDigits: 2, maximumFractionDigits: 2}});
}}

function esc(value) {{
    return String(value ?? "").replace(/[&<>"']/g, function(c) {{
        return {{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}}[c];
    }});
}}

function badge(status) {{
    const s = String(status || "").toUpperCase();
    let cls = "badge-neutral";
    if (s === "MATCHED") cls = "badge-matched";
    else if (s === "PARTIAL_MATCH") cls = "badge-partial";
    else if (s === "OPEN") cls = "badge-open";
    else if (s === "EXCEPTION") cls = "badge-exception";
    return `<span class="badge ${{cls}}">${{esc(s.replaceAll("_"," "))}}</span>`;
}}

function renderBars(targetId, values, formatter, statusMode=false) {{
    const target = document.getElementById(targetId);
    const entries = Object.entries(values || {{}});
    if (!entries.length) {{
        target.innerHTML = '<div class="empty">No data available.</div>';
        return;
    }}
    const max = Math.max(...entries.map(x => Number(x[1]) || 0), 1);
    target.innerHTML = entries.map(([label, value]) => {{
        const cls = statusMode ? `status-${{label}}` : "";
        const pct = ((Number(value) || 0) / max) * 100;
        return `<div class="bar-row ${{cls}}">
            <div class="bar-label">${{esc(label.replaceAll("_"," "))}}</div>
            <div class="bar-track"><div class="bar-fill" style="width:${{pct}}%"></div></div>
            <div class="bar-value">${{formatter ? formatter(value) : value}}</div>
        </div>`;
    }}).join("");
}}

function renderMonthSummary() {{
    const body = document.getElementById("monthSummary");
    if (!DATA.month_summary.length) {{
        body.innerHTML = '<tr><td colspan="8" class="empty">Monthly breakdown not available in reconciliation output.</td></tr>';
        return;
    }}
    body.innerHTML = DATA.month_summary.map(r => `
        <tr>
            <td><strong>${{esc(r.month)}}</strong></td>
            <td>${{r.records}}</td>
            <td>${{money(r.internal_amount)}}</td>
            <td>${{money(r.variance)}}</td>
            <td>${{r.matched}}</td>
            <td>${{r.partial}}</td>
            <td>${{r.open}}</td>
            <td>${{r.exception}}</td>
        </tr>
    `).join("");
}}

function renderExceptionSummary() {{
    const body = document.getElementById("exceptionSummary");
    const entries = Object.entries(DATA.exception_counts || {{}});
    if (!entries.length) {{
        body.innerHTML = '<tr><td colspan="3" class="empty">No exception records.</td></tr>';
        return;
    }}
    body.innerHTML = entries.map(([cat, count]) => `
        <tr>
            <td>${{esc(cat.replaceAll("_"," "))}}</td>
            <td>${{count}}</td>
            <td>${{money(DATA.exception_values?.[cat] || 0)}}</td>
        </tr>
    `).join("");
}}

function renderTransactions() {{
    const body = document.getElementById("transactionTable");
    const search = document.getElementById("txnSearch").value.toLowerCase();
    const status = document.getElementById("txnStatus").value;
    const card = document.getElementById("txnCardinality").value;

    const rows = DATA.status_records.filter(r => {{
        const text = JSON.stringify(r).toLowerCase();
        const rowStatus = String(r["{status_col or 'status'}"] ?? "");
        const rowCard = String(r["{cardinality_col or 'cardinality'}"] ?? "");
        return (!search || text.includes(search))
            && (!status || rowStatus === status)
            && (!card || rowCard === card);
    }});

    if (!rows.length) {{
        body.innerHTML = '<tr><td colspan="9" class="empty">No matching records.</td></tr>';
        return;
    }}

    body.innerHTML = rows.map(r => `
        <tr>
            <td>${{esc(r["{internal_ref_col or ''}"])}}</td>
            <td>${{esc(r["{bank_ref_col or ''}"])}}</td>
            <td>${{esc(r["{group_col or ''}"])}}</td>
            <td>${{esc(r["{cardinality_col or ''}"])}}</td>
            <td>${{money(r["{internal_amount_col or ''}"])}}</td>
            <td>${{money(r["{bank_amount_col or ''}"])}}</td>
            <td>${{money(r["{variance_col or ''}"])}}</td>
            <td>${{badge(r["{status_col or ''}"])}}</td>
            <td>${{esc(r["{method_col or ''}"])}}</td>
        </tr>
    `).join("");
}}

function renderExceptions() {{
    const body = document.getElementById("exceptionTable");
    if (!DATA.exception_records.length) {{
        body.innerHTML = '<tr><td colspan="6" class="empty">No exception records.</td></tr>';
        return;
    }}

    const sample = DATA.exception_records[0] || {{}};
    const categoryKey = "{exception_category_col or ''}";
    const amountKey = "{exception_amount_col or ''}";
    const varianceKey = "{exception_variance_col or ''}";
    const ageingKey = "{ageing_col or ''}";
    const refKey = Object.keys(sample).find(k => /reference|ref|txn|line_id/i.test(k)) || "";

    body.innerHTML = DATA.exception_records.map(r => `
        <tr>
            <td>${{esc(r[categoryKey])}}</td>
            <td>${{esc(r[refKey])}}</td>
            <td>${{money(r[amountKey])}}</td>
            <td>${{money(r[varianceKey])}}</td>
            <td>${{esc(r[ageingKey])}}</td>
            <td>${{esc(r[Object.keys(r).find(k => /recommended|action/i.test(k)) || ""])}}</td>
        </tr>
    `).join("");
}}

function renderDynamicTable(headId, bodyId, rows) {{
    const head = document.getElementById(headId);
    const body = document.getElementById(bodyId);
    if (!rows.length) {{
        head.innerHTML = "";
        body.innerHTML = '<tr><td class="empty">No records available.</td></tr>';
        return;
    }}
    const keys = Object.keys(rows[0]);
    head.innerHTML = "<tr>" + keys.map(k => `<th>${{esc(k.replaceAll("_"," "))}}</th>`).join("") + "</tr>";
    body.innerHTML = rows.map(r =>
        "<tr>" + keys.map(k => `<td>${{esc(r[k])}}</td>`).join("") + "</tr>"
    ).join("");
}}

function initCardinalityFilter() {{
    const select = document.getElementById("txnCardinality");
    Object.keys(DATA.cardinality_counts || {{}}).forEach(v => {{
        const option = document.createElement("option");
        option.value = v;
        option.textContent = v;
        select.appendChild(option);
    }});
}}

function showView(viewName) {{
    document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
    const target = document.getElementById("view-" + viewName);
    if (target) target.classList.add("active");

    document.querySelectorAll(".nav-link").forEach(b => {{
        b.classList.toggle("active", b.dataset.view === viewName);
    }});

    const titles = {{
        overview: "Reconciliation Overview",
        transactions: "Transactions",
        exceptions: "Exceptions",
        backlog: "Backlog",
        validation: "Input Validation",
        reports: "Reports & Methodology"
    }};
    document.getElementById("topbarTitle").textContent = titles[viewName] || "Bancapp Console";
    history.replaceState(null, "", "#" + viewName);
}}

document.querySelectorAll(".nav-link").forEach(btn => {{
    btn.addEventListener("click", () => showView(btn.dataset.view));
}});

document.getElementById("txnSearch").addEventListener("input", renderTransactions);
document.getElementById("txnStatus").addEventListener("change", renderTransactions);
document.getElementById("txnCardinality").addEventListener("change", renderTransactions);

const SUN_ICON = `
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
     stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <circle cx="12" cy="12" r="4"></circle>
    <path d="M12 2v2.2M12 19.8V22M4.93 4.93l1.55 1.55M17.52 17.52l1.55 1.55
             M2 12h2.2M19.8 12H22M4.93 19.07l1.55-1.55M17.52 6.48l1.55-1.55"></path>
</svg>`;

const MOON_ICON = `
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
     stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M20.2 15.4A8.5 8.5 0 0 1 8.6 3.8
             8.5 8.5 0 1 0 20.2 15.4Z"></path>
</svg>`;

function setTheme(theme) {{
    document.documentElement.setAttribute("data-theme", theme);
    const icon = document.getElementById("themeIcon");
    const button = document.getElementById("themeBtn");
    const isDark = theme === "dark";

    icon.innerHTML = isDark ? SUN_ICON : MOON_ICON;
    button.setAttribute(
        "aria-label",
        isDark ? "Switch to light mode" : "Switch to dark mode"
    );
    button.setAttribute(
        "title",
        isDark ? "Switch to light mode" : "Switch to dark mode"
    );

    localStorage.setItem("bancapp-theme", theme);
}}

document.getElementById("themeBtn").addEventListener("click", () => {{
    const current = document.documentElement.getAttribute("data-theme") || "light";
    setTheme(current === "dark" ? "light" : "dark");
}});

const savedTheme = localStorage.getItem("bancapp-theme") || "light";
setTheme(savedTheme);

const initialView = location.hash.replace("#", "");
showView(["overview","transactions","exceptions","backlog","validation","reports"].includes(initialView) ? initialView : "overview");

renderBars("statusChart", DATA.status_counts, v => v, true);
renderBars("cardinalityChart", DATA.cardinality_counts, v => v);
renderMonthSummary();
renderExceptionSummary();
renderTransactions();
renderExceptions();
renderDynamicTable("backlogHead", "backlogTable", DATA.backlog_records);
renderDynamicTable("validationHead", "validationTable", DATA.validation_records);
initCardinalityFilter();
</script>
</body>
</html>
"""

    output_path = os.path.join(OUTPUT_DIR, "reconciliation_dashboard.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Dashboard generated: {output_path}")


if __name__ == "__main__":
    generate_html_dashboard()
