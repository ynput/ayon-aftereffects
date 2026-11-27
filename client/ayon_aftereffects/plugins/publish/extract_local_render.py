import os

from ayon_core.pipeline import publish

from ayon_aftereffects.api import get_stub
from ayon_aftereffects.api.render_progress import (
    RenderProgress,
    render_with_progress,
)
from ayon_aftereffects.api.render_progress_window import (
    create_progress_window,
)


class ExtractLocalRender(publish.Extractor):
    """Render RenderQueue locally."""

    order = publish.Extractor.order - 0.47
    label = "Extract Local Render"
    hosts = ["aftereffects"]
    families = ["render.local"]

    # Seconds between two checks of the staging directory while rendering
    poll_interval = 0.5
    # Log at most one line per this many percent of the render
    log_step = 10

    def process(self, instance):
        stub = get_stub()
        staging_dir = instance.data["stagingDir"]
        self.log.debug("staging_dir::{}".format(staging_dir))

        # pull file name collected value from Render Queue Output module
        if not instance.data["render_queue_file_paths"]:
            raise ValueError("No file extension set in Render Queue")

        comp_id = instance.data['comp_id']
        progress = RenderProgress(
            staging_dir,
            instance.data["render_queue_file_paths"],
            frame_start=instance.data.get("frameStart"),
            frame_end=instance.data.get("frameEnd"),
        )
        self._render_with_progress(
            instance, stub, staging_dir, comp_id, progress
        )

        representations = []
        for file_name in instance.data["render_queue_file_paths"]:
            _, ext = os.path.splitext(os.path.basename(file_name))
            ext = ext[1:]

            first_file_path = None
            files = []
            for found_file_name in os.listdir(staging_dir):
                if not found_file_name.endswith(ext):
                    continue

                files.append(found_file_name)
                if first_file_path is None:
                    first_file_path = os.path.join(staging_dir,
                                                   found_file_name)

            if not files:
                self.log.info("no files")
                return

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

    def _render_with_progress(
        self, instance, stub, staging_dir, comp_id, progress
    ):
        """Render on a worker thread and report progress while it runs.

        'AfterEffects.render' blocks until the whole render queue finished, so
        it runs on a thread to be able to count the output files that appear
        in the staging directory meanwhile.

        Args:
            instance (pyblish.api.Instance): Instance being published.
            stub (AfterEffectsServerStub): Connected After Effects stub.
            staging_dir (str): Directory the render writes into.
            comp_id (int): Id of the composition to render.
            progress (RenderProgress): Progress estimate to report.

        """
        comp_name = instance.data.get("comp_name", comp_id)
        self.log.info("Rendering '{}' locally".format(comp_name))

        window = self._create_progress_window(comp_name)
        self._progress_window = window
        try:
            render_with_progress(
                lambda: stub.render(staging_dir, comp_id),
                progress,
                poll_interval=self.poll_interval,
                log_step=self.log_step,
                report=self._on_progress,
                log=self.log.info,
                poll=self._pump_events,
            )
        finally:
            self._progress_window = None
            if window is not None:
                window.close()

    def _create_progress_window(self, comp_name):
        """Show the render progress window, or None when it cannot be shown.

        Showing progress is best effort: it must never break the publish, so
        a failure to create the window only removes the visual feedback.

        Args:
            comp_name (str): Name of the composition being rendered.

        Returns:
            RenderProgressWindow | None: Shown window or None.

        """
        try:
            window = create_progress_window(comp_name)
        except Exception:  # noqa: BLE001
            self.log.debug(
                "Could not create the render progress window", exc_info=True
            )
            return None

        if window is not None:
            window.show()
        return window

    def _on_progress(self, progress, finished=False):
        """Update the progress window and forward the state to core.

        Args:
            progress (RenderProgress): Snapshot of the render progress.
            finished (bool): The render is over.

        """
        window = getattr(self, "_progress_window", None)
        if window is not None:
            window.update_progress(progress)

        self._report_state(progress, finished)

    def _report_state(self, progress, finished=False):
        """Forward progress to the Publisher when core supports it.

        'AYONPyblishPluginMixin.set_state' is not part of every supported
        core version yet. Where it is missing this does nothing and the
        log lines are the only feedback; it starts driving the Publisher
        progress bar once core provides it.

        Args:
            progress (RenderProgress): Progress estimate to report.
            finished (bool): Report the render as completed.

        """
        percent = None
        if progress.is_measurable:
            percent = 100 if finished else progress.percent

        set_state = getattr(self, "set_state", None)
        if set_state is None:
            return

        try:
            set_state(percent=percent, message=progress.message)
        except Exception:  # noqa: BLE001
            self.log.debug("Failed to report plugin state", exc_info=True)

    @staticmethod
    def _pump_events():
        """Process pending Qt events so the Publisher keeps repainting.

        The polling loop runs on the main thread while the render happens on
        a worker thread. Without this the Publisher UI would stay frozen for
        the whole render and the progress lines would only show up at the end.

        Does nothing when Qt is not available, e.g. in a headless environment.
        """
        try:
            from qtpy.QtWidgets import QApplication
        except ImportError:
            return

        app = QApplication.instance()
        if app is not None:
            app.processEvents()
