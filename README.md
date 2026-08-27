# Market Risk AI Agent

Market Risk AI is a Python assistant for market-risk managers. It accepts a
risk-engine data extract, exposes deterministic analytics tools for VaR, P&L,
stress testing, limits, backtesting, and attribution, and uses Gemini to plan
and explain an evidence-led investigation.

## Current version: V14

`market_risk_agent_v11.py` builds on V8's investigation flow:

```text
PLAN → EXECUTION → OBSERVATION → SYNTHESIS
```

V9 adds auditable investigation memory. Each completed investigation is
recorded locally and the agent can retrieve recent context only when it matches
the same risk-engine data snapshot. Prior answers are never treated as current
financial evidence.


V10 adds a Streamlit dashboard with current risk metrics, VaR and P&L trends,
risk-factor attribution, stress testing, limit and backtesting controls, and
the V9 risk-agent question panel.

V11 adds transparent, rules-based risk alerts for limits, VaR movements,
backtesting exceptions, data-quality issues, and adverse stress scenarios. It
also refines the dashboard's risk-agent experience and visual hierarchy.

V12 adds a generic risk-run ingestion adapter. It validates a downstream CSV
schema and presents data lineage, validation status, data fingerprint, scope,
and a deterministic demo run ID. As the existing demo CSV does not provide
production lineage fields, generated metadata is labelled demo-only and
validation is never treated as business approval.

## Setup

1. Install Python 3.10 or later.
2. Create and activate a virtual environment.
3. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env` and provide a valid `GEMINI_API_KEY`.
5. Place a compatible risk-engine CSV file at the path configured in
   `market_risk_agent_v8.py`.
6. Run:

   ```powershell
   python market_risk_agent_v9.py
   ```

Or start the V14 dashboard:

```powershell
python -m streamlit run .\market_risk_dashboard_v14.py --server.port 8504
```
Type `exit` at the `You:` prompt to close the assistant.

## Data and security

The repository intentionally excludes `.env` files, CSV data extracts, and
`market_risk_investigation_audit.jsonl`. They can contain credentials,
confidential risk-engine data, and investigation history. Use anonymised or
synthetic data if you want to share a runnable example publicly.

## Project files

- `market_risk_agent_v8.py` — V8 baseline with deterministic analytics and an
  explicit LLM investigation workflow.
- `market_risk_agent_v9.py` — V9 memory and local audit-log enhancement.
- `market_risk_agent_v11.py` — V11 risk-alert enhancement.
- `market_risk_ingestion_v12.py` — generic CSV risk-run ingestion and validation.
- `market_risk_agent_v12.py` — V12 run-lineage enhancement.
- `market_risk_agent_v13.py` — V13 stress-scenario evolution.
- `market_risk_agent_v14.py` — V14 portfolio-scope enhancement.
- `market_risk_dashboard_v10.py` — V10 Streamlit risk-manager dashboard.
- `market_risk_dashboard_v11.py` — V11 alerts and refined agent dashboard.
- `market_risk_dashboard_v12.py` — V12 dashboard with risk-run lineage controls.
- `market_risk_dashboard_v13.py` — V13 focused risk-manager dashboard.
- `market_risk_dashboard_v14.py` — V14 dashboard with top navigation and portfolio filtering.
- `requirements.txt` — Python dependencies.
- `.env.example` — safe environment-variable template.

