"""Tests for the missing source footage formatting.

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


class Layer:
    """Stand-in for an object with attributes instead of a dict."""

    def __init__(self, layer, reason):
        self.layer = layer
        self.reason = reason


def test_reasons_are_translated():
    sources = RULES.collect_missing_sources(
        [
            {"layer": "logo.png", "reason": "missing_source"},
            {"layer": "bg.mov", "reason": "footage_missing"},
            {"layer": "plate.exr", "reason": "file_missing"},
        ]
    )
    assert [source.reason for source in sources] == [
        "layer has no source",
        "source footage is missing",
        "source file is missing",
    ], sources


def test_unknown_reason_is_kept():
    sources = RULES.collect_missing_sources(
        [{"layer": "odd.mov", "reason": "weird"}]
    )
    assert sources[0].reason == "weird", sources


def test_missing_reason_falls_back():
    sources = RULES.collect_missing_sources([{"layer": "odd.mov"}])
    assert sources[0].reason == "unknown reason", sources


def test_unnamed_layer():
    sources = RULES.collect_missing_sources([{"reason": "missing_source"}])
    assert sources[0].layer == "<unnamed layer>", sources


def test_duplicates_are_removed():
    record = {"layer": "logo.png", "reason": "missing_source"}
    sources = RULES.collect_missing_sources([record, dict(record)])
    assert len(sources) == 1, sources


def test_objects_are_supported():
    sources = RULES.collect_missing_sources(
        [Layer("logo.png", "file_missing")]
    )
    assert sources[0].description == "logo.png (source file is missing)", (
        sources
    )


def test_empty_input():
    assert RULES.collect_missing_sources(None) == [], "None"
    assert RULES.collect_missing_sources([]) == [], "empty"
    assert RULES.summarize_missing_sources(None) == "", "summary"


def test_summary_lists_layers():
    summary = RULES.summarize_missing_sources(
        [
            {"layer": "logo.png", "reason": "missing_source"},
            {"layer": "bg.mov", "reason": "file_missing"},
        ]
    )
    assert summary == (
        "logo.png (layer has no source), bg.mov (source file is missing)"
    ), summary


def test_summary_is_truncated():
    summary = RULES.summarize_missing_sources(
        [
            {"layer": "layer{}".format(index), "reason": "missing_source"}
            for index in range(8)
        ]
    )
    assert summary.endswith("and 3 more"), summary
    assert summary.count("layer has no source") == 5, summary


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
