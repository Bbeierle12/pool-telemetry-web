"""Event detection for collisions, pockets, and fouls."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Sequence

import numpy as np

from ..cv.tracker import TrackedBall
from ..cv.calibration import POCKET_POSITIONS, POCKET_RADIUS

logger = logging.getLogger(__name__)

# Detection parameters
COLLISION_DISTANCE = 30  # Distance threshold for collision detection (table units)
COLLISION_VELOCITY_CHANGE = 3.0  # Minimum velocity change to confirm collision
POCKET_THRESHOLD = 35  # Distance to pocket center to consider ball pocketed


class EventType(Enum):
    """Types of game events."""

    COLLISION = auto()      # Ball-ball collision
    POCKET = auto()         # Ball pocketed
    RAIL_BOUNCE = auto()    # Ball hit rail
    CUE_STRIKE = auto()     # Cue ball struck
    SCRATCH = auto()        # Cue ball pocketed
    FOUL_NO_RAIL = auto()   # No ball hit rail after contact
    FOUL_WRONG_BALL = auto()  # Wrong ball hit first
    SHOT_START = auto()     # Shot began
    SHOT_END = auto()       # Shot ended


@dataclass
class GameEvent:
    """A detected game event."""

    event_type: EventType
    timestamp_ms: int
    frame_number: int

    # Event-specific data
    ball_ids: list[int] = field(default_factory=list)
    ball_names: list[str] = field(default_factory=list)
    position: tuple[float, float] | None = None
    pocket_name: str | None = None
    velocity_before: tuple[float, float] | None = None
    velocity_after: tuple[float, float] | None = None
    details: dict = field(default_factory=dict)

    @property
    def description(self) -> str:
        """Human-readable event description."""
        if self.event_type == EventType.COLLISION:
            balls = " and ".join(self.ball_names) if self.ball_names else "balls"
            return f"Collision between {balls}"
        elif self.event_type == EventType.POCKET:
            ball = self.ball_names[0] if self.ball_names else "ball"
            pocket = self.pocket_name or "pocket"
            return f"{ball} pocketed in {pocket}"
        elif self.event_type == EventType.SCRATCH:
            return f"Scratch! Cue ball pocketed in {self.pocket_name or 'pocket'}"
        elif self.event_type == EventType.RAIL_BOUNCE:
            ball = self.ball_names[0] if self.ball_names else "ball"
            return f"{ball} bounced off rail"
        elif self.event_type == EventType.CUE_STRIKE:
            return "Cue ball struck"
        elif self.event_type == EventType.FOUL_NO_RAIL:
            return "Foul: No ball hit rail after contact"
        elif self.event_type == EventType.FOUL_WRONG_BALL:
            return f"Foul: Wrong ball hit first ({self.ball_names[0] if self.ball_names else 'unknown'})"
        elif self.event_type == EventType.SHOT_START:
            return "Shot started"
        elif self.event_type == EventType.SHOT_END:
            return "Shot ended"
        return f"Event: {self.event_type.name}"


@dataclass
class BallState:
    """Tracking state for a single ball."""

    track_id: int
    class_name: str
    last_position: tuple[float, float]
    last_velocity: tuple[float, float]
    is_pocketed: bool = False
    collision_cooldown: int = 0  # Frames to wait before detecting another collision


class EventDetector:
    """Detects game events from ball tracking data."""

    def __init__(
        self,
        collision_distance: float = COLLISION_DISTANCE,
        collision_velocity_change: float = COLLISION_VELOCITY_CHANGE,
        pocket_threshold: float = POCKET_THRESHOLD,
    ) -> None:
        """Initialize event detector.

        Args:
            collision_distance: Distance threshold for collision detection.
            collision_velocity_change: Minimum velocity change for collision.
            pocket_threshold: Distance to pocket center for pocket detection.
        """
        self._collision_distance = collision_distance
        self._collision_velocity_change = collision_velocity_change
        self._pocket_threshold = pocket_threshold

        # Ball state tracking
        self._ball_states: dict[int, BallState] = {}
        self._pocketed_balls: set[int] = set()

        # Shot tracking
        self._shot_active = False
        self._shot_events: list[GameEvent] = []
        self._rail_contact_this_shot = False
        self._first_contact_ball: str | None = None

        # Event history
        self._events: list[GameEvent] = []

    @property
    def events(self) -> list[GameEvent]:
        """Get all detected events."""
        return self._events

    @property
    def pocketed_balls(self) -> set[int]:
        """Get set of pocketed ball track IDs."""
        return self._pocketed_balls

    def reset(self) -> None:
        """Reset detector state."""
        self._ball_states = {}
        self._pocketed_balls = set()
        self._shot_active = False
        self._shot_events = []
        self._rail_contact_this_shot = False
        self._first_contact_ball = None
        self._events = []

    def start_shot(self, timestamp_ms: int, frame_number: int) -> GameEvent:
        """Mark start of a new shot."""
        self._shot_active = True
        self._shot_events = []
        self._rail_contact_this_shot = False
        self._first_contact_ball = None

        event = GameEvent(
            event_type=EventType.SHOT_START,
            timestamp_ms=timestamp_ms,
            frame_number=frame_number,
        )
        self._events.append(event)
        self._shot_events.append(event)
        return event

    def end_shot(
        self,
        timestamp_ms: int,
        frame_number: int,
        target_ball_type: str | None = None,
    ) -> tuple[GameEvent, list[GameEvent]]:
        """Mark end of shot and check for fouls.

        Args:
            timestamp_ms: Current timestamp.
            frame_number: Current frame.
            target_ball_type: Expected first contact ball type ("solid" or "stripe").

        Returns:
            (shot_end_event, list of foul events)
        """
        fouls = []

        # Check for no-rail foul (if there was contact but no rail)
        had_collision = any(
            e.event_type == EventType.COLLISION for e in self._shot_events
        )
        if had_collision and not self._rail_contact_this_shot:
            foul = GameEvent(
                event_type=EventType.FOUL_NO_RAIL,
                timestamp_ms=timestamp_ms,
                frame_number=frame_number,
            )
            fouls.append(foul)
            self._events.append(foul)

        # Check for wrong-ball foul
        if target_ball_type and self._first_contact_ball:
            if target_ball_type == "solid" and not self._first_contact_ball.startswith("solid"):
                if self._first_contact_ball != "eight_ball":
                    foul = GameEvent(
                        event_type=EventType.FOUL_WRONG_BALL,
                        timestamp_ms=timestamp_ms,
                        frame_number=frame_number,
                        ball_names=[self._first_contact_ball],
                    )
                    fouls.append(foul)
                    self._events.append(foul)
            elif target_ball_type == "stripe" and not self._first_contact_ball.startswith("stripe"):
                if self._first_contact_ball != "eight_ball":
                    foul = GameEvent(
                        event_type=EventType.FOUL_WRONG_BALL,
                        timestamp_ms=timestamp_ms,
                        frame_number=frame_number,
                        ball_names=[self._first_contact_ball],
                    )
                    fouls.append(foul)
                    self._events.append(foul)

        # Create shot end event
        event = GameEvent(
            event_type=EventType.SHOT_END,
            timestamp_ms=timestamp_ms,
            frame_number=frame_number,
            details={
                "events_count": len(self._shot_events),
                "fouls": [f.event_type.name for f in fouls],
            },
        )
        self._events.append(event)

        self._shot_active = False
        shot_events = list(self._shot_events)
        self._shot_events = []

        return event, fouls

    def update(
        self,
        tracks: Sequence[TrackedBall],
        timestamp_ms: int,
        frame_number: int,
    ) -> list[GameEvent]:
        """Process new frame and detect events.

        Args:
            tracks: Current tracked balls.
            timestamp_ms: Current timestamp.
            frame_number: Current frame number.

        Returns:
            List of events detected in this frame.
        """
        frame_events = []

        # Update cooldowns
        for state in self._ball_states.values():
            if state.collision_cooldown > 0:
                state.collision_cooldown -= 1

        # Process each tracked ball
        for track in tracks:
            # Skip already pocketed balls
            if track.track_id in self._pocketed_balls:
                continue

            # Get or create ball state
            if track.track_id not in self._ball_states:
                self._ball_states[track.track_id] = BallState(
                    track_id=track.track_id,
                    class_name=track.class_name,
                    last_position=(track.x, track.y),
                    last_velocity=(track.vx, track.vy),
                )
                continue

            state = self._ball_states[track.track_id]
            current_pos = (track.x, track.y)
            current_vel = (track.vx, track.vy)

            # Check for pocket event
            pocket_event = self._check_pocket(
                track, current_pos, timestamp_ms, frame_number
            )
            if pocket_event:
                frame_events.append(pocket_event)
                self._events.append(pocket_event)
                if self._shot_active:
                    self._shot_events.append(pocket_event)

            # Check for rail bounce
            rail_event = self._check_rail_bounce(
                track, state, current_pos, current_vel, timestamp_ms, frame_number
            )
            if rail_event:
                frame_events.append(rail_event)
                self._events.append(rail_event)
                if self._shot_active:
                    self._shot_events.append(rail_event)
                    self._rail_contact_this_shot = True

            # Update state
            state.last_position = current_pos
            state.last_velocity = current_vel
            state.class_name = track.class_name

        # Check for collisions between balls
        collision_events = self._check_collisions(tracks, timestamp_ms, frame_number)
        for event in collision_events:
            frame_events.append(event)
            self._events.append(event)
            if self._shot_active:
                self._shot_events.append(event)
                # Track first contact
                if self._first_contact_ball is None:
                    # Find the non-cue ball in the collision
                    for name in event.ball_names:
                        if name != "cue":
                            self._first_contact_ball = name
                            break

        return frame_events

    def _check_pocket(
        self,
        track: TrackedBall,
        position: tuple[float, float],
        timestamp_ms: int,
        frame_number: int,
    ) -> GameEvent | None:
        """Check if ball entered a pocket."""
        x, y = position

        for pocket_name, (px, py) in POCKET_POSITIONS.items():
            distance = np.sqrt((x - px) ** 2 + (y - py) ** 2)

            if distance < self._pocket_threshold:
                self._pocketed_balls.add(track.track_id)

                # Check if it's a scratch
                if track.is_cue:
                    event = GameEvent(
                        event_type=EventType.SCRATCH,
                        timestamp_ms=timestamp_ms,
                        frame_number=frame_number,
                        ball_ids=[track.track_id],
                        ball_names=[track.class_name],
                        position=position,
                        pocket_name=pocket_name,
                    )
                else:
                    event = GameEvent(
                        event_type=EventType.POCKET,
                        timestamp_ms=timestamp_ms,
                        frame_number=frame_number,
                        ball_ids=[track.track_id],
                        ball_names=[track.class_name],
                        position=position,
                        pocket_name=pocket_name,
                    )

                logger.info(
                    "%s pocketed in %s at frame %d",
                    track.class_name,
                    pocket_name,
                    frame_number,
                )
                return event

        return None

    def _check_rail_bounce(
        self,
        track: TrackedBall,
        state: BallState,
        position: tuple[float, float],
        velocity: tuple[float, float],
        timestamp_ms: int,
        frame_number: int,
    ) -> GameEvent | None:
        """Check if ball bounced off a rail."""
        x, y = position
        vx, vy = velocity
        prev_vx, prev_vy = state.last_velocity

        # Table boundaries (with margin for ball radius)
        margin = 15
        min_x, max_x = margin, 1000 - margin
        min_y, max_y = margin, 500 - margin

        # Check for velocity reversal near edges
        at_edge = (
            x <= min_x or x >= max_x or
            y <= min_y or y >= max_y
        )

        if at_edge:
            # Check for velocity sign change (bounce)
            x_reversed = (vx * prev_vx < 0) and abs(prev_vx) > 1.0
            y_reversed = (vy * prev_vy < 0) and abs(prev_vy) > 1.0

            if x_reversed or y_reversed:
                return GameEvent(
                    event_type=EventType.RAIL_BOUNCE,
                    timestamp_ms=timestamp_ms,
                    frame_number=frame_number,
                    ball_ids=[track.track_id],
                    ball_names=[track.class_name],
                    position=position,
                    velocity_before=(prev_vx, prev_vy),
                    velocity_after=(vx, vy),
                )

        return None

    def _check_collisions(
        self,
        tracks: Sequence[TrackedBall],
        timestamp_ms: int,
        frame_number: int,
    ) -> list[GameEvent]:
        """Check for ball-ball collisions."""
        events = []
        checked_pairs: set[tuple[int, int]] = set()

        for i, ball1 in enumerate(tracks):
            if ball1.track_id in self._pocketed_balls:
                continue

            state1 = self._ball_states.get(ball1.track_id)
            if state1 is None or state1.collision_cooldown > 0:
                continue

            for j, ball2 in enumerate(tracks):
                if i >= j:  # Avoid duplicate checks
                    continue

                if ball2.track_id in self._pocketed_balls:
                    continue

                state2 = self._ball_states.get(ball2.track_id)
                if state2 is None or state2.collision_cooldown > 0:
                    continue

                # Check if pair already checked
                pair = (min(ball1.track_id, ball2.track_id), max(ball1.track_id, ball2.track_id))
                if pair in checked_pairs:
                    continue
                checked_pairs.add(pair)

                # Calculate distance
                distance = np.sqrt(
                    (ball1.x - ball2.x) ** 2 + (ball1.y - ball2.y) ** 2
                )

                if distance < self._collision_distance:
                    # Check for significant velocity change
                    vel_change1 = np.sqrt(
                        (ball1.vx - state1.last_velocity[0]) ** 2 +
                        (ball1.vy - state1.last_velocity[1]) ** 2
                    )
                    vel_change2 = np.sqrt(
                        (ball2.vx - state2.last_velocity[0]) ** 2 +
                        (ball2.vy - state2.last_velocity[1]) ** 2
                    )

                    if vel_change1 > self._collision_velocity_change or vel_change2 > self._collision_velocity_change:
                        event = GameEvent(
                            event_type=EventType.COLLISION,
                            timestamp_ms=timestamp_ms,
                            frame_number=frame_number,
                            ball_ids=[ball1.track_id, ball2.track_id],
                            ball_names=[ball1.class_name, ball2.class_name],
                            position=((ball1.x + ball2.x) / 2, (ball1.y + ball2.y) / 2),
                            details={
                                "distance": distance,
                                "velocity_change_1": vel_change1,
                                "velocity_change_2": vel_change2,
                            },
                        )
                        events.append(event)

                        # Set cooldown to prevent duplicate detections
                        state1.collision_cooldown = 5
                        state2.collision_cooldown = 5

                        logger.debug(
                            "Collision: %s and %s at frame %d",
                            ball1.class_name,
                            ball2.class_name,
                            frame_number,
                        )

        return events

    def get_shot_summary(self) -> dict:
        """Get summary of events in current/last shot."""
        collisions = [e for e in self._shot_events if e.event_type == EventType.COLLISION]
        pockets = [e for e in self._shot_events if e.event_type == EventType.POCKET]
        scratches = [e for e in self._shot_events if e.event_type == EventType.SCRATCH]
        rail_bounces = [e for e in self._shot_events if e.event_type == EventType.RAIL_BOUNCE]

        return {
            "collision_count": len(collisions),
            "pocketed_balls": [e.ball_names[0] for e in pockets],
            "scratched": len(scratches) > 0,
            "rail_contacts": len(rail_bounces),
            "first_contact": self._first_contact_ball,
        }
