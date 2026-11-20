"""Output Module checks for the After Effects Render Queue.

A Render Queue item stores the file format, the codec and the output file
name in its Output Module. AYON only rewrites the output folder, so the
format stays under the artist's control - which is why it is worth
validating before a render starts.

This module is pure Python on purpose: no AYON or After Effects imports,
so every rule can be unit tested without launching After Effects.
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

#: Frame padding assumed when a preset does not configure it.
DEFAULT_PADDING = 5

#: Placeholder replaced with the product name in a file name pattern.
PRODUCT_NAME_TOKEN = "{product_name}"

#: AE writes frame numbers with square brackets, e.g. "comp_[#####].exr".
#: A printf pattern such as "comp_%05d.exr" is not a valid AE output name.
_SEQUENCE_TOKEN_RE = re.compile(r"\[(?P<hashes>#+)\]")

#: Marker the frame token is replaced with before comparing names.
_FRAME_MARKER = "{frame}"

#: Character AE adds to a queued item after publishing (PUBLISH_ICON).
_PUBLISH_ICON = "\u2117"


@dataclass(frozen=True)
class OutputName:
    """Parsed Output Module file name."""

    raw: Any
    name: str
    stem: str
    ext: str
    padding: int | None


@dataclass(frozen=True)
class OutputProblem:
    """Single validation problem with a stable key."""

    key: str
    message: str
    fields: Mapping[str, Any] = field(default_factory=dict)


def parse_output_name(value: Any) -> OutputName:
    """Parse an Output Module file name.

    Args:
        value: File name, `file://` URL or absolute path.

    Returns:
        Parsed name. `padding` is the number of `#` characters of the
        frame token, or `None` when the name has no frame token.
    """
    name = _basename(value)
    token = _SEQUENCE_TOKEN_RE.search(name)
    padding = len(token.group("hashes")) if token else None

    stem_part, separator, ext = name.rpartition(".")
    if not separator or not ext.isalnum():
        stem_part, ext = name, ""

    return OutputName(
        raw=value,
        name=name,
        stem=_SEQUENCE_TOKEN_RE.sub(_FRAME_MARKER, stem_part).casefold(),
        ext=ext.casefold(),
        padding=padding,
    )


def describe_presets(presets: Iterable[Any]) -> str:
    """Return a human readable list of allowed presets.

    Args:
        presets: Preset models or dictionaries.

    Returns:
        Comma separated description, used in error messages.
    """
    labels = []
    for preset in presets:
        label = (
            _text(_get(preset, "label", ""))
            or _text(_get(preset, "format", ""))
            or _text(_get(preset, "template", ""))
        )
        if not label:
            continue

        extensions = [
            str(ext).strip().lstrip(".").casefold()
            for ext in (_get(preset, "extensions", None) or [])
            if str(ext).strip()
        ]
        if extensions:
            label = "{} ({})".format(
                label, ", ".join("." + ext for ext in extensions)
            )
        labels.append(label)

    return "; ".join(labels) or "no presets configured"


def match_preset(
    module: Any,
    presets: Iterable[Mapping[str, Any]],
    actual: OutputName,
) -> Mapping[str, Any] | None:
    """Return the preset an Output Module belongs to.

    A preset is matched by template name first, then by format and codec.
    When the host could not report the format (older extension), the
    extension is used as a last resort.

    Args:
        module: Output Module record, dictionary or model.
        presets: Normalized presets.
        actual: Parsed output file name.

    Returns:
        Matching preset, or `None` when the module is not allowed.
    """
    module_format = _text(_get(module, "format", ""))
    module_codec = _text(_get(module, "codec", ""))
    module_names = {
        _text(_get(module, "name", "")),
        _text(_get(module, "template", "")),
    }

    for preset in presets:
        if preset["template"] and preset["template"] in module_names:
            return preset

    for preset in presets:
        if not preset["format"] or preset["format"] != module_format:
            continue
        if preset["codec"] and preset["codec"] != module_codec:
            continue
        return preset

    if not module_format:
        for preset in presets:
            if actual.ext and actual.ext in preset["extensions"]:
                return preset

    return None


def validate_output_modules(
    product_name: str,
    modules: Iterable[Any],
    presets: Iterable[Any],
) -> list[OutputProblem]:
    """Check every Output Module against the allowed presets.

    Args:
        product_name: Product name of the instance, used for the name
            check.
        modules: Output Module records from the host, or dictionaries
            with only `file_name` and `index` as a fallback.
        presets: Allowed presets from project settings.

    Returns:
        Problems in detection order. An empty list means the Output
        Modules are valid.
    """
    normalized_presets = [
        _normalize_preset(preset) for preset in presets or []
    ]
    modules = list(modules or [])

    if not modules:
        return [
            OutputProblem(
                key="missing",
                message=(
                    "No Render Queue Output Module was found. Add the "
                    "composition to the Render Queue and refresh the "
                    "publisher."
                ),
            )
        ]

    allowed = describe_presets(normalized_presets)
    problems: list[OutputProblem] = []
    for module in modules:
        problems.extend(
            _validate_module(
                product_name, module, normalized_presets, allowed
            )
        )
    return problems


def _validate_module(
    product_name: str,
    module: Any,
    presets: list[Mapping[str, Any]],
    allowed: str,
) -> list[OutputProblem]:
    """Check one Output Module record.

    Args:
        product_name: Product name of the instance.
        module: Output Module record.
        presets: Normalized presets.
        allowed: Human readable list of allowed presets.

    Returns:
        Problems found for this Output Module.
    """
    index = _get(module, "index", 1) or 1
    raw_name = _get(module, "file_name", "") or ""
    if not raw_name:
        return [
            OutputProblem(
                key="missing_name",
                message=(
                    "Output Module {} has no output file name set.".format(
                        index
                    )
                ),
                fields={"index": index},
            )
        ]

    actual = parse_output_name(raw_name)
    preset = match_preset(module, presets, actual)
    if preset is None:
        configured = (
            _get(module, "format", "") or actual.ext or "unknown"
        )
        return [
            OutputProblem(
                key="not_allowed",
                message=(
                    "Output Module {} uses '{}', which is not an allowed "
                    "output preset. Allowed: {}.".format(
                        index, configured, allowed
                    )
                ),
                fields={
                    "index": index,
                    "actual": configured,
                    "allowed": allowed,
                },
            )
        ]

    label = (
        preset["label"] or preset["format"] or preset["template"] or "preset"
    )
    problems: list[OutputProblem] = []

    extensions = preset["extensions"]
    if extensions and actual.ext not in extensions:
        problems.append(
            OutputProblem(
                key="extension",
                message=(
                    "Output Module {} writes '.{}', but '{}' allows "
                    "{}.".format(
                        index,
                        actual.ext,
                        label,
                        ", ".join("." + ext for ext in extensions),
                    )
                ),
                fields={
                    "index": index,
                    "actual": "." + actual.ext if actual.ext else "",
                    "expected": ", ".join(
                        "." + ext for ext in extensions
                    ),
                },
            )
        )

    frame_problem = False
    if preset["sequence"]:
        if actual.padding is None:
            frame_problem = True
            problems.append(
                OutputProblem(
                    key="sequence",
                    message=(
                        "Output Module {} is a frame sequence, but '{}' "
                        "has no [#####] frame token.".format(
                            index, actual.name
                        )
                    ),
                    fields={"index": index, "actual": actual.name},
                )
            )
        elif actual.padding != preset["padding"]:
            frame_problem = True
            problems.append(
                OutputProblem(
                    key="padding",
                    message=(
                        "Output Module {} uses {} digit(s) for the frame "
                        "number, expected {}.".format(
                            index, actual.padding, preset["padding"]
                        )
                    ),
                    fields={
                        "index": index,
                        "actual": str(actual.padding),
                        "expected": str(preset["padding"]),
                    },
                )
            )
    elif actual.padding is not None:
        frame_problem = True
        problems.append(
            OutputProblem(
                key="single_file",
                message=(
                    "Output Module {} writes a frame sequence, but '{}' "
                    "is a single file preset.".format(index, label)
                ),
                fields={"index": index, "actual": actual.name},
            )
        )

    expected_name = preset["name_pattern"]
    if expected_name and not frame_problem:
        expected_display = expected_name.replace(
            PRODUCT_NAME_TOKEN, product_name or ""
        )
        expected = parse_output_name(expected_display)
        if actual.stem != expected.stem:
            problems.append(
                OutputProblem(
                    key="name",
                    message=(
                        "Output Module {} writes '{}', expected "
                        "'{}'.".format(
                            index, actual.name, expected_display
                        )
                    ),
                    fields={
                        "index": index,
                        "actual": actual.name,
                        "expected": expected_display,
                    },
                )
            )

    if preset["format"] and _get(module, "format", ""):
        if _text(_get(module, "format")) != preset["format"]:
            problems.append(
                OutputProblem(
                    key="format",
                    message=(
                        "Output Module {} uses format '{}', expected "
                        "'{}'.".format(
                            index,
                            _get(module, "format"),
                            preset["format"],
                        )
                    ),
                    fields={
                        "index": index,
                        "actual": _get(module, "format"),
                        "expected": preset["format"],
                    },
                )
            )

    if preset["codec"] and _get(module, "codec", ""):
        if _text(_get(module, "codec")) != preset["codec"]:
            problems.append(
                OutputProblem(
                    key="codec",
                    message=(
                        "Output Module {} uses codec '{}', expected "
                        "'{}'.".format(
                            index,
                            _get(module, "codec"),
                            preset["codec"],
                        )
                    ),
                    fields={
                        "index": index,
                        "actual": _get(module, "codec"),
                        "expected": preset["codec"],
                    },
                )
            )

    return problems


def _normalize_preset(preset: Any) -> dict[str, Any]:
    """Return a preset as a dictionary with defaults filled in.

    Args:
        preset: Preset model or dictionary from project settings.

    Returns:
        Normalized preset.
    """
    extensions = [
        str(ext).strip().lstrip(".").casefold()
        for ext in (_get(preset, "extensions", None) or [])
        if str(ext).strip()
    ]

    padding = _get(preset, "padding", DEFAULT_PADDING)
    try:
        padding = int(padding)
    except (TypeError, ValueError):
        padding = DEFAULT_PADDING

    return {
        "label": str(_get(preset, "label", "") or "").strip(),
        "template": _text(_get(preset, "template", "")),
        "format": _text(_get(preset, "format", "")),
        "codec": _text(_get(preset, "codec", "")),
        "name_pattern": str(_get(preset, "name_pattern", "") or ""),
        "extensions": extensions,
        "sequence": bool(_get(preset, "sequence", False)),
        "padding": max(padding, 1),
    }


def _basename(value: Any) -> str:
    """Return the decoded file name of an Output Module path or URL.

    Args:
        value: File name, `file://` URL or absolute path.

    Returns:
        File name without folders, publish marker or surrounding spaces.
    """
    text = urllib.parse.unquote(str(value or "")).replace("\\", "/")
    for prefix in ("file:///", "file://"):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break

    name = text.rsplit("/", 1)[-1]
    return name.replace(_PUBLISH_ICON, "").strip()


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


def _text(value: Any) -> str:
    """Return a trimmed, case folded string.

    Args:
        value: Any value.

    Returns:
        Normalized string.
    """
    return str(value or "").strip().casefold()
