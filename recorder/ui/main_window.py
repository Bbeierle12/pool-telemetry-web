from __future__ import annotations

import time

import cv2

from PyQt6 import QtCore, QtGui, QtWidgets

from ..config import AppConfig
from ..exporter import ExportManager
from ..gemini.client import GeminiClient, GeminiConnection
from ..gemini.processor import EventProcessor, EventRecord
from ..sessions import SessionManager
from ..storage import StorageManager
from ..video.sources import VideoSettings, parse_resolution
from ..video.worker import VideoWorker
from .dialogs import GoProConnectDialog
from .export_dialog import ExportDialog
from .session_browser import SessionBrowserDialog
from .settings_dialog import SettingsDialog


class MainWindow(QtWidgets.QMainWindow):
    def __init__(
        self,
        config: AppConfig,
        event_processor: EventProcessor,
        session_manager: SessionManager,
        export_manager: ExportManager,
        storage_manager: StorageManager,
    ) -> None:
        super().__init__()
        self._config = config
        self._event_processor = event_processor
        self._session_manager = session_manager
        self._export_manager = export_manager
        self._storage_manager = storage_manager
        self._video_worker: VideoWorker | None = None
        self._gemini_client: GeminiClient | None = None
        self._last_frame = None
        self._video_label: QtWidgets.QLabel | None = None
        self._event_log: QtWidgets.QPlainTextEdit | None = None
        self._ball_table: QtWidgets.QTableWidget | None = None
        self._ball_rows: dict[str, int] = {}
        self._shot_count = 0
        self._pocketed_count = 0
        self._foul_count = 0
        self._counted_shots: set[int] = set()
        self._session_start: float | None = None
        self._session_id: str | None = None
        self._last_session_id: str | None = None
        self._current_source_type = "unknown"
        self._current_source_path = ""
        self._cost_total = 0.0
        self._runtime_label: QtWidgets.QLabel | None = None
        self._shots_label: QtWidgets.QLabel | None = None
        self._pocketed_label: QtWidgets.QLabel | None = None
        self._fouls_label: QtWidgets.QLabel | None = None
        self._cost_label: QtWidgets.QLabel | None = None
        self._runtime_timer = QtCore.QTimer(self)
        self._last_frame_time = 0.0
        self._max_preview_fps = 30.0
        self._last_gemini_send = 0.0
        self._paused = False
        self._pause_button: QtWidgets.QPushButton | None = None
        self._source_status_label = QtWidgets.QLabel("Source: Disconnected")
        self._gemini_status_label = QtWidgets.QLabel("Gemini: Disconnected")
        self.setWindowTitle("Pool Telemetry Recorder")
        self.resize(1200, 800)
        self._build_menu()
        self._build_layout()
        self.statusBar().addPermanentWidget(self._source_status_label)
        self.statusBar().addPermanentWidget(self._gemini_status_label)
        self.statusBar().showMessage("Ready")
        self._event_processor.event_ready.connect(self._on_event_ready)
        self._event_processor.error.connect(self._on_event_error)
        self._runtime_timer.timeout.connect(self._update_runtime)
        self._runtime_timer.start(1000)

    def _build_menu(self) -> None:
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("File")
        new_session_action = QtGui.QAction("New Session", self)
        new_session_action.setShortcut("Ctrl+N")
        new_session_action.triggered.connect(self._on_new_session)
        file_menu.addAction(new_session_action)

        export_action = QtGui.QAction("Export...", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self._on_export)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        exit_action = QtGui.QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Session menu
        session_menu = menu_bar.addMenu("Session")
        browser_action = QtGui.QAction("Session Browser...", self)
        browser_action.setShortcut("Ctrl+B")
        browser_action.triggered.connect(self._open_session_browser)
        session_menu.addAction(browser_action)

        session_menu.addSeparator()

        start_action = QtGui.QAction("Start Recording", self)
        start_action.setShortcut("F5")
        start_action.triggered.connect(self._on_session_start)
        session_menu.addAction(start_action)

        pause_action = QtGui.QAction("Pause/Resume", self)
        pause_action.setShortcut("F6")
        pause_action.triggered.connect(self._on_session_pause)
        session_menu.addAction(pause_action)

        stop_action = QtGui.QAction("Stop Recording", self)
        stop_action.setShortcut("F7")
        stop_action.triggered.connect(self._on_session_stop)
        session_menu.addAction(stop_action)

        # View menu
        view_menu = menu_bar.addMenu("View")
        self._show_raw_json_action = QtGui.QAction("Show Raw JSON", self)
        self._show_raw_json_action.setCheckable(True)
        self._show_raw_json_action.setChecked(self._config.ui.show_raw_json)
        self._show_raw_json_action.triggered.connect(self._toggle_raw_json)
        view_menu.addAction(self._show_raw_json_action)

        self._show_trajectory_action = QtGui.QAction("Show Trajectory Overlay", self)
        self._show_trajectory_action.setCheckable(True)
        self._show_trajectory_action.setChecked(self._config.ui.show_trajectory_overlay)
        self._show_trajectory_action.triggered.connect(self._toggle_trajectory_overlay)
        view_menu.addAction(self._show_trajectory_action)

        view_menu.addSeparator()

        clear_log_action = QtGui.QAction("Clear Event Log", self)
        clear_log_action.triggered.connect(self._clear_event_log)
        view_menu.addAction(clear_log_action)

        # Analysis menu
        analysis_menu = menu_bar.addMenu("Analysis")
        analyze_session_action = QtGui.QAction("Analyze Current Session...", self)
        analyze_session_action.triggered.connect(self._on_analyze)
        analysis_menu.addAction(analyze_session_action)

        analysis_menu.addSeparator()

        shot_breakdown_action = QtGui.QAction("Shot Breakdown", self)
        shot_breakdown_action.triggered.connect(self._show_shot_breakdown)
        analysis_menu.addAction(shot_breakdown_action)

        accuracy_stats_action = QtGui.QAction("Accuracy Statistics", self)
        accuracy_stats_action.triggered.connect(self._show_accuracy_stats)
        analysis_menu.addAction(accuracy_stats_action)

        # Settings menu
        settings_menu = menu_bar.addMenu("Settings")
        settings_action = QtGui.QAction("Preferences...", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._open_settings)
        settings_menu.addAction(settings_action)

        # Help menu
        help_menu = menu_bar.addMenu("Help")
        about_action = QtGui.QAction("About Pool Telemetry Recorder", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        help_menu.addSeparator()

        docs_action = QtGui.QAction("Documentation", self)
        docs_action.setShortcut("F1")
        docs_action.triggered.connect(self._show_documentation)
        help_menu.addAction(docs_action)

        shortcuts_action = QtGui.QAction("Keyboard Shortcuts", self)
        shortcuts_action.triggered.connect(self._show_shortcuts)
        help_menu.addAction(shortcuts_action)

    def _build_layout(self) -> None:
        central = QtWidgets.QWidget()
        layout = QtWidgets.QGridLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(12)

        video_panel = self._video_panel()
        ball_panel = self._ball_matrix_panel()
        event_panel = self._event_panel()
        session_panel = self._session_info_panel()
        controls_panel = self._controls_panel()

        layout.addWidget(video_panel, 0, 0)
        layout.addWidget(ball_panel, 0, 1)
        layout.addWidget(event_panel, 1, 0, 1, 2)
        layout.addWidget(session_panel, 2, 0)
        layout.addWidget(controls_panel, 2, 1)

        layout.setColumnStretch(0, 3)
        layout.setColumnStretch(1, 2)
        layout.setRowStretch(1, 2)

        self.setCentralWidget(central)
        self._apply_theme()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self._stop_video_worker()
        self._stop_gemini_client()
        self._event_processor.close()
        super().closeEvent(event)

    def _event_panel(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("Event Stream")
        layout = QtWidgets.QVBoxLayout(group)
        self._event_log = QtWidgets.QPlainTextEdit()
        self._event_log.setReadOnly(True)
        self._event_log.setPlaceholderText("Waiting for session to start...")
        layout.addWidget(self._event_log)
        return group

    def _ball_matrix_panel(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("Ball Matrix")
        layout = QtWidgets.QVBoxLayout(group)
        table = QtWidgets.QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Ball", "Position", "Confidence", "Motion"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        table.setRowCount(16)
        ball_labels = [
            "CUE",
            "1-S",
            "2-S",
            "3-S",
            "4-S",
            "5-S",
            "6-S",
            "7-S",
            "8",
            "9-T",
            "10-T",
            "11-T",
            "12-T",
            "13-T",
            "14-T",
            "15-T",
        ]
        for row, label in enumerate(ball_labels):
            self._ball_rows[label] = row
            table.setItem(row, 0, QtWidgets.QTableWidgetItem(label))
            table.setItem(row, 1, QtWidgets.QTableWidgetItem("[---, ---]"))
            confidence_bar = QtWidgets.QProgressBar()
            confidence_bar.setRange(0, 100)
            confidence_bar.setValue(0)
            table.setCellWidget(row, 2, confidence_bar)
            table.setItem(row, 3, QtWidgets.QTableWidgetItem("--"))

        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        table.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        table.horizontalHeader().setSectionResizeMode(
            2, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        self._ball_table = table
        layout.addWidget(table)
        return group

    def _session_info_panel(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("Session Info")
        layout = QtWidgets.QGridLayout(group)
        self._shots_label = QtWidgets.QLabel("Shots: 0")
        self._pocketed_label = QtWidgets.QLabel("Pocketed: 0")
        self._fouls_label = QtWidgets.QLabel("Fouls: 0")
        self._runtime_label = QtWidgets.QLabel("Runtime: 00:00:00")
        self._cost_label = QtWidgets.QLabel("Cost: $0.00")
        layout.addWidget(self._shots_label, 0, 0)
        layout.addWidget(self._pocketed_label, 0, 1)
        layout.addWidget(self._fouls_label, 1, 0)
        layout.addWidget(self._runtime_label, 1, 1)
        layout.addWidget(self._cost_label, 2, 0)
        return group

    def _video_panel(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("Video")
        layout = QtWidgets.QVBoxLayout(group)
        self._video_label = QtWidgets.QLabel("No video source")
        self._video_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._video_label.setMinimumHeight(260)

        button_row = QtWidgets.QHBoxLayout()
        connect_button = QtWidgets.QPushButton("Connect GoPro")
        import_button = QtWidgets.QPushButton("Import Video")
        connect_button.clicked.connect(self._on_connect_gopro)
        import_button.clicked.connect(self._on_import_video)
        button_row.addWidget(connect_button)
        button_row.addWidget(import_button)
        button_row.addStretch(1)

        layout.addWidget(self._video_label)
        layout.addLayout(button_row)
        return group

    def _controls_panel(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("Controls")
        layout = QtWidgets.QHBoxLayout(group)
        start_button = QtWidgets.QPushButton("Start")
        self._pause_button = QtWidgets.QPushButton("Pause")
        stop_button = QtWidgets.QPushButton("Stop")
        export_button = QtWidgets.QPushButton("Export")
        analyze_button = QtWidgets.QPushButton("Analyze")
        start_button.clicked.connect(self._on_session_start)
        self._pause_button.clicked.connect(self._on_session_pause)
        stop_button.clicked.connect(self._on_session_stop)
        export_button.clicked.connect(self._on_export)
        analyze_button.clicked.connect(self._on_analyze)
        layout.addWidget(start_button)
        layout.addWidget(self._pause_button)
        layout.addWidget(stop_button)
        layout.addStretch(1)
        layout.addWidget(export_button)
        layout.addWidget(analyze_button)
        return group

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        if self._last_frame is not None:
            self._update_video_label(self._last_frame)

    def _on_connect_gopro(self) -> None:
        dialog = GoProConnectDialog(self._config.gopro, self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        source, resolution, framerate, stabilization = dialog.values()
        connection_mode = dialog.connection_mode()
        wifi_ip = dialog.wifi_ip()

        # Determine source type and path for session tracking
        if connection_mode == "wifi":
            self._current_source_type = "gopro_wifi"
            self._current_source_path = wifi_ip or str(source)
        else:
            self._current_source_type = "gopro_usb"
            self._current_source_path = f"device:{source}" if isinstance(source, int) else str(source)

        settings = VideoSettings(
            resolution=parse_resolution(resolution),
            framerate=framerate,
            stabilization=stabilization,
        )
        self._start_video_source(source, settings, playback_real_time=False)

    def _on_import_video(self) -> None:
        formats = self._config.video_import.supported_formats
        globs = " ".join(f"*.{ext}" for ext in formats)
        filter_text = f"Video Files ({globs});;All Files (*.*)"
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Import Video",
            self._config.video_import.default_directory,
            filter_text,
        )
        if not path:
            return
        self._current_source_type = "video_file"
        self._current_source_path = path
        self._start_video_source(path, None, playback_real_time=True)

    def _start_video_source(
        self,
        source: int | str,
        settings: VideoSettings | None,
        playback_real_time: bool,
    ) -> None:
        self._stop_video_worker()
        self._video_worker = VideoWorker(
            source,
            settings=settings,
            playback_real_time=playback_real_time,
        )
        self._video_worker.frame_ready.connect(self._on_frame_ready)
        self._video_worker.status.connect(self.statusBar().showMessage)
        self._video_worker.error.connect(self._on_video_error)
        self._video_worker.ended.connect(self._on_video_ended)
        self._video_worker.start()
        self._set_source_status("Connected")

    def _on_video_error(self, message: str) -> None:
        self.statusBar().showMessage(f"Video error: {message}")
        self._set_source_status("Error")

    def _stop_video_worker(self) -> None:
        if not self._video_worker:
            return
        self._video_worker.stop()
        self._video_worker.wait(1000)
        self._video_worker = None

    def _on_video_ended(self) -> None:
        if self._video_label:
            self._video_label.setText("No video source")
        self._set_source_status("Disconnected")

    def _on_frame_ready(self, frame, timestamp_ms: float) -> None:
        now = time.monotonic()
        min_interval = 1.0 / self._max_preview_fps
        if now - self._last_frame_time < min_interval:
            return
        self._last_frame_time = now
        self._last_frame = frame
        self._update_video_label(frame)
        self._send_frame_to_gemini(frame, timestamp_ms)

    def _update_video_label(self, frame) -> None:
        if not self._video_label:
            return
        height, width, channels = frame.shape
        bytes_per_line = channels * width
        # QImage wraps the buffer without copying, so we must copy() to ensure
        # the data remains valid after the original frame array is released/modified
        image = QtGui.QImage(
            frame.data,
            width,
            height,
            bytes_per_line,
            QtGui.QImage.Format.Format_BGR888,
        ).copy()
        pixmap = QtGui.QPixmap.fromImage(image)
        scaled = pixmap.scaled(
            self._video_label.size(),
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        self._video_label.setPixmap(scaled)

    def _on_event_ready(self, record: EventRecord) -> None:
        if not self._event_log:
            return
        seconds = record.timestamp_ms / 1000.0
        line = f"{seconds:10.3f}  {record.event_type}"
        self._event_log.appendPlainText(line)
        self._apply_event_to_state(record)

    def _apply_event_to_state(self, record: EventRecord) -> None:
        payload = record.event_data
        event_type = str(record.event_type).upper()
        shot_number = payload.get("shot_number")
        if shot_number is not None:
            try:
                shot_number = int(shot_number)
            except (TypeError, ValueError):
                shot_number = None

        # Track shot events and save key frames
        if event_type in {"SHOT_START", "SHOT_BEGIN"}:
            self._increment_shot(shot_number)
            self._save_shot_frame("pre_shot", shot_number, record.timestamp_ms)
        elif event_type == "SHOT":
            phase = str(payload.get("phase", "")).upper()
            if phase in {"START", "BEGIN"}:
                self._increment_shot(shot_number)
                self._save_shot_frame("pre_shot", shot_number, record.timestamp_ms)
            elif phase in {"END", "COMPLETE"}:
                self._save_shot_frame("post_shot", shot_number, record.timestamp_ms)
        elif event_type in {"SHOT_END", "SHOT_COMPLETE"}:
            self._save_shot_frame("post_shot", shot_number, record.timestamp_ms)

        if event_type in {"POCKET", "POCKETED"}:
            self._pocketed_count += 1
            if self._pocketed_label:
                self._pocketed_label.setText(f"Pocketed: {self._pocketed_count}")

        if event_type in {"FOUL", "FOUL_COMMITTED"}:
            self._foul_count += 1
            if self._fouls_label:
                self._fouls_label.setText(f"Fouls: {self._foul_count}")

        ball_updates = self._extract_ball_updates(payload)
        for update in ball_updates:
            self._update_ball_row(
                update.get("id"),
                update.get("position"),
                update.get("confidence"),
                update.get("motion"),
            )

        cost_value = payload.get("cost_usd") or payload.get("cost")
        if isinstance(cost_value, (int, float)):
            self._cost_total += float(cost_value)
            if self._cost_label:
                self._cost_label.setText(f"Cost: ${self._cost_total:.2f}")
            warn_threshold = self._config.cost_tracking.warn_threshold_usd
            stop_threshold = self._config.cost_tracking.stop_threshold_usd
            if stop_threshold and self._cost_total >= stop_threshold:
                self.statusBar().showMessage("Cost stop threshold reached - stopping session")
                self._on_session_stop()
            elif warn_threshold and self._cost_total >= warn_threshold:
                self.statusBar().showMessage("Cost warning threshold reached")

    def _increment_shot(self, shot_number: int | None) -> None:
        if shot_number is not None:
            if shot_number in self._counted_shots:
                return
            self._counted_shots.add(shot_number)
        self._shot_count += 1
        if self._shots_label:
            self._shots_label.setText(f"Shots: {self._shot_count}")

    def _save_shot_frame(
        self, frame_type: str, shot_number: int | None, timestamp_ms: int
    ) -> None:
        """Save a key frame for a shot event."""
        if self._session_id is None or self._last_frame is None:
            return
        if not self._config.storage.save_key_frames:
            return
        self._storage_manager.save_frame(
            self._session_id,
            self._last_frame,
            frame_type,
            shot_number=shot_number or self._shot_count,
            timestamp_ms=timestamp_ms,
        )

    def _extract_ball_updates(self, payload: dict) -> list[dict]:
        candidates = []
        if "balls" in payload:
            candidates = payload.get("balls", [])
        elif "table_state" in payload and isinstance(payload["table_state"], dict):
            candidates = payload["table_state"].get("balls", [])
        elif "ball_positions" in payload:
            candidates = payload.get("ball_positions", [])

        updates = []
        if isinstance(candidates, dict):
            for ball_id, position in candidates.items():
                updates.append(
                    {"id": str(ball_id), "position": position, "confidence": None, "motion": None}
                )
            return updates

        if not isinstance(candidates, list):
            return updates

        for ball in candidates:
            if not isinstance(ball, dict):
                continue
            updates.append(
                {
                    "id": ball.get("id") or ball.get("label") or ball.get("ball"),
                    "position": ball.get("position") or ball.get("pos"),
                    "confidence": ball.get("confidence"),
                    "motion": ball.get("motion") or ball.get("state"),
                }
            )
        return updates

    def _update_ball_row(
        self,
        ball_id: object,
        position: object,
        confidence: object,
        motion: object,
    ) -> None:
        if not self._ball_table:
            return
        label = self._normalize_ball_label(ball_id)
        if not label or label not in self._ball_rows:
            return
        row = self._ball_rows[label]
        position_text = "[---, ---]"
        if isinstance(position, (list, tuple)) and len(position) >= 2:
            position_text = f"[{position[0]}, {position[1]}]"
        self._ball_table.item(row, 1).setText(position_text)
        if isinstance(confidence, (int, float)):
            widget = self._ball_table.cellWidget(row, 2)
            if isinstance(widget, QtWidgets.QProgressBar):
                widget.setValue(max(0, min(100, int(confidence * 100))))
        if motion is not None:
            self._ball_table.item(row, 3).setText(str(motion))

    def _normalize_ball_label(self, ball_id: object) -> str | None:
        if ball_id is None:
            return None
        if isinstance(ball_id, str):
            upper = ball_id.strip().upper()
            if upper in self._ball_rows:
                return upper
            if upper.isdigit():
                return self._number_to_label(int(upper))
            return upper
        if isinstance(ball_id, int):
            return self._number_to_label(ball_id)
        return None

    def _number_to_label(self, number: int) -> str | None:
        if number == 0:
            return "CUE"
        if number == 8:
            return "8"
        if 1 <= number <= 7:
            return f"{number}-S"
        if 9 <= number <= 15:
            return f"{number}-T"
        return None

    def _on_session_pause(self) -> None:
        if not self._session_id:
            return
        self._paused = not self._paused
        if self._paused:
            self.statusBar().showMessage("Paused - Gemini analysis suspended")
            if self._pause_button:
                self._pause_button.setText("Resume")
        else:
            self.statusBar().showMessage("Recording")
            if self._pause_button:
                self._pause_button.setText("Pause")

    def _on_session_stop(self) -> None:
        self.statusBar().showMessage("Stopped")
        if self._session_id:
            self._last_session_id = self._session_id

            # Update storage metadata with final stats
            self._storage_manager.update_session_metadata(
                self._session_id,
                {
                    "ended_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "total_shots": self._shot_count,
                    "total_pocketed": self._pocketed_count,
                    "total_fouls": self._foul_count,
                    "cost_usd": self._cost_total,
                },
            )

            self._session_manager.end_session(
                self._session_id,
                self._shot_count,
                self._pocketed_count,
                self._foul_count,
                self._cost_total,
            )
            self._event_processor.set_session(None)
            self._session_id = None
            self._reset_session_counters()
        self._stop_gemini_client()

    def _update_runtime(self) -> None:
        if not self._runtime_label:
            return
        if self._session_start is None:
            return
        elapsed = int(time.time() - self._session_start)
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60
        self._runtime_label.setText(f"Runtime: {hours:02d}:{minutes:02d}:{seconds:02d}")

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #12161c;
                color: #e6e6e6;
            }
            QGroupBox {
                border: 1px solid #2b3440;
                border-radius: 6px;
                margin-top: 10px;
                padding: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px 0 4px;
            }
            QPlainTextEdit, QTableWidget, QLineEdit {
                background-color: #0f1318;
                border: 1px solid #2b3440;
                color: #e6e6e6;
            }
            QPushButton {
                background-color: #1f6feb;
                color: #ffffff;
                border-radius: 4px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background-color: #2b7cff;
            }
            QPushButton:disabled {
                background-color: #3a3f46;
                color: #9aa0a6;
            }
            """
        )

    def _on_event_error(self, message: str) -> None:
        self.statusBar().showMessage(message)

    def _on_gemini_status(self, message: str) -> None:
        self.statusBar().showMessage(message)
        lower = message.lower()
        if "connected" in lower:
            self._set_gemini_status("Connected")
        elif "disconnected" in lower:
            self._set_gemini_status("Disconnected")

    def _set_source_status(self, state: str) -> None:
        self._source_status_label.setText(f"Source: {state}")

    def _set_gemini_status(self, state: str) -> None:
        self._gemini_status_label.setText(f"Gemini: {state}")

    def _reset_session_counters(self) -> None:
        self._shot_count = 0
        self._pocketed_count = 0
        self._foul_count = 0
        self._cost_total = 0.0
        self._counted_shots.clear()
        self._session_start = None
        self._paused = False
        if self._shots_label:
            self._shots_label.setText("Shots: 0")
        if self._pocketed_label:
            self._pocketed_label.setText("Pocketed: 0")
        if self._fouls_label:
            self._fouls_label.setText("Fouls: 0")
        if self._cost_label:
            self._cost_label.setText("Cost: $0.00")
        if self._runtime_label:
            self._runtime_label.setText("Runtime: 00:00:00")
        if self._pause_button:
            self._pause_button.setText("Pause")

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self._config, self)
        dialog.exec()

    def _open_session_browser(self) -> None:
        dialog = SessionBrowserDialog(self._session_manager, self._export_manager, self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            selected_id = dialog.selected_session_id
            if selected_id:
                self._last_session_id = selected_id

    def _on_export(self) -> None:
        session_id = self._session_id or self._last_session_id
        if not session_id:
            QtWidgets.QMessageBox.warning(
                self,
                "Export",
                "Start or select a session before exporting.",
            )
            return
        dialog = ExportDialog(self._export_manager, session_id, self)
        dialog.exec()

    def _on_analyze(self) -> None:
        session_id = self._session_id or self._last_session_id
        if not session_id:
            QtWidgets.QMessageBox.warning(
                self,
                "Analyze",
                "Start or select a session before analyzing.",
            )
            return
        # Placeholder for future analysis functionality
        QtWidgets.QMessageBox.information(
            self,
            "Analyze",
            "Analysis feature coming soon. Session data has been recorded and can be exported for external analysis.",
        )

    def _start_gemini_client(self) -> None:
        api_key = self._config.api_keys.gemini
        if not api_key:
            self.statusBar().showMessage("Gemini API key missing; skipping live analysis")
            return
        if self._gemini_client:
            return
        self._set_gemini_status("Connecting")
        connection = GeminiConnection(
            api_key=api_key,
            model=self._config.gemini.model,
            system_prompt=self._config.gemini.system_prompt,
            reconnect_attempts=self._config.gemini.reconnect_attempts,
            reconnect_delay_ms=self._config.gemini.reconnect_delay_ms,
        )
        self._gemini_client = GeminiClient(connection, self)
        self._gemini_client.raw_event.connect(self._event_processor.process_raw)
        self._gemini_client.status.connect(self._on_gemini_status)
        self._gemini_client.error.connect(self._on_event_error)
        self._gemini_client.start()

    def _stop_gemini_client(self) -> None:
        if not self._gemini_client:
            return
        self._gemini_client.stop()
        self._gemini_client.wait(1000)
        self._gemini_client = None
        self._set_gemini_status("Disconnected")

    def _send_frame_to_gemini(self, frame, timestamp_ms: float) -> None:
        if not self._gemini_client or self._paused:
            return
        now = time.monotonic()
        sample_interval = self._config.gemini.frame_sample_rate_ms / 1000.0
        if now - self._last_gemini_send < sample_interval:
            return
        self._last_gemini_send = now
        quality = int(self._config.storage.frame_quality)
        ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ok:
            return
        self._gemini_client.enqueue_frame(buffer.tobytes(), timestamp_ms)

    def _on_session_start(self) -> None:
        if self._session_id is None:
            session = self._session_manager.start_session(
                None,
                self._current_source_type,
                self._current_source_path,
            )
            self._session_id = session.session_id
            self._event_processor.set_session(self._session_id)
            self._reset_session_counters()

            # Create session storage directory
            self._storage_manager.create_session_storage(
                self._session_id,
                metadata={
                    "source_type": self._current_source_type,
                    "source_path": self._current_source_path,
                    "name": session.name,
                },
            )

            # Link source video if it's a file
            if self._current_source_type == "video_file":
                self._storage_manager.link_source_video(
                    self._session_id, self._current_source_path
                )

            # Save first frame as session thumbnail
            if self._last_frame is not None:
                self._storage_manager.save_thumbnail(
                    self._session_id, self._last_frame, "session_thumb"
                )

        self._start_gemini_client()
        if self._session_start is None:
            self._session_start = time.time()
        self.statusBar().showMessage("Recording")

    # --- New Session ---
    def _on_new_session(self) -> None:
        if self._session_id:
            reply = QtWidgets.QMessageBox.question(
                self,
                "New Session",
                "A session is currently active. Stop it and start a new one?",
                QtWidgets.QMessageBox.StandardButton.Yes
                | QtWidgets.QMessageBox.StandardButton.No,
            )
            if reply != QtWidgets.QMessageBox.StandardButton.Yes:
                return
            self._on_session_stop()
        self._reset_session_counters()
        self.statusBar().showMessage("Ready for new session")

    # --- View menu handlers ---
    def _toggle_raw_json(self, checked: bool) -> None:
        self._config.ui.show_raw_json = checked
        self.statusBar().showMessage(f"Raw JSON display {'enabled' if checked else 'disabled'}")

    def _toggle_trajectory_overlay(self, checked: bool) -> None:
        self._config.ui.show_trajectory_overlay = checked
        self.statusBar().showMessage(f"Trajectory overlay {'enabled' if checked else 'disabled'}")

    def _clear_event_log(self) -> None:
        if self._event_log:
            self._event_log.clear()
            self.statusBar().showMessage("Event log cleared")

    # --- Analysis menu handlers ---
    def _show_shot_breakdown(self) -> None:
        session_id = self._session_id or self._last_session_id
        if not session_id:
            QtWidgets.QMessageBox.information(
                self,
                "Shot Breakdown",
                "No session available. Start or select a session first.",
            )
            return
        QtWidgets.QMessageBox.information(
            self,
            "Shot Breakdown",
            f"Shot breakdown analysis for session.\n\n"
            f"Total shots: {self._shot_count}\n"
            f"Balls pocketed: {self._pocketed_count}\n"
            f"Fouls: {self._foul_count}\n\n"
            f"(Detailed breakdown coming in future update)",
        )

    def _show_accuracy_stats(self) -> None:
        session_id = self._session_id or self._last_session_id
        if not session_id:
            QtWidgets.QMessageBox.information(
                self,
                "Accuracy Statistics",
                "No session available. Start or select a session first.",
            )
            return
        accuracy = 0.0
        if self._shot_count > 0:
            accuracy = (self._pocketed_count / self._shot_count) * 100
        QtWidgets.QMessageBox.information(
            self,
            "Accuracy Statistics",
            f"Session Accuracy Statistics\n\n"
            f"Pocketing accuracy: {accuracy:.1f}%\n"
            f"Shots taken: {self._shot_count}\n"
            f"Successful pockets: {self._pocketed_count}\n\n"
            f"(Advanced statistics coming in future update)",
        )

    # --- Help menu handlers ---
    def _show_about(self) -> None:
        QtWidgets.QMessageBox.about(
            self,
            "About Pool Telemetry Recorder",
            "<h3>Pool Telemetry Recorder</h3>"
            f"<p>Version {self._config.version}</p>"
            "<p>A real-time pool/billiards telemetry analysis tool using "
            "Google Gemini Live API for AI-powered shot detection and tracking.</p>"
            "<p><b>Features:</b></p>"
            "<ul>"
            "<li>Live video capture from GoPro or video files</li>"
            "<li>Real-time ball position tracking</li>"
            "<li>Shot detection and analysis</li>"
            "<li>Session recording and export</li>"
            "</ul>"
            "<p>Built with PyQt6, OpenCV, and Gemini Live API.</p>",
        )

    def _show_documentation(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "Documentation",
            "<h3>Quick Start Guide</h3>"
            "<p><b>1. Connect Video Source</b></p>"
            "<p>Click 'Connect GoPro' for live capture or 'Import Video' for recorded footage.</p>"
            "<p><b>2. Start Recording</b></p>"
            "<p>Click 'Start' or press F5 to begin a session. The Gemini API will analyze frames.</p>"
            "<p><b>3. Monitor Progress</b></p>"
            "<p>Watch the Ball Matrix for positions and Event Stream for detected events.</p>"
            "<p><b>4. Export Data</b></p>"
            "<p>Use File → Export to save session data in JSON, CSV, or JSONL format.</p>"
            "<p><b>API Key Required</b></p>"
            "<p>Set your Gemini API key in Settings → Preferences.</p>",
        )

    def _show_shortcuts(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "Keyboard Shortcuts",
            "<h3>Keyboard Shortcuts</h3>"
            "<table>"
            "<tr><td><b>Ctrl+N</b></td><td>New Session</td></tr>"
            "<tr><td><b>Ctrl+E</b></td><td>Export</td></tr>"
            "<tr><td><b>Ctrl+B</b></td><td>Session Browser</td></tr>"
            "<tr><td><b>Ctrl+,</b></td><td>Preferences</td></tr>"
            "<tr><td><b>Ctrl+Q</b></td><td>Exit</td></tr>"
            "<tr><td><b>F1</b></td><td>Documentation</td></tr>"
            "<tr><td><b>F5</b></td><td>Start Recording</td></tr>"
            "<tr><td><b>F6</b></td><td>Pause/Resume</td></tr>"
            "<tr><td><b>F7</b></td><td>Stop Recording</td></tr>"
            "</table>",
        )
