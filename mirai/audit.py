"""Minimal SQLite audit trail for V31 investigations."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path


class AuditStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def record(self, run_id: str, event_type: str, metadata: dict) -> int:
        created_at = datetime.now(UTC).isoformat()
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "INSERT INTO audit_events (run_id, event_type, created_at, metadata_json) VALUES (?, ?, ?, ?)",
                (run_id, event_type, created_at, json.dumps(metadata, sort_keys=True)),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def list_for_run(self, run_id: str) -> list[dict]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT event_id, run_id, event_type, created_at, metadata_json FROM audit_events WHERE run_id = ? ORDER BY event_id",
                (run_id,),
            ).fetchall()
        return [
            {
                "event_id": row[0],
                "run_id": row[1],
                "event_type": row[2],
                "created_at": datetime.fromisoformat(row[3]),
                "metadata": json.loads(row[4]),
            }
            for row in rows
        ]
