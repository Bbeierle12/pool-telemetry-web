from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .config import AppConfig

logger = logging.getLogger(__name__)

# Current schema version - increment when schema changes
SCHEMA_VERSION = 2

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        applied_at DATETIME
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        name TEXT,
        created_at DATETIME,
        started_at DATETIME,
        ended_at DATETIME,
        source_type TEXT,
        source_path TEXT,
        video_duration_ms INTEGER,
        video_resolution TEXT,
        video_framerate REAL,
        calibration_data TEXT,
        total_shots INTEGER,
        total_pocketed INTEGER,
        total_fouls INTEGER,
        total_games INTEGER,
        gemini_cost_usd REAL,
        status TEXT,
        notes TEXT,
        metadata TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS shots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT REFERENCES sessions(id),
        shot_number INTEGER,
        game_number INTEGER,
        player INTEGER,
        timestamp_start_ms INTEGER,
        timestamp_end_ms INTEGER,
        duration_ms INTEGER,
        table_state_before TEXT,
        table_state_after TEXT,
        cue_stick_data TEXT,
        cue_ball_trajectory TEXT,
        object_ball_trajectories TEXT,
        collisions TEXT,
        pocketing_events TEXT,
        cushion_contacts INTEGER,
        balls_contacted TEXT,
        balls_pocketed TEXT,
        derived_metrics TEXT,
        confidence_overall REAL,
        frames_analyzed INTEGER,
        anomalies TEXT,
        pre_frame_path TEXT,
        post_frame_path TEXT,
        analyzed BOOLEAN DEFAULT 0,
        analysis_data TEXT,
        created_at DATETIME
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT REFERENCES sessions(id),
        timestamp_ms INTEGER,
        event_type TEXT,
        event_data TEXT,
        processed BOOLEAN DEFAULT 0,
        error_message TEXT,
        received_at DATETIME
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fouls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT REFERENCES sessions(id),
        shot_id INTEGER REFERENCES shots(id),
        shot_number INTEGER,
        timestamp_ms INTEGER,
        foul_type TEXT,
        details TEXT,
        created_at DATETIME
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT REFERENCES sessions(id),
        game_number INTEGER,
        game_type TEXT,
        started_at_ms INTEGER,
        ended_at_ms INTEGER,
        winner INTEGER,
        win_condition TEXT,
        player_1_type TEXT,
        player_2_type TEXT,
        final_score TEXT,
        created_at DATETIME
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS key_frames (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT REFERENCES sessions(id),
        shot_id INTEGER REFERENCES shots(id),
        timestamp_ms INTEGER,
        frame_type TEXT,
        file_path TEXT,
        file_size_bytes INTEGER,
        resolution TEXT,
        created_at DATETIME
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_shots_session_id ON shots(session_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_events_session_id ON events(session_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_fouls_session_id ON fouls(session_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_games_session_id ON games(session_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_key_frames_session_id ON key_frames(session_id)
    """,
    # New tables for local CV pipeline (schema version 2)
    """
    CREATE TABLE IF NOT EXISTS trajectories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT REFERENCES sessions(id),
        shot_id INTEGER REFERENCES shots(id),
        ball_name TEXT,
        track_id INTEGER,
        points TEXT,
        start_timestamp_ms INTEGER,
        end_timestamp_ms INTEGER,
        total_distance REAL,
        max_speed REAL,
        created_at DATETIME
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ball_collisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT REFERENCES sessions(id),
        shot_id INTEGER REFERENCES shots(id),
        timestamp_ms INTEGER,
        frame_number INTEGER,
        ball1_name TEXT,
        ball2_name TEXT,
        ball1_track_id INTEGER,
        ball2_track_id INTEGER,
        position_x REAL,
        position_y REAL,
        ball1_vx_before REAL,
        ball1_vy_before REAL,
        ball1_vx_after REAL,
        ball1_vy_after REAL,
        ball2_vx_before REAL,
        ball2_vy_before REAL,
        ball2_vx_after REAL,
        ball2_vy_after REAL,
        deflection_angle REAL,
        energy_transferred REAL,
        created_at DATETIME
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS physics_analysis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT REFERENCES sessions(id),
        shot_id INTEGER REFERENCES shots(id),
        cue_initial_speed REAL,
        cue_initial_speed_mph REAL,
        cue_initial_angle REAL,
        cue_distance_traveled REAL,
        cue_final_x REAL,
        cue_final_y REAL,
        total_collisions INTEGER,
        energy_efficiency REAL,
        physics_valid BOOLEAN,
        validation_errors TEXT,
        simulation_match_score REAL,
        position_errors TEXT,
        analysis_json TEXT,
        created_at DATETIME
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS calibrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT REFERENCES sessions(id),
        corners TEXT,
        perspective_matrix TEXT,
        inverse_matrix TEXT,
        frame_width INTEGER,
        frame_height INTEGER,
        created_at DATETIME
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_trajectories_session_id ON trajectories(session_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_trajectories_shot_id ON trajectories(shot_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_ball_collisions_session_id ON ball_collisions(session_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_ball_collisions_shot_id ON ball_collisions(shot_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_physics_analysis_session_id ON physics_analysis(session_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_physics_analysis_shot_id ON physics_analysis(shot_id)
    """,
]


def get_db_path(config: AppConfig) -> Path:
    """Get the database file path from configuration.

    Args:
        config: Application configuration.

    Returns:
        Path to the SQLite database file.
    """
    return Path(config.storage.data_directory) / "database.sqlite"


def connect(db_path: Path) -> sqlite3.Connection:
    """Open a connection to the SQLite database.

    Creates parent directories if needed. Sets row_factory to sqlite3.Row
    for dict-like row access.

    Args:
        db_path: Path to the database file.

    Returns:
        SQLite connection with Row factory configured.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(config: AppConfig) -> sqlite3.Connection:
    """Initialize the database with schema and pragmas.

    Creates all tables and indexes if they don't exist. Safe to call
    multiple times (idempotent).

    Args:
        config: Application configuration.

    Returns:
        Open database connection (caller should close when done).
    """
    db_path = get_db_path(config)
    conn = connect(db_path)
    _apply_pragmas(conn)
    _initialize_schema(conn, SCHEMA_STATEMENTS)
    _check_schema_version(conn)
    return conn


def insert_event(
    conn: sqlite3.Connection,
    session_id: str,
    timestamp_ms: int,
    event_type: str,
    event_data: dict,
) -> None:
    """Insert an event record into the events table.

    Args:
        conn: Database connection.
        session_id: ID of the session this event belongs to.
        timestamp_ms: Event timestamp in milliseconds.
        event_type: Type of event (e.g., "SHOT_START", "POCKET").
        event_data: Event payload as a dictionary (will be JSON-serialized).
    """
    conn.execute(
        """
        INSERT INTO events (session_id, timestamp_ms, event_type, event_data, received_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            session_id,
            timestamp_ms,
            event_type,
            json.dumps(event_data),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()


def insert_trajectory(
    conn: sqlite3.Connection,
    session_id: str,
    shot_id: int,
    ball_name: str,
    track_id: int,
    points: list[tuple[float, float, int, int]],
    total_distance: float,
    max_speed: float,
) -> int:
    """Insert a ball trajectory record.

    Args:
        conn: Database connection.
        session_id: Session ID.
        shot_id: Shot ID this trajectory belongs to.
        ball_name: Name of the ball (e.g., "cue", "solid_1").
        track_id: Tracker ID for this ball.
        points: List of (x, y, timestamp_ms, frame_number) tuples.
        total_distance: Total distance traveled in table units.
        max_speed: Maximum speed during trajectory.

    Returns:
        ID of the inserted trajectory.
    """
    start_ts = points[0][2] if points else 0
    end_ts = points[-1][2] if points else 0

    cursor = conn.execute(
        """
        INSERT INTO trajectories (
            session_id, shot_id, ball_name, track_id, points,
            start_timestamp_ms, end_timestamp_ms, total_distance, max_speed, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            shot_id,
            ball_name,
            track_id,
            json.dumps(points),
            start_ts,
            end_ts,
            total_distance,
            max_speed,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    return cursor.lastrowid


def insert_collision(
    conn: sqlite3.Connection,
    session_id: str,
    shot_id: int,
    timestamp_ms: int,
    frame_number: int,
    ball1_name: str,
    ball2_name: str,
    ball1_track_id: int,
    ball2_track_id: int,
    position: tuple[float, float],
    ball1_vel_before: tuple[float, float],
    ball1_vel_after: tuple[float, float],
    ball2_vel_before: tuple[float, float],
    ball2_vel_after: tuple[float, float],
    deflection_angle: float = 0.0,
    energy_transferred: float = 0.0,
) -> int:
    """Insert a ball collision record.

    Args:
        conn: Database connection.
        session_id: Session ID.
        shot_id: Shot ID.
        timestamp_ms: Collision timestamp.
        frame_number: Frame number.
        ball1_name: First ball name.
        ball2_name: Second ball name.
        ball1_track_id: First ball track ID.
        ball2_track_id: Second ball track ID.
        position: Collision position (x, y).
        ball1_vel_before: Ball 1 velocity before (vx, vy).
        ball1_vel_after: Ball 1 velocity after (vx, vy).
        ball2_vel_before: Ball 2 velocity before (vx, vy).
        ball2_vel_after: Ball 2 velocity after (vx, vy).
        deflection_angle: Deflection angle in degrees.
        energy_transferred: Energy transferred estimate.

    Returns:
        ID of the inserted collision.
    """
    cursor = conn.execute(
        """
        INSERT INTO ball_collisions (
            session_id, shot_id, timestamp_ms, frame_number,
            ball1_name, ball2_name, ball1_track_id, ball2_track_id,
            position_x, position_y,
            ball1_vx_before, ball1_vy_before, ball1_vx_after, ball1_vy_after,
            ball2_vx_before, ball2_vy_before, ball2_vx_after, ball2_vy_after,
            deflection_angle, energy_transferred, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            shot_id,
            timestamp_ms,
            frame_number,
            ball1_name,
            ball2_name,
            ball1_track_id,
            ball2_track_id,
            position[0],
            position[1],
            ball1_vel_before[0],
            ball1_vel_before[1],
            ball1_vel_after[0],
            ball1_vel_after[1],
            ball2_vel_before[0],
            ball2_vel_before[1],
            ball2_vel_after[0],
            ball2_vel_after[1],
            deflection_angle,
            energy_transferred,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    return cursor.lastrowid


def insert_physics_analysis(
    conn: sqlite3.Connection,
    session_id: str,
    shot_id: int,
    analysis: dict,
) -> int:
    """Insert physics analysis for a shot.

    Args:
        conn: Database connection.
        session_id: Session ID.
        shot_id: Shot ID.
        analysis: Analysis data dict with fields matching ShotAnalysis.

    Returns:
        ID of the inserted analysis.
    """
    cursor = conn.execute(
        """
        INSERT INTO physics_analysis (
            session_id, shot_id, cue_initial_speed, cue_initial_speed_mph,
            cue_initial_angle, cue_distance_traveled, cue_final_x, cue_final_y,
            total_collisions, energy_efficiency, physics_valid,
            validation_errors, simulation_match_score, position_errors,
            analysis_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            shot_id,
            analysis.get("cue_initial_speed", 0),
            analysis.get("cue_initial_speed_mph", 0),
            analysis.get("cue_initial_angle", 0),
            analysis.get("cue_distance_traveled", 0),
            analysis.get("cue_final_position", (0, 0))[0],
            analysis.get("cue_final_position", (0, 0))[1],
            analysis.get("total_collisions", 0),
            analysis.get("energy_efficiency", 0),
            analysis.get("physics_valid", True),
            json.dumps(analysis.get("validation_errors", [])),
            analysis.get("simulation_match_score"),
            json.dumps(analysis.get("position_errors", {})),
            json.dumps(analysis),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    return cursor.lastrowid


def insert_calibration(
    conn: sqlite3.Connection,
    session_id: str,
    corners: list[tuple[float, float]],
    perspective_matrix: list | None,
    inverse_matrix: list | None,
    frame_width: int,
    frame_height: int,
) -> int:
    """Insert calibration data for a session.

    Args:
        conn: Database connection.
        session_id: Session ID.
        corners: Four corner points in pixel coordinates.
        perspective_matrix: 3x3 perspective transform matrix (as list).
        inverse_matrix: 3x3 inverse transform matrix (as list).
        frame_width: Video frame width.
        frame_height: Video frame height.

    Returns:
        ID of the inserted calibration.
    """
    cursor = conn.execute(
        """
        INSERT INTO calibrations (
            session_id, corners, perspective_matrix, inverse_matrix,
            frame_width, frame_height, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            json.dumps(corners),
            json.dumps(perspective_matrix) if perspective_matrix else None,
            json.dumps(inverse_matrix) if inverse_matrix else None,
            frame_width,
            frame_height,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    return cursor.lastrowid


def get_calibration(conn: sqlite3.Connection, session_id: str) -> dict | None:
    """Get the latest calibration for a session.

    Args:
        conn: Database connection.
        session_id: Session ID.

    Returns:
        Calibration dict or None if not found.
    """
    row = conn.execute(
        """
        SELECT * FROM calibrations
        WHERE session_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (session_id,),
    ).fetchone()

    if row:
        return {
            "id": row["id"],
            "session_id": row["session_id"],
            "corners": json.loads(row["corners"]) if row["corners"] else [],
            "perspective_matrix": json.loads(row["perspective_matrix"]) if row["perspective_matrix"] else None,
            "inverse_matrix": json.loads(row["inverse_matrix"]) if row["inverse_matrix"] else None,
            "frame_width": row["frame_width"],
            "frame_height": row["frame_height"],
        }
    return None


def get_shot_trajectories(conn: sqlite3.Connection, shot_id: int) -> list[dict]:
    """Get all trajectories for a shot.

    Args:
        conn: Database connection.
        shot_id: Shot ID.

    Returns:
        List of trajectory dicts.
    """
    rows = conn.execute(
        """
        SELECT * FROM trajectories
        WHERE shot_id = ?
        ORDER BY ball_name
        """,
        (shot_id,),
    ).fetchall()

    return [
        {
            "id": row["id"],
            "ball_name": row["ball_name"],
            "track_id": row["track_id"],
            "points": json.loads(row["points"]) if row["points"] else [],
            "start_timestamp_ms": row["start_timestamp_ms"],
            "end_timestamp_ms": row["end_timestamp_ms"],
            "total_distance": row["total_distance"],
            "max_speed": row["max_speed"],
        }
        for row in rows
    ]


def get_shot_collisions(conn: sqlite3.Connection, shot_id: int) -> list[dict]:
    """Get all collisions for a shot.

    Args:
        conn: Database connection.
        shot_id: Shot ID.

    Returns:
        List of collision dicts.
    """
    rows = conn.execute(
        """
        SELECT * FROM ball_collisions
        WHERE shot_id = ?
        ORDER BY timestamp_ms
        """,
        (shot_id,),
    ).fetchall()

    return [
        {
            "id": row["id"],
            "timestamp_ms": row["timestamp_ms"],
            "frame_number": row["frame_number"],
            "ball1_name": row["ball1_name"],
            "ball2_name": row["ball2_name"],
            "position": (row["position_x"], row["position_y"]),
            "deflection_angle": row["deflection_angle"],
        }
        for row in rows
    ]


def get_physics_analysis(conn: sqlite3.Connection, shot_id: int) -> dict | None:
    """Get physics analysis for a shot.

    Args:
        conn: Database connection.
        shot_id: Shot ID.

    Returns:
        Analysis dict or None if not found.
    """
    row = conn.execute(
        """
        SELECT * FROM physics_analysis
        WHERE shot_id = ?
        """,
        (shot_id,),
    ).fetchone()

    if row:
        return {
            "id": row["id"],
            "cue_initial_speed": row["cue_initial_speed"],
            "cue_initial_speed_mph": row["cue_initial_speed_mph"],
            "cue_initial_angle": row["cue_initial_angle"],
            "cue_distance_traveled": row["cue_distance_traveled"],
            "cue_final_position": (row["cue_final_x"], row["cue_final_y"]),
            "total_collisions": row["total_collisions"],
            "physics_valid": row["physics_valid"],
            "validation_errors": json.loads(row["validation_errors"]) if row["validation_errors"] else [],
            "simulation_match_score": row["simulation_match_score"],
            "full_analysis": json.loads(row["analysis_json"]) if row["analysis_json"] else {},
        }
    return None


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")


def _initialize_schema(conn: sqlite3.Connection, statements: Iterable[str]) -> None:
    for statement in statements:
        conn.execute(statement)
    conn.commit()


def _get_schema_version(conn: sqlite3.Connection) -> int:
    """Get the current schema version from the database.

    Returns:
        Schema version number, or 0 if not set.
    """
    try:
        row = conn.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
        return row[0] or 0
    except sqlite3.OperationalError:
        # Table doesn't exist yet
        return 0


def _set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    """Record the schema version in the database."""
    conn.execute(
        "INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (?, ?)",
        (version, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def _check_schema_version(conn: sqlite3.Connection) -> None:
    """Check and log schema version status."""
    db_version = _get_schema_version(conn)

    if db_version == 0:
        # Fresh database, set initial version
        _set_schema_version(conn, SCHEMA_VERSION)
        logger.info("Initialized database schema version %d", SCHEMA_VERSION)
    elif db_version < SCHEMA_VERSION:
        # Database needs migration (future feature)
        logger.warning(
            "Database schema version %d is older than application version %d. "
            "Migration may be needed.",
            db_version,
            SCHEMA_VERSION,
        )
        # For now, just update the version (no actual migration logic yet)
        _set_schema_version(conn, SCHEMA_VERSION)
    elif db_version > SCHEMA_VERSION:
        logger.warning(
            "Database schema version %d is newer than application version %d. "
            "You may be using an older application version.",
            db_version,
            SCHEMA_VERSION,
        )
