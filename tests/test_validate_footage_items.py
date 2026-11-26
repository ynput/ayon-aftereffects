"""Tests for footage validation error aggregation.

Run with pytest, or directly::

    python tests/test_validate_footage_items.py
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[1]
PLUGIN_PATH = (
    ROOT
    / "client"
    / "ayon_aftereffects"
    / "plugins"
    / "publish"
    / "validate_footage_items.py"
)


class PublishXmlValidationError(Exception):
    """Stand-in for the AYON publish validation exception."""

    def __init__(self, plugin, message, key=None, formatting_data=None):
        super().__init__(message)
        self.plugin = plugin
        self.key = key
        self.formatting_data = formatting_data


def _load_validator():
    """Load the plugin with lightweight stubs for host dependencies."""
    fake_pyblish = types.ModuleType("pyblish")
    fake_pyblish_api = types.ModuleType("pyblish.api")
    fake_pyblish_api.InstancePlugin = type("InstancePlugin", (), {})
    fake_pyblish_api.ValidatorOrder = 1
    fake_pyblish.api = fake_pyblish_api

    fake_ayon_core = types.ModuleType("ayon_core")
    fake_ayon_core_pipeline = types.ModuleType("ayon_core.pipeline")
    fake_ayon_core_pipeline.PublishXmlValidationError = (
        PublishXmlValidationError
    )
    fake_ayon_core.pipeline = fake_ayon_core_pipeline

    fake_ayon_aftereffects = types.ModuleType("ayon_aftereffects")
    fake_ayon_aftereffects_api = types.ModuleType("ayon_aftereffects.api")
    fake_ayon_aftereffects_api.get_stub = lambda: None
    fake_footage_sources = types.ModuleType(
        "ayon_aftereffects.api.footage_sources"
    )
    fake_footage_sources.summarize_missing_sources = lambda records: ""
    fake_ayon_aftereffects_api.footage_sources = fake_footage_sources
    fake_ayon_aftereffects.api = fake_ayon_aftereffects_api

    stubs = {
        "pyblish": fake_pyblish,
        "pyblish.api": fake_pyblish_api,
        "ayon_core": fake_ayon_core,
        "ayon_core.pipeline": fake_ayon_core_pipeline,
        "ayon_aftereffects": fake_ayon_aftereffects,
        "ayon_aftereffects.api": fake_ayon_aftereffects_api,
        "ayon_aftereffects.api.footage_sources": fake_footage_sources,
    }
    original_modules = {
        name: sys.modules.get(name) for name in stubs
    }
    sys.modules.update(stubs)
    try:
        spec = importlib.util.spec_from_file_location(
            "ae_validate_footage_items_test", PLUGIN_PATH
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, original in original_modules.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


VALIDATOR_MODULE = _load_validator()


def _process_error(invalid):
    """Return the validation error raised for the supplied problem list."""
    plugin = VALIDATOR_MODULE.ValidateFootageItems()
    plugin.get_invalid = lambda instance: invalid
    instance = types.SimpleNamespace(data={"comp_name": "Comp"})
    try:
        plugin.process(instance)
    except PublishXmlValidationError as exc:
        return exc
    raise AssertionError("Expected footage validation to fail")


def test_single_invalid_record_uses_the_combined_error():
    error = _process_error(
        [{"key": "main", "message": "Missing footage", "data": {}}]
    )
    assert error.key == "problems", error.key
    assert error.args[0] == "Missing footage", error.args
    assert error.formatting_data == {
        "comp_name": "Comp",
        "count": 1,
        "problems": "Missing footage",
    }, error.formatting_data


def test_all_invalid_records_are_included_in_the_error():
    error = _process_error(
        [
            {"key": "main", "message": "Missing footage", "data": {}},
            {"key": "missing_source", "message": "No source", "data": {}},
        ]
    )
    assert error.key == "problems", error.key
    assert error.args[0] == "Missing footage\nNo source", error.args
    assert error.formatting_data == {
        "comp_name": "Comp",
        "count": 2,
        "problems": "Missing footage\nNo source",
    }, error.formatting_data


def main():
    """Run each test function and report failures."""
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
