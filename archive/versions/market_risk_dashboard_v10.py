"""Market Risk AI V10: Streamlit dashboard for risk-manager investigations."""

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Market Risk AI Dashboard | V10", page_icon="📈", layout="wide")

try:
    import market_risk_agent_v8 as v8
    import market_risk_agent_v9 as v9
except Exception as error:
    st.error(f"The risk dashboard could not load its data or configuration: {error}")
    st.stop()


def money(value):
    return f"{value:,.0f}"


def percentage(value):
    return f"{value:.1f}%"


def risk_status_colour(status):
    return {"LOW": "🟢", "MODERATE": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}.get(status, "⚪")


df = v8.df.copy()
current_risk = v8.get_current_risk()
trend = v8.get_var_trend()
limit = v8.get_limit_analysis()
backtesting = v8.get_backtesting_analysis()

st.title(" Market Risk AI Dashboard")
st.caption(f"V10 risk-manager dashboard · Risk-engine data as of {current_risk['date']}")

overview_tab, drivers_tab, controls_tab, agent_tab = st.tabs(
    ["Overview", "Risk Drivers", "Stress & Controls", "Ask the Risk Agent"]
)

with overview_tab:
    metrics = st.columns(4)
    metrics[0].metric("1-day Historical VaR (99%)", money(current_risk["var_hist"]))
    metrics[1].metric("Stressed VaR", money(current_risk["stressed_var"]))
    metrics[2].metric("Expected Shortfall (97.5%)", money(current_risk["expected_shortfall"]))
    metrics[3].metric(
        "Limit Utilisation",
        percentage(current_risk["limit_utilisation"]),
        delta=f"{risk_status_colour(limit['status'])} {limit['status']}",
        delta_color="off",
    )

    st.subheader("VaR trend")
    trend_chart = df.set_index("cob_date")[["var_1d_99_hist", "var_1d_99_param", "var_1d_99_mc"]]
    trend_chart.columns = ["Historical VaR", "Parametric VaR", "Monte Carlo VaR"]
    st.line_chart(trend_chart, use_container_width=True)
    st.caption(
        f"Historical VaR changed by {money(trend['change'])} "
        f"({percentage(trend['change_pct'])}) since the prior observation and is "
        f"{percentage(trend['vs_10_day_average_pct'])} versus the available-data average."
    )

    left_column, right_column = st.columns(2)
    with left_column:
        st.subheader("Daily actual P&L")
        pnl_chart = df.set_index("cob_date")[["actual_pnl"]].rename(columns={"actual_pnl": "Actual P&L"})
        st.bar_chart(pnl_chart, use_container_width=True)
    with right_column:
        st.subheader("Current P&L")
        pnl_frame = pd.DataFrame({"P&L": v8.get_pnl_analysis()}).rename_axis("Measure").reset_index()
        st.dataframe(pnl_frame, hide_index=True, use_container_width=True)

with drivers_tab:
    st.subheader("Historical VaR attribution")
    attribution_frame = pd.Series(v8.get_var_attribution(), name="VaR contribution").sort_values(ascending=False).to_frame()
    st.bar_chart(attribution_frame, use_container_width=True)
    st.dataframe(attribution_frame.rename_axis("Risk factor").reset_index(), hide_index=True, use_container_width=True)
    st.caption("Contributions are displayed exactly as supplied by the risk-engine data.")

with controls_tab:
    st.subheader(f"Limit monitoring: {risk_status_colour(limit['status'])} {limit['status']}")
    limit_columns = st.columns(3)
    limit_columns[0].metric("Current Historical VaR", money(limit["current_var"]))
    limit_columns[1].metric("Approved VaR Limit", money(limit["var_limit"]))
    limit_columns[2].metric("Utilisation", percentage(limit["utilisation_pct"]))

    st.subheader("Stress scenarios")
    stress_frame = pd.Series(v8.get_stress_analysis(), name="P&L impact").sort_values().rename_axis("Scenario").reset_index()
    st.dataframe(stress_frame, hide_index=True, use_container_width=True)

    st.subheader("Backtesting")
    backtest_columns = st.columns(3)
    backtest_columns[0].metric("250-day exceptions", backtesting["exception_count_250d"])
    backtest_columns[1].metric("Hypothetical exception today", backtesting["hypothetical_exception"])
    backtest_columns[2].metric("Basel traffic-light zone", backtesting["basel_traffic_light_zone"])

    with st.expander("Data-quality checks"):
        quality = pd.DataFrame([v8.validate_data()]).T.rename(columns={0: "Result"})
        st.dataframe(quality, use_container_width=True)

with agent_tab:
    st.subheader("Ask the Market Risk Agent")
    st.write("The agent plans an investigation, calls deterministic analytics tools, and records auditable follow-up context.")
    with st.form("risk_question_form"):
        question = st.text_area("Question", placeholder="What are the main risks today and should I be concerned?")
        submitted = st.form_submit_button("Analyse risk")

    if submitted:
        if not question.strip():
            st.warning("Enter a market-risk question before running the analysis.")
        else:
            with st.spinner("Planning and running the risk investigation..."):
                try:
                    answer = v9.ask_risk_agent(question.strip())
                except Exception as error:
                    st.error(f"The agent could not complete the investigation: {error}")
                else:
                    st.success("Investigation complete")
                    st.markdown(answer)

    with st.expander("Recent investigation memory"):
        memory = v9.get_recent_investigation_context()
        st.caption(memory["usage_note"])
        if memory["recent_investigations"]:
            for record in reversed(memory["recent_investigations"]):
                st.markdown(f"**{record['question']}**")
                st.caption(f"{record['timestamp_utc']} · tools: {', '.join(record['tools_used'])}")
        else:
            st.info("No completed investigations have been recorded for this data snapshot yet.")
