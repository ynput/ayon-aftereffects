from ayon_core.tools.utils.host_tools import HostToolsHelper
from ayon_core.tools.utils.lib import qt_app_context

from .run_scripts_window import RunScriptsWindow
from .scripts import get_script_service


class AEHostToolsHelper(HostToolsHelper):
    """After Effects host tools wrapper with addon-local tools."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._run_scripts_tool = None

    def get_run_scripts_tool(self, parent=None):
        """Create, cache, and return the run scripts dialog.

        Args:
            parent: Optional parent widget.

        Returns:
            Cached run scripts dialog.
        """
        if self._run_scripts_tool is None:
            self._run_scripts_tool = RunScriptsWindow(
                service=get_script_service(),
                parent=parent or self._parent,
            )
        return self._run_scripts_tool

    def show_run_scripts_tool(self, parent=None):
        """Show the manual run scripts dialog.

        Args:
            parent: Optional parent widget.
        """
        with qt_app_context():
            window = self.get_run_scripts_tool(parent)
            window.refresh()
            window.show()
            window.raise_()
            window.activateWindow()
            window.showNormal()

    def get_tool_by_name(self, tool_name, parent=None, *args, **kwargs):
        """Return a cached tool window by name.

        Args:
            tool_name: Tool identifier.
            parent: Optional parent widget.
            *args: Unused positional arguments passed through.
            **kwargs: Unused keyword arguments passed through.

        Returns:
            Cached tool instance.
        """
        if tool_name == "run_scripts":
            return self.get_run_scripts_tool(parent)
        return super().get_tool_by_name(tool_name, parent, *args, **kwargs)

    def show_tool_by_name(self, tool_name, parent=None, *args, **kwargs):
        """Show a tool window by name.

        Args:
            tool_name: Tool identifier.
            parent: Optional parent widget.
            *args: Positional arguments passed through.
            **kwargs: Keyword arguments passed through.
        """
        if tool_name == "run_scripts":
            self.show_run_scripts_tool(parent)
            return
        super().show_tool_by_name(tool_name, parent, *args, **kwargs)


_helper = None


def _get_helper():
    global _helper
    if _helper is None:
        _helper = AEHostToolsHelper()
    return _helper


def get_tool_by_name(tool_name, parent=None, *args, **kwargs):
    """Return an After Effects host tool by name."""
    return _get_helper().get_tool_by_name(tool_name, parent, *args, **kwargs)


def show_tool_by_name(tool_name, parent=None, *args, **kwargs):
    """Show an After Effects host tool by name."""
    _get_helper().show_tool_by_name(tool_name, parent, *args, **kwargs)


def show_run_scripts_tool(parent=None):
    """Show the manual run scripts tool."""
    _get_helper().show_tool_by_name("run_scripts", parent)
