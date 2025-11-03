import re

from ayon_core.pipeline import get_representation_path

from ayon_aftereffects import api
from ayon_aftereffects.api.lib import get_background_layers


class BackgroundLoader(api.AfterEffectsLoader):
    """
        Load images from Background product type
        Creates for each background separate folder with all imported images
        from background json AND automatically created composition with layers,
        each layer for separate image.

        For each load container is created and stored in project (.aep)
        metadata
    """
    label = "Load JSON Background"
    product_types = {"background"}
    representations = {"json"}

    def load(self, context, name=None, namespace=None, data=None):
        stub = self.get_stub()
        loaded_item_name = f"{context['folder']['name']}_{name}"
        comps = stub.get_items(comps=True)
        loaded_item_name = self._get_unique_loaded_item_name(
            stub, comps, loaded_item_name
        )

        path = self.filepath_from_context(context)
        layers = get_background_layers(path)
        if not layers:
            raise ValueError("No layers found in {}".format(path))

        loaded_item = stub.import_background(
            None, stub.LOADED_ICON + loaded_item_name, layers
        )

        if not loaded_item:
            raise ValueError(
                "Import background failed. "
                "Please contact support"
            )

        self[:] = [loaded_item]
        namespace = namespace or loaded_item

        return api.containerise(
            name,
            namespace,
            loaded_item,
            context,
            self.__class__.__name__
        )

    def update(self, container, context):
        stub = self.get_stub()
        folder_name = context["folder"]["name"]
        product_name = context["product"]["name"]
        repre_entity = context["representation"]

        _ = container.pop("layer")

        # without iterator number (_001, 002...)
        namespace_from_container = re.sub(
            r"_\d{3}$", "", container["namespace"]
        )

        loaded_item_name = f"{folder_name}_{product_name}"
        # switching assets
        if namespace_from_container != loaded_item_name:
            loaded_item_name = self._get_unique_loaded_item_name(
                stub, loaded_item_name)
        else:  # switching version - keep same name
            loaded_item_name = container["namespace"]

        path = get_representation_path(repre_entity)

        layers = get_background_layers(path)
        loaded_item = stub.reload_background(
            container["members"][1],
            stub.LOADED_ICON + loaded_item_name,
            layers
        )

        # update container
        container["representation"] = repre_entity["id"]
        container["name"] = product_name
        container["namespace"] = loaded_item_name
        container["members"] = loaded_item.members

        stub.imprint(loaded_item.id, container)
