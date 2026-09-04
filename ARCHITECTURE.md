# MIRAI architecture (V31)

V30 is the stable Streamlit dashboard. V31 introduces a deliberately small service boundary:

```text
Synthetic approved risk feed → MIRAI risk service → FastAPI → Streamlit/API clients
                                      ↓
                                SQLite audit trail
```

- `mirai/risk_service.py` owns feed loading, date selection, limit classification and illustrative scenario calculations.
- `mirai/api.py` exposes validated, documented REST endpoints.
- `mirai/audit.py` records API investigation events in SQLite.
- `market_risk_dashboard_v31.py` is a small API-backed console; it does not replace the V30 product dashboard.

The synthetic feed remains the source for this demo. In a bank integration, the risk engine would publish approved runs to this service or its governed data store.
