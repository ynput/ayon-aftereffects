from ayon_core.tools.utils.host_tools import HostToolsHelper
from ayon_core.tools.utils.lib import qt_app_context

from .lib import raise_window_to_front
from .run_scripts_window import RunScriptsWindow
from .scripts import get_script_service

_TOOL_RUN_SCRIPTS = "run_scripts"


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
            raise_window_to_front(window)

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
        if tool_name == _TOOL_RUN_SCRIPTS:
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
        if tool_name == _TOOL_RUN_SCRIPTS:
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
    _get_helper().show_tool_by_name(_TOOL_RUN_SCRIPTS, parent)
