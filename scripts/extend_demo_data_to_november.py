"""Deterministically extend MIRAI's synthetic demo feeds to 10 November 2026.

The script always rebuilds the extension from the preserved 24 August anchor,
so rerunning it produces byte-for-byte stable business-date observations.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RISK_PATH = ROOT / "data" / "market_risk_attribution_wide.csv"
PLA_PATH = ROOT / "data" / "mirai_pla_history.csv"
ANCHOR_DATE = pd.Timestamp("2026-08-24")
TARGET_DATE = pd.Timestamp("2026-11-10")
SEED = 20261110

VAR_COMPONENTS = [
    "contrib_var_fx_spot",
    "contrib_var_fx_vol_implied",
    "contrib_var_fx_basis",
    "contrib_var_ir_sofr_curve",
    "contrib_var_ir_estr_curve",
    "contrib_var_ir_sonia_curve",
    "contrib_var_ir_swaption_vol",
    "contrib_var_ir_basis_tenor",
    "contrib_var_ir_convexity",
    "contrib_var_credit_ig_spread",
    "contrib_var_credit_hy_spread",
    "contrib_var_credit_cds_basis",
    "contrib_var_equity_spot",
    "contrib_var_equity_vol",
    "contrib_var_commodity_energy",
    "contrib_var_commodity_metals",
    "contrib_var_inflation_breakeven",
    "contrib_var_new_trades",
    "contrib_var_expired_trades",
    "contrib_var_modified_trades",
]

PNL_DRIVERS = [
    "pnl_driver_fx_delta",
    "pnl_driver_ir_dv01",
    "pnl_driver_vega",
    "pnl_driver_gamma",
    "pnl_driver_theta",
    "pnl_driver_cs01",
    "pnl_driver_cross_gamma",
]

STRESS_COLUMNS = [
    "stress_2008_lehman_crisis",
    "stress_2011_us_downgrade",
    "stress_2020_covid_liquidity",
    "stress_2022_rate_hikes",
    "stress_ir_up_100bp",
    "stress_ir_down_100bp",
    "stress_ir_steepener_50bp",
    "stress_ir_flattener_50bp",
    "stress_fx_usd_up_10pct",
    "stress_vol_up_50pct",
    "stress_credit_spreads_150bp",
    "stress_equity_down_30pct",
    "stress_eur_usd_down_15pct",
    "stress_basis_widen_50bp",
    "stress_em_rates_up_200bp",
    "stress_credit_spreads_300bp",
    "stress_equity_down_60pct",
    "stress_eur_usd_down_30pct",
    "stress_basis_widen_100bp",
    "stress_em_rates_up_400bp",
]

PLA_DRIVERS = [
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


def _business_dates() -> pd.DatetimeIndex:
    return pd.bdate_range(ANCHOR_DATE + pd.offsets.BDay(1), TARGET_DATE)


def _preserved_base_text(path: Path) -> str:
    """Keep every original CSV byte through the anchor date unchanged."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError(f"{path.name} is empty.")
    anchor = ANCHOR_DATE.strftime("%Y-%m-%d")
    base_lines = [lines[0], *(line for line in lines[1:] if line.split(",", 1)[0] <= anchor)]
    return "\n".join(base_lines)


def _write_extension(
    path: Path,
    base_text: str,
    extension: pd.DataFrame,
    *,
    float_format: str,
) -> None:
    extension_text = extension.to_csv(
        index=False,
        header=False,
        date_format="%Y-%m-%d",
        float_format=float_format,
        lineterminator="\n",
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(base_text.rstrip("\n") + "\n" + extension_text)


def extend_risk_feed() -> pd.DataFrame:
    base_text = _preserved_base_text(RISK_PATH)
    source = pd.read_csv(RISK_PATH, parse_dates=["cob_date"])
    base = source.loc[source["cob_date"] <= ANCHOR_DATE].copy()
    if base.empty or base.iloc[-1]["cob_date"] != ANCHOR_DATE:
        raise ValueError("The expected 24 August 2026 anchor is missing.")

    anchor = base.iloc[-1].copy()
    dates = _business_dates()
    rng = np.random.default_rng(SEED)
    rows: list[pd.Series] = []
    previous_hvar = float(anchor["var_1d_99_hist"])
    anchor_hvar = previous_hvar
    anchor_components = anchor[VAR_COMPONENTS].astype(float)
    driver_weights = np.array([0.24, 0.30, 0.13, 0.09, 0.07, 0.10, 0.07])

    for index, date in enumerate(dates, start=1):
        row = anchor.copy()
        row["cob_date"] = date

        volatility_wave = 230_000 * np.sin(index / 6.2) + 150_000 * np.sin(index / 2.8)
        september_event = 330_000 * np.exp(-((index - 21) / 6.0) ** 2)
        october_relief = -260_000 * np.exp(-((index - 45) / 7.0) ** 2)
        long_run_level = 5_080_000 + volatility_wave + september_event + october_relief
        hvar = np.clip(
            0.82 * previous_hvar + 0.18 * long_run_level + rng.normal(0, 105_000),
            4_350_000,
            5_780_000,
        )
        previous_hvar = float(hvar)
        row["var_1d_99_hist"] = round(hvar, 2)
        row["var_1d_99_param"] = round(hvar * (0.96 + rng.normal(0, 0.018)), 2)
        row["var_1d_99_mc"] = round(hvar * (1.025 + rng.normal(0, 0.018)), 2)
        row["var_10d_99_reg"] = round(hvar * np.sqrt(10) * 0.93, 2)
        svar = np.clip(hvar * 1.54 + 410_000 + rng.normal(0, 125_000), 7_650_000, 8_880_000)
        row["stressed_var_1d_99"] = round(svar, 2)
        row["expected_shortfall_97_5"] = round(hvar * (1.20 + rng.normal(0, 0.015)), 2)
        row["var_limit_amount"] = 6_000_000.0
        row["var_limit_utilization_pct"] = round(hvar / 6_000_000 * 100, 2)

        component_scale = hvar / anchor_hvar
        varied_components = []
        for component_index, value in enumerate(anchor_components):
            cycle = 1.0 + 0.055 * np.sin(index / (3.8 + component_index % 5) + component_index)
            noise = rng.normal(0, 0.018)
            varied_components.append(float(value) * component_scale * (cycle + noise))
        row[VAR_COMPONENTS] = np.round(varied_components, 2)
        row["diversification_effect"] = round(hvar - sum(varied_components), 2)

        actual_pnl = float(np.clip(rng.normal(-25_000, 360_000) + 125_000 * np.sin(index / 4.7), -1_250_000, 1_150_000))
        unexplained = float(np.clip(rng.normal(0, 55_000), -145_000, 145_000))
        clean_pnl = actual_pnl - unexplained
        hypothetical_pnl = actual_pnl - rng.normal(0, 82_000)
        row["actual_pnl"] = round(actual_pnl, 2)
        row["hypothetical_pnl"] = round(hypothetical_pnl, 2)
        row["clean_pnl"] = round(clean_pnl, 2)
        row["unexplained_pnl"] = round(unexplained, 2)
        driver_values = clean_pnl * driver_weights
        row[PNL_DRIVERS] = np.round(driver_values, 2)

        stress_scale = 0.975 + 0.075 * component_scale + 0.018 * np.sin(index / 5.5)
        for stress_index, column in enumerate(STRESS_COLUMNS):
            scenario_noise = rng.normal(0, 0.008)
            row[column] = round(float(anchor[column]) * (stress_scale + scenario_noise), 2)
        for adverse, extreme in [
            ("stress_credit_spreads_150bp", "stress_credit_spreads_300bp"),
            ("stress_equity_down_30pct", "stress_equity_down_60pct"),
            ("stress_eur_usd_down_15pct", "stress_eur_usd_down_30pct"),
            ("stress_basis_widen_50bp", "stress_basis_widen_100bp"),
            ("stress_em_rates_up_200bp", "stress_em_rates_up_400bp"),
        ]:
            row[extreme] = round(float(row[adverse]) * (2.0 + rng.normal(0, 0.018)), 2)

        row["backtest_hypo_exception"] = bool(hypothetical_pnl < -hvar)
        row["backtest_actual_exception"] = bool(actual_pnl < -hvar)
        rows.append(row)

    extended = pd.concat([base, pd.DataFrame(rows)], ignore_index=True)
    extended["backtest_exception_count_250d"] = (
        extended["backtest_hypo_exception"].astype(bool).rolling(250, min_periods=1).sum().astype(int)
    )
    extended["basel_traffic_light_zone"] = np.select(
        [extended["backtest_exception_count_250d"] <= 4, extended["backtest_exception_count_250d"] <= 9],
        ["GREEN", "AMBER"],
        default="RED",
    )
    _write_extension(
        RISK_PATH,
        base_text,
        extended.loc[extended["cob_date"] > ANCHOR_DATE],
        float_format="%.2f",
    )
    return extended


def extend_pla_feed() -> pd.DataFrame:
    base_text = _preserved_base_text(PLA_PATH)
    source = pd.read_csv(PLA_PATH, parse_dates=["cob_date"])
    base = source.loc[source["cob_date"] <= ANCHOR_DATE].copy()
    templates = base.sort_values("cob_date").groupby("trading_desk", sort=False).tail(1)
    rng = np.random.default_rng(SEED + 1)
    rows: list[dict] = []
    dates = _business_dates()
    flagged_desks = {"Equity volatility", "Exotics", "Swaptions"}

    for date_index, date in enumerate(dates, start=1):
        common_market_move = rng.normal(0, 1)
        for desk_index, template in enumerate(templates.to_dict("records")):
            scale = max(abs(float(template["hypothetical_pnl"])), 45_000.0)
            beta = 0.45 + 0.08 * (desk_index % 5)
            hpl = scale * (0.48 * beta * common_market_move + rng.normal(0, 0.62))
            rtpl = hpl * (0.96 + rng.normal(0, 0.025)) + rng.normal(0, scale * 0.06)
            apl = hpl + rng.normal(0, scale * 0.12)
            residual_ratio = 0.07 + 0.02 * abs(np.sin(date_index / 7 + desk_index))
            if date == TARGET_DATE and template["trading_desk"] in flagged_desks:
                residual_ratio = 0.26
            unexplained = np.sign(rtpl if rtpl else 1.0) * abs(apl) * residual_ratio
            explained = rtpl - unexplained

            template_explained = float(template["explained_pnl"])
            if abs(template_explained) < 1e-9:
                weights = np.repeat(1 / len(PLA_DRIVERS), len(PLA_DRIVERS))
            else:
                weights = np.array([float(template[column]) / template_explained for column in PLA_DRIVERS])
            driver_values = explained * weights
            driver_values[-1] += explained - driver_values.sum()

            row = dict(template)
            row.update(
                {
                    "cob_date": date,
                    "actual_pnl": apl,
                    "hypothetical_pnl": hpl,
                    "risk_theoretical_pnl": rtpl,
                    "apl_hpl_difference": apl - hpl,
                    "hpl_rtpl_difference": hpl - rtpl,
                    "explained_pnl": explained,
                    "unexplained_pnl": unexplained,
                    "data_classification": "Deterministic synthetic V33 PLA demo",
                }
            )
            row.update(dict(zip(PLA_DRIVERS, driver_values)))
            rows.append(row)

    extended = pd.concat([base, pd.DataFrame(rows)], ignore_index=True)
    extended = extended.sort_values(["cob_date", "trading_desk"]).reset_index(drop=True)
    _write_extension(
        PLA_PATH,
        base_text,
        extended.loc[extended["cob_date"] > ANCHOR_DATE],
        float_format="%.6f",
    )
    return extended


def main() -> None:
    risk = extend_risk_feed()
    pla = extend_pla_feed()
    print(
        f"Risk feed: {len(risk)} business dates through {risk['cob_date'].max().date()}\n"
        f"PLA feed: {len(pla)} desk/date rows through {pla['cob_date'].max().date()}"
    )


if __name__ == "__main__":
    main()
