import os
import platform
import re
from pathlib import Path

from ayon_applications import PreLaunchHook, LaunchTypes
from ayon_aftereffects import AFTEREFFECTS_ADDON_ROOT


class OpenPanelOnFirstLaunch(PreLaunchHook):
    """Deploy a JSX to AE's Scripts/Startup folder to auto-open the panel.

    The deployed JSX polls until CEP registers the AYON menu command,
    then waits to see if the workspace restores the panel automatically.
    If it does not within 5 seconds, it calls executeCommand to open it.
    """

    app_groups = {"aftereffects"}
    order = 15
    launch_types = {LaunchTypes.local}

    def execute(self):
        try:
            settings = self.data["project_settings"]["aftereffects"]
            if settings["auto_open_panel"]:
                self._inner_execute()
        except Exception:
            self.log.warning(
                "Could not deploy panel startup script.",
                exc_info=True,
            )

    def _inner_execute(self):
        # launch_args[0] is still the AE executable at order=15;
        # AEPrelaunchHook (order=20) pops it later.
        exe_path = str(self.launch_context.launch_args[0])
        startup_dirs = self._get_startup_dirs(exe_path)
        script_name = "open_ayon_panel.jsx"

        source = (
            Path(AFTEREFFECTS_ADDON_ROOT) /
            "api" /
            "extension" /
            "jsx" /
            script_name
        )

        script_content = source.read_text(encoding="utf-8")
        for startup_dir in startup_dirs:
            startup_dir.mkdir(parents=True, exist_ok=True)
            target = startup_dir / script_name
            target.write_text(script_content, encoding="utf-8")
            self.log.info("Panel startup script deployed to: %s", target)

    def _get_startup_dirs(self, exe_path: str) -> "list[Path]":
        """Return user-level Scripts/Startup paths for the targeted AE.

        Extracts the release year from the executable path (e.g. 2025),
        converts it to the internal major version (25), then globs the
        user-level Adobe preferences directory for matching version
        folders (e.g. 25.6).  Returns an empty list when no matching
        folder exists yet (first-ever AE launch before prefs are
        created) or on unsupported platforms.
        """
        match = re.search(r"After Effects (\d{4})", exe_path)
        if not match:
            return []

        major = int(match.group(1)) - 2000  # 2025 → 25

        system = platform.system().lower()
        if system == "darwin":
            base = (
                Path.home() / 'Library/Preferences/Adobe/After Effects'
            )
        elif system == "windows":
            appdata = os.environ.get("APPDATA", "")
            if not appdata:
                return []
            base = Path(appdata) / 'Adobe/After Effects'
        else:
            return []

        matching = list(base.glob(f"{major}.*"))
        return [d / "Scripts/Startup" for d in matching]
