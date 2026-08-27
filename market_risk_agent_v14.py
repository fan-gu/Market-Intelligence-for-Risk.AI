"""Market Risk AI Assistant V14: portfolio scope awareness."""

import market_risk_agent_v13 as v13
from google.genai import types


VERSION = "V14"
v12 = v13.v12
v11 = v13.v11
v9 = v13.v9
v8 = v13.v8


def get_portfolio_scope():
    """Return the portfolios present in the current risk-run extract."""
    scope = (
        v8.df.groupby("portfolio_id", dropna=False)
        .agg(observation_count=("cob_date", "size"), reporting_currency=("reporting_currency", "first"))
        .reset_index()
    )
    return {
        "portfolio_count": int(len(scope)),
        "portfolios": scope.to_dict(orient="records"),
        "usage_note": "Portfolio scope comes from the current risk-run extract; it is not a portfolio hierarchy service.",
    }


# Register exactly one new V14 agent-visible deterministic function.
v8.TOOL_FUNCTIONS["get_portfolio_scope"] = get_portfolio_scope
v8.TOOL_DESCRIPTIONS["get_portfolio_scope"] = (
    "Portfolio IDs, reporting currencies and observation counts present in the current risk-run extract."
)
v9.VERSION = VERSION
v9.SYSTEM_INSTRUCTION += """

V14 portfolio control:
- get_portfolio_scope reports only the portfolios present in the supplied risk-run extract.
- Do not infer a missing hierarchy, legal entity or booking structure.
"""
v9.tools = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(name=name, description=description)
        for name, description in v8.TOOL_DESCRIPTIONS.items()
    ])
]

ask_risk_agent = v9.ask_risk_agent

# Streamlit has no need for console diagnostics; redirecting them also avoids Windows code-page errors.
import contextlib
import io

def ask_risk_agent(question):
    with contextlib.redirect_stdout(io.StringIO()):
        return v13.ask_risk_agent(question)
