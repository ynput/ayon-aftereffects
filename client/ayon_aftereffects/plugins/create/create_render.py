import re

from ayon_core.lib import BoolDef, UISeparatorDef, EnumDef
from ayon_core.pipeline import (
    Creator,
    CreatedInstance,
    CreatorError
)
from ayon_core.lib import prepare_template_data
from ayon_core.pipeline.context_tools import get_current_project_settings
from ayon_core.pipeline.create import PRODUCT_NAME_ALLOWED_SYMBOLS

from ayon_aftereffects import api
from ayon_aftereffects.api import output_module
from ayon_aftereffects.api.pipeline import cache_and_get_instances
from ayon_aftereffects.api.lib import set_settings


class RenderCreator(Creator):
    """Creates 'render' instance for publishing.

    Result of 'render' instance is video or sequence of images for particular
    composition based of configuration in its RenderQueue.
    """
    identifier = "render"
    label = "Render"
    product_base_type = "render"
    product_type = product_base_type
    description = "Render creator"
    icon = "eye"
    settings_category = "aftereffects"

    create_allow_context_change = True

    rendering_targets = {
        "local": "Local machine rendering",
        "farm": "Farm rendering",
        "frames": "Use existing frames"
    }

    # Settings
    mark_for_review = True
    force_setting_values = True
    rename_comp_to_product_name = True
    sync_with_render_queue = False

    @staticmethod
    def _clean_composition_name(comp_name) -> str:
        """Strip characters that are not allowed in product names."""
        return re.sub(
            "[^{}]+".format(PRODUCT_NAME_ALLOWED_SYMBOLS), "", comp_name
        )

    @staticmethod
    def _fill_composition(product_name, composition_name) -> str:
        """Fill the '{composition}' placeholder, in any letter case."""
        dynamic_fill: dict[str, str] = prepare_template_data(
            {"composition": composition_name}
        )
        return product_name.format(**dynamic_fill)

    def create(self, product_name, instance_data, pre_create_data):
        stub = api.get_stub()  # only after After Effects is up

        try:
            _ = stub.get_active_document_full_name()
        except ValueError:
            raise CreatorError(
                "Please save workfile via Workfile app first!"
            )

        if pre_create_data.get("use_selection"):
            comps = stub.get_selected_items(
                comps=True, folders=False, footages=False
            )
        else:
            comps = stub.get_items(comps=True, folders=False, footages=False)

        if not comps:
            raise CreatorError(
                "Nothing to create. Select composition in Project Bin if "
                "'Use selection' is toggled or create at least "
                "one composition."
            )
        use_composition_name = (pre_create_data.get("use_composition_name") or
                                len(comps) > 1)

        # Transfer certain attributes to creator attributes
        creator_attributes = {
            "render_target": pre_create_data["render_target"],
            "mark_for_review": pre_create_data["mark_for_review"]
        }

        for comp in comps:
            composition_name = self._clean_composition_name(comp.name)
            if use_composition_name:
                if "{composition}" not in product_name.lower():
                    product_name += "{Composition}"

                comp_product_name = self._fill_composition(
                    product_name, composition_name
                )
                instance_data["composition_name"] = composition_name
            else:
                comp_product_name = re.sub(
                    r"\{composition\}",
                    "",
                    product_name,
                    flags=re.IGNORECASE
                )

            instance_data["members"] = [comp.id]
            instance_data["creator_attributes"] = creator_attributes
            if self.rename_comp_to_product_name:
                instance_data["orig_comp_name"] = composition_name

            self._add_new_instance(comp_product_name, instance_data)

            if self.rename_comp_to_product_name:
                stub.rename_item(comp.id, comp_product_name)
            if self.force_setting_values:
                # Force fps, frame range and resolution of comp to match
                # the target publish context attributes.
                # Task is not required for an instance, so it may be not set
                if instance_data.get("task"):
                    entity = self.create_context.get_task_entity(
                        folder_path=instance_data["folderPath"],
                        task_name=instance_data["task"],
                    )
                else:
                    entity = self.create_context.get_folder_entity(
                        folder_path=instance_data["folderPath"]
                    )
                set_settings(
                    frames=True,
                    resolution=True,
                    comp_ids=[comp.id],
                    print_msg=False,
                    entity=entity)
            self._ensure_comp_in_render_queue(
                stub=stub,
                comp_id=comp.id,
                product_name=comp_product_name,
                render_target=creator_attributes["render_target"]
            )

    def get_pre_create_attr_defs(self):
        output = [
            BoolDef("use_selection",
                    tooltip="Composition for publishable instance should be "
                            "selected by default.",
                    default=True, label="Use selection"),
            BoolDef("use_composition_name",
                    label="Use composition name in product"),
            UISeparatorDef(),
            EnumDef(
                "render_target",
                items=self.rendering_targets,
                label="Render target"
            ),
            BoolDef(
                "mark_for_review",
                label="Review",
                default=self.mark_for_review
            )
        ]
        return output

    def get_instance_attr_defs(self):
        return [
            EnumDef(
                "render_target",
                items=self.rendering_targets,
                label="Render target"
            ),
            BoolDef(
                "mark_for_review",
                label="Review",
                default=False
            )
        ]

    def _add_new_instance(self, product_name, data):
        """Create an instance, store it in the workfile and add it to context.

        Args:
            product_name (str): Fully resolved product name.
            data (dict): Instance data. Product type is read from its
                'productType' key, defaulting to the creator's base type.
        """
        product_type = data.get("productType") or self.product_base_type
        new_instance = CreatedInstance(
            product_base_type=self.product_base_type,
            product_type=product_type,
            product_name=product_name,
            data=data,
            creator=self,
        )
        api.get_stub().imprint(new_instance.id, new_instance.data_to_store())
        self._add_instance_to_context(new_instance)

    def _ensure_comp_in_render_queue(
        self,
        stub: object,
        comp_id: int,
        product_name: str,
        render_target: str,
    ) -> None:
        """Ensure composition is present in After Effects render queue.

        Args:
            stub (object): Connected After Effects server stub.
            comp_id (int): Composition item id in After Effects.
            product_name (str): Product name, used for readable errors and
                for the output file name.
            render_target (str): Where the instance renders, 'local',
                'farm' or 'frames' for existing frames.

        Raises:
            CreatorError: When composition cannot be queued.
        """
        try:
            queued = stub.add_comp_to_render_queue(comp_id)
        except ValueError as exc:
            raise CreatorError(
                f"Failed to add '{product_name}' to render queue: {exc}"
            ) from exc

        if not queued:
            raise CreatorError(
                f"Failed to add '{product_name}' to render queue."
            )

        self._apply_output_module_name(
            stub, comp_id, product_name, render_target
        )

    def _apply_output_module_name(
        self,
        stub: object,
        comp_id: int,
        product_name: str,
        render_target: str,
    ) -> None:
        """Name the Output Module from the matching preset.

        AYON queues the composition with the bare product name, so a
        sequence format becomes `name.exr00835` once After Effects appends
        the frame number after the extension - a render that cannot be
        published. The presets already describe the expected name, so the
        instance is created correct instead of failing later.

        Instances that publish existing frames are left alone: their files
        are already on disk under the current name, and renaming the
        Output Module would make those frames unrecognisable.

        Never raises: a missing preset, an older AYON extension or a host
        error must not stop the instance from being created.

        Args:
            stub (object): Connected After Effects server stub.
            comp_id (int): Composition item id in After Effects.
            product_name (str): Product name of the instance.
            render_target (str): Where the instance renders.
        """
        if render_target == "frames":
            self.log.debug(
                "Publishing existing frames of '%s', keeping the Output "
                "Module name.",
                product_name,
            )
            return

        presets = self._output_presets()
        if not presets:
            return

        try:
            modules = stub.get_output_module_info(comp_id)
        except Exception:
            self.log.warning(
                "Cannot read the Output Module of '%s'. Is the AYON "
                "extension up to date? The Render Queue keeps the name "
                "'%s'.",
                product_name,
                product_name,
                exc_info=True,
            )
            return

        for module in modules or []:
            name = output_module.creation_name(product_name, module, presets)
            if not name:
                continue

            current = output_module.parse_output_name(module.get("file_name"))
            if name == current.name:
                continue

            try:
                stub.fix_output_module(comp_id, module.get("index", 1), name)
            except Exception:
                self.log.warning(
                    "Cannot name Output Module %s of '%s' as '%s'.",
                    module.get("index", 1),
                    product_name,
                    name,
                    exc_info=True,
                )
                continue

            self.log.info(
                "Output Module %s of '%s' writes '%s'.",
                module.get("index", 1),
                product_name,
                name,
            )

    @staticmethod
    def _output_presets():
        """Return the Output Module presets from project settings.

        The presets are configured on the Validate Output Module plugin and
        describe the allowed format, extension and file name per Output
        Module, so they are used for naming as well.

        Returns:
            list[dict]: Preset settings, empty when not configured.
        """
        try:
            project_settings = get_current_project_settings()
        except Exception:
            return []

        after_effects = (project_settings or {}).get("aftereffects") or {}
        publish_settings = after_effects.get("publish") or {}
        plugin_settings = publish_settings.get("ValidateOutputModule") or {}
        return plugin_settings.get("presets") or []

    def collect_instances(self):
        instances_by_comp_id = {}
        for instance_data in cache_and_get_instances(self):
            creator_id = instance_data.get("creator_identifier")
            if not creator_id:
                # NOTE this is for backwards compatibility but probably can be
                #   removed
                # - legacy family was 'render' or 'renderLocal'
                family = instance_data.get("family", "").replace("Local", "")
                if family == self.product_base_type:
                    creator_id = self.identifier

            if creator_id == self.identifier:
                instance_data = self._handle_legacy(instance_data)
                instance = CreatedInstance.from_existing(
                    instance_data, self
                )
                self._add_instance_to_context(instance)
                members = instance.data.get("members")
                if members:
                    instances_by_comp_id[int(members[0])] = instance

        if self.sync_with_render_queue:
            self._sync_with_render_queue(instances_by_comp_id)

    def _sync_with_render_queue(self, instances_by_comp_id):
        """Mirror the After Effects render queue into created instances.

        Compositions queued directly in After Effects gain an instance, and
        instances whose composition left the queue are dropped.

        Args:
            instances_by_comp_id (dict[int, CreatedInstance]): Already
                collected instances keyed by the composition they publish.
        """
        try:
            queued_comps = api.get_stub().get_render_queue_comps()
        except Exception:
            # Publisher reset must survive a disconnected or wedged AE
            self.log.warning(
                "Cannot read render queue, skipping sync.", exc_info=True
            )
            return

        queued_by_comp_id = {int(comp.id): comp for comp in queued_comps}

        for comp_id, comp in queued_by_comp_id.items():
            if comp_id not in instances_by_comp_id:
                self._create_instance_for_queued_comp(comp)

        for comp_id, instance in instances_by_comp_id.items():
            if comp_id in queued_by_comp_id:
                continue
            self.log.info(
                f"Composition {comp_id} left the render queue, "
                "removing its instance."
            )
            self._remove_instance_from_context(instance)
            self.host.remove_instance(instance)

    def _create_instance_for_queued_comp(self, comp):
        """Create a render instance for a composition found in the queue.

        Uses the creator's default variant. The composition name only
        appears in the product name where the template has a
        '{composition}' placeholder. Folder and task come from the current
        context, as the queue carries no publish context of its own.

        Args:
            comp (AEItem): Composition record from the render queue.
        """
        composition_name = self._clean_composition_name(comp.name)
        if not composition_name:
            self.log.warning(
                f"Cannot use composition name '{comp.name}' in a product "
                "name, skipping."
            )
            return
        variant = self.default_variant

        project_name = self.create_context.get_current_project_name()
        project_entity = self.create_context.get_current_project_entity()
        folder_entity = self.create_context.get_current_folder_entity()
        task_entity = self.create_context.get_current_task_entity()

        if not (project_name and project_entity and folder_entity):
            self.log.warning(
                "No current project or folder, cannot create instance for "
                f"'{comp.name}'."
            )
            return

        # Same default as 'CreateContext.create', so a product type set in
        # the creator settings applies here too
        product_type = next(
            (item.product_type for item in self.get_product_type_items()),
            self.product_base_type,
        )

        data = {
            "folderPath": folder_entity["path"],
            "task": task_entity["name"] if task_entity else None,
            "productType": product_type,
            "variant": variant,
            "composition_name": composition_name,
            "members": [comp.id],
            "orig_comp_name": composition_name,
            "creator_attributes": {
                "render_target": "local",
                "mark_for_review": self.mark_for_review,
            },
        }

        product_name = self.get_product_name(
            project_name=project_name,
            project_entity=project_entity,
            folder_entity=folder_entity,
            task_entity=task_entity,
            variant=variant,
            host_name=self.create_context.host_name,
            product_type=product_type,
        )
        # 'get_dynamic_data' leaves '{composition}' unresolved without an
        # instance to read it from, so fill it in here
        product_name = self._fill_composition(product_name, composition_name)

        self._add_new_instance(product_name, data)

    def update_instances(self, update_list):
        for created_inst, _changes in update_list:
            api.get_stub().imprint(created_inst.get("instance_id"),
                                   created_inst.data_to_store())
            name_change = _changes.get("productName")
            if self.rename_comp_to_product_name and name_change:
                api.get_stub().rename_item(created_inst.data["members"][0],
                                           name_change.new_value)

    def remove_instances(self, instances):
        """Removes metadata and renames to original comp name if available."""
        for instance in instances:
            self._remove_instance_from_context(instance)
            self.host.remove_instance(instance)

            if self.rename_comp_to_product_name:
                comp_id = instance.data["members"][0]
                comp = api.get_stub().get_item(comp_id)
                orig_comp_name = instance.data.get("orig_comp_name")
                if comp:
                    if orig_comp_name:
                        new_comp_name = orig_comp_name
                    else:
                        new_comp_name = "dummyCompName"
                    api.get_stub().rename_item(comp_id,
                                               new_comp_name)

    def get_detail_description(self):
        return """Creator for Render instances

        Main publishable item in AfterEffects will be of `render` product type.
        Result of this item (instance) is picture sequence or video that could
        be a final delivery product or loaded and used in another DCCs.

        Select single composition and create instance of 'render' product type
        or turn off 'Use selection' to create instance for all compositions.

        'Use composition name in product' allows to explicitly add composition
        name into created product name.

        Position of composition name could be set in
        `project_settings/global/tools/creator/product_name_profiles` with
        some form of '{composition}' placeholder.

        Composition name will be used implicitly if multiple composition should
        be handled at same time.

        If {composition} placeholder is not us 'product_name_profiles'
        composition name will be capitalized and set at the end of
        product name if necessary.

        If composition name should be used, it will be cleaned up of characters
        that would cause an issue in published file names.
        """

    def get_dynamic_data(
        self,
        project_name,
        folder_entity,
        task_entity,
        variant,
        host_name,
        instance=None,
        project_entity=None,
        product_type=None,
    ):
        dynamic_data = {}
        if instance is not None:
            composition_name = instance.get("composition_name")
            if composition_name:
                dynamic_data["composition"] = composition_name
        else:
            dynamic_data["composition"] = "{composition}"

        return dynamic_data

    def _handle_legacy(self, instance_data):
        """Converts old instances to new format."""
        if not instance_data.get("members"):
            instance_data["members"] = [instance_data.get("uuid")]

        if instance_data.get("uuid"):
            # uuid not needed, replaced with unique instance_id
            api.get_stub().remove_instance(instance_data.get("uuid"))
            instance_data.pop("uuid")

        if not instance_data.get("task"):
            instance_data["task"] = self.create_context.get_current_task_name()

        if not instance_data.get("creator_attributes"):
            is_old_farm = instance_data.get("family") != "renderLocal"
            instance_data["creator_attributes"] = {"farm": is_old_farm}
            instance_data["productBaseType"] = self.product_base_type
            instance_data["productType"] = self.product_base_type

        if instance_data["creator_attributes"].get("mark_for_review") is None:
            instance_data["creator_attributes"]["mark_for_review"] = True

        farm = instance_data["creator_attributes"].pop("farm", None)
        if farm is not None:
            if farm:
                instance_data["creator_attributes"]["render_target"] = "farm"
            else:
                instance_data["creator_attributes"]["render_target"] = "local"

        return instance_data
