# Business problem and target users

## Problem

Market-risk managers receive large risk-engine outputs across books, desks and business lines. Existing reporting can make it slow to identify material movements, connect VaR, P&L, sensitivities and stress results, and reconstruct why an escalation was raised. Generic chatbots add another risk: fluent answers that are not tied to approved figures.

MIRAI is a downstream risk-analysis cockpit. It does not replace pricing or risk engines. It validates and organises supplied results, applies deterministic controls, presents drill-down analysis, and lets an analyst ask questions whose numerical evidence comes from governed tools.

## Target users

| User | Primary need | MIRAI outcome |
|---|---|---|
| Market-risk manager | Bank-to-book overview and fast prioritisation | Dashboard, hierarchy filters, warnings and breaches |
| Desk risk analyst | Explain daily changes and investigate drivers | VaR/P&L attribution, sensitivities, stress history and Scenario Lab |
| Risk controller | Verify runs, limits and exceptions | Data-quality checks, reconciliation, lineage and audit trail |
| Senior risk approver | Review evidence before decisions | Concise risk brief, severity ordering and explicit approval gates |
| Model-risk, audit and technology teams | Reconstruct behaviour and challenge controls | Deterministic calculations, documented limitations, API tests and logs |

MIRAI is not intended for autonomous trading, limit approval, regulatory submission or replacement of independent model validation.

## Success criteria

### Measured baseline — 11 September 2026

These are observations from the current repository, not estimates of production performance.

| Measure | Current result | Test boundary |
|---|---:|---|
| Automated tests | 13 passing | GitHub CI on Python 3.12 |
| Service-layer test coverage | 92% | `pytest --cov=mirai`; not whole-dashboard coverage |
| Granular data reconciliation | Maximum absolute error `3.73e-9` | 5,200 synthetic book/date records; additive fields only |
| `GET /health` latency | p50 5.54 ms; p95 7.19 ms | 100 local in-process requests after five warm-ups |
| `GET /risk/summary` latency | p50 30.78 ms; p95 33.42 ms | Same local benchmark; includes temporary SQLite audit writes |
| `GET /risk/breaches` latency | p50 45.71 ms; p95 49.89 ms | Same local benchmark |
| `POST /risk/scenario` latency | p50 30.45 ms; p95 35.73 ms | Same local benchmark; deterministic approximation only |
| Anomaly-detection accuracy | Not measured | No labelled anomaly benchmark exists yet |
| Grounded-answer rate | Not measured | No question/evidence evaluation set exists yet |
| LLM cost | Not measured | Token and request-cost telemetry is not implemented |
| Analyst time saved | Not measured | No controlled user study has been run |

Local in-process latency excludes network, browser rendering, cold starts and Gemini response time. It must not be presented as public-cloud performance.

### Proposed targets — assumptions until validated

| Outcome | Acceptance target | Measurement method |
|---|---:|---|
| Anomaly detection | Precision ≥90%, recall ≥85%, F1 ≥0.87 | At least 500 labelled observations, scored separately by anomaly class |
| Grounded answers | ≥95% grounded-answer rate; 100% numerical agreement for cited fields | At least 200 representative questions; unsupported material claims fail |
| Response time | Deterministic API p95 <1 s; succinct AI p95 <15 s; detailed AI p95 <30 s | Hosted end-to-end telemetry including cold starts and model latency |
| Cost | Median ≤EUR 0.05 and p95 ≤EUR 0.10 per AI investigation | Record model, tokens, tool calls and applicable provider price |
| Analyst time saved | Median investigation time reduced by ≥30%, with no loss of control accuracy | Paired study with at least 10 analysts |
| Operational quality | No unreviewed action or limit change; 100% of AI investigations auditable | Audit-log and approval-workflow review |

Targets are product hypotheses. They become measured results only after the stated protocol, sample size, environment and date are recorded.
