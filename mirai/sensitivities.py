"""Sensitivity data contract and aggregations for the active MIRAI app."""

from __future__ import annotations

from .core import CURRENCY_ORDER, DELTA_LIMITS, _load_sensitivities, df


def get_market_sensitivities() -> dict:
    frame = _load_sensitivities().copy()
    return {
        "as_of_date": str(df.iloc[-1]["cob_date"].date()),
        "currencies": CURRENCY_ORDER,
        "curve_families": ["OIS", "BOR"],
        "tenors": ["1M", "3M", "6M", "1Y", "2Y", "5Y", "10Y", "30Y"],
        "vega_option_expiries": ["1Y", "5Y"],
        "vega_underlying_tenors": ["2Y", "10Y"],
        "sensitivities": frame.to_dict("records"),
        "usage_note": "Deterministic V33 sensitivity feed across eight currencies. Rates use OIS and BOR curves only; no inflation curves are included.",
    }


def get_delta_curve_tenor_summary(currencies=None) -> dict:
    selected = CURRENCY_ORDER if currencies is None else list(currencies)
    frame = _load_sensitivities()
    delta = frame.loc[
        frame["measure"].eq("IR Delta (DV01)") & frame["currency"].isin(selected)
    ].copy()
    tenors = ["1M", "3M", "6M", "1Y", "2Y", "5Y", "10Y+"]
    detail = delta.pivot_table(
        index=["currency", "curve_type", "curve"],
        columns="tenor",
        values="value",
        aggfunc="sum",
        fill_value=0.0,
    ).reset_index()
    for tenor in ["1M", "3M", "6M", "1Y", "2Y", "5Y", "10Y", "30Y"]:
        if tenor not in detail:
            detail[tenor] = 0.0
    detail["10Y+"] = detail["10Y"] + detail["30Y"]

    rows = []
    for currency in selected:
        currency_detail = detail.loc[detail["currency"].eq(currency)].copy()
        net_limit, gross_limit = DELTA_LIMITS[currency]
        counts = currency_detail.groupby("curve_type")["curve"].nunique().to_dict()
        for item in currency_detail.sort_values(["curve_type", "curve"]).to_dict("records"):
            share = (0.65 if item["curve_type"] == "OIS" else 0.35) / max(
                counts.get(item["curve_type"], 1), 1
            )
            values = {tenor: float(item[tenor]) for tenor in tenors}
            net = sum(values.values())
            gross = sum(abs(value) for value in values.values())
            rows.append(
                {
                    "currency": currency,
                    "curve_type": item["curve_type"],
                    "curve": item["curve"],
                    **values,
                    "net_delta": net,
                    "net_limit": net_limit * share,
                    "net_pct": abs(net) / (net_limit * share) * 100.0,
                    "gross_delta": gross,
                    "gross_limit": gross_limit * share,
                    "gross_pct": gross / (gross_limit * share) * 100.0,
                    "row_type": "Curve",
                }
            )
        nodes = delta.loc[delta["currency"].eq(currency)]
        totals = nodes.groupby("tenor")["value"].sum()
        values = {tenor: float(totals.get(tenor, 0.0)) for tenor in tenors[:-1]}
        values["10Y+"] = float(totals.get("10Y", 0.0) + totals.get("30Y", 0.0))
        net = sum(values.values())
        gross = sum(
            row["gross_delta"]
            for row in rows
            if row["currency"] == currency and row["row_type"] == "Curve"
        )
        rows.append(
            {
                "currency": currency,
                "curve_type": "Subtotal",
                "curve": f"{currency} total",
                **values,
                "net_delta": net,
                "net_limit": net_limit,
                "net_pct": abs(net) / net_limit * 100.0,
                "gross_delta": gross,
                "gross_limit": gross_limit,
                "gross_pct": gross / gross_limit * 100.0,
                "row_type": "Currency subtotal",
            }
        )
    return {
        "currencies": selected,
        "tenors": tenors,
        "rows": rows,
        "usage_note": "Curve rows and subtotals include OIS and BOR curves only. Net Delta is signed; Gross Delta is absolute.",
    }


def get_ir_vega_surface(currencies=None) -> dict:
    selected = CURRENCY_ORDER if currencies is None else list(currencies)
    frame = _load_sensitivities()
    rows = frame.loc[
        frame["measure"].eq("Vega") & frame["currency"].isin(selected)
    ].copy()
    return {
        "option_expiries": ["1Y", "5Y"],
        "underlying_tenors": ["2Y", "10Y"],
        "surface": rows.to_dict("records"),
        "usage_note": "IR Vega is represented by a 2 x 2 option-expiry by underlying-swap-tenor surface.",
    }


def get_dashboard_ir_volatility_surface(currency="EUR") -> dict:
    frame = _load_sensitivities()
    gross = float(
        frame.loc[
            frame["measure"].eq("Vega") & frame["currency"].eq(currency),
            "value",
        ].abs().sum()
    )
    expiries = ["1M", "3M", "6M", "1Y", "2Y", "5Y"]
    tenors = ["1Y", "2Y", "5Y", "10Y", "30Y"]
    expiry_weights = [0.08, 0.12, 0.16, 0.20, 0.20, 0.24]
    tenor_weights = [0.08, 0.12, 0.21, 0.29, 0.30]
    rows = [
        {
            "currency": currency,
            "option_expiry": expiry,
            "underlying_tenor": tenor,
            "value": gross * expiry_weight * tenor_weight,
        }
        for expiry, expiry_weight in zip(expiries, expiry_weights)
        for tenor, tenor_weight in zip(tenors, tenor_weights)
    ]
    return {
        "currency": currency,
        "option_expiries": expiries,
        "underlying_tenors": tenors,
        "surface": rows,
        "usage_note": "Dashboard-only gross IR-volatility aggregation. The Sensitivities page retains the native 2 x 2 matrix.",
    }


def get_scenario_lab_specification() -> dict:
    frame = _load_sensitivities()
    rate_rows = frame.loc[frame["risk_class"].eq("Rates")]
    fx_rows = frame.loc[frame["measure"].eq("FX Delta")]
    return {
        "rate_currencies": sorted(rate_rows["currency"].dropna().unique().tolist()),
        "curve_families": sorted(rate_rows["curve_type"].dropna().unique().tolist()),
        "fx_pairs": sorted(fx_rows["curve"].dropna().unique().tolist()),
        "severity_options": {"Adverse (1x)": 1.0, "Extreme (2x)": 2.0},
        "methodology": "Estimated scenario P&L = Delta x shock + 0.5 x Gamma x shock^2 + Vega x volatility change + FX Delta x spot move + Theta x horizon.",
        "governance_note": "Sensitivity-based what-if estimate. It is not an official full-revaluation risk-engine result and does not recalculate official VaR or Expected Shortfall.",
    }
