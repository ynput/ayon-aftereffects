import os
import platform
import collections
import re
import urllib.parse

import pyblish.api

from ayon_core.pipeline.publish import KnownPublishError


class CollectExistingFrames(pyblish.api.InstancePlugin):
    """Collect existing files rendered via Render in Render Queues.

    These files might exist there from test render, triggered manually by
    artist, now its only about collecting and publishing them to save time.

    This is prepared for multiple output modules in Render Queue, which is not
    currently allowed, but might be in the future.
    It is expected if there are multiple output modules per Render Queue,
    they must have different extension!

    Prepares representations to allow integration later.
    """

    order = pyblish.api.CollectorOrder + 0.150
    label = "Collect Exiting Frames"
    hosts = ["aftereffects"]
    families = ["render"]

    settings_category = "aftereffects"

    def process(self, instance):
        use_existing_frames = instance.data["creator_attributes"]["frames"]

        if not use_existing_frames:
            return

        render_queue_file_paths = instance.data["render_queue_file_paths"]
        files_by_ext = collections.defaultdict(list)
        folders_by_ext = collections.defaultdict(list)
        expected_files = []
        for render_queue_file_path in render_queue_file_paths:
            render_queue_file_path = (
                self._normalize_path(render_queue_file_path))

            render_queue_folder = os.path.dirname(render_queue_file_path)
            if not os.path.exists(render_queue_folder):
                self.log.warning(f"{render_queue_folder} doesn't exist.")
                continue

            _, render_queue_extension = (
                os.path.splitext(os.path.basename(render_queue_file_path))
            )
            render_queue_extension = render_queue_extension.lstrip(".")

            self._add_expected_files(
                instance, render_queue_file_path, expected_files)

            if render_queue_extension in folders_by_ext:
                raise KnownPublishError(
                    "Multiple render queues detected "
                    "with same extension. \n"
                     "Please change one the extensions!"
                )

            folders_by_ext[render_queue_extension] = render_queue_folder

            for file_name in os.listdir(render_queue_folder):
                if not file_name.endswith(render_queue_extension):
                    continue
                files_by_ext[render_queue_extension].append(file_name)

        if not files_by_ext:
            self.log.info("no files")
            return

        representations = []
        for ext, files in files_by_ext.items():
            # single file cannot be wrapped in array
            resulting_files = files
            if len(files) == 1:
                resulting_files = files[0]

            repre_data = {
                "frameStart": instance.data["frameStart"],
                "frameEnd": instance.data["frameEnd"],
                "name": ext,
                "ext": ext,
                "files": resulting_files,
                "stagingDir": folders_by_ext[ext]
            }
            first_repre = not representations
            if instance.data["review"] and first_repre:
                repre_data["tags"] = ["review"]
                # TODO return back when Extract from source same as regular
                # thumbnail_path = os.path.join(staging_dir, files[0])
                # instance.data["thumbnailSource"] = thumbnail_path

            representations.append(repre_data)

        instance.data["representations"] = representations
        instance.data["expectedFiles"] = expected_files

    def _add_expected_files(self, instance, render_queue_path, expected_files):
        """Calculate expected files from file patterns in Render Queue"""
        render_queue_path = urllib.parse.unquote(render_queue_path)
        frames_pattern = re.search("\[#*\]", render_queue_path)

        if not frames_pattern:
            expected_files.append(render_queue_path)
            return

        frames_pattern = frames_pattern.group()

        frame_start = instance.data["frameStart"]
        frame_end = instance.data["frameEnd"]

        frames_length = frames_pattern.count("#")
        for frame in range(frame_start, frame_end + 1):
            frame_str = "%0*d" % (frames_length, int(frame))
            render_queue_path = render_queue_path.replace(
                frames_pattern, frame_str)
            expected_files.append(render_queue_path)


    def _normalize_path(self, path):
        """AE might return path like '/c/Users/...', convert to proper path"""
        current_platform = platform.system().lower()
        if current_platform == "windows" and path.startswith("/"):
            path = path.lstrip("/")
            first_slash_index = path.find("/")
            path = f"{path[0:first_slash_index]}:{path[first_slash_index:]}"

        return path
