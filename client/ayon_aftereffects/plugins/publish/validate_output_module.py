"""Validate the Render Queue Output Module of render instances.

The Output Module of a Render Queue item decides the format, the codec
and the output file name. AYON only rewrites the output folder, so a
wrong format or a file name that does not match the product name is
discovered too late - after the render has finished.

Requires the AYON extension to provide `getOutputModuleInfo`. With an
older extension only the file name and the extension are validated.
"""

from __future__ import annotations

import pyblish.api

from ayon_core.pipeline import (
    OptionalPyblishPluginMixin,
    PublishXmlValidationError,
)

from ayon_aftereffects.api import get_stub
from ayon_aftereffects.api.output_module import validate_output_modules
from ayon_aftereffects.api.ws_stub import ConnectionNotEstablishedYet

#: Maps a problem key to the matching id in `validate_output_module.xml`.
ERROR_KEYS = {
    "missing": "main",
    "missing_name": "main",
    "name": "name",
    "extension": "extension",
    "sequence": "sequence",
    "padding": "sequence",
    "single_file": "sequence",
    "not_allowed": "not_allowed",
    "format": "not_allowed",
    "codec": "not_allowed",
}


class ValidateOutputModule(
    OptionalPyblishPluginMixin, pyblish.api.InstancePlugin
):
    """Check format, codec and file name of the Render Queue item.

    Each Output Module of the instance composition is compared with the
    allowed presets from project settings: format, codec, extension, file
    name and the `[#####]` frame token.

    The plugin is disabled by default. Enable it per project once the
    presets match the studio output templates, otherwise existing
    productions with different naming would fail validation.
    """

    order = pyblish.api.ValidatorOrder + 0.05
    label = "Validate Output Module"
    families = ["render"]
    hosts = ["aftereffects"]
    settings_category = "aftereffects"

    enabled = False
    optional = True
    active = True

    check_format = True
    presets = []

    def process(self, instance):
        """Check all Output Modules of the instance composition.

        Args:
            instance (pyblish.api.Instance): Publish instance.

        Raises:
            PublishXmlValidationError: When an Output Module does not
                match one of the allowed presets.
        """
        if not self.is_active(instance.data):
            return

        problems = validate_output_modules(
            instance.data.get("productName", ""),
            self._collect_modules(instance),
            self.presets,
        )
        if not problems:
            return

        messages = [problem.message for problem in problems]
        first = problems[0]
        raise PublishXmlValidationError(
            self,
            "\n".join(messages),
            key=ERROR_KEYS.get(first.key, "main"),
            formatting_data={
                "comp_name": instance.data.get("comp_name", ""),
                "product_name": instance.data.get("productName", ""),
                "problems": "<br/>".join(messages),
                "allowed": first.fields.get("allowed", ""),
                "actual": first.fields.get("actual", ""),
                "expected": first.fields.get("expected", ""),
                "index": first.fields.get("index", 1),
            },
        )

    def _collect_modules(self, instance):
        """Return Output Module records for the instance composition.

        Falls back to the file names already collected by
        `CollectAERender` when the extension cannot report the full
        Output Module settings, so name checks still run.

        Args:
            instance (pyblish.api.Instance): Publish instance.

        Returns:
            list[dict]: One record per Output Module.
        """
        file_paths = instance.data.get("render_queue_file_paths") or []
        fallback = [
            {"index": index + 1, "file_name": path}
            for index, path in enumerate(file_paths)
        ]

        comp_id = instance.data.get("comp_id")
        if not self.check_format or comp_id is None:
            return fallback

        try:
            modules = get_stub().get_output_module_info(comp_id)
        except ConnectionNotEstablishedYet:
            self.log.warning(
                "Not connected to After Effects, checking output file "
                "names only."
            )
            return fallback
        except Exception:
            self.log.warning(
                "Cannot read Output Module settings, checking output "
                "file names only. Is the AYON extension up to date?",
                exc_info=True,
            )
            return fallback

        return modules or fallback
