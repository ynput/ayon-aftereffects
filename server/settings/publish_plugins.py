from ayon_server.settings import BaseSettingsModel, SettingsField
from pydantic import validator


class CollectReviewPluginModel(BaseSettingsModel):
    enabled: bool = SettingsField(True, title="Enabled")


class ValidateSceneSettingsModel(BaseSettingsModel):
    """Validate naming of products and layers"""

    # _isGroup = True
    enabled: bool = SettingsField(True, title="Enabled")
    optional: bool = SettingsField(False, title="Optional")
    active: bool = SettingsField(True, title="Active")
    skip_resolution_check: list[str] = SettingsField(
        default_factory=list,
        title="Skip Resolution Check for Tasks",
    )
    skip_timelines_check: list[str] = SettingsField(
        default_factory=list,
        title="Skip Timeline Check for Tasks",
    )


class ValidateFootageLocationModel(BaseSettingsModel):
    """Validate footage is stored inside the project roots"""

    enabled: bool = SettingsField(False, title="Enabled")
    optional: bool = SettingsField(True, title="Optional")
    active: bool = SettingsField(True, title="Active")


class OutputPresetModel(BaseSettingsModel):
    """Allowed Render Queue Output Module preset."""

    _layout = "compact"
    label: str = SettingsField(
        "",
        title="Label",
        description="Name shown in validation errors.",
    )
    template: str = SettingsField(
        "",
        title="Output Module template",
        description=(
            "Output Module template name as shown in the Render Queue, "
            "e.g. 'H.264 - Match Render Settings'. Matched first."
        ),
    )
    format: str = SettingsField(
        "",
        title="Format",
        description=(
            "Format shown in the Output Module, e.g. 'H.264' or "
            "'OpenEXR'. Used when the template name does not match."
        ),
    )
    codec: str = SettingsField(
        "",
        title="Codec",
        description=(
            "Codec shown in the Output Module, e.g. "
            "'Apple ProRes 422 HQ'. Empty means any codec."
        ),
    )
    name_pattern: str = SettingsField(
        "{product_name}",
        title="File name pattern",
        description=(
            "Expected output file name. '{product_name}' is replaced with "
            "the product name. Use '[#####]' for frame sequences."
        ),
    )
    extensions: list[str] = SettingsField(
        default_factory=list,
        title="Extensions",
        description="Allowed output extensions without the dot.",
    )
    sequence: bool = SettingsField(
        False,
        title="Frame sequence",
        description=(
            "True when the format writes numbered frames and the file "
            "name needs a '[#####]' token."
        ),
    )
    padding: int = SettingsField(
        5,
        title="Frame padding",
        description="Number of digits in the '[#####]' token.",
    )

    @validator("extensions")
    def normalize_extensions(cls, value: list[str]) -> list[str]:
        """Strip dots and lowercase the configured extensions."""
        return [
            ext.strip().lstrip(".").lower()
            for ext in value
            if ext.strip()
        ]


class ValidateOutputModuleModel(BaseSettingsModel):
    """Validate format, codec and file name of the Render Queue item"""

    enabled: bool = SettingsField(
        False,
        title="Enabled",
        description=(
            "Disabled by default: enable it per project once the presets "
            "match the studio output templates."
        ),
    )
    optional: bool = SettingsField(True, title="Optional")
    active: bool = SettingsField(True, title="Active")
    check_format: bool = SettingsField(
        True,
        title="Check format and codec",
        description=(
            "Read the Output Module settings from After Effects. Requires "
            "the matching AYON extension; without it only the file name "
            "and the extension are checked."
        ),
    )
    presets: list[OutputPresetModel] = SettingsField(
        default_factory=list,
        title="Allowed presets",
    )


class AfterEffectsPublishPlugins(BaseSettingsModel):
    CollectReview: CollectReviewPluginModel = SettingsField(
        default_factory=CollectReviewPluginModel,
        title="Collect Review",
    )
    ValidateSceneSettings: ValidateSceneSettingsModel = SettingsField(
        default_factory=ValidateSceneSettingsModel,
        title="Validate Scene Settings",
    )
    ValidateFootageLocation: ValidateFootageLocationModel = SettingsField(
        default_factory=ValidateFootageLocationModel,
        title="Validate Footage Location",
    )
    ValidateOutputModule: ValidateOutputModuleModel = SettingsField(
        default_factory=ValidateOutputModuleModel,
        title="Validate Output Module",
    )


AE_PUBLISH_PLUGINS_DEFAULTS = {
    "CollectReview": {
        "enabled": True
    },
    "ValidateSceneSettings": {
        "enabled": True,
        "optional": True,
        "active": True,
        "skip_resolution_check": [
            ".*"
        ],
        "skip_timelines_check": [
            ".*"
        ]
    },
    "ValidateOutputModule": {
        "enabled": False,
        "optional": True,
        "active": True,
        "check_format": True,
        "presets": [
            {
                "label": "H.264 MP4",
                "template": "",
                "format": "H.264",
                "codec": "",
                "name_pattern": "{product_name}",
                "extensions": ["mp4"],
                "sequence": False,
                "padding": 5,
            },
            {
                "label": "QuickTime MOV",
                "template": "",
                "format": "QuickTime",
                "codec": "",
                "name_pattern": "{product_name}",
                "extensions": ["mov"],
                "sequence": False,
                "padding": 5,
            },
            {
                "label": "OpenEXR Sequence",
                "template": "",
                "format": "OpenEXR",
                "codec": "",
                "name_pattern": "{product_name}_[#####]",
                "extensions": ["exr"],
                "sequence": True,
                "padding": 5,
            },
            {
                "label": "PNG Sequence",
                "template": "",
                "format": "PNG Sequence",
                "codec": "",
                "name_pattern": "{product_name}_[#####]",
                "extensions": ["png"],
                "sequence": True,
                "padding": 5,
            },
        ],
    },
}
