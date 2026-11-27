"""AYON styled window showing the progress of a local render.

'ExtractLocalRender' renders the whole render queue in one blocking call, so
this window is the only place the artist can see how far along it is. It is
owned by the addon because the Publisher UI comes from ayon-core.

Requires 'AYProgressBar' from ayon-core, which is available from
'ayon_core.ui.components' since core 1.10.4 (see 'package.py').
"""
from __future__ import annotations

from qtpy import QtCore, QtGui, QtWidgets

from ayon_core.style import get_app_icon_path, load_stylesheet
from ayon_core.ui.components import (
    AYContainer,
    AYLabel,
    AYProgressBar,
    AYVBoxLayout,
)


class RenderProgressWindow(QtWidgets.QDialog):
    """Progress of a local After Effects render.

    Non modal: the publish keeps running in the thread that waits for the
    render, this window must never block it.

    Args:
        comp_name (str): Name of the composition being rendered.
        parent (QtWidgets.QWidget | None): Optional parent widget.

    """

    def __init__(self, comp_name, parent=None):
        super().__init__(parent)

        self._closed = False

        self.setWindowTitle("Rendering {}".format(comp_name))
        self.setWindowIcon(QtGui.QIcon(get_app_icon_path()))
        self.setModal(False)
        # Stay above the Publisher and After Effects, otherwise the render
        # runs with the progress hidden behind another window.
        self.setWindowFlag(
            QtCore.Qt.WindowType.WindowStaysOnTopHint, True
        )
        self.setMinimumWidth(420)

        # Dialog surface, paints the AYON background under the widgets.
        surface = AYContainer(
            self,
            layout=AYContainer.Layout.VBox,
            variant=AYContainer.Variants.High_Dark,
            layout_margin=12,
            layout_spacing=8,
        )

        title_label = AYLabel(comp_name, parent=surface)
        detail_label = AYLabel("Starting render...", dim=True, parent=surface)
        detail_label.setWordWrap(True)

        progress_bar = AYProgressBar(surface, show_value=True)

        surface.add_widget(title_label, 0)
        surface.add_widget(detail_label, 0)
        surface.add_widget(progress_bar, 0)

        main_layout = AYVBoxLayout(self, margin=0, spacing=0)
        main_layout.addWidget(surface, 1)

        self._detail_label = detail_label
        self._progress_bar = progress_bar
        self._first_show = True

    def showEvent(self, event) -> None:
        """Apply the AYON stylesheet the first time the window is shown."""
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            self.setStyleSheet(load_stylesheet())

    def update_progress(self, progress) -> None:
        """Apply a 'RenderProgress' snapshot to the window.

        Args:
            progress (RenderProgress): Snapshot of the render progress.

        """
        if self._closed:
            return

        # 'maximum' must be set before 'value', 'set_value' is clamped by it.
        if progress.is_measurable:
            self._progress_bar.set_maximum(progress.total)
            self._progress_bar.set_value(progress.done)
        else:
            # A negative maximum makes the bar indeterminate, which is what a
            # render that produces a single movie file looks like. A zero
            # maximum would still render as a determinate empty bar.
            self._progress_bar.set_maximum(-1)
            self._progress_bar.set_value(0)
        self._detail_label.setText(progress.message)

    def closeEvent(self, event) -> None:
        """Ignore further updates once the artist closed the window."""
        self._closed = True
        super().closeEvent(event)


def create_progress_window(comp_name):
    """Create a progress window for a local render.

    Args:
        comp_name (str): Name of the composition being rendered.

    Returns:
        RenderProgressWindow | None: The window, or None when there is no Qt
            application to show it in (e.g. a headless environment).

    """
    if QtWidgets.QApplication.instance() is None:
        return None
    return RenderProgressWindow(comp_name)
