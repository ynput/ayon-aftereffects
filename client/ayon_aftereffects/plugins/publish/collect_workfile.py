import os

import pyblish.api


class CollectWorkfile(pyblish.api.InstancePlugin):
    """Collect Workfile representation."""

    label = "Collect After Effects Workfile"
    order = pyblish.api.CollectorOrder + 0.1
    families = ["workfile"]
    hosts = ["aftereffects"]

    def process(self, instance):
        current_file = instance.context.data["currentFile"]
        staging_dir = os.path.dirname(current_file)
        scene_file = os.path.basename(current_file)

        # creating representation
        instance.data.setdefault("representations", []).append({
            "name": "aep",
            "ext": "aep",
            "files": scene_file,
            "stagingDir": staging_dir,
        })
