from __future__ import annotations

import time

import cv2
from PyQt6 import QtCore

from .sources import VideoSettings, VideoSource, open_capture


class VideoWorker(QtCore.QThread):
    frame_ready = QtCore.pyqtSignal(object, float)
    status = QtCore.pyqtSignal(str)
    error = QtCore.pyqtSignal(str)
    ended = QtCore.pyqtSignal()

    def __init__(
        self,
        source: VideoSource,
        settings: VideoSettings | None = None,
        target_fps: float | None = None,
        playback_real_time: bool = False,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._source = source
        self._settings = settings
        self._target_fps = target_fps
        self._playback_real_time = playback_real_time
        self._running = True
        self._is_file_source = isinstance(source, str)

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        cap = open_capture(self._source, self._settings)
        if not cap.isOpened():
            self.error.emit(f"Video source failed to open: {self._source}")
            self.ended.emit()
            return

        frame_delay = None
        if self._target_fps and self._target_fps > 0:
            frame_delay = 1.0 / self._target_fps
        elif self._playback_real_time:
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps and fps > 0:
                frame_delay = 1.0 / fps

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) if self._is_file_source else 0
        frame_count = 0
        self.status.emit("Video source connected")

        while self._running:
            ok, frame = cap.read()
            if not ok:
                if self._is_file_source:
                    # End of file reached
                    self.status.emit("Video playback complete")
                else:
                    # Live source read failure
                    self.error.emit("Video capture read failed")
                break
            frame_count += 1
            timestamp_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
            self.frame_ready.emit(frame, timestamp_ms)
            if frame_delay:
                time.sleep(frame_delay)

        cap.release()
        if self._running:
            # Ended naturally (not stopped by user)
            if self._is_file_source and total_frames > 0:
                self.status.emit(f"Processed {frame_count}/{total_frames} frames")
        else:
            self.status.emit("Video source stopped by user")
        self.ended.emit()
