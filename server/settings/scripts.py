from ayon_server.settings import (
    BaseSettingsModel,
    SettingsField,
    normalize_name,
)
from pydantic import validator


class ScriptConfigModel(BaseSettingsModel):
    """Configuration for a single After Effects script."""

    name: str = SettingsField(default="", title="Script name.")
    auto: bool = SettingsField(
        True,
        description="Auto/Manual toggle.",
    )
    path: str = SettingsField("", title="Path to script.")

    @validator("name")
    def normalize_value(cls, value: str) -> str:
        return normalize_name(value)


class Scripts(BaseSettingsModel):
    """Scripts to run at workfile open."""

    configs: list[ScriptConfigModel] = SettingsField(
        default_factory=list, title="Script config"
    )
