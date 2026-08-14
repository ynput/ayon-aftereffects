from __future__ import annotations
import pyblish.api


class CollectSyncWorkfileVersion(pyblish.api.InstancePlugin):
    """Collect sync workfile version to instance data
    after scene version is collected by CollectSceneVersion.
    """

    order = pyblish.api.CollectorOrder + 0.001
    label = "Collect Sync Workfile Version"
    hosts = ["aftereffects"]

    settings_category = "aftereffects"

    def process(self, instance: pyblish.api.Instance):
        instance.data['version'] = instance.context.data['version']
