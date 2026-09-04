"""MIRAI V31 API-backed console. V30 remains the full product dashboard."""

from __future__ import annotations

import json
import os
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import streamlit as st

st.set_page_config(page_title="MIRAI V31 | Risk Run API", page_icon=":material/api:", layout="wide")
API_BASE_URL = os.getenv("MIRAI_API_URL", "http://localhost:8000").rstrip("/")


@st.cache_data(ttl=10)
def api_get(path: str, params: dict | None = None):
    query = f"?{urlencode(params)}" if params else ""
    with urlopen(f"{API_BASE_URL}{path}{query}", timeout=5) as response:  # nosec B310 - demo-configured local API URL
        return json.loads(response.read().decode("utf-8"))


st.title("M.I.R.A.I. V31")
st.caption("API-backed risk-run console. V30 remains the stable full dashboard.")
try:
    health = api_get("/health")
    summary = api_get("/risk/summary")
except (URLError, TimeoutError) as error:
    st.error(f"The MIRAI API is unavailable at {API_BASE_URL}. Start it with: python -m uvicorn mirai.api:app --reload --port 8000")
    st.stop()

st.success(f"API online · {health['service']} · {health['version']}")
metrics = st.columns(3)
metrics[0].metric("P&L", f"{summary['pnl']:,.0f}")
metrics[1].metric("HVaR", f"{summary['hvar']['value']:,.0f}", f"{summary['hvar']['consumption_pct']:.1f}% of limit")
metrics[2].metric("SVaR", f"{summary['svar']['value']:,.0f}", f"{summary['svar']['consumption_pct']:.1f}% of limit")
st.json(summary, expanded=False)
