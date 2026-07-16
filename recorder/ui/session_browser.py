from __future__ import annotations

from datetime import datetime

from PyQt6 import QtCore, QtWidgets

from ..exporter import ExportManager
from ..sessions import SessionManager
from .export_dialog import ExportDialog


class SessionBrowserDialog(QtWidgets.QDialog):
    def __init__(
        self,
        session_manager: SessionManager,
        export_manager: ExportManager,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._session_manager = session_manager
        self._export_manager = export_manager
        self._selected_session_id: str | None = None
        self.setWindowTitle("Session Browser")
        self.setModal(True)

        self._table = QtWidgets.QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["Date", "Name", "Shots", "Pocketed", "Duration", "Status"]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)

        self._refresh_table()

        button_row = QtWidgets.QHBoxLayout()
        self._open_button = QtWidgets.QPushButton("Open")
        self._export_button = QtWidgets.QPushButton("Export")
        self._delete_button = QtWidgets.QPushButton("Delete")
        close_button = QtWidgets.QPushButton("Close")
        close_button.clicked.connect(self.reject)
        self._open_button.clicked.connect(self._on_open)
        self._export_button.clicked.connect(self._on_export)
        self._delete_button.clicked.connect(self._on_delete)
        button_row.addWidget(self._open_button)
        button_row.addWidget(self._export_button)
        button_row.addWidget(self._delete_button)
        button_row.addStretch(1)
        button_row.addWidget(close_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._table)
        layout.addLayout(button_row)

        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._set_action_state(False)

    @property
    def selected_session_id(self) -> str | None:
        return self._selected_session_id

    def _refresh_table(self) -> None:
        sessions = self._session_manager.list_sessions()
        self._table.setRowCount(len(sessions))
        for row, session in enumerate(sessions):
            created_at = session.get("created_at")
            if created_at:
                try:
                    created_at = datetime.fromisoformat(created_at).strftime("%Y-%m-%d %H:%M")
                except ValueError:
                    pass
            duration_text = "--"
            started_at = session.get("started_at")
            ended_at = session.get("ended_at")
            if started_at and ended_at:
                try:
                    start = datetime.fromisoformat(started_at)
                    end = datetime.fromisoformat(ended_at)
                    delta = end - start
                    seconds = int(delta.total_seconds())
                    duration_text = f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"
                except ValueError:
                    duration_text = "--"
            values = [
                created_at or "--",
                session.get("name") or "--",
                str(session.get("total_shots") or 0),
                str(session.get("total_pocketed") or 0),
                duration_text,
                session.get("status") or "--",
            ]
            for col, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                if col == 0:
                    item.setData(QtCore.Qt.ItemDataRole.UserRole, session.get("id"))
                self._table.setItem(row, col, item)
            self._table.setRowHeight(row, 22)
            self._table.setRowHidden(row, False)

    def _on_selection_changed(self) -> None:
        items = self._table.selectedItems()
        if not items:
            self._selected_session_id = None
            self._set_action_state(False)
            return
        row = items[0].row()
        table_item = self._table.item(row, 0)
        if table_item:
            self._selected_session_id = table_item.data(QtCore.Qt.ItemDataRole.UserRole)
        else:
            self._selected_session_id = None
        self._set_action_state(self._selected_session_id is not None)

    def _set_action_state(self, enabled: bool) -> None:
        self._open_button.setEnabled(enabled)
        self._export_button.setEnabled(enabled)
        self._delete_button.setEnabled(enabled)

    def _on_open(self) -> None:
        if not self._selected_session_id:
            return
        self.accept()

    def _on_export(self) -> None:
        if not self._selected_session_id:
            return
        dialog = ExportDialog(self._export_manager, self._selected_session_id, self)
        dialog.exec()

    def _on_delete(self) -> None:
        if not self._selected_session_id:
            return
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Delete Session",
            "Delete the selected session and all associated data?",
        )
        if confirm != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self._session_manager.delete_session(self._selected_session_id)
        self._selected_session_id = None
        self._refresh_table()
        self._set_action_state(False)
