from ayon_server.settings import BaseSettingsModel, SettingsField


class HookOptionalModel(BaseSettingsModel):
    enabled: bool = SettingsField(False, title="Enabled")


class HooksModel(BaseSettingsModel):
    InstallAyonExtensionToAfterEffects: HookOptionalModel = SettingsField(
        default_factory=HookOptionalModel,
        title="Install AYON Extension",
    )


DEFAULT_HOOK_VALUES = {
    "hooks": {
        "InstallAyonExtensionToAfterEffects": {
            "enabled": False,
        }
    }
}
