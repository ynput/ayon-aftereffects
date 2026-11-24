"""Tests for the Output Module rules, the Repair plan and creation naming.

No AYON or After Effects import is needed: the rules live in
`client/ayon_aftereffects/api/output_module.py` and are plain Python.

Run with pytest, or directly::

    python tests/test_output_module.py
"""

from __future__ import annotations

import sys

from _helpers import MP4, PRESETS, PRORES, load_api_module, run

RULES = load_api_module("ae_output_module", "output_module.py")

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


def test_appended_frame_number_reports_the_missing_token():
    # With no [#####] token AE appends the frame number after the
    # extension, 'my_shot.exr00835'. That is a missing token, not a bad
    # extension, so it must be reported as one.
    problems = validate(
        [
            {
                "index": 1,
                "format": "OpenEXR",
                "file_name": "file:///D:/out/my_shot.exr00835",
            }
        ]
    )
    assert keys(problems) == ["appended"], keys(problems)


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


#: Repair plan
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


#: Name used when an instance is created
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


if __name__ == "__main__":
    sys.exit(run(globals()))
