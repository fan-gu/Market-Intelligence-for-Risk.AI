"""M.R. AI Agent V21: material stress selection and dedicated sensitivity views."""

from __future__ import annotations

import pandas as pd
from google.genai import types

import market_risk_agent_v20 as v20


VERSION = "V21"
v20.v9.VERSION = VERSION
v19 = v20.v19
v18 = v20.v18
v17 = v20.v17
v16 = v20.v16
v15 = v20.v15
v14 = v20.v14
v13 = v20.v13
v12 = v20.v12
v11 = v20.v11
v9 = v20.v9
v8 = v20.v8
DRIVER_COLUMNS = v20.DRIVER_COLUMNS
build_pla_demo_history = v20.build_pla_demo_history
evaluate_pla_test = v20.evaluate_pla_test
evaluate_all_limits = v20.evaluate_all_limits
evaluate_pnl_explain_alerts = v20.evaluate_pnl_explain_alerts

STRESS_SCENARIO_DEFINITIONS = {
    "2008 Lehman": {"column": "stress_2008_lehman_crisis", "type": "Historical", "definition": "Portfolio revaluation under the supplied 2008 Lehman market-shock set."},
    "2011 US downgrade": {"column": "stress_2011_us_downgrade", "type": "Historical", "definition": "Portfolio revaluation under the supplied 2011 US downgrade market-shock set."},
    "2020 COVID": {"column": "stress_2020_covid_liquidity", "type": "Historical", "definition": "Portfolio revaluation under the supplied 2020 COVID liquidity market-shock set."},
    "2022 rate hikes": {"column": "stress_2022_rate_hikes", "type": "Historical", "definition": "Portfolio revaluation under the supplied 2022 rate-hike market-shock set."},
    "IR steepener": {"column": "stress_ir_steepener_50bp", "type": "Hypothetical", "definition": "Portfolio revaluation under the supplied 50 basis-point curve-steepening shock."},
    "IR flattener": {"column": "stress_ir_flattener_50bp", "type": "Hypothetical", "definition": "Portfolio revaluation under the supplied 50 basis-point curve-flattening shock."},
    "IR +100 bp": {"column": "stress_ir_up_100bp", "type": "Adverse", "definition": "Portfolio revaluation after a parallel +100 basis-point interest-rate shock."},
    "IR -100 bp": {"column": "stress_ir_down_100bp", "type": "Adverse", "definition": "Portfolio revaluation after a parallel -100 basis-point interest-rate shock."},
    "USD +10%": {"column": "stress_fx_usd_up_10pct", "type": "Adverse", "definition": "Portfolio revaluation after a supplied 10% strengthening shock to USD."},
    "Vol +50%": {"column": "stress_vol_up_50pct", "type": "Adverse", "definition": "Portfolio revaluation under the supplied 50% volatility shock."},
}

EXTREME_SCENARIO_CONFIGURATIONS = [
    {"scenario": "IR +200 bp", "category": "Extreme", "shock": "+200 bp parallel rates", "derived_from": "IR +100 bp"},
    {"scenario": "IR -200 bp", "category": "Extreme", "shock": "-200 bp parallel rates", "derived_from": "IR -100 bp"},
    {"scenario": "USD +20%", "category": "Extreme", "shock": "+20% USD", "derived_from": "USD +10%"},
    {"scenario": "Vol +100%", "category": "Extreme", "shock": "+100% volatility", "derived_from": "Vol +50%"},
]

THETA_BY_CURRENCY = {"EUR": -8_000.0, "USD": -6_000.0, "JPY": -2_000.0, "GBP": -3_000.0}


def build_supplied_stress_frame(as_of_date=None):
    """Return unchanged priced scenarios with V21 governance categories."""
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


def get_stress_scenario_catalog():
    """Return governed definitions without manufacturing extreme P&L."""
    rows = [
        {
            "scenario": scenario,
            "category": definition["type"],
            "shock": definition["definition"],
            "pricing_status": "Priced by supplied risk-engine feed",
            "derived_from": "",
        }
        for scenario, definition in STRESS_SCENARIO_DEFINITIONS.items()
    ]
    rows.extend(
        {**configuration, "pricing_status": "Awaiting risk-engine revaluation"}
        for configuration in EXTREME_SCENARIO_CONFIGURATIONS
    )
    return rows


def get_stress_evolution():
    """Return supplied stress values and the governed V21 taxonomy."""
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
            "Curves show risk-engine-supplied revaluation P&L only. Historical scenarios replay observed periods; "
            "hypothetical scenarios reshape selected factors; adverse scenarios are severe calibrated shocks. "
            "Extreme shock parameters are twice their adverse counterparts and remain unpriced until revaluation."
        ),
    }


def get_material_stress_scenarios(as_of_date=None, maximum_scenarios=6):
    """Select material priced curves from latest magnitude and latest jump."""
    frame, metadata = build_supplied_stress_frame(as_of_date)
    if frame.empty:
        return {"selected_scenarios": [], "scenario_metrics": [], "rule": "No observations available."}
    latest = frame.iloc[-1].drop(labels="cob_date").astype(float)
    previous = frame.iloc[-2].drop(labels="cob_date").astype(float) if len(frame) > 1 else latest
    metrics = pd.DataFrame({
        "scenario": latest.index,
        "latest_impact": latest.values,
        "latest_jump": (latest - previous).values,
    })
    max_magnitude = max(float(metrics["latest_impact"].abs().max()), 1.0)
    max_jump = max(float(metrics["latest_jump"].abs().max()), 1.0)
    metrics["magnitude_score"] = metrics["latest_impact"].abs() / max_magnitude
    metrics["jump_score"] = metrics["latest_jump"].abs() / max_jump
    metrics["materiality_score"] = metrics[["magnitude_score", "jump_score"]].max(axis=1)
    metrics["category"] = metrics["scenario"].map(lambda name: metadata[name]["type"])
    metrics["selection_reason"] = metrics.apply(
        lambda row: "Large magnitude and jump"
        if row["magnitude_score"] >= 0.60 and row["jump_score"] >= 0.60
        else ("Large current magnitude" if row["magnitude_score"] >= row["jump_score"] else "Large latest jump"),
        axis=1,
    )
    material = metrics.loc[
        (metrics["magnitude_score"] >= 0.60) | (metrics["jump_score"] >= 0.60)
    ].sort_values("materiality_score", ascending=False)
    minimum = min(3, len(metrics))
    if len(material) < minimum:
        material = metrics.nlargest(minimum, "materiality_score")
    material = material.head(maximum_scenarios)
    return {
        "as_of_date": str(frame["cob_date"].max().date()),
        "selected_scenarios": material["scenario"].tolist(),
        "scenario_metrics": material.to_dict("records"),
        "rule": "Select curves at or above 60% of the largest current absolute impact or latest absolute jump; show at least three and at most six.",
    }


def get_market_sensitivities():
    """Return the V20 feed with Theta split across major currencies."""
    result = v20.get_market_sensitivities()
    rows = [row for row in result["sensitivities"] if row["measure"] != "Theta"]
    for currency, theta in THETA_BY_CURRENCY.items():
        rows.append({
            "risk_class": "Time",
            "measure": "Theta",
            "currency": currency,
            "curve_type": "Portfolio",
            "curve": f"{currency} portfolio",
            "value": theta,
            "unit": "EUR / day",
            "definition": "Expected one-business-day P&L from time decay, holding market inputs constant.",
        })
    return {
        **result,
        "sensitivities": rows,
        "usage_note": (
            "Unit-aware deterministic synthetic V21 sensitivity feed. Rates are split by EUR, USD, JPY and GBP "
            "OIS/BOR curves; FX Delta covers each non-USD currency versus USD. Replace with risk-engine records in production."
        ),
    }


v8.TOOL_FUNCTIONS["get_market_sensitivities"] = get_market_sensitivities
v8.TOOL_DESCRIPTIONS["get_market_sensitivities"] = "IR Delta, IR Gamma, IR Vega, FX Delta and Theta by major currency and curve family."
v8.TOOL_FUNCTIONS["get_stress_evolution"] = get_stress_evolution
v8.TOOL_DESCRIPTIONS["get_stress_evolution"] = "Priced stress evolution with governed Historical, Hypothetical, Adverse and Extreme categories."
v8.TOOL_FUNCTIONS["get_material_stress_scenarios"] = get_material_stress_scenarios
v8.TOOL_DESCRIPTIONS["get_material_stress_scenarios"] = "Material priced stress curves selected by current magnitude and latest jump."
v8.TOOL_FUNCTIONS["evaluate_pnl_explain_alerts"] = evaluate_pnl_explain_alerts
v8.TOOL_DESCRIPTIONS["evaluate_pnl_explain_alerts"] = "Desk flags where absolute unexplained P&L exceeds 20% of absolute APL."

v9.SYSTEM_INSTRUCTION += """

V21 dashboard controls:
- Use evaluate_pnl_explain_alerts for the 20% unexplained-to-APL control.
- Use get_material_stress_scenarios to focus the chart on large current impacts or latest jumps.
- Sensitivities use five distinct views: IR Delta, IR Gamma, IR Vega, FX Delta and Theta.
- Extreme shock parameters are twice the corresponding adverse shock, but have no P&L until risk-engine revaluation. Never double adverse P&L as a proxy.
"""
v9.tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=name, description=description)
    for name, description in v8.TOOL_DESCRIPTIONS.items()
])]

ask_risk_agent = v20.ask_risk_agent
