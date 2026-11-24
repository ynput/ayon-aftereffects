"""Missing source detection for compiled After Effects compositions.

`ValidateFootageItems` compares the paths of the footage items that still
exist in the After Effects project. That misses the case where the footage
itself is gone - an artist removed it, or the project references an item that
was deleted - because then there is no footage item left to check. The layers
that used it stay in the compositions, After Effects renders them as black
frames, and the publish reports nothing.

The extension reports those layers, this module turns the records into the
artist message. Pure Python on purpose: no AYON or After Effects imports, so
the formatting can be unit tested without launching After Effects.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

#: Reason reported by the extension, in artist words.
REASONS = {
    "missing_source": "layer has no source",
    "footage_missing": "source footage is missing",
    "file_missing": "source file is missing",
}

#: Layer name used when the host reports none.
_UNNAMED_LAYER = "<unnamed layer>"

#: How many layers the summary names before it counts the rest.
_SUMMARY_LIMIT = 5


def summarize_missing_sources(records: Iterable[Any] | None) -> str:
    """Return a one line summary of the layers that cannot render.

    Args:
        records: Layer source records reported by the extension, mappings
            or models with `layer` and `reason`.

    Returns:
        Comma separated "layer (reason)" entries, at most
        `_SUMMARY_LIMIT`, or an empty string when every layer can render.
    """
    seen = set()
    parts = []
    for record in records or []:
        layer = str(_get(record, "layer", "") or "").strip()
        layer = layer or _UNNAMED_LAYER
        code = str(_get(record, "reason", "") or "").strip()
        reason = REASONS.get(code, code or "unknown reason")

        if (layer, reason) in seen:
            continue
        seen.add((layer, reason))
        parts.append("{} ({})".format(layer, reason))

    shown = parts[:_SUMMARY_LIMIT]
    if len(parts) > len(shown):
        shown.append("and {} more".format(len(parts) - len(shown)))
    return ", ".join(shown)


def _get(value: Any, key: str, default: Any = None) -> Any:
    """Read `key` from a mapping or an object.

    Args:
        value: Dictionary or model.
        key: Field name.
        default: Value returned when the field is missing.

    Returns:
        Field value or `default`.
    """
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)
