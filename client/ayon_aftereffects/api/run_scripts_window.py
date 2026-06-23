from __future__ import annotations

from qtpy import QtCore, QtWidgets

from .scripts import ScriptItem, ScriptService


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

        self.setWindowTitle("Run Scripts")
        self.resize(720, 420)

        self._scripts_view = QtWidgets.QTreeWidget(self)
        self._scripts_view.setColumnCount(3)
        self._scripts_view.setHeaderLabels(["Name", "Path", "Status"])
        self._scripts_view.setRootIsDecorated(False)
        self._scripts_view.setAlternatingRowColors(True)
        self._scripts_view.setUniformRowHeights(True)
        self._scripts_view.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection
        )
        self._scripts_view.setEditTriggers(
            QtWidgets.QAbstractItemView.NoEditTriggers
        )

        header = self._scripts_view.header()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)

        self._status_label = QtWidgets.QLabel(self)
        self._refresh_btn = QtWidgets.QPushButton("Refresh", self)
        self._run_btn = QtWidgets.QPushButton("Run", self)
        self._close_btn = QtWidgets.QPushButton("Close", self)
        self._run_btn.setEnabled(False)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self._status_label, 1)
        button_layout.addWidget(self._refresh_btn)
        button_layout.addWidget(self._run_btn)
        button_layout.addWidget(self._close_btn)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._scripts_view)
        layout.addLayout(button_layout)

        self._refresh_btn.clicked.connect(self.refresh)
        self._run_btn.clicked.connect(self._on_run_clicked)
        self._close_btn.clicked.connect(self.close)
        self._scripts_view.itemSelectionChanged.connect(
            self._on_selection_changed
        )
        self._scripts_view.itemDoubleClicked.connect(
            self._on_item_double_clicked
        )

    def refresh(self) -> None:
        """Reload the manual scripts from settings."""
        self._items_by_id = {}
        self._scripts_view.clear()

        items = self._service.list_manual_items()
        if not items:
            self._status_label.setText("No manual scripts configured.")
            self._run_btn.setEnabled(False)
            return

        for item in items:
            self._items_by_id[item.script_id] = item
            status = "Ready" if item.exists else item.error or "Unavailable"
            tree_item = QtWidgets.QTreeWidgetItem(
                [item.name, item.path, status]
            )
            tree_item.setData(0, QtCore.Qt.UserRole, item.script_id)
            tree_item.setToolTip(1, item.path)
            tree_item.setToolTip(2, status)
            self._scripts_view.addTopLevelItem(tree_item)

        self._scripts_view.setCurrentItem(self._scripts_view.topLevelItem(0))
        self._status_label.setText("Select a script to run.")
        self._on_selection_changed()

    def _on_selection_changed(self) -> None:
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
        item = self._get_selected_item()
        if item is None:
            return

        result = self._service.run_item(item)
        self._status_label.setText(result.message)

    def _get_selected_item(self) -> ScriptItem | None:
        """Return the currently selected script item."""
        selected_items = self._scripts_view.selectedItems()
        if not selected_items:
            return None

        script_id = selected_items[0].data(0, QtCore.Qt.UserRole)
        return self._items_by_id.get(script_id)
