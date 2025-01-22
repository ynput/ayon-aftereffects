from ayon_server.settings import BaseSettingsMode, SettingsField


class HookOptionalModel(BaseSettingsMode):
    enabled: bool = SettingsField(False, title="Enabled")


class HooksModel(BaseSettingsMode):
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
