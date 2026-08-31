"""Market Risk AI V15: restored risk-manager pages with hierarchy allocation filters."""

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Market Risk AI | V15", page_icon=":material/monitoring:", layout="wide")

try:
    import market_risk_agent_v15 as v15
except Exception as error:
    st.error(f"The risk dashboard could not load its data or configuration: {error}")
    st.stop()


v13 = v15.v13
v12 = v15.v12
v11 = v15.v11
v8 = v15.v8
if "risk_agent_messages" not in st.session_state:
    st.session_state.risk_agent_messages = []


def amount(value):
    return f"{value:,.0f}"


def percentage(value):
    return f"{value:.1f}%"


def date_labels(frame):
    labelled = frame.copy()
    labelled["display_date"] = labelled["cob_date"].dt.strftime("%d/%m")
    return labelled


def display_amount_table(frame, amount_columns):
    formatted = frame.copy()
    for column in amount_columns:
        if column in formatted:
            formatted[column] = formatted[column].map(amount)
    st.dataframe(formatted, hide_index=True)


def alert_badge(severity):
    return {"CRITICAL": ":red-badge[Critical]", "HIGH": ":orange-badge[High]", "MEDIUM": ":yellow-badge[Monitor]", "INFO": ":blue-badge[Information]"}[severity]


df = v8.df.copy()
current_risk = v8.get_current_risk()
trend = v8.get_var_trend()
limit = v8.get_limit_analysis()
backtesting = v8.get_backtesting_analysis()
alert_summary = v11.get_risk_alerts()
risk_run = v12.get_risk_run_lineage()
lineage = risk_run["lineage"]
stress_evolution = v13.get_stress_evolution()
stress_frame, stress_metadata = v13.build_stress_evolution_frame()
portfolio_scope = v15.v14.get_portfolio_scope()
portfolio_ids = [row["portfolio_id"] for row in portfolio_scope["portfolios"]]

st.title("Market Risk AI")
st.caption(f"Validated demo risk run · Data as of {current_risk['date']} · V15")
nav, portfolio_control = st.columns([5, 2], vertical_alignment="bottom")
with nav:
    page = st.segmented_control(
        "Navigate",
        ["Overview", "VaR", "P&L", "Stress", "Controls & risk run", "Alerts", "Ask MR Agent"],
        default="Overview",
        required=True,
        width="stretch",
        label_visibility="collapsed",
        key="v14_navigation",
    )
with portfolio_control:
    selected_portfolio = st.selectbox("Portfolio", portfolio_ids, key="v14_portfolio")

portfolio_df = df.loc[df["portfolio_id"] == selected_portfolio].copy()
if portfolio_df.empty:
    st.error("The selected portfolio has no observations in the current run.")
    st.stop()

books, _ = v15.build_hierarchy()
hierarchy_columns = st.columns(3, vertical_alignment="bottom")
with hierarchy_columns[0]:
    selected_business_line = st.selectbox("Business line", ["All business lines"] + sorted(books["business_line"].unique()))
scoped_books = books if selected_business_line == "All business lines" else books.loc[books["business_line"] == selected_business_line]
with hierarchy_columns[1]:
    selected_desk = st.selectbox("Trading desk", ["All desks"] + sorted(scoped_books["trading_desk"].unique()))
scoped_books = scoped_books if selected_desk == "All desks" else scoped_books.loc[scoped_books["trading_desk"] == selected_desk]
with hierarchy_columns[2]:
    selected_book = st.selectbox("Book", ["All books"] + sorted(scoped_books["book_id"].unique()))
if selected_book != "All books":
    scoped_books = scoped_books.loc[scoped_books["book_id"] == selected_book]
allocation_weight = float(scoped_books["allocation_weight"].sum())
scope_label = " / ".join(value for value in [selected_business_line if selected_business_line != "All business lines" else None, selected_desk if selected_desk != "All desks" else None, selected_book if selected_book != "All books" else None] if value) or "Whole portfolio"
st.caption(f"Hierarchy scope: {scope_label} · synthetic allocation: {allocation_weight:.1%} of the aggregate risk run")
st.info("V15 hierarchy filters apply transparent synthetic allocations for exploration. They are not trade-level revaluation or additive VaR.", icon=":material/info:")

numeric_columns = portfolio_df.select_dtypes(include="number").columns
portfolio_df[numeric_columns] = portfolio_df[numeric_columns] * allocation_weight
for key in ("var_hist", "var_parametric", "var_monte_carlo", "var_10d_regulatory", "stressed_var", "expected_shortfall", "var_limit"):
    current_risk[key] *= allocation_weight
for key in ("current_var", "previous_var", "change", "10_day_average"):
    trend[key] *= allocation_weight
for key in ("current_var", "var_limit"):
    limit[key] *= allocation_weight
stress_frame = stress_frame.copy()
stress_numeric = [column for column in stress_frame.columns if column != "cob_date"]
stress_frame[stress_numeric] = stress_frame[stress_numeric] * allocation_weight

if page == "Overview":
    st.header("Overview")
    st.caption(f"Portfolio: {selected_portfolio} · {len(portfolio_df)} business-day observations")
    with st.container(horizontal=True):
        st.metric("Historical VaR (1 day, 99%)", amount(current_risk["var_hist"]), border=True)
        st.metric("Stressed VaR (SVaR)", amount(current_risk["stressed_var"]), border=True)
        st.metric("Expected shortfall (97.5%)", amount(current_risk["expected_shortfall"]), border=True)
        st.metric("Limit utilisation", percentage(current_risk["limit_utilisation"]), border=True)
    if alert_summary["action_required_count"]:
        st.warning(f"{alert_summary['action_required_count']} item(s) require review. See Alerts for detail.", icon=":material/warning:")
    with st.container(border=True):
        st.subheader("Current run")
        st.write(f"**{lineage.get('run_id', 'Unavailable')}** · {lineage.get('source_file', 'Unavailable')}")
        st.caption("The run ID is generated by the demo adapter because the source export has no supplied run ID.")

elif page == "VaR":
    st.header("VaR")
    with st.container(horizontal=True):
        st.metric("Historical VaR (1 day, 99%)", amount(current_risk["var_hist"]), percentage(trend["change_pct"]), border=True)
        st.metric("Stressed VaR (SVaR)", amount(current_risk["stressed_var"]), border=True)
        st.metric("Approved VaR limit", amount(limit["var_limit"]), border=True)
        st.metric("Limit utilisation", percentage(limit["utilisation_pct"]), border=True)
    with st.container(border=True):
        st.subheader("Historical VaR evolution")
        var_chart = date_labels(portfolio_df).set_index("display_date")[["var_1d_99_hist"]].rename(columns={"var_1d_99_hist": "Historical VaR"})
        st.line_chart(var_chart)
        st.caption(f"Latest movement: {amount(trend['change'])} ({percentage(trend['change_pct'])}) versus the previous business-day observation.")
    with st.container(border=True):
        st.subheader("Historical VaR attribution")
        attribution = (pd.Series(v8.get_var_attribution(), name="VaR contribution") * allocation_weight).sort_values(ascending=False)
        st.bar_chart(attribution)
        display_amount_table(attribution.rename_axis("Risk factor").reset_index(), ["VaR contribution"])

elif page == "P&L":
    st.header("P&L")
    pnl = {key: value * allocation_weight for key, value in v8.get_pnl_analysis().items()}
    with st.container(horizontal=True):
        st.metric("Actual P&L", amount(pnl["actual_pnl"]), border=True)
        st.metric("Hypothetical P&L", amount(pnl["hypothetical_pnl"]), border=True)
        st.metric("Clean P&L", amount(pnl["clean_pnl"]), border=True)
        st.metric("Unexplained P&L", amount(pnl["unexplained_pnl"]), border=True)
    with st.container(border=True):
        st.subheader("P&L evolution")
        pnl_chart = date_labels(portfolio_df).set_index("display_date")[["actual_pnl", "hypothetical_pnl", "clean_pnl", "unexplained_pnl"]]
        pnl_chart.columns = ["Actual P&L", "Hypothetical P&L", "Clean P&L", "Unexplained P&L"]
        st.line_chart(pnl_chart)
    with st.container(border=True):
        st.subheader("Current P&L explain drivers")
        driver_columns = [column for column in portfolio_df.columns if column.startswith("pnl_driver_")]
        drivers = portfolio_df.iloc[-1][driver_columns].rename(lambda column: column.replace("pnl_driver_", "").replace("_", " ").upper())
        st.bar_chart(drivers.sort_values())
        display_amount_table(drivers.rename_axis("Driver").rename("P&L impact").reset_index(), ["P&L impact"])
    with st.container(border=True):
        st.subheader("Backtesting")
        with st.container(horizontal=True):
            st.metric("250-day exceptions", backtesting["exception_count_250d"], border=True)
            st.metric("Hypothetical exception today", backtesting["hypothetical_exception"], border=True)
            st.metric("Actual exception today", backtesting["actual_exception"], border=True)
            st.metric("Traffic-light zone", backtesting["basel_traffic_light_zone"], border=True)

elif page == "Stress":
    st.header("Stress")
    st.caption("Risk-engine supplied stresses plus clearly labelled illustrative V13 proxy scenarios.")
    st.info(stress_evolution["usage_note"], icon=":material/info:")
    latest_stress = stress_frame.iloc[-1].drop(labels="cob_date").sort_values()
    worst_scenario, worst_impact = latest_stress.index[0], latest_stress.iloc[0]
    previous_stress = stress_frame.iloc[-2].drop(labels="cob_date")
    deterioration = (latest_stress - previous_stress).sort_values().iloc[0]
    with st.container(horizontal=True):
        st.metric("Most adverse scenario", worst_scenario, amount(worst_impact), border=True)
        st.metric("Largest day-on-day deterioration", amount(deterioration), border=True)
        st.metric("Scenarios tracked", len(latest_stress), border=True)
    with st.container(border=True):
        st.subheader("Stress evolution by scenario")
        scenario_names = [column for column in stress_frame.columns if column != "cob_date"]
        selected_scenarios = st.multiselect("Scenarios to display", scenario_names, default=scenario_names)
        if selected_scenarios:
            stress_chart = date_labels(stress_frame).set_index("display_date")[selected_scenarios]
            st.line_chart(stress_chart)
    with st.container(border=True):
        st.subheader("Current scenario impacts")
        stress_table = pd.DataFrame({
            "Scenario": latest_stress.index,
            "Current P&L impact": latest_stress.values,
            "Source": [stress_metadata[name]["source"] for name in latest_stress.index],
            "Scenario theme": [stress_metadata[name]["theme"] for name in latest_stress.index],
        })
        display_amount_table(stress_table, ["Current P&L impact"])

elif page == "Controls & risk run":
    st.header("Controls & risk run")
    weekday_rows = int((portfolio_df["cob_date"].dt.dayofweek < 5).sum())
    with st.container(horizontal=True):
        st.metric("Validation", risk_run["validation_status"], border=True)
        st.metric("Rows validated", lineage.get("row_count", 0), border=True)
        st.metric("Portfolio observations", len(portfolio_df), border=True)
        st.metric("Weekday observations", weekday_rows, border=True)
    with st.container(border=True):
        st.subheader("Run lineage")
        lineage_table = pd.DataFrame([
            ("Run ID", lineage.get("run_id")), ("Source", lineage.get("source_type")),
            ("Source file", lineage.get("source_file")), ("Fingerprint", lineage.get("data_fingerprint")),
            ("As-of date", pd.to_datetime(lineage.get("as_of_date")).strftime("%d/%m")),
        ], columns=["Field", "Value"])
        st.dataframe(lineage_table, hide_index=True)
    with st.container(border=True):
        st.subheader("Business-date controls")
        st.success("All observations in the current extract fall on Monday–Friday.", icon=":material/check_circle:")
        preview = date_labels(portfolio_df)[["display_date", "portfolio_id", "reporting_currency"]].rename(columns={"display_date": "COB date"})
        st.dataframe(preview, hide_index=True)
    with st.container(border=True):
        st.subheader("Data-quality checks")
        quality = pd.DataFrame([v8.validate_data()]).T.rename(columns={0: "Result"}).reset_index(names="Control")
        st.dataframe(quality, hide_index=True)

elif page == "Alerts":
    st.header("Alerts")
    st.caption("Transparent rules for limit utilisation, VaR movement, backtesting, data quality and stress results.")
    for alert in alert_summary["alerts"]:
        with st.container(border=True):
            st.markdown(f"{alert_badge(alert['severity'])}  **{alert['title']}**")
            st.write(alert["summary"])

else:
    st.header("Ask MR Agent")
    st.caption("The agent investigates deterministic risk results, stress evolution, run lineage and portfolio scope.")
    with st.container(border=True):
        selected_question = None
        if not st.session_state.risk_agent_messages:
            selected_question = st.pills("Suggested questions", ["How has stress evolved across scenarios?", "Which portfolios are included in this risk run?", "What are the main VaR and P&L risks today?"], label_visibility="collapsed")
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
                        answer = v15.ask_risk_agent(question)
                    except Exception as error:
                        status.update(label="Investigation could not be completed", state="error")
                        st.error(str(error), icon=":material/error:")
                    else:
                        status.update(label="Investigation complete", state="complete", expanded=False)
                        st.markdown(answer)
                        st.session_state.risk_agent_messages.append({"role": "assistant", "content": answer})
    with st.expander("Recent investigation memory", icon=":material/history:"):
        memory = v15.v9.get_recent_investigation_context()
        st.caption(memory["usage_note"])
        if memory["recent_investigations"]:
            for record in reversed(memory["recent_investigations"]):
                st.markdown(f"**{record['question']}**")
                st.caption(f"{record['timestamp_utc']} · tools: {', '.join(record['tools_used'])}")
        else:
            st.info("No completed investigations have been recorded for this data snapshot yet.", icon=":material/info:")
