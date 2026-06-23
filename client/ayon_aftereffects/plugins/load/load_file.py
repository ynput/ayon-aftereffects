import re

from ayon_aftereffects import api
import ayon_api


class FileLoader(api.AfterEffectsLoader):
    """Load images and full AE workfiles.

    Stores the imported product version in a container named after the folder.
    """
    label = "Load file"

    product_base_types = {
        "image",
        "plate",
        "render",
        "prerender",
        "review",
        "audio",
        "workfile",
    }
    product_types = product_base_types
    representations = {"*"}

    def load(self, context, name=None, namespace=None, options=None):
        stub = self.get_stub()
        loaded_item_name = f"{context['folder']['name']}_{name}"
        footages = stub.get_items(comps=False, footages=True, folders=False)
        loaded_item_name = self._get_unique_loaded_item_name(
            stub, footages, loaded_item_name
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

        if import_options.get("sequence"):
            import_options['fps'] = self._get_fps_data(context)

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
            footages = stub.get_items(
                comps=False, footages=True, folders=False
            )
            loaded_item_name = self._get_unique_loaded_item_name(
                stub, footages, loaded_item_name
            )
        else:  # switching version - keep same name
            loaded_item_name = container["namespace"]
        path = self.filepath_from_context(context)

        stub.replace_item(item.id, path, stub.LOADED_ICON + loaded_item_name)
        stub.imprint(
            item.id,
            {
                "representation": repre_entity["id"],
                "name": product_name,
                "namespace": loaded_item_name
            }
        )

    def _get_fps_data(self, context: dict) -> float:
        """Get fps data from version. Fallback to task or folder
        if version doesn't have fps.

        Args:
            context (dict): context data with version, task and folder info

        Returns:
            float: fps value
        """
        version_entity = context["version"]
        version_attributes = version_entity["attrib"]
        if "fps" in version_attributes:
            return version_attributes["fps"]
        task_id = context["version"]["taskId"]
        if task_id is not None:
            task_entity = ayon_api.get_task_by_id(
                project_name=context["project"]["name"],
                task_id=task_id,
                fields={"attrib"},
            )
            if task_entity:
                return task_entity["attrib"]["fps"]

        folder_fps = context["folder"]["attrib"]["fps"]
        return folder_fps
