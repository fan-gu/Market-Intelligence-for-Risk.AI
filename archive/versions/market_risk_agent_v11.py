"""Market Risk AI Assistant V11: deterministic risk alerts."""

from archive.versions import market_risk_agent_v9 as v9
from google.genai import types


VERSION = "V11"
v8 = v9.v8

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "INFO": 3}


def get_risk_alerts():
    """Return transparent, rules-based alerts from the current data snapshot."""
    alerts = []
    limit = v8.get_limit_analysis()
    trend = v8.get_var_trend()
    backtesting = v8.get_backtesting_analysis()
    quality = v8.validate_data()
    stresses = v8.get_stress_analysis()

    if limit["utilisation_pct"] >= 90:
        alerts.append({
            "severity": "CRITICAL",
            "title": "VaR limit utilisation is critical",
            "summary": f"Utilisation is {limit['utilisation_pct']:.1f}%, above the 90% critical threshold.",
        })
    elif limit["utilisation_pct"] >= 80:
        alerts.append({
            "severity": "HIGH",
            "title": "VaR limit utilisation is high",
            "summary": f"Utilisation is {limit['utilisation_pct']:.1f}%, above the 80% high threshold.",
        })
    elif limit["utilisation_pct"] >= 60:
        alerts.append({
            "severity": "MEDIUM",
            "title": "VaR limit utilisation requires monitoring",
            "summary": f"Utilisation is {limit['utilisation_pct']:.1f}%, above the 60% monitoring threshold.",
        })

    movement = abs(trend["change_pct"])
    if movement >= 20:
        alerts.append({
            "severity": "HIGH",
            "title": "Material day-on-day VaR movement",
            "summary": f"Historical VaR moved {trend['change_pct']:.1f}% versus the prior observation.",
        })
    elif movement >= 10:
        alerts.append({
            "severity": "MEDIUM",
            "title": "Notable day-on-day VaR movement",
            "summary": f"Historical VaR moved {trend['change_pct']:.1f}% versus the prior observation.",
        })

    exception_types = []
    if backtesting["hypothetical_exception"]:
        exception_types.append("hypothetical")
    if backtesting["actual_exception"]:
        exception_types.append("actual")
    if exception_types:
        alerts.append({
            "severity": "HIGH",
            "title": "New VaR backtesting exception",
            "summary": f"Today's {', '.join(exception_types)} P&L breached the VaR backtest.",
        })

    data_issues = []
    if quality["missing_values"]:
        data_issues.append(f"{quality['missing_values']} missing values")
    if quality["duplicate_dates"]:
        data_issues.append(f"{quality['duplicate_dates']} duplicate dates")
    calendar_review_needed = not quality["date_sequence_ok"]
    if data_issues:
        alerts.append({
            "severity": "CRITICAL",
            "title": "Risk data-quality issue",
            "summary": "; ".join(data_issues) + ".",
        })

    if calendar_review_needed:
        alerts.append({
            "severity": "INFO",
            "title": "Data-calendar coverage review",
            "summary": "The observations are not consecutive calendar days; confirm the risk-engine calendar covers weekends and holidays as intended.",
        })
    worst_scenario, worst_impact = min(stresses.items(), key=lambda item: item[1])
    if worst_impact < 0:
        alerts.append({
            "severity": "INFO",
            "title": "Most adverse stress scenario",
            "summary": f"{worst_scenario} produces the lowest reported impact: {worst_impact:,.0f}.",
        })

    if not alerts:
        alerts.append({
            "severity": "INFO",
            "title": "No rule-based alerts",
            "summary": "All monitored metrics are within the configured V11 thresholds.",
        })

    alerts.sort(key=lambda alert: SEVERITY_ORDER[alert["severity"]])
    action_required = sum(alert["severity"] != "INFO" for alert in alerts)
    return {
        "as_of_date": v8.get_current_risk()["date"],
        "action_required_count": action_required,
        "alerts": alerts,
        "thresholds": {
            "limit_utilisation_monitoring_pct": 60,
            "limit_utilisation_high_pct": 80,
            "limit_utilisation_critical_pct": 90,
            "var_movement_notable_pct": 10,
            "var_movement_material_pct": 20,
        },
    }


# Register exactly one new deterministic V11 agent function.
v8.TOOL_FUNCTIONS["get_risk_alerts"] = get_risk_alerts
v8.TOOL_DESCRIPTIONS["get_risk_alerts"] = (
    "Rule-based current alerts for VaR limits, material VaR movements, "
    "backtesting exceptions, data quality, and the most adverse stress scenario."
)
v9.VERSION = VERSION
v9.SYSTEM_INSTRUCTION += """

V11 alert control:
- get_risk_alerts reports transparent rules-based monitoring alerts.
- State the alert thresholds when they are material to your conclusion.
- Treat alerts as prompts for review, not proof of causality.
"""
v9.tools = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(name=name, description=description)
            for name, description in v8.TOOL_DESCRIPTIONS.items()
        ]
    )
]

ask_risk_agent = v9.ask_risk_agent


def main():
    print("\nMARKET RISK AI ASSISTANT — V11")
    print("Rule-based risk alerts and investigation memory are ready.")
    print("Type 'exit' to stop.\n")
    while True:
        question = input("You: ")
        if question.lower().strip() == "exit":
            print("Assistant: Goodbye.")
            break
        try:
            print("Assistant:")
            print(ask_risk_agent(question))
            print()
        except Exception as error:
            print(f"\nERROR:\n{error}\n")


if __name__ == "__main__":
    main()
