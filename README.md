# M.I.R.A.I. — Market Intelligence for Risk AI

[![MIRAI CI](https://github.com/fan-gu/Market-Intelligence-for-Risk.AI/actions/workflows/ci.yml/badge.svg)](https://github.com/fan-gu/Market-Intelligence-for-Risk.AI/actions/workflows/ci.yml)

An open, synthetic-data prototype of a market-risk manager cockpit. MIRAI treats validated risk runs as the source of truth, then adds hierarchy drill-down, explainable charts, scenario analysis, controls, and an auditable Gemini-powered assistant.

## See it in action

Run the app locally, or try the live demo on [Streamlit Community Cloud](https://market-intelligence-risk-ai.streamlit.app/).

![Risk cockpit overview](docs/screenshots/overview.png)

## Main functions

- **Risk cockpit:** explicit book/date risk records aggregated through book, trading-desk, business-line, and bank-wide views.
- **VaR, P&L and sensitivities:** historical VaR/SVaR, P&L attribution, PLA indicators, and IR/FX risk-factor views.
- **Stress and controls:** historical, hypothetical, adverse, and extreme scenarios with limits, consumption, warnings, and breaches.
- **Scenario Lab:** change a shock and see the deterministic stressed P&L/risk response immediately.
- **Ask MIRAI:** ask questions over the selected risk run; answers cite the underlying deterministic tools and can be audited.

## Run locally

```powershell
cd "C:\FG\Market Risk AI"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Add your own GEMINI_API_KEY to .env
python -m streamlit run streamlit_app.py
```

The app opens at `http://localhost:8501`. For Streamlit Cloud, select `streamlit_app.py` as the main file and add `GEMINI_API_KEY` under App settings → Secrets. Never commit a real key.

## Project layout

```text
streamlit_app.py                 tiny deployment entrypoint
market_risk_dashboard_v32.py     current Streamlit dashboard
market_risk_agent_v32.py         scope-aware agent API
mirai/book_risk.py               granular book-risk generation and aggregation
data/                             synthetic risk-run data
archive/versions/                 earlier versions, retained for history
docs/                             references and README screenshots
```

## Data and scope

The included data is synthetic and compact. V32 creates 5,200 explicit records (20 books across 260 business dates); additive measures reconcile daily to the supplied bank-wide source. VaR and SVaR book fields are Euler-style contributions to the parent portfolio, not standalone revaluations. This is a demonstrator, not a production risk engine, official bank architecture, investment advice, or a substitute for independent model validation.

## Version update log

- **V32:** explicit book-level daily risk records, hierarchy-aware aggregation, scoped VaR/P&L/stress/limits, and book-to-bank reconciliation controls.
- **V31:** typed FastAPI boundary, SQLite audit trail, CI tests, and Architecture & Governance view.
- **V30:** bank-wide Dashboard summary, project-wide SVaR governance, and MIRAI branding.
- **V29:** Scenario Lab with deterministic what-if shocks and audit trail; deployment-ready entrypoint.
- **V28:** compact curve sensitivity tables, IR Vega surfaces, and cleaner Stress/Ask-agent presentation.
- **V27:** VaR movement attribution and improved P&L explain visualisation.
- **V26:** hierarchy filters, governance controls, and risk-factor limits.
- **V25:** tenor-aware sensitivities across currencies and curve families.
- **V24:** hierarchy exploration and transparent synthetic allocations.
- **V23:** daily/weekly/monthly VaR movement context.
- **V22:** VaR movement attribution foundation.
- **V21:** Scenario Lab foundation and stress categories.
- **V20:** daily risk brief and workflow foundations.
- **V19:** portfolio aggregation and risk-run comparison foundations.
- **V18:** P&L explain and explained/unexplained controls.
- **V17:** limits and governance across risk factors.
- **V16:** sensitivities tab (IR Delta/Gamma/Vega, FX Delta, Theta).
- **V15:** trade → book → trading desk → business-line hierarchy.
- **V14 and earlier:** ingestion, deterministic analytics, memory, and initial dashboard iterations (see `archive/versions/`).

## V31 architecture foundation

V31 added a separate, testable risk-run API beneath the dashboard:

- `GET /health`, `GET /risk/summary`, `GET /risk/breaches`, `POST /risk/scenario`, `POST /agent/query`, and `GET /runs/{run_id}/audit-trail`.
- Independent risk-data/limit logic, Pydantic request-validation, SQLite audit events, pytest tests and GitHub Actions CI.
- An **Architecture & Governance** page distinguishes implemented services from planned LangGraph/RAG capabilities and shows human approval gates.
- Start locally with `python -m uvicorn mirai.api:app --reload --port 8000`, then run `python -m streamlit run mirai_api_console_v31.py` for the API console. The public entrypoint now serves V32.

V30 and V31 remain recoverable through the `v30-stable` and `v31-stable` Git tags.
