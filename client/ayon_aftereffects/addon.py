import os

from ayon_core.addon import AYONAddon, IHostAddon

from .version import __version__

AFTEREFFECTS_ADDON_ROOT = os.path.dirname(os.path.abspath(__file__))


class AfterEffectsAddon(AYONAddon, IHostAddon):
    name = "aftereffects"
    version = __version__
    host_name = "aftereffects"

    def add_implementation_envs(self, env, _app):
        """Modify environments to contain all required for implementation."""
        defaults = {
            "AYON_LOG_NO_COLORS": "1",
            "WEBSOCKET_URL": "ws://localhost:8097/ws/"
        }
        for key, value in defaults.items():
            if not env.get(key):
                env[key] = value

    def get_workfile_extensions(self):
        return [".aep"]

    def get_launch_hook_paths(self, app):
        if app.host_name != self.host_name:
            return []
        return [
            os.path.join(AFTEREFFECTS_ADDON_ROOT, "hooks")
        ]

    def publish_in_test(self, log, close_plugin_name=None):
        """Runs publish in an opened host with a context.

        Close Python process at the end.
        """

        from ayon_aftereffects.api.lib import publish_in_test

        publish_in_test(log, close_plugin_name)


def get_launch_script_path():
    return os.path.join(
        AFTEREFFECTS_ADDON_ROOT, "api", "launch_script.py"
    )
