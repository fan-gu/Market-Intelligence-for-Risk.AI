"""Single production analytics and agent runtime for MIRAI.

Archived versions are rollback artefacts only. The active application imports
this module and the focused services in :mod:`mirai`; it never imports the
historical V8-V32 chain.
"""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

VERSION = "V33"
MODEL_NAME = os.getenv("MIRAI_MODEL", "gemini-3.6-flash")
REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = Path(
    os.getenv(
        "RISK_DATA_FILE",
        REPO_ROOT / "data" / "market_risk_attribution_wide.csv",
    )
)
SENSITIVITY_PATH = REPO_ROOT / "data" / "mirai_sensitivities.csv"
PLA_PATH = REPO_ROOT / "data" / "mirai_pla_history.csv"
AUDIT_PATH = Path(
    os.getenv("MIRAI_AUDIT_DB", REPO_ROOT / "data" / "mirai_audit.db")
)

SVAR_LIMIT_MULTIPLIER = 1.5
UNEXPLAINED_APL_ALERT_THRESHOLD_PCT = 20.0
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
    "New trades",
    "Expired trades",
    "Modified trades",
]

VAR_ATTRIBUTION_GROUPS = {
    "FX": [
        "contrib_var_fx_spot",
        "contrib_var_fx_vol_implied",
        "contrib_var_fx_basis",
    ],
    "Rates": [
        "contrib_var_ir_sofr_curve",
        "contrib_var_ir_estr_curve",
        "contrib_var_ir_sonia_curve",
        "contrib_var_ir_swaption_vol",
        "contrib_var_ir_basis_tenor",
        "contrib_var_ir_convexity",
    ],
    "Credit": [
        "contrib_var_credit_ig_spread",
        "contrib_var_credit_hy_spread",
        "contrib_var_credit_cds_basis",
    ],
    "Equity": ["contrib_var_equity_spot", "contrib_var_equity_vol"],
    "Commodity": [
        "contrib_var_commodity_energy",
        "contrib_var_commodity_metals",
    ],
    "Inflation": ["contrib_var_inflation_breakeven"],
    "New trades": ["contrib_var_new_trades"],
    "Expired trades": ["contrib_var_expired_trades"],
    "Modified trades": ["contrib_var_modified_trades"],
    "Diversification": ["diversification_effect"],
}

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
    "2008 Lehman": 16_000_000.0,
    "2011 US downgrade": 10_000_000.0,
    "2020 COVID": 12_000_000.0,
    "2022 rate hikes": 12_000_000.0,
    "IR +100 bp": 5_000_000.0,
    "IR -100 bp": 5_000_000.0,
    "IR steepener": 6_000_000.0,
    "IR flattener": 6_000_000.0,
    "USD +10%": 4_000_000.0,
    "Vol +50%": 8_000_000.0,
    "Credit +150 bp": 8_000_000.0,
    "Equity -30%": 10_000_000.0,
    "EUR/USD -15%": 7_000_000.0,
    "Basis +50 bp": 6_000_000.0,
    "EM rates +200 bp": 9_000_000.0,
    "Credit +300 bp": 16_000_000.0,
    "Equity -60%": 20_000_000.0,
    "EUR/USD -30%": 14_000_000.0,
    "Basis +100 bp": 12_000_000.0,
    "EM rates +400 bp": 18_000_000.0,
}

CURRENCY_ORDER = ["EUR", "USD", "JPY", "GBP", "CHF", "AUD", "HKD", "CNY"]
DELTA_LIMITS = {
    "EUR": (160_000.0, 180_000.0),
    "USD": (130_000.0, 145_000.0),
    "JPY": (55_000.0, 65_000.0),
    "GBP": (70_000.0, 80_000.0),
    "CHF": (50_000.0, 60_000.0),
    "AUD": (60_000.0, 70_000.0),
    "HKD": (45_000.0, 55_000.0),
    "CNY": (50_000.0, 60_000.0),
}


@lru_cache(maxsize=1)
def load_data() -> pd.DataFrame:
    frame = pd.read_csv(DATA_PATH)
    frame["cob_date"] = pd.to_datetime(frame["cob_date"])
    return frame.sort_values("cob_date").reset_index(drop=True)


@lru_cache(maxsize=1)
def _load_sensitivities() -> pd.DataFrame:
    return pd.read_csv(SENSITIVITY_PATH).fillna({"tenor": "N/A"})


@lru_cache(maxsize=1)
def build_pla_demo_history() -> pd.DataFrame:
    frame = pd.read_csv(PLA_PATH)
    frame["cob_date"] = pd.to_datetime(frame["cob_date"])
    return frame.sort_values(["cob_date", "trading_desk"]).reset_index(drop=True)


df = load_data()


def _latest(as_of_date=None) -> pd.Series:
    source = df if as_of_date is None else df.loc[df["cob_date"] <= pd.Timestamp(as_of_date)]
    if source.empty:
        raise ValueError("No risk observation is available for the selected date.")
    return source.iloc[-1]


def get_current_risk(as_of_date=None) -> dict:
    row = _latest(as_of_date)
    return {
        "date": str(row["cob_date"].date()),
        "var_hist": float(row["var_1d_99_hist"]),
        "var_parametric": float(row["var_1d_99_param"]),
        "var_monte_carlo": float(row["var_1d_99_mc"]),
        "var_10d_regulatory": float(row["var_10d_99_reg"]),
        "stressed_var": float(row["stressed_var_1d_99"]),
        "expected_shortfall": float(row["expected_shortfall_97_5"]),
        "var_limit": float(row["var_limit_amount"]),
        "limit_utilisation": float(row["var_limit_utilization_pct"]),
    }


def get_var_trend(as_of_date=None) -> dict:
    source = df if as_of_date is None else df.loc[df["cob_date"] <= pd.Timestamp(as_of_date)]
    current = float(source.iloc[-1]["var_1d_99_hist"])
    previous = float(source.iloc[-2]["var_1d_99_hist"]) if len(source) > 1 else current
    average = float(source.tail(10)["var_1d_99_hist"].mean())
    return {
        "current_var": current,
        "previous_var": previous,
        "change": current - previous,
        "change_pct": 0.0 if previous == 0 else (current / previous - 1.0) * 100.0,
        "10_day_average": average,
        "vs_10_day_average_pct": 0.0 if average == 0 else (current / average - 1.0) * 100.0,
    }


def get_limit_analysis(as_of_date=None) -> dict:
    current = get_current_risk(as_of_date)
    utilisation = current["limit_utilisation"]
    status = "CRITICAL" if utilisation >= 90 else "HIGH" if utilisation >= 80 else "MEDIUM" if utilisation >= 60 else "NORMAL"
    return {
        "current_var": current["var_hist"],
        "var_limit": current["var_limit"],
        "utilisation_pct": utilisation,
        "status": status,
    }


def get_backtesting_analysis(as_of_date=None) -> dict:
    row = _latest(as_of_date)
    return {
        "hypothetical_exception": int(row["backtest_hypo_exception"]),
        "actual_exception": int(row["backtest_actual_exception"]),
        "exception_count_250d": int(row["backtest_exception_count_250d"]),
        "basel_traffic_light_zone": str(row["basel_traffic_light_zone"]),
    }


def get_pnl_analysis(as_of_date=None) -> dict:
    row = _latest(as_of_date)
    return {
        "actual_pnl": float(row["actual_pnl"]),
        "hypothetical_pnl": float(row["hypothetical_pnl"]),
        "clean_pnl": float(row["clean_pnl"]),
        "unexplained_pnl": float(row["unexplained_pnl"]),
    }


def get_ten_day_summary(as_of_date=None) -> dict:
    source = df if as_of_date is None else df.loc[df["cob_date"] <= pd.Timestamp(as_of_date)]
    source = source.tail(10)
    return {
        "var_average": float(source["var_1d_99_hist"].mean()),
        "var_min": float(source["var_1d_99_hist"].min()),
        "var_max": float(source["var_1d_99_hist"].max()),
        "var_standard_deviation": float(source["var_1d_99_hist"].std()),
        "average_limit_utilisation": float(source["var_limit_utilization_pct"].mean()),
        "maximum_limit_utilisation": float(source["var_limit_utilization_pct"].max()),
        "cumulative_actual_pnl": float(source["actual_pnl"].sum()),
        "best_pnl_day": float(source["actual_pnl"].max()),
        "worst_pnl_day": float(source["actual_pnl"].min()),
    }


def validate_data() -> dict:
    dates = pd.DatetimeIndex(df["cob_date"])
    expected = pd.bdate_range(dates.min(), dates.max())
    return {
        "rows": len(df),
        "columns": len(df.columns),
        "missing_values": int(df.isna().sum().sum()),
        "duplicate_dates": int(dates.duplicated().sum()),
        "weekday_only": bool((dates.dayofweek < 5).all()),
        "business_date_sequence_ok": bool(dates.equals(expected)),
        "date_sequence_ok": bool(dates.equals(expected)),
    }


def get_portfolio_scope() -> dict:
    scope = (
        df.groupby("portfolio_id", dropna=False)
        .agg(observation_count=("cob_date", "size"), reporting_currency=("reporting_currency", "first"))
        .reset_index()
    )
    return {
        "portfolio_count": int(len(scope)),
        "portfolios": scope.to_dict("records"),
        "usage_note": "Portfolio scope comes from the current risk-run extract; it is not a portfolio hierarchy service.",
    }


def get_risk_run_lineage() -> dict:
    payload = DATA_PATH.read_bytes()
    fingerprint = hashlib.sha256(payload).hexdigest()[:16]
    latest = df.iloc[-1]
    run_id = f"DEMO-RUN-{latest['cob_date'].date()}-{fingerprint[:8]}"
    return {
        "validation_status": "VALIDATED" if validate_data()["business_date_sequence_ok"] else "REVIEW",
        "lineage": {
            "run_id": run_id,
            "run_id_note": "Generated by the consolidated demo adapter.",
            "source_file": DATA_PATH.name,
            "source_type": "Synthetic risk-engine extract",
            "data_fingerprint": fingerprint,
            "ingested_at_utc": datetime.now(UTC).isoformat(),
            "validation_status": "VALIDATED",
            "approval_note": "Schema validation is not business approval.",
            "as_of_date": str(latest["cob_date"].date()),
            "first_observation_date": str(df.iloc[0]["cob_date"].date()),
            "portfolio_count": int(df["portfolio_id"].nunique()),
            "reporting_currencies": sorted(df["reporting_currency"].unique().tolist()),
            "row_count": int(len(df)),
            "column_count": int(len(df.columns)),
            "missing_value_count": int(df.isna().sum().sum()),
            "duplicate_date_count": int(df["cob_date"].duplicated().sum()),
            "invalid_date_count": 0,
        },
        "errors": [],
        "warnings": [],
    }


def _empirical_ks_statistic(first, second) -> float:
    first_sorted = np.sort(np.asarray(first, dtype=float))
    second_sorted = np.sort(np.asarray(second, dtype=float))
    combined = np.sort(np.concatenate([first_sorted, second_sorted]))
    first_cdf = np.searchsorted(first_sorted, combined, side="right") / len(first_sorted)
    second_cdf = np.searchsorted(second_sorted, combined, side="right") / len(second_sorted)
    return float(np.max(np.abs(first_cdf - second_cdf)))


def _pla_zone(correlation: float, ks_statistic: float) -> str:
    if correlation > PLA_GREEN_CORRELATION and ks_statistic < PLA_GREEN_KS:
        return "GREEN"
    if correlation < PLA_RED_CORRELATION or ks_statistic > PLA_RED_KS:
        return "RED"
    return "AMBER"


