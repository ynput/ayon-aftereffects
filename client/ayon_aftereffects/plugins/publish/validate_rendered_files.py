# -*- coding: utf-8 -*-
"""Validate collected and expected files
Requires:
"""
import os.path

import pyblish.api

from ayon_core.pipeline import PublishValidationError


class ValidateRenderedFiles(pyblish.api.InstancePlugin):
    """Validates if locally pre rendered files are all as expected.

    Artists might render manually with AE`Render` button and want only to
    publish these files after visually checking them.
    This validator checks that there exists files with same names as were
    expected to be rendered.

    Applies only on instances created with 'Use existing frames'.
    """

    order = pyblish.api.ValidatorOrder
    label = "Validate Rendered Files"
    families = ["render"]
    hosts = ["aftereffects"]
    optional = True

    def process(self, instance):
        """Plugin entry point."""
        use_existing_frames = (
            instance.data["creator_attributes"]
                         ["render_target"] == "frames"
        )

        if not use_existing_frames:
            self.log.debug("Not using existing frames, skipping")
            return

        expected_files = {os.path.basename(file_path)
                          for file_path in instance.data["expectedFiles"]}
        collected_files = []
        for repre in instance.data["representations"]:
            repre_files = repre["files"]
            if isinstance(repre_files, str):
                repre_files = [repre_files]

            collected_files.extend(repre_files)

        collected_files = set(collected_files)

        missing = expected_files - collected_files
        if missing:
            checked_folders = {os.path.dirname(file_path)
                               for file_path in instance.data["expectedFiles"]}
            raise PublishValidationError(
                "<b>Checked:</b> {}<br/><br/>"
                "<b>Missing expected files:</b> {}<br/><br/>"
                "Expected files: {}<br/>"
                "Existing files: {}".format(
                    sorted(checked_folders),
                    sorted(missing),
                    sorted(expected_files),
                    sorted(collected_files)
                )
            )
        else:
            self.log.debug("Matching expected and found files")
