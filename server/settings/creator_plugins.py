from ayon_server.settings import BaseSettingsModel, SettingsField


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
            "instance whose variant is the composition name, and instances "
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


class AfterEffectsCreatorPlugins(BaseSettingsModel):
    RenderCreator: CreateRenderPlugin = SettingsField(
        title="Create Render",
        default_factory=CreateRenderPlugin,
    )
