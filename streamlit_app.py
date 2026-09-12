"""Stable Streamlit entry point for the consolidated MIRAI application."""

import runpy
from pathlib import Path

# Streamlit reruns this file for every interaction. Execute the active modular
# shell each time so Python module caching cannot produce a blank second page.
runpy.run_path(
    str(Path(__file__).parent / "mirai" / "ui" / "app.py"),
    run_name="__main__",
)
