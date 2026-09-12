"""Lazy, grounded MIRAI language-agent boundary with one SQLite audit trail."""

from __future__ import annotations

import json
import os
from functools import lru_cache

from .audit import AuditStore
from .controls import evaluate_all_limits, generate_daily_risk_brief
from .core import (
    AUDIT_PATH,
    MODEL_NAME,
    get_current_risk,
    get_risk_run_lineage,
    get_var_trend,
)
from .scenario import run_interactive_scenario
from .sensitivities import get_market_sensitivities
from .stress import get_stress_limit_monitor


@lru_cache(maxsize=1)
def _api_key() -> str:
    from dotenv import load_dotenv

    load_dotenv()
    value = os.getenv("GEMINI_API_KEY", "")
    if not value:
        try:
            import streamlit as st

            value = str(st.secrets.get("GEMINI_API_KEY", ""))
        except Exception:
            value = ""
    if not value:
        raise RuntimeError("GEMINI_API_KEY is not configured. Add it to Streamlit Secrets or the local .env file.")
    return value


@lru_cache(maxsize=1)
def _client():
    """Import and create the external model client only after a user asks."""
    from google import genai

    return genai.Client(api_key=_api_key())


def _select_evidence(question: str) -> tuple[list[str], dict]:
    lowered = question.lower()
    names = ["get_current_risk", "evaluate_all_limits", "generate_daily_risk_brief"]
    evidence = {
        "get_current_risk": get_current_risk(),
        "evaluate_all_limits": evaluate_all_limits(),
        "generate_daily_risk_brief": generate_daily_risk_brief(),
    }
    optional = [
        (("var", "value at risk", "hvar", "svar"), "get_var_trend", get_var_trend),
        (("stress", "scenario"), "get_stress_limit_monitor", get_stress_limit_monitor),
        (("sensi", "delta", "gamma", "vega", "theta", "fx"), "get_market_sensitivities", get_market_sensitivities),
    ]
    for keywords, name, function in optional:
        if any(keyword in lowered for keyword in keywords):
            names.append(name)
            evidence[name] = function()
    return names, evidence


def _record(question: str, tools: list[str], answer: str, *, context_type: str) -> None:
    lineage = get_risk_run_lineage()["lineage"]
    AuditStore(AUDIT_PATH).record(
        lineage["run_id"],
        "agent_investigation",
        {
            "question": question,
            "tools_used": tools,
            "context_type": context_type,
            "answer": answer,
            "data_fingerprint": lineage["data_fingerprint"],
            "human_approval_required": True,
        },
    )


def ask_risk_agent(question: str) -> str:
    """Answer from deterministic evidence; the model may explain but not calculate."""
    tools, evidence = _select_evidence(question)
    instruction = """You are MIRAI, a market-risk investigation assistant.
Use only the supplied deterministic evidence for numbers and status. Never invent, recompute, or alter a limit, exposure, severity, or date. Reporting currency is EUR; format monetary values as 'EUR 1,234' without dollar signs or LaTeX. Clearly distinguish synthetic demo data from production facts. If evidence is insufficient, say so. Recommendations require a human market-risk manager's approval."""
    response = _client().models.generate_content(
        model=MODEL_NAME,
        contents=f"Question:\n{question}\n\nDeterministic evidence:\n{json.dumps(evidence, indent=2, default=str)}",
        config={"system_instruction": instruction},
    )
    answer = response.text or "No analysis was returned by the configured model."
    _record(question, tools, answer, context_type="risk")
    return answer


def ask_scenario_agent(question: str, scenario_context: dict) -> str:
    """Explain an already-calculated Scenario Lab result."""
    instruction = """You are MIRAI. Explain only the supplied deterministic Scenario Lab result. It is a sensitivity approximation, never an official full revaluation, VaR, Expected Shortfall, or capital calculation. Use EUR, not dollar signs. A zero no-shock reference is scenario impact, not Actual P&L. State key contributions, limitations, and decisions requiring human approval."""
    response = _client().models.generate_content(
        model=MODEL_NAME,
        contents=f"Question:\n{question}\n\nScenario evidence:\n{json.dumps(scenario_context, indent=2, default=str)}",
        config={"system_instruction": instruction},
    )
    answer = response.text or "No analysis was returned by the configured model."
    _record(question, [run_interactive_scenario.__name__], answer, context_type="scenario")
    return answer


def get_recent_investigation_context(limit: int = 5) -> dict:
    """Return recent records for the active data fingerprint from the unified audit store."""
    lineage = get_risk_run_lineage()["lineage"]
    records = AuditStore(AUDIT_PATH).list_for_run(lineage["run_id"])
    investigations = []
    for record in records[-limit:]:
        metadata = record["metadata"]
        if record["event_type"] != "agent_investigation":
            continue
        investigations.append({
            "question": metadata.get("question", ""),
            "timestamp_utc": record["created_at"].isoformat(),
            "tools_used": metadata.get("tools_used", []),
        })
    return {
        "recent_investigations": investigations,
        "usage_note": "Recent investigations are read from MIRAI's single SQLite audit trail for the current risk-run fingerprint.",
    }
