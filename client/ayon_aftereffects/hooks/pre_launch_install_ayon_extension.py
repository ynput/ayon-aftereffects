import os
import platform
from zipfile import ZipFile
import xml.etree.ElementTree as ET
from shutil import rmtree


from ayon_aftereffects import AFTEREFFECTS_ADDON_ROOT
from ayon_applications import PreLaunchHook, LaunchTypes


class InstallAyonExtensionToAfterEffect(PreLaunchHook):
    """
    Automatically 'installs' the AYON AfterEffects extension.

    Checks if AE already has the extension in the relevant folder,
    will try to create that folder and unzip the extension if not.
    Will compare versions if folder does exist, replacing if mismatched.
    """

    app_groups = {"aftereffects"}

    order = 1
    launch_types = {LaunchTypes.local}

    def execute(self):
        try:
            settings = self.data["project_settings"]["aftereffects"]
            if not settings["hooks"]["InstallAyonExtensionToAfterEffects"][
                "enabled"
            ]:
                return
            self.inner_execute()

        except Exception:
            self.log.warning(
                "Processing of {} crashed.".format(self.__class__.__name__),
                exc_info=True,
            )

    def inner_execute(self):
        self.log.info("Installing AYON After Effects extension.")

        # Windows only for now.
        if not platform.system().lower() == "windows":
            self.log.info("Non Windows platform. Cancelling..")
            return

        target_path = os.path.join(
            os.environ["appdata"], r"Adobe\CEP\extensions\io.ynput.AE.panel"
        )

        extension_path = os.path.join(
            AFTEREFFECTS_ADDON_ROOT,
            "api",
            "extension.zxp",
        )

        # Extension already installed, compare the versions
        if os.path.exists(target_path):
            self.log.info(
                f"The extension already exists at: {target_path}. "
                f"Comparing versions.."
            )
            if not self._compare_extension_versions(
                target_path, extension_path
            ):
                return

        try:
            self.log.debug(f"Creating directory: {target_path}")
            os.makedirs(target_path, exist_ok=True)

            with ZipFile(extension_path, "r") as archive:
                archive.extractall(path=target_path)
            self.log.info("Successfully installed AYON extension")

        except OSError as error:
            self.log.warning(f"OS error has occured: {error}")

        except PermissionError as error:
            self.log.warning(f"Permissions error has occured: {error}")

        except Exception as error:
            self.log.warning(f"An unexpected error occured: {error}")

    def _compare_extension_versions(
        self, target_path: str, extension_path: str
    ) -> bool:
        try:
            # opens the existing extension manifest to get the Version attr
            with open(f"{target_path}/CSXS/manifest.xml", "rb") as xml_file:
                installed_version = (
                    ET.parse(xml_file)
                    .getroot()
                    .attrib.get("ExtensionBundleVersion")
                )
            self.log.debug(
                f"Current extension version found: {installed_version}"
            )

            if not installed_version:
                self.log.warning(
                    "Unable to resolve the currently installed extension "
                    "version. Cancelling.."
                )
                return False

            # opens the .zxp manifest to get the Version attribute.
            with ZipFile(extension_path, "r") as archive:
                xml_file = archive.open("CSXS/manifest.xml")
                new_version = (
                    ET.parse(xml_file)
                    .getroot()
                    .attrib.get("ExtensionBundleVersion")
                )
                if not new_version:
                    self.log.warning(
                        "Unable to resolve the new extension version. "
                        "Cancelling.."
                    )
                self.log.debug(f"New extension version found: {new_version}")

                # compare the two versions, a simple == is enough since
                # we don't care if the version increments or decrements
                # if they match nothing happens.
                if installed_version == new_version:
                    self.log.info("Versions matched. Cancelling..")
                    return False

                # remove the existing addon
                self.log.info(
                    "Version mismatch found. Removing old extensions.."
                )
                rmtree(target_path)
                return True

        except PermissionError as error:
            self.log.warning(
                "Permissions error has occurred while comparing "
                f"versions: {error}"
            )
            return False

        except OSError as error:
            self.log.warning(
                f"OS error has occured while comparing versions: {error}"
            )
            return False

        except Exception as error:
            self.log.warning(
                f"An unexpected error occured when comparing version: {error}"
            )
            return False
