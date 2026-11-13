from ayon_server.settings import (
    BaseSettingsModel,
    task_types_enum,
    folder_types_enum,
    SettingsField,
)


class TemplatedWorkfileProfileModel(BaseSettingsModel):
    task_types: list[str] = SettingsField(
        default_factory=list,
        title="Task types",
        enum_resolver=task_types_enum
    )
    task_names: list[str] = SettingsField(
        default_factory=list,
        title="Task names"
    )
    folder_types: list[str] = SettingsField(
        default_factory=list,
        title="Folder Types",
        enum_resolver=folder_types_enum
    )
    folder_paths: list[str] = SettingsField(
        default_factory=list,
        title="Folder paths"
    )
    path: str = SettingsField(
        title="Path to template"
    )
    keep_placeholder: bool = SettingsField(
        False,
        title="Keep placeholders")
    create_first_version: bool = SettingsField(
        True,
        title="Create first version"
    )


class TemplatedWorkfileBuildModel(BaseSettingsModel):
    """Workfile template builder with dynamic items via Placeholders"""
    profiles: list[TemplatedWorkfileProfileModel] = SettingsField(
        default_factory=list
    )
