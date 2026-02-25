import os
import sys
import subprocess
import collections
import logging
import asyncio
import functools
import traceback
import runpy

from wsrpc_aiohttp import (
    WebSocketRoute,
    WebSocketAsync
)

from qtpy import QtCore

from ayon_core.lib import Logger, is_in_tests, env_value_to_bool
from ayon_core.pipeline import install_host
from ayon_core.addon import AddonsManager
from ayon_core.tools.utils import host_tools, get_ayon_qt_app

from .webserver import WebServerTool
from .ws_stub import get_stub
from .lib import set_settings

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


console_window = None


def safe_excepthook(*args):
    traceback.print_exception(*args)


def main(*subprocess_args):
    """Main entrypoint to AE launching, called from pre hook."""
    sys.excepthook = safe_excepthook

    from ayon_aftereffects.api import AfterEffectsHost

    host = AfterEffectsHost()
    install_host(host)

    os.environ["AYON_LOG_NO_COLORS"] = "0"
    app = get_ayon_qt_app()
    app.setQuitOnLastWindowClosed(False)

    launcher = ProcessLauncher(subprocess_args)
    launcher.start()

    if _queue_custom_script(launcher):
        sys.exit(app.exec_())

    env_workfiles_on_launch = os.getenv(
        "AYON_AFTEREFFECTS_WORKFILES_ON_LAUNCH",
        # Backwards compatibility
        os.getenv("AVALON_AFTEREFFECTS_WORKFILES_ON_LAUNCH", True)
    )
    workfiles_on_launch = env_value_to_bool(value=env_workfiles_on_launch)

    if is_in_tests():
        manager = AddonsManager()
        aftereffects_addon = manager["aftereffects"]

        launcher.execute_in_main_thread(
            functools.partial(
                aftereffects_addon.publish_in_test,
                log,
                "CloseAE",
            )
        )

    elif workfiles_on_launch:
        save = False
        if os.getenv("WORKFILES_SAVE_AS"):
            save = True

        launcher.execute_in_main_thread(
            lambda: host_tools.show_tool_by_name("workfiles", save=save)
        )

    sys.exit(app.exec_())


def show_tool_by_name(tool_name):
    kwargs = {}
    if tool_name == "loader":
        kwargs["use_context"] = True

    host_tools.show_tool_by_name(tool_name, **kwargs)


def show_script_editor():
    from ayon_core.lib import is_func_signature_supported
    from ayon_core.tools.console_interpreter import InterpreterController
    from ayon_core.tools.console_interpreter.ui import ConsoleInterpreterWindow

    # Global so it doesn't get garbage collected instantly
    global console_window
    if console_window is None:
        # Signature added in ayon-core 1.7.0
        if is_func_signature_supported(
            InterpreterController, name="aftereffects"
        ):
            controller = InterpreterController(name="aftereffects")
        else:
            controller = InterpreterController()
        console_window = ConsoleInterpreterWindow(controller)
        console_window.setWindowTitle("Python Script Editor - AFX")
        console_window.setWindowFlags(
            console_window.windowFlags() |
            QtCore.Qt.Dialog |
            QtCore.Qt.WindowMinimizeButtonHint)
    console_window.show()
    console_window.raise_()
    console_window.activateWindow()


def _system_exit_code(exc):
    """Convert SystemExit to integer exit code."""
    if exc.code is None:
        return 0
    if isinstance(exc.code, int):
        return exc.code
    return 1


def _run_custom_script():
    """Run custom launch script payload in-process."""
    script_path = os.getenv("AYON_AFTEREFFECTS_SCRIPT_PATH")
    if not script_path:
        return

    normalized_script_path = os.path.normpath(script_path)
    if not os.path.isfile(normalized_script_path):
        raise FileNotFoundError(
            f"After Effects script not found: {normalized_script_path}"
        )

    script_args = os.getenv("AYON_AFTEREFFECTS_SCRIPT_ARGS")
    original_argv = list(sys.argv)
    argv = [normalized_script_path]
    if script_args:
        argv.append(script_args)

    log.info(
        f"Running After Effects control script in-process: {normalized_script_path}"
    )

    sys.argv = argv
    try:
        runpy.run_path(normalized_script_path, run_name="__main__")
    except SystemExit as exc:
        exit_code = _system_exit_code(exc)
        if exit_code:
            raise RuntimeError(
                f"After Effects control script exited with code {exc.code}"
            ) from exc
    finally:
        sys.argv = original_argv


def _queue_custom_script(launcher):
    """Queue custom startup script if configured."""
    if not os.getenv("AYON_AFTEREFFECTS_SCRIPT_PATH"):
        return False

    auto_exit = env_value_to_bool("AYON_AFTEREFFECTS_SCRIPT_AUTO_EXIT")
    log.info(f"Custom script mode enabled. AUTO_EXIT={auto_exit}")

    def _callback():
        exit_code = 0
        try:
            _run_custom_script()
        except Exception:
            log.warning("After Effects control script failed", exc_info=True)
            exit_code = 1
        finally:
            if auto_exit or exit_code:
                launcher.shutdown(exit_code=exit_code, request_client_close=True)

    launcher.execute_in_main_thread(_callback)
    return True


def _request_host_close():
    """Ask connected AE client to close gracefully.

    Returns:
        bool: True if close command was sent, False otherwise.
    """
    try:
        stub = get_stub()
    except Exception:
        log.warning("Could not get AE websocket stub for auto-exit.", exc_info=True)
        return False

    try:
        stub.close()
        log.info("Sent AfterEffects.close to host client.")
        return True
    except Exception:
        log.warning("Failed to send AfterEffects.close to host client.", exc_info=True)
        return False


class ProcessLauncher(QtCore.QObject):
    """Launches webserver, connects to it, runs main thread."""
    route_name = "AfterEffects"
    _main_thread_callbacks = collections.deque()

    def __init__(self, subprocess_args):
        self._subprocess_args = subprocess_args
        self._log = None

        super(ProcessLauncher, self).__init__()

        # Keep track if launcher was alreadu started
        self._started = False

        self._process = None
        self._websocket_server = None

        start_process_timer = QtCore.QTimer()
        start_process_timer.setInterval(100)

        loop_timer = QtCore.QTimer()
        loop_timer.setInterval(200)

        start_process_timer.timeout.connect(self._on_start_process_timer)
        loop_timer.timeout.connect(self._on_loop_timer)

        self._start_process_timer = start_process_timer
        self._loop_timer = loop_timer

    @property
    def log(self):
        if self._log is None:
            self._log = Logger.get_logger("{}-launcher".format(
                self.route_name))
        return self._log

    @property
    def websocket_server_is_running(self):
        if self._websocket_server is not None:
            return self._websocket_server.is_running
        return False

    @property
    def is_process_running(self):
        if self._process is not None:
            return self._process.poll() is None
        return False

    @property
    def is_host_connected(self):
        """Returns True if connected, False if app is not running at all."""
        if not self.is_process_running:
            return False

        try:

            _stub = get_stub()
            if _stub:
                return True
        except Exception:
            pass

        return None

    @classmethod
    def execute_in_main_thread(cls, callback):
        cls._main_thread_callbacks.append(callback)

    def start(self):
        if self._started:
            return
        self.log.info("Started launch logic of AfterEffects")
        self._started = True
        self._start_process_timer.start()

    def exit(self):
        """ Exit whole application. """
        self.shutdown(exit_code=0, request_client_close=False)

    def shutdown(self, exit_code=0, request_client_close=False):
        """Stop launcher resources and quit Qt app with exit code."""
        if self._start_process_timer.isActive():
            self._start_process_timer.stop()
        if self._loop_timer.isActive():
            self._loop_timer.stop()

        close_sent = False
        if request_client_close:
            close_sent = _request_host_close()

        if self._websocket_server is not None:
            self._websocket_server.stop()

        if close_sent and self._process and self._process.poll() is None:
            self._process.wait(timeout=10)

        if self._process and self._process.poll() is None:
            if request_client_close and not close_sent:
                self.log.warning(
                    "Auto-exit requested but close RPC was not sent; "
                    "falling back to host process termination."
                )
            self._terminate_host_process()

        QtCore.QCoreApplication.exit(exit_code)

    def _terminate_host_process(self, graceful_timeout=5):
        """Terminate host process and its children as a last resort."""
        if not self._process or self._process.poll() is not None:
            return

        self._process.terminate()
        self._process.wait(timeout=graceful_timeout)

        if self._process.poll() is not None:
            return

        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(self._process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            self._process.wait(timeout=graceful_timeout)

        if self._process.poll() is None:
            self._process.kill()
            self._process.wait(timeout=graceful_timeout)

    def _on_loop_timer(self):
        # TODO find better way and catch errors
        # Run only callbacks that are in queue at the moment
        cls = self.__class__
        for _ in range(len(cls._main_thread_callbacks)):
            if cls._main_thread_callbacks:
                callback = cls._main_thread_callbacks.popleft()
                callback()

        if not self.is_process_running:
            self.log.info("Host process is not running. Closing")
            self.exit()

        elif not self.websocket_server_is_running:
            self.log.info("Websocket server is not running. Closing")
            self.exit()

    def _on_start_process_timer(self):
        # TODO add try except validations for each part in this method
        # Start server as first thing
        if self._websocket_server is None:
            self._init_server()
            return

        # TODO add waiting time
        # Wait for webserver
        if not self.websocket_server_is_running:
            return

        # Start application process
        if self._process is None:
            self._start_process()
            self.log.info("Waiting for host to connect")
            return

        # TODO add waiting time
        # Wait until host is connected
        if self.is_host_connected:
            self._start_process_timer.stop()
            self._loop_timer.start()
        elif (
            not self.is_process_running
            or not self.websocket_server_is_running
        ):
            self.exit()

    def _init_server(self):
        if self._websocket_server is not None:
            return

        self.log.debug(
            "Initialization of websocket server for host communication"
        )

        self._websocket_server = websocket_server = WebServerTool()
        port = self.find_available_port(websocket_server)
        if port is None:
            self.log.info(
                "Server already running, sending actual context and exit."
            )
            asyncio.run(websocket_server.send_context_change(self.route_name))
            self.exit()
            return

        # Add Websocket route
        websocket_server.add_route("*", "/ws/", WebSocketAsync)
        # Add after effects route to websocket handler

        print("Adding {} route".format(self.route_name))
        WebSocketAsync.add_route(
            self.route_name, AfterEffectsRoute
        )

        self.log.info(
            "Starting websocket server for host communication at "
            f"{websocket_server.host_name}:{websocket_server.port}"
        )
        websocket_server.start_server()

    def find_available_port(self, websocket_server: WebServerTool):
        """Find an available port for the websocket server.

        This will update `self.port` and `self.webserver_thread.port` to match
        the port if a valid entry is found. It may be better to
        """
        # TODO: Do not hardcode the port range, but use a config value?
        alternative_ports = list(range(8097, 8110))
        alternative_index = 0
        while websocket_server.port_occupied(
            websocket_server.host_name,
            websocket_server.port
        ):
            if alternative_index > len(alternative_ports):
                return None

            alternative_port: int = alternative_ports[alternative_index]
            self.log.info(f"Testing alternative port: {alternative_port}")
            websocket_server.port = alternative_port

            # TODO: This is a bit of a hack, but the webserver thread needs
            #  to follow along, because it gets initialized on `__init__`.
            #  Probably a better way?
            websocket_server.webserver_thread.port = alternative_port
            alternative_index += 1
        return websocket_server.port

    def _start_process(self):
        if self._process is not None:
            return
        self.log.info("Starting host process")

        # Pass along the resulting websocket URL to the host process.
        # It may have been changed by the port finding logic.
        environ = os.environ.copy()
        environ["WEBSOCKET_URL"] = "ws://localhost:{}/ws/".format(
            self._websocket_server.port
        )
        try:
            self._process = subprocess.Popen(
                self._subprocess_args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=environ
            )
        except Exception:
            self.log.info("exce", exc_info=True)
            self.exit()


class AfterEffectsRoute(WebSocketRoute):
    """
        One route, mimicking external application (like Harmony, etc).
        All functions could be called from client.
        'do_notify' function calls function on the client - mimicking
            notification after long running job on the server or similar
    """
    instance = None

    def init(self, **kwargs):
        # Python __init__ must be return "self".
        # This method might return anything.
        log.debug("someone called AfterEffects route")
        self.instance = self
        return kwargs

    # server functions
    async def ping(self):
        log.debug("someone called AfterEffects route ping")

    # This method calls function on the client side
    # client functions
    async def set_context(self, project, folder, task):
        """
            Sets 'project', 'folder' and 'task' to envs, eg. setting context

            Args:
                project (str)
                folder (str)
                task (str)
        """
        log.info("Setting context change")
        log.info("project {} folder {} ".format(project, folder))
        if project:
            os.environ["AYON_PROJECT_NAME"] = project
        if folder:
            os.environ["AYON_FOLDER_PATH"] = folder
        if task:
            os.environ["AYON_TASK_NAME"] = task

    async def read(self):
        log.debug("aftereffects.read client calls server server calls "
                  "aftereffects client")
        return await self.socket.call('aftereffects.read')

    # panel routes for tools
    async def workfiles_route(self):
        self._tool_route("workfiles")

    async def loader_route(self):
        self._tool_route("loader")

    async def publish_route(self):
        self._tool_route("publisher")

    async def sceneinventory_route(self):
        self._tool_route("sceneinventory")

    async def setresolution_route(self):
        self._settings_route(False, True)

    async def setframes_route(self):
        self._settings_route(True, False)

    async def setall_route(self):
        self._settings_route(True, True)

    async def script_editor_route(self):
        ProcessLauncher.execute_in_main_thread(show_script_editor)

        # Required return statement.
        return "nothing"

    async def experimental_tools_route(self):
        self._tool_route("experimental_tools")

    def _tool_route(self, _tool_name):
        """The address accessed when clicking on the buttons."""

        partial_method = functools.partial(show_tool_by_name,
                                           _tool_name)

        ProcessLauncher.execute_in_main_thread(partial_method)

        # Required return statement.
        return "nothing"

    def _settings_route(self, frames, resolution):
        partial_method = functools.partial(set_settings,
                                           frames,
                                           resolution)

        ProcessLauncher.execute_in_main_thread(partial_method)

        # Required return statement.
        return "nothing"

    def create_placeholder_route(self):
        from ayon_aftereffects.api.workfile_template_builder import \
            create_placeholder
        partial_method = functools.partial(create_placeholder)

        ProcessLauncher.execute_in_main_thread(partial_method)

        # Required return statement.
        return "nothing"

    def update_placeholder_route(self):
        from ayon_aftereffects.api.workfile_template_builder import \
            update_placeholder
        partial_method = functools.partial(update_placeholder)

        ProcessLauncher.execute_in_main_thread(partial_method)

        # Required return statement.
        return "nothing"

    def build_workfile_template_route(self):
        from ayon_aftereffects.api.workfile_template_builder import \
            build_workfile_template
        partial_method = functools.partial(build_workfile_template)

        ProcessLauncher.execute_in_main_thread(partial_method)

        # Required return statement.
        return "nothing"
