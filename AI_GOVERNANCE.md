# MIRAI AI governance (V31)

MIRAI analyses approved, synthetic risk results. It does not calculate official regulatory risk, approve limits, or execute trades.

- Every API read, scenario request and agent query receives an audit event linked to a run ID.
- The V31 scenario endpoint is explicitly labelled as an illustrative sensitivity proxy, not full revaluation.
- The V31 agent endpoint blocks basic prompt-injection patterns and does not expose hidden prompts.
- Secrets stay in environment variables or Streamlit secrets; they are never committed.
- A human risk manager remains responsible for conclusions and escalations.
