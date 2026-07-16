from __future__ import annotations

from pathlib import Path

from PyQt6 import QtWidgets

from ..exporter import ExportManager


class ExportDialog(QtWidgets.QDialog):
    def __init__(
        self,
        export_manager: ExportManager,
        session_id: str,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._export_manager = export_manager
        self._session_id = session_id
        self.setWindowTitle("Export Session")
        self.setModal(True)

        self._format = QtWidgets.QComboBox()
        self._format.addItems(
            [
                "Claude Analysis Package (JSON)",
                "Full Data Export (JSON)",
                "Shot Summary (CSV)",
                "Raw Event Stream (JSONL)",
            ]
        )

        self._destination = QtWidgets.QLineEdit()
        browse_button = QtWidgets.QPushButton("Browse")
        browse_button.clicked.connect(self._browse_destination)

        form = QtWidgets.QFormLayout()
        form.addRow("Export Format", self._format)
        form.addRow("Destination", self._destination)
        form.addRow("", browse_button)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
            | QtWidgets.QDialogButtonBox.StandardButton.Ok
        )
        buttons.accepted.connect(self._on_export)
        buttons.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _browse_destination(self) -> None:
        format_label = self._format.currentText()
        extension = "json"
        if "CSV" in format_label:
            extension = "csv"
        elif "JSONL" in format_label:
            extension = "jsonl"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Session",
            f"session_export.{extension}",
            f"*.{extension}",
        )
        if path:
            self._destination.setText(path)

    def _on_export(self) -> None:
        destination_text = self._destination.text().strip()
        if not destination_text:
            QtWidgets.QMessageBox.warning(self, "Export", "Choose a destination path.")
            return
        destination = Path(destination_text)
        format_label = self._format.currentText()
        try:
            if format_label.startswith("Claude"):
                self._export_manager.export_claude_json(self._session_id, destination)
            elif format_label.startswith("Full"):
                self._export_manager.export_full_json(self._session_id, destination)
            elif format_label.startswith("Shot"):
                self._export_manager.export_shots_csv(self._session_id, destination)
            else:
                self._export_manager.export_events_jsonl(self._session_id, destination)
            QtWidgets.QMessageBox.information(
                self, "Export", f"Successfully exported to:\n{destination}"
            )
            self.accept()
        except OSError as exc:
            QtWidgets.QMessageBox.critical(
                self, "Export Failed", f"Failed to write export file:\n{exc}"
            )
