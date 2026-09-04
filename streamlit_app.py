"""Streamlit entry point for the MIRAI demo."""

import runpy
from pathlib import Path

# Streamlit reruns this file after every widget interaction. ``runpy`` executes
# the dashboard on every rerun; a normal import would execute it only once and
# leave subsequent reruns blank because of Python's module cache.
runpy.run_path(
    str(Path(__file__).with_name("market_risk_dashboard_v32.py")),
    run_name="__main__",
)
