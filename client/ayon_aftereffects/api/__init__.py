"""Public API

Anything that isn't defined here is INTERNAL and unreliable for external use.

"""

from .lib import (
    get_entity_attributes,
    get_extension_manifest_path,
    maintained_selection,
    set_settings,
)
from .pipeline import AfterEffectsHost, containerise, ls
from .plugin import AfterEffectsLoader
from .ws_stub import (
    get_stub,
)

__all__ = [
    # pipeline
    "AfterEffectsHost",
    # plugin
    "AfterEffectsLoader",
    "containerise",
    "get_entity_attributes",
    "get_extension_manifest_path",
    # ws_stub
    "get_stub",
    "ls",
    # lib
    "maintained_selection",
    "set_settings"
]
