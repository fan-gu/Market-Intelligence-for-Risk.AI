"""M.R. AI Agent V27: curve-level Delta reporting and currency Vega surfaces."""

from __future__ import annotations

import pandas as pd

from archive.versions import market_risk_agent_v26 as v26
from archive.versions.market_risk_agent_v26 import *  # noqa: F401,F403 - preserve the public version API


VERSION = "V27"
v26.v9.VERSION = VERSION


def get_delta_curve_tenor_summary(currencies=None):
    """Return curve rows plus a governed subtotal for each selected currency."""
    source = v26.get_market_sensitivities()
    selected = source["currencies"] if currencies is None else currencies
    tenor_order = source["tenors"]
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
    for tenor in tenor_order:
        if tenor not in detail:
            detail[tenor] = 0.0

    rows = []
    for currency in selected:
        currency_detail = detail.loc[detail["currency"] == currency].sort_values(
            ["curve_type", "curve"]
        )
        for item in currency_detail.to_dict("records"):
            tenor_values = [float(item[tenor]) for tenor in tenor_order]
            rows.append({
                "currency": currency,
                "curve_type": item["curve_type"],
                "curve": item["curve"],
                **{tenor: float(item[tenor]) for tenor in tenor_order},
                "net_delta": sum(tenor_values),
                "net_limit": None,
                "net_pct": None,
                "gross_delta": sum(abs(value) for value in tenor_values),
                "gross_limit": None,
                "gross_pct": None,
                "row_type": "Curve",
            })

        currency_nodes = delta.loc[delta["currency"] == currency]
        net_delta = float(currency_nodes["value"].sum())
        gross_delta = float(currency_nodes["value"].abs().sum())
        limits = v26.DELTA_LIMITS[currency]
        tenor_totals = currency_nodes.groupby("tenor")["value"].sum()
        rows.append({
            "currency": currency,
            "curve_type": "Subtotal",
            "curve": f"{currency} total",
            **{tenor: float(tenor_totals.get(tenor, 0.0)) for tenor in tenor_order},
            "net_delta": net_delta,
            "net_limit": limits["net"],
            "net_pct": abs(net_delta) / limits["net"] * 100.0,
            "gross_delta": gross_delta,
            "gross_limit": limits["gross"],
            "gross_pct": gross_delta / limits["gross"] * 100.0,
            "row_type": "Currency subtotal",
        })

    return {
        "currencies": selected,
        "tenors": tenor_order,
        "rows": rows,
        "usage_note": (
            "Curve rows preserve the signed V25 tenor buckets. Each currency has its own subtotal, "
            "Net Delta limit and Gross Delta limit; there is no cross-currency total."
        ),
    }


v8.TOOL_FUNCTIONS["get_delta_curve_tenor_summary"] = get_delta_curve_tenor_summary
v8.TOOL_DESCRIPTIONS["get_delta_curve_tenor_summary"] = (
    "Curve and tenor IR Delta rows with governed subtotals by currency."
)

v9.SYSTEM_INSTRUCTION += """

V27 sensitivity reporting:
- Use get_delta_curve_tenor_summary when explaining curve-level or tenor-level IR Delta.
- Delta limits are evaluated separately for each currency; do not invent an all-currency subtotal.
- IR Vega is presented as a separate expiry-by-underlying-tenor surface for each currency.
"""

v9.tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=name, description=description)
    for name, description in v8.TOOL_DESCRIPTIONS.items()
])]

ask_risk_agent = v26.ask_risk_agent
