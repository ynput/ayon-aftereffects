# -*- coding: utf-8 -*-
"""Collect footage items of the current After Effects project."""
import pyblish.api

from ayon_aftereffects.api import get_stub


class CollectFootageItems(pyblish.api.ContextPlugin):
    """Collect all FootageItems of the AE project once per publish.

    Stored under `context.data["footageItems"]` so validators do not each
    pay for their own blocking RPC round-trip to After Effects.
    """

    label = "Collect After Effects Footage Items"
    order = pyblish.api.CollectorOrder - 0.4
    hosts = ["aftereffects"]

    def process(self, context):
        footage_items = get_stub().get_items(
            comps=False, folders=False, footages=True
        )
        context.data["footageItems"] = footage_items
        self.log.debug(f"Collected {len(footage_items)} footage item(s).")
