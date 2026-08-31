"""Market Risk AI Assistant V9: investigation memory and audit logging.

V9 retains V8's deterministic analytics and adds one agent-visible function:
get_recent_investigation_context().  Each completed investigation is stored in
an append-only local JSONL audit log, so relevant follow-up context can be
retrieved without treating a prior answer as current market-risk evidence.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from archive.versions import market_risk_agent_v8 as v8
from google.genai import types


VERSION = "V9"
AUDIT_LOG_PATH = Path(__file__).with_name("market_risk_investigation_audit.jsonl")
MAX_CONTEXT_RECORDS = 3
MAX_ANSWER_CHARS = 4_000


def get_dataset_context():
    """Return immutable identifiers that tie an investigation to its input data."""
    data_path = Path(v8.FILE_NAME)
    try:
        digest = hashlib.sha256(data_path.read_bytes()).hexdigest()[:16]
    except OSError:
        digest = "unavailable"

    return {
        "source_file": data_path.name,
        "as_of_date": str(v8.df.iloc[-1]["cob_date"].date()),
        "row_count": len(v8.df),
        "data_fingerprint": digest,
    }


def read_audit_log():
    """Read valid entries only; a damaged historical line must not stop the agent."""
    if not AUDIT_LOG_PATH.exists():
        return []

    records = []
    try:
        with AUDIT_LOG_PATH.open("r", encoding="utf-8") as audit_file:
            for line in audit_file:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict):
                    records.append(record)
    except OSError:
        return []
    return records


def get_recent_investigation_context():
    """Retrieve recent investigations for the current risk-engine data snapshot."""
    dataset_context = get_dataset_context()
    matching_records = [
        record
        for record in read_audit_log()
        if record.get("dataset", {}).get("data_fingerprint")
        == dataset_context["data_fingerprint"]
    ]
    recent_records = matching_records[-MAX_CONTEXT_RECORDS:]

    return {
        "dataset": dataset_context,
        "matching_investigation_count": len(matching_records),
        "recent_investigations": [
            {
                "timestamp_utc": record.get("timestamp_utc"),
                "question": record.get("question"),
                "tools_used": record.get("tools_used", []),
                "answer": record.get("answer"),
            }
            for record in recent_records
        ],
        "usage_note": (
            "This is prior investigation context, not current financial evidence. "
            "Use deterministic analytics tools to support all current risk facts."
        ),
    }


def write_audit_record(question, plan, results, additional_results, answer):
    """Append a traceable record after a completed investigation."""
    record = {
        "version": VERSION,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": get_dataset_context(),
        "question": question,
        "plan": plan,
        "tools_used": list(results) + list(additional_results),
        "observed_results": results,
        "additional_results": additional_results,
        "answer": answer[:MAX_ANSWER_CHARS],
    }
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as audit_file:
        audit_file.write(json.dumps(record, ensure_ascii=False) + "\n")


# Register V9's single new agent function alongside V8's analytics tools.
v8.TOOL_FUNCTIONS["get_recent_investigation_context"] = get_recent_investigation_context
v8.TOOL_DESCRIPTIONS["get_recent_investigation_context"] = (
    "Recent completed investigations for the same risk-engine data snapshot. "
    "Use for follow-up questions; current financial claims still require analytics tools."
)

tools = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(name=name, description=description)
            for name, description in v8.TOOL_DESCRIPTIONS.items()
        ]
    )
]

SYSTEM_INSTRUCTION = v8.SYSTEM_INSTRUCTION + """

V9 memory control:
- get_recent_investigation_context provides auditable prior conversation context
  only for the identical input-data fingerprint.
- Do not present a previous answer or remembered number as current evidence.
- For every current financial fact, use a deterministic analytics tool result
  from this investigation.
"""


def ask_risk_agent(question):
    plan = v8.create_investigation_plan(question)
    v8.print_plan(plan)
    results = v8.execute_plan(plan)

    chat = v8.client.chats.create(
        model=v8.MODEL_NAME,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=tools,
        ),
    )
    evidence = json.dumps(results, indent=2)
    response = chat.send_message(
        f"User question: {question}\n\n"
        f"Approved investigation plan: {json.dumps(plan)}\n\n"
        f"Observed deterministic tool results:\n{evidence}\n\n"
        "Review the observed results. Request another tool only if it is needed "
        "to complete the requested assessment."
    )

    additional_results = {}
    while response.function_calls:
        print("\n[ADDITIONAL INVESTIGATION]\n")
        function_responses = []
        for function_call in response.function_calls:
            function_name = function_call.name
            print(f"→ {function_name}()")
            result = v8.execute_tool(function_name)
            additional_results[function_name] = result
            function_responses.append(
                types.Part.from_function_response(
                    name=function_name,
                    response={"result": result},
                )
            )
        response = chat.send_message(function_responses)

    answer = response.text
    write_audit_record(question, plan, results, additional_results, answer)
    print("\n[AGENT SYNTHESIS]\n")
    return answer


def main():
    print("\n" + "=" * 70)
    print("             MARKET RISK AI ASSISTANT")
    print("                         V9")
    print("=" * 70)
    print("\n10-day / 54-column dataset loaded.")
    print("Gemini planning agent with investigation memory is ready.")
    print("Completed investigations are written to a local audit log.")
    print("Type 'exit' to stop.\n")

    while True:
        question = input("You: ")
        if question.lower().strip() == "exit":
            print("Assistant: Goodbye.")
            break

        try:
            answer = ask_risk_agent(question)
            print("Assistant:")
            print(answer)
            print()
        except Exception as error:
            print("\nERROR:")
            print(error)
            print()


if __name__ == "__main__":
    main()
