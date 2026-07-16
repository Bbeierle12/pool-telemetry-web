"""Table calibration and perspective transformation."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Standard table dimensions (normalized coordinate system)
TABLE_WIDTH = 1000  # Length of table (long side)
TABLE_HEIGHT = 500  # Width of table (short side)

# Standard pocket positions (normalized)
POCKET_POSITIONS = {
    "top_left": (0, 0),
    "top_center": (TABLE_WIDTH / 2, 0),
    "top_right": (TABLE_WIDTH, 0),
    "bottom_left": (0, TABLE_HEIGHT),
    "bottom_center": (TABLE_WIDTH / 2, TABLE_HEIGHT),
    "bottom_right": (TABLE_WIDTH, TABLE_HEIGHT),
}

# Pocket radius for detection (normalized units)
POCKET_RADIUS = 25


@dataclass
class CalibrationData:
    """Stored calibration data for a table."""

    corners: list[tuple[float, float]]  # 4 corners in pixel coordinates
    perspective_matrix: np.ndarray | None = None
    inverse_matrix: np.ndarray | None = None
    table_width_px: int = 0
    table_height_px: int = 0

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary."""
        return {
            "corners": self.corners,
            "perspective_matrix": self.perspective_matrix.tolist() if self.perspective_matrix is not None else None,
            "inverse_matrix": self.inverse_matrix.tolist() if self.inverse_matrix is not None else None,
            "table_width_px": self.table_width_px,
            "table_height_px": self.table_height_px,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CalibrationData:
        """Create from dictionary."""
        return cls(
            corners=data["corners"],
            perspective_matrix=np.array(data["perspective_matrix"]) if data.get("perspective_matrix") else None,
            inverse_matrix=np.array(data["inverse_matrix"]) if data.get("inverse_matrix") else None,
            table_width_px=data.get("table_width_px", 0),
            table_height_px=data.get("table_height_px", 0),
        )

    def save(self, path: Path) -> None:
        """Save calibration to JSON file."""
        path.write_text(json.dumps(self.to_dict(), indent=2))
        logger.info("Saved calibration to %s", path)

    @classmethod
    def load(cls, path: Path) -> CalibrationData | None:
        """Load calibration from JSON file."""
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        logger.info("Loaded calibration from %s", path)
        return cls.from_dict(data)


class TableCalibration:
    """Handles table detection and coordinate transformation."""

    def __init__(self) -> None:
        """Initialize calibration handler."""
        self._calibration: CalibrationData | None = None
        self._is_calibrated = False

    @property
    def is_calibrated(self) -> bool:
        """Check if calibration is complete."""
        return self._is_calibrated and self._calibration is not None

    @property
    def calibration_data(self) -> CalibrationData | None:
        """Get current calibration data."""
        return self._calibration

    def calibrate_from_corners(
        self,
        corners: Sequence[tuple[float, float]],
        frame_width: int,
        frame_height: int,
    ) -> CalibrationData:
        """Calibrate using manually specified corners.

        Args:
            corners: Four corner points in pixel coordinates.
                     Order: top-left, top-right, bottom-right, bottom-left
            frame_width: Width of video frame.
            frame_height: Height of video frame.

        Returns:
            CalibrationData with perspective matrices.
        """
        if len(corners) != 4:
            raise ValueError("Exactly 4 corners required")

        # Source points (pixel coordinates from camera)
        src_points = np.array(corners, dtype=np.float32)

        # Destination points (normalized table coordinates)
        dst_points = np.array([
            [0, 0],                        # top-left
            [TABLE_WIDTH, 0],              # top-right
            [TABLE_WIDTH, TABLE_HEIGHT],   # bottom-right
            [0, TABLE_HEIGHT],             # bottom-left
        ], dtype=np.float32)

        # Calculate perspective transform matrix
        perspective_matrix = cv2.getPerspectiveTransform(src_points, dst_points)
        inverse_matrix = cv2.getPerspectiveTransform(dst_points, src_points)

        self._calibration = CalibrationData(
            corners=list(corners),
            perspective_matrix=perspective_matrix,
            inverse_matrix=inverse_matrix,
            table_width_px=frame_width,
            table_height_px=frame_height,
        )
        self._is_calibrated = True

        logger.info("Calibration complete with corners: %s", corners)
        return self._calibration

    def auto_detect_table(self, frame: np.ndarray) -> list[tuple[float, float]] | None:
        """Attempt automatic table detection using color and edge detection.

        Args:
            frame: BGR image from camera.

        Returns:
            Four corner points if detected, None otherwise.
        """
        # Convert to HSV for color detection
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Detect green felt (common pool table color)
        # Adjust these ranges for different table colors
        lower_green = np.array([35, 50, 50])
        upper_green = np.array([85, 255, 255])
        mask = cv2.inRange(hsv, lower_green, upper_green)

        # Clean up mask
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            logger.warning("No table contours detected")
            return None

        # Find largest contour (should be the table)
        largest = max(contours, key=cv2.contourArea)

        # Approximate to polygon
        epsilon = 0.02 * cv2.arcLength(largest, True)
        approx = cv2.approxPolyDP(largest, epsilon, True)

        if len(approx) != 4:
            logger.warning("Could not approximate table to 4 corners (got %d)", len(approx))
            return None

        # Order corners: top-left, top-right, bottom-right, bottom-left
        corners = self._order_corners(approx.reshape(4, 2))

        logger.info("Auto-detected table corners: %s", corners)
        return corners

    def _order_corners(self, corners: np.ndarray) -> list[tuple[float, float]]:
        """Order corners consistently: TL, TR, BR, BL."""
        # Sort by y-coordinate first (top vs bottom)
        sorted_by_y = corners[np.argsort(corners[:, 1])]

        # Top two points
        top = sorted_by_y[:2]
        top = top[np.argsort(top[:, 0])]  # Sort by x (left to right)

        # Bottom two points
        bottom = sorted_by_y[2:]
        bottom = bottom[np.argsort(bottom[:, 0])]  # Sort by x (left to right)

        return [
            (float(top[0][0]), float(top[0][1])),      # top-left
            (float(top[1][0]), float(top[1][1])),      # top-right
            (float(bottom[1][0]), float(bottom[1][1])),  # bottom-right
            (float(bottom[0][0]), float(bottom[0][1])),  # bottom-left
        ]

    def pixel_to_table(self, x: float, y: float) -> tuple[float, float]:
        """Transform pixel coordinates to table coordinates.

        Args:
            x: X coordinate in pixels.
            y: Y coordinate in pixels.

        Returns:
            (x, y) in normalized table coordinates (0-1000, 0-500).
        """
        if not self.is_calibrated or self._calibration.perspective_matrix is None:
            raise RuntimeError("Calibration required before coordinate transformation")

        point = np.array([[[x, y]]], dtype=np.float32)
        transformed = cv2.perspectiveTransform(point, self._calibration.perspective_matrix)
        return float(transformed[0][0][0]), float(transformed[0][0][1])

    def table_to_pixel(self, x: float, y: float) -> tuple[float, float]:
        """Transform table coordinates to pixel coordinates.

        Args:
            x: X coordinate in table units (0-1000).
            y: Y coordinate in table units (0-500).

        Returns:
            (x, y) in pixel coordinates.
        """
        if not self.is_calibrated or self._calibration.inverse_matrix is None:
            raise RuntimeError("Calibration required before coordinate transformation")

        point = np.array([[[x, y]]], dtype=np.float32)
        transformed = cv2.perspectiveTransform(point, self._calibration.inverse_matrix)
        return float(transformed[0][0][0]), float(transformed[0][0][1])

    def get_bird_eye_view(self, frame: np.ndarray, output_size: tuple[int, int] = (1000, 500)) -> np.ndarray:
        """Transform frame to bird's-eye view of the table.

        Args:
            frame: Original BGR frame.
            output_size: Size of output image (width, height).

        Returns:
            Warped image showing bird's-eye view.
        """
        if not self.is_calibrated or self._calibration.perspective_matrix is None:
            raise RuntimeError("Calibration required")

        return cv2.warpPerspective(
            frame,
            self._calibration.perspective_matrix,
            output_size,
        )

    def is_in_pocket(self, x: float, y: float) -> str | None:
        """Check if table coordinates are in a pocket.

        Args:
            x: X coordinate in table units.
            y: Y coordinate in table units.

        Returns:
            Pocket name if in pocket, None otherwise.
        """
        for pocket_name, (px, py) in POCKET_POSITIONS.items():
            distance = np.sqrt((x - px) ** 2 + (y - py) ** 2)
            if distance < POCKET_RADIUS:
                return pocket_name
        return None

    def draw_overlay(self, frame: np.ndarray, alpha: float = 0.3) -> np.ndarray:
        """Draw calibration overlay on frame.

        Args:
            frame: BGR frame to draw on.
            alpha: Transparency of overlay.

        Returns:
            Frame with overlay drawn.
        """
        if not self.is_calibrated:
            return frame

        overlay = frame.copy()
        corners = np.array(self._calibration.corners, dtype=np.int32)

        # Draw table boundary
        cv2.polylines(overlay, [corners], True, (0, 255, 0), 2)

        # Draw corner points
        for i, (x, y) in enumerate(self._calibration.corners):
            cv2.circle(overlay, (int(x), int(y)), 8, (0, 0, 255), -1)
            cv2.putText(
                overlay,
                str(i + 1),
                (int(x) + 10, int(y) - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )

        # Draw pocket positions (transformed to pixel coords)
        for pocket_name, (px, py) in POCKET_POSITIONS.items():
            try:
                pixel_x, pixel_y = self.table_to_pixel(px, py)
                cv2.circle(overlay, (int(pixel_x), int(pixel_y)), 15, (255, 0, 255), 2)
            except RuntimeError:
                pass

        return cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0)

    def load(self, path: Path) -> bool:
        """Load calibration from file.

        Args:
            path: Path to calibration JSON file.

        Returns:
            True if loaded successfully.
        """
        data = CalibrationData.load(path)
        if data:
            self._calibration = data
            self._is_calibrated = True
            return True
        return False

    def save(self, path: Path) -> None:
        """Save current calibration to file.

        Args:
            path: Path to save calibration JSON.
        """
        if self._calibration:
            self._calibration.save(path)
