"""Market Risk AI V11: risk-manager dashboard with deterministic alerts."""

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Market Risk AI | V11",
    page_icon=":material/monitoring:",
    layout="wide",
)

try:
    import market_risk_agent_v11 as v11
except Exception as error:
    st.error(f"The risk dashboard could not load its data or configuration: {error}")
    st.stop()


v8 = v11.v8
if "risk_agent_messages" not in st.session_state:
    st.session_state.risk_agent_messages = []


def money(value):
    return f"{value:,.0f}"


def percentage(value):
    return f"{value:.1f}%"


def severity_badge(severity):
    return {
        "CRITICAL": ":red-badge[Critical]",
        "HIGH": ":orange-badge[High]",
        "MEDIUM": ":yellow-badge[Monitor]",
        "INFO": ":blue-badge[Information]",
    }[severity]


df = v8.df.copy()
current_risk = v8.get_current_risk()
trend = v8.get_var_trend()
limit = v8.get_limit_analysis()
backtesting = v8.get_backtesting_analysis()
alert_summary = v11.get_risk_alerts()

st.title("Market Risk AI")
st.caption(f"Risk-manager dashboard · Data as of {current_risk['date']} · V11")

if alert_summary["action_required_count"]:
    st.warning(
        f"{alert_summary['action_required_count']} item(s) require review. Open the Alerts tab for the rule-based detail.",
        icon=":material/warning:",
    )
else:
    st.success("No rule-based monitoring threshold is currently breached.", icon=":material/check_circle:")

overview_tab, alerts_tab, drivers_tab, controls_tab, agent_tab = st.tabs(
    ["Overview", "Alerts", "Risk drivers", "Stress & controls", "Ask the Risk Agent"]
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
        st.caption(
            f"Historical VaR changed by {money(trend['change'])} ({percentage(trend['change_pct'])}) "
            f"versus the prior observation."
        )

    left_column, right_column = st.columns(2)
    with left_column:
        with st.container(border=True):
            st.subheader("Daily actual P&L")
            pnl_chart = df.set_index("cob_date")[["actual_pnl"]].rename(columns={"actual_pnl": "Actual P&L"})
            st.bar_chart(pnl_chart)
    with right_column:
        with st.container(border=True):
            st.subheader("Current P&L")
            pnl_frame = pd.DataFrame({"P&L": v8.get_pnl_analysis()}).rename_axis("Measure").reset_index()
            st.dataframe(pnl_frame, hide_index=True)

with alerts_tab:
    st.subheader("Risk alerts")
    st.caption("Rules monitor limit utilisation, VaR movement, backtesting, data quality, and stress scenarios.")
    for alert in alert_summary["alerts"]:
        with st.container(border=True):
            st.markdown(f"{severity_badge(alert['severity'])}  **{alert['title']}**")
            st.write(alert["summary"])
    with st.expander("V11 alert thresholds", icon=":material/tune:"):
        threshold_frame = pd.DataFrame(
            alert_summary["thresholds"].items(), columns=["Rule", "Threshold"]
        )
        st.dataframe(threshold_frame, hide_index=True)

with drivers_tab:
    with st.container(border=True):
        st.subheader("Historical VaR attribution")
        attribution_frame = pd.Series(v8.get_var_attribution(), name="VaR contribution").sort_values(ascending=False).to_frame()
        st.bar_chart(attribution_frame)
        st.dataframe(attribution_frame.rename_axis("Risk factor").reset_index(), hide_index=True)
        st.caption("Contributions are displayed exactly as supplied by the risk-engine data.")

with controls_tab:
    with st.container(border=True):
        st.subheader("Limit monitoring")
        limit_columns = st.columns(3)
        limit_columns[0].metric("Current historical VaR", money(limit["current_var"]))
        limit_columns[1].metric("Approved VaR limit", money(limit["var_limit"]))
        limit_columns[2].metric("Utilisation", percentage(limit["utilisation_pct"]))

    left_column, right_column = st.columns(2)
    with left_column:
        with st.container(border=True):
            st.subheader("Stress scenarios")
            stress_frame = pd.Series(v8.get_stress_analysis(), name="P&L impact").sort_values().rename_axis("Scenario").reset_index()
            st.dataframe(stress_frame, hide_index=True)
    with right_column:
        with st.container(border=True):
            st.subheader("Backtesting")
            st.metric("250-day exceptions", backtesting["exception_count_250d"])
            st.metric("Hypothetical exception today", backtesting["hypothetical_exception"])
            st.metric("Basel traffic-light zone", backtesting["basel_traffic_light_zone"])

    with st.expander("Data-quality checks", icon=":material/fact_check:"):
        quality = pd.DataFrame([v8.validate_data()]).T.rename(columns={0: "Result"})
        st.dataframe(quality)

with agent_tab:
    with st.container(border=True):
        st.subheader("Ask the Risk Agent")
        st.caption("The agent plans an investigation, uses deterministic evidence, and records auditable follow-up context.")

        if not st.session_state.risk_agent_messages:
            suggestions = [
                "What are the main risks today?",
                "Are there any limit or backtesting concerns?",
                "Which risk factors drive VaR?",
            ]
            selected_question = st.pills(
                "Suggested questions",
                suggestions,
                label_visibility="collapsed",
                key="risk_question_suggestion",
            )
        else:
            selected_question = None

        for message in st.session_state.risk_agent_messages:
            avatar = ":material/analytics:" if message["role"] == "assistant" else None
            with st.chat_message(message["role"], avatar=avatar):
                st.markdown(message["content"])

        typed_question = st.chat_input(
            "Ask about the current market-risk position",
            key="risk_agent_input",
            submit_mode="disable",
        )
        question = typed_question or selected_question

        if question:
            st.session_state.risk_agent_messages.append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)
            with st.chat_message("assistant", avatar=":material/analytics:"):
                with st.status("Running the risk investigation...", expanded=True) as status:
                    try:
                        answer = v11.ask_risk_agent(question)
                    except Exception as error:
                        status.update(label="Investigation could not be completed", state="error")
                        st.error(str(error), icon=":material/error:")
                    else:
                        status.update(label="Investigation complete", state="complete", expanded=False)
                        st.markdown(answer)
                        st.session_state.risk_agent_messages.append({"role": "assistant", "content": answer})

    with st.expander("Recent investigation memory", icon=":material/history:"):
        memory = v11.v9.get_recent_investigation_context()
        st.caption(memory["usage_note"])
        if memory["recent_investigations"]:
            for record in reversed(memory["recent_investigations"]):
                st.markdown(f"**{record['question']}**")
                st.caption(f"{record['timestamp_utc']} · tools: {', '.join(record['tools_used'])}")
        else:
            st.info("No completed investigations have been recorded for this data snapshot yet.", icon=":material/info:")
