# -*- coding: utf-8 -*-
"""Validate footage is stored inside the project's AYON roots.

Requires:
    context -> anatomy
    context -> footageItems
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

    Refreshes the collected footage before recomputing, so footage relinked
    since the validation failed is no longer selected, and footage deleted
    in the meantime is skipped instead of raising.
    """

    label = "Select invalid footage"
    icon = "search"
    on = "failed"

    def process(self, context, plugin):
        if plugin not in get_errored_plugins_from_context(context):
            return

        stub = get_stub()
        # re-query so the recompute reflects the current project state
        context.data["footageItems"] = stub.get_items(
            comps=False, folders=False, footages=True
        )

        invalid = plugin.get_invalid(context)
        self.log.info(f"Selecting {len(invalid)} invalid footage item(s).")
        # an empty list deselects everything
        stub.select_items([item.id for item in invalid])


class ValidateFootageLocation(
    OptionalPyblishPluginMixin, pyblish.api.ContextPlugin
):
    """Validates that all footage is stored under an AYON project root.

    Footage loaded from a local folder (Desktop, Downloads, a personal
    drive) is not reachable from the render farm or from other artists'
    machines. AE fails silently on unreachable footage, so the farm render
    produces missing frames with no error.
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
                "anatomy" and "footageItems".

        Returns:
            list[AEItem]: Footage items outside of the project roots.
        """
        anatomy = context.data["anatomy"]

        invalid = []
        for item in context.data["footageItems"]:
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

        msg = "{} footage item(s) stored outside of project roots:\n{}".format(
            len(invalid),
            "\n".join(f"- {item.name}: {item.path}" for item in invalid),
        )

        formatting_data = {
            "invalid_footage_str": "<br/>".join(
                f"<b>{item.name}</b>: {item.path}" for item in invalid
            )
        }
        raise PublishXmlValidationError(
            self, msg, formatting_data=formatting_data
        )
