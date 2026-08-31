"""Market Risk AI V12: dashboard with a generic validated risk-run interface."""

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Market Risk AI | V12", page_icon=":material/account_tree:", layout="wide")

try:
    import market_risk_agent_v12 as v12
except Exception as error:
    st.error(f"The risk dashboard could not load its data or configuration: {error}")
    st.stop()

v11 = v12.v11
v8 = v12.v8
if "risk_agent_messages" not in st.session_state:
    st.session_state.risk_agent_messages = []


def money(value):
    return f"{value:,.0f}"


def percentage(value):
    return f"{value:.1f}%"


def severity_badge(severity):
    return {"CRITICAL": ":red-badge[Critical]", "HIGH": ":orange-badge[High]", "MEDIUM": ":yellow-badge[Monitor]", "INFO": ":blue-badge[Information]"}[severity]


df = v8.df.copy()
current_risk = v8.get_current_risk()
trend = v8.get_var_trend()
limit = v8.get_limit_analysis()
backtesting = v8.get_backtesting_analysis()
alert_summary = v11.get_risk_alerts()
risk_run = v12.get_risk_run_lineage()
lineage = risk_run["lineage"]

st.title("Market Risk AI")
st.caption(f"Risk-manager cockpit · Data as of {current_risk['date']} · V12")
if risk_run["validation_status"] == "VALIDATED":
    st.success(f"{lineage['run_id']} passed the V12 demo ingestion controls.", icon=":material/verified:")
else:
    st.error("The current risk run failed V12 ingestion controls. Review the Risk run tab.", icon=":material/error:")
if alert_summary["action_required_count"]:
    st.warning(f"{alert_summary['action_required_count']} item(s) require review.", icon=":material/warning:")

overview_tab, run_tab, alerts_tab, drivers_tab, controls_tab, agent_tab = st.tabs(
    ["Overview", "Risk run", "Alerts", "Risk drivers", "Stress & controls", "Ask the Risk Agent"]
)

with overview_tab:
    with st.container(horizontal=True):
        st.metric("1-day historical VaR (99%)", money(current_risk["var_hist"]), border=True)
        st.metric("Stressed VaR", money(current_risk["stressed_var"]), border=True)
        st.metric("Expected shortfall (97.5%)", money(current_risk["expected_shortfall"]), border=True)
        st.metric("Limit utilisation", percentage(current_risk["limit_utilisation"]), border=True)
    with st.container(border=True):
        st.subheader("VaR trend")
        trend_chart = df.set_index("cob_date")[["var_1d_99_hist", "var_1d_99_param", "var_1d_99_mc"]]
        trend_chart.columns = ["Historical VaR", "Parametric VaR", "Monte Carlo VaR"]
        st.line_chart(trend_chart)
        st.caption(f"Historical VaR changed by {money(trend['change'])} ({percentage(trend['change_pct'])}) versus the prior observation.")
    with st.container(border=True):
        st.subheader("Daily actual P&L")
        st.bar_chart(df.set_index("cob_date")[["actual_pnl"]].rename(columns={"actual_pnl": "Actual P&L"}))

with run_tab:
    st.subheader("Risk-run ingestion and lineage")
    st.caption("Generic V12 demo interface — it does not describe any institution's production data flow.")
    badge = ":green-badge[Validated]" if risk_run["validation_status"] == "VALIDATED" else ":red-badge[Rejected]"
    st.markdown(badge)
    with st.container(horizontal=True):
        st.metric("Run ID", lineage.get("run_id", "Unavailable"), border=True)
        st.metric("As-of date", lineage.get("as_of_date", "Unavailable"), border=True)
        st.metric("Portfolios", lineage.get("portfolio_count", 0), border=True)
        st.metric("Rows validated", lineage.get("row_count", 0), border=True)
    with st.container(border=True):
        st.subheader("Lineage")
        lineage_frame = pd.DataFrame([
            ("Source", lineage.get("source_type")), ("Source file", lineage.get("source_file")),
            ("Data fingerprint", lineage.get("data_fingerprint")), ("First observation", lineage.get("first_observation_date")),
            ("Reporting currencies", ", ".join(lineage.get("reporting_currencies", []))), ("Ingested at (UTC)", lineage.get("ingested_at_utc")),
        ], columns=["Field", "Value"])
        st.dataframe(lineage_frame, hide_index=True)
        st.caption(lineage.get("run_id_note", ""))
        st.caption(lineage.get("approval_note", ""))
    if risk_run["errors"]:
        st.error("\n".join(risk_run["errors"]))
    if risk_run["warnings"]:
        st.warning("\n".join(risk_run["warnings"]))
    with st.expander("Curated risk-run preview", icon=":material/table_view:"):
        preview_columns = ["cob_date", "portfolio_id", "reporting_currency", "var_1d_99_hist", "stressed_var_1d_99", "expected_shortfall_97_5", "actual_pnl"]
        st.dataframe(df[preview_columns].tail(10), hide_index=True, column_config={
            "cob_date": st.column_config.DateColumn("COB date"),
            "var_1d_99_hist": st.column_config.NumberColumn("Historical VaR", format="%,.0f"),
            "stressed_var_1d_99": st.column_config.NumberColumn("Stressed VaR", format="%,.0f"),
            "expected_shortfall_97_5": st.column_config.NumberColumn("Expected shortfall", format="%,.0f"),
            "actual_pnl": st.column_config.NumberColumn("Actual P&L", format="%,.0f"),
        })

with alerts_tab:
    st.subheader("Risk alerts")
    st.caption("Rules monitor limits, VaR movement, backtesting, data quality, and stress scenarios.")
    for alert in alert_summary["alerts"]:
        with st.container(border=True):
            st.markdown(f"{severity_badge(alert['severity'])}  **{alert['title']}**")
            st.write(alert["summary"])

with drivers_tab:
    with st.container(border=True):
        st.subheader("Historical VaR attribution")
        attribution = pd.Series(v8.get_var_attribution(), name="VaR contribution").sort_values(ascending=False)
        st.bar_chart(attribution)
        st.dataframe(attribution.rename_axis("Risk factor").reset_index(), hide_index=True)
        st.caption("Contributions are displayed exactly as supplied by the risk-engine data.")

with controls_tab:
    with st.container(horizontal=True):
        st.metric("Current historical VaR", money(limit["current_var"]), border=True)
        st.metric("Approved VaR limit", money(limit["var_limit"]), border=True)
        st.metric("Utilisation", percentage(limit["utilisation_pct"]), border=True)
        st.metric("250-day exceptions", backtesting["exception_count_250d"], border=True)
    left_column, right_column = st.columns(2)
    with left_column:
        with st.container(border=True):
            st.subheader("Stress scenarios")
            stresses = pd.Series(v8.get_stress_analysis(), name="P&L impact").sort_values().rename_axis("Scenario").reset_index()
            st.dataframe(stresses, hide_index=True)
    with right_column:
        with st.container(border=True):
            st.subheader("Backtesting")
            st.metric("Hypothetical exception today", backtesting["hypothetical_exception"])
            st.metric("Basel traffic-light zone", backtesting["basel_traffic_light_zone"])

with agent_tab:
    with st.container(border=True):
        st.subheader("Ask the Risk Agent")
        st.caption("The agent investigates deterministic results and can now retrieve V12 run lineage.")
        selected_question = None
        if not st.session_state.risk_agent_messages:
            selected_question = st.pills("Suggested questions", ["What is the status and scope of this risk run?", "What are the main risks today?", "Are there any limit or backtesting concerns?"], label_visibility="collapsed")
        for message in st.session_state.risk_agent_messages:
            avatar = ":material/analytics:" if message["role"] == "assistant" else None
            with st.chat_message(message["role"], avatar=avatar):
                st.markdown(message["content"])
        typed_question = st.chat_input("Ask about the current market-risk position", submit_mode="disable")
        question = typed_question or selected_question
        if question:
            st.session_state.risk_agent_messages.append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)
            with st.chat_message("assistant", avatar=":material/analytics:"):
                with st.status("Running the risk investigation...", expanded=True) as status:
                    try:
                        answer = v12.ask_risk_agent(question)
                    except Exception as error:
                        status.update(label="Investigation could not be completed", state="error")
                        st.error(str(error), icon=":material/error:")
                    else:
                        status.update(label="Investigation complete", state="complete", expanded=False)
                        st.markdown(answer)
                        st.session_state.risk_agent_messages.append({"role": "assistant", "content": answer})
    with st.expander("Recent investigation memory", icon=":material/history:"):
        memory = v12.v9.get_recent_investigation_context()
        st.caption(memory["usage_note"])
        if memory["recent_investigations"]:
            for record in reversed(memory["recent_investigations"]):
                st.markdown(f"**{record['question']}**")
                st.caption(f"{record['timestamp_utc']} · tools: {', '.join(record['tools_used'])}")
        else:
            st.info("No completed investigations have been recorded for this data snapshot yet.", icon=":material/info:")
