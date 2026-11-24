"""Missing source detection for compiled After Effects compositions.

`ValidateFootageItems` compares the paths of the footage items that still
exist in the After Effects project. That misses the case where the footage
itself is gone - an artist removed it with *AYON > Manage > Remove*, or the
project references an item that was deleted - because then there is no
footage item left to check. The layers that used it stay in the
compositions, After Effects renders them as black frames, and the publish
reports nothing.

The extension reports those layers, this module turns the records into
artist messages. Pure Python on purpose: no AYON or After Effects imports,
so the formatting can be unit tested without launching After Effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

#: Reason reported by the extension, in artist words.
REASONS = {
    "missing_source": "layer has no source",
    "footage_missing": "source footage is missing",
    "file_missing": "source file is missing",
}

#: Placeholder used when a layer has no name.
_UNNAMED_LAYER = "<unnamed layer>"


@dataclass(frozen=True)
class MissingSource:
    """A layer of a composition that cannot render."""

    layer: str
    reason: str

    @property
    def description(self) -> str:
        """Artist facing description of this problem."""
        return "{} ({})".format(self.layer, self.reason)


def collect_missing_sources(
    records: Iterable[Any] | None,
) -> list[MissingSource]:
    """Normalize layer source records reported by the extension.

    Args:
        records: Dictionaries or models with `layer` and `reason`.

    Returns:
        One entry per unusable layer, duplicates removed.
    """
    seen = set()
    sources: list[MissingSource] = []
    for record in records or []:
        layer = str(_get(record, "layer", "") or "").strip()
        layer = layer or _UNNAMED_LAYER
        code = str(_get(record, "reason", "") or "").strip()
        reason = REASONS.get(code, code or "unknown reason")

        key = (layer, reason)
        if key in seen:
            continue
        seen.add(key)
        sources.append(MissingSource(layer=layer, reason=reason))

    return sources


def summarize_missing_sources(records: Iterable[Any] | None) -> str:
    """Return a one line summary of the unusable layers.

    Args:
        records: Layer source records reported by the extension.

    Returns:
        Comma separated descriptions, or an empty string.
    """
    sources = collect_missing_sources(records)
    if not sources:
        return ""

    shown = [source.description for source in sources[:5]]
    if len(sources) > len(shown):
        shown.append("and {} more".format(len(sources) - len(shown)))

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
