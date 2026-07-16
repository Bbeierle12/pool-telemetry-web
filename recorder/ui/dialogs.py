from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import cv2
from PyQt6 import QtCore, QtWidgets

if TYPE_CHECKING:
    from ..config import GoProConfig

logger = logging.getLogger(__name__)


def enumerate_cameras(max_index: int = 10) -> list[tuple[int, str]]:
    """Enumerate available camera devices.

    Args:
        max_index: Maximum device index to check.

    Returns:
        List of (index, description) tuples for available cameras.
    """
    cameras: list[tuple[int, str]] = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            # Try to get backend name
            backend = cap.getBackendName()
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            desc = f"Camera {i} ({backend}, {width}x{height})"
            cameras.append((i, desc))
            cap.release()
    return cameras


def test_video_source(source: int | str, timeout_ms: int = 3000) -> tuple[bool, str]:
    """Test if a video source can be opened and read.

    Args:
        source: Device index or URL/path.
        timeout_ms: Timeout for connection test.

    Returns:
        Tuple of (success, message).
    """
    try:
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            return False, "Failed to open video source"

        # Try to read a frame with timeout
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        ret, _ = cap.read()
        cap.release()

        if not ret:
            return False, "Connected but failed to read frame"
        return True, "Connection successful"
    except Exception as e:
        return False, f"Error: {e}"


class GoProConnectDialog(QtWidgets.QDialog):
    """Dialog for connecting to a GoPro camera."""

    def __init__(
        self,
        gopro_config: GoProConfig | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._gopro_config = gopro_config
        self.setWindowTitle("Connect GoPro")
        self.setModal(True)
        self.setMinimumWidth(400)

        # Connection mode selection
        self._mode_group = QtWidgets.QButtonGroup(self)
        self._usb_radio = QtWidgets.QRadioButton("USB Webcam Mode")
        self._wifi_radio = QtWidgets.QRadioButton("WiFi Streaming")
        self._mode_group.addButton(self._usb_radio, 0)
        self._mode_group.addButton(self._wifi_radio, 1)

        mode_layout = QtWidgets.QHBoxLayout()
        mode_layout.addWidget(self._usb_radio)
        mode_layout.addWidget(self._wifi_radio)

        mode_group_box = QtWidgets.QGroupBox("Connection Mode")
        mode_group_box.setLayout(mode_layout)

        # USB Webcam settings
        self._device_combo = QtWidgets.QComboBox()
        self._refresh_button = QtWidgets.QPushButton("Refresh")
        self._refresh_button.clicked.connect(self._refresh_cameras)

        device_layout = QtWidgets.QHBoxLayout()
        device_layout.addWidget(self._device_combo, 1)
        device_layout.addWidget(self._refresh_button)

        self._usb_widget = QtWidgets.QWidget()
        usb_form = QtWidgets.QFormLayout(self._usb_widget)
        usb_form.setContentsMargins(0, 0, 0, 0)
        usb_form.addRow("Camera", device_layout)

        # WiFi settings
        self._wifi_ip = QtWidgets.QLineEdit()
        self._wifi_ip.setPlaceholderText("e.g., 10.5.5.9 or 172.2x.1xx.51")
        self._wifi_port = QtWidgets.QSpinBox()
        self._wifi_port.setRange(1, 65535)
        self._wifi_port.setValue(8080)
        self._wifi_protocol = QtWidgets.QComboBox()
        self._wifi_protocol.addItems(["UDP Stream", "HTTP Preview", "RTSP (if available)"])

        self._wifi_widget = QtWidgets.QWidget()
        wifi_form = QtWidgets.QFormLayout(self._wifi_widget)
        wifi_form.setContentsMargins(0, 0, 0, 0)
        wifi_form.addRow("GoPro IP", self._wifi_ip)
        wifi_form.addRow("Port", self._wifi_port)
        wifi_form.addRow("Protocol", self._wifi_protocol)

        # Video settings (common)
        self._resolution = QtWidgets.QComboBox()
        self._resolution.addItems(["1080p", "720p", "4K", "2.7K"])
        self._resolution.setEditable(True)
        self._resolution.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)

        self._framerate = QtWidgets.QComboBox()
        self._framerate.addItems(["24", "30", "60", "120", "240"])

        self._stabilization = QtWidgets.QCheckBox("Enable Stabilization")

        video_form = QtWidgets.QFormLayout()
        video_form.addRow("Resolution", self._resolution)
        video_form.addRow("Framerate", self._framerate)
        video_form.addRow("", self._stabilization)

        video_group_box = QtWidgets.QGroupBox("Video Settings")
        video_group_box.setLayout(video_form)

        # Connection test
        self._test_button = QtWidgets.QPushButton("Test Connection")
        self._test_button.clicked.connect(self._test_connection)
        self._status_label = QtWidgets.QLabel("")
        self._status_label.setWordWrap(True)

        test_layout = QtWidgets.QHBoxLayout()
        test_layout.addWidget(self._test_button)
        test_layout.addWidget(self._status_label, 1)

        # Dialog buttons
        self._button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
            | QtWidgets.QDialogButtonBox.StandardButton.Ok
        )
        self._button_box.accepted.connect(self._on_accept)
        self._button_box.rejected.connect(self.reject)

        # Main layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(mode_group_box)
        layout.addWidget(self._usb_widget)
        layout.addWidget(self._wifi_widget)
        layout.addWidget(video_group_box)
        layout.addLayout(test_layout)
        layout.addWidget(self._button_box)

        # Connect mode switching
        self._usb_radio.toggled.connect(self._on_mode_changed)
        self._wifi_radio.toggled.connect(self._on_mode_changed)

        # Initialize from config
        self._apply_config_defaults()
        self._refresh_cameras()
        self._on_mode_changed()

    def _apply_config_defaults(self) -> None:
        """Apply defaults from GoProConfig."""
        if not self._gopro_config:
            self._usb_radio.setChecked(True)
            return

        # Connection mode
        if self._gopro_config.connection_mode == "wifi":
            self._wifi_radio.setChecked(True)
            if self._gopro_config.wifi_ip:
                self._wifi_ip.setText(self._gopro_config.wifi_ip)
        else:
            self._usb_radio.setChecked(True)

        # Resolution
        res = self._gopro_config.resolution
        idx = self._resolution.findText(res, QtCore.Qt.MatchFlag.MatchFixedString)
        if idx >= 0:
            self._resolution.setCurrentIndex(idx)
        else:
            self._resolution.setCurrentText(res)

        # Framerate
        fps = str(self._gopro_config.framerate)
        idx = self._framerate.findText(fps)
        if idx >= 0:
            self._framerate.setCurrentIndex(idx)

        # Stabilization
        self._stabilization.setChecked(self._gopro_config.stabilization)

    def _refresh_cameras(self) -> None:
        """Refresh the list of available cameras."""
        self._device_combo.clear()
        self._status_label.setText("Scanning for cameras...")
        self._status_label.setStyleSheet("")
        QtWidgets.QApplication.processEvents()

        cameras = enumerate_cameras()
        if cameras:
            for idx, desc in cameras:
                self._device_combo.addItem(desc, idx)
            self._status_label.setText(f"Found {len(cameras)} camera(s)")
            self._status_label.setStyleSheet("color: green;")
        else:
            self._device_combo.addItem("No cameras found", -1)
            self._status_label.setText("No cameras detected")
            self._status_label.setStyleSheet("color: orange;")

    def _on_mode_changed(self) -> None:
        """Handle connection mode changes."""
        is_usb = self._usb_radio.isChecked()
        self._usb_widget.setVisible(is_usb)
        self._wifi_widget.setVisible(not is_usb)
        self._status_label.setText("")

    def _get_video_source(self) -> int | str | None:
        """Get the video source based on current settings."""
        if self._usb_radio.isChecked():
            idx = self._device_combo.currentData()
            if idx is None or idx < 0:
                return None
            return idx
        else:
            ip = self._wifi_ip.text().strip()
            if not ip:
                return None
            port = self._wifi_port.value()
            protocol = self._wifi_protocol.currentIndex()

            if protocol == 0:  # UDP Stream
                return f"udp://{ip}:{port}"
            elif protocol == 1:  # HTTP Preview
                return f"http://{ip}:{port}/live/amba.m3u8"
            else:  # RTSP
                return f"rtsp://{ip}:{port}/live"

    def _test_connection(self) -> None:
        """Test the current connection settings."""
        source = self._get_video_source()
        if source is None:
            self._status_label.setText("Please select a valid source")
            self._status_label.setStyleSheet("color: orange;")
            return

        self._status_label.setText("Testing connection...")
        self._status_label.setStyleSheet("")
        self._test_button.setEnabled(False)
        QtWidgets.QApplication.processEvents()

        success, message = test_video_source(source)

        self._test_button.setEnabled(True)
        self._status_label.setText(message)
        if success:
            self._status_label.setStyleSheet("color: green;")
        else:
            self._status_label.setStyleSheet("color: red;")

    def _on_accept(self) -> None:
        """Validate and accept the dialog."""
        source = self._get_video_source()
        if source is None:
            QtWidgets.QMessageBox.warning(
                self,
                "Invalid Source",
                "Please select a valid camera or enter a WiFi IP address.",
            )
            return
        self.accept()

    def values(self) -> tuple[int | str, str, float, bool]:
        """Get the selected connection values.

        Returns:
            Tuple of (source, resolution, framerate, stabilization).
        """
        source = self._get_video_source()
        if source is None:
            source = 0  # Fallback
        return (
            source,
            self._resolution.currentText(),
            float(self._framerate.currentText()),
            self._stabilization.isChecked(),
        )

    def connection_mode(self) -> str:
        """Get the selected connection mode."""
        return "wifi" if self._wifi_radio.isChecked() else "usb_webcam"

    def wifi_ip(self) -> str | None:
        """Get the WiFi IP if in WiFi mode."""
        if self._wifi_radio.isChecked():
            ip = self._wifi_ip.text().strip()
            return ip if ip else None
        return None
