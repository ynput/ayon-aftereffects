from __future__ import annotations

import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor

from qtpy import QtCore, QtGui, QtWidgets

from ayon_core.style import get_app_icon_path, load_stylesheet
from ayon_core.tools.utils import get_qt_icon
from ayon_core.ui.components import (
    AYButton,
    AYContainer,
    AYHBoxLayout,
    AYLabel,
    AYTreeView,
    AYVBoxLayout,
)
from ayon_core.ui.style_types import get_ayon_style_data

from .scripts import ScriptItem, ScriptRunResult, ScriptService

log = logging.getLogger(__name__)

# How long to keep waiting on After Effects before releasing the dialog.
# The call cannot be cancelled, so this bounds the wait, not the work.
RUN_TIMEOUT_SECONDS = 300.0
POLL_INTERVAL_MS = 100

SCRIPT_ID_ROLE = QtCore.Qt.ItemDataRole.UserRole + 1

_NAME_COLUMN = 0
_PATH_COLUMN = 1
_STATUS_COLUMN = 2
_HEADER_LABELS = ("Name", "Path", "Status")


def _status_icons() -> tuple[QtGui.QIcon, QtGui.QIcon]:
    """Return the (ready, unavailable) status icons.

    Colors come from the AYON style tokens so they follow the theme.

    Returns:
        Icons for a runnable script and for one that can't run.
    """
    style_data = get_ayon_style_data("AYProgressBar", "default")
    ready_icon = get_qt_icon(
        {
            "type": "material-symbols",
            "name": "check_circle",
            "color": style_data.get("success-color", "#23e0a9"),
        }
    )
    error_icon = get_qt_icon(
        {
            "type": "material-symbols",
            "name": "error",
            "color": style_data.get("failed-color", "#ffb4ab"),
        }
    )
    return ready_icon, error_icon


class RunScriptsWindow(QtWidgets.QDialog):
    """Dialog for manually running configured After Effects scripts."""

    def __init__(
        self,
        service: ScriptService,
        parent: QtWidgets.QWidget | None = None,
    ):
        super().__init__(parent)

        self._service = service
        self._items_by_id: dict[str, ScriptItem] = {}

        # the dialog is cached and reused by AEHostToolsHelper, so the
        # executor outlives a close and must not be shut down there
        self._executor: ThreadPoolExecutor | None = None
        self._future: Future | None = None
        self._run_started_at = 0.0

        self.setWindowTitle("Run Scripts")
        self.setWindowIcon(QtGui.QIcon(get_app_icon_path()))
        self.setMinimumSize(480, 280)
        self.resize(720, 420)

        # Dialog surface, paints the AYON background under the widgets.
        surface = AYContainer(
            self,
            layout=AYContainer.Layout.VBox,
            variant=AYContainer.Variants.High_Dark,
            layout_margin=12,
            layout_spacing=8,
        )

        scripts_model = QtGui.QStandardItemModel(0, len(_HEADER_LABELS))
        scripts_model.setHorizontalHeaderLabels(_HEADER_LABELS)

        scripts_view = AYTreeView(surface)
        scripts_view.setModel(scripts_model)
        scripts_view.setHeaderHidden(False)
        scripts_view.setRootIsDecorated(False)
        scripts_view.setIndentation(0)
        scripts_view.setUniformRowHeights(True)
        scripts_view.setSelectionMode(AYTreeView.SelectionMode.SingleSelection)
        scripts_view.setEditTriggers(AYTreeView.EditTrigger.NoEditTriggers)

        # The AYON delegate reports no text width, so ResizeToContents
        # would collapse columns. Use fixed starting widths instead.
        header = scripts_view.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(
            _PATH_COLUMN, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        scripts_view.setColumnWidth(_NAME_COLUMN, 180)
        scripts_view.setColumnWidth(_STATUS_COLUMN, 240)

        status_label = AYLabel("", dim=True, parent=surface)
        status_label.setWordWrap(True)

        refresh_btn = AYButton(
            "Refresh",
            variant=AYButton.Variants.Surface,
            icon="refresh",
            tooltip="Reload scripts from project settings",
            parent=surface,
        )
        close_btn = AYButton(
            "Close", variant=AYButton.Variants.Surface, parent=surface
        )
        run_btn = AYButton(
            "Run",
            variant=AYButton.Variants.Filled,
            icon="play_arrow",
            tooltip="Run the selected script in After Effects",
            parent=surface,
        )
        run_btn.setEnabled(False)

        buttons_layout = AYHBoxLayout(margin=0, spacing=4)
        buttons_layout.addWidget(refresh_btn, 0)
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(close_btn, 0)
        buttons_layout.addWidget(run_btn, 0)

        surface.add_widget(scripts_view, stretch=1)
        surface.add_widget(status_label, stretch=0)
        surface.add_layout(buttons_layout, 0)

        main_layout = AYVBoxLayout(self, margin=0, spacing=0)
        main_layout.addWidget(surface, 1)

        poll_timer = QtCore.QTimer(self)
        poll_timer.setInterval(POLL_INTERVAL_MS)

        refresh_btn.clicked.connect(self.refresh)
        run_btn.clicked.connect(self._on_run_clicked)
        close_btn.clicked.connect(self.close)
        scripts_view.selection_changed.connect(self._on_selection_changed)
        scripts_view.double_clicked.connect(self._on_item_double_clicked)
        poll_timer.timeout.connect(self._on_poll_run)

        self._scripts_model = scripts_model
        self._scripts_view = scripts_view
        self._status_label = status_label
        self._refresh_btn = refresh_btn
        self._close_btn = close_btn
        self._run_btn = run_btn
        self._poll_timer = poll_timer

        # Icons need a QApplication, so they are created on first refresh.
        self._ready_icon: QtGui.QIcon | None = None
        self._error_icon: QtGui.QIcon | None = None
        self._first_show = True

    def showEvent(self, event) -> None:
        """Apply the AYON stylesheet the first time the dialog is shown.

        The AYON widgets paint themselves, the stylesheet covers the rest,
        e.g. tooltips. The dialog is cached, so this only runs once.
        """
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            self.setStyleSheet(load_stylesheet())

    def refresh(self) -> None:
        """Reload the manual scripts from settings."""
        self._items_by_id = {}
        self._scripts_model.removeRows(0, self._scripts_model.rowCount())

        items = self._service.list_manual_items()
        if not items:
            self._status_label.setText("No manual scripts configured.")
            self._run_btn.setEnabled(False)
            return

        if self._ready_icon is None or self._error_icon is None:
            self._ready_icon, self._error_icon = _status_icons()

        for item in items:
            self._items_by_id[item.script_id] = item
            if item.exists:
                status = "Ready"
                status_icon = self._ready_icon
            else:
                status = item.error or "Unavailable"
                status_icon = self._error_icon

            name_item = QtGui.QStandardItem(item.name)
            name_item.setData(item.script_id, SCRIPT_ID_ROLE)
            name_item.setToolTip(item.name)

            path_item = QtGui.QStandardItem(item.path)
            path_item.setToolTip(item.path)

            status_item = QtGui.QStandardItem(status)
            status_item.setIcon(status_icon)
            status_item.setToolTip(status)

            row = [name_item, path_item, status_item]
            for column_item in row:
                column_item.setEditable(False)
            self._scripts_model.appendRow(row)

        self._scripts_view.setCurrentIndex(self._scripts_model.index(0, 0))
        self._status_label.setText("Select a script to run.")
        self._on_selection_changed()

    def _on_selection_changed(self, *_args) -> None:
        """Update UI state from the current selection."""
        item = self._get_selected_item()
        can_run = bool(item and item.exists)
        self._run_btn.setEnabled(can_run)

        if item is None:
            self._status_label.setText("Select a script to run.")
            return

        if item.exists:
            self._status_label.setText(f"Ready to run: {item.name}")
            return

        self._status_label.setText(
            item.error or "Selected script is unavailable."
        )

    def _on_item_double_clicked(self, *_args) -> None:
        """Run the selected script on double click when possible."""
        if self._run_btn.isEnabled():
            self._on_run_clicked()

    def _on_run_clicked(self) -> None:
        """Run the currently selected manual script."""
        if self._future is not None:
            return

        item = self._get_selected_item()
        if item is None:
            return

        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="ayon-ae-run-scripts"
            )

        self._set_running(True, f"Running {item.name}...")
        self._run_started_at = time.monotonic()
        self._future = self._executor.submit(self._service.run_item, item)
        self._poll_timer.start()

    def _on_poll_run(self) -> None:
        """Check on the running script without blocking the event loop."""
        future = self._future
        if future is None:
            self._poll_timer.stop()
            return

        if future.done():
            self._stop_waiting()
            self._status_label.setText(self._result_message(future))
            return

        if time.monotonic() - self._run_started_at < RUN_TIMEOUT_SECONDS:
            return

        # a blocked websocket call cannot be cancelled, so let it finish in
        # the background rather than hold the dialog hostage
        self._stop_waiting()
        self._status_label.setText(
            f"After Effects did not respond within "
            f"{int(RUN_TIMEOUT_SECONDS)}s. The script may still be running."
        )

    def _stop_waiting(self) -> None:
        """Stop polling and hand the dialog back to the artist."""
        self._poll_timer.stop()
        self._future = None
        self._set_running(False)

    @staticmethod
    def _result_message(future: Future) -> str:
        """Status message for a finished run."""
        try:
            result: ScriptRunResult = future.result()
        except Exception:
            log.warning("Script run failed", exc_info=True)
            return "Script run failed unexpectedly, see the log for details."

        return result.message

    def closeEvent(self, event) -> None:
        """Never block on a running script when the dialog is closed."""
        self._poll_timer.stop()
        self._future = None
        super().closeEvent(event)

    def _set_running(self, running: bool, message: str = "") -> None:
        """Disable input while a script runs."""
        self._run_btn.setEnabled(not running)
        self._refresh_btn.setEnabled(not running)
        self._scripts_view.setEnabled(not running)

        if running:
            self._status_label.setText(message)
            return

        self._on_selection_changed()

    def _get_selected_item(self) -> ScriptItem | None:
        """Return the currently selected script item."""
        selection_model = self._scripts_view.selectionModel()
        selected_rows = selection_model.selectedRows(_NAME_COLUMN)
        if not selected_rows:
            return None

        script_id = selected_rows[0].data(SCRIPT_ID_ROLE)
        return self._items_by_id.get(script_id)
