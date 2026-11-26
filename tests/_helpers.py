"""Shared fixtures and helpers for the rules tests.

The rules modules are loaded by path, so the tests run without importing the
addon package: that would need AYON, pyblish and After Effects.

Run a test module with pytest, or directly::

    python tests/test_output_module.py
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: Presets shared by the Output Module tests.
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


def load_api_module(spec_name, file_name):
    """Load a module of the addon's 'api' package by path.

    Args:
        spec_name (str): Unique name to register the module under.
        file_name (str): File name inside 'client/ayon_aftereffects/api'.

    Returns:
        module: The loaded module.
    """
    path = ROOT / "client" / "ayon_aftereffects" / "api" / file_name
    spec = importlib.util.spec_from_file_location(spec_name, path)
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve string annotations through sys.modules
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run(namespace):
    """Run every `test_*` function of a module namespace.

    Args:
        namespace (dict): Result of `globals()` in the test module.

    Returns:
        int: Exit code, 0 when every test passed.
    """
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
