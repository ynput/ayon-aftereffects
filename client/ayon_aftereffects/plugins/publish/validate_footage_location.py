# -*- coding: utf-8 -*-
"""Validate footage is stored inside the project's AYON roots.

Requires:
    context -> anatomy
"""

import pyblish.api

from ayon_core.pipeline import (
    OptionalPyblishPluginMixin,
    PublishXmlValidationError,
)
from ayon_core.pipeline.publish import get_errored_plugins_from_context

from ayon_aftereffects.api import get_stub


class SelectInvalidFootageAction(pyblish.api.Action):
    """Select the offending FootageItems in the AE Project panel.

    The invalid items are recomputed on every click, so footage relinked
    since the validation failed is no longer selected, and footage deleted
    in the meantime is skipped instead of raising.
    """

    label = "Select invalid footage"
    icon = "search"
    on = "failed"

    def process(self, context, plugin):
        if plugin not in get_errored_plugins_from_context(context):
            return

        invalid = plugin.get_invalid(context)
        self.log.info(f"Selecting {len(invalid)} invalid footage item(s).")
        # an empty list deselects everything
        get_stub().select_items([item.id for item in invalid])


class ValidateFootageLocation(
    OptionalPyblishPluginMixin, pyblish.api.ContextPlugin
):
    """Validates that all footage is stored under an AYON project root.

    Footage loaded from a local folder (Desktop, Downloads, a personal
    drive) is not reachable from the render farm or from other artists'
    machines. AE fails silently on unreachable footage, so the farm render
    produces missing frames with no error.

    Scoped to the whole project on purpose, unlike `ValidateFootageItems`.
    AE's `usedIn`, which feeds `AEItem.containing_comps`, is undocumented
    for nested precomps, so filtering by comp could silently miss footage
    inside one. The whole project is a guaranteed superset.
    """

    order = pyblish.api.ValidatorOrder
    label = "Validate Footage Location"
    hosts = ["aftereffects"]
    settings_category = "aftereffects"
    actions = [SelectInvalidFootageAction]

    enabled = False
    optional = True
    active = True

    @classmethod
    def get_invalid(cls, context):
        """Return footage items stored outside of the project roots.

        Args:
            context (pyblish.api.Context): Publish context, provides
                "anatomy".

        Returns:
            list[AEItem]: Footage items outside of the project roots.
        """
        anatomy = context.data["anatomy"]
        footage_items = get_stub().get_items(
            comps=False, folders=False, footages=True
        )

        invalid = []
        for item in footage_items:
            # solids, placeholders and generated sources have no file
            if not item.path:
                continue
            success, _ = anatomy.find_root_template_from_path(item.path)
            if not success:
                invalid.append(item)

        return invalid

    def process(self, context):
        if not self.is_active(context.data):
            return

        invalid = self.get_invalid(context)
        if not invalid:
            return

        invalid_str = "\n".join(
            f"- {item.name}: {item.path}" for item in invalid
        )
        msg = (
            f"{len(invalid)} footage item(s) stored outside of project "
            f"roots:\n{invalid_str}"
        )
        raise PublishXmlValidationError(
            self, msg, formatting_data={"invalid_footage_str": invalid_str}
        )
