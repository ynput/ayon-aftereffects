import re
import os

from ayon_core.pipeline import get_representation_path
from ayon_aftereffects import api
from ayon_aftereffects.api.lib import get_unique_item_name


class FileLoader(api.AfterEffectsLoader):
    """Load images

    Stores the imported product version in a container named after the folder.
    """
    label = "Load file"

    product_types = {
        "image",
        "plate",
        "render",
        "prerender",
        "review",
        "audio",
    }
    representations = {"*"}

    def load(self, context, name=None, namespace=None, data=None):
        stub = self.get_stub()
        loaded_item_name = f"{context['folder']['name']}_{name}"
        loaded_item_name = self._get_unique_loaded_item_name(
            stub, loaded_item_name
        )

        import_options = {}

        path = self.filepath_from_context(context)

        if len(context["representation"]["files"]) > 1:
            import_options['sequence'] = True

        if not path:
            repr_id = context["representation"]["id"]
            self.log.warning(
                f"Representation id `{repr_id}` is failing to load"
            )
            return

        path = path.replace("\\", "/")
        if '.psd' in path:
            import_options['ImportAsType'] = 'ImportAsType.COMP'

        loaded_item = stub.import_file(
            path, stub.LOADED_ICON + loaded_item_name, import_options
        )
        if not loaded_item:
            self.log.warning(
                f"Representation `{path}` is failing to load"
            )
            self.log.warning("Check host app for alert error.")
            return

        self[:] = [loaded_item]
        namespace = namespace or loaded_item_name
        return api.containerise(
            name,
            namespace,
            loaded_item,
            context,
            self.__class__.__name__
        )

    def update(self, container, context):
        stub = self.get_stub()
        item = container.pop("layer")

        folder_name = context["folder"]["name"]
        product_name = context["product"]["name"]
        repre_entity = context["representation"]

        namespace_from_container = re.sub(
            r"_\d{3}$", "", container["namespace"]
        )

        loaded_item_name = f"{folder_name}_{product_name}"
        if namespace_from_container != loaded_item_name:
            loaded_item_name = self._get_unique_loaded_item_name(
                stub, loaded_item_name
            )
        else:  # switching version - keep same name
            loaded_item_name = container["namespace"]
        path = get_representation_path(repre_entity)

        if len(repre_entity["files"]) > 1:
           path = os.path.dirname(path)
        stub.replace_item(item.id, path, stub.LOADED_ICON + loaded_item_name)
        stub.imprint(
            item.id,
            {
                "representation": repre_entity["id"],
                "name": product_name,
                "namespace": loaded_item_name
            }
        )

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

    def _get_unique_loaded_item_name(self, stub, loaded_item_name):
        footages = stub.get_items(comps=False, footages=True, folders=False)
        existing_footage_names = [
            footage.name.replace(stub.LOADED_ICON, "") for footage in footages
        ]
        loaded_item_name = get_unique_item_name(
            existing_footage_names, loaded_item_name
        )
        return loaded_item_name
