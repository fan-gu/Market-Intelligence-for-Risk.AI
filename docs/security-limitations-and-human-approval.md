# Security, limitations and human-approval rules

## Current security posture

The public MIRAI deployment contains synthetic demonstration data only. A Gemini key is stored through environment variables or Streamlit secrets and must never be committed. The FastAPI prototype validates request schemas, blocks a small set of obvious prompt-injection phrases and records selected events in SQLite.

These are demonstration controls, not a production security boundary. The public app has no bank SSO, role-based access control, row-level entitlements, private network isolation, DLP, customer-managed encryption keys or approved retention policy.

## Mandatory rules

1. Do not enter confidential, personal, client-identifying, position-level or proprietary bank data into the public demo.
2. Treat risk-engine results and deterministic calculations as authoritative; LLM text is an interpretation requiring review.
3. Never allow the LLM to change source data, limits, model parameters, approvals or audit history.
4. Record run ID, as-of date, hierarchy scope, tool evidence, model/version and human decision for material investigations.
5. Reject or quarantine invalid, incomplete, duplicate or unauthorised runs.
6. Use an approved enterprise model endpoint and contractual no-training/data-retention controls before processing real bank information.
7. Enforce least privilege, encryption, secrets management, logging, retention and incident response in production.

## Human-approval matrix

| Activity | MIRAI may prepare | Required human authority |
|---|---|---|
| View or filter an approved run | Yes | Authenticated, entitled user in production |
| Flag a warning, breach or anomaly | Yes | Analyst validates evidence and severity |
| Produce a narrative or investigation suggestion | Yes | Risk analyst reviews before reliance or distribution |
| Run an illustrative Scenario Lab shock | Yes | Analyst accepts assumptions; result remains non-official |
| Submit an official scenario or risk result | No | Authorised risk-engine/control process |
| Create or change a limit | No | Mandate owner plus required independent approval |
| Close or downgrade an escalation | No | Named risk owner/approver with recorded rationale |
| Change IMA eligibility or regulatory treatment | No | Model-risk, regulatory-capital and supervisory governance |
| Recommend or execute a trade | Recommendation only if permitted; no execution | Trader and applicable risk/compliance approval |
| Send external or senior-management communication | Draft only | Accountable human sign-off |

## Known limitations

- All data and hierarchy records are synthetic; demo behaviour is not evidence of production accuracy.
- Book HVaR and SVaR are Euler-style parent-portfolio contributions, not independently revalued standalone measures.
- Scenario Lab uses sensitivities and approximations; it cannot capture all nonlinearities, basis effects, liquidity or model changes.
- Statistical anomaly detection has not been benchmarked; current alerts are mainly deterministic rules and thresholds.
- Grounded-answer accuracy, hallucination rate, LLM latency, token cost and analyst time saved have not been measured.
- SQLite is not immutable, highly available or suitable as a bank-wide audit platform.
- Prompt-injection protection is basic; no permission-aware RAG or content firewall is implemented.
- The FastAPI service and public Streamlit UI are not yet integrated as one production runtime.
- No claim is made that the demo satisfies FRTB, internal-model approval, privacy, outsourcing or operational-resilience obligations.

## Release gate for real data

Real data remains blocked until security architecture, data classification, SSO/RBAC, book entitlements, model-provider approval, encryption, immutable audit, retention, monitoring, penetration testing, model-risk validation and human workflow controls are independently approved.

Measured evidence and proposed targets are separated in [Business problem and target users](business-problem-and-target-users.md#success-criteria).
