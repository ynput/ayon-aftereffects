from __future__ import annotations

from typing import Any

from ayon_core.pipeline import InventoryAction

from ayon_aftereffects.api import get_stub


def _set_version_locked(
    containers: list[dict[str, Any]], locked: bool
) -> None:
    """Store `version_locked` on each container in the project metadata.

    Metadata and items are read once and shared by every `imprint` call,
    which updates the matching container entry in place.
    """
    stub = get_stub()
    items_meta = stub.get_metadata()
    all_items = stub.get_items(comps=True, folders=True, footages=True)

    for container in containers:
        stub.imprint(
            container["layer"].id,
            {"version_locked": locked},
            all_items=all_items,
            items_meta=items_meta,
        )


class LockVersions(InventoryAction):
    label = "Lock versions"
    icon = "lock"
    color = "#ffffff"
    order = -1

    @staticmethod
    def is_compatible(container: dict[str, Any]) -> bool:
        return container.get("version_locked") is not True

    def process(self, containers: list[dict[str, Any]]) -> bool:
        _set_version_locked(to_lock, True)
        return True


class UnlockVersions(InventoryAction):
    label = "Unlock versions"
    icon = "lock-open"
    color = "#ffffff"
    order = -1

    @staticmethod
    def is_compatible(container: dict[str, Any]) -> bool:
        return container.get("version_locked") is True

    def process(self, containers: list[dict[str, Any]]) -> bool:
        _set_version_locked(to_unlock, False)
        return True
