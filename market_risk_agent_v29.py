"""M.R. AI Agent V29: interactive sensitivity-based Scenario Lab."""

from __future__ import annotations

import hashlib
import json

import pandas as pd
from google.genai import types

from archive.versions import market_risk_agent_v28 as v28
from archive.versions.market_risk_agent_v28 import *  # noqa: F401,F403 - preserve the public version API


VERSION = "V29"
v28.v9.VERSION = VERSION

v8 = v28.v8
v9 = v28.v9
DRIVER_COLUMNS = v28.DRIVER_COLUMNS
# Explicitly expose the shared SVaR governance convention at the V29 API
# boundary; relying on star-import inheritance is fragile across reruns.
SVAR_LIMIT_MULTIPLIER = getattr(v28, "SVAR_LIMIT_MULTIPLIER", 1.5)

BASE_SCENARIO_LOSS_LIMIT = 15_000_000.0
SCENARIO_WARNING_THRESHOLD_PCT = 80.0
SCENARIO_BREACH_THRESHOLD_PCT = 100.0

TENOR_YEARS = {
    "1M": 1 / 12,
    "3M": 0.25,
    "6M": 0.5,
    "1Y": 1.0,
    "2Y": 2.0,
    "5Y": 5.0,
    "10Y": 10.0,
    "30Y": 30.0,
}


def _twist_loading(tenor: str) -> float:
    """Map curve tenor to a -1 (front end) to +1 (long end) twist loading."""
    years = TENOR_YEARS.get(str(tenor), 5.0)
    minimum = min(TENOR_YEARS.values())
    maximum = max(TENOR_YEARS.values())
    return -1.0 + 2.0 * (years - minimum) / (maximum - minimum)


def get_scenario_lab_specification():
    """Return available shock dimensions and the V29 approximation methodology."""
    frame = pd.DataFrame(v28.get_market_sensitivities()["sensitivities"])
    rate_rows = frame.loc[frame["risk_class"] == "Rates"]
    fx_rows = frame.loc[frame["measure"] == "FX Delta"]
    return {
        "rate_currencies": sorted(rate_rows["currency"].dropna().unique().tolist()),
        "curve_families": sorted(rate_rows["curve_type"].dropna().unique().tolist()),
        "fx_pairs": sorted(fx_rows["curve"].dropna().unique().tolist()),
        "severity_options": {"Adverse (1x)": 1.0, "Extreme (2x)": 2.0},
        "methodology": (
            "Estimated scenario P&L = Delta x shock + 0.5 x Gamma x shock^2 + "
            "Vega x volatility change + FX Delta x spot move + Theta x horizon."
        ),
        "governance_note": (
            "Sensitivity-based what-if estimate. It is not an official full-revaluation "
            "risk-engine result and does not recalculate official VaR or Expected Shortfall."
        ),
    }


def run_interactive_scenario(
    rate_currency: str = "EUR",
    curve_family: str = "All curve families",
    parallel_shift_bp: float = 0.0,
    curve_twist_bp: float = 0.0,
    fx_pair: str = "EUR/USD",
    fx_spot_move_pct: float = 0.0,
    volatility_shift_points: float = 0.0,
    horizon_days: int = 0,
    severity_multiplier: float = 1.0,
    allocation_weight: float = 1.0,
    scope_label: str = "Whole portfolio",
    as_of_date: str | None = None,
):
    """Estimate a custom scenario from the supplied Delta/Gamma/Vega/Theta feed.

    Rate and market shocks are multiplied by ``severity_multiplier``. Theta uses
    the explicitly selected horizon and is not doubled for an extreme scenario.
    Negative total P&L represents a loss and consumes the illustrative scenario
    loss limit.
    """
    if severity_multiplier not in (1.0, 2.0):
        raise ValueError("Severity multiplier must be 1.0 (adverse) or 2.0 (extreme).")
    if allocation_weight < 0:
        raise ValueError("Allocation weight cannot be negative.")

    specification = get_scenario_lab_specification()
    if rate_currency not in specification["rate_currencies"] + ["All currencies"]:
        raise ValueError(f"Unknown rate currency: {rate_currency}")
    if curve_family not in specification["curve_families"] + ["All curve families"]:
        raise ValueError(f"Unknown curve family: {curve_family}")
    if fx_pair not in specification["fx_pairs"] + ["All FX pairs"]:
        raise ValueError(f"Unknown FX pair: {fx_pair}")

    frame = pd.DataFrame(v28.get_market_sensitivities()["sensitivities"]).copy()
    frame["value"] = frame["value"].astype(float) * float(allocation_weight)
    detail_rows: list[dict] = []

    rate_filter = frame["risk_class"].eq("Rates")
    if rate_currency != "All currencies":
        rate_filter &= frame["currency"].eq(rate_currency)
    if curve_family != "All curve families":
        rate_filter &= frame["curve_type"].eq(curve_family)

    effective_parallel = float(parallel_shift_bp) * severity_multiplier
    effective_twist = float(curve_twist_bp) * severity_multiplier
    for measure, component in (("IR Delta (DV01)", "IR Delta"), ("IR Gamma", "IR Gamma")):
        selected = frame.loc[rate_filter & frame["measure"].eq(measure)]
        for row in selected.to_dict("records"):
            node_shock = effective_parallel + effective_twist * _twist_loading(row["tenor"])
            if component == "IR Delta":
                contribution = float(row["value"]) * node_shock
            else:
                contribution = 0.5 * float(row["value"]) * node_shock**2
            detail_rows.append({
                "component": component,
                "currency": row["currency"],
                "curve_family": row["curve_type"],
                "curve": str(row["curve"]).replace("\ufffdSTR", "ESTR"),
                "tenor": row["tenor"],
                "applied_shock": f"{node_shock:+.1f} bp",
                "estimated_pnl": float(contribution),
            })

    vega_filter = frame["measure"].eq("Vega")
    if rate_currency != "All currencies":
        vega_filter &= frame["currency"].eq(rate_currency)
    if curve_family != "All curve families":
        vega_filter &= frame["curve_type"].eq(curve_family)
    effective_volatility_shift = float(volatility_shift_points) * severity_multiplier
    for row in frame.loc[vega_filter].to_dict("records"):
        contribution = float(row["value"]) * effective_volatility_shift
        detail_rows.append({
            "component": "IR Vega",
            "currency": row["currency"],
            "curve_family": row["curve_type"],
            "curve": str(row["curve"]).replace("\ufffdSTR", "ESTR"),
            "tenor": row.get("surface_node", row["tenor"]),
            "applied_shock": f"{effective_volatility_shift:+.1f} vol points",
            "estimated_pnl": float(contribution),
        })

    fx_filter = frame["measure"].eq("FX Delta")
    if fx_pair != "All FX pairs":
        fx_filter &= frame["curve"].eq(fx_pair)
    effective_fx_move = float(fx_spot_move_pct) * severity_multiplier
    for row in frame.loc[fx_filter].to_dict("records"):
        contribution = float(row["value"]) * effective_fx_move
        detail_rows.append({
            "component": "FX Delta",
            "currency": row["currency"],
            "curve_family": row["curve_type"],
            "curve": row["curve"],
            "tenor": "Spot",
            "applied_shock": f"{effective_fx_move:+.1f}%",
            "estimated_pnl": float(contribution),
        })

    theta_filter = frame["measure"].eq("Theta")
    if rate_currency != "All currencies":
        theta_filter &= frame["currency"].eq(rate_currency)
    for row in frame.loc[theta_filter].to_dict("records"):
        contribution = float(row["value"]) * int(horizon_days)
        detail_rows.append({
            "component": "Theta",
            "currency": row["currency"],
            "curve_family": row["curve_type"],
            "curve": row["curve"],
            "tenor": "Time",
            "applied_shock": f"{int(horizon_days)} days",
            "estimated_pnl": float(contribution),
        })

    detail = pd.DataFrame(detail_rows)
    component_order = ["IR Delta", "IR Gamma", "IR Vega", "FX Delta", "Theta"]
    component_values = (
        detail.groupby("component")["estimated_pnl"].sum().to_dict()
        if not detail.empty
        else {}
    )
    components = [
        {"component": component, "estimated_pnl": float(component_values.get(component, 0.0))}
        for component in component_order
    ]
    estimated_pnl = float(sum(row["estimated_pnl"] for row in components))
    if abs(estimated_pnl) < 1e-9:
        estimated_pnl = 0.0
    scenario_limit = float(BASE_SCENARIO_LOSS_LIMIT * allocation_weight)
    loss_amount = max(-estimated_pnl, 0.0)
    if abs(loss_amount) < 1e-9:
        loss_amount = 0.0
    consumption_pct = loss_amount / scenario_limit * 100.0 if scenario_limit else 0.0
    if consumption_pct >= SCENARIO_BREACH_THRESHOLD_PCT:
        status = "BREACH"
    elif consumption_pct >= SCENARIO_WARNING_THRESHOLD_PCT:
        status = "WARNING"
    else:
        status = "OK"

    if detail.empty:
        top_contributors = []
        currency_contributions = []
        curve_contributions = []
    else:
        ranked = detail.assign(abs_pnl=detail["estimated_pnl"].abs()).sort_values(
            "abs_pnl", ascending=False
        )
        top_contributors = ranked.drop(columns="abs_pnl").head(15).to_dict("records")
        currency_contributions = (
            detail.groupby(["currency", "component"], as_index=False)["estimated_pnl"]
            .sum()
            .to_dict("records")
        )
        curve_contributions = (
            detail.groupby(["currency", "curve", "component"], as_index=False)["estimated_pnl"]
            .sum()
            .assign(abs_pnl=lambda data: data["estimated_pnl"].abs())
            .sort_values("abs_pnl", ascending=False)
            .drop(columns="abs_pnl")
            .head(20)
            .to_dict("records")
        )

    parameters = {
        "rate_currency": rate_currency,
        "curve_family": curve_family,
        "parallel_shift_bp": float(parallel_shift_bp),
        "curve_twist_bp": float(curve_twist_bp),
        "fx_pair": fx_pair,
        "fx_spot_move_pct": float(fx_spot_move_pct),
        "volatility_shift_points": float(volatility_shift_points),
        "horizon_days": int(horizon_days),
        "severity_multiplier": float(severity_multiplier),
    }
    scenario_hash = hashlib.sha256(
        json.dumps({"parameters": parameters, "scope": scope_label, "as_of": as_of_date}, sort_keys=True).encode("utf-8")
    ).hexdigest()[:10].upper()

    return {
        "scenario_id": f"SCN-V29-{scenario_hash}",
        "version": VERSION,
        "as_of_date": as_of_date,
        "scope": scope_label,
        "allocation_weight": float(allocation_weight),
        "calculation_mode": "Sensitivity approximation",
        "parameters": parameters,
        "effective_shocks": {
            "parallel_shift_bp": effective_parallel,
            "curve_twist_bp": effective_twist,
            "fx_spot_move_pct": effective_fx_move,
            "volatility_shift_points": effective_volatility_shift,
            "horizon_days": int(horizon_days),
        },
        "baseline": {"estimated_pnl": 0.0, "limit_consumption_pct": 0.0, "status": "OK"},
        "scenario": {
            "estimated_pnl": estimated_pnl,
            "loss_amount": loss_amount,
            "loss_limit": scenario_limit,
            "limit_consumption_pct": float(consumption_pct),
            "status": status,
            "new_limit_event": status in {"WARNING", "BREACH"},
        },
        "component_contributions": components,
        "currency_contributions": currency_contributions,
        "curve_contributions": curve_contributions,
        "top_contributors": top_contributors,
        "methodology": specification["methodology"],
        "governance_note": specification["governance_note"],
        "assumptions": [
            "Delta and Vega contributions are linear in their respective shocks.",
            "IR Gamma uses 0.5 x Gamma x rate-shock squared at each curve-tenor node.",
            "Curve twist loading runs from -1 at the shortest tenor to +1 at the longest tenor.",
            "Cross-gamma, smile dynamics, basis interactions and trade-level full revaluation are not modelled.",
            "The scenario loss limit is an illustrative V29 control, not an approved bank limit.",
        ],
    }


def ask_scenario_agent(question: str, scenario_context: dict) -> str:
    """Explain one deterministic V29 Scenario Lab result with Gemini."""
    system_instruction = v9.SYSTEM_INSTRUCTION + """

V29 Scenario Lab control:
- The supplied scenario context is deterministic evidence from run_interactive_scenario.
- Always call it a sensitivity approximation, never an official risk-engine revaluation.
- Do not claim that official VaR, Expected Shortfall or regulatory capital was recalculated.
- Highlight the largest contributions, loss-limit impact, scope, as-of date and omitted effects.
"""
    chat = v8.client.chats.create(
        model=v8.MODEL_NAME,
        config=types.GenerateContentConfig(system_instruction=system_instruction),
    )
    response = chat.send_message(
        f"User question: {question}\n\n"
        "Deterministic Scenario Lab result:\n"
        f"{json.dumps(scenario_context, indent=2, default=str)}\n\n"
        "Provide a concise market-risk-manager assessment grounded only in this result."
    )
    answer = response.text
    v9.write_audit_record(
        question,
        {"steps": ["Assess the saved sensitivity-based scenario."], "tools": ["run_interactive_scenario"]},
        {"run_interactive_scenario": scenario_context},
        {},
        answer,
    )
    return answer


v8.TOOL_FUNCTIONS["get_scenario_lab_specification"] = get_scenario_lab_specification
v8.TOOL_DESCRIPTIONS["get_scenario_lab_specification"] = (
    "V29 interactive scenario dimensions, sensitivity approximation formula and governance caveat."
)

v9.SYSTEM_INSTRUCTION += """

V29 Scenario Lab conventions:
- Interactive scenario results are sensitivity approximations, not official risk-engine revaluations.
- Do not state or imply that Scenario Lab recalculates official VaR, ES or regulatory capital.
"""
v9.tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=name, description=description)
    for name, description in v8.TOOL_DESCRIPTIONS.items()
])]

ask_risk_agent = v28.ask_risk_agent
