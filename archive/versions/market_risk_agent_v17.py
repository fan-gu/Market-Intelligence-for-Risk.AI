"""Market Risk AI Assistant V17: governed limits and corrected risk semantics."""

import pandas as pd

from archive.versions import market_risk_agent_v16 as v16
from google.genai import types


VERSION = "V17"
v16.v9.VERSION = VERSION
v15 = v16.v15
v14 = v16.v14
v13 = v16.v13
v12 = v16.v12
v11 = v16.v11
v9 = v16.v9
v8 = v16.v8


STRESS_SCENARIO_DEFINITIONS = {
    "2008 Lehman crisis": {"column": "stress_2008_lehman_crisis", "type": "Historical", "definition": "Portfolio revaluation under the supplied 2008 Lehman market-shock set."},
    "2011 US downgrade": {"column": "stress_2011_us_downgrade", "type": "Historical", "definition": "Portfolio revaluation under the supplied 2011 US downgrade market-shock set."},
    "2020 COVID liquidity": {"column": "stress_2020_covid_liquidity", "type": "Historical", "definition": "Portfolio revaluation under the supplied 2020 COVID liquidity market-shock set."},
    "2022 rate hikes": {"column": "stress_2022_rate_hikes", "type": "Historical", "definition": "Portfolio revaluation under the supplied 2022 rate-hike market-shock set."},
    "IR +100 bp": {"column": "stress_ir_up_100bp", "type": "Hypothetical", "definition": "Portfolio revaluation after a parallel +100 basis-point interest-rate shock."},
    "IR -100 bp": {"column": "stress_ir_down_100bp", "type": "Hypothetical", "definition": "Portfolio revaluation after a parallel -100 basis-point interest-rate shock."},
    "IR steepener 50 bp": {"column": "stress_ir_steepener_50bp", "type": "Hypothetical", "definition": "Portfolio revaluation under the supplied 50 basis-point curve-steepening shock."},
    "IR flattener 50 bp": {"column": "stress_ir_flattener_50bp", "type": "Hypothetical", "definition": "Portfolio revaluation under the supplied 50 basis-point curve-flattening shock."},
    "USD +10%": {"column": "stress_fx_usd_up_10pct", "type": "Hypothetical", "definition": "Portfolio revaluation after a supplied 10% strengthening shock to USD."},
    "Volatility +50%": {"column": "stress_vol_up_50pct", "type": "Hypothetical", "definition": "Portfolio revaluation under the supplied 50% volatility shock."},
}


def build_supplied_stress_frame(as_of_date=None):
    """Return only stress scenarios present in the supplied risk-engine extract."""
    source = v8.df
    if as_of_date is not None:
        source = source.loc[source["cob_date"] <= pd.Timestamp(as_of_date)]
    frame = source[["cob_date"]].copy()
    metadata = {}
    for scenario, definition in STRESS_SCENARIO_DEFINITIONS.items():
        frame[scenario] = source[definition["column"]].astype(float)
        metadata[scenario] = {
            "source": "Risk-engine supplied",
            "type": definition["type"],
            "definition": definition["definition"],
        }
    return frame.reset_index(drop=True), metadata


def get_stress_evolution():
    """Return risk-engine-supplied stress P&L paths, excluding illustrative proxies."""
    frame, metadata = build_supplied_stress_frame()
    return {
        "as_of_date": str(frame["cob_date"].max().date()),
        "observation_count": len(frame),
        "scenario_metadata": metadata,
        "series": {
            scenario: [
                {"date": str(row["cob_date"].date()), "impact": float(row[scenario])}
                for _, row in frame[["cob_date", scenario]].iterrows()
            ]
            for scenario in metadata
        },
        "usage_note": (
            "Stress values are risk-engine-supplied scenario revaluation P&L impacts in the reporting currency. "
            "Negative values are losses versus the base valuation. They are not first-order sensitivities."
        ),
    }


def get_market_sensitivities():
    """Return unit-aware synthetic sensitivities for the V17 demo feed."""
    current = v8.df.iloc[-1]
    rows = [
        ("IR Delta (DV01)", "EUR OIS curve", -128_000, "EUR / bp", "P&L change for a +1 bp parallel move in the named rate curve."),
        ("IR Delta (DV01)", "USD SOFR curve", 94_000, "EUR / bp", "P&L change for a +1 bp parallel move in the named rate curve."),
        ("IR Gamma", "EUR OIS curve", 1_850, "EUR / bp²", "Change in DV01 for a +1 bp move in the named rate curve."),
        ("FX Delta", "EUR/USD spot", 410_000, "EUR / 1% spot", "P&L change for a +1% move in the named FX spot rate."),
        ("Vega", "EUR swaption volatility", -63_000, "EUR / vol point", "P&L change for a +1 percentage-point move in implied volatility."),
        ("Vega", "EUR/USD implied volatility", 48_000, "EUR / vol point", "P&L change for a +1 percentage-point move in implied volatility."),
        ("Theta", "Whole portfolio", -19_000, "EUR / day", "Expected one-business-day P&L from time decay, holding market inputs constant."),
    ]
    return {
        "as_of_date": str(current["cob_date"].date()),
        "sensitivities": [
            {"measure": measure, "underlying": underlying, "value": float(value), "unit": unit, "definition": definition}
            for measure, underlying, value, unit, definition in rows
        ],
        "usage_note": (
            "Unit-aware synthetic sensitivity feed for the V17 prototype. These values are separate from "
            "P&L-explain drivers and must be replaced by risk-engine sensitivity records in production."
        ),
    }


def evaluate_limit_breaches():
    """Evaluate the configured VaR limit and return governance status."""
    current = v8.get_current_risk()
    utilization = float(current["limit_utilisation"])
    if utilization >= 100:
        status = "CRITICAL"
        escalation = "Immediate escalation required"
    elif utilization >= 80:
        status = "WARNING"
        escalation = "Owner review required"
    else:
        status = "OK"
        escalation = "No escalation"
    return {
        "as_of_date": current["date"],
        "limits": [{
            "limit_name": "Historical VaR (1 day, 99%)",
            "exposure": current["var_hist"],
            "limit": current["var_limit"],
            "utilization_pct": utilization,
            "warning_threshold_pct": 80.0,
            "critical_threshold_pct": 100.0,
            "status": status,
            "owner": "Market Risk",
            "escalation_status": escalation,
        }],
    }


v8.TOOL_FUNCTIONS.pop("get_greek_sensitivities", None)
v8.TOOL_DESCRIPTIONS.pop("get_greek_sensitivities", None)
v8.TOOL_FUNCTIONS["get_market_sensitivities"] = get_market_sensitivities
v8.TOOL_DESCRIPTIONS["get_market_sensitivities"] = "Unit-aware market sensitivities from the separate V17 demo sensitivity feed."
v8.TOOL_FUNCTIONS["get_stress_evolution"] = get_stress_evolution
v8.TOOL_DESCRIPTIONS["get_stress_evolution"] = "Risk-engine-supplied stress scenario revaluation P&L paths only."
v8.TOOL_FUNCTIONS["evaluate_limit_breaches"] = evaluate_limit_breaches
v8.TOOL_DESCRIPTIONS["evaluate_limit_breaches"] = "Configured VaR limit status, thresholds, owner and escalation state."

v9.SYSTEM_INSTRUCTION += """

V17 risk semantics and governance:
- Stress results are scenario revaluation P&L impacts; negative values are losses. Never describe them as sensitivities.
- Use get_market_sensitivities for unit-aware Greeks. IR Delta is DV01 in reporting currency per 1 bp.
- The V17 sensitivity values are synthetic demo-feed records and are separate from P&L-explain drivers.
- Use evaluate_limit_breaches for limit status, ownership and escalation.
"""
v9.tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=name, description=description)
    for name, description in v8.TOOL_DESCRIPTIONS.items()
])]

ask_risk_agent = v16.ask_risk_agent
