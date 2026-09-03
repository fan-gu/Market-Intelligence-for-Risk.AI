"""MIRAI V30: Market Intelligence for Risk AI bank-wide dashboard."""

from html import escape

import altair as alt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="MIRAI | Market Intelligence for Risk AI | V30", page_icon=":material/monitoring:", layout="wide")

try:
    import market_risk_agent_v29 as v29
except Exception as error:
    st.error(f"The risk dashboard could not load its data or configuration: {error}")
    st.stop()


v13 = v29.v13
v12 = v29.v12
v11 = v29.v11
v8 = v29.v8
# Keep the presentation layer resilient when Streamlit reruns against a
# previously cached V29 module. The same convention is used by governance:
# SVaR limit = 1.5 x the approved Historical VaR limit.
SVAR_LIMIT_MULTIPLIER = 1.5
st.session_state.setdefault("risk_agent_messages", [])
st.session_state.setdefault("v29_active_page", "Dashboard")


def select_dashboard_page():
    st.session_state.v29_active_page = st.session_state.v29_navigation


def select_agent_page():
    st.session_state.v29_active_page = "Ask MR Agent"


def select_scenario_agent_page(scenario_context):
    st.session_state.v29_scenario_context = scenario_context
    st.session_state.v29_pending_scenario_question = (
        "Assess this saved Scenario Lab result. Explain the principal risk contributions, "
        "the loss-limit impact, the important modelling limitations and the actions a market "
        "risk manager should consider."
    )
    st.session_state.v29_active_page = "Ask MR Agent"


def clear_scenario_agent_context():
    st.session_state.pop("v29_scenario_context", None)
    st.session_state.pop("v29_pending_scenario_question", None)


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


def build_waterfall_chart(
    factor_contributions,
    total_label,
    total_value,
    bridge_label=None,
    bridge_value=None,
):
    """Build a cumulative factor bridge with an optional unexplained step."""
    rows = []
    running = 0.0
    for contribution in factor_contributions:
        label, value = contribution[:2]
        contribution_type = contribution[2] if len(contribution) > 2 else "Risk factor"
        start = running
        running += float(value)
        rows.append({
            "Step": label,
            "start": start,
            "end": running,
            "low": min(start, running),
            "high": max(start, running),
            "display_value": float(value),
            "Type": contribution_type,
        })
    if bridge_label is not None and bridge_value is not None:
        bridge_end = running + float(bridge_value)
        rows.append({
            "Step": bridge_label,
            "start": running,
            "end": bridge_end,
            "low": min(running, bridge_end),
            "high": max(running, bridge_end),
            "display_value": float(bridge_value),
            "Type": "Unexplained",
        })
    rows.append({
        "Step": total_label,
        "start": 0.0,
        "end": float(total_value),
        "low": min(0.0, float(total_value)),
        "high": max(0.0, float(total_value)),
        "display_value": float(total_value),
        "Type": "Total",
    })
    waterfall = pd.DataFrame(rows)
    order = waterfall["Step"].tolist()
    base = alt.Chart(waterfall).encode(
        x=alt.X("Step:N", title=None, sort=order, axis=alt.Axis(labelAngle=-25)),
        tooltip=[
            alt.Tooltip("Step:N"),
            alt.Tooltip("display_value:Q", title="Contribution", format=",.0f"),
            alt.Tooltip("end:Q", title="Running total", format=",.0f"),
            alt.Tooltip("Type:N"),
        ],
    )
    bars = base.mark_bar(size=48).encode(
        y=alt.Y("low:Q", title="EUR"),
        y2="high:Q",
        color=alt.Color(
            "Type:N",
            title=None,
            scale=alt.Scale(
                domain=["Risk factor", "Diversification", "Unexplained", "Total"],
                range=["#60A5FA", "#FBBF24", "#F87171", "#34D399"],
            ),
        ),
    )
    zero = alt.Chart(pd.DataFrame({"zero": [0]})).mark_rule(
        color="#94A3B8", strokeWidth=1
    ).encode(y="zero:Q")
    positive_labels = (
        base.transform_filter(alt.datum.display_value >= 0)
        .mark_text(dy=-9, fontWeight="bold", color="#E2E8F0")
        .encode(y="high:Q", text=alt.Text("display_value:Q", format=",.0f"))
    )
    negative_labels = (
        base.transform_filter(alt.datum.display_value < 0)
        .mark_text(dy=13, fontWeight="bold", color="#E2E8F0")
        .encode(y="low:Q", text=alt.Text("display_value:Q", format=",.0f"))
    )
    return (zero + bars + positive_labels + negative_labels).properties(height=390)


def build_horizontal_waterfall_chart(factor_contributions, total_label, total_value):
    """Build a horizontal cumulative VaR-movement bridge."""
    rows, running = [], 0.0
    for label, value, *rest in factor_contributions:
        item_type = rest[0] if rest else "Risk factor"
        start = running
        running += float(value)
        rows.append({"Step": label, "start": start, "end": running, "low": min(start, running), "high": max(start, running), "display_value": float(value), "Type": item_type})
    rows.append({"Step": total_label, "start": 0.0, "end": float(total_value), "low": min(0.0, float(total_value)), "high": max(0.0, float(total_value)), "display_value": float(total_value), "Type": "Total"})
    waterfall = pd.DataFrame(rows)
    order = waterfall["Step"].tolist()
    base = alt.Chart(waterfall).encode(y=alt.Y("Step:N", sort=order, title=None), tooltip=[alt.Tooltip("Step:N"), alt.Tooltip("display_value:Q", title="Contribution", format=",.0f"), alt.Tooltip("end:Q", title="Running total", format=",.0f"), alt.Tooltip("Type:N")])
    bars = base.mark_bar(size=32).encode(x=alt.X("low:Q", title="VaR change (EUR)"), x2="high:Q", color=alt.Color("Type:N", title=None, scale=alt.Scale(domain=["Risk factor","Diversification","Total"], range=["#60A5FA","#FBBF24","#34D399"])))
    labels = base.mark_text(align="left", dx=5, color="#E2E8F0").encode(x="high:Q", text=alt.Text("display_value:Q", format=",.0f"))
    zero = alt.Chart(pd.DataFrame({"zero":[0]})).mark_rule(color="#94A3B8").encode(x="zero:Q")
    return (zero + bars + labels).properties(height=390)

df = v8.df.copy()
current_risk = v8.get_current_risk()
trend = v8.get_var_trend()
limit = v8.get_limit_analysis()
backtesting = v8.get_backtesting_analysis()
alert_summary = v11.get_risk_alerts()
risk_run = v12.get_risk_run_lineage()
lineage = risk_run["lineage"]
stress_evolution = v29.get_stress_evolution()

portfolio_scope = v29.v14.get_portfolio_scope()
portfolio_ids = [row["portfolio_id"] for row in portfolio_scope["portfolios"]]

available_as_of_dates = sorted(df["cob_date"].dt.date.unique(), reverse=True)
books, _ = v29.v15.build_hierarchy()

header_background = "#0F172A"
header_border = "#334155"
st.html(
    f"""
    <style>
    html, body, [data-testid="stAppViewContainer"], .stApp {{
        background: #0F172A !important;
        color-scheme: dark;
    }}
    [data-testid="stMainBlockContainer"] {{
        overflow: visible !important;
    }}
    div[data-testid="stElementContainer"]:has(.st-key-sticky_header),
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.st-key-sticky_header),
    .st-key-sticky_header {{
        position: sticky !important;
        top: 2.875rem !important;
        z-index: 9999 !important;
        overflow: visible !important;
        background: {header_background} !important;
    }}
    .st-key-sticky_header {{
        padding: 0.35rem 0 0.45rem 0;
        border-bottom: 1px solid {header_border};
        box-shadow: 0 6px 14px rgba(0, 0, 0, 0.24);
        isolation: isolate;
    }}
    .st-key-sticky_header > div {{
        background: {header_background} !important;
    }}
    .st-key-sticky_header h1 {{
        font-size: 3.25rem !important;
        line-height: 1 !important;
        letter-spacing: -0.04em !important;
        white-space: nowrap;
    }}
    </style>
    """
)

with st.container(key="sticky_header"):
    header_controls = st.columns([1.25, 1.05, 1.05, 1.05, 1.35], vertical_alignment="bottom")
    with header_controls[0]:
        st.button(
            "M.I.R.A.I.",
            icon=":material/auto_awesome:",
            type="primary",
            width="stretch",
            on_click=select_agent_page,
            key="v29_header_agent_button",
        )
    with header_controls[1]:
        selected_business_line = st.selectbox(
            "Business line",
            ["All business lines"] + sorted(books["business_line"].unique()),
            key="v29_business_line",
            label_visibility="collapsed",
        )
    scoped_books = (
        books
        if selected_business_line == "All business lines"
        else books.loc[books["business_line"] == selected_business_line]
    )
    with header_controls[2]:
        selected_desk = st.selectbox(
            "Trading desk",
            ["All desks"] + sorted(scoped_books["trading_desk"].unique()),
            key="v29_trading_desk",
            label_visibility="collapsed",
        )
    scoped_books = (
        scoped_books
        if selected_desk == "All desks"
        else scoped_books.loc[scoped_books["trading_desk"] == selected_desk]
    )
    with header_controls[3]:
        selected_book = st.selectbox(
            "Book",
            ["All books"] + sorted(scoped_books["book_id"].unique()),
            key="v29_book",
            label_visibility="collapsed",
        )
    if selected_book != "All books":
        scoped_books = scoped_books.loc[scoped_books["book_id"] == selected_book]
    with header_controls[4]:
        selected_as_of_date = pd.Timestamp(st.date_input(
            "AsOf",
            value=pd.Timestamp(max(available_as_of_dates)).date(),
            min_value=pd.Timestamp(min(available_as_of_dates)).date(),
            max_value=pd.Timestamp(max(available_as_of_dates)).date(),
            format="DD/MM/YYYY",
            key="v30_as_of_calendar",
        ))

    st.segmented_control(
        "Navigate",
        ["Dashboard", "VaR", "P&L", "Sensitivities", "Stress", "Scenario Lab", "Controls"],
        default="Dashboard",
        required=True,
        width="stretch",
        label_visibility="collapsed",
        key="v29_navigation",
        on_change=select_dashboard_page,
    )
page = st.session_state.v29_active_page
portfolio_df = df.loc[df["cob_date"] <= pd.Timestamp(selected_as_of_date)].copy()
if portfolio_df.empty:
    st.error("There are no observations on or before the selected as-of date.")
    st.stop()
stress_frame, stress_metadata = v29.build_supplied_stress_frame(selected_as_of_date)

allocation_weight = float(scoped_books["allocation_weight"].sum())
scope_label = " / ".join(
    value
    for value in [
        selected_business_line if selected_business_line != "All business lines" else None,
        selected_desk if selected_desk != "All desks" else None,
        selected_book if selected_book != "All books" else None,
    ]
    if value
) or "Whole portfolio"
header_limit_rows = v29.evaluate_all_limits()["limits"]
header_stress_rows = v29.get_stress_limit_monitor(selected_as_of_date)["scenarios"]
header_breaches = (
    [row["metric"] for row in header_limit_rows if row["status"] == "BREACH"]
    + [row["scenario"] for row in header_stress_rows if row["status"] == "BREACH"]
)
header_warnings = (
    [row["metric"] for row in header_limit_rows if row["status"] == "WARNING"]
    + [row["scenario"] for row in header_stress_rows if row["status"] == "WARNING"]
)
if header_breaches:
    st.error("Current limit breaches: " + " · ".join(dict.fromkeys(header_breaches)), icon=":material/error:")
if not header_breaches and not header_warnings:
    st.success("All current governed risk measures are below warning thresholds.", icon=":material/check_circle:")
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

if page == "Dashboard":
    st.header("Dashboard")
    selected_row = portfolio_df.sort_values("cob_date").iloc[-1]
    selected_var = float(selected_row["var_1d_99_hist"])
    selected_svar = float(selected_row["stressed_var_1d_99"])
    selected_es = float(selected_row["expected_shortfall_97_5"])
    selected_apl = float(selected_row["actual_pnl"])

    with st.container(horizontal=True):
        st.metric("Historical VaR", amount(selected_var), border=True)
        st.metric("SVaR", amount(selected_svar), border=True)
        st.metric("Expected shortfall", amount(selected_es), border=True)
        st.metric("Actual P&L", amount(selected_apl), border=True)

    dashboard_chart_row = st.columns(2, gap="large")
    with dashboard_chart_row[0]:
        with st.container(border=True):
            st.subheader("Daily P&L attribution")
            pnl_factors = {
                "Rates": "pnl_driver_ir_dv01", "FX": "pnl_driver_fx_delta",
                "Vega": "pnl_driver_vega", "Gamma": "pnl_driver_gamma",
                "Theta": "pnl_driver_theta", "Credit": "pnl_driver_cs01",
                "Cross-gamma": "pnl_driver_cross_gamma",
            }
            pnl_attribution = pd.DataFrame({"Factor": list(pnl_factors), "P&L": [float(selected_row[column]) for column in pnl_factors.values()]})
            pnl_attribution = pnl_attribution.sort_values("P&L")
            st.altair_chart(
                alt.Chart(pnl_attribution).mark_bar().encode(
                    x=alt.X("P&L:Q", title="Daily P&L (EUR)", axis=alt.Axis(format=",.0f")),
                    y=alt.Y("Factor:N", sort=None, title=None),
                    color=alt.condition(alt.datum["P&L"] < 0, alt.value("#F87171"), alt.value("#34D399")),
                    tooltip=[alt.Tooltip("Factor:N"), alt.Tooltip("P&L:Q", format=",.0f")],
                ).properties(height=300),
                key="dashboard_daily_pnl_attribution",
            )
    with dashboard_chart_row[1]:
        with st.container(border=True):
            st.subheader("VaR and SVaR evolution")
            var_history = portfolio_df[["cob_date", "var_1d_99_hist", "stressed_var_1d_99", "var_limit_amount"]].copy()
            var_history["svar_limit_amount"] = var_history["var_limit_amount"] * SVAR_LIMIT_MULTIPLIER
            var_history = var_history.melt("cob_date", var_name="series", value_name="amount")
            var_history["series"] = var_history["series"].replace({"var_1d_99_hist":"Historical VaR", "stressed_var_1d_99":"SVaR", "var_limit_amount":"VaR limit", "svar_limit_amount":"SVaR limit"})
            st.altair_chart(
                alt.Chart(var_history).mark_line().encode(
                    x=alt.X("cob_date:T", title="Business date", axis=alt.Axis(format="%b", tickCount=12)),
                    y=alt.Y("amount:Q", title="EUR", scale=alt.Scale(zero=False)), color=alt.Color("series:N", title="Series"),
                    tooltip=[alt.Tooltip("cob_date:T", title="Date", format="%d/%m/%Y"), alt.Tooltip("series:N"), alt.Tooltip("amount:Q", title="EUR", format=",.0f")],
                ).properties(height=300), key="dashboard_var_evolution",
            )

    risk_chart_row = st.columns(2, gap="large")
    with risk_chart_row[0]:
        with st.container(border=True):
            st.subheader("EUR IR volatility surface")
            # Keep the Dashboard visual independent of a newly-added agent API.
            # This avoids stale-module errors on managed Streamlit deployments.
            sensitivity_frame = pd.DataFrame(v29.get_market_sensitivities()["sensitivities"])
            eur_vega = float(
                sensitivity_frame.loc[
                    (sensitivity_frame["measure"] == "Vega")
                    & (sensitivity_frame["currency"] == "EUR"),
                    "value",
                ].abs().sum()
            )
            surface_expiries = ["1M", "3M", "6M", "1Y", "2Y", "5Y"]
            surface_tenors = ["1Y", "2Y", "5Y", "10Y", "30Y"]
            surface_rows = [
                {
                    "option_expiry": expiry,
                    "underlying_tenor": tenor,
                    "value": eur_vega * expiry_weight * tenor_weight,
                }
                for expiry, expiry_weight in zip(surface_expiries, [0.08, 0.12, 0.16, 0.20, 0.20, 0.24])
                for tenor, tenor_weight in zip(surface_tenors, [0.08, 0.12, 0.21, 0.29, 0.30])
            ]
            dashboard_surface = {
                "surface": surface_rows,
                "option_expiries": surface_expiries,
                "underlying_tenors": surface_tenors,
            }
            vega_surface = pd.DataFrame(dashboard_surface["surface"])
            expiries, underlyings = dashboard_surface["option_expiries"], dashboard_surface["underlying_tenors"]
            surface_grid = vega_surface.pivot(index="option_expiry", columns="underlying_tenor", values="value").reindex(index=expiries, columns=underlyings).fillna(0.0)
            surface_figure = go.Figure(data=[go.Surface(z=surface_grid.values, x=underlyings, y=expiries, colorscale="Blues", colorbar={"title":"EUR / vol point"}, hovertemplate="Option expiry: %{y}<br>Underlying tenor: %{x}<br>Vega: %{z:,.0f}<extra></extra>")])
            surface_figure.update_layout(height=330, margin={"l":0,"r":0,"t":10,"b":0}, scene={"xaxis_title":"Underlying swap tenor", "yaxis_title":"Option expiry", "zaxis_title":"IR Vega", "bgcolor":"#0F172A", "xaxis":{"backgroundcolor":"#0F172A"}, "yaxis":{"backgroundcolor":"#0F172A"}, "zaxis":{"backgroundcolor":"#0F172A"}}, paper_bgcolor="#0F172A", font={"color":"#E5E7EB"})
            st.plotly_chart(surface_figure, width="stretch", key="dashboard_eur_ir_vol_surface")
    with risk_chart_row[1]:
        with st.container(border=True):
            st.subheader("Largest current stress losses")
            latest_stress = stress_frame.sort_values("cob_date").iloc[-1]
            stress_summary = pd.DataFrame({"Scenario": stress_numeric, "Stressed P&L": [float(latest_stress[item]) for item in stress_numeric]}).sort_values("Stressed P&L").head(6)
            st.altair_chart(alt.Chart(stress_summary).mark_bar().encode(x=alt.X("Stressed P&L:Q", title="EUR", axis=alt.Axis(format=",.0f")), y=alt.Y("Scenario:N", sort=None, title=None), color=alt.condition(alt.datum["Stressed P&L"] < 0, alt.value("#F87171"), alt.value("#34D399")), tooltip=[alt.Tooltip("Scenario:N"), alt.Tooltip("Stressed P&L:Q", format=",.0f")]).properties(height=300), key="dashboard_stress_losses")

    with st.container(border=True):
        st.subheader("Attention points")
        attention = []
        attention.extend({"Severity": row["severity"], "Source": "Risk alerts", "Finding": f"{row['title']}: {row['summary']}"} for row in alert_summary.get("alerts", []))
        stress_monitor = v29.get_stress_limit_monitor(selected_as_of_date)
        attention.extend({"Severity": row["status"], "Source": "Stress limits", "Finding": f"{row['scenario']}: {row['consumption_pct']:.1f}% consumed"} for row in stress_monitor["scenarios"] if row["status"] in {"WARNING", "BREACH"})
        if attention:
            severity_order = {"BREACH":0,"CRITICAL":0,"WARNING":1,"HIGH":1,"MEDIUM":2,"INFO":3}
            attention_frame = pd.DataFrame(attention); attention_frame["_severity_order"] = attention_frame["Severity"].map(severity_order).fillna(9)
            st.dataframe(attention_frame.sort_values(["_severity_order","Source","Finding"]).drop(columns="_severity_order"), hide_index=True, width="stretch")
        else:
            st.success("No current attention points are above configured thresholds.", icon=":material/check_circle:")

elif page == "VaR":
    st.header("VaR")
    selected_raw_risk = v8.df.loc[v8.df["cob_date"] <= pd.Timestamp(selected_as_of_date)].sort_values("cob_date").iloc[-1]
    selected_hist_var = float(selected_raw_risk["var_1d_99_hist"]) * allocation_weight
    selected_stressed_var = float(selected_raw_risk["stressed_var_1d_99"]) * allocation_weight
    selected_var_limit = float(selected_raw_risk["var_limit_amount"]) * allocation_weight
    selected_svar_limit = selected_var_limit * SVAR_LIMIT_MULTIPLIER
    var_metrics = st.columns(6, gap="small")
    metric_values = [
        ("HVaR", amount(selected_hist_var)),
        ("HVaR limit", amount(selected_var_limit)),
        ("HVaR consumption", percentage(0 if selected_var_limit == 0 else selected_hist_var / selected_var_limit * 100)),
        ("SVaR", amount(selected_stressed_var)),
        ("SVaR limit", amount(selected_svar_limit)),
        ("SVaR consumption", percentage(0 if selected_svar_limit == 0 else selected_stressed_var / selected_svar_limit * 100)),
    ]
    for block, (label, value) in zip(var_metrics, metric_values):
        with block:
            st.metric(label, value, border=True)

    history = v8.df.loc[v8.df["cob_date"] <= pd.Timestamp(selected_as_of_date)].sort_values("cob_date").copy()
    def movement(column, days):
        latest = history.iloc[-1]
        prior = history.loc[history["cob_date"] <= latest["cob_date"] - pd.Timedelta(days=days)]
        if prior.empty: return None
        reference = prior.iloc[-1]
        value = 0.0 if float(reference[column]) == 0 else (float(latest[column]) / float(reference[column]) - 1.0) * 100.0
        return value, pd.Timestamp(reference["cob_date"]).strftime("%d/%m")
    with st.container(border=True):
        st.subheader("VaR movement")
        movement_blocks = st.columns(2, gap="large")
        for block, label, column, periods in [(movement_blocks[0], "HVaR change", "var_1d_99_hist", [("Daily",1),("Weekly",7),("Monthly",30)]), (movement_blocks[1], "SVaR change", "stressed_var_1d_99", [("Weekly",7),("Monthly",30)])]:
            with block.container(border=True):
                st.markdown(f"**{label}**")
                with st.container(horizontal=True):
                    for period, days in periods:
                        result = movement(column, days)
                        if result is None: st.metric(period, "N/A", border=True)
                        else: st.metric(period, f"{result[0]:+.1f}%", f"vs {result[1]}", border=True)

    with st.container(border=True):
        st.subheader("HVaR evolution")
        hvar_history = history[["cob_date", "var_1d_99_hist", "var_limit_amount"]].copy()
        hvar_history[["var_1d_99_hist", "var_limit_amount"]] *= allocation_weight
        hvar_line = alt.Chart(hvar_history).mark_line(color="#60A5FA", strokeWidth=2.4).encode(x=alt.X("cob_date:T", title="Month", axis=alt.Axis(format="%b", tickCount=12)), y=alt.Y("var_1d_99_hist:Q", title="HVaR (EUR)", scale=alt.Scale(zero=False)), tooltip=[alt.Tooltip("cob_date:T", title="Date", format="%d/%m/%Y"), alt.Tooltip("var_1d_99_hist:Q", title="HVaR", format=",.0f")])
        hvar_limit = alt.Chart(hvar_history).mark_rule(color="#F59E0B", strokeDash=[6,4], strokeWidth=2).encode(y=alt.Y("var_limit_amount:Q"), tooltip=[alt.Tooltip("var_limit_amount:Q", title="HVaR limit", format=",.0f")])
        st.altair_chart((hvar_line + hvar_limit).properties(height=340), key="hvar_evolution")

    with st.container(border=True):
        st.subheader("VaR movement attribution")
        attribution_horizon = st.segmented_control("Attribution horizon", ["Daily","Weekly","Monthly"], default="Daily", required=True, key="v29_var_attribution_horizon")
        var_attribution = v29.get_var_change_attribution(selected_as_of_date, horizon=attribution_horizon, hierarchy_level=scope_label)
        if var_attribution["status"] == "AVAILABLE":
            factors = [("Diversification effect" if item["factor"] == "Diversification" else item["factor"], item["change"] * allocation_weight, "Diversification" if item["factor"] == "Diversification" else "Risk factor") for item in var_attribution["factor_changes"]]
            st.altair_chart(build_horizontal_waterfall_chart(factors, total_label="Total VaR change", total_value=var_attribution["total_change"] * allocation_weight), key="var_movement_attribution")
            st.caption(f"{attribution_horizon} movement from {pd.Timestamp(var_attribution['reference_date']).strftime('%d/%m')} to {pd.Timestamp(var_attribution['as_of_date']).strftime('%d/%m')}. {var_attribution['usage_note']}")
        else: st.info(f"Insufficient history for {attribution_horizon.lower()} VaR movement attribution.", icon=":material/info:")

    with st.container(border=True):
        st.subheader("Historical VaR attribution")
        attribution = (pd.Series(v8.get_var_attribution(), name="VaR contribution") * allocation_weight).sort_values(ascending=False).rename_axis("Risk factor").reset_index()
        st.altair_chart(alt.Chart(attribution).mark_bar().encode(x=alt.X("VaR contribution:Q", title="VaR contribution (EUR)", axis=alt.Axis(format=",.0f")), y=alt.Y("Risk factor:N", sort="-x", title=None), color=alt.Color("Risk factor:N", legend=None), tooltip=[alt.Tooltip("Risk factor:N"), alt.Tooltip("VaR contribution:Q", format=",.0f")]).properties(height=360), key="historical_var_attribution")

elif page == "P&L":
    st.header("P&L attribution")
    st.caption("Official FRTB terminology: Actual P&L (APL), Hypothetical P&L (HPL), and Risk-theoretical P&L (RTPL).")

    pla_history = v29.build_pla_demo_history()
    pla_history = pla_history.loc[pla_history["cob_date"] <= pd.Timestamp(selected_as_of_date)].copy()
    pnl_value_columns = [
        "actual_pnl", "hypothetical_pnl", "risk_theoretical_pnl",
        "apl_hpl_difference", "hpl_rtpl_difference", "explained_pnl", "unexplained_pnl",
        *v29.DRIVER_COLUMNS,
    ]
    full_desk_weights = books.groupby("trading_desk")["allocation_weight"].sum()
    scope_desk_weights = scoped_books.groupby("trading_desk")["allocation_weight"].sum()
    scope_scalars = (scope_desk_weights / full_desk_weights.reindex(scope_desk_weights.index)).to_dict()
    scoped_pla_history = pla_history.loc[
        pla_history["trading_desk"].isin(scope_scalars)
    ].copy()
    scoped_pla_history["scope_scalar"] = scoped_pla_history["trading_desk"].map(scope_scalars)
    scoped_pla_history[pnl_value_columns] = scoped_pla_history[pnl_value_columns].mul(
        scoped_pla_history["scope_scalar"], axis=0
    )
    desk_history = scoped_pla_history.groupby("cob_date", as_index=False)[pnl_value_columns].sum()
    latest_pnl = desk_history.iloc[-1]
    pla_correlation = float(
        desk_history["hypothetical_pnl"].rank(method="average").corr(
            desk_history["risk_theoretical_pnl"].rank(method="average")
        )
    )
    pla_ks = v29.v19._empirical_ks_statistic(
        desk_history["hypothetical_pnl"], desk_history["risk_theoretical_pnl"]
    )
    pla_zone = v29.v19._pla_zone(pla_correlation, pla_ks)
    pla_consequence = {
        "GREEN": "PLA green zone: no PLA surcharge from this test.",
        "AMBER": "PLA amber zone: the desk remains within IMA scope but a capital surcharge applies.",
        "RED": "PLA red zone: the desk is ineligible for IMA and falls back to the Standardised Approach.",
    }[pla_zone]
    desk_pla = {
        "business_line": selected_business_line,
        "trading_desk": scope_label,
        "observations": len(desk_history),
        "spearman_correlation": pla_correlation,
        "ks_statistic": pla_ks,
        "pla_zone": pla_zone,
        "regulatory_consequence": pla_consequence,
        "latest_hpl": float(latest_pnl["hypothetical_pnl"]),
        "latest_rtpl": float(latest_pnl["risk_theoretical_pnl"]),
        "latest_pla_residual": float(latest_pnl["hpl_rtpl_difference"]),
    }
    pla_results = pd.DataFrame([desk_pla])
    unexplained_ratio = (
        0.0
        if float(latest_pnl["actual_pnl"]) == 0
        else abs(float(latest_pnl["unexplained_pnl"])) / abs(float(latest_pnl["actual_pnl"])) * 100.0
    )
    desk_pnl_alert = {
        "unexplained_to_apl_pct": unexplained_ratio,
        "status": "ALERT" if unexplained_ratio > 20.0 else "OK",
    }
    st.caption(f"All P&L and PLA charts follow the top hierarchy perimeter: {scope_label}.")

    with st.container(horizontal=True):
        st.metric("Actual P&L (APL)", amount(latest_pnl["actual_pnl"]), border=True)
        st.metric("Hypothetical P&L (HPL)", amount(latest_pnl["hypothetical_pnl"]), border=True)
        st.metric("Risk-theoretical P&L (RTPL)", amount(latest_pnl["risk_theoretical_pnl"]), border=True)
        st.metric("APL − HPL difference", amount(latest_pnl["apl_hpl_difference"]), border=True)
        st.metric("HPL − RTPL PLA residual", amount(latest_pnl["hpl_rtpl_difference"]), border=True)

    with st.container(border=True):
        st.subheader("P&L levels and residuals")
        recent_window = desk_history.tail(22).copy()
        recent_window["Business date"] = recent_window["cob_date"]
        date_order = None

        level_data = recent_window[
            ["Business date", "actual_pnl", "hypothetical_pnl", "risk_theoretical_pnl"]
        ].melt("Business date", var_name="series", value_name="value")
        level_data["series"] = level_data["series"].map({
            "actual_pnl": "APL",
            "hypothetical_pnl": "HPL",
            "risk_theoretical_pnl": "RTPL",
        })
        residual_data = recent_window[
            ["Business date", "apl_hpl_difference", "hpl_rtpl_difference"]
        ].melt("Business date", var_name="series", value_name="value")
        residual_data["series"] = residual_data["series"].map({
            "apl_hpl_difference": "APL − HPL",
            "hpl_rtpl_difference": "HPL − RTPL",
        })
        residual_bars = (
            alt.Chart(residual_data)
            .mark_bar(opacity=0.32, size=9)
            .encode(
                x=alt.X("Business date:T", title="Month", axis=alt.Axis(format="%b", tickCount=12)),
                xOffset=alt.XOffset("series:N", sort=["APL − HPL", "HPL − RTPL"]),
                y=alt.Y("value:Q", title="Residual (EUR)", axis=alt.Axis(orient="right"), scale=alt.Scale(zero=True)),
                color=alt.Color(
                    "series:N",
                    title="Residual bars",
                    scale=alt.Scale(domain=["APL − HPL", "HPL − RTPL"], range=["#E07A5F", "#3D5A80"]),
                ),
                tooltip=[
                    alt.Tooltip("Business date:N", title="Date"),
                    alt.Tooltip("series:N", title="Residual"),
                    alt.Tooltip("value:Q", title="Value", format=",.0f"),
                ],
            )
        )
        pnl_lines = (
            alt.Chart(level_data)
            .mark_line(strokeWidth=2.5)
            .encode(
                x=alt.X("Business date:T", title="Month", axis=alt.Axis(format="%b", tickCount=12)),
                y=alt.Y("value:Q", title="P&L level (EUR)", scale=alt.Scale(zero=False)),
                color=alt.Color(
                    "series:N",
                    title="P&L lines",
                    scale=alt.Scale(domain=["APL", "HPL", "RTPL"], range=["#2F6BFF", "#22A06B", "#8B5CF6"]),
                ),
                tooltip=[
                    alt.Tooltip("Business date:N", title="Date"),
                    alt.Tooltip("series:N", title="P&L"),
                    alt.Tooltip("value:Q", title="Value", format=",.0f"),
                ],
            )
        )
        combined_pnl_chart = (
            alt.layer(residual_bars, pnl_lines)
            .resolve_scale(y="independent", color="independent")
            .properties(height=430)
        )
        st.altair_chart(combined_pnl_chart)
        st.caption(
            "APL, HPL and RTPL are lines on the left axis. APL − HPL and HPL − RTPL are translucent bars "
            "on the right axis. The full 260-business-day history is shown with monthly labels."
        )
    with st.container(border=True):
        st.subheader("Risk-model P&L explain")
        with st.container(horizontal=True):
            st.metric("Explained P&L", amount(latest_pnl["explained_pnl"]), border=True)
            st.metric("Driver unexplained P&L", amount(latest_pnl["unexplained_pnl"]), border=True)
            st.metric("PLA residual (HPL − RTPL)", amount(latest_pnl["hpl_rtpl_difference"]), border=True)
            st.metric("Unexplained / |APL|", percentage(desk_pnl_alert["unexplained_to_apl_pct"]), border=True)
        if desk_pnl_alert["status"] == "ALERT":
            st.error(
                f"Unexplained P&L is {desk_pnl_alert['unexplained_to_apl_pct']:.1f}% of |APL|, above the 20% threshold.",
                icon=":material/error:",
            )
        else:
            st.success("Unexplained P&L is within the 20% of |APL| threshold.", icon=":material/check_circle:")
        explain_rows = pd.DataFrame(
            [{"Factor": column, "P&L": float(latest_pnl[column])} for column in v29.DRIVER_COLUMNS]
            + [{"Factor": "Unexplained P&L", "P&L": float(latest_pnl["unexplained_pnl"])}]
        )
        explain_rows["Factor"] = explain_rows["Factor"].replace({"Gamma and cross-gamma": "Gamma / cross-gamma"})
        explain_rows = explain_rows.sort_values("P&L")
        explain_bars = alt.Chart(explain_rows).mark_bar().encode(
            x=alt.X("P&L:Q", title="P&L contribution (EUR)", axis=alt.Axis(format=",.0f")),
            y=alt.Y("Factor:N", sort=None, title=None),
            color=alt.Color("Factor:N", title="P&L factor", legend=alt.Legend(orient="bottom")),
            tooltip=[alt.Tooltip("Factor:N"), alt.Tooltip("P&L:Q", format=",.0f")],
        )
        explain_labels = explain_bars.mark_text(align="left", dx=4, color="#E5E7EB").encode(text=alt.Text("P&L:Q", format=",.0f"))
        st.altair_chart((explain_bars + explain_labels).properties(height=380), key="risk_model_pnl_explain")
        st.caption("Each driver, including lifecycle effects and unexplained P&L, is shown separately. HPL minus RTPL remains the PLA residual above.")
    with st.container(border=True):
        st.subheader("FRTB P&L Attribution test")
        st.caption(
            "IMA means Internal Models Approach: supervisory permission to use approved internal market-risk models "
            "for regulatory capital. IMA-eligible means a nominated trading desk remains qualified through ongoing "
            "desk-level PLA and backtesting requirements; a green PLA result alone is not supervisory approval."
        )
        with st.container(horizontal=True):
            st.metric("PLA zone", desk_pla["pla_zone"], border=True)
            st.metric("Spearman correlation", f"{desk_pla['spearman_correlation']:.3f}", border=True)
            st.metric("KS statistic", f"{desk_pla['ks_statistic']:.3f}", border=True)
            st.metric("Observations", int(desk_pla["observations"]), border=True)

        if desk_pla["pla_zone"] == "RED":
            st.error(desk_pla["regulatory_consequence"], icon=":material/error:")
        elif desk_pla["pla_zone"] == "AMBER":
            st.warning(desk_pla["regulatory_consequence"], icon=":material/warning:")
        else:
            st.success(desk_pla["regulatory_consequence"], icon=":material/check_circle:")

        st.caption(
            "Green: Spearman > 0.80 and KS < 0.09 · "
            "Red: Spearman < 0.70 or KS > 0.12 · Otherwise amber."
        )
        pla_scatter_data = desk_history[["hypothetical_pnl", "risk_theoretical_pnl", "cob_date"]].copy()
        domain_min = float(pla_scatter_data[["hypothetical_pnl", "risk_theoretical_pnl"]].min().min())
        domain_max = float(pla_scatter_data[["hypothetical_pnl", "risk_theoretical_pnl"]].max().max())
        scatter = (
            alt.Chart(pla_scatter_data)
            .mark_circle(size=45, opacity=0.55)
            .encode(
                x=alt.X("hypothetical_pnl:Q", title="Hypothetical P&L (HPL)", scale=alt.Scale(domain=[domain_min, domain_max])),
                y=alt.Y("risk_theoretical_pnl:Q", title="Risk-theoretical P&L (RTPL)", scale=alt.Scale(domain=[domain_min, domain_max])),
                tooltip=[
                    alt.Tooltip("cob_date:T", title="Date", format="%d/%m/%Y"),
                    alt.Tooltip("hypothetical_pnl:Q", title="HPL", format=",.0f"),
                    alt.Tooltip("risk_theoretical_pnl:Q", title="RTPL", format=",.0f"),
                ],
            )
        )
        diagonal_data = pd.DataFrame({"HPL": [domain_min, domain_max], "RTPL": [domain_min, domain_max]})
        diagonal = alt.Chart(diagonal_data).mark_line(strokeDash=[5, 5], color="#808080").encode(
            x=alt.X("HPL:Q", scale=alt.Scale(domain=[domain_min, domain_max])),
            y=alt.Y("RTPL:Q", scale=alt.Scale(domain=[domain_min, domain_max])),
        )
        st.altair_chart(scatter + diagonal)
        st.caption("Points close to the diagonal indicate close agreement between HPL and RTPL.")

    with st.container(border=True):
        st.subheader("PLA status across trading desks")
        st.dataframe(
            pla_results,
            hide_index=True,
            column_order=[
                "business_line",
                "trading_desk",
                "observations",
                "spearman_correlation",
                "ks_statistic",
                "pla_zone",
                "regulatory_consequence",
                "latest_pla_residual",
            ],
            column_config={
                "business_line": "Business line",
                "trading_desk": "Trading desk",
                "observations": "Observations",
                "spearman_correlation": st.column_config.NumberColumn("Spearman", format="%.3f"),
                "ks_statistic": st.column_config.NumberColumn("KS", format="%.3f"),
                "pla_zone": "PLA zone",
                "regulatory_consequence": "Consequence",
                "latest_pla_residual": st.column_config.NumberColumn("Latest HPL − RTPL", format="%.0f"),
            },
        )

    with st.container(border=True):
        st.subheader("Backtesting")
        st.caption("Backtesting compares VaR with APL and HPL. RTPL is used for PLA, not backtesting.")
        with st.container(horizontal=True):
            st.metric("250-day exceptions", backtesting["exception_count_250d"], border=True)
            st.metric("Hypothetical exception today", backtesting["hypothetical_exception"], border=True)
            st.metric("Actual exception today", backtesting["actual_exception"], border=True)
            st.metric("Traffic-light zone", backtesting["basel_traffic_light_zone"], border=True)

elif page == "Sensitivities":
    st.header("Sensitivities")
    sensitivities = v29.get_market_sensitivities()
    sensitivity_frame = pd.DataFrame(sensitivities["sensitivities"])
    sensitivity_frame["value"] = sensitivity_frame["value"] * allocation_weight

    selected_currencies = st.multiselect(
        "Rates and Theta currencies",
        sensitivities["currencies"],
        default=sensitivities["currencies"],
        key="v29_sensi_currencies",
    )
    if not selected_currencies:
        st.warning("Select at least one currency to display sensitivities.")
        st.stop()

    rates_frame = sensitivity_frame.loc[
        (sensitivity_frame["risk_class"] == "Rates")
        & sensitivity_frame["currency"].isin(selected_currencies)
    ].copy()
    fx_frame = sensitivity_frame.loc[sensitivity_frame["risk_class"] == "FX"].copy()
    theta_frame = sensitivity_frame.loc[
        (sensitivity_frame["measure"] == "Theta")
        & sensitivity_frame["currency"].isin(selected_currencies)
    ].copy()

    dv01 = rates_frame.loc[rates_frame["measure"] == "IR Delta (DV01)", "value"]
    gamma = rates_frame.loc[rates_frame["measure"] == "IR Gamma", "value"]
    vega = rates_frame.loc[rates_frame["measure"] == "Vega", "value"]
    with st.container(horizontal=True):
        st.metric("Net Delta (EUR / bp)", amount(dv01.sum()), border=True)
        st.metric("Gross Delta (EUR / bp)", amount(dv01.abs().sum()), border=True)
        st.metric("IR Gamma (EUR / bp^2)", amount(gamma.sum()), border=True)
        st.metric("IR Vega (EUR / vol point)", amount(vega.sum()), border=True)
        st.metric("FX Delta (EUR / 1% spot)", amount(fx_frame["value"].abs().sum()), border=True)
        st.metric("Theta (EUR / day)", amount(theta_frame["value"].sum()), border=True)

    currency_domain = ["EUR", "USD", "JPY", "GBP", "CHF", "AUD", "HKD", "CNY"]
    currency_range = ["#2F6BFF", "#E07A5F", "#22A06B", "#8B5CF6", "#60A5FA", "#FB7185", "#F59E0B", "#14B8A6"]

    with st.container(border=True):
        st.subheader("IR Delta by curve and tenor (EUR / bp)")
        delta_result = v29.get_delta_curve_tenor_summary(selected_currencies)
        tenor_order = delta_result["tenors"]
        delta_table = pd.DataFrame(delta_result["rows"])
        scaled_columns = tenor_order + ["net_delta", "gross_delta"]
        delta_table[scaled_columns] = delta_table[scaled_columns] * allocation_weight

        controlled_mask = delta_table["net_limit"].notna()
        delta_table.loc[controlled_mask, "net_pct"] = (
            delta_table.loc[controlled_mask, "net_delta"].abs()
            / delta_table.loc[controlled_mask, "net_limit"]
            * 100.0
        )
        delta_table.loc[controlled_mask, "gross_pct"] = (
            delta_table.loc[controlled_mask, "gross_delta"]
            / delta_table.loc[controlled_mask, "gross_limit"]
            * 100.0
        )

        delta_table["curve_display"] = delta_table.apply(
            lambda row: (
                str(row["curve"])
                if row["row_type"] == "Currency subtotal"
                else f'{row["curve_type"]} | {row["curve"]}'
            ),
            axis=1,
        )

        delta_display_columns = (
            ["currency", "curve_display"]
            + tenor_order
            + [
                "net_delta", "net_limit", "net_pct",
                "gross_delta", "gross_limit", "gross_pct",
            ]
        )
        delta_headers = {
            "currency": "Currency",
            "curve_display": "Curve",
            **{tenor: tenor for tenor in tenor_order},
            "net_delta": "Net Delta",
            "net_limit": "Limit",
            "net_pct": "%",
            "gross_delta": "Gross Delta",
            "gross_limit": "Limit",
            "gross_pct": "%",
        }
        percentage_columns = {"net_pct", "gross_pct"}
        text_columns = {"currency", "curve_display"}

        def format_delta_cell(column, value):
            if pd.isna(value) or value == "":
                return ""
            if column in text_columns:
                return escape(str(value))
            if column in percentage_columns:
                return f"{float(value):.1f}%"
            return f"{float(value):,.0f}"

        delta_html_rows = []
        for delta_row in delta_table.to_dict("records"):
            row_class = "currency-subtotal" if delta_row["row_type"] == "Currency subtotal" else "curve-row"
            cells = "".join(
                f"<td>{format_delta_cell(column, delta_row[column])}</td>"
                for column in delta_display_columns
            )
            delta_html_rows.append(f'<tr class="{row_class}">{cells}</tr>')
            if delta_row["row_type"] == "Currency subtotal":
                delta_html_rows.append(
                    f'<tr class="currency-gap"><td colspan="{len(delta_display_columns)}"></td></tr>'
                )

        delta_header_html = "".join(
            f"<th>{escape(delta_headers[column])}</th>"
            for column in delta_display_columns
        )
        delta_table_html = f"""
        <style>
            .delta-risk-wrap {{
                max-height: 610px;
                overflow-y: auto;
                overflow-x: hidden;
                border: 1px solid #334155;
                border-radius: 7px;
            }}
            .delta-risk-table {{
                width: 100%;
                min-width: 0;
                table-layout: fixed;
                border-collapse: separate;
                border-spacing: 0;
                color: #E5E7EB;
                font-family: Inter, Arial, sans-serif;
                font-size: 0.67rem;
            }}
            .delta-risk-table th {{
                position: sticky;
                top: 0;
                z-index: 2;
                padding: 5px 3px;
                background: #1E293B;
                border-bottom: 1px solid #475569;
                text-align: right;
                white-space: nowrap;
            }}
            .delta-risk-table td {{
                padding: 5px 3px;
                border-bottom: 1px solid #263449;
                background: #111827;
                text-align: right;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .delta-risk-table th:nth-child(-n+2),
            .delta-risk-table td:nth-child(-n+2) {{ text-align: left; }}
            .delta-risk-table th:nth-child(1),
            .delta-risk-table td:nth-child(1) {{ width: 4%; }}
            .delta-risk-table th:nth-child(2),
            .delta-risk-table td:nth-child(2) {{ width: 10%; }}
            .delta-risk-table tr.currency-subtotal td {{
                background: #24324A;
                border-top: 1px solid #60A5FA;
                font-weight: 700;
            }}
            .delta-risk-table tr.currency-gap td {{
                height: 14px;
                padding: 0;
                border: 0;
                background: #0F172A;
            }}
        </style>
        <div class="delta-risk-wrap">
            <table class="delta-risk-table">
                <thead><tr>{delta_header_html}</tr></thead>
                <tbody>{''.join(delta_html_rows)}</tbody>
            </table>
        </div>
        """
        st.html(delta_table_html)
        st.caption(delta_result["usage_note"])

    with st.container(border=True):
        st.subheader("IR Gamma by currency (EUR / bp^2)")
        gamma_table = (
            rates_frame.loc[rates_frame["measure"] == "IR Gamma"]
            .groupby("currency", as_index=False)["value"]
            .sum()
            .rename(columns={"currency": "Currency", "value": "IR Gamma"})
        )
        gamma_columns = st.columns([1.65, 1], gap="medium", vertical_alignment="center")
        with gamma_columns[0]:
            st.altair_chart(
                alt.Chart(gamma_table)
                .mark_bar(size=38)
                .encode(
                    x=alt.X("Currency:N", sort=currency_domain),
                    y=alt.Y("IR Gamma:Q", title="EUR / bp^2", scale=alt.Scale(zero=True)),
                    color=alt.Color(
                        "Currency:N",
                        scale=alt.Scale(domain=currency_domain, range=currency_range),
                        legend=None,
                    ),
                    tooltip=["Currency:N", alt.Tooltip("IR Gamma:Q", format=",.0f")],
                )
                .properties(height=205)
            )
        with gamma_columns[1]:
            st.dataframe(
                gamma_table,
                hide_index=True,
                height=245,
                column_config={
                    "Currency": st.column_config.TextColumn(pinned=True),
                    "IR Gamma": st.column_config.NumberColumn(format="%.0f"),
                },
            )
        st.caption(
            "IR Gamma is the signed sum across all curve and tenor nodes for each currency. "
            "It is informational and has no limit or consumption."
        )

    with st.container(border=True):
        st.subheader("IR Vega surfaces by currency (EUR / vol point)")
        surface_result = v29.get_ir_vega_surface(selected_currencies)
        surface_frame = pd.DataFrame(surface_result["surface"])
        surface_frame["value"] = surface_frame["value"] * allocation_weight
        currency_surface = (
            surface_frame.groupby(
                ["currency", "option_expiry", "underlying_tenor"],
                as_index=False,
            )["value"]
            .sum()
        )
        surface_order = [
            currency for currency in currency_domain if currency in selected_currencies
        ]

        for row_start in range(0, len(surface_order), 4):
            surface_columns = st.columns(4, gap="small")
            for offset, currency in enumerate(surface_order[row_start:row_start + 4]):
                with surface_columns[offset]:
                    with st.container(border=True):
                        st.markdown(f"**{currency}**")
                        currency_data = currency_surface.loc[
                            currency_surface["currency"] == currency
                        ].copy()
                        currency_scale = max(float(currency_data["value"].abs().max()), 1.0)
                        cells = (
                            alt.Chart(currency_data)
                            .mark_rect(cornerRadius=4)
                            .encode(
                                x=alt.X(
                                    "underlying_tenor:N",
                                    title=None,
                                    sort=surface_result["underlying_tenors"],
                                    axis=alt.Axis(labelAngle=0),
                                ),
                                y=alt.Y(
                                    "option_expiry:N",
                                    title=None,
                                    sort=surface_result["option_expiries"],
                                ),
                                color=alt.Color(
                                    "value:Q",
                                    title=None,
                                    scale=alt.Scale(
                                        scheme="redblue",
                                        domain=[-currency_scale, currency_scale],
                                        domainMid=0,
                                    ),
                                    legend=None,
                                ),
                                tooltip=[
                                    alt.Tooltip("currency:N", title="Currency"),
                                    alt.Tooltip("option_expiry:N", title="Option expiry"),
                                    alt.Tooltip("underlying_tenor:N", title="Swap tenor"),
                                    alt.Tooltip("value:Q", title="IR Vega", format=",.0f"),
                                ],
                            )
                            .properties(height=155)
                        )
                        labels = (
                            alt.Chart(currency_data)
                            .mark_text(
                                font="Arial",
                                fontSize=13,
                                fontWeight=700,
                                color="#F8FAFC",
                                stroke="#0F172A",
                                strokeWidth=1.6,
                            )
                            .encode(
                                x=alt.X(
                                    "underlying_tenor:N",
                                    sort=surface_result["underlying_tenors"],
                                ),
                                y=alt.Y(
                                    "option_expiry:N",
                                    sort=surface_result["option_expiries"],
                                ),
                                text=alt.Text("value:Q", format=",.0f"),
                            )
                        )
                        st.altair_chart(cells + labels, width="stretch")
        st.caption(
            "Each currency has its own 2 x 2 option-expiry by underlying-swap-tenor matrix. "
            "Each matrix uses a local symmetric color scale so all four cells remain legible. "
            "The V29 prototype preserves each currency's source Vega; production feeds should provide native surface nodes."
        )

    lower_charts = st.columns(2)
    with lower_charts[0]:
        with st.container(border=True, height="stretch"):
            st.subheader("FX Delta (EUR / 1% spot)")
            fx_chart = (
                alt.Chart(fx_frame)
                .mark_bar()
                .encode(
                    x=alt.X("curve:N", title="FX pair", sort=None),
                    y=alt.Y("value:Q", title="EUR / 1% spot", scale=alt.Scale(zero=True)),
                    color=alt.Color("currency:N", title="FX pair"),
                    tooltip=[
                        alt.Tooltip("curve:N", title="FX pair"),
                        alt.Tooltip("value:Q", title="FX Delta", format=",.0f"),
                    ],
                )
                .properties(height=290)
            )
            st.altair_chart(fx_chart)
    with lower_charts[1]:
        with st.container(border=True, height="stretch"):
            st.subheader("Theta (EUR / day)")
            theta_chart = (
                alt.Chart(theta_frame)
                .mark_bar()
                .encode(
                    x=alt.X("currency:N", title="Currency", sort=currency_domain),
                    y=alt.Y("value:Q", title="EUR / day", scale=alt.Scale(zero=True)),
                    color=alt.Color(
                        "currency:N",
                        title="Currency",
                        scale=alt.Scale(domain=currency_domain, range=currency_range),
                    ),
                    tooltip=[
                        alt.Tooltip("currency:N", title="Currency"),
                        alt.Tooltip("value:Q", title="Theta", format=",.0f"),
                    ],
                )
                .properties(height=290)
            )
            st.altair_chart(theta_chart)

    st.caption(
        "IR Delta is DV01 per +1 bp move at each curve-tenor node. Net and Gross Delta controls "
        "are evaluated separately by currency. IR Vega is displayed as separate currency surfaces. "
        "FX Delta is measured per +1% move in the quoted pair."
    )
elif page == "Scenario Lab":
    st.header("Scenario Lab")
    scenario_specification = v29.get_scenario_lab_specification()
    st.info(
        "Invent a market shock and watch the supplied sensitivities react instantly. "
        "This is a sensitivity approximation, not an official risk-engine revaluation.",
        icon=":material/science:",
    )

    scenario_layout = st.columns([1, 1.45], gap="large", vertical_alignment="top")
    with scenario_layout[0]:
        with st.container(border=True):
            st.subheader("Build a scenario")
            severity_label = st.segmented_control(
                "Severity",
                list(scenario_specification["severity_options"]),
                default="Adverse (1x)",
                required=True,
                width="stretch",
                key="v29_scenario_severity",
            )
            st.caption("Extreme doubles rate, FX and volatility shocks. The selected time horizon is unchanged.")
            rate_currency = st.selectbox(
                "Rates and volatility currency",
                ["All currencies"] + scenario_specification["rate_currencies"],
                index=1,
                key="v29_scenario_rate_currency",
            )
            curve_family = st.selectbox(
                "Curve family",
                ["All curve families"] + scenario_specification["curve_families"],
                key="v29_scenario_curve_family",
            )
            parallel_shift_bp = st.slider(
                "Parallel rate shift (bp)",
                min_value=-200,
                max_value=200,
                value=50,
                step=5,
                key="v29_scenario_parallel_shift",
            )
            curve_twist_bp = st.slider(
                "Curve twist (bp)",
                min_value=-100,
                max_value=100,
                value=0,
                step=5,
                help="Positive values lower the front end and raise the long end; negative values flatten the curve.",
                key="v29_scenario_curve_twist",
            )
            fx_pair = st.selectbox(
                "FX pair",
                ["All FX pairs"] + scenario_specification["fx_pairs"],
                index=1,
                key="v29_scenario_fx_pair",
            )
            fx_spot_move_pct = st.slider(
                "FX spot move (%)",
                min_value=-25,
                max_value=25,
                value=-5,
                step=1,
                key="v29_scenario_fx_move",
            )
            volatility_shift_points = st.slider(
                "IR implied-volatility change (vol points)",
                min_value=-10,
                max_value=25,
                value=5,
                step=1,
                key="v29_scenario_volatility_shift",
            )
            horizon_days = st.slider(
                "Time horizon (business days)",
                min_value=0,
                max_value=10,
                value=1,
                step=1,
                key="v29_scenario_horizon",
            )

    scenario_result = v29.run_interactive_scenario(
        rate_currency=rate_currency,
        curve_family=curve_family,
        parallel_shift_bp=parallel_shift_bp,
        curve_twist_bp=curve_twist_bp,
        fx_pair=fx_pair,
        fx_spot_move_pct=fx_spot_move_pct,
        volatility_shift_points=volatility_shift_points,
        horizon_days=horizon_days,
        severity_multiplier=scenario_specification["severity_options"][severity_label],
        allocation_weight=allocation_weight,
        scope_label=scope_label,
        as_of_date=selected_as_of_date.isoformat(),
    )
    scenario = scenario_result["scenario"]
    scenario_baseline_apl = float(portfolio_df.sort_values("cob_date").iloc[-1]["actual_pnl"])
    scenario_total_pnl = scenario_baseline_apl + float(scenario["estimated_pnl"])

    with scenario_layout[1]:
        with st.container(border=True):
            st.subheader("Today versus your scenario")
            with st.container(horizontal=True):
                st.metric(
                    "Current Actual P&L (APL)",
                    f"EUR {amount(scenario_baseline_apl)}",
                    border=True,
                )
                st.metric(
                    "Estimated scenario impact",
                    f"EUR {amount(scenario['estimated_pnl'])}",
                    delta="Sensitivity-based estimate",
                    border=True,
                )
                st.metric(
                    "Scenario P&L (APL + impact)",
                    f"EUR {amount(scenario_total_pnl)}",
                    border=True,
                )

            st.info(
                "Scenario Lab shows an estimated P&L impact added to the current Actual P&L (APL). "
                "It is separate from official risk-engine limit governance.",
                icon=":material/info:",
            )

            scenario_comparison = pd.DataFrame([
                {
                    "Metric": "Current Actual P&L (APL)",
                    "Today": scenario_baseline_apl,
                    "Under your scenario": scenario_baseline_apl,
                },
                {
                    "Metric": "Estimated scenario impact",
                    "Today": 0.0,
                    "Under your scenario": scenario["estimated_pnl"],
                },
                {
                    "Metric": "Scenario P&L (APL + impact)",
                    "Today": scenario_baseline_apl,
                    "Under your scenario": scenario_total_pnl,
                },
            ])
            st.dataframe(
                scenario_comparison,
                hide_index=True,
                column_config={
                    "Metric": st.column_config.TextColumn(pinned=True),
                    "Today": st.column_config.NumberColumn(format="%,.0f"),
                    "Under your scenario": st.column_config.NumberColumn(format="%,.0f"),
                },
            )
            effective = scenario_result["effective_shocks"]
            st.caption(
                f"{scenario_result['scenario_id']} · {scope_label} · "
                f"effective parallel shift {effective['parallel_shift_bp']:+.0f} bp · "
                f"twist {effective['curve_twist_bp']:+.0f} bp · "
                f"FX {effective['fx_spot_move_pct']:+.0f}% · "
                f"IR volatility {effective['volatility_shift_points']:+.0f} points"
            )

    component_frame = pd.DataFrame(scenario_result["component_contributions"])
    contribution_layout = st.columns(2, gap="medium")
    with contribution_layout[0]:
        with st.container(border=True, height="stretch"):
            st.subheader("Estimated P&L bridge")
            if component_frame["estimated_pnl"].abs().sum() == 0:
                st.info("Move a shock control to create an estimated P&L impact.", icon=":material/info:")
            else:
                component_contributions = [
                    (row["component"], row["estimated_pnl"], "Risk factor")
                    for row in scenario_result["component_contributions"]
                ]
                st.altair_chart(
                    build_waterfall_chart(
                        component_contributions,
                        "Estimated P&L",
                        scenario["estimated_pnl"],
                    ),
                    width="stretch",
                )
    with contribution_layout[1]:
        with st.container(border=True, height="stretch"):
            st.subheader("Contribution by currency")
            currency_contributions = pd.DataFrame(scenario_result["currency_contributions"])
            if currency_contributions.empty:
                st.info("No non-zero sensitivity population is available for this selection.", icon=":material/info:")
            else:
                currency_chart = (
                    alt.Chart(currency_contributions)
                    .mark_bar()
                    .encode(
                        x=alt.X("currency:N", title="Currency"),
                        y=alt.Y("estimated_pnl:Q", title="Estimated P&L (EUR)"),
                        color=alt.Color("component:N", title="Component"),
                        tooltip=[
                            alt.Tooltip("currency:N", title="Currency"),
                            alt.Tooltip("component:N", title="Component"),
                            alt.Tooltip("estimated_pnl:Q", title="Estimated P&L", format=",.0f"),
                        ],
                    )
                    .properties(height=390)
                )
                st.altair_chart(currency_chart, width="stretch")

    with st.container(border=True):
        st.subheader("Largest sensitivity contributions")
        top_contributors = pd.DataFrame(scenario_result["top_contributors"])
        if top_contributors.empty:
            st.info("No sensitivity contributions are available for this selection.", icon=":material/info:")
        else:
            st.dataframe(
                top_contributors,
                hide_index=True,
                column_order=[
                    "component", "currency", "curve_family", "curve", "tenor",
                    "applied_shock", "estimated_pnl",
                ],
                column_config={
                    "component": "Component",
                    "currency": "Currency",
                    "curve_family": "Curve family",
                    "curve": "Curve",
                    "tenor": "Tenor / surface node",
                    "applied_shock": "Applied shock",
                    "estimated_pnl": st.column_config.NumberColumn("Estimated P&L", format="%,.0f"),
                },
            )

    with st.expander("Methodology and limitations", icon=":material/rule:"):
        st.write(scenario_result["methodology"])
        for assumption in scenario_result["assumptions"]:
            st.markdown(f"- {assumption}")
        st.warning(scenario_result["governance_note"], icon=":material/warning:")

    st.button(
        "Ask MIRAI about this scenario",
        icon=":material/auto_awesome:",
        type="primary",
        width="stretch",
        on_click=select_scenario_agent_page,
        args=(scenario_result,),
        key="v29_scenario_agent_button",
    )

elif page == "Stress":
    st.header("Stress")
    st.caption("Risk-engine-supplied scenario revaluation P&L only. Negative values represent losses versus the base valuation.")
    st.info("The supplied demo extract contains historical, hypothetical, adverse and extreme full-revaluation scenario results.", icon=":material/info:")

    scenario_names = [column for column in stress_frame.columns if column != "cob_date"]
    stress_limit_monitor = v29.get_stress_limit_monitor(selected_as_of_date)
    stress_limit_table = pd.DataFrame(stress_limit_monitor["scenarios"])
    stress_movements = pd.DataFrame(v29.get_stress_movement_table(selected_as_of_date)["scenarios"])

    movement_scores = stress_movements.copy()
    movement_scores["magnitude_score"] = movement_scores["latest_impact"].abs() / max(movement_scores["latest_impact"].abs().max(), 1.0)
    movement_scores["move_score"] = movement_scores["daily_move"].abs() / max(movement_scores["daily_move"].abs().max(), 1.0)
    material_defaults = movement_scores.assign(attention_score=movement_scores["magnitude_score"] + movement_scores["move_score"]).nlargest(10, "attention_score")["scenario"].tolist()

    with st.container(border=True):
        st.subheader("Top 10 stress evolutions")
        selected_scenarios = st.multiselect(
            "Priced scenarios to display",
            scenario_names,
            default=material_defaults,
            key="v30_stress_scenarios",
        )
        if selected_scenarios:
            chart_wide = stress_frame[["cob_date"] + selected_scenarios].copy()
            chart_long = chart_wide.melt("cob_date", var_name="scenario", value_name="impact")
            chart_long["category"] = chart_long["scenario"].map(lambda name: stress_metadata[name]["type"])
            lines = (
                alt.Chart(chart_long)
                .mark_line(strokeWidth=2)
                .encode(
                    x=alt.X("cob_date:T", title="Business date", axis=alt.Axis(format="%b", tickCount=12)),
                    y=alt.Y("impact:Q", title="P&L impact (EUR)", scale=alt.Scale(zero=False)),
                    color=alt.Color("scenario:N", title="Scenario"),
                    strokeDash=alt.StrokeDash("category:N", title="Category", legend=alt.Legend(orient="bottom")),
                    tooltip=[alt.Tooltip("cob_date:T", title="Date", format="%d/%m/%Y"), alt.Tooltip("scenario:N", title="Scenario"), alt.Tooltip("category:N", title="Category"), alt.Tooltip("impact:Q", title="P&L impact", format=",.0f")],
                )
            )
            last_date = chart_long["cob_date"].max()
            endpoints = chart_long.loc[chart_long["cob_date"] == last_date]
            endpoint_points = alt.Chart(endpoints).mark_point(filled=True, size=65).encode(x="cob_date:T", y="impact:Q", color=alt.Color("scenario:N", legend=None))
            endpoint_labels = alt.Chart(endpoints).mark_text(align="left", dx=7, fontSize=11).encode(x="cob_date:T", y="impact:Q", text=alt.Text("scenario:N"), color=alt.Color("scenario:N", legend=None))
            st.altair_chart((lines + endpoint_points + endpoint_labels).properties(height=430), key="stress_evolution")
        else:
            st.info("Select at least one priced scenario.", icon=":material/info:")

    with st.container(border=True):
        st.subheader("Scenario definitions and current impacts")
        limit_lookup = stress_limit_table.set_index("scenario")
        movement_lookup = stress_movements.set_index("scenario")
        latest_stress = stress_frame.iloc[-1].drop(labels="cob_date").sort_values()
        stress_table = pd.DataFrame({
            "Scenario": latest_stress.index,
            "Category": [stress_metadata[name]["type"] for name in latest_stress.index],
            "Stressed P&L": latest_stress.values * allocation_weight,
            "Daily move": [movement_lookup.loc[name, "daily_move"] * allocation_weight for name in latest_stress.index],
            "Weekly move": [movement_lookup.loc[name, "weekly_move"] * allocation_weight for name in latest_stress.index],
            "Monthly move": [movement_lookup.loc[name, "monthly_move"] * allocation_weight for name in latest_stress.index],
            "Limit": [limit_lookup.loc[name, "limit"] * allocation_weight for name in latest_stress.index],
            "Consumption": [limit_lookup.loc[name, "consumption_pct"] for name in latest_stress.index],
            "Status": [limit_lookup.loc[name, "status"] for name in latest_stress.index],
            "Definition": [stress_metadata[name]["definition"] for name in latest_stress.index],
        })
        st.dataframe(
            stress_table,
            hide_index=True,
            column_config={
                "Stressed P&L": st.column_config.NumberColumn(format="%,.0f"),
                "Daily move": st.column_config.NumberColumn(format="%,.0f"),
                "Weekly move": st.column_config.NumberColumn(format="%,.0f"),
                "Monthly move": st.column_config.NumberColumn(format="%,.0f"),
                "Limit": st.column_config.NumberColumn(format="%,.0f"),
                "Consumption": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=120),
            },
        )

    with st.expander("Scenario catalogue", icon=":material/assignment:"):
        scenario_catalog = pd.DataFrame(v29.get_stress_scenario_catalog())
        scenario_catalog["limit"] = scenario_catalog["limit"] * allocation_weight
        st.dataframe(
            scenario_catalog,
            hide_index=True,
            column_order=["scenario", "category", "shock", "limit", "limit_unit", "derived_from", "pricing_status"],
            column_config={
                "scenario": "Scenario",
                "category": "Category",
                "shock": "Shock / definition",
                "limit": st.column_config.NumberColumn("Limit", format="%,.0f"),
                "limit_unit": "Limit unit",
                "derived_from": "Adverse counterpart",
                "pricing_status": "Pricing status",
            },
        )
        st.caption(stress_limit_monitor["usage_note"])

elif page == "Controls":
    st.header("Controls")
    limit_evaluation = v29.evaluate_all_limits()
    limit_frame = pd.DataFrame(limit_evaluation["limits"])
    status_rank = {"BREACH": 0, "WARNING": 1, "OK": 2}
    limit_frame["status_rank"] = limit_frame["status"].map(status_rank)
    limit_frame = limit_frame.sort_values(["status_rank", "consumption_pct"], ascending=[True, False]).drop(columns="status_rank")
    limit_summary = limit_evaluation["summary"]

    with st.container(border=True):
        st.subheader("Limit governance")
        st.caption("Below 80% is OK · 80% to below 100% is WARNING · 100% or above is BREACH.")
        if limit_summary["breaches"]:
            st.error(f"{limit_summary['breaches']} limit breach(es) require immediate escalation.", icon=":material/error:")
        elif limit_summary["warnings"]:
            st.warning(f"{limit_summary['warnings']} limit warning(s) require owner review.", icon=":material/warning:")
        else:
            st.success("All governed metrics are below the 80% warning threshold.", icon=":material/check_circle:")
        st.dataframe(
            limit_frame,
            hide_index=True,
            column_order=["family", "metric", "exposure", "limit", "unit", "consumption_pct", "status", "owner", "escalation_status", "consumption_basis"],
            column_config={
                "family": "Risk family",
                "metric": "Metric",
                "exposure": st.column_config.NumberColumn("Exposure", format="%.0f"),
                "limit": st.column_config.NumberColumn("Limit", format="%.0f"),
                "unit": "Unit",
                "consumption_pct": st.column_config.ProgressColumn("Consumption", format="%.1f%%", min_value=0, max_value=120),
                "status": "Status",
                "owner": "Owner",
                "escalation_status": "Escalation",
                "consumption_basis": "Consumption basis",
            },
        )
        st.caption(limit_evaluation["usage_note"])
    daily_brief = v29.generate_daily_risk_brief(selected_as_of_date)
    daily_actions = pd.DataFrame(daily_brief["actions"])
    with st.container(border=True):
        st.subheader("Daily risk brief and action queue")
        with st.container(horizontal=True):
            st.metric("Daily status", daily_brief["overall_status"], border=True)
            st.metric("Open actions", daily_brief["sign_off"]["open_actions"], border=True)
            st.metric("Sign-off", daily_brief["sign_off"]["status"], border=True)
            st.metric("Required role", daily_brief["sign_off"]["required_role"], border=True)
        if daily_brief["overall_status"] == "ESCALATION REQUIRED":
            st.error(daily_brief["headline"], icon=":material/error:")
        elif daily_brief["overall_status"] == "REVIEW REQUIRED":
            st.warning(daily_brief["headline"], icon=":material/warning:")
        else:
            st.info(daily_brief["headline"], icon=":material/info:")
        if not daily_actions.empty:
            st.dataframe(
                daily_actions,
                hide_index=True,
                column_order=[
                    "action_id", "priority", "source", "finding", "owner",
                    "required_action", "workflow_status", "due",
                ],
                column_config={
                    "action_id": "Action ID",
                    "priority": "Priority",
                    "source": "Source",
                    "finding": "Finding",
                    "owner": "Owner",
                    "required_action": "Required action",
                    "workflow_status": "Workflow status",
                    "due": "Due",
                },
            )
        st.caption(daily_brief["usage_note"])
    materiality = v29.detect_material_risk_movements(selected_as_of_date)
    materiality_frame = pd.DataFrame(materiality["findings"])
    with st.container(border=True):
        st.subheader("Material risk movements")
        with st.container(horizontal=True):
            st.metric("Critical", materiality["summary"]["critical"], border=True)
            st.metric("High", materiality["summary"]["high"], border=True)
            st.metric("Medium", materiality["summary"]["medium"], border=True)
            st.metric("Findings", materiality["finding_count"], border=True)
        if materiality_frame.empty:
            st.success("No material movement crossed a configured threshold.", icon=":material/check_circle:")
        else:
            st.dataframe(
                materiality_frame,
                hide_index=True,
                column_order=["severity", "source", "finding", "observed", "threshold", "unit", "action"],
                column_config={
                    "severity": "Severity",
                    "source": "Source",
                    "finding": "Finding",
                    "observed": st.column_config.NumberColumn("Observed", format="%.1f"),
                    "threshold": st.column_config.NumberColumn("Threshold", format="%.1f"),
                    "unit": "Unit",
                    "action": "Required review",
                },
            )
        st.caption(materiality["usage_note"])
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
        quality["Result"] = quality["Result"].astype(str)
        st.dataframe(quality, hide_index=True)

    with st.container(border=True):
        st.subheader("Alerts and exceptions")
        pnl_alert_evaluation = v29.evaluate_pnl_explain_alerts()
        pnl_alert_frame = pd.DataFrame(pnl_alert_evaluation["desk_results"])
        flagged_pnl = pnl_alert_frame.loc[pnl_alert_frame["status"] == "ALERT"].copy()
        with st.container(horizontal=True):
            st.metric("Rules-based risk alerts", len(alert_summary["alerts"]), border=True)
            st.metric("Unexplained-P&L flags", pnl_alert_evaluation["flagged_count"], border=True)
            st.metric("Unexplained threshold", "20% of |APL|", border=True)

        for alert in alert_summary["alerts"]:
            st.markdown(f"{alert_badge(alert['severity'])}  **{alert['title']}** — {alert['summary']}")

        if flagged_pnl.empty:
            st.success("No desk exceeds the unexplained-P&L threshold.", icon=":material/check_circle:")
        else:
            st.error(
                f"{len(flagged_pnl)} desk(s) exceed the 20% unexplained-to-|APL| threshold.",
                icon=":material/error:",
            )
            st.dataframe(
                flagged_pnl,
                hide_index=True,
                column_order=[
                    "business_line",
                    "trading_desk",
                    "actual_pnl",
                    "unexplained_pnl",
                    "unexplained_to_apl_pct",
                    "threshold_pct",
                    "status",
                ],
                column_config={
                    "business_line": "Business line",
                    "trading_desk": "Trading desk",
                    "actual_pnl": st.column_config.NumberColumn("APL", format="%.0f"),
                    "unexplained_pnl": st.column_config.NumberColumn("Unexplained P&L", format="%.0f"),
                    "unexplained_to_apl_pct": st.column_config.ProgressColumn(
                        "Unexplained / |APL|",
                        format="%.1f%%",
                        min_value=0,
                        max_value=50,
                    ),
                    "threshold_pct": st.column_config.NumberColumn("Threshold", format="%.1f%%"),
                    "status": "Status",
                },
            )
        st.caption(pnl_alert_evaluation["usage_note"])

else:
    st.header("ask M.I.R.A.I.")
    st.caption(
        "Security note: this public demo uses synthetic risk data. Do not enter confidential, "
        "client, trade, personal, or other restricted information. In production, connect MIRAI "
        "only to your organisation's approved model endpoint and data controls."
    )
    scenario_context = st.session_state.get("v29_scenario_context")
    pending_scenario_question = st.session_state.pop("v29_pending_scenario_question", None)
    if scenario_context:
        with st.container(horizontal=True, vertical_alignment="center"):
            st.info(
                f"Scenario context attached: {scenario_context['scenario_id']} · "
                f"{scenario_context['scope']} · {scenario_context['calculation_mode']}",
                icon=":material/science:",
            )
            st.button(
                "Clear scenario",
                icon=":material/close:",
                on_click=clear_scenario_agent_context,
                key="v29_clear_scenario_context",
            )
    with st.container(border=True):
        selected_question = pending_scenario_question
        answer_detail = st.segmented_control(
            "Answer detail",
            ["Succinct", "Moderate", "Detailed"],
            default="Moderate",
            selection_mode="single",
            key="v30_answer_detail",
            width="stretch",
        )
        if not st.session_state.risk_agent_messages and selected_question is None:
            selected_question = st.pills("Suggested questions", ["How has stress evolved across scenarios?", "Which portfolios are included in this risk run?", "What are the main VaR and P&L risks today?"], label_visibility="collapsed")
        for message in st.session_state.risk_agent_messages:
            avatar = ":material/analytics:" if message["role"] == "assistant" else None
            with st.chat_message(message["role"], avatar=avatar):
                st.markdown(message["content"])
        typed_question = st.chat_input("Ask about the current market-risk position", submit_mode="disable")
        question = typed_question or selected_question
        if question:
            detail_instruction = {
                "Succinct": "Answer format: succinct. Give an executive conclusion and at most three evidence-based bullets.",
                "Moderate": "Answer format: moderate. Give a concise conclusion, evidence and recommended actions.",
                "Detailed": "Answer format: detailed. Explain the conclusion, quantified evidence, drivers, caveats and recommended actions.",
            }[answer_detail]
            agent_question = f"{question}\n\n{detail_instruction}"
            st.session_state.risk_agent_messages.append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)
            answer = None
            with st.status("Running the risk investigation...", expanded=True) as status:
                try:
                    if scenario_context:
                        answer = v29.ask_scenario_agent(agent_question, scenario_context)
                    else:
                        answer = v29.ask_risk_agent(agent_question)
                except Exception as error:
                    status.update(label="Investigation could not be completed", state="error")
                    st.error(str(error), icon=":material/error:")
                else:
                    status.update(label="Investigation complete", state="complete", expanded=False)
            if answer is not None:
                st.session_state.risk_agent_messages.append({"role": "assistant", "content": answer})
                with st.chat_message("assistant", avatar=":material/analytics:"):
                    st.markdown(answer)
    with st.expander("Recent investigation memory", icon=":material/history:"):
        memory = v29.v9.get_recent_investigation_context()
        st.caption(memory["usage_note"])
        if memory["recent_investigations"]:
            for record in reversed(memory["recent_investigations"]):
                st.markdown(f"**{record['question']}**")
                st.caption(f"{record['timestamp_utc']} · tools: {', '.join(record['tools_used'])}")
        else:
            st.info("No completed investigations have been recorded for this data snapshot yet.", icon=":material/info:")



