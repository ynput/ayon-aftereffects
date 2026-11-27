"""Estimate the progress of a local After Effects render.

After Effects renders the whole render queue in a single blocking call
(``app.project.renderQueue.render()``) and offers no callback to hook into.
The rendered files do appear in the staging directory while it renders, so
counting them gives a usable estimate.

This module is pure Python without AYON or After Effects imports, so it can
be tested on its own (see ``tests/test_render_progress.py``).
"""
import os
import threading


class RenderProgress:
    """Progress of a local render estimated from the files on disk.

    Multiple output modules are supported: an output module whose file name
    contains ``#`` is a numbered frame sequence and is expected to produce one
    file per rendered frame, any other output module produces a single file.

    Args:
        directory (str): Directory the render writes into.
        output_paths (list[str]): Expected output file names as collected
            from the render queue output modules. A ``#`` marks a frame
            sequence.
        frame_start (int | None): First rendered frame. Required to count the
            files of a frame sequence.
        frame_end (int | None): Last rendered frame.

    """

    def __init__(
        self,
        directory,
        output_paths,
        frame_start=None,
        frame_end=None,
    ):
        self._directory = directory
        self._extensions = set()
        self._has_sequence = False
        self._total = 0

        frame_count = 0
        if frame_start is not None and frame_end is not None:
            frame_count = max(0, int(frame_end) - int(frame_start) + 1)

        for path in output_paths or []:
            extension = os.path.splitext(path)[1].lower()
            if extension:
                self._extensions.add(extension)
            if "#" in path:
                self._has_sequence = True
                self._total += frame_count
            else:
                self._total += 1

    @property
    def extensions(self):
        """set[str]: File extensions the render is expected to produce."""
        return set(self._extensions)

    @property
    def total(self):
        """int: Expected number of output files."""
        return self._total

    @property
    def done(self):
        """int: Number of output files that already exist."""
        try:
            names = os.listdir(self._directory)
        except OSError:
            return 0

        count = 0
        for name in names:
            if os.path.splitext(name)[1].lower() in self._extensions:
                count += 1

        if self._total:
            return min(count, self._total)
        return count

    @property
    def is_measurable(self):
        """bool: Can the progress be expressed as a percentage?

        Only a frame sequence writes files while it renders. A single movie
        file appears when the render is already over, so reporting a
        percentage for it would be misleading.
        """
        return self._has_sequence and self._total > 0

    @property
    def percent(self):
        """float: Progress in range <0.0-100.0>."""
        if not self.is_measurable:
            return 0.0
        return max(0.0, min(100.0, self.done / float(self.total) * 100.0))

    @property
    def message(self):
        """str: Short human readable status of the render."""
        if not self.is_measurable:
            return "Rendering locally, progress cannot be measured"
        return "Rendered {}/{} output files ({}%)".format(
            self.done, self.total, int(self.percent)
        )


def render_with_progress(
    render_callable,
    progress,
    poll_interval=0.5,
    log_step=10,
    report=None,
    log=None,
    poll=None,
):
    """Run a blocking render call and report progress while it runs.

    The render call is moved to a worker thread, the calling thread keeps
    checking ``progress`` so it can report how far along the render is.

    Args:
        render_callable (Callable): Blocking call that runs the render.
        progress (RenderProgress): Progress estimate to report.
        poll_interval (float): Seconds between two checks.
        log_step (int): Report the log message at most once per this many
            percent of the render.
        report (Callable | None): Called with ``(progress, finished)`` after
            every check and once when the render is over.
        log (Callable | None): Called with the status message.
        poll (Callable | None): Called after every check, e.g. to pump the UI
            event loop so the reported progress is painted.

    Raises:
        Exception: Whatever ``render_callable`` raised, raised after the
            render finished.

    """
    errors = []

    def _render():
        try:
            render_callable()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    thread = threading.Thread(
        target=_render, name="AYON-AELocalRender", daemon=True
    )
    thread.start()

    last_step = None
    while thread.is_alive():
        thread.join(poll_interval)
        if not thread.is_alive():
            break

        if report is not None:
            report(progress, False)

        step = None
        if progress.is_measurable:
            step = int(progress.percent // log_step)
        if log is not None and step != last_step:
            log(progress.message)
            last_step = step

        if poll is not None:
            poll()

    if errors:
        raise errors[0]

    if report is not None:
        report(progress, True)
    if log is not None:
        log(progress.message)
