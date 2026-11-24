"""Tests for the Output Module Repair plan.

No AYON or After Effects import is needed: the plan is built by
`client/ayon_aftereffects/api/output_module.py`, which is plain Python.

Run with pytest, or directly::

    python tests/test_output_repair.py
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[1]
RULES_PATH = ROOT / "client" / "ayon_aftereffects" / "api" / "output_module.py"


def _load_rules():
    """Load the rules module without importing the addon package."""
    spec = importlib.util.spec_from_file_location(
        "ae_output_module_repair", RULES_PATH
    )
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve string annotations through sys.modules
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RULES = _load_rules()

MP4 = {
    "label": "H.264 MP4",
    "format": "H.264",
    "codec": "",
    "name_pattern": "{product_name}",
    "extensions": ["mp4"],
    "sequence": False,
    "padding": 5,
}
EXR = {
    "label": "OpenEXR Sequence",
    "format": "OpenEXR",
    "codec": "",
    "name_pattern": "{product_name}_[#####]",
    "extensions": ["exr"],
    "sequence": True,
    "padding": 5,
}
PRORES = {
    "label": "ProRes",
    "template": "AYON ProRes",
    "format": "",
    "codec": "",
    "name_pattern": "{product_name}",
    "extensions": ["mov"],
    "sequence": False,
    "padding": 5,
}
PRESETS = [MP4, EXR, PRORES]


def plan(modules, product_name="my_shot", presets=None):
    """Build a Repair plan with the test presets."""
    return RULES.build_repair(
        product_name,
        modules,
        PRESETS if presets is None else presets,
    )


def written(repair_plan):
    """Return `(index, file_name, template)` for every planned write."""
    return [
        (write.index, write.file_name, write.template)
        for write in repair_plan.writes
    ]


def test_wrong_product_name_is_renamed():
    repair_plan = plan(
        [
            {
                "index": 1,
                "format": "H.264",
                "file_name": "file:///D:/out/other_shot.mp4",
            }
        ]
    )
    assert written(repair_plan) == [(1, "my_shot.mp4", "")], written(
        repair_plan
    )
    assert repair_plan.notes == (), repair_plan.notes


def test_product_name_case_is_preserved():
    repair_plan = plan(
        [
            {
                "index": 1,
                "format": "H.264",
                "file_name": "file:///D:/out/other.mp4",
            }
        ],
        product_name="My_Shot_FINAL",
    )
    assert written(repair_plan) == [(1, "My_Shot_FINAL.mp4", "")], written(
        repair_plan
    )


def test_valid_module_is_not_written():
    repair_plan = plan(
        [
            {
                "index": 1,
                "format": "H.264",
                "file_name": "file:///D:/out/my_shot.mp4",
            }
        ]
    )
    assert repair_plan.writes == (), written(repair_plan)
    assert not repair_plan


def test_only_failing_module_is_written():
    repair_plan = plan(
        [
            {
                "index": 1,
                "format": "H.264",
                "file_name": "file:///D:/out/my_shot.mp4",
            },
            {
                "index": 2,
                "format": "H.264",
                "file_name": "file:///D:/out/mistake.mp4",
            },
        ]
    )
    assert written(repair_plan) == [(2, "my_shot.mp4", "")], written(
        repair_plan
    )


def test_missing_frame_token_is_added():
    repair_plan = plan(
        [
            {
                "index": 1,
                "format": "OpenEXR",
                "file_name": "file:///D:/out/my_shot.exr",
            }
        ]
    )
    assert written(repair_plan) == [(1, "my_shot_[#####].exr", "")], written(
        repair_plan
    )


def test_wrong_padding_is_corrected():
    repair_plan = plan(
        [
            {
                "index": 1,
                "format": "OpenEXR",
                "file_name": "file:///D:/out/my_shot_%5B%23%23%23%23%5D.exr",
            }
        ]
    )
    assert written(repair_plan) == [(1, "my_shot_[#####].exr", "")], written(
        repair_plan
    )


def test_appended_frame_number_is_repaired():
    # AYON queued the comp as 'my_shot.exr', so AE wrote 'my_shot.exr00835'.
    # The frame number must not survive into the repaired name.
    repair_plan = plan(
        [
            {
                "index": 1,
                "format": "OpenEXR",
                "file_name": "file:///D:/out/my_shot.exr00835",
            }
        ]
    )
    assert written(repair_plan) == [(1, "my_shot_[#####].exr", "")], written(
        repair_plan
    )
    assert repair_plan.notes == (), repair_plan.notes


def test_unknown_format_uses_the_template():
    repair_plan = plan(
        [
            {
                "index": 1,
                "format": "MPEG-4",
                "file_name": "file:///D:/out/my_shot.mp4",
            }
        ]
    )
    # MP4 is the first preset and has no template, so format stays manual
    assert written(repair_plan) == [(1, "my_shot.mp4", "")], written(
        repair_plan
    )
    assert any("format or codec" in note for note in repair_plan.notes), (
        repair_plan.notes
    )


def test_template_preset_switches_format_and_extension():
    repair_plan = plan(
        [
            {
                "index": 1,
                "format": "MPEG-4",
                "file_name": "file:///D:/out/my_shot.mp4",
            }
        ],
        presets=[PRORES],
    )
    assert written(repair_plan) == [(1, "my_shot.mov", "AYON ProRes")], (
        written(repair_plan)
    )
    assert repair_plan.notes == (), repair_plan.notes


def test_extension_is_not_moved_without_template():
    repair_plan = plan(
        [
            {
                "index": 1,
                "format": "H.264",
                "file_name": "file:///D:/out/my_shot.mov",
            }
        ]
    )
    assert written(repair_plan) == [(1, "my_shot.mov", "")], written(
        repair_plan
    )
    assert any("extension" in note for note in repair_plan.notes), (
        repair_plan.notes
    )


def test_pattern_extension_is_kept():
    preset = dict(MP4, name_pattern="{product_name}.mp4")
    repair_plan = plan(
        [{"index": 1, "format": "H.264", "file_name": "file:///D:/out/x.mp4"}],
        presets=[preset],
    )
    assert written(repair_plan) == [(1, "my_shot.mp4", "")], written(
        repair_plan
    )


def test_no_presets_reports_a_note():
    repair_plan = plan(
        [{"index": 1, "file_name": "file:///D:/out/my_shot.mp4"}],
        presets=[],
    )
    assert repair_plan.writes == (), written(repair_plan)
    assert any("No output presets" in note for note in repair_plan.notes), (
        repair_plan.notes
    )


def test_no_modules_plans_nothing():
    repair_plan = plan([])
    assert repair_plan.writes == (), written(repair_plan)
    assert repair_plan.notes == (), repair_plan.notes


def main():
    """Run every test function and report failures."""
    failed = 0
    total = 0
    for name in sorted(globals()):
        if not name.startswith("test_"):
            continue
        test = globals()[name]
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

    print("\n{} passed, {} failed of {}".format(total - failed, failed, total))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
