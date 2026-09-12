# ruff: noqa: E402
"""MIRAI V33 consolidated Streamlit application shell."""

import re

import altair as alt
import pandas as pd
import streamlit as st

from mirai.book_risk import (
    aggregate_scope_history,
    build_book_risk_history,
)

st.set_page_config(page_title="MIRAI | Market Intelligence for Risk AI | V33", page_icon=":material/monitoring:", layout="wide")

from mirai import runtime as risk

SVAR_LIMIT_MULTIPLIER = 1.5
st.session_state.setdefault("risk_agent_messages", [])
st.session_state.setdefault("v29_active_page", "Dashboard")


@st.cache_data(show_spinner="Loading granular book-level risk records...")
def load_book_risk_history(bank_history, hierarchy):
    """Cache the 5,200-row deterministic risk fact set across Streamlit reruns."""
    return build_book_risk_history(bank_history, hierarchy)


def select_dashboard_page():
    st.session_state.v29_active_page = st.session_state.v29_navigation


def select_agent_page():
    st.session_state.v29_active_page = "Ask MIRAI"


def select_scenario_agent_page(scenario_context):
    st.session_state.v29_scenario_context = scenario_context
    st.session_state.v29_pending_scenario_question = (
        "Assess this saved Scenario Lab result. Explain the principal risk contributions, "
        "the loss-limit impact, the important modelling limitations and the actions a market "
        "risk manager should consider."
    )
    st.session_state.v29_active_page = "Ask MIRAI"


def clear_scenario_agent_context():
    st.session_state.pop("v29_scenario_context", None)
    st.session_state.pop("v29_pending_scenario_question", None)


def amount(value):
    return f"{value:,.0f}"


def percentage(value):
    return f"{value:.1f}%"


def normalize_agent_answer(answer):
    """Keep rendered monetary amounts in MIRAI's EUR reporting currency."""
    return re.sub(r"\$(?=\s*[-+]?\d)", "EUR ", str(answer))


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

df = risk.df.copy()
current_risk = risk.get_current_risk()
trend = risk.get_var_trend()
limit = risk.get_limit_analysis()
backtesting = risk.get_backtesting_analysis()
alert_summary = risk.get_risk_alerts()
risk_run = risk.get_risk_run_lineage()
lineage = risk_run["lineage"]
stress_evolution = risk.get_stress_evolution()

portfolio_scope = risk.get_portfolio_scope()
portfolio_ids = [row["portfolio_id"] for row in portfolio_scope["portfolios"]]

available_as_of_dates = sorted(df["cob_date"].dt.date.unique(), reverse=True)
books, _ = risk.build_hierarchy()
book_risk_history = load_book_risk_history(df, books)

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
    .st-key-var_summary_cards [data-testid="stMetricLabel"] {{
        font-size: 0.70rem !important;
        white-space: nowrap !important;
    }}
    .st-key-var_summary_cards [data-testid="stMetricValue"] {{
        font-size: 1.18rem !important;
        white-space: nowrap !important;
    }}
    .st-key-var_summary_cards [data-testid="stMetricValue"] > div {{
        font-size: 1.18rem !important;
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
            "As of",
            value=pd.Timestamp(max(available_as_of_dates)).date(),
            min_value=pd.Timestamp(min(available_as_of_dates)).date(),
            max_value=pd.Timestamp(max(available_as_of_dates)).date(),
            format="DD/MM/YYYY",
            key="v30_as_of_calendar",
        ))

    st.segmented_control(
        "Navigate",
        [
            "Dashboard",
            "VaR",
            "P&L",
            "Sensitivities",
            "Stress",
            "Scenario Lab",
            "Controls",
            "Architecture & Governance",
        ],
        default="Dashboard",
        required=True,
        width="stretch",
        label_visibility="collapsed",
        key="v29_navigation",
        on_change=select_dashboard_page,
    )
page = st.session_state.v29_active_page
scope_book_history = book_risk_history.loc[
    book_risk_history["book_id"].isin(scoped_books["book_id"])
    & (book_risk_history["cob_date"] <= pd.Timestamp(selected_as_of_date))
].copy()
portfolio_df = aggregate_scope_history(scope_book_history)
if portfolio_df.empty:
    st.error("There are no observations on or before the selected as-of date.")
    st.stop()
_, stress_metadata = risk.build_supplied_stress_frame(selected_as_of_date)

bank_latest = df.loc[df["cob_date"] <= pd.Timestamp(selected_as_of_date)].sort_values("cob_date").iloc[-1]
scope_latest = portfolio_df.sort_values("cob_date").iloc[-1]
allocation_weight = (
    0.0
    if float(bank_latest["var_1d_99_hist"]) == 0.0
    else float(scope_latest["var_1d_99_hist"]) / float(bank_latest["var_1d_99_hist"])
)
scope_label = " / ".join(
    value
    for value in [
        selected_business_line if selected_business_line != "All business lines" else None,
        selected_desk if selected_desk != "All desks" else None,
        selected_book if selected_book != "All books" else None,
    ]
    if value
) or "Whole portfolio"
base_limit_rows = risk.evaluate_all_limits()["limits"]
scenario_columns = [definition["column"] for definition in risk.STRESS_SCENARIO_DEFINITIONS.values()]
worst_scope_stress = abs(min(float(scope_latest[scenario_columns].min()), 0.0))
scope_limit_rows = []
for source_row in base_limit_rows:
    row = dict(source_row)
    if row["unit"] != "Exceptions":
        row["limit"] = float(row["limit"]) * allocation_weight
        row["exposure"] = float(row["exposure"]) * allocation_weight
    if row["metric"] == "Historical VaR (1 day, 99%)":
        row["exposure"], row["limit"] = abs(float(scope_latest["var_1d_99_hist"])), abs(float(scope_latest["var_limit_amount"]))
    elif row["metric"] == "Stressed VaR (SVaR, 1 day, 99%)":
        row["exposure"], row["limit"] = abs(float(scope_latest["stressed_var_1d_99"])), abs(float(scope_latest["var_limit_amount"])) * SVAR_LIMIT_MULTIPLIER
    elif row["metric"] == "Worst-case stress loss":
        row["exposure"] = worst_scope_stress
    elif row["metric"] == "Daily actual loss":
        row["exposure"] = abs(min(float(scope_latest["actual_pnl"]), 0.0))
    elif row["metric"] == "Absolute unexplained P&L":
        row["exposure"] = abs(float(scope_latest["unexplained_pnl"]))
    elif row["metric"] == "250-day exceptions":
        row["exposure"] = float(scope_latest["backtest_exception_count_250d"])
    row["consumption_pct"] = 0.0 if float(row["limit"]) == 0.0 else float(row["exposure"]) / float(row["limit"]) * 100.0
    row["status"] = "BREACH" if row["consumption_pct"] >= 100.0 else "WARNING" if row["consumption_pct"] >= 80.0 else "OK"
    row["escalation_status"] = "Immediate escalation required" if row["status"] == "BREACH" else "Owner review required" if row["status"] == "WARNING" else "No escalation"
    scope_limit_rows.append(row)
scope_limit_summary = {
    "breaches": sum(row["status"] == "BREACH" for row in scope_limit_rows),
    "warnings": sum(row["status"] == "WARNING" for row in scope_limit_rows),
    "ok": sum(row["status"] == "OK" for row in scope_limit_rows),
}
scope_limit_evaluation = {
    "limits": scope_limit_rows,
    "summary": scope_limit_summary,
    "usage_note": "V33 limits follow the selected explicit book perimeter; warning starts at 80% and breach at 100%.",
}
header_limit_rows = scope_limit_rows
header_breaches = [row["metric"] for row in header_limit_rows if row["status"] == "BREACH"]
header_warnings = [row["metric"] for row in header_limit_rows if row["status"] == "WARNING"]
if header_breaches:
    st.error("Current limit breaches: " + " · ".join(dict.fromkeys(header_breaches)), icon=":material/error:")
if not header_breaches and not header_warnings:
    st.success("All current governed risk measures are below warning thresholds.", icon=":material/check_circle:")
st.caption(f"Selected perimeter: {scope_label} · {scoped_books['book_id'].nunique()} book(s) · explicit book-level risk records")
stress_frame = portfolio_df[["cob_date"]].copy()
for scenario, definition in risk.STRESS_SCENARIO_DEFINITIONS.items():
    stress_frame[scenario] = portfolio_df[definition["column"]].astype(float)
stress_numeric = [column for column in stress_frame.columns if column != "cob_date"]

from mirai.ui.pages import (
    architecture_governance,
    ask_mirai,
    controls,
    dashboard,
    p_l,
    scenario_lab,
    sensitivities,
    stress,
    var,
)

_PAGE_RENDERERS = {
    "Dashboard": dashboard.render,
    "VaR": var.render,
    "P&L": p_l.render,
    "Sensitivities": sensitivities.render,
    "Scenario Lab": scenario_lab.render,
    "Stress": stress.render,
    "Architecture & Governance": architecture_governance.render,
    "Controls": controls.render,
    "Ask MIRAI": ask_mirai.render,
}
_PAGE_RENDERERS.get(page, ask_mirai.render)(dict(globals()))
