import pyblish.api

from ayon_core.pipeline import publish
from ayon_aftereffects.api import get_stub


class ExtractSaveScene(pyblish.api.InstancePlugin):
    """Collects all compositions contained in workfile.

    Used later in Premiere to choose which composition to load.
    """

    order = publish.Extractor.order
    label = "Extract Compositions"
    hosts = ["aftereffects"]
    families = ["workfile"]

    def process(self, instance):
        stub = get_stub()
        representation = instance.data["representations"][0]

        comp_items =  stub.get_items(
            comps=True,
            folders=False,
            footages=False
        )
        if not "data" in representation:
            representation["data"] = {}
        data = {
            "composition_names_in_workfile": [item.name for item in comp_items]
        }
        representation["data"].update(data)
