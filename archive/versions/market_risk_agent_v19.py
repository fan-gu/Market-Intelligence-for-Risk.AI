"""M.R. AI Agent V19: FRTB P&L attribution and desk-level PLA testing."""

from __future__ import annotations

import numpy as np
import pandas as pd

from archive.versions import market_risk_agent_v18 as v18
from google.genai import types


VERSION = "V19"
v18.v9.VERSION = VERSION
v17 = v18.v17
v16 = v18.v16
v15 = v18.v15
v14 = v18.v14
v13 = v18.v13
v12 = v18.v12
v11 = v18.v11
v9 = v18.v9
v8 = v18.v8
build_supplied_stress_frame = v18.build_supplied_stress_frame
get_market_sensitivities = v18.get_market_sensitivities
get_stress_evolution = v18.get_stress_evolution
evaluate_all_limits = v18.evaluate_all_limits

PLA_OBSERVATIONS = 250
PLA_GREEN_CORRELATION = 0.80
PLA_RED_CORRELATION = 0.70
PLA_GREEN_KS = 0.09
PLA_RED_KS = 0.12
DRIVER_COLUMNS = [
    "Rates",
    "FX",
    "Credit",
    "Equity",
    "Vega",
    "Theta",
    "Gamma and cross-gamma",
]


def _empirical_ks_statistic(first, second):
    """Return the two-sample empirical Kolmogorov-Smirnov distance."""
    first_sorted = np.sort(np.asarray(first, dtype=float))
    second_sorted = np.sort(np.asarray(second, dtype=float))
    combined = np.sort(np.concatenate([first_sorted, second_sorted]))
    first_cdf = np.searchsorted(first_sorted, combined, side="right") / len(first_sorted)
    second_cdf = np.searchsorted(second_sorted, combined, side="right") / len(second_sorted)
    return float(np.max(np.abs(first_cdf - second_cdf)))


def _pla_zone(correlation, ks_statistic):
    if correlation > PLA_GREEN_CORRELATION and ks_statistic < PLA_GREEN_KS:
        return "GREEN"
    if correlation < PLA_RED_CORRELATION or ks_statistic > PLA_RED_KS:
        return "RED"
    return "AMBER"


def _zone_consequence(zone):
    return {
        "GREEN": "IMA eligible",
        "AMBER": "IMA eligible with capital surcharge",
        "RED": "IMA ineligible; Standardised Approach required",
    }[zone]


def build_pla_demo_history():
    """Build a deterministic, synthetic 250-business-day desk-level PLA feed."""
    books, _ = v15.build_hierarchy()
    desks = (
        books.groupby(["business_line", "trading_desk"], as_index=False)["allocation_weight"]
        .sum()
        .sort_values(["business_line", "trading_desk"])
        .reset_index(drop=True)
    )
    end_date = v8.df["cob_date"].max()
    dates = pd.bdate_range(end=end_date, periods=PLA_OBSERVATIONS)
    rng = np.random.default_rng(19019)
    current = v8.df.iloc[-1]
    rows = []

    for desk_index, desk in desks.iterrows():
        weight = float(desk["allocation_weight"])
        scale = 1_700_000 * max(weight, 0.04)
        market_component = rng.normal(0, scale, PLA_OBSERVATIONS)
        desk_component = rng.normal(0, scale * 0.35, PLA_OBSERVATIONS)
        hpl = market_component + desk_component

        if desk_index < 6:
            rtpl = hpl * rng.normal(1.0, 0.015, PLA_OBSERVATIONS) + rng.normal(0, scale * 0.09, PLA_OBSERVATIONS)
        elif desk_index < 9:
            rtpl = hpl * 0.82 + rng.normal(0, scale * 0.32, PLA_OBSERVATIONS) + scale * 0.08
        else:
            rtpl = hpl * 0.45 + rng.normal(0, scale * 0.85, PLA_OBSERVATIONS) + scale * 0.18

        apl = hpl + rng.normal(0, scale * 0.22, PLA_OBSERVATIONS)

        hpl[-1] = float(current["hypothetical_pnl"]) * weight
        apl[-1] = float(current["actual_pnl"]) * weight
        latest_model_gap = (0.025 + desk_index * 0.006) * scale
        rtpl[-1] = hpl[-1] - latest_model_gap

        driver_weights = np.array([0.28, 0.23, 0.10, 0.08, 0.14, 0.07, 0.10])
        if "FX" in desk["business_line"]:
            driver_weights = np.array([0.10, 0.44, 0.06, 0.04, 0.20, 0.06, 0.10])
        elif "IR" in desk["business_line"]:
            driver_weights = np.array([0.49, 0.08, 0.06, 0.02, 0.19, 0.07, 0.09])
        elif "Equity" in desk["business_line"]:
            driver_weights = np.array([0.06, 0.08, 0.05, 0.43, 0.23, 0.05, 0.10])

        driver_weights = driver_weights * 0.94

        for observation, cob_date in enumerate(dates):
            driver_values = rtpl[observation] * driver_weights
            row = {
                "cob_date": cob_date,
                "business_line": desk["business_line"],
                "trading_desk": desk["trading_desk"],
                "actual_pnl": float(apl[observation]),
                "hypothetical_pnl": float(hpl[observation]),
                "risk_theoretical_pnl": float(rtpl[observation]),
                "apl_hpl_difference": float(apl[observation] - hpl[observation]),
                "hpl_rtpl_difference": float(hpl[observation] - rtpl[observation]),
                "explained_pnl": float(driver_values.sum()),
                "unexplained_pnl": float(rtpl[observation] - driver_values.sum()),
                "data_classification": "Deterministic synthetic V19 PLA demo",
            }
            row.update({name: float(value) for name, value in zip(DRIVER_COLUMNS, driver_values)})
            rows.append(row)

    return pd.DataFrame(rows)


def evaluate_pla_test():
    """Evaluate Basel PLA statistics for every synthetic demo trading desk."""
    history = build_pla_demo_history()
    results = []
    for desk_name, desk_history in history.groupby("trading_desk", sort=True):
        correlation = float(
            desk_history["hypothetical_pnl"].rank(method="average").corr(
                desk_history["risk_theoretical_pnl"].rank(method="average")
            )
        )
        ks_statistic = _empirical_ks_statistic(
            desk_history["hypothetical_pnl"],
            desk_history["risk_theoretical_pnl"],
        )
        zone = _pla_zone(correlation, ks_statistic)
        latest = desk_history.iloc[-1]
        results.append({
            "business_line": latest["business_line"],
            "trading_desk": desk_name,
            "observations": len(desk_history),
            "spearman_correlation": correlation,
            "ks_statistic": ks_statistic,
            "pla_zone": zone,
            "regulatory_consequence": _zone_consequence(zone),
            "latest_hpl": float(latest["hypothetical_pnl"]),
            "latest_rtpl": float(latest["risk_theoretical_pnl"]),
            "latest_pla_residual": float(latest["hpl_rtpl_difference"]),
        })
    return {
        "as_of_date": str(history["cob_date"].max().date()),
        "required_observations": PLA_OBSERVATIONS,
        "thresholds": {
            "green": {"spearman_above": PLA_GREEN_CORRELATION, "ks_below": PLA_GREEN_KS},
            "red": {"spearman_below": PLA_RED_CORRELATION, "ks_above": PLA_RED_KS},
            "otherwise": "AMBER",
        },
        "desk_results": results,
        "usage_note": (
            "The PLA methodology and thresholds follow the Basel framework. The 250-day desk history is "
            "deterministic synthetic V19 demo data, not a regulatory submission or IMA eligibility decision."
        ),
    }


v8.TOOL_FUNCTIONS["evaluate_pla_test"] = evaluate_pla_test
v8.TOOL_DESCRIPTIONS["evaluate_pla_test"] = (
    "Basel-style 250-day desk-level HPL-versus-RTPL PLA results, zones and consequences using labelled synthetic demo history."
)
v9.SYSTEM_INSTRUCTION += """

V19 P&L attribution control:
- Use official terminology: Actual P&L (APL), Hypothetical P&L (HPL), and Risk-theoretical P&L (RTPL).
- PLA compares HPL with RTPL over 250 trading days using Spearman rank correlation and the empirical KS statistic.
- Do not use APL in the PLA test; APL and HPL are used for backtesting.
- Keep the HPL-minus-RTPL PLA residual separate from internal driver-level unexplained P&L.
- Always state that the V19 desk history is deterministic synthetic demo data and does not establish regulatory eligibility.
"""
v9.tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name=name, description=description)
    for name, description in v8.TOOL_DESCRIPTIONS.items()
])]

ask_risk_agent = v18.ask_risk_agent
