"""Prototype local video scoring using OpenCV heuristics."""
from __future__ import annotations

from dataclasses import dataclass, field
from math import hypot, pi
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import cv2
import numpy as np


@dataclass(slots=True)
class BallObservation:
    """Single ball-like detection in a frame."""

    x: float
    y: float
    radius: float
    confidence: float
    brightness: float
    saturation: float


@dataclass(slots=True)
class BallTrack:
    """Tracked ball state for a sampled frame."""

    name: str
    x: float
    y: float
    radius: float
    confidence: float
    brightness: float
    saturation: float
    is_cue_ball: bool = False
    motion_px: float = 0.0
    missing_frames: int = 0


@dataclass(slots=True)
class FrameState:
    """Reduced state for one analyzed frame."""

    frame_index: int
    timestamp_ms: int
    frame_width: int
    frame_height: int
    tracks: List[BallTrack]
    moving_names: List[str]


@dataclass(slots=True)
class PrototypeDetectedEvent:
    """Event emitted by the prototype analyzer."""

    timestamp_ms: int
    event_type: str
    event_data: dict


@dataclass(slots=True)
class PrototypeDetectedShot:
    """Shot summary derived from a motion window."""

    shot_number: int
    timestamp_start_ms: int
    timestamp_end_ms: int
    duration_ms: int
    balls_pocketed: List[str]
    foul_types: List[str]
    confidence_overall: float
    table_state_before: dict
    table_state_after: dict
    analysis_data: dict = field(default_factory=dict)


@dataclass(slots=True)
class PrototypeAnalysisResult:
    """Aggregate result returned to the API layer."""

    analyzed_frames: int
    sample_fps: int
    events: List[PrototypeDetectedEvent]
    shots: List[PrototypeDetectedShot]
    notes: List[str]
    duration_ms: int
    frame_width: Optional[int] = None
    frame_height: Optional[int] = None

    @property
    def pockets_detected(self) -> int:
        return sum(1 for event in self.events if event.event_type == "pocket")

    @property
    def fouls_detected(self) -> int:
        return sum(1 for event in self.events if event.event_type == "foul")


class PrototypeEventBuilder:
    """Convert tracked ball snapshots into shots, pockets, and fouls."""

    def __init__(
        self,
        *,
        stationary_start_frames: int = 2,
        settle_frames: int = 3,
        pocket_missing_frames: int = 2,
    ):
        self.stationary_start_frames = stationary_start_frames
        self.settle_frames = settle_frames
        self.pocket_missing_frames = pocket_missing_frames

        self.events: List[PrototypeDetectedEvent] = []
        self.shots: List[PrototypeDetectedShot] = []

        self.previous_tracks: Dict[str, BallTrack] = {}
        self.missing_counts: Dict[str, int] = {}
        self.pocketed_balls: set[str] = set()

        self.frames_without_motion = stationary_start_frames
        self.in_shot = False
        self.current_shot_number = 0
        self.current_shot_start_ms = 0
        self.current_shot_motion_frames = 0
        self.current_shot_max_moving = 0
        self.current_shot_stationary_frames = 0
        self.current_shot_pocketed: List[str] = []
        self.current_shot_fouls: List[str] = []
        self.current_shot_before: dict = {"balls": []}
        self.last_frame_state: Optional[FrameState] = None

    def process_frame(self, frame_state: FrameState) -> None:
        """Consume one sampled frame."""
        current_tracks = {track.name: track for track in frame_state.tracks}
        self._detect_pockets(frame_state, current_tracks)

        moving_names = set(frame_state.moving_names)

        if moving_names and not self.in_shot and self.frames_without_motion >= self.stationary_start_frames:
            self._start_shot(frame_state)

        if self.in_shot:
            if moving_names:
                self.current_shot_motion_frames += 1
                self.current_shot_max_moving = max(self.current_shot_max_moving, len(moving_names))
                self.current_shot_stationary_frames = 0
            else:
                self.current_shot_stationary_frames += 1
                if self.current_shot_stationary_frames >= self.settle_frames:
                    self._finish_shot(frame_state)

        if moving_names:
            self.frames_without_motion = 0
        else:
            self.frames_without_motion += 1

        self.previous_tracks = current_tracks
        self.last_frame_state = frame_state

    def finish(self) -> None:
        """Finalize an in-flight shot at end of stream."""
        if self.in_shot and self.last_frame_state is not None:
            self._finish_shot(self.last_frame_state)

    def _start_shot(self, frame_state: FrameState) -> None:
        self.in_shot = True
        self.current_shot_number += 1
        self.current_shot_start_ms = frame_state.timestamp_ms
        self.current_shot_motion_frames = 1
        self.current_shot_max_moving = len(frame_state.moving_names)
        self.current_shot_stationary_frames = 0
        self.current_shot_pocketed = []
        self.current_shot_fouls = []
        baseline_tracks = self.previous_tracks.values() if self.previous_tracks else frame_state.tracks
        self.current_shot_before = self._serialize_table_state(baseline_tracks)

    def _finish_shot(self, frame_state: FrameState) -> None:
        shot = PrototypeDetectedShot(
            shot_number=self.current_shot_number,
            timestamp_start_ms=self.current_shot_start_ms,
            timestamp_end_ms=frame_state.timestamp_ms,
            duration_ms=max(0, frame_state.timestamp_ms - self.current_shot_start_ms),
            balls_pocketed=list(self.current_shot_pocketed),
            foul_types=list(self.current_shot_fouls),
            confidence_overall=self._shot_confidence(),
            table_state_before=self.current_shot_before,
            table_state_after=self._serialize_table_state(frame_state.tracks),
            analysis_data={
                "motion_frames": self.current_shot_motion_frames,
                "max_balls_in_motion": self.current_shot_max_moving,
                "settled_frames": self.current_shot_stationary_frames,
            },
        )
        self.shots.append(shot)
        self.events.append(
            PrototypeDetectedEvent(
                timestamp_ms=shot.timestamp_end_ms,
                event_type="shot",
                event_data={
                    "shot_number": shot.shot_number,
                    "timestamp_start_ms": shot.timestamp_start_ms,
                    "timestamp_end_ms": shot.timestamp_end_ms,
                    "duration_ms": shot.duration_ms,
                    "balls_pocketed": shot.balls_pocketed,
                    "foul_types": shot.foul_types,
                    "confidence_overall": shot.confidence_overall,
                },
            )
        )

        self.in_shot = False
        self.current_shot_stationary_frames = 0

    def _detect_pockets(self, frame_state: FrameState, current_tracks: Dict[str, BallTrack]) -> None:
        current_names = set(current_tracks)

        for name, previous_track in self.previous_tracks.items():
            if name in self.pocketed_balls:
                continue

            if name in current_names:
                self.missing_counts.pop(name, None)
                continue

            self.missing_counts[name] = self.missing_counts.get(name, 0) + 1
            if self.missing_counts[name] != self.pocket_missing_frames:
                continue

            pocket_id = self._nearest_pocket(
                previous_track.x,
                previous_track.y,
                frame_state.frame_width,
                frame_state.frame_height,
            )
            if not pocket_id:
                continue

            self.pocketed_balls.add(name)
            if name not in self.current_shot_pocketed:
                self.current_shot_pocketed.append(name)

            self.events.append(
                PrototypeDetectedEvent(
                    timestamp_ms=frame_state.timestamp_ms,
                    event_type="pocket",
                    event_data={
                        "ball": name,
                        "pocket": pocket_id,
                        "shot_number": self.current_shot_number or None,
                    },
                )
            )

            if previous_track.is_cue_ball:
                foul_type = "scratch"
                if foul_type not in self.current_shot_fouls:
                    self.current_shot_fouls.append(foul_type)
                self.events.append(
                    PrototypeDetectedEvent(
                        timestamp_ms=frame_state.timestamp_ms,
                        event_type="foul",
                        event_data={
                            "foul_type": foul_type,
                            "shot_number": self.current_shot_number or None,
                            "details": {
                                "ball": name,
                                "pocket": pocket_id,
                            },
                        },
                    )
                )

    def _nearest_pocket(
        self,
        x: float,
        y: float,
        frame_width: int,
        frame_height: int,
    ) -> Optional[str]:
        pocket_centers = {
            "top_left": (0.0, 0.0),
            "top_center": (frame_width / 2, 0.0),
            "top_right": (float(frame_width), 0.0),
            "bottom_left": (0.0, float(frame_height)),
            "bottom_center": (frame_width / 2, float(frame_height)),
            "bottom_right": (float(frame_width), float(frame_height)),
        }
        pocket_radius = max(28.0, min(frame_width, frame_height) * 0.085)

        closest_name = None
        closest_distance = float("inf")
        for pocket_name, (pocket_x, pocket_y) in pocket_centers.items():
            distance = hypot(x - pocket_x, y - pocket_y)
            if distance < closest_distance:
                closest_name = pocket_name
                closest_distance = distance

        if closest_name and closest_distance <= pocket_radius:
            return closest_name
        return None

    def _serialize_table_state(self, tracks: Iterable[BallTrack]) -> dict:
        balls = [
            {
                "name": track.name,
                "x": round(track.x, 1),
                "y": round(track.y, 1),
                "confidence": round(track.confidence, 3),
                "is_cue_ball": track.is_cue_ball,
            }
            for track in tracks
            if track.name not in self.pocketed_balls
        ]
        return {"balls": balls}

    def _shot_confidence(self) -> float:
        confidence = 0.45
        confidence += min(0.2, self.current_shot_motion_frames * 0.04)
        confidence += min(0.15, len(self.current_shot_pocketed) * 0.08)
        if self.current_shot_fouls:
            confidence += 0.05
        return round(min(confidence, 0.95), 3)


class BallTracker:
    """Assign stable ball identifiers across sampled frames."""

    def __init__(self, *, max_distance_px: float = 42.0, max_missing_frames: int = 4):
        self.max_distance_px = max_distance_px
        self.max_missing_frames = max_missing_frames
        self.next_track_id = 1
        self.active_tracks: Dict[str, BallTrack] = {}

    def update(self, observations: Sequence[BallObservation]) -> List[BallTrack]:
        """Match raw observations to active tracks."""
        visible_tracks: Dict[str, BallTrack] = {}
        remaining_tracks = set(self.active_tracks)

        for observation in sorted(observations, key=lambda item: item.confidence, reverse=True):
            best_name = None
            best_distance = float("inf")

            for track_name in remaining_tracks:
                track = self.active_tracks[track_name]
                distance = hypot(observation.x - track.x, observation.y - track.y)
                threshold = max(self.max_distance_px, track.radius * 3.0)
                if distance <= threshold and distance < best_distance:
                    best_name = track_name
                    best_distance = distance

            if best_name is None:
                track_name = f"ball_{self.next_track_id}"
                self.next_track_id += 1
                visible_tracks[track_name] = BallTrack(
                    name=track_name,
                    x=observation.x,
                    y=observation.y,
                    radius=observation.radius,
                    confidence=observation.confidence,
                    brightness=observation.brightness,
                    saturation=observation.saturation,
                )
                continue

            previous_track = self.active_tracks[best_name]
            visible_tracks[best_name] = BallTrack(
                name=best_name,
                x=observation.x,
                y=observation.y,
                radius=observation.radius,
                confidence=observation.confidence,
                brightness=observation.brightness,
                saturation=observation.saturation,
                is_cue_ball=previous_track.is_cue_ball,
                motion_px=best_distance,
            )
            remaining_tracks.remove(best_name)

        for track_name in remaining_tracks:
            stale_track = self.active_tracks[track_name]
            stale_track.missing_frames += 1
            if stale_track.missing_frames > self.max_missing_frames:
                self.active_tracks.pop(track_name, None)

        self.active_tracks.update(visible_tracks)
        self._assign_cue_ball(visible_tracks)
        return list(visible_tracks.values())

    def _assign_cue_ball(self, visible_tracks: Dict[str, BallTrack]) -> None:
        if not visible_tracks:
            return

        if any(track.is_cue_ball for track in self.active_tracks.values() if track.missing_frames == 0):
            return

        likely_white = [
            track
            for track in visible_tracks.values()
            if track.brightness >= 150 and track.saturation <= 70
        ]
        candidates = likely_white or list(visible_tracks.values())
        cue_ball = max(candidates, key=lambda track: (track.brightness - track.saturation, track.confidence))

        for track in self.active_tracks.values():
            track.is_cue_ball = track.name == cue_ball.name


class OpenCVPoolPrototypeAnalyzer:
    """Analyze uploaded video files and emit prototype scoring events."""

    def __init__(
        self,
        *,
        sample_fps: int = 6,
        max_frames: Optional[int] = None,
        motion_threshold_px: float = 7.0,
    ):
        self.sample_fps = sample_fps
        self.max_frames = max_frames
        self.motion_threshold_px = motion_threshold_px

    def analyze(self, video_path: Path) -> PrototypeAnalysisResult:
        """Run the prototype analyzer against a local video file."""
        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise ValueError(f"Unable to open video file: {video_path}")

        source_fps = capture.get(cv2.CAP_PROP_FPS) or 0.0
        if source_fps <= 1.0:
            source_fps = 30.0

        sample_step = max(1, round(source_fps / max(self.sample_fps, 1)))
        tracker = BallTracker()
        builder = PrototypeEventBuilder()
        notes: List[str] = []

        analyzed_frames = 0
        frame_index = -1
        last_timestamp_ms = 0
        frame_width: Optional[int] = None
        frame_height: Optional[int] = None

        try:
            while True:
                success, frame = capture.read()
                if not success:
                    break

                frame_index += 1
                if frame_index % sample_step != 0:
                    continue

                if self.max_frames is not None and analyzed_frames >= self.max_frames:
                    notes.append(f"Stopped after {self.max_frames} sampled frames to keep prototype analysis bounded.")
                    break

                normalized_frame = self._normalize_frame(frame)
                frame_height, frame_width = normalized_frame.shape[:2]
                observations = self._detect_ball_observations(normalized_frame)
                tracks = tracker.update(observations)
                moving_names = [track.name for track in tracks if track.motion_px >= self.motion_threshold_px]
                timestamp_ms = int(round((frame_index / source_fps) * 1000))
                last_timestamp_ms = timestamp_ms

                builder.process_frame(
                    FrameState(
                        frame_index=frame_index,
                        timestamp_ms=timestamp_ms,
                        frame_width=frame_width,
                        frame_height=frame_height,
                        tracks=tracks,
                        moving_names=moving_names,
                    )
                )
                analyzed_frames += 1
        finally:
            capture.release()

        if analyzed_frames == 0:
            raise ValueError("No analyzable frames were available in the selected video.")

        builder.finish()

        if not builder.shots:
            notes.append("No shots were detected. Try an overhead camera angle with the full table in frame.")
        if not any(track.is_cue_ball for track in tracker.active_tracks.values()):
            notes.append("Cue ball identification stayed heuristic; scratch detection may be incomplete.")

        return PrototypeAnalysisResult(
            analyzed_frames=analyzed_frames,
            sample_fps=self.sample_fps,
            events=builder.events,
            shots=builder.shots,
            notes=notes,
            duration_ms=last_timestamp_ms,
            frame_width=frame_width,
            frame_height=frame_height,
        )

    def _normalize_frame(self, frame: np.ndarray) -> np.ndarray:
        height, width = frame.shape[:2]
        if width <= 960:
            return frame
        scale = 960.0 / float(width)
        resized_height = max(1, int(round(height * scale)))
        return cv2.resize(frame, (960, resized_height), interpolation=cv2.INTER_AREA)

    def _detect_ball_observations(self, frame: np.ndarray) -> List[BallObservation]:
        table_mask = self._build_table_mask(frame)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (9, 9), 1.6)

        min_radius = max(5, int(min(frame.shape[:2]) * 0.008))
        max_radius = max(min_radius + 3, int(min(frame.shape[:2]) * 0.028))
        min_distance = max(12, min_radius * 3)

        circles = cv2.HoughCircles(
            gray,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=min_distance,
            param1=80,
            param2=18,
            minRadius=min_radius,
            maxRadius=max_radius,
        )

        observations: List[BallObservation] = []
        if circles is not None:
            for x, y, radius in np.round(circles[0]).astype(int):
                if y < 0 or x < 0 or y >= table_mask.shape[0] or x >= table_mask.shape[1]:
                    continue
                if table_mask[y, x] == 0:
                    continue
                observations.append(self._build_observation(frame, x, y, radius, base_confidence=0.62))

        if observations:
            return self._dedupe_observations(observations)

        return self._detect_from_contours(frame, table_mask)

    def _detect_from_contours(self, frame: np.ndarray, table_mask: np.ndarray) -> List[BallObservation]:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        dominant_hue = self._dominant_table_hue(hsv, table_mask)
        hue_diff = self._hue_difference(hsv[:, :, 0].astype(np.int16), dominant_hue)

        table_pixels = table_mask > 0
        median_value = float(np.median(hsv[:, :, 2][table_pixels])) if np.any(table_pixels) else 0.0
        median_saturation = float(np.median(hsv[:, :, 1][table_pixels])) if np.any(table_pixels) else 0.0

        candidate_mask = np.zeros_like(table_mask)
        candidate_mask[
            table_pixels
            & (
                (hue_diff > 12)
                | (hsv[:, :, 2] > median_value + 35)
                | (hsv[:, :, 1] < max(25.0, median_saturation - 35))
            )
        ] = 255

        kernel = np.ones((3, 3), np.uint8)
        candidate_mask = cv2.morphologyEx(candidate_mask, cv2.MORPH_OPEN, kernel)
        candidate_mask = cv2.morphologyEx(candidate_mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(candidate_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        observations: List[BallObservation] = []

        min_area = max(40.0, (min(frame.shape[:2]) * 0.008) ** 2 * pi)
        max_area = max(min_area * 4.0, (min(frame.shape[:2]) * 0.03) ** 2 * pi)

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area or area > max_area:
                continue

            perimeter = cv2.arcLength(contour, True)
            if perimeter == 0:
                continue

            circularity = 4 * pi * area / (perimeter * perimeter)
            if circularity < 0.42:
                continue

            (x, y), radius = cv2.minEnclosingCircle(contour)
            observations.append(self._build_observation(frame, x, y, radius, base_confidence=0.54))

        return self._dedupe_observations(observations)

    def _build_observation(
        self,
        frame: np.ndarray,
        x: float,
        y: float,
        radius: float,
        *,
        base_confidence: float,
    ) -> BallObservation:
        patch_radius = max(4, int(round(radius)))
        top = max(0, int(round(y)) - patch_radius)
        bottom = min(frame.shape[0], int(round(y)) + patch_radius)
        left = max(0, int(round(x)) - patch_radius)
        right = min(frame.shape[1], int(round(x)) + patch_radius)
        patch = frame[top:bottom, left:right]

        if patch.size == 0:
            brightness = 0.0
            saturation = 0.0
        else:
            hsv_patch = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
            brightness = float(np.mean(hsv_patch[:, :, 2]))
            saturation = float(np.mean(hsv_patch[:, :, 1]))

        confidence = base_confidence
        if brightness >= 140:
            confidence += 0.08
        if saturation <= 90:
            confidence += 0.05

        return BallObservation(
            x=float(x),
            y=float(y),
            radius=float(radius),
            confidence=round(min(confidence, 0.94), 3),
            brightness=brightness,
            saturation=saturation,
        )

    def _dedupe_observations(self, observations: Sequence[BallObservation]) -> List[BallObservation]:
        deduped: List[BallObservation] = []
        for observation in sorted(observations, key=lambda item: item.confidence, reverse=True):
            if any(hypot(observation.x - existing.x, observation.y - existing.y) <= max(6.0, observation.radius) for existing in deduped):
                continue
            deduped.append(observation)
        return deduped

    def _build_table_mask(self, frame: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        dominant_hue = self._dominant_table_hue(hsv)
        hue_diff = self._hue_difference(hsv[:, :, 0].astype(np.int16), dominant_hue)

        table_mask = np.zeros(frame.shape[:2], dtype=np.uint8)
        table_mask[(hue_diff <= 18) & (hsv[:, :, 1] >= 20) & (hsv[:, :, 2] >= 20)] = 255

        kernel = np.ones((9, 9), np.uint8)
        table_mask = cv2.morphologyEx(table_mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return np.full(frame.shape[:2], 255, dtype=np.uint8)

        largest_contour = max(contours, key=cv2.contourArea)
        refined_mask = np.zeros_like(table_mask)
        cv2.drawContours(refined_mask, [largest_contour], -1, 255, thickness=-1)
        return refined_mask

    def _dominant_table_hue(self, hsv: np.ndarray, mask: Optional[np.ndarray] = None) -> int:
        height, width = hsv.shape[:2]
        central_crop = hsv[height // 4:(height * 3) // 4, width // 4:(width * 3) // 4]
        central_mask = None if mask is None else mask[height // 4:(height * 3) // 4, width // 4:(width * 3) // 4]

        valid = (central_crop[:, :, 1] > 30) & (central_crop[:, :, 2] > 30)
        if central_mask is not None:
            valid &= central_mask > 0

        if not np.any(valid):
            return 60

        hue_values = central_crop[:, :, 0][valid].astype(np.int16)
        histogram = np.bincount(hue_values, minlength=180)
        return int(histogram.argmax())

    def _hue_difference(self, hue_channel: np.ndarray, target_hue: int) -> np.ndarray:
        delta = np.abs(hue_channel - target_hue)
        return np.minimum(delta, 180 - delta)