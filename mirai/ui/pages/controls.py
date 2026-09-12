"""Render the Controls page."""

from mirai.book_risk import reconciliation_report


def render(context):
    """Render this page from the application-shell context."""
    alert_badge = context["alert_badge"]
    alert_summary = context["alert_summary"]
    book_risk_history = context["book_risk_history"]
    date_labels = context["date_labels"]
    df = context["df"]
    lineage = context["lineage"]
    pd = context["pd"]
    portfolio_df = context["portfolio_df"]
    risk = context["risk"]
    risk_run = context["risk_run"]
    scope_book_history = context["scope_book_history"]
    scope_limit_evaluation = context["scope_limit_evaluation"]
    scoped_books = context["scoped_books"]
    selected_as_of_date = context["selected_as_of_date"]
    st = context["st"]
    st.header("Controls")
    limit_evaluation = scope_limit_evaluation
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
    daily_brief = risk.generate_daily_risk_brief(selected_as_of_date)
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
    materiality = risk.detect_material_risk_movements(selected_as_of_date)
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
        st.metric("Selected records", len(scope_book_history), border=True)
        st.metric("Selected books", scoped_books["book_id"].nunique(), border=True)
        st.metric("Business dates", len(portfolio_df), border=True)
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
        st.subheader("Book-to-bank reconciliation")
        reconciliation = reconciliation_report(df, book_risk_history)
        with st.container(horizontal=True):
            st.metric("Book/date records", reconciliation["records"], border=True)
            st.metric("Books", reconciliation["books"], border=True)
            st.metric("Business dates", reconciliation["dates"], border=True)
            st.metric("Maximum absolute error", f"{reconciliation['max_absolute_error']:.2e}", border=True)
        st.success("Every additive daily measure reconciles to the consolidated bank-wide source within floating-point tolerance.", icon=":material/check_circle:")
    with st.container(border=True):
        st.subheader("Business-date controls")
        st.success("All observations in the current extract fall on Monday–Friday.", icon=":material/check_circle:")
        preview = date_labels(portfolio_df)[["display_date", "portfolio_id", "reporting_currency"]].rename(columns={"display_date": "COB date"})
        st.dataframe(preview, hide_index=True)
    with st.container(border=True):
        st.subheader("Data-quality checks")
        quality = pd.DataFrame([risk.validate_data()]).T.rename(columns={0: "Result"}).reset_index(names="Control")
        quality["Result"] = quality["Result"].astype(str)
        st.dataframe(quality, hide_index=True)

    with st.container(border=True):
        st.subheader("Alerts and exceptions")
        pnl_alert_evaluation = risk.evaluate_pnl_explain_alerts()
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
