# -*- coding: utf-8 -*-
"""Validate that each render instance has exactly one Render Queue item
Requires:
    instance -> render_queue_error (set by CollectAERender on a problem)
"""
import pyblish.api

from ayon_core.pipeline import PublishXmlValidationError
from ayon_core.pipeline.publish import RepairAction

from ayon_aftereffects.api import get_stub


class ValidateRenderQueue(pyblish.api.InstancePlugin):
    """Validates the Render Queue item of a rendered composition.

    Each composition must be in the Render Queue exactly once, because its
    output settings and file name are read from that single item. A second
    item usually comes from queuing the composition again after a local
    render.

    The check itself happens in CollectAERender, which records the problem
    on the instance instead of stopping the whole collection. This plugin
    reports it and offers a Repair:
        - more than one item: keeps one, removes the rest
        - no item: adds the composition to the Render Queue
    """

    order = pyblish.api.ValidatorOrder
    label = "Validate Render Queue"
    families = ["render"]
    hosts = ["aftereffects"]
    actions = [RepairAction]

    def process(self, instance):
        """Plugin entry point."""
        error = instance.data.get("render_queue_error")
        if not error:
            return

        count = instance.data.get("render_queue_item_count", 0)
        if count > 1:
            key = "duplicate_items"
        elif count == 0:
            key = "no_item"
        else:
            key = "main"

        comp_name = instance.data["comp_name"]
        formatting_data = {
            "comp_name": comp_name,
            "count": count,
            "error": error,
        }
        raise PublishXmlValidationError(
            self,
            f"Render Queue problem for '{comp_name}': {error}",
            key=key,
            formatting_data=formatting_data,
        )

    @classmethod
    def repair(cls, instance):
        stub = get_stub()
        comp_id = instance.data["comp_id"]
        count = instance.data.get("render_queue_item_count", 0)
        if count > 1:
            removed = stub.remove_duplicate_render_queue_items(comp_id)
            cls.log.info(
                f"Removed {removed} extra Render Queue item(s) for "
                f"'{instance.data['comp_name']}'."
            )
        elif count == 0:
            stub.add_comp_to_render_queue(comp_id)
            cls.log.info(
                f"Added '{instance.data['comp_name']}' to the Render Queue."
            )
        else:
            cls.log.warning(
                "Nothing to repair automatically, check the Render Queue "
                "item and its Output Module."
            )
