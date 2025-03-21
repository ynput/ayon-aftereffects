from ayon_server.settings import (
    BaseSettingsModel,
    SettingsField,
    MultiplatformPathModel,
)


class CustomBuilderTemplate(BaseSettingsModel):
    task_types: list[str] = SettingsField(
        default_factory=list,
        title="Task types",
    )
    path: MultiplatformPathModel = SettingsField(
        default_factory=MultiplatformPathModel
    )


class WorkfileBuilderPlugin(BaseSettingsModel):
    """Simpler workfile template based on Task type"""
    _title = "Workfile Builder"
    create_first_version: bool = SettingsField(
        False,
        title="Create first workfile",
        description="Save first workfile with the built template on "
                    "first run if no existing workfile exists."
    )

    custom_templates: list[CustomBuilderTemplate] = SettingsField(
        default_factory=list
    )
