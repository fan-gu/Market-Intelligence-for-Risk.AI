"""Render the Ask MIRAI page."""

def render(context):
    """Render this page from the application-shell context."""
    clear_scenario_agent_context = context["clear_scenario_agent_context"]
    normalize_agent_answer = context["normalize_agent_answer"]
    risk = context["risk"]
    st = context["st"]
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
                st.markdown(normalize_agent_answer(message["content"]))
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
            initial_stage = "Validating scenario" if scenario_context else "Validating risk request"
            with st.status(initial_stage, expanded=True) as status:
                try:
                    st.write(f":material/check_circle: {initial_stage}")
                    status.update(label="Calculating contributions")
                    st.write(":material/functions: Calculating contributions from deterministic risk tools")
                    status.update(label="Generating analysis")
                    st.write(":material/auto_awesome: Generating analysis with Gemini")
                    if scenario_context:
                        answer = risk.ask_scenario_agent(agent_question, scenario_context)
                    else:
                        answer = risk.ask_risk_agent(agent_question)
                    answer = normalize_agent_answer(answer)
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
        memory = risk.get_recent_investigation_context()
        st.caption(memory["usage_note"])
        if memory["recent_investigations"]:
            for record in reversed(memory["recent_investigations"]):
                st.markdown(f"**{record['question']}**")
                st.caption(f"{record['timestamp_utc']} · tools: {', '.join(record['tools_used'])}")
        else:
            st.info("No completed investigations have been recorded for this data snapshot yet.", icon=":material/info:")
