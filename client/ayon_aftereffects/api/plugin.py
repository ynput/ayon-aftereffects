from ayon_core.pipeline import LoaderPlugin

from .launch_logic import get_stub
from ayon_aftereffects.api.lib import get_unique_item_name


class AfterEffectsLoader(LoaderPlugin):
    @staticmethod
    def get_stub():
        return get_stub()

    def remove(self, container):
        """
            Removes element from scene: deletes layer + removes from Headline
        Args:
            container (dict): container to be removed - used to get layer_id
        """
        stub = self.get_stub()
        item = container.pop("layer")
        stub.imprint(item.id, {})
        stub.delete_item(item.id)

    def switch(self, container, context):
        self.update(container, context)

    def _get_unique_loaded_item_name(
        self, stub, loaded_items, loaded_item_name
    ):
        existing_item_names = [
            item.name.replace(stub.LOADED_ICON, "") for item in loaded_items
        ]
        loaded_item_name = get_unique_item_name(
            existing_item_names, loaded_item_name
        )
        return loaded_item_name
