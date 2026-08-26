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
        print("Error: Please run run_reconciliation.py first.")
        return

    # Calculate metrics
    total_exceptions = len(exception_df)
    exception_counts = exception_df['exception_category'].value_counts().to_dict()
    
    # Filter reco_df for status and cardinality
    status_counts = reco_df['status'].value_counts().to_dict()
    cardinality_counts = reco_df[reco_df['status'].isin(['MATCHED', 'PARTIAL_MATCH'])]['cardinality'].value_counts().to_dict()
    
    # Percentages
    total_reco_records = len(reco_df)
    status_percentages = {k: (v / total_reco_records) * 100 for k, v in status_counts.items()}
    
    total_cardinality = sum(cardinality_counts.values())
    card_percentages = {k: (v / total_cardinality) * 100 for k, v in cardinality_counts.items()} if total_cardinality > 0 else {}

    # Sum the counts across May and June to get the big totals
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
                --primary: #1e3a5f;
                --secondary: #2c5282;
                --accent: #3182ce;
                --bg: #f7fafc;
                --card-bg: #ffffff;
                --text-main: #2d3748;
                --text-muted: #718096;
                --success: #38a169;
                --warning: #d69e2e;
                --danger: #e53e3e;
                --info: #3182ce;
                --border: #e2e8f0;
            }}
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{ 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', sans-serif; 
                background-color: var(--bg); 
                color: var(--text-main); 
                line-height: 1.6;
            }}
            .container {{ max-width: 1200px; margin: 0 auto; padding: 40px 20px; }}
            
            /* Header */
            header {{ 
                background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%); 
                color: white; 
                padding: 40px; 
                border-radius: 8px; 
                margin-bottom: 40px; 
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }}
            header h1 {{ font-size: 28px; font-weight: 600; margin-bottom: 8px; letter-spacing: -0.5px; }}
            header p {{ color: #e2e8f0; font-size: 15px; font-weight: 400; }}
            .timestamp {{ font-size: 13px; color: #cbd5e0; text-align: right; margin-top: 15px; }}

            /* KPI Cards */
            .kpi-grid {{ 
                display: grid; 
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
                gap: 20px; 
                margin-bottom: 40px; 
            }}
            .kpi-card {{ 
                background: var(--card-bg); 
                padding: 28px; 
                border-radius: 8px; 
                border-left: 4px solid var(--accent); 
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
                transition: transform 0.2s, box-shadow 0.2s;
            }}
            .kpi-card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1); }}
            .kpi-value {{ font-size: 36px; font-weight: 700; color: var(--primary); margin-bottom: 8px; line-height: 1.2; }}
            .kpi-label {{ color: var(--text-muted); font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; }}
            .kpi-card.success {{ border-left-color: var(--success); }}
            .kpi-card.warning {{ border-left-color: var(--warning); }}
            .kpi-card.danger {{ border-left-color: var(--danger); }}

            /* Sections */
            .section {{ 
                background: var(--card-bg); 
                padding: 32px; 
                border-radius: 8px; 
                margin-bottom: 32px; 
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
                border: 1px solid var(--border);
            }}
            .section-title {{ 
                font-size: 18px; 
                font-weight: 600; 
                color: var(--primary); 
                margin-bottom: 24px; 
                padding-bottom: 12px;
                border-bottom: 2px solid var(--border);
            }}
            .section-description {{
                color: var(--text-muted);
                font-size: 14px;
                margin-bottom: 20px;
                line-height: 1.6;
            }}

            /* Charts */
            .chart-row {{ display: flex; align-items: center; margin-bottom: 16px; }}
            .chart-label {{ 
                width: 180px; 
                font-size: 14px; 
                font-weight: 600; 
                color: var(--text-main);
            }}
            .chart-track {{ 
                flex-grow: 1; 
                background: #edf2f7; 
                height: 28px; 
                border-radius: 4px; 
                position: relative; 
                margin: 0 15px; 
                overflow: hidden;
            }}
            .chart-fill {{ 
                height: 100%; 
                border-radius: 4px; 
                transition: width 0.6s ease;
                display: flex;
                align-items: center;
                padding-left: 12px;
                font-size: 12px;
                font-weight: 600;
                color: white;
            }}
            .chart-value {{ 
                width: 80px; 
                text-align: right; 
                font-size: 14px; 
                font-weight: 700; 
                color: var(--primary);
            }}

            /* Tables */
            table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
            th {{ 
                text-align: left; 
                padding: 14px 16px; 
                background: var(--primary); 
                color: white; 
                font-size: 13px; 
                text-transform: uppercase; 
                font-weight: 600; 
                letter-spacing: 0.5px;
            }}
            td {{ 
                padding: 14px 16px; 
                border-bottom: 1px solid var(--border); 
                font-size: 14px;
                color: var(--text-main);
            }}
            tr:hover {{ background: #f7fafc; }}
            tr:last-child td {{ border-bottom: none; }}
            
            /* Badges */
            .badge {{ 
                display: inline-block; 
                padding: 6px 14px; 
                border-radius: 4px; 
                font-size: 12px; 
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.3px;
            }}
            .badge-success {{ background: #c6f6d5; color: #22543d; }}
            .badge-warning {{ background: #fefcbf; color: #744210; }}
            .badge-danger {{ background: #fed7d7; color: #742a2a; }}
            .badge-info {{ background: #bee3f8; color: #2a4365; }}

            /* Footer */
            footer {{ 
                text-align: center; 
                color: var(--text-muted); 
                font-size: 13px; 
                margin-top: 40px; 
                padding-top: 20px; 
                border-top: 1px solid var(--border);
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>Bancapp Reconciliation Dashboard</h1>
                <p>Automated Financial Reconciliation and Exception Management Report</p>
                <div class="timestamp">Generated on {timestamp}</div>
            </header>

            <div class="kpi-grid">
                <div class="kpi-card">
                    <div class="kpi-value">{int(total_int)}</div>
                    <div class="kpi-label">Total Internal Transactions</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-value">{int(total_bank)}</div>
                    <div class="kpi-label">Total Bank Lines</div>
                </div>
                <div class="kpi-card success">
                    <div class="kpi-value">{int(matched_int)}</div>
                    <div class="kpi-label">Internal Transactions Matched</div>
                </div>
                <div class="kpi-card success">
                    <div class="kpi-value">{int(matched_bank)}</div>
                    <div class="kpi-label">Bank Lines Matched</div>
                </div>
                <div class="kpi-card warning">
                    <div class="kpi-value">{total_exceptions}</div>
                    <div class="kpi-label">Total Exceptions</div>
                </div>
                <div class="kpi-card success">
                    <div class="kpi-value">{int(backlog_cleared)}</div>
                    <div class="kpi-label">May Backlog Cleared in June</div>
                </div>
            </div>

            <div class="section">
                <div class="section-title">Reconciliation Status Summary</div>
                <div class="section-description">
                    Overview of reconciliation outcomes across all transactions. Matched items have been successfully reconciled, 
                    exceptions require investigation, and open items are pending settlement.
                </div>
    """

    status_colors = {
        'MATCHED': 'var(--success)', 
        'PARTIAL_MATCH': 'var(--warning)', 
        'OPEN': 'var(--info)', 
        'EXCEPTION': 'var(--danger)'
    }
    for status, count in status_counts.items():
        pct = status_percentages.get(status, 0)
        color = status_colors.get(status, 'var(--accent)')
        html_content += f"""
                <div class="chart-row">
                    <div class="chart-label">{status.replace('_', ' ').title()}</div>
                    <div class="chart-track">
                        <div class="chart-fill" style="width: {pct}%; background-color: {color};">
                            {pct:.1f}%
                        </div>
                    </div>
                    <div class="chart-value">{count}</div>
                </div>
        """

    html_content += f"""
            </div>

            <div class="section">
                <div class="section-title">Matching Cardinality Distribution</div>
                <div class="section-description">
                    Distribution of matched transactions by cardinality type. 
                    1:1 represents direct matches, while N:1, 1:N, and N:M represent batch settlements, 
                    partial settlements, and net settlements respectively.
                </div>
    """

    for card, count in sorted(cardinality_counts.items(), key=lambda x: x[1], reverse=True):
        pct = card_percentages.get(card, 0)
        html_content += f"""
                <div class="chart-row">
                    <div class="chart-label">{card}</div>
                    <div class="chart-track">
                        <div class="chart-fill" style="width: {pct}%; background-color: var(--accent);">
                            {pct:.1f}%
                        </div>
                    </div>
                    <div class="chart-value">{count}</div>
                </div>
        """

    html_content += f"""
            </div>

            <div class="section">
                <div class="section-title">Exception Breakdown</div>
                <div class="section-description">
                    Categorized exceptions requiring operational review. 
                    Settlement lag items are within normal processing timeframes, 
                    while genuine exceptions require immediate investigation.
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Exception Category</th>
                            <th>Count</th>
                            <th>Severity</th>
                        </tr>
                    </thead>
                    <tbody>
    """

    severity_map = {
        'GENUINE_EXCEPTION': 'danger', 
        'SETTLEMENT_LAG': 'warning', 
        'DUPLICATE_BANK_CREDIT': 'danger', 
        'ORPHAN_BANK_CREDIT': 'warning', 
        'INTERNAL_SELF_NETTING': 'info'
    }
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

            <footer>
                <p>Bancapp Reconciliation Engine | Confidential and Proprietary</p>
                <p style="margin-top: 8px;">For questions or support, contact the reconciliation operations team.</p>
            </footer>
        </div>
    </body>
    </html>
    """

    with open("output/reconciliation_dashboard.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("Dashboard generated successfully: output/reconciliation_dashboard.html")

if __name__ == "__main__":
    generate_html_dashboard()