"""Market Risk AI Assistant V16: Greek sensitivity proxies."""

from archive.versions import market_risk_agent_v15 as v15
from google.genai import types

VERSION = "V16"
v15.v9.VERSION = VERSION
v14 = v15.v14
v13 = v15.v13
v12 = v15.v12
v11 = v15.v11
v9 = v15.v9
v8 = v15.v8


def get_greek_sensitivities():
    """Return current Greek-labelled P&L-driver proxies from the demo extract."""
    current = v8.df.iloc[-1]
    values = {
        "Delta": float(current["pnl_driver_fx_delta"]),
        "Gamma": float(current["pnl_driver_gamma"]),
        "Vega": float(current["pnl_driver_vega"]),
        "Theta": float(current["pnl_driver_theta"]),
    }
    return {
        "as_of_date": str(current["cob_date"].date()),
        "sensitivities": values,
        "usage_note": "These are P&L-driver proxies from the demo input, not independently calculated risk-engine Greek exposures.",
    }


v8.TOOL_FUNCTIONS["get_greek_sensitivities"] = get_greek_sensitivities
v8.TOOL_DESCRIPTIONS["get_greek_sensitivities"] = "Current Delta, Gamma, Vega and Theta P&L-driver proxies from the demo extract."
v9.SYSTEM_INSTRUCTION += """

V16 sensitivity control:
- get_greek_sensitivities returns demo P&L-driver proxies, not calibrated Greek exposures.
- State this limitation whenever discussing these values.
"""
v9.tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=name, description=description)
    for name, description in v8.TOOL_DESCRIPTIONS.items()
])]
ask_risk_agent = v15.ask_risk_agent
