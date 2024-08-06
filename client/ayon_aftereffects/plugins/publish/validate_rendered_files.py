# -*- coding: utf-8 -*-
"""Validate collected and expected files
Requires:
"""
import os.path
import clique

import pyblish.api

from ayon_core.pipeline.publish import PublishValidationError, RepairAction


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
    actions = [RepairAction]
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

        collected_files = self._get_collected_files(instance)

        # prepared for multiple outputs per render queue, now it will be only
        # single folder
        checked_folders = self._get_checked_folders(instance)

        missing = expected_files - collected_files
        if missing:
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

        collections, remainders = (
            self._get_collections_and_remainders(collected_files))

        if remainders:
            raise PublishValidationError(
                f"Folders {checked_folders} contain out of sequence files "
                f"{remainders}. <br/><br/>"
                f"This will cause issue when integrating.<br/><br/>"
                "Please remove these files manually or use `Repair` action to "
                "delete them."
            )

        if len(collections) > 1:
            raise PublishValidationError(
                f"Folders {checked_folders} contain multiple collections "
                f"{collections}. <br/><br/>"
                f"This will cause issue during extraction of review.<br/><br/>"
                "Please remove one of the collections manually!"
            )

    @classmethod
    def _get_checked_folders(cls, instance):
        """Parses physical output dirs from Render Queue Output Module(s)"""
        checked_folders = {os.path.dirname(file_path)
                           for file_path in instance.data["expectedFiles"]}
        return checked_folders

    @classmethod
    def _get_collections_and_remainders(cls, collected_files):
        """Looks for similarly named files outside of collected sequence.

        Could cause an issue in ExtractReview or Integrate.
        """
        return clique.assemble(collected_files)

    @classmethod
    def _get_collected_files(cls, instance):
        """Returns all physically found frames for output dir(s)"""
        collected_files = []
        for repre in instance.data["representations"]:
            repre_files = repre["files"]
            if isinstance(repre_files, str):
                repre_files = [repre_files]

            collected_files.extend(repre_files)
        collected_files = set(collected_files)
        return collected_files

    @classmethod
    def repair(cls, instance):
        """Deletes out of sequence files from output dir(s)."""
        collected_files = cls._get_collected_files(instance)
        checked_folders = cls._get_checked_folders(instance)

        remainders = cls._get_collections_and_remainders(collected_files)

        for remainder_file_name in remainders:
            for checked_folder in checked_folders:
                file_path = os.path.join(checked_folder, remainder_file_name)
                if os.path.exists(file_path):
                    cls.log.warning(f"Removing {file_path}")
                    os.remove(file_path)
                    continue
