from ayon_server.settings import BaseSettingsModel, SettingsField


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


class AfterEffectsCreatorPlugins(BaseSettingsModel):
    RenderCreator: CreateRenderPlugin = SettingsField(
        title="Create Render",
        default_factory=CreateRenderPlugin,
    )
