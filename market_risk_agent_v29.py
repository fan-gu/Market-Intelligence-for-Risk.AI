"""MIRAI V29: Market Intelligence for Risk AI interactive Scenario Lab."""

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

# The full priced demo catalogue distinguishes historical/hypothetical scenarios
# from adverse and extreme shocks. Every item is supplied in the synthetic feed.
STRESS_SCENARIO_DEFINITIONS = {
    "2008 Lehman": {"column": "stress_2008_lehman_crisis", "type": "Historical", "definition": "2008 Lehman shock set."},
    "2011 US downgrade": {"column": "stress_2011_us_downgrade", "type": "Historical", "definition": "2011 US sovereign-downgrade shock set."},
    "2020 COVID": {"column": "stress_2020_covid_liquidity", "type": "Historical", "definition": "2020 COVID liquidity shock set."},
    "2022 rate hikes": {"column": "stress_2022_rate_hikes", "type": "Historical", "definition": "2022 rapid rate-hike shock set."},
    "IR +100 bp": {"column": "stress_ir_up_100bp", "type": "Hypothetical", "definition": "+100 bp parallel interest-rate shock."},
    "IR -100 bp": {"column": "stress_ir_down_100bp", "type": "Hypothetical", "definition": "-100 bp parallel interest-rate shock."},
    "IR steepener": {"column": "stress_ir_steepener_50bp", "type": "Hypothetical", "definition": "50 bp curve-steepening shock."},
    "IR flattener": {"column": "stress_ir_flattener_50bp", "type": "Hypothetical", "definition": "50 bp curve-flattening shock."},
    "USD +10%": {"column": "stress_fx_usd_up_10pct", "type": "Hypothetical", "definition": "10% USD strengthening shock."},
    "Vol +50%": {"column": "stress_vol_up_50pct", "type": "Hypothetical", "definition": "50% implied-volatility shock."},
    "Credit +150 bp": {"column": "stress_credit_spreads_150bp", "type": "Adverse", "definition": "150 bp credit-spread widening shock."},
    "Equity -30%": {"column": "stress_equity_down_30pct", "type": "Adverse", "definition": "30% equity-market decline shock."},
    "EUR/USD -15%": {"column": "stress_eur_usd_down_15pct", "type": "Adverse", "definition": "15% EUR/USD decline shock."},
    "Basis +50 bp": {"column": "stress_basis_widen_50bp", "type": "Adverse", "definition": "50 bp cross-currency and tenor-basis widening shock."},
    "EM rates +200 bp": {"column": "stress_em_rates_up_200bp", "type": "Adverse", "definition": "200 bp emerging-market rates sell-off shock."},
    "Credit +300 bp": {"column": "stress_credit_spreads_300bp", "type": "Extreme", "definition": "300 bp credit-spread widening shock."},
    "Equity -60%": {"column": "stress_equity_down_60pct", "type": "Extreme", "definition": "60% equity-market decline shock."},
    "EUR/USD -30%": {"column": "stress_eur_usd_down_30pct", "type": "Extreme", "definition": "30% EUR/USD decline shock."},
    "Basis +100 bp": {"column": "stress_basis_widen_100bp", "type": "Extreme", "definition": "100 bp cross-currency and tenor-basis widening shock."},
    "EM rates +400 bp": {"column": "stress_em_rates_up_400bp", "type": "Extreme", "definition": "400 bp emerging-market rates sell-off shock."},
}

STRESS_SCENARIO_LIMITS = {
    "2008 Lehman": 16_000_000.0, "2011 US downgrade": 10_000_000.0,
    "2020 COVID": 12_000_000.0, "2022 rate hikes": 12_000_000.0,
    "IR +100 bp": 5_000_000.0, "IR -100 bp": 5_000_000.0,
    "IR steepener": 6_000_000.0, "IR flattener": 6_000_000.0,
    "USD +10%": 4_000_000.0, "Vol +50%": 8_000_000.0,
    "Credit +150 bp": 8_000_000.0, "Equity -30%": 10_000_000.0,
    "EUR/USD -15%": 7_000_000.0, "Basis +50 bp": 6_000_000.0,
    "EM rates +200 bp": 9_000_000.0, "Credit +300 bp": 16_000_000.0,
    "Equity -60%": 20_000_000.0, "EUR/USD -30%": 14_000_000.0,
    "Basis +100 bp": 12_000_000.0, "EM rates +400 bp": 18_000_000.0,
}



def _twist_loading(tenor: str) -> float:
    """Map curve tenor to a -1 (front end) to +1 (long end) twist loading."""
    years = TENOR_YEARS.get(str(tenor), 5.0)
    minimum = min(TENOR_YEARS.values())
    maximum = max(TENOR_YEARS.values())
    return -1.0 + 2.0 * (years - minimum) / (maximum - minimum)


def build_supplied_stress_frame(as_of_date=None):
    """Return all supplied stress revaluation series up to an optional COB date."""
    source = v8.df.copy()
    if as_of_date is not None:
        source = source.loc[source["cob_date"] <= pd.Timestamp(as_of_date)]
    frame = source[["cob_date"]].copy()
    metadata = {}
    for scenario, definition in STRESS_SCENARIO_DEFINITIONS.items():
        frame[scenario] = source[definition["column"]].astype(float)
        metadata[scenario] = {
            "source": "Supplied synthetic risk-engine feed",
            "type": definition["type"],
            "definition": definition["definition"],
        }
    return frame.reset_index(drop=True), metadata


def _stress_reference_row(frame, current_date, days=None, months=None):
    target_date = (
        current_date - pd.Timedelta(days=days)
        if days is not None
        else current_date - pd.DateOffset(months=months)
    )
    candidates = frame.loc[frame["cob_date"] <= target_date]
    return None if candidates.empty else candidates.iloc[-1]


def get_stress_movement_table(as_of_date=None):
    """Return current stress impacts with daily, weekly and monthly moves."""
    frame, metadata = build_supplied_stress_frame(as_of_date)
    if frame.empty:
        return {"status": "NO_DATA", "scenarios": []}
    latest = frame.iloc[-1]
    previous = frame.iloc[-2] if len(frame) > 1 else None
    weekly = _stress_reference_row(frame, latest["cob_date"], days=7)
    monthly = _stress_reference_row(frame, latest["cob_date"], months=1)
    rows = []
    for scenario, item in metadata.items():
        current_impact = float(latest[scenario])
        rows.append({
            "scenario": scenario,
            "category": item["type"],
            "latest_impact": current_impact,
            "daily_move": None if previous is None else current_impact - float(previous[scenario]),
            "weekly_move": None if weekly is None else current_impact - float(weekly[scenario]),
            "monthly_move": None if monthly is None else current_impact - float(monthly[scenario]),
            "definition": item["definition"],
        })
    return {
        "status": "AVAILABLE",
        "as_of_date": str(pd.Timestamp(latest["cob_date"]).date()),
        "scenarios": rows,
        "usage_note": "Daily uses the previous business-date observation; weekly and monthly use the latest available business date on or before the calendar reference date.",
    }


def get_stress_scenario_catalog():
    """Return the complete directly priced supplied stress catalogue."""
    return [
        {
            "scenario": scenario,
            "category": definition["type"],
            "shock": definition["definition"],
            "limit": STRESS_SCENARIO_LIMITS[scenario],
            "limit_unit": "EUR P&L loss",
            "derived_from": "",
            "pricing_status": "Priced by supplied synthetic risk-engine feed",
        }
        for scenario, definition in STRESS_SCENARIO_DEFINITIONS.items()
    ]


def get_stress_limit_monitor(as_of_date=None):
    """Evaluate current scenario losses against deterministic prototype limits."""
    movement = get_stress_movement_table(as_of_date)
    rows = []
    for item in movement.get("scenarios", []):
        limit = float(STRESS_SCENARIO_LIMITS[item["scenario"]])
        consumption = abs(min(float(item["latest_impact"]), 0.0)) / limit * 100.0
        status = "BREACH" if consumption >= 100.0 else "WARNING" if consumption >= 80.0 else "OK"
        rows.append({
            "scenario": item["scenario"],
            "category": item["category"],
            "impact": item["latest_impact"],
            "limit": limit,
            "consumption_pct": consumption,
            "status": status,
        })
    return {
        "status": movement.get("status", "NO_DATA"),
        "as_of_date": movement.get("as_of_date"),
        "scenarios": rows,
        "summary": {
            "breaches": sum(row["status"] == "BREACH" for row in rows),
            "warnings": sum(row["status"] == "WARNING" for row in rows),
            "ok": sum(row["status"] == "OK" for row in rows),
        },
        "usage_note": "Prototype scenario limits use 80% for warning and 100% for breach; they are not approved production mandates.",
    }


def get_stress_analysis():
    """Expose every latest priced stress value to the deterministic agent tools."""
    frame, _ = build_supplied_stress_frame()
    latest = frame.iloc[-1]
    return {scenario: float(latest[scenario]) for scenario in STRESS_SCENARIO_DEFINITIONS}


def validate_data():
    """Validate business-day continuity instead of calendar-day continuity."""
    dates = pd.DatetimeIndex(v8.df["cob_date"])
    expected = pd.bdate_range(dates.min(), dates.max())
    return {
        "rows": len(v8.df),
        "columns": len(v8.df.columns),
        "missing_values": int(v8.df.isna().sum().sum()),
        "duplicate_dates": int(dates.duplicated().sum()),
        "weekday_only": bool((dates.dayofweek < 5).all()),
        "business_date_sequence_ok": bool(dates.equals(expected)),
        "date_sequence_ok": bool(dates.equals(expected)),
    }


def evaluate_all_limits():
    """Preserve existing multi-factor limits with the full supplied stress universe."""
    result = v28.evaluate_all_limits()
    rows = [dict(row) for row in result["limits"]]
    stress_monitor = get_stress_limit_monitor()
    worst_loss = max(
        (abs(min(float(row["impact"]), 0.0)) for row in stress_monitor["scenarios"]),
        default=0.0,
    )
    for row in rows:
        if row["metric"] == "Worst supplied scenario loss":
            row["exposure"] = worst_loss
            row["limit"] = 15_000_000.0
            row["consumption_pct"] = worst_loss / row["limit"] * 100.0
            row["status"] = "BREACH" if row["consumption_pct"] >= 100.0 else "WARNING" if row["consumption_pct"] >= 80.0 else "OK"
            row["escalation_status"] = (
                "Immediate escalation required" if row["status"] == "BREACH"
                else "Owner review required" if row["status"] == "WARNING"
                else "No escalation"
            )
    return {
        **result,
        "as_of_date": str(v8.df.iloc[-1]["cob_date"].date()),
        "limits": rows,
        "summary": {
            "breaches": sum(row["status"] == "BREACH" for row in rows),
            "warnings": sum(row["status"] == "WARNING" for row in rows),
            "ok": sum(row["status"] == "OK" for row in rows),
        },
        "usage_note": "Configured prototype limits across VaR, P&L, backtesting, sensitivities and the full supplied stress catalogue.",
    }




CURRENCY_ORDER = ["EUR", "USD", "JPY", "GBP", "CHF", "AUD", "HKD", "CNY"]
V30_DELTA_LIMITS = {"EUR": (160000.,180000.), "USD": (130000.,145000.), "JPY": (55000.,65000.), "GBP": (70000.,80000.), "CHF": (50000.,60000.), "AUD": (60000.,70000.), "HKD": (45000.,55000.), "CNY": (50000.,60000.)}


def get_market_sensitivities():
    """Return eight-currency OIS/BOR sensitivities without inflation curves."""
    source = v28.get_market_sensitivities()
    frame = pd.DataFrame(source["sensitivities"])
    frame = frame.loc[frame["curve_type"].ne("Inflation")].copy()
    additions = []
    for currency, reference, multiplier, names in [
        ("CHF", "EUR", .42, {"OIS": "SARON OIS", "BOR": "CHF projection"}),
        ("AUD", "GBP", .55, {"OIS": "AONIA OIS", "BOR": "AUD projection"}),
    ]:
        for row in frame.loc[frame["risk_class"].eq("Rates") & frame["currency"].eq(reference)].to_dict("records"):
            row = dict(row)
            row["currency"], row["curve"] = currency, names.get(row["curve_type"], f"{currency} curve")
            row["value"] = float(row["value"]) * multiplier
            row["definition"] = f"{row['measure']} for {row['curve']} {currency} risk factor."
            additions.append(row)
    additions += [
        {"risk_class":"FX", "measure":"FX Delta", "currency":"CHF/USD", "curve_type":"Spot", "curve":"CHF/USD", "value":-95000., "unit":"EUR / 1% spot", "definition":"P&L change for a +1% move in CHF/USD."},
        {"risk_class":"FX", "measure":"FX Delta", "currency":"AUD/USD", "curve_type":"Spot", "curve":"AUD/USD", "value":120000., "unit":"EUR / 1% spot", "definition":"P&L change for a +1% move in AUD/USD."},
    ]
    combined = pd.concat([frame, pd.DataFrame(additions)], ignore_index=True, sort=False)
    return {**source, "currencies": CURRENCY_ORDER, "curve_families": ["OIS", "BOR"], "sensitivities": combined.to_dict("records"), "usage_note": "Deterministic V30 prototype sensitivity feed across eight currencies. Rates use OIS and BOR curve families only; no inflation curves are included."}


def get_delta_curve_tenor_summary(currencies=None):
    """Return compact OIS/BOR curve Delta rows and currency subtotals."""
    source = get_market_sensitivities()
    selected = source["currencies"] if currencies is None else currencies
    frame = pd.DataFrame(source["sensitivities"])
    delta = frame.loc[frame["measure"].eq("IR Delta (DV01)") & frame["currency"].isin(selected)].copy()
    tenors = ["1M", "3M", "6M", "1Y", "2Y", "5Y", "10Y+"]
    detail = delta.pivot_table(index=["currency", "curve_type", "curve"], columns="tenor", values="value", aggfunc="sum", fill_value=0.0).reset_index()
    for tenor in ["1M", "3M", "6M", "1Y", "2Y", "5Y", "10Y", "30Y"]:
        if tenor not in detail: detail[tenor] = 0.0
    detail["10Y+"] = detail["10Y"] + detail["30Y"]
    rows = []
    for currency in selected:
        currency_detail = detail.loc[detail["currency"].eq(currency)].copy()
        net_limit, gross_limit = V30_DELTA_LIMITS[currency]
        counts = currency_detail.groupby("curve_type")["curve"].nunique().to_dict()
        for item in currency_detail.sort_values(["curve_type", "curve"]).to_dict("records"):
            share = (.65 if item["curve_type"] == "OIS" else .35) / max(counts.get(item["curve_type"], 1), 1)
            values = {tenor:float(item[tenor]) for tenor in tenors}
            net, gross = sum(values.values()), sum(abs(value) for value in values.values())
            rows.append({"currency":currency, "curve_type":item["curve_type"], "curve":item["curve"], **values, "net_delta":net, "net_limit":net_limit*share, "net_pct":abs(net)/(net_limit*share)*100, "gross_delta":gross, "gross_limit":gross_limit*share, "gross_pct":gross/(gross_limit*share)*100, "row_type":"Curve"})
        nodes = delta.loc[delta["currency"].eq(currency)]
        totals = nodes.groupby("tenor")["value"].sum()
        values = {tenor:float(totals.get(tenor, 0.)) for tenor in tenors[:-1]}
        values["10Y+"] = float(totals.get("10Y", 0.) + totals.get("30Y", 0.))
        net = sum(values.values())
        gross = sum(row["gross_delta"] for row in rows if row["currency"] == currency and row["row_type"] == "Curve")
        rows.append({"currency":currency, "curve_type":"Subtotal", "curve":f"{currency} total", **values, "net_delta":net, "net_limit":net_limit, "net_pct":abs(net)/net_limit*100, "gross_delta":gross, "gross_limit":gross_limit, "gross_pct":gross/gross_limit*100, "row_type":"Currency subtotal"})
    return {"currencies":selected, "tenors":tenors, "rows":rows, "usage_note":"Curve rows and subtotals include OIS and BOR curves only. Net Delta is signed; Gross Delta is absolute."}


def get_ir_vega_surface(currencies=None):
    source = get_market_sensitivities()
    selected = source["currencies"] if currencies is None else currencies
    frame = pd.DataFrame(source["sensitivities"])
    return {"option_expiries":["1Y", "5Y"], "underlying_tenors":["2Y", "10Y"], "surface":frame.loc[frame["measure"].eq("Vega") & frame["currency"].isin(selected)].to_dict("records"), "usage_note":"IR Vega is represented by a 2 x 2 option-expiry by underlying-swap-tenor surface."}


def build_pla_demo_history():
    """Extend the deterministic PLA feed to the same 260 business-day horizon."""
    base = v28.build_pla_demo_history().copy()
    dates = pd.bdate_range(end=v8.df["cob_date"].max(), periods=len(v8.df))
    missing = [date for date in dates if date not in set(base["cob_date"])]
    if not missing: return base
    rng = __import__("numpy").random.default_rng(30030)
    extra = []
    for _, history in base.groupby("trading_desk", sort=False):
        template = history.sort_values("cob_date").iloc[0].to_dict()
        scale = max(abs(float(template["hypothetical_pnl"]))*.22, 20000.)
        for date in missing:
            row = dict(template); row["cob_date"] = date
            hpl = float(template["hypothetical_pnl"])*rng.normal(.85,.24) + rng.normal(0,scale)
            rtpl = hpl*rng.normal(.97,.04) + rng.normal(0,scale*.18)
            apl = hpl + rng.normal(0,scale*.30)
            row.update({"actual_pnl":apl, "hypothetical_pnl":hpl, "risk_theoretical_pnl":rtpl, "apl_hpl_difference":apl-hpl, "hpl_rtpl_difference":hpl-rtpl})
            for driver in DRIVER_COLUMNS: row[driver] = float(template[driver])*rng.normal(.82,.28)
            row["explained_pnl"] = sum(float(row[driver]) for driver in DRIVER_COLUMNS)
            row["unexplained_pnl"] = rtpl-row["explained_pnl"]
            row["data_classification"] = "Deterministic synthetic V30 PLA demo"
            extra.append(row)
    return pd.concat([pd.DataFrame(extra), base], ignore_index=True).sort_values(["cob_date","trading_desk"]).reset_index(drop=True)


def get_dashboard_ir_volatility_surface(currency="EUR"):
    """Return an aggregated short-expiry, long-tenor IR volatility surface for the Dashboard only."""
    frame = pd.DataFrame(get_market_sensitivities()["sensitivities"])
    gross_total = float(frame.loc[(frame["measure"] == "Vega") & (frame["currency"] == currency), "value"].abs().sum())
    option_expiries = ["1M", "3M", "6M", "1Y", "2Y", "5Y"]
    underlying_tenors = ["1Y", "2Y", "5Y", "10Y", "30Y"]
    expiry_weights = [0.08, 0.12, 0.16, 0.20, 0.20, 0.24]
    tenor_weights = [0.08, 0.12, 0.21, 0.29, 0.30]
    rows = []
    for expiry, expiry_weight in zip(option_expiries, expiry_weights):
        for tenor, tenor_weight in zip(underlying_tenors, tenor_weights):
            rows.append({"currency": currency, "option_expiry": expiry, "underlying_tenor": tenor, "value": gross_total * expiry_weight * tenor_weight})
    return {"currency": currency, "option_expiries": option_expiries, "underlying_tenors": underlying_tenors, "surface": rows, "usage_note": "Dashboard-only gross IR-volatility aggregation. The Sensitivities tab retains its unchanged 2 x 2 native-zone matrix."}


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
        "Provide a market-risk-manager assessment grounded only in this result, following the requested answer detail."
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



v8.validate_data = validate_data
v8.TOOL_FUNCTIONS["validate_data"] = validate_data
v8.TOOL_DESCRIPTIONS["validate_data"] = "Business-day extract validation: weekday-only, complete business-date sequence, duplicates and missing values."
v8.TOOL_FUNCTIONS["get_stress_analysis"] = get_stress_analysis
v8.TOOL_DESCRIPTIONS["get_stress_analysis"] = "Latest supplied stress revaluation P&L across historical, hypothetical, adverse and extreme scenarios."
v8.TOOL_FUNCTIONS["get_stress_movement_table"] = get_stress_movement_table
v8.TOOL_DESCRIPTIONS["get_stress_movement_table"] = "Current supplied stress impacts with business-day, weekly and monthly movements."
v8.TOOL_FUNCTIONS["get_stress_limit_monitor"] = get_stress_limit_monitor
v8.TOOL_DESCRIPTIONS["get_stress_limit_monitor"] = "Scenario-level loss, limit consumption and status for all supplied stress scenarios."
v8.TOOL_FUNCTIONS["evaluate_all_limits"] = evaluate_all_limits
v8.TOOL_DESCRIPTIONS["evaluate_all_limits"] = "Configured prototype limits across VaR, P&L, backtesting, sensitivities and supplied stress scenarios."

v8.TOOL_FUNCTIONS["get_market_sensitivities"] = get_market_sensitivities
v8.TOOL_DESCRIPTIONS["get_market_sensitivities"] = "Eight-currency OIS/BOR sensitivity feed without inflation curves."
v8.TOOL_FUNCTIONS["get_delta_curve_tenor_summary"] = get_delta_curve_tenor_summary
v8.TOOL_DESCRIPTIONS["get_delta_curve_tenor_summary"] = "OIS/BOR IR Delta curve-tenor rows with currency subtotals and limits."
v8.TOOL_FUNCTIONS["get_ir_vega_surface"] = get_ir_vega_surface
v8.TOOL_DESCRIPTIONS["get_ir_vega_surface"] = "IR Vega 2 x 2 expiry-by-underlying-tenor surface."
v8.TOOL_FUNCTIONS["build_pla_demo_history"] = build_pla_demo_history
v8.TOOL_DESCRIPTIONS["build_pla_demo_history"] = "260-business-day deterministic synthetic desk-level PLA history."
v8.TOOL_FUNCTIONS["get_dashboard_ir_volatility_surface"] = get_dashboard_ir_volatility_surface
v8.TOOL_DESCRIPTIONS["get_dashboard_ir_volatility_surface"] = "Aggregated short-expiry, long-tenor Dashboard IR volatility surface."
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
