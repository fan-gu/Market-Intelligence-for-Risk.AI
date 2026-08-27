"""Market Risk AI Assistant V15: trade-to-business-line hierarchy."""

import market_risk_agent_v14 as v14
from google.genai import types

from market_risk_hierarchy_v15 import allocated_hierarchy_summary, build_hierarchy


VERSION = "V15"
v14.v9.VERSION = VERSION
v13 = v14.v13
v12 = v14.v12
v11 = v14.v11
v9 = v14.v9
v8 = v14.v8


def get_risk_hierarchy():
    """Return the synthetic V15 hierarchy and allocated risk summary."""
    books, trades = build_hierarchy()
    summary = allocated_hierarchy_summary(v8.get_current_risk())
    business_lines = summary.groupby("business_line", as_index=False).agg(
        trading_desks=("trading_desk", "nunique"),
        books=("book_id", "nunique"),
        allocated_historical_var=("allocated_historical_var", "sum"),
        allocated_stressed_var=("allocated_stressed_var", "sum"),
    )
    return {
        "business_lines": business_lines.to_dict(orient="records"),
        "trading_desk_count": int(books["trading_desk"].nunique()),
        "book_count": int(len(books)),
        "trade_count": int(len(trades)),
        "usage_note": (
            "V15 hierarchy and trade inventory are synthetic demo data. Risk amounts are transparent allocations "
            "of the aggregate risk-engine result, not trade-level revaluation or a VaR aggregation method."
        ),
    }


v8.TOOL_FUNCTIONS["get_risk_hierarchy"] = get_risk_hierarchy
v8.TOOL_DESCRIPTIONS["get_risk_hierarchy"] = (
    "Synthetic V15 trade-to-book-to-trading-desk-to-business-line hierarchy and allocated aggregate-risk summary."
)
v9.SYSTEM_INSTRUCTION += """

V15 hierarchy control:
- get_risk_hierarchy returns synthetic demo hierarchy and allocation data.
- Never state allocated amounts are trade-level revaluation or an additive VaR calculation.
"""
v9.tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=name, description=description)
    for name, description in v8.TOOL_DESCRIPTIONS.items()
])]

ask_risk_agent = v14.ask_risk_agent
