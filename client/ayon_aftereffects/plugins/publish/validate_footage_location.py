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

from ayon_aftereffects.api import get_stub


class SelectInvalidFootageAction(pyblish.api.Action):
    """Select the offending FootageItems in the AE Project panel."""

    label = "Select invalid footage"
    icon = "search"
    on = "failed"

    def process(self, context, plugin):
        item_ids = context.data.get("localFootageItemIds")
        if item_ids:
            get_stub().select_items(item_ids)


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

    optional = True
    active = True

    def process(self, context):
        if not self.is_active(context.data):
            return

        anatomy = context.data["anatomy"]

        invalid = []
        for item in context.data["footageItems"]:
            # solids, placeholders and generated sources have no file
            if not item.path:
                continue
            success, _ = anatomy.find_root_template_from_path(item.path)
            if not success:
                invalid.append(item)

        if not invalid:
            return

        context.data["localFootageItemIds"] = [item.id for item in invalid]

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
