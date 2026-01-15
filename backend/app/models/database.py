"""SQLAlchemy database models - migrated from existing schema."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean,
    ForeignKey, Text, JSON, Index
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class Profile(Base):
    """Family member profile for authentication."""
    __tablename__ = "profiles"

    id = Column(String(32), primary_key=True)
    name = Column(String(100), nullable=False)
    pin_hash = Column(String(255), nullable=False)
    avatar = Column(String(50), default="default")
    created_at = Column(DateTime, default=datetime.utcnow)
    is_admin = Column(Boolean, default=False)

    sessions = relationship("Session", back_populates="profile")


class Session(Base):
    """Recording session - top level container."""
    __tablename__ = "sessions"

    id = Column(String(32), primary_key=True)
    profile_id = Column(String(32), ForeignKey("profiles.id"), nullable=True)
    name = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="pending")  # pending, recording, completed, error

    # Source info
    source_type = Column(String(50))  # gopro_wifi, gopro_usb, video_file
    source_path = Column(Text)

    # Video info
    video_duration_ms = Column(Integer, default=0)
    video_resolution = Column(String(20))
    video_framerate = Column(Integer)

    # Statistics
    total_shots = Column(Integer, default=0)
    total_pocketed = Column(Integer, default=0)
    total_fouls = Column(Integer, default=0)
    total_games = Column(Integer, default=0)

    # Cost tracking
    gemini_cost_usd = Column(Float, default=0.0)

    # Additional data
    calibration_data = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    extra_data = Column(JSON, nullable=True)  # Renamed from 'metadata' (reserved by SQLAlchemy)

    # Relationships
    profile = relationship("Profile", back_populates="sessions")
    shots = relationship("Shot", back_populates="session", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="session", cascade="all, delete-orphan")
    fouls = relationship("Foul", back_populates="session", cascade="all, delete-orphan")
    games = relationship("Game", back_populates="session", cascade="all, delete-orphan")
    key_frames = relationship("KeyFrame", back_populates="session", cascade="all, delete-orphan")
    trajectories = relationship("Trajectory", back_populates="session", cascade="all, delete-orphan")
    collisions = relationship("BallCollision", back_populates="session", cascade="all, delete-orphan")
    physics_analyses = relationship("PhysicsAnalysis", back_populates="session", cascade="all, delete-orphan")
    calibrations = relationship("Calibration", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_sessions_created", "created_at"),
        Index("idx_sessions_status", "status"),
    )


class Shot(Base):
    """Individual shot data."""
    __tablename__ = "shots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(32), ForeignKey("sessions.id"), nullable=False)
    shot_number = Column(Integer, nullable=False)
    game_number = Column(Integer, default=1)
    player = Column(String(50), nullable=True)

    # Timing
    timestamp_start_ms = Column(Integer)
    timestamp_end_ms = Column(Integer)
    duration_ms = Column(Integer)

    # Table states (JSON)
    table_state_before = Column(JSON)
    table_state_after = Column(JSON)

    # Cue data
    cue_stick_data = Column(JSON)
    cue_ball_trajectory = Column(JSON)
    object_ball_trajectories = Column(JSON)

    # Results
    collisions = Column(JSON)
    pocketing_events = Column(JSON)
    cushion_contacts = Column(JSON)
    balls_contacted = Column(JSON)
    balls_pocketed = Column(JSON)

    # Analysis
    derived_metrics = Column(JSON)
    pre_frame_path = Column(Text)
    post_frame_path = Column(Text)
    frames_analyzed = Column(Integer, default=0)
    analyzed = Column(Boolean, default=False)
    analysis_data = Column(JSON)
    confidence_overall = Column(Float)
    anomalies = Column(JSON)

    session = relationship("Session", back_populates="shots")
    physics_analysis = relationship("PhysicsAnalysis", back_populates="shot", uselist=False)

    __table_args__ = (
        Index("idx_shots_session", "session_id"),
        Index("idx_shots_number", "session_id", "shot_number"),
    )


class Event(Base):
    """Real-time events from Gemini or local detection."""
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(32), ForeignKey("sessions.id"), nullable=False)
    timestamp_ms = Column(Integer, nullable=False)
    event_type = Column(String(50), nullable=False)
    event_data = Column(JSON)
    processed = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    received_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="events")

    __table_args__ = (
        Index("idx_events_session", "session_id"),
        Index("idx_events_type", "event_type"),
    )


class Foul(Base):
    """Foul records."""
    __tablename__ = "fouls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(32), ForeignKey("sessions.id"), nullable=False)
    shot_id = Column(Integer, ForeignKey("shots.id"), nullable=True)
    shot_number = Column(Integer)
    timestamp_ms = Column(Integer)
    foul_type = Column(String(50))
    details = Column(JSON)

    session = relationship("Session", back_populates="fouls")


class Game(Base):
    """Game-level aggregation."""
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(32), ForeignKey("sessions.id"), nullable=False)
    game_number = Column(Integer, nullable=False)
    game_type = Column(String(50))
    started_at_ms = Column(Integer)
    ended_at_ms = Column(Integer)
    winner = Column(String(50))
    win_condition = Column(String(50))
    final_score = Column(JSON)
    player_1_type = Column(String(50))
    player_2_type = Column(String(50))

    session = relationship("Session", back_populates="games")


class KeyFrame(Base):
    """Saved video frames."""
    __tablename__ = "key_frames"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(32), ForeignKey("sessions.id"), nullable=False)
    shot_id = Column(Integer, ForeignKey("shots.id"), nullable=True)
    timestamp_ms = Column(Integer)
    frame_type = Column(String(50))  # pre_shot, post_shot, pocket, foul
    file_path = Column(Text, nullable=False)
    file_size_bytes = Column(Integer)
    resolution = Column(String(20))

    session = relationship("Session", back_populates="key_frames")


class Trajectory(Base):
    """Ball movement tracking - CV pipeline."""
    __tablename__ = "trajectories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(32), ForeignKey("sessions.id"), nullable=False)
    shot_id = Column(Integer, ForeignKey("shots.id"), nullable=True)
    ball_name = Column(String(20), nullable=False)
    track_id = Column(Integer)
    start_timestamp_ms = Column(Integer)
    end_timestamp_ms = Column(Integer)
    points = Column(JSON)  # List of [x, y, timestamp_ms, frame_number]
    total_distance = Column(Float)
    max_speed = Column(Float)

    session = relationship("Session", back_populates="trajectories")

    __table_args__ = (
        Index("idx_trajectories_session", "session_id"),
        Index("idx_trajectories_shot", "shot_id"),
    )


class BallCollision(Base):
    """Ball collision events - CV pipeline."""
    __tablename__ = "ball_collisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(32), ForeignKey("sessions.id"), nullable=False)
    shot_id = Column(Integer, ForeignKey("shots.id"), nullable=True)
    timestamp_ms = Column(Integer)
    frame_number = Column(Integer)
    position_x = Column(Float)
    position_y = Column(Float)
    ball1_name = Column(String(20))
    ball2_name = Column(String(20))
    ball1_vx_before = Column(Float)
    ball1_vy_before = Column(Float)
    ball1_vx_after = Column(Float)
    ball1_vy_after = Column(Float)
    ball2_vx_before = Column(Float)
    ball2_vy_before = Column(Float)
    ball2_vx_after = Column(Float)
    ball2_vy_after = Column(Float)
    deflection_angle = Column(Float)
    energy_transferred = Column(Float)

    session = relationship("Session", back_populates="collisions")


class PhysicsAnalysis(Base):
    """Shot-level physics validation."""
    __tablename__ = "physics_analysis"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(32), ForeignKey("sessions.id"), nullable=False)
    shot_id = Column(Integer, ForeignKey("shots.id"), nullable=False, unique=True)
    cue_initial_speed = Column(Float)
    cue_initial_speed_mph = Column(Float)
    cue_initial_angle = Column(Float)
    cue_distance_traveled = Column(Float)
    cue_final_x = Column(Float)
    cue_final_y = Column(Float)
    total_collisions = Column(Integer)
    energy_efficiency = Column(Float)
    physics_valid = Column(Boolean)
    validation_errors = Column(JSON)
    simulation_match_score = Column(Float)
    position_errors = Column(JSON)
    analysis_json = Column(JSON)

    session = relationship("Session", back_populates="physics_analyses")
    shot = relationship("Shot", back_populates="physics_analysis")

    __table_args__ = (
        Index("idx_physics_shot", "shot_id"),
    )


class Calibration(Base):
    """Table perspective calibration."""
    __tablename__ = "calibrations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(32), ForeignKey("sessions.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    corners = Column(JSON)  # 4 corner points
    perspective_matrix = Column(JSON)
    inverse_matrix = Column(JSON)
    frame_width = Column(Integer)
    frame_height = Column(Integer)

    session = relationship("Session", back_populates="calibrations")
