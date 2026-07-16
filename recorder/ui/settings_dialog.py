from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from ..config import AppConfig, save_config


class SettingsDialog(QtWidgets.QDialog):
    """Application settings dialog with tabbed interface."""

    def __init__(self, config: AppConfig, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setMinimumWidth(450)

        # Create tab widget
        self._tabs = QtWidgets.QTabWidget()
        self._tabs.addTab(self._create_api_tab(), "API Keys")
        self._tabs.addTab(self._create_gopro_tab(), "GoPro")
        self._tabs.addTab(self._create_storage_tab(), "Storage")
        self._tabs.addTab(self._create_cost_tab(), "Cost Tracking")

        # Dialog buttons
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
            | QtWidgets.QDialogButtonBox.StandardButton.Apply
            | QtWidgets.QDialogButtonBox.StandardButton.Ok
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Apply).clicked.connect(
            self._on_apply
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._tabs)
        layout.addWidget(buttons)

    def _create_api_tab(self) -> QtWidgets.QWidget:
        """Create the API Keys settings tab."""
        widget = QtWidgets.QWidget()

        self._gemini_key = QtWidgets.QLineEdit()
        self._gemini_key.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self._gemini_key.setText(self._config.api_keys.gemini or "")
        self._gemini_key.setPlaceholderText("Enter Gemini API key")

        self._anthropic_key = QtWidgets.QLineEdit()
        self._anthropic_key.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self._anthropic_key.setText(self._config.api_keys.anthropic or "")
        self._anthropic_key.setPlaceholderText("Enter Anthropic API key (optional)")

        # Show/hide toggles
        gemini_show = QtWidgets.QCheckBox("Show")
        gemini_show.toggled.connect(
            lambda checked: self._gemini_key.setEchoMode(
                QtWidgets.QLineEdit.EchoMode.Normal if checked else QtWidgets.QLineEdit.EchoMode.Password
            )
        )
        anthropic_show = QtWidgets.QCheckBox("Show")
        anthropic_show.toggled.connect(
            lambda checked: self._anthropic_key.setEchoMode(
                QtWidgets.QLineEdit.EchoMode.Normal if checked else QtWidgets.QLineEdit.EchoMode.Password
            )
        )

        gemini_layout = QtWidgets.QHBoxLayout()
        gemini_layout.addWidget(self._gemini_key)
        gemini_layout.addWidget(gemini_show)

        anthropic_layout = QtWidgets.QHBoxLayout()
        anthropic_layout.addWidget(self._anthropic_key)
        anthropic_layout.addWidget(anthropic_show)

        info_label = QtWidgets.QLabel(
            "<i>API keys can also be set via environment variables:<br>"
            "GEMINI_API_KEY, ANTHROPIC_API_KEY</i>"
        )
        info_label.setWordWrap(True)

        form = QtWidgets.QFormLayout(widget)
        form.addRow("Gemini API Key", gemini_layout)
        form.addRow("Anthropic API Key", anthropic_layout)
        form.addRow("", info_label)

        return widget

    def _create_gopro_tab(self) -> QtWidgets.QWidget:
        """Create the GoPro settings tab."""
        widget = QtWidgets.QWidget()

        # Connection mode
        self._gopro_mode = QtWidgets.QComboBox()
        self._gopro_mode.addItems(["USB Webcam", "WiFi"])
        if self._config.gopro.connection_mode == "wifi":
            self._gopro_mode.setCurrentIndex(1)
        else:
            self._gopro_mode.setCurrentIndex(0)

        # WiFi IP
        self._gopro_wifi_ip = QtWidgets.QLineEdit()
        self._gopro_wifi_ip.setText(self._config.gopro.wifi_ip or "")
        self._gopro_wifi_ip.setPlaceholderText("e.g., 10.5.5.9")

        # Resolution
        self._gopro_resolution = QtWidgets.QComboBox()
        self._gopro_resolution.addItems(["1080p", "720p", "4K", "2.7K"])
        self._gopro_resolution.setEditable(True)
        res = self._config.gopro.resolution
        idx = self._gopro_resolution.findText(res, QtCore.Qt.MatchFlag.MatchFixedString)
        if idx >= 0:
            self._gopro_resolution.setCurrentIndex(idx)
        else:
            self._gopro_resolution.setCurrentText(res)

        # Framerate
        self._gopro_framerate = QtWidgets.QComboBox()
        self._gopro_framerate.addItems(["24", "30", "60", "120", "240"])
        fps = str(self._config.gopro.framerate)
        idx = self._gopro_framerate.findText(fps)
        if idx >= 0:
            self._gopro_framerate.setCurrentIndex(idx)

        # Stabilization
        self._gopro_stabilization = QtWidgets.QCheckBox("Enable HyperSmooth Stabilization")
        self._gopro_stabilization.setChecked(self._config.gopro.stabilization)

        # Enable/disable WiFi IP based on mode
        self._gopro_mode.currentIndexChanged.connect(self._on_gopro_mode_changed)
        self._on_gopro_mode_changed()

        form = QtWidgets.QFormLayout(widget)
        form.addRow("Default Connection", self._gopro_mode)
        form.addRow("WiFi IP Address", self._gopro_wifi_ip)
        form.addRow("Default Resolution", self._gopro_resolution)
        form.addRow("Default Framerate", self._gopro_framerate)
        form.addRow("", self._gopro_stabilization)

        # Info section
        info_group = QtWidgets.QGroupBox("GoPro Setup Tips")
        info_layout = QtWidgets.QVBoxLayout(info_group)
        info_label = QtWidgets.QLabel(
            "<b>USB Webcam Mode:</b><br>"
            "1. Connect GoPro via USB-C<br>"
            "2. Set GoPro to 'USB Connection' → 'GoPro Connect'<br>"
            "3. Camera appears as standard webcam<br><br>"
            "<b>WiFi Mode:</b><br>"
            "1. Enable WiFi on GoPro<br>"
            "2. Connect computer to GoPro's WiFi network<br>"
            "3. Default IP is usually 10.5.5.9<br>"
        )
        info_label.setWordWrap(True)
        info_layout.addWidget(info_label)

        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addLayout(form)
        main_layout.addWidget(info_group)
        main_layout.addStretch()
        widget.setLayout(main_layout)

        return widget

    def _on_gopro_mode_changed(self) -> None:
        """Enable/disable WiFi IP field based on connection mode."""
        is_wifi = self._gopro_mode.currentIndex() == 1
        self._gopro_wifi_ip.setEnabled(is_wifi)

    def _create_storage_tab(self) -> QtWidgets.QWidget:
        """Create the Storage settings tab."""
        widget = QtWidgets.QWidget()

        self._data_dir = QtWidgets.QLineEdit()
        self._data_dir.setText(self._config.storage.data_directory)

        browse_button = QtWidgets.QPushButton("Browse...")
        browse_button.clicked.connect(self._browse_data_dir)

        dir_layout = QtWidgets.QHBoxLayout()
        dir_layout.addWidget(self._data_dir)
        dir_layout.addWidget(browse_button)

        self._save_key_frames = QtWidgets.QCheckBox("Save key frames as images")
        self._save_key_frames.setChecked(self._config.storage.save_key_frames)

        self._save_raw_events = QtWidgets.QCheckBox("Save raw Gemini events")
        self._save_raw_events.setChecked(self._config.storage.save_raw_events)

        self._frame_quality = QtWidgets.QSpinBox()
        self._frame_quality.setRange(1, 100)
        self._frame_quality.setValue(self._config.storage.frame_quality)
        self._frame_quality.setSuffix("%")

        self._max_storage = QtWidgets.QSpinBox()
        self._max_storage.setRange(1, 1000)
        self._max_storage.setValue(self._config.storage.max_storage_gb)
        self._max_storage.setSuffix(" GB")

        self._auto_cleanup = QtWidgets.QSpinBox()
        self._auto_cleanup.setRange(0, 365)
        self._auto_cleanup.setValue(self._config.storage.auto_cleanup_days)
        self._auto_cleanup.setSuffix(" days")
        self._auto_cleanup.setSpecialValueText("Never")

        form = QtWidgets.QFormLayout(widget)
        form.addRow("Data Directory", dir_layout)
        form.addRow("", self._save_key_frames)
        form.addRow("", self._save_raw_events)
        form.addRow("Frame Quality", self._frame_quality)
        form.addRow("Max Storage", self._max_storage)
        form.addRow("Auto Cleanup", self._auto_cleanup)

        return widget

    def _create_cost_tab(self) -> QtWidgets.QWidget:
        """Create the Cost Tracking settings tab."""
        widget = QtWidgets.QWidget()

        self._cost_enabled = QtWidgets.QCheckBox("Enable cost tracking")
        self._cost_enabled.setChecked(self._config.cost_tracking.enabled)

        self._warn_threshold = QtWidgets.QDoubleSpinBox()
        self._warn_threshold.setRange(0, 1000)
        self._warn_threshold.setDecimals(2)
        self._warn_threshold.setPrefix("$")
        self._warn_threshold.setValue(self._config.cost_tracking.warn_threshold_usd)

        self._stop_threshold = QtWidgets.QDoubleSpinBox()
        self._stop_threshold.setRange(0, 1000)
        self._stop_threshold.setDecimals(2)
        self._stop_threshold.setPrefix("$")
        self._stop_threshold.setValue(self._config.cost_tracking.stop_threshold_usd or 0.0)
        self._stop_threshold.setSpecialValueText("No limit")

        # Enable/disable thresholds based on tracking enabled
        self._cost_enabled.toggled.connect(self._on_cost_enabled_changed)
        self._on_cost_enabled_changed()

        form = QtWidgets.QFormLayout(widget)
        form.addRow("", self._cost_enabled)
        form.addRow("Warning Threshold", self._warn_threshold)
        form.addRow("Stop Threshold", self._stop_threshold)

        info_label = QtWidgets.QLabel(
            "<i>Warning threshold shows a notification.<br>"
            "Stop threshold automatically ends the session.</i>"
        )
        info_label.setWordWrap(True)
        form.addRow("", info_label)

        return widget

    def _on_cost_enabled_changed(self) -> None:
        """Enable/disable threshold fields based on cost tracking enabled."""
        enabled = self._cost_enabled.isChecked()
        self._warn_threshold.setEnabled(enabled)
        self._stop_threshold.setEnabled(enabled)

    def _browse_data_dir(self) -> None:
        """Open directory browser for data directory."""
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select Data Directory",
            self._data_dir.text(),
        )
        if path:
            self._data_dir.setText(path)

    def _apply_config(self) -> None:
        """Apply current settings to config and save."""
        # API Keys
        self._config.api_keys.gemini = self._gemini_key.text().strip() or None
        self._config.api_keys.anthropic = self._anthropic_key.text().strip() or None

        # GoPro
        self._config.gopro.connection_mode = "wifi" if self._gopro_mode.currentIndex() == 1 else "usb_webcam"
        self._config.gopro.wifi_ip = self._gopro_wifi_ip.text().strip() or None
        self._config.gopro.resolution = self._gopro_resolution.currentText()
        self._config.gopro.framerate = int(self._gopro_framerate.currentText())
        self._config.gopro.stabilization = self._gopro_stabilization.isChecked()

        # Storage
        self._config.storage.data_directory = self._data_dir.text().strip()
        self._config.storage.save_key_frames = self._save_key_frames.isChecked()
        self._config.storage.save_raw_events = self._save_raw_events.isChecked()
        self._config.storage.frame_quality = self._frame_quality.value()
        self._config.storage.max_storage_gb = self._max_storage.value()
        self._config.storage.auto_cleanup_days = self._auto_cleanup.value()

        # Cost tracking
        self._config.cost_tracking.enabled = self._cost_enabled.isChecked()
        self._config.cost_tracking.warn_threshold_usd = float(self._warn_threshold.value())
        stop_value = float(self._stop_threshold.value())
        self._config.cost_tracking.stop_threshold_usd = stop_value if stop_value > 0 else None

        save_config(self._config)

    def _on_apply(self) -> None:
        """Handle Apply button click."""
        self._apply_config()

    def _on_accept(self) -> None:
        """Handle OK button click."""
        self._apply_config()
        self.accept()
