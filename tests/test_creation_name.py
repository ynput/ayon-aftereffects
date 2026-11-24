"""Tests for the Output Module name used when an instance is created.

No AYON or After Effects import is needed: the rules live in
`client/ayon_aftereffects/api/output_module.py` and are plain Python.

Run with pytest, or directly::

    python tests/test_creation_name.py
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
        "ae_output_module_creation", RULES_PATH
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


def name(module, product_name="MyShot", presets=None):
    """Return the creation name for one Output Module record."""
    return RULES.creation_name(
        product_name,
        module,
        PRESETS if presets is None else presets,
    )


def test_sequence_format_gets_the_frame_token():
    # This is the reported bug: AYON queued the comp as 'comp.exr', so AE
    # wrote 'comp.exr00835'.
    assert (
        name(
            {
                "index": 1,
                "format": "OpenEXR",
                "file_name": "file:///D:/out/MyShot.exr",
            }
        )
        == "MyShot_[#####].exr"
    )


def test_single_file_format_keeps_its_extension():
    assert (
        name(
            {
                "index": 1,
                "format": "H.264",
                "file_name": "file:///D:/out/MyShot.mp4",
            }
        )
        == "MyShot.mp4"
    )


def test_product_name_case_is_preserved():
    assert (
        name(
            {"index": 1, "format": "OpenEXR", "file_name": "x.exr"},
            product_name="My_Shot_FINAL",
        )
        == "My_Shot_FINAL_[#####].exr"
    )


def test_padding_comes_from_the_preset():
    preset = dict(EXR, padding=4)
    assert (
        name(
            {"index": 1, "format": "OpenEXR", "file_name": "x.exr"},
            presets=[preset],
        )
        == "MyShot_[####].exr"
    )


def test_existing_token_is_normalized():
    assert (
        name(
            {
                "index": 1,
                "format": "OpenEXR",
                "file_name": "file:///D:/out/comp_[###].exr",
            }
        )
        == "MyShot_[#####].exr"
    )


def test_already_correct_name_is_returned_unchanged():
    # The creator compares with the current name and skips the write.
    assert (
        name(
            {
                "index": 1,
                "format": "OpenEXR",
                "file_name": "file:///D:/out/MyShot_[#####].exr",
            }
        )
        == "MyShot_[#####].exr"
    )


def test_appended_frame_number_is_dropped():
    assert (
        name(
            {
                "index": 1,
                "format": "OpenEXR",
                "file_name": "file:///D:/out/MyShot.exr00835",
            }
        )
        == "MyShot_[#####].exr"
    )


def test_template_preset_is_matched():
    assert (
        name(
            {
                "index": 1,
                "name": "AYON ProRes",
                "file_name": "file:///D:/o/x.mov",
            }
        )
        == "MyShot.mov"
    )


def test_unknown_format_is_left_alone():
    assert (
        name(
            {"index": 1, "format": "MPEG-4", "file_name": "file:///D:/o/x.mp4"}
        )
        is None
    )


def test_no_presets_means_no_change():
    assert (
        name(
            {"index": 1, "format": "OpenEXR", "file_name": "x.exr"}, presets=[]
        )
        is None
    )


def test_no_file_name_means_no_change():
    assert name({"index": 1, "format": "OpenEXR"}) is None
    assert name({"index": 1, "format": "OpenEXR", "file_name": ""}) is None


def test_pattern_with_extension_is_used():
    preset = dict(MP4, name_pattern="{product_name}.mp4", extensions=["mp4"])
    assert (
        name(
            {"index": 1, "format": "H.264", "file_name": "file:///D:/o/x.mp4"},
            presets=[preset],
        )
        == "MyShot.mp4"
    )


def main():
    """Run every test function and report failures."""
    failed = 0
    total = 0
    for test_name in sorted(globals()):
        if not test_name.startswith("test_"):
            continue
        test = globals()[test_name]
        if not callable(test):
            continue
        total += 1
        try:
            test()
        except AssertionError as exc:
            failed += 1
            print("FAIL {}: {}".format(test_name, exc))
        else:
            print("ok   {}".format(test_name))

    print("\n{} passed, {} failed of {}".format(total - failed, failed, total))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
