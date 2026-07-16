from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .db import connect


@dataclass
class SessionInfo:
    session_id: str
    name: str
    created_at: str
    status: str
    source_type: str
    source_path: str


class SessionManager:
    """Manages recording session lifecycle (create, update, delete)."""

    def __init__(self, db_path: Path) -> None:
        """Initialize SessionManager with database path.

        Args:
            db_path: Path to the SQLite database file.
        """
        self._db_path = db_path

    def start_session(
        self,
        name: str | None,
        source_type: str,
        source_path: str,
    ) -> SessionInfo:
        """Create and start a new recording session.

        Args:
            name: Optional session name. Auto-generated if None.
            source_type: Type of video source (e.g., "gopro_live", "video_file").
            source_path: Path or identifier for the video source.

        Returns:
            SessionInfo with the new session's details.
        """
        session_id = uuid.uuid4().hex
        created_at = datetime.now(timezone.utc).isoformat()
        session_name = name or f"Session {created_at}"
        with connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO sessions (id, name, created_at, started_at, source_type, source_path, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    session_name,
                    created_at,
                    created_at,
                    source_type,
                    source_path,
                    "recording",
                ),
            )
            conn.commit()
        return SessionInfo(
            session_id=session_id,
            name=session_name,
            created_at=created_at,
            status="recording",
            source_type=source_type,
            source_path=source_path,
        )

    def end_session(
        self,
        session_id: str,
        total_shots: int,
        total_pocketed: int,
        total_fouls: int,
        cost_usd: float,
        notes: str | None = None,
    ) -> None:
        """Mark a session as completed and record final statistics.

        Args:
            session_id: ID of the session to end.
            total_shots: Total number of shots in the session.
            total_pocketed: Total balls pocketed.
            total_fouls: Total fouls committed.
            cost_usd: Total Gemini API cost in USD.
            notes: Optional session notes.
        """
        ended_at = datetime.now(timezone.utc).isoformat()
        with connect(self._db_path) as conn:
            conn.execute(
                """
                UPDATE sessions
                SET ended_at = ?, total_shots = ?, total_pocketed = ?, total_fouls = ?,
                    gemini_cost_usd = ?, status = ?, notes = ?
                WHERE id = ?
                """,
                (
                    ended_at,
                    total_shots,
                    total_pocketed,
                    total_fouls,
                    cost_usd,
                    "completed",
                    notes,
                    session_id,
                ),
            )
            conn.commit()

    def list_sessions(self) -> list[dict[str, Any]]:
        """Retrieve all sessions ordered by creation date (newest first).

        Returns:
            List of session dictionaries with id, name, stats, and status.
        """
        with connect(self._db_path) as conn:
            cursor = conn.execute(
                """
                SELECT id, name, created_at, started_at, ended_at, total_shots, total_pocketed,
                       total_fouls, status
                FROM sessions
                ORDER BY created_at DESC
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def delete_session(self, session_id: str) -> None:
        """Delete a session and all its associated data.

        Cascades deletion to events, shots, fouls, games, and key_frames tables.

        Args:
            session_id: ID of the session to delete.
        """
        with connect(self._db_path) as conn:
            conn.execute("DELETE FROM key_frames WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM fouls WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM events WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM shots WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM games WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
