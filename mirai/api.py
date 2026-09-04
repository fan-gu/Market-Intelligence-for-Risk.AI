"""FastAPI boundary for approved MIRAI risk-run results."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException

from .audit import AuditStore
from .risk_service import RiskDataError, RiskDataService
from .schemas import (
    AgentQueryRequest,
    AgentQueryResponse,
    AuditEventResponse,
    BreachResponse,
    HealthResponse,
    RiskSummaryResponse,
    ScenarioRequest,
    ScenarioResponse,
)


def create_app(
    *, data_path: str | Path | None = None, audit_path: str | Path | None = None
) -> FastAPI:
    service = (
        RiskDataService(Path(data_path))
        if data_path
        else RiskDataService.from_default_data()
    )
    audit = AuditStore(
        audit_path or Path(__file__).resolve().parents[1] / "data" / "mirai_audit.db"
    )
    app = FastAPI(
        title="MIRAI Risk Run API",
        version="31.0.0",
        description="Synthetic approved-risk-run service for the MIRAI demo.",
    )

    def summary_or_404(as_of_date: date | None) -> dict:
        try:
            return service.get_summary(as_of_date)
        except RiskDataError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/health", response_model=HealthResponse, tags=["platform"])
    def health() -> dict:
        return {"status": "ok", "service": "mirai-risk-run-api", "version": "31.0.0"}

    @app.get("/risk/summary", response_model=RiskSummaryResponse, tags=["risk"])
    def risk_summary(as_of_date: date | None = None) -> dict:
        summary = summary_or_404(as_of_date)
        audit.record(
            summary["run_id"],
            "risk_summary_read",
            {"as_of_date": str(summary["as_of_date"])},
        )
        return summary

    @app.get("/risk/breaches", response_model=BreachResponse, tags=["risk"])
    def risk_breaches(as_of_date: date | None = None) -> dict:
        summary = summary_or_404(as_of_date)
        breaches = service.get_breaches(as_of_date)
        audit.record(
            summary["run_id"], "risk_breaches_read", {"count": len(breaches["items"])}
        )
        return breaches

    @app.post("/risk/scenario", response_model=ScenarioResponse, tags=["risk"])
    def risk_scenario(request: ScenarioRequest) -> dict:
        try:
            result = service.run_scenario(**request.model_dump())
        except RiskDataError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        audit.record(
            result["run_id"], "scenario_requested", request.model_dump(mode="json")
        )
        return result

    @app.post("/agent/query", response_model=AgentQueryResponse, tags=["agent"])
    def agent_query(request: AgentQueryRequest) -> dict:
        summary = summary_or_404(None)
        lowered = request.question.lower()
        blocked = any(
            marker in lowered
            for marker in (
                "ignore previous",
                "reveal system prompt",
                "developer message",
            )
        )
        if blocked:
            answer = "Request blocked by MIRAI prompt-safety controls. Rephrase it as a market-risk question."
            status = "blocked"
        else:
            answer = (
                f"The latest approved synthetic run is {summary['run_id']}. "
                f"HVaR is {summary['hvar']['value']:,.0f} ({summary['hvar']['consumption_pct']:.1f}% of limit) and "
                f"SVaR is {summary['svar']['value']:,.0f} ({summary['svar']['consumption_pct']:.1f}% of limit). "
                "This V31 endpoint is deterministic and auditable; the Gemini investigation workflow remains in the V30 interface."
            )
            status = "allowed"
        audit.record(
            summary["run_id"],
            "agent_query",
            {"detail": request.detail, "guardrail_status": status},
        )
        return {
            "run_id": summary["run_id"],
            "answer": answer,
            "guardrail_status": status,
        }

    @app.get(
        "/runs/{run_id}/audit-trail",
        response_model=list[AuditEventResponse],
        tags=["audit"],
    )
    def audit_trail(run_id: str) -> list[dict]:
        return audit.list_for_run(run_id)

    return app


app = create_app()
