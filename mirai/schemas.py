"""Typed API contracts for the MIRAI risk-run service."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str


class LimitMetric(BaseModel):
    metric: str
    value: float
    limit: float
    consumption_pct: float
    status: Literal["OK", "WARNING", "BREACH"]


class RiskSummaryResponse(BaseModel):
    run_id: str
    as_of_date: date
    reporting_currency: str
    pnl: float
    hvar: LimitMetric
    svar: LimitMetric


class BreachResponse(BaseModel):
    run_id: str
    as_of_date: date
    items: list[LimitMetric]


class ScenarioRequest(BaseModel):
    as_of_date: date | None = None
    rate_shock_bp: float = Field(default=0.0, ge=-500, le=500)
    fx_spot_move_pct: float = Field(default=0.0, ge=-50, le=50)
    volatility_shock_pct: float = Field(default=0.0, ge=-100, le=200)
    severity: Literal["Adverse", "Extreme"] = "Adverse"


class ScenarioResponse(BaseModel):
    run_id: str
    as_of_date: date
    estimated_pnl: float
    methodology: str
    is_official_risk_result: Literal[False] = False


class AgentQueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    detail: Literal["succinct", "moderate", "detailed"] = "moderate"


class AgentQueryResponse(BaseModel):
    run_id: str
    answer: str
    guardrail_status: Literal["allowed", "blocked"]


class AuditEventResponse(BaseModel):
    event_id: int
    run_id: str
    event_type: str
    created_at: datetime
    metadata: dict
