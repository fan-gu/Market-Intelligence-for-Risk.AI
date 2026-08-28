# Market Risk AI Agent

Market Risk AI is a Python assistant for market-risk managers. It accepts a
risk-engine data extract, exposes deterministic analytics tools for VaR, P&L,
stress testing, limits, backtesting, and attribution, and uses Gemini to plan
and explain an evidence-led investigation.

## Current version: V21

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

V13 adds stress-scenario evolution and distinguishes risk-engine supplied
scenarios from transparent, illustrative proxy scenarios.

V14 adds top navigation, portfolio filtering, unambiguous DD/MM date labels,
and business-date controls. The current demo extract contains weekday
observations only.

V15 adds a synthetic Trade → Book → Trading desk → Business line hierarchy and
transparent allocation filters while preserving all risk-manager pages.

V16 adds a sensitivity page. V17 corrects the data semantics: P&L-explain
contributions are no longer presented as Greek exposures. Instead, V17 uses a
separate, unit-aware synthetic sensitivity feed (for example, rate Delta as
DV01 in EUR per basis point). V17 also removes all illustrative stress proxies,
shows only risk-engine-supplied scenario revaluation P&L, and adds governed VaR
limit evaluation with warning and critical thresholds, ownership, and
escalation status.

V18 generalises limit governance across VaR, SVaR, supplied stress loss,
DV01, Gamma, FX Delta, Vega, daily P&L, unexplained P&L, and backtesting.
Consumption below 80% is OK, 80% to below 100% is WARNING, and 100% or
above is BREACH. Thresholds and owners remain configurable demo values.

V19 adds official FRTB Actual P&L (APL), Hypothetical P&L (HPL), and
Risk-theoretical P&L (RTPL) terminology; desk-level P&L explain; and a
Basel-style 250-day PLA test using Spearman rank correlation and the empirical
Kolmogorov-Smirnov statistic. The desk histories are deterministic synthetic
demo data and do not constitute regulatory IMA eligibility decisions.

V20 replaces overlapping P&L level lines with grouped comparison bars, residual
bars and an HPL-versus-RTPL scatter; adds a 20% unexplained-to-|APL| alert;
expands synthetic sensitivities across EUR, USD, JPY and GBP OIS/BOR curves
and USD FX pairs; shortens stress display names without changing scenario values;
merges alerts into Controls; and gives Ask MR Agent a distinct primary action.

V21 makes the P&L bars explicit and readable, gives IR Delta, IR Gamma, IR Vega,
FX Delta and Theta separate charts, and groups rate curves by OIS/BOR family with
currency colors. Stress defaults to curves selected by current magnitude or latest
jump and labels their endpoints. Scenarios use Historical, Hypothetical, Adverse
and Extreme governance categories. Extreme shock parameters are twice the related
Adverse parameters, but remain unpriced until a risk-engine revaluation.
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

Or start the current dashboard:

```powershell
python -m streamlit run .\market_risk_dashboard_v21.py --server.port 8501
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
- `market_risk_hierarchy_v15.py` — synthetic four-level market-risk hierarchy.
- `market_risk_agent_v15.py` — V15 hierarchy enhancement.
- `market_risk_dashboard_v15.py` — V15 hierarchy-filtered dashboard.
- `market_risk_agent_v16.py` — V16 sensitivity prototype retained for version history.
- `market_risk_dashboard_v16.py` — V16 sensitivity dashboard retained for version history.
- `market_risk_agent_v17.py` — corrected stress/sensitivity semantics and limit governance.
- `market_risk_dashboard_v17.py` — V17 dashboard with the compact header and governed controls.
- `market_risk_agent_v18.py` — V18 multi-metric limit evaluation.
- `market_risk_dashboard_v18.py` — V18 dashboard with general governance in Controls.
- `market_risk_agent_v19.py` — V19 FRTB P&L attribution and PLA evaluation.
- `market_risk_dashboard_v19.py` — V19 dashboard with desk-level P&L explain and PLA.
- `market_risk_agent_v20.py` — V20 curve sensitivities, stress labels and P&L alerts.
- `market_risk_dashboard_v20.py` — V20 consolidated dashboard and highlighted agent entry.
- `market_risk_agent_v21.py` — V21 material-stress selection and scenario taxonomy.
- `market_risk_dashboard_v21.py` — V21 dedicated sensitivity charts and labelled stress curves.
- `requirements.txt` — Python dependencies.
- `.env.example` — safe environment-variable template.

