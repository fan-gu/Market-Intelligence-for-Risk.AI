"""Market Risk AI Assistant V13: stress-scenario evolution."""

from archive.versions import market_risk_agent_v12 as v12
from google.genai import types


VERSION = "V13"
v11 = v12.v11
v9 = v12.v9
v8 = v12.v8

SUPPLIED_SCENARIOS = {
    "2008 Lehman crisis": "stress_2008_lehman_crisis",
    "2011 US downgrade": "stress_2011_us_downgrade",
    "2020 COVID liquidity": "stress_2020_covid_liquidity",
    "2022 rate hikes": "stress_2022_rate_hikes",
    "IR +100 bp": "stress_ir_up_100bp",
    "IR -100 bp": "stress_ir_down_100bp",
    "IR steepener": "stress_ir_steepener_50bp",
    "IR flattener": "stress_ir_flattener_50bp",
    "USD +10%": "stress_fx_usd_up_10pct",
    "Volatility +50%": "stress_vol_up_50pct",
}

# These are transparent combinations of supplied stress results, not repriced
# positions and not regulatory calibrations.  They exist solely as V13 demo
# scenarios inspired by published macro-financial risk themes.
ILLUSTRATIVE_SCENARIOS = {
    "Illustrative — geopolitical and trade fragmentation": {
        "weights": {"stress_2022_rate_hikes": 0.45, "stress_fx_usd_up_10pct": 0.30, "stress_vol_up_50pct": 0.25},
        "theme": "Geopolitical escalation, trade fragmentation and supply-chain disruption.",
    },
    "Illustrative — energy and commodity supply shock": {
        "weights": {"stress_2022_rate_hikes": 0.65, "stress_vol_up_50pct": 0.35},
        "theme": "Energy and commodity price shock with higher volatility.",
    },
    "Illustrative — sovereign spread and rate shock": {
        "weights": {"stress_2011_us_downgrade": 0.45, "stress_ir_up_100bp": 0.35, "stress_ir_steepener_50bp": 0.20},
        "theme": "Sovereign-risk repricing and adverse curve movement.",
    },
    "Illustrative — global liquidity and volatility shock": {
        "weights": {"stress_2020_covid_liquidity": 0.60, "stress_vol_up_50pct": 0.40},
        "theme": "Abrupt liquidity deterioration and volatility spike.",
    },
    "Illustrative — risk-assets correlation sell-off": {
        "weights": {"stress_2008_lehman_crisis": 0.60, "stress_2011_us_downgrade": 0.40},
        "theme": "Correlated equity and credit-risk sell-off.",
    },
    "Illustrative — USD funding and FX dislocation": {
        "weights": {"stress_fx_usd_up_10pct": 0.70, "stress_vol_up_50pct": 0.30},
        "theme": "USD funding pressure with FX and volatility dislocation.",
    },
}


def build_stress_evolution_frame():
    """Return the complete stress time series used by the V13 dashboard."""
    frame = v8.df[["cob_date"]].copy()
    metadata = {}
    for name, column in SUPPLIED_SCENARIOS.items():
        frame[name] = v8.df[column].astype(float)
        metadata[name] = {"source": "Risk-engine supplied", "theme": "Supplied stress scenario."}
    for name, definition in ILLUSTRATIVE_SCENARIOS.items():
        frame[name] = sum(v8.df[column].astype(float) * weight for column, weight in definition["weights"].items())
        metadata[name] = {"source": "Illustrative V13 proxy", "theme": definition["theme"]}
    return frame, metadata


def get_stress_evolution():
    """Return risk-engine and labelled illustrative stress paths through time."""
    frame, metadata = build_stress_evolution_frame()
    return {
        "as_of_date": str(frame["cob_date"].max().date()),
        "observation_count": len(frame),
        "scenario_metadata": metadata,
        "series": {
            scenario: [
                {"date": str(row["cob_date"].date()), "impact": float(row[scenario])}
                for _, row in frame[["cob_date", scenario]].iterrows()
            ]
            for scenario in frame.columns
            if scenario != "cob_date"
        },
        "usage_note": (
            "Risk-engine supplied scenarios are deterministic inputs. Illustrative V13 scenarios are transparent "
            "weighted proxies of supplied stress results, not independent pricing-engine calculations or regulatory scenarios."
        ),
    }


# Register exactly one new V13 agent-visible deterministic function.
v8.TOOL_FUNCTIONS["get_stress_evolution"] = get_stress_evolution
v8.TOOL_DESCRIPTIONS["get_stress_evolution"] = (
    "Stress-scenario time series, separating risk-engine supplied scenarios from labelled V13 illustrative proxies."
)
v9.VERSION = VERSION
v9.SYSTEM_INSTRUCTION += """

V13 stress control:
- get_stress_evolution is the source for stress paths over time.
- Clearly distinguish risk-engine supplied scenarios from illustrative V13 proxy scenarios.
- Do not call an illustrative proxy a regulatory scenario or pricing-engine result.
"""
v9.tools = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(name=name, description=description)
        for name, description in v8.TOOL_DESCRIPTIONS.items()
    ])
]

ask_risk_agent = v9.ask_risk_agent
