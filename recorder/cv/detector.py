"""Ball detection using YOLOv8."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

logger = logging.getLogger(__name__)

# Ball class names mapping
BALL_CLASSES = {
    0: "cue",
    1: "solid_1",
    2: "solid_2",
    3: "solid_3",
    4: "solid_4",
    5: "solid_5",
    6: "solid_6",
    7: "solid_7",
    8: "eight_ball",
    9: "stripe_9",
    10: "stripe_10",
    11: "stripe_11",
    12: "stripe_12",
    13: "stripe_13",
    14: "stripe_14",
    15: "stripe_15",
}

# Reverse mapping
CLASS_TO_ID = {v: k for k, v in BALL_CLASSES.items()}


@dataclass
class DetectedBall:
    """A detected ball in a frame."""

    class_name: str          # "cue", "solid_1", "stripe_9", "eight_ball", etc.
    class_id: int            # Numeric class ID
    x: float                 # Center X in table coordinates (0-1000)
    y: float                 # Center Y in table coordinates (0-500)
    x_pixel: float           # Center X in pixel coordinates
    y_pixel: float           # Center Y in pixel coordinates
    confidence: float        # Detection confidence (0.0-1.0)
    bbox: tuple[float, float, float, float]  # (x1, y1, x2, y2) in pixels
    radius_pixel: float      # Estimated ball radius in pixels

    @property
    def is_cue(self) -> bool:
        """Check if this is the cue ball."""
        return self.class_name == "cue"

    @property
    def is_solid(self) -> bool:
        """Check if this is a solid ball (1-7)."""
        return self.class_name.startswith("solid_")

    @property
    def is_stripe(self) -> bool:
        """Check if this is a stripe ball (9-15)."""
        return self.class_name.startswith("stripe_")

    @property
    def is_eight(self) -> bool:
        """Check if this is the 8-ball."""
        return self.class_name == "eight_ball"

    @property
    def ball_number(self) -> int | None:
        """Get ball number (1-15) or None for cue."""
        if self.is_cue:
            return None
        if self.is_eight:
            return 8
        try:
            return int(self.class_name.split("_")[1])
        except (IndexError, ValueError):
            return None


class BallDetector:
    """YOLOv8-based ball detector."""

    def __init__(
        self,
        model_path: str | Path | None = None,
        confidence_threshold: float = 0.5,
        device: str = "auto",
    ) -> None:
        """Initialize ball detector.

        Args:
            model_path: Path to YOLOv8 weights file. If None, uses default model.
            confidence_threshold: Minimum confidence for detections.
            device: Device to run on ("cpu", "cuda", "mps", or "auto").
        """
        self._confidence_threshold = confidence_threshold
        self._device = device
        self._model = None
        self._model_path = model_path

        # Lazy load to avoid import errors if ultralytics not installed
        self._ultralytics_available = False

    def _ensure_model_loaded(self) -> None:
        """Load model if not already loaded."""
        if self._model is not None:
            return

        try:
            from ultralytics import YOLO

            self._ultralytics_available = True

            if self._model_path and Path(self._model_path).exists():
                logger.info("Loading custom model from %s", self._model_path)
                self._model = YOLO(str(self._model_path))
            else:
                # Use pre-trained YOLOv8 model
                # In production, you'd want a fine-tuned pool ball model
                logger.info("Loading default YOLOv8n model (not trained for pool balls)")
                self._model = YOLO("yolov8n.pt")

            # Set device
            if self._device == "auto":
                # Let YOLO decide
                pass
            else:
                self._model.to(self._device)

        except ImportError:
            logger.error("ultralytics not installed. Run: pip install ultralytics")
            raise RuntimeError("ultralytics package required for ball detection")

    def detect(
        self,
        frame: np.ndarray,
        calibration=None,
    ) -> list[DetectedBall]:
        """Detect balls in a frame.

        Args:
            frame: BGR image from camera.
            calibration: Optional TableCalibration for coordinate transform.

        Returns:
            List of detected balls.
        """
        self._ensure_model_loaded()

        # Run inference
        results = self._model(
            frame,
            conf=self._confidence_threshold,
            verbose=False,
        )

        detections = []

        for result in results:
            boxes = result.boxes

            if boxes is None:
                continue

            for i in range(len(boxes)):
                # Get box coordinates
                x1, y1, x2, y2 = boxes.xyxy[i].cpu().numpy()
                conf = float(boxes.conf[i].cpu().numpy())
                class_id = int(boxes.cls[i].cpu().numpy())

                # Calculate center and radius
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                radius = min(x2 - x1, y2 - y1) / 2

                # Get class name
                class_name = BALL_CLASSES.get(class_id, f"unknown_{class_id}")

                # Transform to table coordinates if calibration available
                if calibration and calibration.is_calibrated:
                    try:
                        table_x, table_y = calibration.pixel_to_table(center_x, center_y)
                    except RuntimeError:
                        table_x, table_y = center_x, center_y
                else:
                    table_x, table_y = center_x, center_y

                detection = DetectedBall(
                    class_name=class_name,
                    class_id=class_id,
                    x=table_x,
                    y=table_y,
                    x_pixel=center_x,
                    y_pixel=center_y,
                    confidence=conf,
                    bbox=(float(x1), float(y1), float(x2), float(y2)),
                    radius_pixel=radius,
                )
                detections.append(detection)

        logger.debug("Detected %d balls", len(detections))
        return detections

    def detect_with_fallback(
        self,
        frame: np.ndarray,
        calibration=None,
    ) -> list[DetectedBall]:
        """Detect balls with color-based fallback for cue ball.

        If YOLO doesn't detect a cue ball, try color-based detection.

        Args:
            frame: BGR image from camera.
            calibration: Optional TableCalibration for coordinate transform.

        Returns:
            List of detected balls.
        """
        detections = self.detect(frame, calibration)

        # Check if cue ball was detected
        has_cue = any(d.is_cue for d in detections)

        if not has_cue:
            # Try color-based cue ball detection
            cue_detection = self._detect_cue_by_color(frame, calibration)
            if cue_detection:
                detections.append(cue_detection)

        return detections

    def _detect_cue_by_color(
        self,
        frame: np.ndarray,
        calibration=None,
    ) -> DetectedBall | None:
        """Detect cue ball using color (white ball detection).

        Args:
            frame: BGR image.
            calibration: Optional calibration for coordinate transform.

        Returns:
            DetectedBall if found, None otherwise.
        """
        import cv2

        # Convert to HSV
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # White color range (cue ball)
        lower_white = np.array([0, 0, 200])
        upper_white = np.array([180, 30, 255])
        mask = cv2.inRange(hsv, lower_white, upper_white)

        # Clean up mask
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        # Find circles using Hough transform
        circles = cv2.HoughCircles(
            mask,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=50,
            param1=50,
            param2=30,
            minRadius=10,
            maxRadius=50,
        )

        if circles is None:
            return None

        # Take the most circular/confident detection
        circles = np.uint16(np.around(circles))
        x, y, r = circles[0][0]

        center_x, center_y = float(x), float(y)
        radius = float(r)

        # Transform to table coordinates if calibration available
        if calibration and calibration.is_calibrated:
            try:
                table_x, table_y = calibration.pixel_to_table(center_x, center_y)
            except RuntimeError:
                table_x, table_y = center_x, center_y
        else:
            table_x, table_y = center_x, center_y

        return DetectedBall(
            class_name="cue",
            class_id=0,
            x=table_x,
            y=table_y,
            x_pixel=center_x,
            y_pixel=center_y,
            confidence=0.7,  # Lower confidence for color-based detection
            bbox=(center_x - radius, center_y - radius, center_x + radius, center_y + radius),
            radius_pixel=radius,
        )

    def draw_detections(
        self,
        frame: np.ndarray,
        detections: Sequence[DetectedBall],
        show_labels: bool = True,
        show_confidence: bool = True,
    ) -> np.ndarray:
        """Draw detection boxes on frame.

        Args:
            frame: BGR image to draw on.
            detections: List of detections to draw.
            show_labels: Whether to show class labels.
            show_confidence: Whether to show confidence scores.

        Returns:
            Frame with detections drawn.
        """
        import cv2

        output = frame.copy()

        for det in detections:
            x1, y1, x2, y2 = det.bbox

            # Color based on ball type
            if det.is_cue:
                color = (255, 255, 255)  # White
            elif det.is_solid:
                color = (255, 165, 0)    # Orange
            elif det.is_stripe:
                color = (0, 255, 255)    # Yellow
            elif det.is_eight:
                color = (0, 0, 0)        # Black
            else:
                color = (128, 128, 128)  # Gray

            # Draw bounding box
            cv2.rectangle(
                output,
                (int(x1), int(y1)),
                (int(x2), int(y2)),
                color,
                2,
            )

            # Draw center point
            cv2.circle(
                output,
                (int(det.x_pixel), int(det.y_pixel)),
                3,
                color,
                -1,
            )

            # Draw label
            if show_labels:
                label = det.class_name
                if show_confidence:
                    label += f" {det.confidence:.2f}"

                cv2.putText(
                    output,
                    label,
                    (int(x1), int(y1) - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    1,
                )

        return output


def create_detector(
    model_path: str | Path | None = None,
    confidence_threshold: float = 0.5,
) -> BallDetector:
    """Factory function to create a ball detector.

    Args:
        model_path: Path to custom YOLOv8 weights.
        confidence_threshold: Minimum detection confidence.

    Returns:
        Configured BallDetector instance.
    """
    return BallDetector(
        model_path=model_path,
        confidence_threshold=confidence_threshold,
    )
