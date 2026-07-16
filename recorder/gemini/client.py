from __future__ import annotations

import base64
import json
import queue
import time
from dataclasses import dataclass

import websocket
from PyQt6 import QtCore


GEMINI_BASE_URL = "wss://generativelanguage.googleapis.com/v1beta/models"


@dataclass
class GeminiConnection:
    api_key: str
    model: str
    system_prompt: str = ""
    reconnect_attempts: int = 3
    reconnect_delay_ms: int = 1000
    base_url: str = GEMINI_BASE_URL

    @property
    def endpoint(self) -> str:
        """Construct full endpoint URL using the configured model."""
        return f"{self.base_url}/{self.model}:streamGenerateContent"


class GeminiClient(QtCore.QThread):
    raw_event = QtCore.pyqtSignal(str)
    status = QtCore.pyqtSignal(str)
    error = QtCore.pyqtSignal(str)

    # Maximum frames to buffer before dropping; prevents unbounded memory growth
    MAX_QUEUE_SIZE = 60

    def __init__(
        self,
        connection: GeminiConnection,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._connection = connection
        self._running = True
        self._queue: queue.Queue[dict] = queue.Queue(maxsize=self.MAX_QUEUE_SIZE)

    def stop(self) -> None:
        self._running = False

    def enqueue_frame(self, frame_bytes: bytes, timestamp_ms: float) -> None:
        payload = {
            "frame": base64.b64encode(frame_bytes).decode("ascii"),
            "timestamp_ms": int(timestamp_ms),
        }
        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            # Drop frame if queue is full to prevent memory growth and blocking
            pass

    def run(self) -> None:
        headers = [f"x-goog-api-key: {self._connection.api_key}"]
        attempts = 0
        max_attempts = self._connection.reconnect_attempts
        base_delay = max(0.5, self._connection.reconnect_delay_ms / 1000.0)

        while self._running:
            ws = websocket.WebSocket()
            ws.settimeout(0.1)
            try:
                ws.connect(self._connection.endpoint, header=headers)
            except Exception as exc:
                attempts += 1
                self.error.emit(f"Gemini connection failed: {exc}")
                if max_attempts and attempts >= max_attempts:
                    self.error.emit("Gemini reconnect attempts exceeded")
                    return
                time.sleep(base_delay * (2 ** (attempts - 1)))
                continue

            attempts = 0
            self.status.emit("Gemini connected")
            if self._connection.system_prompt:
                self._send_system_prompt(ws, self._connection.system_prompt)

            try:
                self._run_connection(ws)
            finally:
                try:
                    ws.close()
                except Exception:
                    pass
                self.status.emit("Gemini disconnected")

            if self._running:
                time.sleep(base_delay)

    def _run_connection(self, ws: websocket.WebSocket) -> None:
        while self._running:
            self._drain_queue(ws)
            try:
                message = ws.recv()
            except websocket.WebSocketTimeoutException:
                continue
            except Exception as exc:
                self.error.emit(f"Gemini connection error: {exc}")
                return
            if message:
                self.raw_event.emit(message)

    def _drain_queue(self, ws: websocket.WebSocket) -> None:
        while not self._queue.empty():
            payload = self._queue.get()
            message = self._build_frame_message(payload)
            try:
                ws.send(message)
            except Exception as exc:
                self.error.emit(f"Gemini send failed: {exc}")
                time.sleep(0.2)
                break

    def _build_frame_message(self, payload: dict) -> str:
        return json.dumps(
            {
                "model": self._connection.model,
                "content": [
                    {
                        "type": "input_image",
                        "image": {"base64": payload["frame"]},
                    }
                ],
                "metadata": {"timestamp_ms": payload["timestamp_ms"]},
            }
        )

    def _send_system_prompt(self, ws: websocket.WebSocket, prompt: str) -> None:
        message = json.dumps(
            {
                "model": self._connection.model,
                "content": [
                    {
                        "type": "input_text",
                        "text": prompt,
                    }
                ],
            }
        )
        try:
            ws.send(message)
        except Exception as exc:
            self.error.emit(f"Gemini prompt send failed: {exc}")
