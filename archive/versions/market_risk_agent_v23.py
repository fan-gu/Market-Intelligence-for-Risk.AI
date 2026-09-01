"""M.R. AI Agent V23: tenor sensitivities and VaR movement attribution."""

from __future__ import annotations

import pandas as pd
from google.genai import types

from archive.versions import market_risk_agent_v22 as v22


VERSION = "V23"
v22.v9.VERSION = VERSION
v21 = v22.v21
v20 = v22.v20
v19 = v22.v19
v18 = v22.v18
v17 = v22.v17
v16 = v22.v16
v15 = v22.v15
v14 = v22.v14
v13 = v22.v13
v12 = v22.v12
v11 = v22.v11
v9 = v22.v9
v8 = v22.v8
DRIVER_COLUMNS = v22.DRIVER_COLUMNS
build_pla_demo_history = v22.build_pla_demo_history
evaluate_pla_test = v22.evaluate_pla_test
evaluate_all_limits = v22.evaluate_all_limits
evaluate_pnl_explain_alerts = v22.evaluate_pnl_explain_alerts
build_supplied_stress_frame = v22.build_supplied_stress_frame
get_stress_evolution = v22.get_stress_evolution
get_material_stress_scenarios = v22.get_material_stress_scenarios
get_stress_scenario_catalog = v22.get_stress_scenario_catalog
get_var_change_summary = v22.get_var_change_summary

TENOR_WEIGHTS = {
    "1Y": 0.12,
    "2Y": 0.18,
    "5Y": 0.30,
    "10Y": 0.25,
    "30Y": 0.15,
}

HKD_RATE_CURVES = [
    ("OIS", "HONIA OIS", 18_000, 240, 4_800),
    ("BOR", "HIBOR 3M", 9_000, 125, 2_600),
    ("BOR", "HIBOR 6M", 5_500, 75, 1_500),
    ("Inflation", "HK CPI", 2_800, 40, 900),
]

CNY_RATE_CURVES = [
    ("OIS", "CNY OIS", 20_000, 280, 5_400),
    ("BOR", "SHIBOR 3M", 10_500, 145, 2_900),
    ("BOR", "SHIBOR 6M", 6_000, 85, 1_700),
    ("Inflation", "CNY CPI", 3_000, 45, 1_000),
]

VAR_ATTRIBUTION_GROUPS = {
    "FX": ["contrib_var_fx_spot", "contrib_var_fx_vol_implied", "contrib_var_fx_basis"],
    "Rates": [
        "contrib_var_ir_sofr_curve",
        "contrib_var_ir_estr_curve",
        "contrib_var_ir_sonia_curve",
        "contrib_var_ir_swaption_vol",
        "contrib_var_ir_basis_tenor",
        "contrib_var_ir_convexity",
    ],
    "Credit": ["contrib_var_credit_ig_spread", "contrib_var_credit_hy_spread", "contrib_var_credit_cds_basis"],
    "Equity": ["contrib_var_equity_spot", "contrib_var_equity_vol"],
    "Commodity": ["contrib_var_commodity_energy", "contrib_var_commodity_metals"],
    "Inflation": ["contrib_var_inflation_breakeven"],
    "New trades": ["contrib_var_new_trades"],
    "Expired trades": ["contrib_var_expired_trades"],
    "Modified trades": ["contrib_var_modified_trades"],
    "Diversification": ["diversification_effect"],
}


def get_market_sensitivities():
    """Return V22 sensitivities split by tenor and expanded to HKD and CNY."""
    source = v22.get_market_sensitivities()
    source_rows = list(source["sensitivities"])

    for currency, rate_curves in [("HKD", HKD_RATE_CURVES), ("CNY", CNY_RATE_CURVES)]:
        for curve_type, curve, delta, gamma, vega in rate_curves:
            source_rows.extend([
            {
                "risk_class": "Rates",
                "measure": "IR Delta (DV01)",
                "currency": currency,
                "curve_type": curve_type,
                "curve": curve,
                "value": float(delta),
                "unit": "EUR / bp",
                "definition": f"P&L change for a +1 bp move in the named {currency} curve.",
            },
            {
                "risk_class": "Rates",
                "measure": "IR Gamma",
                "currency": currency,
                "curve_type": curve_type,
                "curve": curve,
                "value": float(gamma),
                "unit": "EUR / bp²",
                "definition": f"Change in {currency} curve DV01 for a +1 bp move.",
            },
            {
                "risk_class": "Rates",
                "measure": "Vega",
                "currency": currency,
                "curve_type": curve_type,
                "curve": curve,
                "value": float(vega),
                "unit": "EUR / vol point",
                "definition": "P&L change for a +1 percentage-point volatility move.",
            },
            ])

    expanded_rows = []
    for row in source_rows:
        if row["risk_class"] != "Rates":
            expanded_rows.append({**row, "tenor": "N/A"})
            continue
        for tenor, weight in TENOR_WEIGHTS.items():
            expanded_rows.append({
                **row,
                "tenor": tenor,
                "value": float(row["value"]) * weight,
                "definition": f"{row['definition']} Allocated to the {tenor} tenor bucket.",
            })

    expanded_rows.extend([
        {
            "risk_class": "FX",
            "measure": "FX Delta",
            "currency": "USD/HKD",
            "curve_type": "Spot",
            "curve": "USD/HKD",
            "tenor": "N/A",
            "value": 145_000.0,
            "unit": "EUR / 1% spot",
            "definition": "P&L change for a +1% move in USD/HKD.",
        },
        {
            "risk_class": "FX",
            "measure": "FX Delta",
            "currency": "USD/CNY",
            "curve_type": "Spot",
            "curve": "USD/CNY",
            "tenor": "N/A",
            "value": 165_000.0,
            "unit": "EUR / 1% spot",
            "definition": "P&L change for a +1% move in USD/CNY.",
        },
        {
            "risk_class": "Time",
            "measure": "Theta",
            "currency": "HKD",
            "curve_type": "Portfolio",
            "curve": "HKD portfolio",
            "tenor": "N/A",
            "value": -1_500.0,
            "unit": "EUR / day",
            "definition": "Expected one-business-day P&L from HKD time decay.",
        },
        {
            "risk_class": "Time",
            "measure": "Theta",
            "currency": "CNY",
            "curve_type": "Portfolio",
            "curve": "CNY portfolio",
            "tenor": "N/A",
            "value": -1_700.0,
            "unit": "EUR / day",
            "definition": "Expected one-business-day P&L from CNY time decay.",
        },
    ])

    return {
        **source,
        "currencies": ["EUR", "USD", "JPY", "GBP", "HKD", "CNY"],
        "tenors": list(TENOR_WEIGHTS),
        "sensitivities": expanded_rows,
        "usage_note": (
            "Deterministic synthetic V23 feed across EUR, USD, JPY, GBP, HKD and CNY. "
            "OIS, BOR and Inflation sensitivities are split into 1Y, 2Y, 5Y, 10Y and 30Y buckets. "
            "Tenor allocation preserves each curve-level total."
        ),
    }


def _reference_row(frame, current_position, current_date, horizon):
    if horizon == "Daily":
        return None if current_position == 0 else frame.iloc[current_position - 1]
    target = current_date - (
        pd.Timedelta(days=7) if horizon == "Weekly" else pd.DateOffset(months=1)
    )
    candidates = frame.loc[frame["cob_date"] <= target]
    return None if candidates.empty else candidates.iloc[-1]


def get_var_change_attribution(as_of_date=None, horizon="Daily", hierarchy_level="Portfolio"):
    """Explain a Historical VaR movement over the selected horizon."""
    if horizon not in {"Daily", "Weekly", "Monthly"}:
        raise ValueError("horizon must be Daily, Weekly or Monthly")

    frame = v8.df.sort_values("cob_date").reset_index(drop=True)
    requested_date = pd.Timestamp(as_of_date) if as_of_date is not None else frame.iloc[-1]["cob_date"]
    eligible = frame.index[frame["cob_date"] <= requested_date].tolist()
    if not eligible:
        return {"status": "NO_DATA", "factor_changes": []}

    current_position = eligible[-1]
    current = frame.iloc[current_position]
    current_date = pd.Timestamp(current["cob_date"])
    reference = _reference_row(frame, current_position, current_date, horizon)
    if reference is None:
        return {
            "status": "INSUFFICIENT_HISTORY",
            "horizon": horizon,
            "as_of_date": str(current_date.date()),
            "factor_changes": [],
        }

    factor_changes = []
    for factor, columns in VAR_ATTRIBUTION_GROUPS.items():
        sign = -1.0 if factor == "Diversification" else 1.0
        current_value = sign * float(current[columns].sum())
        reference_value = sign * float(reference[columns].sum())
        factor_changes.append({
            "factor": factor,
            "current_contribution": current_value,
            "reference_contribution": reference_value,
            "change": current_value - reference_value,
        })

    total_change = float(current["var_1d_99_hist"] - reference["var_1d_99_hist"])
    attributed_change = sum(item["change"] for item in factor_changes)
    reconciliation = total_change - attributed_change
    return {
        "status": "AVAILABLE",
        "horizon": horizon,
        "hierarchy_level": hierarchy_level,
        "as_of_date": str(current_date.date()),
        "reference_date": str(pd.Timestamp(reference["cob_date"]).date()),
        "current_var": float(current["var_1d_99_hist"]),
        "reference_var": float(reference["var_1d_99_hist"]),
        "total_change": total_change,
        "attributed_change": attributed_change,
        "reconciliation": reconciliation,
        "factor_changes": factor_changes,
        "usage_note": (
            "Movement attribution is calculated from changes in supplied VaR contributions. "
            "New, expired and modified trade effects are included when supplied. Reconciliation "
            "is total Historical VaR change minus the sum of attributed factor changes."
        ),
    }


v8.TOOL_FUNCTIONS["get_market_sensitivities"] = get_market_sensitivities
v8.TOOL_DESCRIPTIONS["get_market_sensitivities"] = "Tenor-split OIS, BOR and Inflation sensitivities across EUR, USD, JPY, GBP, HKD and CNY, plus FX Delta and Theta."
v8.TOOL_FUNCTIONS["get_var_change_attribution"] = get_var_change_attribution
v8.TOOL_DESCRIPTIONS["get_var_change_attribution"] = "Historical VaR movement attribution by risk factor for a Daily, Weekly or Monthly horizon."

v9.SYSTEM_INSTRUCTION += """

V23 controls:
- Use get_var_change_attribution to explain Historical VaR movements by risk factor.
- Report the reconciliation item separately from risk factors; it is not a risk-factor exposure.
- Tenor sensitivities are deterministic synthetic allocations that preserve the curve-level totals.
"""
v9.tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=name, description=description)
    for name, description in v8.TOOL_DESCRIPTIONS.items()
])]

ask_risk_agent = v22.ask_risk_agent
