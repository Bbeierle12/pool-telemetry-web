"""Shot detection based on ball motion states."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Sequence

import numpy as np

from ..cv.tracker import TrackedBall

logger = logging.getLogger(__name__)

# Detection thresholds
SHOT_START_VELOCITY = 5.0      # Minimum cue ball velocity to start shot
STATIONARY_THRESHOLD = 2.0     # Velocity below which ball is stationary
STATIONARY_FRAMES = 15         # Frames balls must be stationary to end shot
MIN_SHOT_DURATION_FRAMES = 10  # Minimum frames for valid shot


class ShotState(Enum):
    """Current state of shot detection."""

    IDLE = auto()           # Waiting for shot to start
    IN_PROGRESS = auto()    # Shot is in progress (balls moving)
    SETTLING = auto()       # Balls slowing down, checking if stationary


@dataclass
class TableState:
    """Snapshot of ball positions on the table."""

    balls: list[dict]  # [{ball_id, class_name, x, y}, ...]
    timestamp_ms: int
    frame_number: int

    @classmethod
    def from_tracks(
        cls,
        tracks: Sequence[TrackedBall],
        timestamp_ms: int,
        frame_number: int,
    ) -> TableState:
        """Create table state from tracked balls."""
        balls = []
        for track in tracks:
            balls.append({
                "track_id": track.track_id,
                "class_name": track.class_name,
                "x": track.x,
                "y": track.y,
                "vx": track.vx,
                "vy": track.vy,
            })
        return cls(balls=balls, timestamp_ms=timestamp_ms, frame_number=frame_number)


@dataclass
class ShotData:
    """Data for a detected shot."""

    shot_number: int
    start_timestamp_ms: int
    end_timestamp_ms: int
    start_frame: int
    end_frame: int
    duration_ms: int
    duration_frames: int

    # Table states
    table_state_before: TableState
    table_state_after: TableState

    # Cue ball data
    cue_start_x: float
    cue_start_y: float
    cue_initial_vx: float
    cue_initial_vy: float
    cue_initial_speed: float
    cue_trajectory: list[tuple[float, float, int, int]]  # [(x, y, timestamp, frame), ...]

    # All ball trajectories during shot
    all_trajectories: dict[int, list[tuple[float, float, int, int]]] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        """Shot duration in seconds."""
        return self.duration_ms / 1000.0


class ShotDetector:
    """Detects shot start and end based on ball motion."""

    def __init__(
        self,
        shot_start_velocity: float = SHOT_START_VELOCITY,
        stationary_threshold: float = STATIONARY_THRESHOLD,
        stationary_frames: int = STATIONARY_FRAMES,
        min_shot_duration: int = MIN_SHOT_DURATION_FRAMES,
    ) -> None:
        """Initialize shot detector.

        Args:
            shot_start_velocity: Minimum cue ball velocity to trigger shot start.
            stationary_threshold: Velocity below which a ball is stationary.
            stationary_frames: Frames balls must be stationary to end shot.
            min_shot_duration: Minimum frames for a valid shot.
        """
        self._shot_start_velocity = shot_start_velocity
        self._stationary_threshold = stationary_threshold
        self._stationary_frames_needed = stationary_frames
        self._min_shot_duration = min_shot_duration

        self._state = ShotState.IDLE
        self._shot_count = 0

        # Current shot tracking
        self._shot_start_timestamp: int = 0
        self._shot_start_frame: int = 0
        self._table_state_before: TableState | None = None
        self._cue_start_position: tuple[float, float] | None = None
        self._cue_initial_velocity: tuple[float, float] | None = None
        self._cue_trajectory: list[tuple[float, float, int, int]] = []
        self._all_trajectories: dict[int, list[tuple[float, float, int, int]]] = {}

        # Stationary detection
        self._stationary_frame_count = 0
        self._last_table_state: TableState | None = None

    @property
    def state(self) -> ShotState:
        """Get current shot state."""
        return self._state

    @property
    def shot_count(self) -> int:
        """Get total shots detected."""
        return self._shot_count

    def reset(self) -> None:
        """Reset detector state."""
        self._state = ShotState.IDLE
        self._shot_count = 0
        self._clear_shot_data()

    def _clear_shot_data(self) -> None:
        """Clear current shot tracking data."""
        self._shot_start_timestamp = 0
        self._shot_start_frame = 0
        self._table_state_before = None
        self._cue_start_position = None
        self._cue_initial_velocity = None
        self._cue_trajectory = []
        self._all_trajectories = {}
        self._stationary_frame_count = 0

    def update(
        self,
        tracks: Sequence[TrackedBall],
        timestamp_ms: int,
        frame_number: int,
    ) -> ShotData | None:
        """Process new frame and detect shot events.

        Args:
            tracks: Current tracked balls.
            timestamp_ms: Current timestamp.
            frame_number: Current frame number.

        Returns:
            ShotData if a shot just completed, None otherwise.
        """
        # Find cue ball
        cue_ball = next((t for t in tracks if t.is_cue), None)

        # Get current table state
        current_state = TableState.from_tracks(tracks, timestamp_ms, frame_number)

        # State machine
        if self._state == ShotState.IDLE:
            return self._handle_idle(cue_ball, current_state, timestamp_ms, frame_number, tracks)
        elif self._state == ShotState.IN_PROGRESS:
            return self._handle_in_progress(cue_ball, current_state, timestamp_ms, frame_number, tracks)
        elif self._state == ShotState.SETTLING:
            return self._handle_settling(cue_ball, current_state, timestamp_ms, frame_number, tracks)

        return None

    def _handle_idle(
        self,
        cue_ball: TrackedBall | None,
        current_state: TableState,
        timestamp_ms: int,
        frame_number: int,
        tracks: Sequence[TrackedBall],
    ) -> None:
        """Handle IDLE state - waiting for shot to start."""
        if cue_ball is None:
            return None

        cue_speed = cue_ball.speed

        if cue_speed >= self._shot_start_velocity:
            # Shot started!
            logger.info(
                "Shot %d started at frame %d (cue speed: %.2f)",
                self._shot_count + 1,
                frame_number,
                cue_speed,
            )

            self._state = ShotState.IN_PROGRESS
            self._shot_start_timestamp = timestamp_ms
            self._shot_start_frame = frame_number
            self._table_state_before = current_state
            self._cue_start_position = (cue_ball.x, cue_ball.y)
            self._cue_initial_velocity = (cue_ball.vx, cue_ball.vy)
            self._cue_trajectory = [(cue_ball.x, cue_ball.y, timestamp_ms, frame_number)]

            # Initialize trajectory tracking for all balls
            for track in tracks:
                self._all_trajectories[track.track_id] = [
                    (track.x, track.y, timestamp_ms, frame_number)
                ]

        else:
            # Store last idle state for "before" snapshot
            self._last_table_state = current_state

        return None

    def _handle_in_progress(
        self,
        cue_ball: TrackedBall | None,
        current_state: TableState,
        timestamp_ms: int,
        frame_number: int,
        tracks: Sequence[TrackedBall],
    ) -> None:
        """Handle IN_PROGRESS state - shot is active."""
        # Record cue ball trajectory
        if cue_ball:
            self._cue_trajectory.append(
                (cue_ball.x, cue_ball.y, timestamp_ms, frame_number)
            )

        # Record all ball trajectories
        for track in tracks:
            if track.track_id not in self._all_trajectories:
                self._all_trajectories[track.track_id] = []
            self._all_trajectories[track.track_id].append(
                (track.x, track.y, timestamp_ms, frame_number)
            )

        # Check if balls are starting to settle
        all_slow = all(
            t.speed < self._stationary_threshold * 2  # Use higher threshold for initial check
            for t in tracks
        )

        if all_slow:
            self._state = ShotState.SETTLING
            self._stationary_frame_count = 0
            logger.debug("Shot entering settling phase at frame %d", frame_number)

        return None

    def _handle_settling(
        self,
        cue_ball: TrackedBall | None,
        current_state: TableState,
        timestamp_ms: int,
        frame_number: int,
        tracks: Sequence[TrackedBall],
    ) -> ShotData | None:
        """Handle SETTLING state - checking if balls have stopped."""
        # Continue recording trajectories
        if cue_ball:
            self._cue_trajectory.append(
                (cue_ball.x, cue_ball.y, timestamp_ms, frame_number)
            )

        for track in tracks:
            if track.track_id not in self._all_trajectories:
                self._all_trajectories[track.track_id] = []
            self._all_trajectories[track.track_id].append(
                (track.x, track.y, timestamp_ms, frame_number)
            )

        # Check if all balls are truly stationary
        all_stationary = all(
            t.speed < self._stationary_threshold
            for t in tracks
        )

        if all_stationary:
            self._stationary_frame_count += 1

            if self._stationary_frame_count >= self._stationary_frames_needed:
                # Shot complete!
                shot_duration_frames = frame_number - self._shot_start_frame

                if shot_duration_frames >= self._min_shot_duration:
                    self._shot_count += 1

                    shot_data = ShotData(
                        shot_number=self._shot_count,
                        start_timestamp_ms=self._shot_start_timestamp,
                        end_timestamp_ms=timestamp_ms,
                        start_frame=self._shot_start_frame,
                        end_frame=frame_number,
                        duration_ms=timestamp_ms - self._shot_start_timestamp,
                        duration_frames=shot_duration_frames,
                        table_state_before=self._table_state_before or current_state,
                        table_state_after=current_state,
                        cue_start_x=self._cue_start_position[0] if self._cue_start_position else 0,
                        cue_start_y=self._cue_start_position[1] if self._cue_start_position else 0,
                        cue_initial_vx=self._cue_initial_velocity[0] if self._cue_initial_velocity else 0,
                        cue_initial_vy=self._cue_initial_velocity[1] if self._cue_initial_velocity else 0,
                        cue_initial_speed=np.sqrt(
                            self._cue_initial_velocity[0] ** 2 + self._cue_initial_velocity[1] ** 2
                        ) if self._cue_initial_velocity else 0,
                        cue_trajectory=list(self._cue_trajectory),
                        all_trajectories=dict(self._all_trajectories),
                    )

                    logger.info(
                        "Shot %d completed: %d frames, %.2f seconds",
                        self._shot_count,
                        shot_duration_frames,
                        shot_data.duration_seconds,
                    )

                    self._state = ShotState.IDLE
                    self._clear_shot_data()
                    return shot_data
                else:
                    # Shot too short, probably noise
                    logger.debug(
                        "Shot too short (%d frames), ignoring",
                        shot_duration_frames,
                    )
                    self._state = ShotState.IDLE
                    self._clear_shot_data()
        else:
            # Ball started moving again
            self._stationary_frame_count = 0

            # Check if significant motion resumed (back to IN_PROGRESS)
            any_fast = any(
                t.speed >= self._shot_start_velocity / 2
                for t in tracks
            )
            if any_fast:
                self._state = ShotState.IN_PROGRESS
                logger.debug("Ball motion resumed at frame %d", frame_number)

        return None

    def force_end_shot(
        self,
        tracks: Sequence[TrackedBall],
        timestamp_ms: int,
        frame_number: int,
    ) -> ShotData | None:
        """Force end the current shot (e.g., for session end).

        Returns:
            ShotData if a shot was in progress, None otherwise.
        """
        if self._state == ShotState.IDLE:
            return None

        current_state = TableState.from_tracks(tracks, timestamp_ms, frame_number)
        shot_duration_frames = frame_number - self._shot_start_frame

        if shot_duration_frames >= self._min_shot_duration:
            self._shot_count += 1

            shot_data = ShotData(
                shot_number=self._shot_count,
                start_timestamp_ms=self._shot_start_timestamp,
                end_timestamp_ms=timestamp_ms,
                start_frame=self._shot_start_frame,
                end_frame=frame_number,
                duration_ms=timestamp_ms - self._shot_start_timestamp,
                duration_frames=shot_duration_frames,
                table_state_before=self._table_state_before or current_state,
                table_state_after=current_state,
                cue_start_x=self._cue_start_position[0] if self._cue_start_position else 0,
                cue_start_y=self._cue_start_position[1] if self._cue_start_position else 0,
                cue_initial_vx=self._cue_initial_velocity[0] if self._cue_initial_velocity else 0,
                cue_initial_vy=self._cue_initial_velocity[1] if self._cue_initial_velocity else 0,
                cue_initial_speed=np.sqrt(
                    self._cue_initial_velocity[0] ** 2 + self._cue_initial_velocity[1] ** 2
                ) if self._cue_initial_velocity else 0,
                cue_trajectory=list(self._cue_trajectory),
                all_trajectories=dict(self._all_trajectories),
            )

            logger.info("Shot %d force-ended", self._shot_count)
            self._state = ShotState.IDLE
            self._clear_shot_data()
            return shot_data

        self._state = ShotState.IDLE
        self._clear_shot_data()
        return None
