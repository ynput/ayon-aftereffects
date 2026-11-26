"""Tests for the missing source footage message.

No AYON or After Effects import is needed: the rules live in
`client/ayon_aftereffects/api/footage_sources.py` and are plain Python.

Run with pytest, or directly::

    python tests/test_footage_sources.py
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[1]
RULES_PATH = (
    ROOT / "client" / "ayon_aftereffects" / "api" / "footage_sources.py"
)


def _load_rules():
    """Load the rules module without importing the addon package."""
    spec = importlib.util.spec_from_file_location(
        "ae_footage_sources", RULES_PATH
    )
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve string annotations through sys.modules
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RULES = _load_rules()


def summary(records):
    """Summarize records with the rules module."""
    return RULES.summarize_missing_sources(records)


def test_every_reason_is_translated():
    assert summary(
        [
            {"layer": "logo.png", "reason": "missing_source"},
            {"layer": "bg.mov", "reason": "footage_missing"},
            {"layer": "plate.exr", "reason": "file_missing"},
        ]
    ) == (
        "logo.png (layer has no source), "
        "bg.mov (source footage is missing), "
        "plate.exr (source file is missing)"
    )


def test_unknown_reason_is_kept():
    assert summary([{"layer": "odd.mov", "reason": "weird"}]) == (
        "odd.mov (weird)"
    )
    assert summary([{"layer": "odd.mov"}]) == "odd.mov (unknown reason)"


def test_unnamed_layers_and_duplicates():
    assert summary([{"reason": "missing_source"}]) == (
        "<unnamed layer> (layer has no source)"
    )
    assert (
        summary(
            [
                {"layer": "logo.png", "reason": "missing_source"},
                {"layer": "logo.png", "reason": "missing_source"},
            ]
        )
        == "logo.png (layer has no source)"
    )


def test_summary_is_truncated():
    result = summary(
        [
            {"layer": "layer{}".format(index), "reason": "missing_source"}
            for index in range(8)
        ]
    )
    assert result.endswith("and 3 more"), result
    assert result.count("layer has no source") == 5, result


def test_empty_composition():
    # The artist deleted the only layer, so nothing is rendered at all.
    assert summary([{"layer": "", "reason": "empty_comp"}]) == (
        "no layers in the composition, the render would be black"
    )
    assert (
        summary(
            [
                {"layer": "", "reason": "empty_comp"},
                {"layer": "logo.png", "reason": "missing_source"},
            ]
        )
        == "no layers in the composition, the render would be black"
    )


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
