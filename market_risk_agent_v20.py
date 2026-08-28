"""M.R. AI Agent V20: richer sensitivities, P&L flags, and consolidated controls."""

from __future__ import annotations

import pandas as pd

import market_risk_agent_v19 as v19
from google.genai import types


VERSION = "V20"
v19.v9.VERSION = VERSION
v18 = v19.v18
v17 = v19.v17
v16 = v19.v16
v15 = v19.v15
v14 = v19.v14
v13 = v19.v13
v12 = v19.v12
v11 = v19.v11
v9 = v19.v9
v8 = v19.v8
DRIVER_COLUMNS = v19.DRIVER_COLUMNS
build_pla_demo_history = v19.build_pla_demo_history
evaluate_pla_test = v19.evaluate_pla_test
evaluate_all_limits = v19.evaluate_all_limits

UNEXPLAINED_APL_ALERT_THRESHOLD_PCT = 20.0

STRESS_SCENARIO_DEFINITIONS = {
    "2008 Lehman": {"column": "stress_2008_lehman_crisis", "type": "Historical", "definition": "Portfolio revaluation under the supplied 2008 Lehman market-shock set."},
    "2011 US downgrade": {"column": "stress_2011_us_downgrade", "type": "Historical", "definition": "Portfolio revaluation under the supplied 2011 US downgrade market-shock set."},
    "2020 COVID": {"column": "stress_2020_covid_liquidity", "type": "Historical", "definition": "Portfolio revaluation under the supplied 2020 COVID liquidity market-shock set."},
    "2022 rate hikes": {"column": "stress_2022_rate_hikes", "type": "Historical", "definition": "Portfolio revaluation under the supplied 2022 rate-hike market-shock set."},
    "IR +100 bp": {"column": "stress_ir_up_100bp", "type": "Hypothetical", "definition": "Portfolio revaluation after a parallel +100 basis-point interest-rate shock."},
    "IR -100 bp": {"column": "stress_ir_down_100bp", "type": "Hypothetical", "definition": "Portfolio revaluation after a parallel -100 basis-point interest-rate shock."},
    "IR steepener": {"column": "stress_ir_steepener_50bp", "type": "Hypothetical", "definition": "Portfolio revaluation under the supplied 50 basis-point curve-steepening shock."},
    "IR flattener": {"column": "stress_ir_flattener_50bp", "type": "Hypothetical", "definition": "Portfolio revaluation under the supplied 50 basis-point curve-flattening shock."},
    "USD +10%": {"column": "stress_fx_usd_up_10pct", "type": "Hypothetical", "definition": "Portfolio revaluation after a supplied 10% strengthening shock to USD."},
    "Vol +50%": {"column": "stress_vol_up_50pct", "type": "Hypothetical", "definition": "Portfolio revaluation under the supplied 50% volatility shock."},
}

RATE_CURVES = [
    ("EUR", "OIS", "€STR OIS", -85_000, 1_350, -28_000),
    ("EUR", "BOR", "Euribor 3M", -28_000, 420, -15_000),
    ("EUR", "BOR", "Euribor 6M", -15_000, 260, -9_000),
    ("USD", "OIS", "SOFR OIS", 72_000, 1_050, 21_000),
    ("USD", "BOR", "USD 3M projection", 22_000, 380, 12_000),
    ("USD", "BOR", "USD 6M projection", 12_000, 210, 7_000),
    ("JPY", "OIS", "TONAR OIS", -24_000, 310, -6_000),
    ("JPY", "BOR", "TIBOR 3M", -11_000, 170, -4_000),
    ("JPY", "BOR", "TIBOR 6M", -7_000, 110, -2_000),
    ("GBP", "OIS", "SONIA OIS", 31_000, 460, 9_000),
    ("GBP", "BOR", "GBP 3M projection", 13_000, 190, 5_000),
    ("GBP", "BOR", "GBP 6M projection", 8_000, 120, 3_000),
]

FX_DELTAS = [
    ("EUR/USD", 410_000),
    ("USD/JPY", -180_000),
    ("GBP/USD", 215_000),
]


def build_pla_demo_history():
    """Return V19 PLA history with varied synthetic driver-coverage quality."""
    history = v19.build_pla_demo_history().copy()
    coverage_targets = {
        "Exotics": 0.48,
        "Swaptions": 0.50,
        "Equity volatility": 0.76,
    }
    for desk, target_coverage in coverage_targets.items():
        mask = history["trading_desk"] == desk
        current_explained = history.loc[mask, DRIVER_COLUMNS].sum(axis=1)
        current_coverage = current_explained / history.loc[mask, "risk_theoretical_pnl"].replace(0, pd.NA)
        scaling = (target_coverage / current_coverage).fillna(1.0)
        history.loc[mask, DRIVER_COLUMNS] = history.loc[mask, DRIVER_COLUMNS].mul(scaling, axis=0)
    history["explained_pnl"] = history[DRIVER_COLUMNS].sum(axis=1)
    history["unexplained_pnl"] = history["risk_theoretical_pnl"] - history["explained_pnl"]
    return history

def build_supplied_stress_frame(as_of_date=None):
    """Return the unchanged supplied scenarios with shorter V20 display names."""
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
    """Return unchanged risk-engine-supplied stress values with shorter labels."""
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
            "Stress values and scenario shocks are unchanged from V19; V20 shortens display names only. "
            "Values are supplied scenario revaluation P&L in the reporting currency."
        ),
    }


def get_market_sensitivities():
    """Return unit-aware synthetic rates and FX sensitivities by currency and curve."""
    current = v8.df.iloc[-1]
    rows = []
    for currency, curve_type, curve, dv01, gamma, vega in RATE_CURVES:
        rows.extend([
            {
                "risk_class": "Rates",
                "measure": "IR Delta (DV01)",
                "currency": currency,
                "curve_type": curve_type,
                "curve": curve,
                "value": float(dv01),
                "unit": "EUR / bp",
                "definition": "P&L change for a +1 bp move in the named curve.",
            },
            {
                "risk_class": "Rates",
                "measure": "IR Gamma",
                "currency": currency,
                "curve_type": curve_type,
                "curve": curve,
                "value": float(gamma),
                "unit": "EUR / bp²",
                "definition": "Change in curve DV01 for a +1 bp move in the named curve.",
            },
            {
                "risk_class": "Rates",
                "measure": "Vega",
                "currency": currency,
                "curve_type": curve_type,
                "curve": curve,
                "value": float(vega),
                "unit": "EUR / vol point",
                "definition": "P&L change for a +1 percentage-point move in implied volatility.",
            },
        ])
    for pair, delta in FX_DELTAS:
        rows.append({
            "risk_class": "FX",
            "measure": "FX Delta",
            "currency": pair,
            "curve_type": "Spot",
            "curve": pair,
            "value": float(delta),
            "unit": "EUR / 1% spot",
            "definition": "P&L change for a +1% move in the quoted FX pair.",
        })
    rows.append({
        "risk_class": "Time",
        "measure": "Theta",
        "currency": "All",
        "curve_type": "Portfolio",
        "curve": "Whole portfolio",
        "value": -19_000.0,
        "unit": "EUR / day",
        "definition": "Expected one-business-day P&L from time decay, holding market inputs constant.",
    })
    return {
        "as_of_date": str(current["cob_date"].date()),
        "currencies": ["EUR", "USD", "JPY", "GBP"],
        "sensitivities": rows,
        "usage_note": (
            "Unit-aware deterministic synthetic V20 sensitivity feed. Rates are split by EUR, USD, JPY and GBP "
            "OIS/BOR curves; FX Delta covers each non-USD currency versus USD. Replace with risk-engine records in production."
        ),
    }


def evaluate_pnl_explain_alerts():
    """Flag desks where absolute driver-unexplained P&L exceeds 20% of absolute APL."""
    history = build_pla_demo_history()
    latest = history.sort_values("cob_date").groupby("trading_desk", as_index=False).tail(1)
    alerts = []
    for _, row in latest.iterrows():
        apl_magnitude = abs(float(row["actual_pnl"]))
        unexplained_magnitude = abs(float(row["unexplained_pnl"]))
        ratio = float("inf") if apl_magnitude == 0 and unexplained_magnitude > 0 else (
            0.0 if apl_magnitude == 0 else unexplained_magnitude / apl_magnitude * 100.0
        )
        flagged = ratio > UNEXPLAINED_APL_ALERT_THRESHOLD_PCT
        alerts.append({
            "business_line": row["business_line"],
            "trading_desk": row["trading_desk"],
            "actual_pnl": float(row["actual_pnl"]),
            "unexplained_pnl": float(row["unexplained_pnl"]),
            "unexplained_to_apl_pct": ratio,
            "threshold_pct": UNEXPLAINED_APL_ALERT_THRESHOLD_PCT,
            "status": "ALERT" if flagged else "OK",
        })
    return {
        "as_of_date": str(latest["cob_date"].max().date()),
        "threshold_pct": UNEXPLAINED_APL_ALERT_THRESHOLD_PCT,
        "flagged_count": sum(item["status"] == "ALERT" for item in alerts),
        "desk_results": alerts,
        "usage_note": (
            "V20 demo control flags |driver-unexplained P&L| / |APL| above 20%. "
            "The threshold and desk history are synthetic prototype governance inputs."
        ),
    }


v8.TOOL_FUNCTIONS["get_market_sensitivities"] = get_market_sensitivities
v8.TOOL_DESCRIPTIONS["get_market_sensitivities"] = "Rates sensitivities by EUR, USD, JPY and GBP OIS/BOR curves plus FX Delta for USD pairs."
v8.TOOL_FUNCTIONS["get_stress_evolution"] = get_stress_evolution
v8.TOOL_DESCRIPTIONS["get_stress_evolution"] = "Unchanged supplied stress scenario values with shorter V20 display labels."
v8.TOOL_FUNCTIONS["evaluate_pnl_explain_alerts"] = evaluate_pnl_explain_alerts
v8.TOOL_DESCRIPTIONS["evaluate_pnl_explain_alerts"] = "Desk flags where absolute unexplained P&L exceeds 20% of absolute APL."

v9.SYSTEM_INSTRUCTION += """

V20 dashboard controls:
- Use evaluate_pnl_explain_alerts for the 20% unexplained-to-APL control.
- Sensitivities are split by currency and OIS/BOR curve and remain deterministic synthetic demo values.
- Stress scenario values and shocks are unchanged; only display names are shortened.
"""
v9.tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=name, description=description)
    for name, description in v8.TOOL_DESCRIPTIONS.items()
])]

ask_risk_agent = v19.ask_risk_agent
