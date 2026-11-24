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

PRESETS = [
    {
        "label": "H.264 MP4",
        "format": "H.264",
        "codec": "",
        "name_pattern": "{product_name}",
        "extensions": ["mp4"],
        "sequence": False,
        "padding": 5,
    },
    {
        "label": "OpenEXR Sequence",
        "format": "OpenEXR",
        "codec": "",
        "name_pattern": "{product_name}_[#####]",
        "extensions": ["exr"],
        "sequence": True,
        "padding": 5,
    },
]


def name(fmt, file_name, presets=None, product_name="MyShot"):
    """Return the creation name for one Output Module record."""
    return RULES.creation_name(
        product_name,
        {"index": 1, "format": fmt, "file_name": file_name},
        PRESETS if presets is None else presets,
    )


def test_sequence_format_gets_the_frame_token():
    # The reported bug: AYON queued the comp with a bare name, so AE wrote
    # 'MyShot.exr00835'.
    assert name("OpenEXR", "file:///D:/out/MyShot.exr") == (
        "MyShot_[#####].exr"
    )


def test_single_file_format_keeps_its_extension():
    assert name("H.264", "file:///D:/out/MyShot.mp4") == "MyShot.mp4"


def test_appended_frame_number_is_dropped():
    assert name("OpenEXR", "file:///D:/out/MyShot.exr00835") == (
        "MyShot_[#####].exr"
    )


def test_no_matching_preset_means_no_change():
    assert name("MPEG-4", "file:///D:/out/MyShot.mp4") is None
    assert name("OpenEXR", "file:///D:/out/MyShot.exr", presets=[]) is None
    assert name("OpenEXR", "") is None


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
