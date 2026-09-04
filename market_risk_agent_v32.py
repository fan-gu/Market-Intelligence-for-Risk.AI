"""MIRAI V32: explicit book-level risk records and scope aggregation."""

from __future__ import annotations

from functools import lru_cache

import pandas as pd
from google.genai import types

import market_risk_agent_v29 as v29
from market_risk_agent_v29 import *  # noqa: F401,F403 - preserve the public API
from mirai.book_risk import aggregate_scope_history, build_book_risk_history

VERSION = "V32"
v29.v9.VERSION = VERSION
v8 = v29.v8


@lru_cache(maxsize=1)
def _book_history() -> pd.DataFrame:
    books, _ = v29.v15.build_hierarchy()
    return build_book_risk_history(v8.df, books)


def get_scope_risk_summary(
    business_line: str | None = None,
    trading_desk: str | None = None,
    book_id: str | None = None,
    as_of_date: str | None = None,
):
    """Return latest risk for an explicit business-line, desk, or book perimeter."""
    history = _book_history().copy()
    filters = {
        "business_line": business_line,
        "trading_desk": trading_desk,
        "book_id": book_id,
    }
    for column, value in filters.items():
        if value:
            history = history.loc[history[column] == value]
    if as_of_date:
        history = history.loc[history["cob_date"] <= pd.Timestamp(as_of_date)]
    if history.empty:
        return {"status": "NO_DATA", "filters": filters}
    scope = aggregate_scope_history(history)
    latest = scope.iloc[-1]
    return {
        "status": "AVAILABLE",
        "as_of_date": str(pd.Timestamp(latest["cob_date"]).date()),
        "scope": {key: value for key, value in filters.items() if value},
        "book_count": int(history["book_id"].nunique()),
        "record_count": int(len(history)),
        "historical_var": float(latest["var_1d_99_hist"]),
        "stressed_var": float(latest["stressed_var_1d_99"]),
        "expected_shortfall": float(latest["expected_shortfall_97_5"]),
        "actual_pnl": float(latest["actual_pnl"]),
        "var_limit": float(latest["var_limit_amount"]),
        "var_limit_consumption_pct": float(latest["var_limit_utilization_pct"]),
        "usage_note": (
            "V32 uses explicit deterministic synthetic book/date records. VaR and SVaR are "
            "Euler-style contributions to the parent portfolio and additive across the selected perimeter."
        ),
    }


v8.TOOL_FUNCTIONS["get_scope_risk_summary"] = get_scope_risk_summary
v8.TOOL_DESCRIPTIONS["get_scope_risk_summary"] = (
    "Latest HVaR, SVaR, expected shortfall, P&L and limit usage for an explicit business-line, trading-desk or book scope."
)
v29.v9.SYSTEM_INSTRUCTION += """

V32 hierarchy evidence:
- Use get_scope_risk_summary for questions about a business line, trading desk, or book.
- State that these are deterministic synthetic book/date records and that VaR/SVaR are parent-portfolio contributions.
"""
v29.tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=name, description=description)
    for name, description in v8.TOOL_DESCRIPTIONS.items()
])]

ask_risk_agent = v29.ask_risk_agent
