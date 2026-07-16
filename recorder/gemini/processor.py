from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from PyQt6 import QtCore


@dataclass
class EventRecord:
    timestamp_ms: int
    event_type: str
    event_data: dict[str, Any]
    received_at: str


class EventProcessor(QtCore.QObject):
    event_ready = QtCore.pyqtSignal(object)
    error = QtCore.pyqtSignal(str)

    def __init__(
        self,
        db_path: str | None = None,
        session_id: str | None = None,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._session_id = session_id
        self._conn: sqlite3.Connection | None = None
        if db_path:
            # check_same_thread=False allows connection to be used from signal handlers
            # that may be invoked from different threads (e.g., GeminiClient thread)
            self._conn = sqlite3.connect(db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def set_session(self, session_id: str | None) -> None:
        self._session_id = session_id

    def process_raw(self, raw_message: str) -> EventRecord | None:
        try:
            payload = json.loads(raw_message)
        except json.JSONDecodeError as exc:
            self.error.emit(f"Invalid JSON from Gemini: {exc}")
            return None
        return self.process_event(payload)

    def process_event(self, payload: dict[str, Any]) -> EventRecord | None:
        event_type = payload.get("event_type") or payload.get("type") or "UNKNOWN"
        timestamp = payload.get("timestamp_ms") or payload.get("timestamp") or 0
        record = EventRecord(
            timestamp_ms=int(timestamp),
            event_type=str(event_type),
            event_data=payload,
            received_at=datetime.now(timezone.utc).isoformat(),
        )
        if self._conn and self._session_id:
            self._insert_event(record)
        self.event_ready.emit(record)
        return record

    def _insert_event(self, record: EventRecord) -> None:
        if not self._conn:
            return
        self._conn.execute(
            """
            INSERT INTO events (session_id, timestamp_ms, event_type, event_data, received_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                self._session_id,
                record.timestamp_ms,
                record.event_type,
                json.dumps(record.event_data),
                record.received_at,
            ),
        )
        self._conn.commit()
