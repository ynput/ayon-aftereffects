from __future__ import annotations

import os
from dataclasses import dataclass

from ayon_core.lib import Logger, StringTemplate
from ayon_core.pipeline import Anatomy
from ayon_core.pipeline.context_tools import (
    get_current_context_template_data,
    get_current_project_settings,
)

from .ws_stub import ConnectionNotEstablishedYet, get_stub

log = Logger.get_logger("ayon_aftereffects.scripts")

_SUPPORTED_EXTENSIONS = (".js", ".jsx")


@dataclass(frozen=True)
class ScriptItem:
    """Resolved After Effects script item.

    Attributes:
        script_id: Stable identifier for the configured script.
        name: Display name shown to the user.
        path: Resolved absolute path or unresolved raw path.
        auto: Whether the script should run automatically on launch.
        exists: Whether the script can be executed.
        error: Validation error when the script is not executable.
    """

    script_id: str
    name: str
    path: str
    auto: bool
    exists: bool
    error: str | None = None


@dataclass(frozen=True)
class ScriptRunResult:
    """Execution result for a configured script.

    Attributes:
        script_id: Stable identifier for the configured script.
        success: Whether the script execution succeeded.
        message: User-facing execution status.
    """

    script_id: str
    success: bool
    message: str


class ScriptService:
    """Resolve and execute configured After Effects scripts."""

    def list_items(self, auto: bool | None = None) -> list[ScriptItem]:
        """Return resolved script items from project settings.

        Args:
            auto: Optional auto/manual filter. When `None`, all items are
                returned.

        Returns:
            Resolved script items in settings order.
        """
        project_settings = get_current_project_settings()
        scripts_settings = project_settings["aftereffects"]["scripts"]
        configs = scripts_settings["configs"]

        if not configs:
            log.debug("No scripts found in project settings.")
            return []

        output: list[ScriptItem] = []
        for index, config in enumerate(configs):
            item_auto: bool = config["auto"]
            if auto is not None and item_auto != auto:
                continue

            raw_path: str = config["path"]
            name: str = config["name"]

            error: str | None = None
            exists = False
            if not raw_path:
                resolved_path = raw_path
                error = "Script path is empty."
            else:
                resolved_path = self.resolve_path(raw_path)
                if not self._has_supported_extension(resolved_path):
                    error = "Only .js and .jsx files are supported."
                elif not os.path.isfile(resolved_path):
                    error = "Script file does not exist."
                else:
                    exists = True

            output.append(
                ScriptItem(
                    script_id=f"script_{index}",
                    name=name,
                    path=resolved_path,
                    auto=item_auto,
                    exists=exists,
                    error=error,
                )
            )
        return output

    def list_manual_items(self) -> list[ScriptItem]:
        """Return scripts configured for manual execution.

        Returns:
            Manual script items.
        """
        return self.list_items(auto=False)

    def resolve_scripts(self, auto: bool = True) -> list[str]:
        """Resolve executable script paths.

        Args:
            auto: Auto/manual filter.

        Returns:
            Ordered list of executable script paths.
        """
        return [
            item.path for item in self.list_items(auto=auto) if item.exists
        ]

    def resolve_path(self, path: str) -> str:
        """Resolve a templated script path against current AYON context.

        Args:
            path: Raw configured path.

        Returns:
            Resolved path.
        """
        template_data = get_current_context_template_data()
        template_data.update(os.environ)

        project_name = template_data["project"]["name"]
        anatomy = Anatomy(project_name)
        template_data["root"] = anatomy.roots

        result = StringTemplate.format_template(path, template_data)
        if result.solved:
            path = result.normalized()
            return anatomy.path_remapper(path)

        return path

    def run_scripts(self, auto: bool = True) -> None:
        """Run all valid scripts for the requested mode.

        Args:
            auto: Auto/manual filter.
        """
        for item in self.list_items(auto=auto):
            result = self._run_item(item)
            if not result.success:
                log.warning(result.message)
            else:
                log.info(f"Script {item.name} ran successfully.")

    def run_item(self, item: ScriptItem) -> ScriptRunResult:
        """Run a resolved script item directly.
        Args:
            item: Already-resolved script item (e.g. from list_manual_items).
        Returns:
            Script execution result.
        """
        return self._run_item(item)

    def _find_item(
        self,
        script_id: str,
        auto: bool | None = None,
    ) -> ScriptItem | None:
        """Find a resolved script item by identifier.

        Args:
            script_id: Stable script identifier.
            auto: Optional auto/manual filter.

        Returns:
            Matching script item, if found.
        """
        for item in self.list_items(auto=auto):
            if item.script_id == script_id:
                return item
        return None

    def _run_item(self, item: ScriptItem) -> ScriptRunResult:
        """Run a resolved script item.

        Args:
            item: Script item to execute.

        Returns:
            Script execution result.
        """
        if not item.exists:
            return ScriptRunResult(
                script_id=item.script_id,
                success=False,
                message=item.error or "Script is not executable.",
            )

        try:
            stub = get_stub()
        except ConnectionNotEstablishedYet:
            return ScriptRunResult(
                script_id=item.script_id,
                success=False,
                message="After Effects client is not connected.",
            )

        try:
            log.debug("Running script: %s", item.path)
            stub.run_jsx_file(item.path)
        except Exception:
            log.warning("Failed to run script: %s", item.path, exc_info=True)
            return ScriptRunResult(
                script_id=item.script_id,
                success=False,
                message=f"Failed to run script: {item.name}",
            )

        return ScriptRunResult(
            script_id=item.script_id,
            success=True,
            message=f"Executed script: {item.name}",
        )

    def _has_supported_extension(self, path: str) -> bool:
        """Return whether the path has a supported extension.

        Args:
            path: Resolved script path.

        Returns:
            Whether the extension is supported.
        """
        return path.lower().endswith(_SUPPORTED_EXTENSIONS)


_SCRIPT_SERVICE = ScriptService()


def get_script_service() -> ScriptService:
    """Return the singleton script service.

    Returns:
        Shared script service instance.
    """
    return _SCRIPT_SERVICE


def resolve_scripts(auto: bool = True) -> list[str]:
    """Resolve active script paths from project settings.

    Args:
        auto: Auto/manual filter.

    Returns:
        Ordered list of executable script paths.
    """
    return get_script_service().resolve_scripts(auto=auto)


def resolve_path(path: str) -> str:
    """Resolve a templated script path against current AYON context.

    Args:
        path: Raw configured path.

    Returns:
        Resolved path.
    """
    return get_script_service().resolve_path(path)


def run_scripts(auto: bool = True) -> None:
    """Run configured After Effects scripts.

    Args:
        auto: Auto/manual filter.
    """
    get_script_service().run_scripts(auto=auto)
