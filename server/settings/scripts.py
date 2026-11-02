from ayon_server.settings import (
    BaseSettingsModel,
    SettingsField,
    normalize_name,
    task_types_enum,
)
from pydantic import validator


class ScriptConfigModel(BaseSettingsModel):
    """Configuration for a single After Effects script."""

    name: str = SettingsField(default="", title="Script name")
    auto: bool = SettingsField(
        True,
        description="Auto/Manual toggle.",
    )
    path: str = SettingsField("", title="Path to script")
    task_types: list[str] = SettingsField(
        default_factory=list,
        title="Task types",
        description="Leave empty to use the script in every task type.",
        enum_resolver=task_types_enum,
    )
    task_names: list[str] = SettingsField(
        default_factory=list,
        title="Task names",
        description=(
            "Leave empty to use the script in every task. Accepts regex."
        ),
    )

    @validator("name")
    def normalize_value(cls, value: str) -> str:
        return normalize_name(value)


class Scripts(BaseSettingsModel):
    """Scripts to run at workfile open."""

    configs: list[ScriptConfigModel] = SettingsField(
        default_factory=list, title="Script list"
    )
