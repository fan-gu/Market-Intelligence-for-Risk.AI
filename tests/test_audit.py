from mirai.audit import AuditStore


def test_audit_events_are_reconstructable(tmp_path):
    audit = AuditStore(tmp_path / "audit.db")
    event_id = audit.record("RUN-1", "risk_summary_read", {"as_of_date": "2026-08-24"})
    events = audit.list_for_run("RUN-1")
    assert events[0]["event_id"] == event_id
    assert events[0]["metadata"]["as_of_date"] == "2026-08-24"
