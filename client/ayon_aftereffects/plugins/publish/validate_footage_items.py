# -*- coding: utf-8 -*-
"""Validate presence of footage in the publishable compositions.

Requires:
    context -> footageItems
"""
import os

import pyblish.api

from ayon_core.pipeline import (
    PublishXmlValidationError
)

from ayon_aftereffects.api import get_stub
from ayon_aftereffects.api.footage_sources import summarize_missing_sources


class ValidateFootageItems(pyblish.api.InstancePlugin):
    """
        Validates if FootageItems contained in composition exist.

    AE fails silently and doesn't render anything if footage item file is
    missing. This will result in nonresponsiveness of AE UI as it expects
    reaction from user, but it will not provide dialog.
    This validator tries to check existence of the files.
    It will not protect from missing frame in multiframes though
    (as AE api doesn't provide this information and it cannot be told how many
    frames should be there easily). Missing frame is replaced by placeholder.

    It also asks the host for layers without a usable source, because
    `footageItems` only lists footage that still exists in the project:
    footage removed from the project leaves its layers behind, they render
    black, and the publish would otherwise report nothing.

    Both checks run before anything is raised, so a single report lists
    every unusable item of the instance instead of only the first one.
    """

    order = pyblish.api.ValidatorOrder
    label = "Validate Footage Items"
    families = ["render.farm", "render.local", "render"]
    hosts = ["aftereffects"]
    optional = True

    def process(self, instance):
        """Plugin entry point."""
        invalid = self.get_invalid(instance)
        if not invalid:
            return

        messages = [problem["message"] for problem in invalid]
        raise PublishXmlValidationError(
            self,
            "\n".join(messages),
            key="problems",
            formatting_data={
                "comp_name": instance.data["comp_name"],
                "count": len(invalid),
                "problems": "\n".join(messages),
            },
        )

    def get_invalid(self, instance):
        """Return one problem per footage item whose file is gone.

        Args:
            instance (pyblish.api.Instance): Publish instance.

        Returns:
            list[dict]: Problem records with `key`, `message` and `data`.
        """
        comp_id = instance.data["comp_id"]
        invalid = []
        for footage_item in instance.context.data["footageItems"]:
            if comp_id not in footage_item.containing_comps:
                continue

            self.log.debug(f"Validating footage item: {footage_item.name}")

            path = footage_item.path
            if path and not os.path.exists(path):
                invalid.append(
                    {
                        "key": "main",
                        "message": f"File {path} not found.",
                        "data": {"name": footage_item.name, "path": path},
                    }
                )

        comp_name = instance.data["comp_name"]
        try:
            records = get_stub().get_missing_layer_sources(comp_id)
        except Exception:
            # An extension without the route must not stop the publish.
            self.log.warning(
                "Cannot check layer sources of '%s'. Is the AYON extension "
                "up to date?",
                comp_name,
                exc_info=True,
            )
            records = []

        if records:
            summary = summarize_missing_sources(records)
            invalid.append(
                {
                    "key": "missing_source",
                    "message": (
                        "Composition '{}' has layers without a usable source: "
                        "{}".format(comp_name, summary)
                    ),
                    "data": {
                        "comp_name": comp_name,
                        "count": len(records),
                        "layers": summary,
                        "comp_id": comp_id,
                    },
                }
            )
        return invalid
