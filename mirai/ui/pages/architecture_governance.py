"""Render the Architecture & Governance page."""

def render(context):
    """Render this page from the application-shell context."""
    pd = context["pd"]
    st = context["st"]
    st.header("Architecture & Governance")
    st.caption(
        "How MIRAI separates the interface, deterministic risk evidence, AI analysis, "
        "controls and human accountability. All public-demo data are synthetic."
    )

    with st.container(border=True):
        st.subheader("Target operating architecture")
        st.code(
            """Approved risk-engine outputs
        |
        v
FastAPI + shared RiskDataService [implemented]
        |
        +--> Deterministic risk analytics and controls [implemented]
        |          |
        |          +--> Unified SQLite audit trail and run lineage [implemented]
        |
        +--> Agent workflow [current: governed Python tools]
                   |
                   +--> LangGraph orchestration [planned]
                   +--> FRTB and policy RAG [planned]
                   +--> Gemini synthesis [implemented]
                              |
                              v
                    Human review and approval""",
            language="text",
        )

    capability_rows = pd.DataFrame([
        {"Capability": "Streamlit risk-manager interface", "Status": "Implemented", "Governance purpose": "Controlled visual investigation of approved synthetic runs"},
        {"Capability": "FastAPI risk-run service", "Status": "Implemented", "Governance purpose": "Typed API boundary and validation; public hosting deferred"},
        {"Capability": "Granular book-risk facts", "Status": "Implemented", "Governance purpose": "Explicit book/date records replace fixed dashboard allocations and reconcile to the bank total"},
        {"Capability": "Deterministic risk tools and controls", "Status": "Implemented", "Governance purpose": "Numbers remain traceable to supplied data and rules"},
        {"Capability": "Audit trail and run lineage", "Status": "Implemented", "Governance purpose": "Reconstruct requests, tools, evidence and responses"},
        {"Capability": "Gemini synthesis", "Status": "Implemented", "Governance purpose": "Narrative interpretation; never the numerical source of truth"},
        {"Capability": "LangGraph workflow", "Status": "Planned", "Governance purpose": "Explicit branching, retries and approval gates"},
        {"Capability": "FRTB / policy RAG", "Status": "Planned", "Governance purpose": "Ground rule interpretations in cited approved documents"},
        {"Capability": "Human approval workflow", "Status": "Policy defined; UI planned", "Governance purpose": "Risk decisions and escalations remain human-owned"},
    ])
    with st.container(border=True):
        st.subheader("Capability status")
        st.dataframe(capability_rows, hide_index=True, width="stretch")

    approval_columns = st.columns(3)
    with approval_columns[0]:
        with st.container(border=True, height="stretch"):
            st.subheader("1. Evidence gate")
            st.write("Validate run ID, as-of date, scope and data quality before analysis.")
    with approval_columns[1]:
        with st.container(border=True, height="stretch"):
            st.subheader("2. Risk-manager gate")
            st.write("A human reviews warnings, breaches, scenario assumptions and proposed actions.")
    with approval_columns[2]:
        with st.container(border=True, height="stretch"):
            st.subheader("3. Action gate")
            st.write("MIRAI cannot approve limits, submit trades or close an escalation autonomously.")

    with st.container(border=True):
        st.subheader("Core governance principles")
        st.markdown(
            """- Risk-engine outputs and deterministic tools are the numerical source of truth.
- AI-generated explanations must remain in EUR, cite available evidence and state limitations.
- Scenario Lab is a sensitivity approximation, not official full revaluation.
- Confidential information must not be entered into the public demo.
- Human approval is required for limit decisions, escalations and risk actions."""
        )


