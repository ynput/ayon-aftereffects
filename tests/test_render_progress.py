"""Tests for the local render progress estimate and its render loop.

The module under test is loaded by path so the tests run without importing the
addon package, which would need AYON and After Effects.

Run with pytest, or directly::

    python tests/test_render_progress.py
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import tempfile
import time

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[1]

EXR_SEQUENCE = "comp_[#####].exr"
MOVIE = "comp.mov"


def _load_render_progress():
    path = ROOT / "client" / "ayon_aftereffects" / "api" / "render_progress.py"
    spec = importlib.util.spec_from_file_location("ae_render_progress", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RENDER_PROGRESS = _load_render_progress()
RenderProgress = RENDER_PROGRESS.RenderProgress
render_with_progress = RENDER_PROGRESS.render_with_progress


def _write(directory, name):
    path = pathlib.Path(directory, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("frame")
    return path


def test_sequence_totals_frames():
    with tempfile.TemporaryDirectory() as tmp:
        progress = RenderProgress(tmp, [EXR_SEQUENCE], 1001, 1005)
        assert progress.total == 5, progress.total
        assert progress.is_measurable is True
        assert progress.done == 0
        assert progress.percent == 0.0


def test_counts_rendered_frames():
    with tempfile.TemporaryDirectory() as tmp:
        progress = RenderProgress(tmp, [EXR_SEQUENCE], 1001, 1005)
        for frame in (1001, 1002, 1003):
            _write(tmp, "comp_{:05d}.exr".format(frame))

        assert progress.done == 3
        assert progress.percent == 60.0
        assert progress.message == "Rendered 3/5 output files (60%)"


def test_movie_only_is_not_measurable():
    """A movie appears only when the render is over, so no percentage."""
    with tempfile.TemporaryDirectory() as tmp:
        progress = RenderProgress(tmp, [MOVIE], 1001, 1005)
        assert progress.is_measurable is False
        assert progress.percent == 0.0
        assert progress.message == (
            "Rendering locally, progress cannot be measured"
        )

        _write(tmp, MOVIE)
        # Even with the file present no percentage is advertised.
        assert progress.percent == 0.0


def test_sequence_without_frame_range_is_not_measurable():
    with tempfile.TemporaryDirectory() as tmp:
        progress = RenderProgress(tmp, [EXR_SEQUENCE], None, None)
        assert progress.total == 0
        assert progress.is_measurable is False


def test_missing_directory_does_not_raise():
    with tempfile.TemporaryDirectory() as tmp:
        progress = RenderProgress(
            str(pathlib.Path(tmp, "does_not_exist")),
            [EXR_SEQUENCE],
            1,
            4,
        )
        assert progress.done == 0
        assert progress.percent == 0.0


def test_extra_files_are_clamped():
    """Files over the expected count must not exceed 100%."""
    with tempfile.TemporaryDirectory() as tmp:
        progress = RenderProgress(tmp, [EXR_SEQUENCE], 1, 2)
        for frame in range(1, 6):
            _write(tmp, "comp_{:05d}.exr".format(frame))

        assert progress.done == 2
        assert progress.percent == 100.0


def test_multiple_output_modules():
    """A sequence per output module adds up, a movie counts as one file."""
    with tempfile.TemporaryDirectory() as tmp:
        progress = RenderProgress(tmp, [EXR_SEQUENCE, MOVIE], 1, 3)
        assert progress.total == 4
        assert progress.extensions == {".exr", ".mov"}

        for frame in (1, 2):
            _write(tmp, "comp_{:05d}.exr".format(frame))

        assert progress.done == 2
        assert progress.percent == 50.0


def test_extension_matching_is_case_insensitive():
    with tempfile.TemporaryDirectory() as tmp:
        progress = RenderProgress(tmp, [EXR_SEQUENCE], 1, 2)
        _write(tmp, "comp_00001.EXR")
        assert progress.done == 1


def test_other_extensions_are_ignored():
    with tempfile.TemporaryDirectory() as tmp:
        progress = RenderProgress(tmp, [EXR_SEQUENCE], 1, 2)
        _write(tmp, "comp_00001.exr")
        _write(tmp, "notes.txt")
        _write(tmp, "comp_00002.tmp")
        assert progress.done == 1


def test_render_with_progress_reports_increasing_percent():
    with tempfile.TemporaryDirectory() as tmp:
        progress = RenderProgress(tmp, [EXR_SEQUENCE], 1, 5)
        reports = []
        logs = []
        polls = []

        def render():
            for frame in range(1, 6):
                _write(tmp, "comp_{:05d}.exr".format(frame))
                time.sleep(0.02)

        render_with_progress(
            render,
            progress,
            poll_interval=0.005,
            log_step=25,
            report=lambda prog, finished: reports.append(
                (prog.percent, finished)
            ),
            log=logs.append,
            poll=lambda: polls.append(True),
        )

        assert reports, "progress was never reported"
        assert polls, "UI was never pumped"
        assert logs, "status was never logged"

        percents = [percent for percent, _ in reports]
        assert percents == sorted(percents), percents
        assert reports[-1] == (100.0, True), reports[-1]
        assert progress.done == progress.total


def test_render_with_progress_reraises_render_error():
    with tempfile.TemporaryDirectory() as tmp:
        progress = RenderProgress(tmp, [EXR_SEQUENCE], 1, 2)

        def render():
            raise RuntimeError("render exploded")

        try:
            render_with_progress(render, progress, poll_interval=0.005)
        except RuntimeError as exc:
            assert str(exc) == "render exploded"
        else:
            raise AssertionError("render error was swallowed")


def test_render_with_progress_works_without_callbacks():
    """Every callback is optional."""
    with tempfile.TemporaryDirectory() as tmp:
        progress = RenderProgress(tmp, [EXR_SEQUENCE], 1, 2)
        render_with_progress(lambda: None, progress, poll_interval=0.005)
        assert True


def test_render_with_progress_handles_unmeasurable_render():
    with tempfile.TemporaryDirectory() as tmp:
        progress = RenderProgress(tmp, [MOVIE], 1, 5)
        logs = []

        def render():
            time.sleep(0.02)
            _write(tmp, MOVIE)

        render_with_progress(
            render,
            progress,
            poll_interval=0.005,
            log=logs.append,
        )

        assert progress.is_measurable is False
        assert logs, "status was never logged"


def run(namespace):
    """Run every `test_*` function of a module namespace."""
    failed = 0
    total = 0
    for name in sorted(namespace):
        if not name.startswith("test_"):
            continue
        test = namespace[name]
        if not callable(test):
            continue

        total += 1
        try:
            test()
        except AssertionError as exc:
            failed += 1
            print("FAIL {}: {}".format(name, exc))
        else:
            print("ok   {}".format(name))

    print("\n{} passed, {} failed of {}".format(
        total - failed, failed, total
    ))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run(globals()))
