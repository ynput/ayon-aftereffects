from ayon_server.settings import (
    BaseSettingsModel,
    SettingsField,
    folder_types_enum,
    task_types_enum,
)

from .output_module import OutputPresetModel


class ProductTypeItemModel(BaseSettingsModel):
    _layout = "compact"
    product_type: str = SettingsField(
        title="Product type",
        description="Product type name",
    )
    label: str = SettingsField(
        title="Label",
        description="Label to display in UI for the product type",
    )


class OutputModuleProfileModel(BaseSettingsModel):
    """Render Queue Output Module settings for matching folders and tasks."""

    _layout = "expanded"
    name: str = SettingsField(
        "",
        title="Profile name",
        description="Used in the log message when the profile is applied.",
    )
    folder_types: list[str] = SettingsField(
        default_factory=list,
        title="Folder types",
        enum_resolver=folder_types_enum,
        description=(
            "Apply the profile to these folder types. Empty matches any "
            "folder type."
        ),
    )
    task_types: list[str] = SettingsField(
        default_factory=list,
        title="Task types",
        enum_resolver=task_types_enum,
        description=(
            "Apply the profile to these task types. Empty matches any task "
            "type, including instances created without a task."
        ),
    )
    output: OutputPresetModel = SettingsField(
        default_factory=OutputPresetModel,
        title="Output Module",
        description=(
            "Template, file name pattern and frame padding applied to the "
            "Render Queue item when the instance is created."
        ),
    )


class CreateRenderPlugin(BaseSettingsModel):
    mark_for_review: bool = SettingsField(True, title="Review")
    default_variants: list[str] = SettingsField(
        default_factory=list,
        title="Default Variants"
    )
    force_setting_values: bool = SettingsField(
        True, title="Force resolution and duration values from Task")
    rename_comp_to_product_name: bool = SettingsField(
        True,
        title="Rename composition to product name",
        description=(
            "Rename composition to product name when creating render instance "
            "or when updating product name, e.g. on variant change."
        )
    )
    sync_with_render_queue: bool = SettingsField(
        False,
        title="Sync created products with render queue",
        description=(
            "Mirror the After Effects render queue into the created products "
            "list. Compositions queued directly in After Effects get a render "
            "instance with the default variant, and instances "
            "whose composition left the queue are removed. Sync runs when the "
            "publisher is opened or refreshed."
        )
    )
    product_type_items: list[ProductTypeItemModel] = SettingsField(
        default_factory=list,
        title="Product type items",
        description=(
            "Optional list of product types that this plugin can create."
        )
    )
    output_module_profiles: list[OutputModuleProfileModel] = SettingsField(
        default_factory=list,
        title="Output Module profiles",
        description=(
            "Default Render Queue Output Module settings per folder and task "
            "type. The best matching profile is applied when a render "
            "instance is created; a more specific profile wins over one with "
            "empty filters. Without a match the Output Module only gets the "
            "file name the Validate Output Module presets expect."
        ),
    )


class AfterEffectsCreatorPlugins(BaseSettingsModel):
    RenderCreator: CreateRenderPlugin = SettingsField(
        title="Create Render",
        default_factory=CreateRenderPlugin,
    )
