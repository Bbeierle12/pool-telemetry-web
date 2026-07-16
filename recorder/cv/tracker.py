"""Ball tracking with persistent IDs across frames."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from .detector import DetectedBall

logger = logging.getLogger(__name__)

# Tracking parameters
MAX_AGE = 30  # Frames to keep track alive without detection
MIN_HITS = 3  # Minimum detections before track is confirmed
IOU_THRESHOLD = 0.3  # Minimum IoU for matching
VELOCITY_SMOOTHING = 0.3  # Exponential smoothing factor for velocity
STATIONARY_THRESHOLD = 2.0  # Speed below which ball is considered stationary
TRAJECTORY_HISTORY = 120  # Number of frames to keep in trajectory history


@dataclass
class TrackedBall:
    """A tracked ball with persistent ID and trajectory history."""

    track_id: int
    class_name: str
    class_id: int
    x: float                    # Current X in table coordinates
    y: float                    # Current Y in table coordinates
    x_pixel: float              # Current X in pixel coordinates
    y_pixel: float              # Current Y in pixel coordinates
    vx: float = 0.0             # Velocity X (table units per frame)
    vy: float = 0.0             # Velocity Y (table units per frame)
    confidence: float = 0.0
    bbox: tuple[float, float, float, float] = (0, 0, 0, 0)

    # Tracking state
    age: int = 0                # Frames since track started
    hits: int = 0               # Number of successful matches
    time_since_update: int = 0  # Frames since last detection match

    # Trajectory history: list of (x, y, timestamp_ms, frame_number)
    trajectory: list[tuple[float, float, int, int]] = field(default_factory=list)

    @property
    def speed(self) -> float:
        """Calculate current speed magnitude."""
        return np.sqrt(self.vx ** 2 + self.vy ** 2)

    @property
    def state(self) -> str:
        """Get motion state: 'stationary', 'moving', or 'decelerating'."""
        speed = self.speed
        if speed < STATIONARY_THRESHOLD:
            return "stationary"
        # Check if decelerating (compare recent velocities)
        if len(self.trajectory) >= 3:
            recent = self.trajectory[-3:]
            if len(recent) >= 2:
                dx1 = recent[-1][0] - recent[-2][0]
                dy1 = recent[-1][1] - recent[-2][1]
                dx2 = recent[-2][0] - recent[-3][0] if len(recent) >= 3 else dx1
                dy2 = recent[-2][1] - recent[-3][1] if len(recent) >= 3 else dy1
                speed1 = np.sqrt(dx1**2 + dy1**2)
                speed2 = np.sqrt(dx2**2 + dy2**2)
                if speed2 > 0 and speed1 < speed2 * 0.9:
                    return "decelerating"
        return "moving"

    @property
    def is_confirmed(self) -> bool:
        """Check if track is confirmed (enough hits)."""
        return self.hits >= MIN_HITS

    @property
    def is_cue(self) -> bool:
        """Check if this is the cue ball."""
        return self.class_name == "cue"

    def add_trajectory_point(
        self,
        x: float,
        y: float,
        timestamp_ms: int,
        frame_number: int,
    ) -> None:
        """Add a point to trajectory history."""
        self.trajectory.append((x, y, timestamp_ms, frame_number))
        # Limit history size
        if len(self.trajectory) > TRAJECTORY_HISTORY:
            self.trajectory = self.trajectory[-TRAJECTORY_HISTORY:]


class KalmanBoxTracker:
    """Kalman filter for tracking a single ball."""

    count = 0  # Class variable for unique IDs

    def __init__(self, detection: DetectedBall) -> None:
        """Initialize tracker with first detection."""
        try:
            from filterpy.kalman import KalmanFilter
        except ImportError:
            raise RuntimeError("filterpy required. Run: pip install filterpy")

        # State: [x, y, vx, vy]
        self.kf = KalmanFilter(dim_x=4, dim_z=2)

        # State transition matrix (constant velocity model)
        self.kf.F = np.array([
            [1, 0, 1, 0],
            [0, 1, 0, 1],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ])

        # Measurement matrix (we only observe position)
        self.kf.H = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0],
        ])

        # Measurement noise
        self.kf.R *= 10

        # Process noise
        self.kf.P[2:, 2:] *= 1000  # High uncertainty for velocity
        self.kf.Q[2:, 2:] *= 0.01  # Low process noise for velocity

        # Initialize state
        self.kf.x[:2] = np.array([[detection.x], [detection.y]])

        # Track metadata
        self.id = KalmanBoxTracker.count
        KalmanBoxTracker.count += 1

        self.class_name = detection.class_name
        self.class_id = detection.class_id
        self.confidence = detection.confidence
        self.bbox = detection.bbox
        self.x_pixel = detection.x_pixel
        self.y_pixel = detection.y_pixel

        self.hits = 1
        self.age = 1
        self.time_since_update = 0
        self.trajectory: list[tuple[float, float, int, int]] = []

    def predict(self) -> np.ndarray:
        """Advance state and return predicted position."""
        self.kf.predict()
        self.age += 1
        self.time_since_update += 1
        return self.kf.x[:2].flatten()

    def update(self, detection: DetectedBall) -> None:
        """Update with new detection."""
        self.kf.update(np.array([[detection.x], [detection.y]]))
        self.hits += 1
        self.time_since_update = 0
        self.confidence = detection.confidence
        self.bbox = detection.bbox
        self.x_pixel = detection.x_pixel
        self.y_pixel = detection.y_pixel
        # Update class if confidence is higher
        if detection.confidence > self.confidence:
            self.class_name = detection.class_name
            self.class_id = detection.class_id

    def get_state(self) -> tuple[float, float, float, float]:
        """Get current state (x, y, vx, vy)."""
        return tuple(self.kf.x.flatten())


class BallTracker:
    """Multi-object tracker for pool balls using Kalman filters."""

    def __init__(
        self,
        max_age: int = MAX_AGE,
        min_hits: int = MIN_HITS,
        iou_threshold: float = IOU_THRESHOLD,
    ) -> None:
        """Initialize tracker.

        Args:
            max_age: Maximum frames to keep track without detection.
            min_hits: Minimum hits before track is confirmed.
            iou_threshold: Minimum IoU for matching detections to tracks.
        """
        self._max_age = max_age
        self._min_hits = min_hits
        self._iou_threshold = iou_threshold
        self._trackers: list[KalmanBoxTracker] = []
        self._frame_count = 0

    def reset(self) -> None:
        """Reset all tracks."""
        self._trackers = []
        self._frame_count = 0
        KalmanBoxTracker.count = 0

    def update(
        self,
        detections: Sequence[DetectedBall],
        timestamp_ms: int = 0,
    ) -> list[TrackedBall]:
        """Update tracks with new detections.

        Args:
            detections: List of detected balls in current frame.
            timestamp_ms: Current timestamp in milliseconds.

        Returns:
            List of tracked balls with persistent IDs.
        """
        self._frame_count += 1

        # Predict new locations of existing tracks
        for tracker in self._trackers:
            tracker.predict()

        # Match detections to tracks
        matched, unmatched_dets, unmatched_trks = self._associate_detections(
            detections, self._trackers
        )

        # Update matched tracks
        for det_idx, trk_idx in matched:
            self._trackers[trk_idx].update(detections[det_idx])
            # Add trajectory point
            det = detections[det_idx]
            self._trackers[trk_idx].trajectory.append(
                (det.x, det.y, timestamp_ms, self._frame_count)
            )

        # Create new tracks for unmatched detections
        for det_idx in unmatched_dets:
            tracker = KalmanBoxTracker(detections[det_idx])
            det = detections[det_idx]
            tracker.trajectory.append(
                (det.x, det.y, timestamp_ms, self._frame_count)
            )
            self._trackers.append(tracker)

        # Remove dead tracks
        self._trackers = [
            t for t in self._trackers
            if t.time_since_update <= self._max_age
        ]

        # Build output
        results = []
        for tracker in self._trackers:
            if tracker.hits >= self._min_hits or self._frame_count <= self._min_hits:
                x, y, vx, vy = tracker.get_state()
                tracked = TrackedBall(
                    track_id=tracker.id,
                    class_name=tracker.class_name,
                    class_id=tracker.class_id,
                    x=x,
                    y=y,
                    x_pixel=tracker.x_pixel,
                    y_pixel=tracker.y_pixel,
                    vx=vx,
                    vy=vy,
                    confidence=tracker.confidence,
                    bbox=tracker.bbox,
                    age=tracker.age,
                    hits=tracker.hits,
                    time_since_update=tracker.time_since_update,
                    trajectory=list(tracker.trajectory),
                )
                results.append(tracked)

        logger.debug(
            "Frame %d: %d detections, %d tracks, %d confirmed",
            self._frame_count,
            len(detections),
            len(self._trackers),
            len(results),
        )

        return results

    def _associate_detections(
        self,
        detections: Sequence[DetectedBall],
        trackers: list[KalmanBoxTracker],
    ) -> tuple[list[tuple[int, int]], list[int], list[int]]:
        """Associate detections with existing tracks using distance.

        Returns:
            (matched_pairs, unmatched_detections, unmatched_trackers)
        """
        if len(trackers) == 0:
            return [], list(range(len(detections))), []

        if len(detections) == 0:
            return [], [], list(range(len(trackers)))

        # Build cost matrix based on Euclidean distance
        cost_matrix = np.zeros((len(detections), len(trackers)))

        for d, det in enumerate(detections):
            for t, trk in enumerate(trackers):
                x, y, _, _ = trk.get_state()
                dist = np.sqrt((det.x - x) ** 2 + (det.y - y) ** 2)
                # Also consider class match
                class_penalty = 0 if det.class_name == trk.class_name else 50
                cost_matrix[d, t] = dist + class_penalty

        # Use Hungarian algorithm for optimal assignment
        try:
            from scipy.optimize import linear_sum_assignment
            row_indices, col_indices = linear_sum_assignment(cost_matrix)
        except ImportError:
            # Fallback to greedy matching
            row_indices, col_indices = self._greedy_match(cost_matrix)

        # Filter out high-cost matches
        matched = []
        unmatched_dets = list(range(len(detections)))
        unmatched_trks = list(range(len(trackers)))

        # Distance threshold (in table units)
        max_distance = 100  # Adjust based on ball size and frame rate

        for row, col in zip(row_indices, col_indices):
            if cost_matrix[row, col] < max_distance:
                matched.append((row, col))
                if row in unmatched_dets:
                    unmatched_dets.remove(row)
                if col in unmatched_trks:
                    unmatched_trks.remove(col)

        return matched, unmatched_dets, unmatched_trks

    def _greedy_match(
        self,
        cost_matrix: np.ndarray,
    ) -> tuple[list[int], list[int]]:
        """Simple greedy matching fallback."""
        rows, cols = [], []
        used_cols = set()

        for i in range(cost_matrix.shape[0]):
            best_j = -1
            best_cost = float("inf")
            for j in range(cost_matrix.shape[1]):
                if j not in used_cols and cost_matrix[i, j] < best_cost:
                    best_cost = cost_matrix[i, j]
                    best_j = j
            if best_j >= 0:
                rows.append(i)
                cols.append(best_j)
                used_cols.add(best_j)

        return rows, cols

    def get_cue_ball(self) -> TrackedBall | None:
        """Get the cue ball track if available."""
        for tracker in self._trackers:
            if tracker.class_name == "cue" and tracker.hits >= self._min_hits:
                x, y, vx, vy = tracker.get_state()
                return TrackedBall(
                    track_id=tracker.id,
                    class_name=tracker.class_name,
                    class_id=tracker.class_id,
                    x=x,
                    y=y,
                    x_pixel=tracker.x_pixel,
                    y_pixel=tracker.y_pixel,
                    vx=vx,
                    vy=vy,
                    confidence=tracker.confidence,
                    bbox=tracker.bbox,
                    age=tracker.age,
                    hits=tracker.hits,
                    time_since_update=tracker.time_since_update,
                    trajectory=list(tracker.trajectory),
                )
        return None

    def all_stationary(self, threshold: float = STATIONARY_THRESHOLD) -> bool:
        """Check if all confirmed tracks are stationary."""
        confirmed = [
            t for t in self._trackers
            if t.hits >= self._min_hits
        ]
        if not confirmed:
            return True

        for tracker in confirmed:
            _, _, vx, vy = tracker.get_state()
            speed = np.sqrt(vx ** 2 + vy ** 2)
            if speed >= threshold:
                return False
        return True

    def draw_tracks(
        self,
        frame: np.ndarray,
        tracks: Sequence[TrackedBall],
        show_trajectory: bool = True,
        show_velocity: bool = True,
    ) -> np.ndarray:
        """Draw tracks on frame.

        Args:
            frame: BGR image to draw on.
            tracks: List of tracked balls.
            show_trajectory: Whether to draw trajectory history.
            show_velocity: Whether to draw velocity vectors.

        Returns:
            Frame with tracks drawn.
        """
        import cv2

        output = frame.copy()

        for track in tracks:
            # Color based on ball type
            if track.class_name == "cue":
                color = (255, 255, 255)
            elif track.class_name.startswith("solid"):
                color = (255, 165, 0)
            elif track.class_name.startswith("stripe"):
                color = (0, 255, 255)
            elif track.class_name == "eight_ball":
                color = (0, 0, 0)
            else:
                color = (128, 128, 128)

            # Draw current position
            cv2.circle(
                output,
                (int(track.x_pixel), int(track.y_pixel)),
                10,
                color,
                2,
            )

            # Draw track ID
            cv2.putText(
                output,
                f"#{track.track_id}",
                (int(track.x_pixel) + 12, int(track.y_pixel) - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                color,
                1,
            )

            # Draw state indicator
            state_color = (0, 255, 0) if track.state == "stationary" else (0, 0, 255)
            cv2.circle(
                output,
                (int(track.x_pixel), int(track.y_pixel)),
                5,
                state_color,
                -1,
            )

            # Draw velocity vector
            if show_velocity and track.speed > STATIONARY_THRESHOLD:
                scale = 5  # Scale factor for visibility
                end_x = int(track.x_pixel + track.vx * scale)
                end_y = int(track.y_pixel + track.vy * scale)
                cv2.arrowedLine(
                    output,
                    (int(track.x_pixel), int(track.y_pixel)),
                    (end_x, end_y),
                    (0, 0, 255),
                    2,
                )

            # Draw trajectory
            if show_trajectory and len(track.trajectory) > 1:
                # We need to convert table coords back to pixel coords
                # For now, just draw if we have pixel coords stored
                points = [(int(track.x_pixel), int(track.y_pixel))]
                # Note: trajectory stores table coords, would need calibration to convert
                # This is simplified - in production, store pixel coords too
                for i in range(len(points) - 1):
                    cv2.line(
                        output,
                        points[i],
                        points[i + 1],
                        color,
                        1,
                    )

        return output
