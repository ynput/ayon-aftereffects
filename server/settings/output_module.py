from ayon_server.settings import BaseSettingsModel, SettingsField
from pydantic import validator


class OutputPresetModel(BaseSettingsModel):
    """Render Queue Output Module settings.

    Used by the Validate Output Module plugin as the allowed set, and by
    the Create Render profiles as the settings to apply on creation, so
    both share one description of format, file name and frame padding.
    """

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
