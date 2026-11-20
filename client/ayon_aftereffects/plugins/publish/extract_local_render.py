import os

from ayon_core.pipeline import publish
from ayon_core.pipeline.publish import PublishError

from ayon_aftereffects.api import get_stub


class ExtractLocalRender(publish.Extractor):
    """Render RenderQueue locally."""

    order = publish.Extractor.order - 0.47
    label = "Extract Local Render"
    hosts = ["aftereffects"]
    families = ["render.local"]

    def process(self, instance):
        stub = get_stub()
        staging_dir = instance.data["stagingDir"]
        self.log.debug("staging_dir::{}".format(staging_dir))

        # pull file name collected value from Render Queue Output module
        render_queue_file_paths = (
            instance.data.get("render_queue_file_paths") or []
        )

        comp_id = instance.data["comp_id"]
        comp_name = instance.data.get("comp_name", comp_id)

        stub.render(staging_dir, comp_id)

        existing_files = sorted(os.listdir(staging_dir))

        representations = []
        for file_name in render_queue_file_paths:
            _, extension = os.path.splitext(os.path.basename(file_name))
            ext = extension[1:]
            files = [
                found_file_name
                for found_file_name in existing_files
                if found_file_name.endswith(ext)
            ]
            if not files:
                found_overview = (
                    ", ".join(existing_files[:5]) or "no files at all"
                )
                if len(existing_files) > 5:
                    found_overview += ", ..."
                raise PublishError(
                    "Render finished, but no '*.{}' output was found in "
                    "'{}'. Found {} file(s): {}. Expected an output named "
                    "like '{}'. Check the Output Module of '{}' in the "
                    "Render Queue.".format(
                        ext,
                        staging_dir,
                        len(existing_files),
                        found_overview,
                        os.path.basename(file_name),
                        comp_name,
                    )
                )

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
                "stagingDir": staging_dir
            }
            first_repre = not representations
            if instance.data["review"] and first_repre:
                repre_data["tags"] = ["review"]
                # TODO return back when Extract from source same as regular
                # thumbnail_path = os.path.join(staging_dir, files[0])
                # instance.data["thumbnailSource"] = thumbnail_path

            representations.append(repre_data)

        instance.data["representations"] = representations
