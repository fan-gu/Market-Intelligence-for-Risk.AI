"""M.R. AI Agent V28: curve limits and compact sensitivity presentation."""

from __future__ import annotations

import pandas as pd
from google.genai import types

from archive.versions import market_risk_agent_v27 as v27
from archive.versions.market_risk_agent_v27 import *  # noqa: F401,F403 - preserve the public version API


VERSION = "V28"
v27.v9.VERSION = VERSION
DRIVER_COLUMNS = v27.v26.v25.DRIVER_COLUMNS

DISPLAY_TENORS = ["1M", "3M", "6M", "1Y", "2Y", "5Y", "10Y+"]
CURVE_FAMILY_LIMIT_SHARES = {"OIS": 0.55, "BOR": 0.30, "Inflation": 0.15}


def get_delta_curve_tenor_summary(currencies=None):
    """Return curve-level Delta limits and one subtotal per currency."""
    source = v27.get_market_sensitivities()
    selected = source["currencies"] if currencies is None else currencies
    frame = pd.DataFrame(source["sensitivities"])
    delta = frame.loc[
        (frame["measure"] == "IR Delta (DV01)")
        & frame["currency"].isin(selected)
    ].copy()

    detail = delta.pivot_table(
        index=["currency", "curve_type", "curve"],
        columns="tenor",
        values="value",
        aggfunc="sum",
        fill_value=0.0,
    ).reset_index()
    for tenor in ["1M", "3M", "6M", "1Y", "2Y", "5Y", "10Y", "30Y"]:
        if tenor not in detail:
            detail[tenor] = 0.0
    detail["10Y+"] = detail["10Y"] + detail["30Y"]

    rows = []
    for currency in selected:
        currency_detail = detail.loc[detail["currency"] == currency].sort_values(
            ["curve_type", "curve"]
        )
        family_counts = currency_detail.groupby("curve_type")["curve"].nunique().to_dict()
        currency_limits = v27.v26.DELTA_LIMITS[currency]

        for item in currency_detail.to_dict("records"):
            tenor_values = [float(item[tenor]) for tenor in DISPLAY_TENORS]
            family_share = CURVE_FAMILY_LIMIT_SHARES.get(item["curve_type"], 0.0)
            curve_count = max(int(family_counts.get(item["curve_type"], 1)), 1)
            curve_share = family_share / curve_count
            net_limit = float(currency_limits["net"]) * curve_share
            gross_limit = float(currency_limits["gross"]) * curve_share
            net_delta = sum(tenor_values)
            gross_delta = sum(abs(value) for value in tenor_values)
            rows.append({
                "currency": currency,
                "curve_type": item["curve_type"],
                "curve": str(item["curve"]).replace("\ufffdSTR", "ESTR"),
                **{tenor: float(item[tenor]) for tenor in DISPLAY_TENORS},
                "net_delta": net_delta,
                "net_limit": net_limit,
                "net_pct": abs(net_delta) / net_limit * 100.0 if net_limit else 0.0,
                "gross_delta": gross_delta,
                "gross_limit": gross_limit,
                "gross_pct": gross_delta / gross_limit * 100.0 if gross_limit else 0.0,
                "row_type": "Curve",
            })

        currency_nodes = delta.loc[delta["currency"] == currency].copy()
        tenor_totals = currency_nodes.groupby("tenor")["value"].sum()
        display_totals = {
            tenor: float(tenor_totals.get(tenor, 0.0))
            for tenor in DISPLAY_TENORS
            if tenor != "10Y+"
        }
        display_totals["10Y+"] = float(
            tenor_totals.get("10Y", 0.0) + tenor_totals.get("30Y", 0.0)
        )
        net_delta = sum(display_totals.values())
        gross_delta = sum(
            row["gross_delta"]
            for row in rows
            if row["currency"] == currency and row["row_type"] == "Curve"
        )
        rows.append({
            "currency": currency,
            "curve_type": "Subtotal",
            "curve": f"{currency} total",
            **display_totals,
            "net_delta": net_delta,
            "net_limit": float(currency_limits["net"]),
            "net_pct": abs(net_delta) / float(currency_limits["net"]) * 100.0,
            "gross_delta": gross_delta,
            "gross_limit": float(currency_limits["gross"]),
            "gross_pct": gross_delta / float(currency_limits["gross"]) * 100.0,
            "row_type": "Currency subtotal",
        })

    return {
        "currencies": selected,
        "tenors": DISPLAY_TENORS,
        "rows": rows,
        "usage_note": (
            "10Y+ combines the 10Y and 30Y source nodes so no Delta is discarded. Curve limits are "
            "fixed prototype allocations of each currency limit: 55% OIS, 30% BOR and 15% Inflation, "
            "split equally between curves in a family."
        ),
    }


v8.TOOL_FUNCTIONS["get_delta_curve_tenor_summary"] = get_delta_curve_tenor_summary
v8.TOOL_DESCRIPTIONS["get_delta_curve_tenor_summary"] = (
    "Curve-level IR Delta, 10Y+ bucket, limits, consumption and currency subtotals."
)

v9.SYSTEM_INSTRUCTION += """

V28 sensitivity conventions:
- Net/Gross terminology is reserved for IR Delta.
- The displayed 10Y+ Delta bucket combines the 10Y and 30Y source nodes.
- Curve-level limits are prototype allocations and must not be represented as approved bank limits.
"""
v9.tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=name, description=description)
    for name, description in v8.TOOL_DESCRIPTIONS.items()
])]

ask_risk_agent = v27.ask_risk_agent
