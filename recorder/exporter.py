from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List

from .db import connect


class ExportManager:
    """Exports session data in various formats (JSON, CSV, JSONL)."""

    def __init__(self, db_path: Path) -> None:
        """Initialize ExportManager with database path.

        Args:
            db_path: Path to the SQLite database file.
        """
        self._db_path = db_path

    def export_full_json(self, session_id: str, destination: Path) -> None:
        """Export complete session data including all related tables.

        Includes: session, shots, events, fouls, games, key_frames.

        Args:
            session_id: ID of the session to export.
            destination: Output file path for the JSON export.
        """
        payload = {
            "session": self._fetch_one(
                "SELECT * FROM sessions WHERE id = ?",
                (session_id,),
            ),
            "shots": self._fetch_all(
                "SELECT * FROM shots WHERE session_id = ? ORDER BY shot_number",
                (session_id,),
            ),
            "events": self._fetch_all(
                "SELECT * FROM events WHERE session_id = ? ORDER BY timestamp_ms",
                (session_id,),
            ),
            "fouls": self._fetch_all(
                "SELECT * FROM fouls WHERE session_id = ? ORDER BY timestamp_ms",
                (session_id,),
            ),
            "games": self._fetch_all(
                "SELECT * FROM games WHERE session_id = ? ORDER BY game_number",
                (session_id,),
            ),
            "key_frames": self._fetch_all(
                "SELECT * FROM key_frames WHERE session_id = ? ORDER BY timestamp_ms",
                (session_id,),
            ),
        }
        destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def export_claude_json(self, session_id: str, destination: Path) -> None:
        """Export session data optimized for Claude analysis.

        Includes only: session, shots, events (no fouls, games, key_frames).

        Args:
            session_id: ID of the session to export.
            destination: Output file path for the JSON export.
        """
        payload = {
            "session": self._fetch_one(
                "SELECT * FROM sessions WHERE id = ?",
                (session_id,),
            ),
            "shots": self._fetch_all(
                "SELECT * FROM shots WHERE session_id = ? ORDER BY shot_number",
                (session_id,),
            ),
            "events": self._fetch_all(
                "SELECT * FROM events WHERE session_id = ? ORDER BY timestamp_ms",
                (session_id,),
            ),
        }
        destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def export_shots_csv(self, session_id: str, destination: Path) -> None:
        """Export shots table as CSV for spreadsheet analysis.

        Args:
            session_id: ID of the session to export.
            destination: Output file path for the CSV export.
        """
        rows = self._fetch_all(
            "SELECT * FROM shots WHERE session_id = ? ORDER BY shot_number",
            (session_id,),
        )
        if not rows:
            destination.write_text("", encoding="utf-8")
            return
        fieldnames = list(rows[0].keys())
        with destination.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def export_events_jsonl(self, session_id: str, destination: Path) -> None:
        """Export events as JSONL (one JSON object per line).

        Useful for streaming processing or log analysis tools.

        Args:
            session_id: ID of the session to export.
            destination: Output file path for the JSONL export.
        """
        rows = self._fetch_all(
            "SELECT * FROM events WHERE session_id = ? ORDER BY timestamp_ms",
            (session_id,),
        )
        with destination.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row))
                handle.write("\n")

    def _fetch_one(self, query: str, params: tuple) -> Dict[str, Any]:
        with connect(self._db_path) as conn:
            row = conn.execute(query, params).fetchone()
            return dict(row) if row else {}

    def _fetch_all(self, query: str, params: tuple) -> List[Dict[str, Any]]:
        with connect(self._db_path) as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
