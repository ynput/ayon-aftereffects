"""Tests for the Output Module validation rules.

No AYON or After Effects import is needed: the rules live in
`client/ayon_aftereffects/api/output_module.py` and are plain Python.

Run with pytest, or directly::

    python tests/test_output_module.py
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[1]
RULES_PATH = (
    ROOT / "client" / "ayon_aftereffects" / "api" / "output_module.py"
)


def _load_rules():
    """Load the rules module without importing the addon package."""
    spec = importlib.util.spec_from_file_location(
        "ae_output_module", RULES_PATH
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
    {
        "label": "ProRes",
        "template": "AYON ProRes",
        "format": "",
        "codec": "",
        "name_pattern": "{product_name}",
        "extensions": ["mov"],
        "sequence": False,
        "padding": 5,
    },
]

EXR_URL = "file:///D:/out/my_shot_%5B%23%23%23%23%23%5D.exr"


def validate(modules, product_name="my_shot", presets=None):
    """Run the rules with the test presets."""
    return RULES.validate_output_modules(
        product_name,
        modules,
        PRESETS if presets is None else presets,
    )


def keys(problems):
    """Return the problem keys in detection order."""
    return [problem.key for problem in problems]


def test_h264_single_file_is_valid():
    problems = validate([
        {
            "index": 1,
            "name": "H.264 - Match Render Settings",
            "format": "H.264",
            "codec": "H.264",
            "file_name": "file:///D:/out/my_shot.mp4",
        }
    ])
    assert keys(problems) == [], keys(problems)


def test_percent_encoded_exr_sequence_is_valid():
    problems = validate([
        {"index": 1, "format": "OpenEXR", "file_name": EXR_URL}
    ])
    assert keys(problems) == [], keys(problems)


def test_template_match_is_valid():
    problems = validate([
        {
            "index": 1,
            "name": "AYON ProRes",
            "file_name": "file:///D:/out/my_shot.mov",
        }
    ])
    assert keys(problems) == [], keys(problems)


def test_extension_fallback_without_format():
    problems = validate([
        {
            "index": 1,
            "file_name": "file:///D:/out/my_shot_%5B%23%23%23%23%23%5D.exr",
        }
    ])
    assert keys(problems) == [], keys(problems)


def test_wrong_product_name():
    problems = validate([
        {
            "index": 1,
            "format": "H.264",
            "file_name": "file:///D:/out/other_shot.mp4",
        }
    ])
    assert keys(problems) == ["name"], keys(problems)


def test_wrong_extension_for_format():
    problems = validate([
        {
            "index": 1,
            "format": "H.264",
            "file_name": "file:///D:/out/my_shot.mov",
        }
    ])
    assert keys(problems) == ["extension"], keys(problems)


def test_sequence_without_frame_token():
    problems = validate([
        {
            "index": 1,
            "format": "OpenEXR",
            "file_name": "file:///D:/out/my_shot.exr",
        }
    ])
    assert keys(problems) == ["sequence"], keys(problems)


def test_sequence_with_wrong_padding():
    problems = validate([
        {
            "index": 1,
            "format": "OpenEXR",
            "file_name": "file:///D:/out/my_shot_%5B%23%23%23%23%5D.exr",
        }
    ])
    assert keys(problems) == ["padding"], keys(problems)


def test_single_file_with_frame_token():
    problems = validate([
        {
            "index": 1,
            "format": "H.264",
            "file_name": "file:///D:/out/my_shot_%5B%23%23%23%23%23%5D.mp4",
        }
    ])
    assert keys(problems) == ["single_file"], keys(problems)


def test_printf_pattern_is_rejected():
    problems = validate([
        {
            "index": 1,
            "format": "OpenEXR",
            "file_name": "file:///D:/out/my_shot_%05d.exr",
        }
    ])
    assert "sequence" in keys(problems), keys(problems)
    assert "name" not in keys(problems), keys(problems)


def test_unknown_format():
    problems = validate([
        {
            "index": 1,
            "format": "MPEG-4",
            "file_name": "file:///D:/out/my_shot.mp4",
        }
    ])
    assert keys(problems) == ["not_allowed"], keys(problems)


def test_missing_file_name():
    problems = validate([{"index": 1, "format": "H.264"}])
    assert keys(problems) == ["missing_name"], keys(problems)


def test_publish_icon_and_spaces_are_ignored():
    problems = validate([
        {
            "index": 1,
            "format": "H.264",
            "file_name": "file:///D:/out/%E2%84%97 my_shot.mp4",
        }
    ])
    assert keys(problems) == [], keys(problems)


def test_parse_padding():
    parsed = RULES.parse_output_name("comp_[#####].exr")
    assert parsed.stem == "comp_{frame}", parsed.stem
    assert parsed.ext == "exr", parsed.ext
    assert parsed.padding == 5, parsed.padding


def test_parse_without_frame_token():
    parsed = RULES.parse_output_name("/tmp/shot.v2.mp4")
    assert parsed.stem == "shot.v2", parsed.stem
    assert parsed.ext == "mp4", parsed.ext
    assert parsed.padding is None, parsed.padding


def test_no_presets_configured():
    problems = validate(
        [{"index": 1, "file_name": "file:///D:/out/my_shot.mp4"}],
        presets=[],
    )
    assert keys(problems) == ["not_allowed"], keys(problems)


def test_missing_modules():
    problems = validate([])
    assert keys(problems) == ["missing"], keys(problems)


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

    print("\n{} passed, {} failed of {}".format(
        total - failed, failed, total
    ))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
