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
    use_comp_name_as_variant: bool = SettingsField(
        False,
        title="Use composition name as variant",
        description=(
            "Derive the variant from the composition name instead of "
            "the artist-entered value. Each instance uses its "
            "composition name as the variant, so the product name "
            "becomes e.g. 'renderSH010_comp'. Replaces the 'Use "
            "composition name in product' option in the Publisher."
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
