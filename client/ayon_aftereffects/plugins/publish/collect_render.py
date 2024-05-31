import os
import tempfile

import attr
import pyblish.api

from ayon_core.pipeline import publish
from ayon_core.pipeline.publish import RenderInstance

from ayon_aftereffects.api import get_stub

@attr.s
class AERenderInstance(RenderInstance):
    # extend generic, composition name is needed
    comp_name = attr.ib(default=None)
    comp_id = attr.ib(default=None)
    fps = attr.ib(default=None)
    projectEntity = attr.ib(default=None)
    stagingDir = attr.ib(default=None)
    app_version = attr.ib(default=None)
    publish_attributes = attr.ib(default={})
    file_names = attr.ib(default=[])


class CollectAERender(publish.AbstractCollectRender):

    order = pyblish.api.CollectorOrder + 0.100
    label = "Collect After Effects Render Layers"
    hosts = ["aftereffects"]

    padding_width = 6
    rendered_extension = 'png'

    _stub = None

    @classmethod
    def get_stub(cls):
        if not cls._stub:
            cls._stub = get_stub()
        return cls._stub

    def get_instances(self, context):
        instances = []

        app_version = CollectAERender.get_stub().get_app_version()
        app_version = app_version[0:4]

        current_file = context.data["currentFile"]
        version = context.data["version"]

        project_entity = context.data["projectEntity"]

        compositions = CollectAERender.get_stub().get_items(True)
        compositions_by_id = {item.id: item for item in compositions}
        for inst in context:
            if not inst.data.get("active", True):
                continue

            product_type = inst.data["productType"]
            if product_type not in ["render", "renderLocal"]:  # legacy
                continue

            comp_id = int(inst.data["members"][0])

            comp_info = CollectAERender.get_stub().get_comp_properties(
                comp_id)

            if not comp_info:
                self.log.warning("Orphaned instance, deleting metadata")
                inst_id = inst.data.get("instance_id") or str(comp_id)
                CollectAERender.get_stub().remove_instance(inst_id)
                continue

            frame_start = comp_info.frameStart
            frame_end = round(comp_info.frameStart +
                              comp_info.framesDuration) - 1
            fps = comp_info.frameRate
            # TODO add resolution when supported by extension

            task_name = inst.data.get("task")

            render_q = CollectAERender.get_stub().get_render_info(comp_id)
            if not render_q:
                raise ValueError("No file extension set in Render Queue")
            render_item = render_q[0]

            product_type = "render"
            instance_families = inst.data.get("families", [])
            instance_families.append(product_type)
            product_name = inst.data["productName"]
            instance = AERenderInstance(
                productType=product_type,
                family=product_type,
                families=instance_families,
                version=version,
                time="",
                source=current_file,
                label="{} - {}".format(product_name, product_type),
                productName=product_name,
                folderPath=inst.data["folderPath"],
                task=task_name,
                attachTo=False,
                setMembers='',
                publish=True,
                name=product_name,
                resolutionWidth=render_item.width,
                resolutionHeight=render_item.height,
                pixelAspect=1,
                tileRendering=False,
                tilesX=0,
                tilesY=0,
                review="review" in instance_families,
                frameStart=frame_start,
                frameEnd=frame_end,
                frameStep=1,
                fps=fps,
                app_version=app_version,
                publish_attributes=inst.data.get("publish_attributes", {}),
                file_names=[item.file_name for item in render_q],

                # The source instance this render instance replaces
                source_instance=inst
            )

            comp = compositions_by_id.get(comp_id)
            if not comp:
                raise ValueError("There is no composition for item {}".
                                 format(comp_id))
            instance.outputDir = self._get_output_dir(instance)
            instance.comp_name = comp.name
            instance.comp_id = comp_id

            is_local = "renderLocal" in inst.data["family"]  # legacy
            if inst.data.get("creator_attributes"):
                is_local = not inst.data["creator_attributes"].get("farm")
            if is_local:
                # for local renders
                instance = self._update_for_local(instance, project_entity)
            else:
                fam = "render.farm"
                if fam not in instance.families:
                    instance.families.append(fam)
                instance.renderer = "aerender"
                instance.farm = True  # to skip integrate
                if "review" in instance.families:
                    # to skip ExtractReview locally
                    instance.families.remove("review")
                instance.deadline = inst.data.get("deadline")

            instances.append(instance)

        return instances

    def get_expected_files(self, render_instance):
        """
            Returns list of rendered files that should be created by
            Deadline. These are not published directly, they are source
            for later 'submit_publish_job'.

        Args:
            render_instance (RenderInstance): to pull anatomy and parts used
                in url

        Returns:
            (list) of absolute urls to rendered file
        """
        start = render_instance.frameStart
        end = render_instance.frameEnd

        base_dir = self._get_output_dir(render_instance)
        expected_files = []
        for file_name in render_instance.file_names:
            _, ext = os.path.splitext(os.path.basename(file_name))
            ext = ext.replace('.', '')
            version_str = "v{:03d}".format(render_instance.version)
            if "#" not in file_name:  # single frame (mov)W
                path = os.path.join(base_dir, "{}_{}_{}.{}".format(
                    render_instance.folderPath,
                    render_instance.productName,
                    version_str,
                    ext
                ))
                expected_files.append(path)
            else:
                for frame in range(start, end + 1):
                    path = os.path.join(base_dir, "{}_{}_{}.{}.{}".format(
                        render_instance.folderPath,
                        render_instance.productName,
                        version_str,
                        str(frame).zfill(self.padding_width),
                        ext
                    ))
                    expected_files.append(path)
        return expected_files

    def _get_output_dir(self, render_instance):
        """
            Returns dir path of rendered files, used in submit_publish_job
            for metadata.json location.
            Should be in separate folder inside of work area.

        Args:
            render_instance (RenderInstance):

        Returns:
            (str): absolute path to rendered files
        """
        # render to folder of workfile
        base_dir = os.path.dirname(render_instance.source)
        file_name, _ = os.path.splitext(
            os.path.basename(render_instance.source))
        base_dir = os.path.join(base_dir, 'renders', 'aftereffects', file_name)

        # for submit_publish_job
        return base_dir

    def _update_for_local(self, instance, project_entity):
        """Update old saved instances to current publishing format"""
        instance.stagingDir = tempfile.mkdtemp()
        instance.projectEntity = project_entity
        fam = "render.local"
        if fam not in instance.families:
            instance.families.append(fam)

        return instance
