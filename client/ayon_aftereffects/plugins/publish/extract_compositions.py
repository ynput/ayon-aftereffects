import pyblish.api

from ayon_core.pipeline import publish
from ayon_aftereffects.api import get_stub


class ExtractCompositions(pyblish.api.InstancePlugin):
    """Collects all compositions contained in workfile.

    Used later in Premiere to choose which composition to load.

    Note: previously named ``ExtractSaveScene``, which collided with the
    real save plug-in in ``extract_save_scene.py``. Because Pyblish
    ``discover()`` dedupes by class name, the actual scene-save plug-in
    was silently dropped and the workfile was never saved at the
    extractor stage, causing downstream plug-ins (farm submit) to read
    a stale workfile from disk. Renaming this class restores the real
    ``ExtractSaveScene`` to the discovered plug-in list.
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
        if "data" not in representation:
            representation["data"] = {}
        data = {
            "composition_names_in_workfile": [item.name for item in comp_items]
        }
        representation["data"].update(data)
