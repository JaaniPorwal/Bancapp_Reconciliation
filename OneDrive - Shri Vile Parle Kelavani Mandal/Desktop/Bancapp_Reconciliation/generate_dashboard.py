import pandas as pd
import os
from datetime import datetime

def generate_html_dashboard():
    os.makedirs("output", exist_ok=True)
    
    try:
        summary_df = pd.read_csv("output/summary_control_report.csv")
        exception_df = pd.read_csv("output/exception_report.csv")
        reco_df = pd.read_csv("output/reconciliation_output.csv")
    except FileNotFoundError:
        print(" Error: Please run run_reconciliation.py first.")
        return

    total_exceptions = len(exception_df)
    exception_counts = exception_df['exception_category'].value_counts().to_dict()
    status_counts = reco_df['status'].value_counts().to_dict()
    cardinality_counts = reco_df[reco_df['status'].isin(['MATCHED', 'PARTIAL_MATCH'])]['cardinality'].value_counts().to_dict()
    
    total_reco_records = len(reco_df)
    status_percentages = {k: (v / total_reco_records) * 100 for k, v in status_counts.items()}
    
    total_cardinality = sum(cardinality_counts.values())
    card_percentages = {k: (v / total_cardinality) * 100 for k, v in cardinality_counts.items()} if total_cardinality > 0 else {}

    total_int = summary_df[summary_df['metric'] == 'Total Internal Txns']['count'].sum()
    total_bank = summary_df[summary_df['metric'] == 'Total Bank Lines']['count'].sum()
    matched_int = summary_df[summary_df['metric'] == 'Matched Internal']['count'].sum()
    matched_bank = summary_df[summary_df['metric'] == 'Matched Bank']['count'].sum()
    backlog_cleared = summary_df[summary_df['metric'] == 'May Backlog Cleared in June']['count'].sum()

    timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Bancapp Reconciliation Dashboard</title>
        <style>
            :root {{
                --primary: #0f172a; --accent: #2563eb; --bg: #f8fafc; --card-bg: #ffffff;
                --text-main: #1e293b; --text-muted: #64748b; --success: #10b981;
                --warning: #f59e0b; --danger: #ef4444; --border: #e2e8f0;
            }}
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: var(--bg); color: var(--text-main); line-height: 1.5; }}
            .container {{ max-width: 1200px; margin: 0 auto; padding: 40px 20px; }}
            header {{ background: var(--primary); color: white; padding: 30px 40px; border-radius: 12px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); }}
            header h1 {{ font-size: 24px; font-weight: 600; }} header p {{ color: #94a3b8; font-size: 14px; margin-top: 5px; }}
            .timestamp {{ font-size: 13px; color: #cbd5e1; text-align: right; }}
            .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 40px; }}
            .kpi-card {{ background: var(--card-bg); padding: 24px; border-radius: 12px; border-left: 4px solid var(--accent); box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); }}
            .kpi-value {{ font-size: 32px; font-weight: 700; color: var(--primary); margin-bottom: 8px; }}
            .kpi-label {{ color: var(--text-muted); font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; }}
            .kpi-card.success {{ border-left-color: var(--success); }} .kpi-card.warning {{ border-left-color: var(--warning); }}
            .section {{ background: var(--card-bg); padding: 30px; border-radius: 12px; margin-bottom: 30px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); }}
            .section-title {{ font-size: 18px; font-weight: 600; color: var(--primary); margin-bottom: 24px; display: flex; align-items: center; gap: 10px; }}
            .chart-row {{ display: flex; align-items: center; margin-bottom: 16px; }}
            .chart-label {{ width: 120px; font-size: 14px; font-weight: 600; }}
            .chart-track {{ flex-grow: 1; background: #f1f5f9; height: 24px; border-radius: 4px; position: relative; margin: 0 15px; }}
            .chart-fill {{ height: 100%; border-radius: 4px; transition: width 0.5s ease; }}
            .chart-percent {{ position: absolute; top: 50%; transform: translateY(-50%); font-size: 12px; font-weight: 600; color: var(--text-muted); margin-left: 8px; }}
            .chart-value {{ width: 60px; text-align: right; font-size: 14px; font-weight: 700; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th {{ text-align: left; padding: 12px 16px; background: #f1f5f9; color: var(--text-muted); font-size: 12px; text-transform: uppercase; font-weight: 600; border-bottom: 2px solid var(--border); }}
            td {{ padding: 16px; border-bottom: 1px solid var(--border); font-size: 14px; }}
            .exception-table thead th {{ background: #0f172a; color: white; font-weight: 600; }}
            .badge {{ display: inline-block; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: 600; }}
            .badge-danger {{ background: #fee2e2; color: #991b1b; }} .badge-warning {{ background: #fef3c7; color: #92400e; }} .badge-info {{ background: #dbeafe; color: #1e40af; }}
            footer {{ text-align: center; color: var(--text-muted); font-size: 13px; margin-top: 40px; border-top: 1px solid var(--border); padding-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <div>
                    <h1>🏦 Bancapp Reconciliation Dashboard</h1>
                    <p>Automated Financial Reconciliation & Exception Management Report</p>
                </div>
                <div class="timestamp">Generated on<br>{timestamp}</div>
            </header>

            <div class="kpi-grid">
                <div class="kpi-card"><div class="kpi-value">{int(total_int)}</div><div class="kpi-label">Total Internal Txns</div></div>
                <div class="kpi-card"><div class="kpi-value">{int(total_bank)}</div><div class="kpi-label">Total Bank Lines</div></div>
                <div class="kpi-card success"><div class="kpi-value">{int(matched_int)}</div><div class="kpi-label">Internal Matched</div></div>
                <div class="kpi-card success"><div class="kpi-value">{int(matched_bank)}</div><div class="kpi-label">Bank Lines Matched</div></div>
                <div class="kpi-card warning"><div class="kpi-value">{total_exceptions}</div><div class="kpi-label">Total Exceptions</div></div>
                <div class="kpi-card success"><div class="kpi-value">{int(backlog_cleared)}</div><div class="kpi-label">May Backlog Cleared</div></div>
            </div>

            <div class="section">
                <div class="section-title"><span>✅</span> Reconciliation Status Summary (Unified View)</div>
    """

    status_colors = {'MATCHED': 'var(--success)', 'PARTIAL_MATCH': 'var(--warning)', 'OPEN': 'var(--accent)', 'EXCEPTION': 'var(--danger)'}
    for status, count in status_counts.items():
        pct = status_percentages.get(status, 0)
        color = status_colors.get(status, 'var(--accent)')
        html_content += f"""
                <div class="chart-row">
                    <div class="chart-label">{status}</div>
                    <div class="chart-track">
                        <div class="chart-fill" style="width: {pct}%; background-color: {color};"></div>
                        <div class="chart-percent" style="left: {pct}%;">{pct:.1f}%</div>
                    </div>
                    <div class="chart-value">{count}</div>
                </div>
        """

    html_content += f"""
            </div>

            <div class="section">
                <div class="section-title"><span>🔗</span> Matching Cardinality Distribution (Matched Only)</div>
    """

    for card, count in sorted(cardinality_counts.items(), key=lambda x: x[1], reverse=True):
        pct = card_percentages.get(card, 0)
        html_content += f"""
                <div class="chart-row">
                    <div class="chart-label">{card}</div>
                    <div class="chart-track">
                        <div class="chart-fill" style="width: {pct}%; background-color: var(--accent);"></div>
                        <div class="chart-percent" style="left: {pct}%;">{pct:.1f}%</div>
                    </div>
                    <div class="chart-value">{count}</div>
                </div>
        """

    html_content += f"""
            </div>

            <div class="section">
                <div class="section-title"><span>️</span> Exception Breakdown (Total: {total_exceptions})</div>
                <table class="exception-table">
                    <thead><tr><th>Exception Category</th><th>Count</th><th>Severity</th></tr></thead>
                    <tbody>
    """

    severity_map = {'GENUINE_EXCEPTION': 'danger', 'SETTLEMENT_LAG': 'warning', 'DUPLICATE_BANK_CREDIT': 'danger', 'ORPHAN_BANK_CREDIT': 'warning', 'INTERNAL_SELF_NETTING': 'info'}
    for category, count in sorted(exception_counts.items(), key=lambda x: x[1], reverse=True):
        severity = severity_map.get(category, 'info')
        html_content += f"""
                        <tr>
                            <td>{category.replace('_', ' ').title()}</td>
                            <td>{count}</td>
                            <td><span class="badge badge-{severity}">{severity.replace('_', ' ').title()}</span></td>
                        </tr>
        """

    html_content += """
                    </tbody>
                </table>
            </div>
            <footer><p>Generated by Bancapp Reconciliation Engine | Confidential & Proprietary</p></footer>
        </div>
    </body>
    </html>
    """

    with open("output/reconciliation_dashboard.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("✅ Dashboard generated successfully.")

if __name__ == "__main__":
    generate_html_dashboard()