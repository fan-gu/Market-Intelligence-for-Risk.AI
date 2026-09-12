"""Deterministic governance, alert, and daily-brief controls for MIRAI."""

from __future__ import annotations

import pandas as pd

from .core import SVAR_LIMIT_MULTIPLIER, build_pla_demo_history, df, get_current_risk
from .sensitivities import get_market_sensitivities
from .stress import get_stress_analysis, get_stress_limit_monitor

WARNING_THRESHOLD_PCT = 80.0
BREACH_THRESHOLD_PCT = 100.0
UNEXPLAINED_APL_ALERT_THRESHOLD_PCT = 20.0


def _limit_status(consumption_pct: float) -> str:
    if consumption_pct >= BREACH_THRESHOLD_PCT:
        return "BREACH"
    if consumption_pct >= WARNING_THRESHOLD_PCT:
        return "WARNING"
    return "OK"


def evaluate_pnl_explain_alerts() -> dict:
    """Flag desks where absolute unexplained P&L exceeds 20% of absolute APL."""
    history = build_pla_demo_history()
    latest = history.sort_values("cob_date").groupby("trading_desk", as_index=False).tail(1)
    results = []
    for row in latest.to_dict("records"):
        apl = abs(float(row["actual_pnl"]))
        unexplained = abs(float(row["unexplained_pnl"]))
        ratio = float("inf") if apl == 0 and unexplained else (0.0 if apl == 0 else unexplained / apl * 100.0)
        results.append({
            "business_line": row["business_line"],
            "trading_desk": row["trading_desk"],
            "actual_pnl": float(row["actual_pnl"]),
            "unexplained_pnl": float(row["unexplained_pnl"]),
            "unexplained_to_apl_pct": ratio,
            "threshold_pct": UNEXPLAINED_APL_ALERT_THRESHOLD_PCT,
            "status": "ALERT" if ratio > UNEXPLAINED_APL_ALERT_THRESHOLD_PCT else "OK",
        })
    return {
        "as_of_date": str(pd.Timestamp(latest["cob_date"].max()).date()),
        "threshold_pct": UNEXPLAINED_APL_ALERT_THRESHOLD_PCT,
        "flagged_count": sum(item["status"] == "ALERT" for item in results),
        "desk_results": results,
        "usage_note": "Control flags |driver-unexplained P&L| / |APL| above 20%; prototype thresholds and data are synthetic.",
    }


def evaluate_sensitivity_limits() -> dict:
    """Evaluate governed sensitivities; Gamma remains informational."""
    frame = pd.DataFrame(get_market_sensitivities()["sensitivities"])
    delta = frame.loc[frame["measure"].eq("IR Delta (DV01)"), "value"].astype(float)
    definitions = [
        ("Net IR Delta", abs(float(delta.sum())), 200_000.0, "EUR / bp", "Rates Risk", "Absolute signed net"),
        ("Gross IR Delta", float(delta.abs().sum()), 500_000.0, "EUR / bp", "Rates Risk", "Gross absolute"),
        ("Vega", float(frame.loc[frame["measure"].eq("Vega"), "value"].abs().sum()), 150_000.0, "EUR / vol point", "Volatility Risk", "Gross surface Vega"),
        ("FX Delta", float(frame.loc[frame["measure"].eq("FX Delta"), "value"].abs().sum()), 1_100_000.0, "EUR / 1% spot", "FX Risk", "Gross absolute"),
        ("Theta", float(frame.loc[frame["measure"].eq("Theta"), "value"].abs().sum()), 40_000.0, "EUR / day", "Market Risk", "Gross absolute"),
    ]
    rows = []
    for measure, exposure, limit, unit, owner, basis in definitions:
        consumption = 0.0 if limit == 0 else exposure / limit * 100.0
        rows.append({
            "measure": measure, "gross_exposure": exposure, "limit": limit,
            "consumption_pct": consumption, "status": _limit_status(consumption),
            "unit": unit, "owner": owner, "consumption_basis": basis,
        })
    return {
        "limits": rows,
        "summary": {status.lower() if status != "OK" else "ok": sum(row["status"] == status for row in rows) for status in ("BREACH", "WARNING", "OK")},
        "usage_note": "Net and Gross Delta have separate controls; IR Gamma is informational. Warning starts at 80% and breach at 100%.",
    }


def _governed_row(family, metric, exposure, limit, unit, owner, basis) -> dict:
    consumption = 0.0 if limit == 0 else float(exposure) / float(limit) * 100.0
    status = _limit_status(consumption)
    return {
        "family": family, "metric": metric, "exposure": float(exposure), "limit": float(limit),
        "unit": unit, "consumption_pct": consumption, "warning_threshold_pct": 80.0,
        "breach_threshold_pct": 100.0, "status": status, "owner": owner,
        "consumption_basis": basis,
        "escalation_status": "Immediate escalation required" if status == "BREACH" else "Owner review required" if status == "WARNING" else "No escalation",
    }


def evaluate_all_limits() -> dict:
    latest = df.iloc[-1]
    stress = get_stress_limit_monitor()
    worst_loss = max((abs(min(float(row["impact"]), 0.0)) for row in stress["scenarios"]), default=0.0)
    rows = [
        _governed_row("VaR", "Historical VaR (1 day, 99%)", abs(latest["var_1d_99_hist"]), abs(latest["var_limit_amount"]), "EUR", "Market Risk", "Absolute HVaR"),
        _governed_row("VaR", "Stressed VaR (SVaR, 1 day, 99%)", abs(latest["stressed_var_1d_99"]), abs(latest["var_limit_amount"]) * SVAR_LIMIT_MULTIPLIER, "EUR", "Market Risk", "Absolute SVaR"),
        _governed_row("Stress", "Worst-case stress loss", worst_loss, 15_000_000.0, "EUR", "Stress Testing", "Largest supplied scenario loss"),
        _governed_row("P&L", "Daily actual loss", abs(min(float(latest["actual_pnl"]), 0.0)), 1_000_000.0, "EUR", "P&L Control", "Current negative APL"),
        _governed_row("P&L", "Absolute unexplained P&L", abs(latest["unexplained_pnl"]), 250_000.0, "EUR", "P&L Control", "Absolute residual"),
        _governed_row("Backtesting", "250-day exceptions", latest["backtest_exception_count_250d"], 4.0, "Exceptions", "Model Validation", "Rolling hypothetical-P&L exceptions"),
    ]
    for item in evaluate_sensitivity_limits()["limits"]:
        rows.append(_governed_row("Sensitivity", item["measure"], item["gross_exposure"], item["limit"], item["unit"], item["owner"], item["consumption_basis"]))
    return {
        "as_of_date": str(pd.Timestamp(latest["cob_date"]).date()),
        "limits": rows,
        "summary": {"breaches": sum(row["status"] == "BREACH" for row in rows), "warnings": sum(row["status"] == "WARNING" for row in rows), "ok": sum(row["status"] == "OK" for row in rows)},
        "usage_note": "Configured prototype limits across VaR, P&L, backtesting, sensitivities and supplied stress results.",
    }


def get_risk_alerts() -> dict:
    current = get_current_risk()
    rows = evaluate_all_limits()["limits"]
    alerts = []
    for row in rows:
        if row["status"] != "OK":
            alerts.append({
                "severity": "CRITICAL" if row["status"] == "BREACH" else "HIGH",
                "title": row["metric"],
                "summary": f"Consumption is {row['consumption_pct']:.1f}% of the configured prototype limit.",
            })
    worst_name, worst_impact = min(get_stress_analysis().items(), key=lambda item: item[1])
    alerts.append({"severity": "INFO", "title": "Most adverse stress scenario", "summary": f"{worst_name} produces the lowest reported impact: {worst_impact:,.0f}."})
    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "INFO": 3}
    alerts.sort(key=lambda item: order[item["severity"]])
    return {"as_of_date": current["date"], "action_required_count": sum(item["severity"] != "INFO" for item in alerts), "alerts": alerts, "thresholds": {"warning_pct": 80, "breach_pct": 100}}


def _reference_row(source: pd.DataFrame, current_date: pd.Timestamp, days: int) -> pd.Series | None:
    eligible = source.loc[source["cob_date"] <= current_date - pd.Timedelta(days=days)]
    return None if eligible.empty else eligible.iloc[-1]


def detect_material_risk_movements(as_of_date=None) -> dict:
    source = df if as_of_date is None else df.loc[df["cob_date"] <= pd.Timestamp(as_of_date)]
    latest = source.iloc[-1]
    findings = []
    for period, days, threshold in (("Daily", 1, 10.0), ("Weekly", 7, 15.0), ("Monthly", 30, 15.0)):
        reference = _reference_row(source, latest["cob_date"], days)
        if reference is not None and float(reference["var_1d_99_hist"]) != 0:
            movement = (float(latest["var_1d_99_hist"]) / float(reference["var_1d_99_hist"]) - 1.0) * 100.0
            if abs(movement) >= threshold:
                findings.append({"source": "VaR", "finding": f"{period} Historical VaR movement", "severity": "HIGH" if abs(movement) >= threshold * 2 else "MEDIUM", "observed": movement, "threshold": threshold, "unit": "%", "action": "Review VaR movement attribution by risk factor."})
    for row in evaluate_pnl_explain_alerts()["desk_results"]:
        if row["status"] == "ALERT":
            findings.append({"source": "P&L", "finding": f"Unexplained P&L: {row['trading_desk']}", "severity": "HIGH", "observed": row["unexplained_to_apl_pct"], "threshold": row["threshold_pct"], "unit": "% of |APL|", "action": "Investigate missing drivers and valuation differences."})
    for row in get_stress_limit_monitor(as_of_date).get("scenarios", []):
        if row["status"] != "OK":
            findings.append({"source": "Stress", "finding": f"{row['scenario']} limit consumption", "severity": "CRITICAL" if row["status"] == "BREACH" else "HIGH", "observed": row["consumption_pct"], "threshold": 100.0 if row["status"] == "BREACH" else 80.0, "unit": "%", "action": "Escalate breach immediately." if row["status"] == "BREACH" else "Review scenario exposure with the limit owner."})
    for row in evaluate_all_limits()["limits"]:
        if row["status"] != "OK":
            findings.append({"source": "Limits", "finding": row["metric"], "severity": "CRITICAL" if row["status"] == "BREACH" else "HIGH", "observed": row["consumption_pct"], "threshold": 100.0 if row["status"] == "BREACH" else 80.0, "unit": "%", "action": row["escalation_status"]})
    sensitivity = pd.DataFrame(get_market_sensitivities()["sensitivities"])
    for measure in ("IR Delta (DV01)", "IR Gamma", "Vega", "FX Delta"):
        gross = sensitivity.loc[sensitivity["measure"].eq(measure)].groupby("currency")["value"].apply(lambda values: values.abs().sum())
        if not gross.empty and gross.sum() and float(gross.max() / gross.sum() * 100.0) >= 55.0:
            share = float(gross.max() / gross.sum() * 100.0)
            findings.append({"source": "Sensitivities", "finding": f"{measure} concentration: {gross.idxmax()}", "severity": "MEDIUM", "observed": share, "threshold": 55.0, "unit": "% of gross", "action": "Review currency and tenor concentration."})
    rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}
    findings.sort(key=lambda row: (rank[row["severity"]], row["source"], row["finding"]))
    return {"as_of_date": str(pd.Timestamp(latest["cob_date"]).date()), "finding_count": len(findings), "summary": {"critical": sum(row["severity"] == "CRITICAL" for row in findings), "high": sum(row["severity"] == "HIGH" for row in findings), "medium": sum(row["severity"] == "MEDIUM" for row in findings)}, "findings": findings, "usage_note": "Materiality detection is deterministic and threshold-based; the LLM cannot alter values or severity."}


def generate_daily_risk_brief(as_of_date=None) -> dict:
    materiality = detect_material_risk_movements(as_of_date)
    findings = materiality["findings"]
    owners = {"VaR": "Market Risk", "P&L": "P&L Control", "Stress": "Stress Testing", "Limits": "Named limit owner", "Sensitivities": "Risk-factor owner"}
    actions = [{"action_id": f"A{index:02d}", "priority": item["severity"], "source": item["source"], "finding": item["finding"], "owner": owners.get(item["source"], "Market Risk"), "required_action": item["action"], "workflow_status": "OPEN", "due": "Today" if item["severity"] in {"CRITICAL", "HIGH"} else "Next review"} for index, item in enumerate(findings, 1)]
    summary = materiality["summary"]
    status = "ESCALATION REQUIRED" if summary["critical"] else "REVIEW REQUIRED" if summary["high"] else "MONITOR" if summary["medium"] else "CLEAR"
    current = get_current_risk()
    stress = get_stress_limit_monitor(as_of_date)
    return {"as_of_date": materiality["as_of_date"], "overall_status": status, "headline": f"{len(findings)} material finding(s): {summary['critical']} critical, {summary['high']} high and {summary['medium']} medium.", "risk_snapshot": {"historical_var": float(current["var_hist"]), "stressed_var": float(current["stressed_var"]), "expected_shortfall": float(current["expected_shortfall"]), "stress_breaches": stress.get("summary", {}).get("breaches", 0), "stress_warnings": stress.get("summary", {}).get("warnings", 0)}, "actions": actions, "sign_off": {"status": "PENDING" if actions else "READY", "required_role": "Market Risk Manager", "open_actions": len(actions)}, "evidence": findings, "usage_note": "Generated from deterministic controls; comments and sign-off require an authorised human and persistent workflow store."}

