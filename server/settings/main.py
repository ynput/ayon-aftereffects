from ayon_server.settings import BaseSettingsModel, SettingsField

from .imageio import AfterEffectsImageIOModel
from .creator_plugins import AfterEffectsCreatorPlugins
from .publish_plugins import (
    AfterEffectsPublishPlugins,
    AE_PUBLISH_PLUGINS_DEFAULTS,
)
from .workfile_builder import WorkfileBuilderPlugin
from .templated_workfile_build import TemplatedWorkfileBuildModel
from .scripts import Scripts


class AfterEffectsSettings(BaseSettingsModel):
    """AfterEffects Project Settings."""

    auto_install_extension: bool = SettingsField(
        False,
        title="Install AYON Extension",
        description="Triggers pre-launch hook which installs extension."
    )
    auto_open_panel: bool = SettingsField(
        True,
        title="Auto-open AYON Panel",
        description=(
            "Automatically open the AYON panel on every After Effects launch."
        ),
    )

    imageio: AfterEffectsImageIOModel = SettingsField(
        default_factory=AfterEffectsImageIOModel, title="OCIO config"
    )
    create: AfterEffectsCreatorPlugins = SettingsField(
        default_factory=AfterEffectsCreatorPlugins, title="Creator plugins"
    )
    publish: AfterEffectsPublishPlugins = SettingsField(
        default_factory=AfterEffectsPublishPlugins, title="Publish plugins"
    )
    workfile_builder: WorkfileBuilderPlugin = SettingsField(
        default_factory=WorkfileBuilderPlugin, title="Workfile Builder"
    )
    templated_workfile_build: TemplatedWorkfileBuildModel = SettingsField(
        default_factory=TemplatedWorkfileBuildModel,
        title="Templated Workfile Build Settings",
    )
    scripts: Scripts = SettingsField(
        default_factory=Scripts,
        title="Scripts",
    )


DEFAULT_AFTEREFFECTS_SETTING = {
    "auto_install_extension": True,
    "auto_open_panel": True,
    "create": {
        "RenderCreator": {
            "mark_for_review": True,
            "default_variants": ["Main"],
            "force_setting_values": True,
            "rename_comp_to_product_name": True,
        }
    },
    "publish": AE_PUBLISH_PLUGINS_DEFAULTS,
    "workfile_builder": {
        "create_first_version": False,
        "custom_templates": [],
    },
    "templated_workfile_build": {"profiles": []},
    "scripts": {"configs": []},
}
