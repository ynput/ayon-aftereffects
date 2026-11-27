"""Tests for the Output Module rules, the Repair plan and creation naming.

No AYON or After Effects import is needed: the rules live in
`client/ayon_aftereffects/api/output_module.py` and are plain Python.

Run with pytest, or directly::

    python tests/test_output_module.py
"""

from __future__ import annotations

import sys

from _helpers import EXR, MP4, PRESETS, PRORES, load_api_module, run

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


def test_later_matching_padding_is_valid_and_not_repaired():
    module = {"index": 1, "format": "OpenEXR", "file_name": EXR_URL}
    presets = [dict(EXR, padding=4), EXR]
    assert keys(validate([module], presets=presets)) == []
    assert not plan([module], presets=presets)


def test_later_matching_candidate_checks_all_rules():
    module = {
        "index": 1,
        "name": "First template",
        "format": "OpenEXR",
        "codec": "Zip",
        "file_name": "my_shot_final_[#####].exr",
    }
    presets = [
        dict(EXR, template="First template", format="Other", codec="Other"),
        dict(EXR, extensions=["png"]),
        dict(EXR, name_pattern="{product_name}_other_[#####]"),
        dict(EXR, sequence=False),
        dict(EXR, codec="Zip", name_pattern="{product_name}_final_[#####]"),
    ]
    assert keys(validate([module], presets=presets)) == []
    assert not plan([module], presets=presets)


def test_later_extension_fallback_candidate_is_valid():
    module = {"index": 1, "file_name": EXR_URL}
    assert keys(validate([module], presets=[dict(EXR, padding=4), EXR])) == []


def test_later_matching_template_candidate_is_valid():
    module = {"index": 1, "name": "Shared template", "file_name": EXR_URL}
    presets = [
        dict(EXR, template="Shared template", padding=4),
        dict(EXR, template="Shared template"),
    ]
    assert keys(validate([module], presets=presets)) == []
    assert not plan([module], presets=presets)


def test_nonmatching_format_and_codec_are_not_alternatives():
    module = {
        "index": 1,
        "format": "OpenEXR",
        "codec": "Zip",
        "file_name": EXR_URL,
    }
    presets = [
        dict(EXR, padding=4, codec="Zip"),
        dict(EXR, format="Other", codec="Zip"),
        dict(EXR, codec="Other"),
    ]
    assert keys(validate([module], presets=presets)) == ["padding"]


def test_candidates_cannot_combine_partial_matches():
    module = {"index": 1, "format": "OpenEXR", "file_name": EXR_URL}
    presets = [
        dict(EXR, padding=4),
        dict(EXR, extensions=["png"]),
    ]
    assert keys(validate([module], presets=presets)) == ["padding"]
    assert written(plan([module], presets=presets)) == [
        (1, "my_shot_[####].exr", "")
    ]


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


def test_sequence_preset_pattern_without_token_is_valid():
    # The pattern may leave the token out, naming still adds it, so the
    # result must validate or Repair could never resolve the failure.
    preset = dict(EXR, name_pattern="{product_name}")
    problems = validate(
        [
            {
                "index": 1,
                "format": "OpenEXR",
                "file_name": "file:///D:/out/my_shot_[#####].exr",
            }
        ],
        presets=[preset],
    )
    assert keys(problems) == [], keys(problems)


def test_sequence_preset_pattern_without_token_is_repairable():
    preset = dict(EXR, name_pattern="{product_name}")
    repair_plan = plan(
        [
            {
                "index": 1,
                "format": "OpenEXR",
                "file_name": "file:///D:/out/my_shot.exr",
            }
        ],
        presets=[preset],
    )
    assert written(repair_plan) == [(1, "my_shot_[#####].exr", "")], written(
        repair_plan
    )
    problems = validate(
        [
            {
                "index": 1,
                "format": "OpenEXR",
                "file_name": "file:///D:/out/my_shot_[#####].exr",
            }
        ],
        presets=[preset],
    )
    assert keys(problems) == [], keys(problems)


def test_dotted_product_name_is_valid():
    problems = validate(
        [
            {
                "index": 1,
                "format": "H.264",
                "file_name": "file:///D:/out/my.shot.mp4",
            }
        ],
        product_name="my.shot",
    )
    assert keys(problems) == [], keys(problems)


def test_dotted_product_name_is_created():
    assert (
        name("H.264", "file:///D:/out/x.mp4", product_name="my.shot")
        == "my.shot.mp4"
    )


def test_dotted_product_name_is_repaired():
    repair_plan = plan(
        [
            {
                "index": 1,
                "format": "H.264",
                "file_name": "file:///D:/out/wrong.mp4",
            }
        ],
        product_name="my.shot",
    )
    assert written(repair_plan) == [(1, "my.shot.mp4", "")], written(
        repair_plan
    )


def test_codec_is_named_when_no_preset_allows_it():
    presets = [dict(PRORES, format="QuickTime", codec="ProRes 422 HQ")]
    problems = validate(
        [
            {
                "index": 1,
                "format": "QuickTime",
                "codec": "Animation",
                "file_name": "file:///D:/out/my_shot.mov",
            }
        ],
        presets=presets,
    )
    assert keys(problems) == ["not_allowed"], keys(problems)

    message = problems[0].message.lower()
    assert "animation" in message, message
    assert "prores 422 hq" in message, message


def test_missing_name_is_repaired_with_the_preset_extension():
    # Nothing to preserve, so the preset names the extension instead of
    # Repair writing a name without one.
    preset = dict(MP4, name_pattern="{product_name}_main")
    repair_plan = plan(
        [{"index": 1, "format": "H.264", "file_name": ""}],
        presets=[preset],
    )
    assert written(repair_plan) == [(1, "my_shot_main.mp4", "")], written(
        repair_plan
    )
    after = validate(
        [
            {
                "index": 1,
                "format": "H.264",
                "file_name": "file:///D:/out/my_shot_main.mp4",
            }
        ],
        presets=[preset],
    )
    assert keys(after) == [], keys(after)


def test_token_in_a_single_file_preset_is_dropped():
    # A token in a single file preset is a configuration mistake; the
    # sequence flag wins, otherwise Repair writes a name the preset rejects.
    preset = dict(EXR, sequence=False)
    repair_plan = plan(
        [
            {
                "index": 1,
                "format": "OpenEXR",
                "file_name": "file:///D:/out/x.exr",
            }
        ],
        presets=[preset],
    )
    assert written(repair_plan) == [(1, "my_shot.exr", "")], written(
        repair_plan
    )
    after = validate(
        [
            {
                "index": 1,
                "format": "OpenEXR",
                "file_name": "file:///D:/out/my_shot.exr",
            }
        ],
        presets=[preset],
    )
    assert keys(after) == [], keys(after)


def test_profile_output_reads_nested_settings():
    profile = {"name": "exr", "output": dict(EXR)}
    assert RULES.profile_output(profile)["format"] == "OpenEXR"
    assert RULES.profile_output(None) == {}
    assert RULES.profile_label(profile) == "exr"
    assert RULES.profile_label({}) == "unnamed"


def test_preset_name_sequence_gets_frame_token():
    name = RULES.preset_name(
        "my_shot", EXR, {"file_name": "/d/out/my_shot.exr"}
    )
    assert name == "my_shot_[#####].exr", name


def test_preset_name_keeps_current_extension():
    name = RULES.preset_name(
        "my_shot",
        dict(EXR, extensions=[]),
        {"file_name": "/d/out/other.exr"},
    )
    assert name == "my_shot_[#####].exr", name


def test_preset_name_single_file_drops_frame_token():
    name = RULES.preset_name(
        "my_shot",
        dict(MP4, name_pattern="{product_name}_[#####]"),
        {"file_name": "/d/out/other.mp4"},
    )
    assert name == "my_shot.mp4", name


def test_preset_name_uses_preset_extension_not_current_one():
    name = RULES.preset_name(
        "my_shot", EXR, {"file_name": "/d/out/other.mp4"}
    )
    assert name == "my_shot_[#####].exr", name


def test_preset_name_uses_preset_extension():
    name = RULES.preset_name("my_shot", EXR, {"file_name": "/d/out/x"})
    assert name == "my_shot_[#####].exr", name


if __name__ == "__main__":
    sys.exit(run(globals()))
