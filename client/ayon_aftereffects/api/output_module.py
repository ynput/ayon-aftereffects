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
from typing import Any, Iterable, Iterator, Mapping

#: Frame padding assumed when a preset does not configure it.
DEFAULT_PADDING = 5

#: Placeholder replaced with the product name in a file name pattern.
PRODUCT_NAME_TOKEN = "{product_name}"

#: AE writes frame numbers with square brackets, e.g. "comp_[#####].exr".
#: A printf pattern such as "comp_%05d.exr" is not a valid AE output name.
_SEQUENCE_TOKEN_RE = re.compile(r"\[(?P<hashes>#+)\]")

#: Digits AE appends after the extension when the name has no frame token,
#: e.g. "comp.exr00835".
_FRAME_SUFFIX_RE = re.compile(r"\d+$")

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


@dataclass(frozen=True)
class ModuleRepair:
    """Output Module write planned by the Repair action."""

    index: int
    file_name: str
    template: str


@dataclass(frozen=True)
class RepairPlan:
    """Writes the Repair action can perform, and what it must leave alone."""

    writes: tuple[ModuleRepair, ...] = ()
    notes: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        """Whether the plan has anything to write."""
        return bool(self.writes)


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
        details = []
        codec = _text(_get(preset, "codec", ""))
        if codec:
            details.append(codec)
        details.extend("." + ext for ext in extensions)
        if details:
            label = "{} ({})".format(label, ", ".join(details))
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
    return next(_matching_presets(module, presets, actual), None)


def _matching_presets(
    module: Any,
    presets: Iterable[Mapping[str, Any]],
    actual: OutputName,
) -> Iterator[Mapping[str, Any]]:
    """Yield matching presets in template, format, then extension order."""
    presets = list(presets)
    module_format = _text(_get(module, "format", ""))
    module_codec = _text(_get(module, "codec", ""))
    module_names = {
        _text(_get(module, "name", "")),
        _text(_get(module, "template", "")),
    }

    for preset in presets:
        if preset["template"] and _text(preset["template"]) in module_names:
            yield preset

    for preset in presets:
        if preset["template"] and _text(preset["template"]) in module_names:
            continue
        if not preset["format"] or preset["format"] != module_format:
            continue
        if preset["codec"] and preset["codec"] != module_codec:
            continue
        yield preset

    if not module_format:
        for preset in presets:
            if (
                preset["template"]
                and _text(preset["template"]) in module_names
            ):
                continue
            if actual.ext and actual.ext in preset["extensions"]:
                yield preset


def validate_output_modules(
    product_name: str,
    modules: Iterable[Any],
    presets: Iterable[Any],
) -> list[OutputProblem]:
    """Check every Output Module against all matching allowed presets.

    An Output Module is valid if any matching preset passes every rule.
    If none passes, report the first matching preset's problems.

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


def creation_name(
    product_name: str,
    module: Any,
    presets: Iterable[Any],
) -> str | None:
    """Return the output file name an Output Module should be created with.

    AYON writes the bare composition name into the Render Queue, so a
    sequence format ends up as `name.exr00835`: After Effects appends the
    frame number after the extension and the render cannot be published.
    Naming from the preset keeps the file name valid from the start, so the
    validation and the extractor only have to deal with renders that were
    set up by hand.

    Only the name is returned: format and codec stay as they are, since
    creating an instance must not change the artist's Output Module.

    Args:
        product_name: Product name of the instance.
        module: Output Module record from the host.
        presets: Allowed presets from project settings.

    Returns:
        File name to write, or `None` when no preset matches and the
        Render Queue should be left alone.
    """
    normalized_presets = [
        _normalize_preset(preset) for preset in presets or []
    ]
    if not normalized_presets:
        return None

    actual = parse_output_name(_get(module, "file_name", "") or "")
    if not actual.name:
        return None

    for candidate in _matching_presets(module, normalized_presets, actual):
        if not _validate_preset(product_name, module, candidate, actual):
            return actual.name

    preset = match_preset(module, normalized_presets, actual)
    if preset is None:
        return None

    return _name_from_pattern(
        product_name, preset, _real_extension(preset, actual)
    )


def build_repair(
    product_name: str,
    modules: Iterable[Any],
    presets: Iterable[Any],
) -> RepairPlan:
    """Plan the Output Module writes needed to fix the reported problems.

    Only modules that fail validation are written, so Repair never touches
    an Output Module the artist already set up correctly. Format and codec
    can only be written through an Output Module template: AE's own
    settings keys differ between versions and locales, so a preset without
    `template` leaves them alone and the note says so.

    Args:
        product_name: Product name of the instance.
        modules: Output Module records from the host.
        presets: Allowed presets from project settings.

    Returns:
        Writes to perform and notes for whatever Repair cannot do.
    """
    normalized_presets = [
        _normalize_preset(preset) for preset in presets or []
    ]
    modules = list(modules or [])
    if not modules:
        return RepairPlan()

    if not normalized_presets:
        return RepairPlan(
            notes=(
                "No output presets are configured, so the Output Module "
                "cannot be repaired automatically.",
            )
        )

    allowed = describe_presets(normalized_presets)
    writes: list[ModuleRepair] = []
    notes: list[str] = []
    for module in modules:
        index = _get(module, "index", 1) or 1
        problems = _validate_module(
            product_name, module, normalized_presets, allowed
        )
        if not problems:
            continue

        actual = parse_output_name(_get(module, "file_name", "") or "")
        preset = match_preset(module, normalized_presets, actual)
        if preset is None:
            preset = normalized_presets[0]

        label = (
            preset["label"]
            or preset["format"]
            or preset["template"]
            or "preset"
        )
        needs_template = any(
            problem.key in ("not_allowed", "format", "codec")
            for problem in problems
        )
        needs_extension = any(
            problem.key == "extension" for problem in problems
        )
        template = preset["template"] if (
            needs_template or needs_extension
        ) else ""
        if needs_template and not template:
            notes.append(
                "Output Module {}: format or codec does not match '{}' and "
                "the preset has no Output Module template, so only the file "
                "name can be repaired.".format(index, label)
            )

        write, note = _plan_name(product_name, index, preset, actual, template)
        writes.append(write)
        if note:
            notes.append(note)

    return RepairPlan(writes=tuple(writes), notes=tuple(notes))


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
    first_problems = None
    for preset in _matching_presets(module, presets, actual):
        problems = _validate_preset(product_name, module, preset, actual)
        if not problems:
            return []
        if first_problems is None:
            first_problems = problems

    if first_problems is None:
        configured = (
            _get(module, "format", "") or actual.ext or "unknown"
        )
        codec = _get(module, "codec", "")
        if codec:
            configured = "{} / {}".format(configured, codec)
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
    return first_problems


def _validate_preset(
    product_name: str,
    module: Any,
    preset: Mapping[str, Any],
    actual: OutputName,
) -> list[OutputProblem]:
    """Check all rules for one matching preset."""
    index = _get(module, "index", 1) or 1
    label = (
        preset["label"] or preset["format"] or preset["template"] or "preset"
    )
    problems: list[OutputProblem] = []

    extensions = preset["extensions"]
    real_extension = _real_extension(preset, actual)
    appended = bool(real_extension) and real_extension != actual.ext
    if appended:
        # AE puts the frame number after the extension when the name has no
        # token, so report that instead of calling '.exr00835' a bad
        # extension - the missing token is what the artist can fix.
        problems.append(
            OutputProblem(
                key="appended",
                message=(
                    "Output Module {} wrote '{}': After Effects put the "
                    "frame number after the extension because the file "
                    "name has no [#####] frame token.".format(
                        index, actual.name
                    )
                ),
                fields={"index": index, "actual": actual.name},
            )
        )
    elif extensions and actual.ext not in extensions:
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
            if not appended:
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
        # Build the name the preset asks for with the same helper naming
        # uses, so a sequence preset without a token in its pattern and a
        # product name with dots are both compared correctly.
        expected_display = _name_from_pattern(
            product_name, preset, actual.ext
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


def _plan_name(
    product_name: str,
    index: int,
    preset: Mapping[str, Any],
    actual: OutputName,
    template: str,
) -> tuple[ModuleRepair, str]:
    """Build the file name to write for one Output Module.

    The extension follows the preset when a template is applied, because
    the template's format decides what AE actually writes. Without a
    template the current extension is kept: renaming '.mov' to '.mp4'
    would only move the failure from validation to extraction.

    Args:
        product_name: Product name of the instance.
        index: Output Module index.
        preset: Normalized preset to write towards.
        actual: Parsed current file name.
        template: Template to apply, empty when none.

    Returns:
        The planned write and a note about what it cannot fix.
    """
    pattern = str(preset["name_pattern"] or PRODUCT_NAME_TOKEN)
    _, pattern_extension = _split_name(pattern)

    note = ""
    if template:
        if preset["extensions"]:
            extension = preset["extensions"][0]
        else:
            extension = pattern_extension
    else:
        # The format decides what AE writes, so only a template may move
        # the extension. Renaming '.mov' to '.mp4' would just move the
        # failure from validation to extraction.
        extension = _real_extension(preset, actual) or pattern_extension
        if not extension and preset["extensions"]:
            # Nothing to preserve, so the preset names the extension.
            extension = preset["extensions"][0]
        if preset["extensions"] and extension not in preset["extensions"]:
            current = "." + extension if extension else "no extension"
            note = (
                "Output Module {} is left with {}, which the preset does "
                "not list ({}). Fix the format, or set a template on the "
                "preset, so Repair can write the extension.".format(
                    index,
                    current,
                    ", ".join("." + ext for ext in preset["extensions"]),
                )
            )

    file_name = _name_from_pattern(product_name, preset, extension)
    write = ModuleRepair(index=index, file_name=file_name, template=template)
    return write, note


def _name_from_pattern(
    product_name: str,
    preset: Mapping[str, Any],
    extension: str,
) -> str:
    """Build a file name from the preset's pattern.

    Args:
        product_name: Product name of the instance.
        preset: Normalized preset.
        extension: Extension to append, without the dot.

    Returns:
        File name with the product name and, for sequence presets, the
        frame token with the configured padding.
    """
    pattern = str(preset["name_pattern"] or PRODUCT_NAME_TOKEN)
    stem, pattern_extension = _split_name(pattern)
    stem = stem.replace(PRODUCT_NAME_TOKEN, product_name or "")

    if preset["sequence"]:
        hashes = "#" * preset["padding"]
        if _SEQUENCE_TOKEN_RE.search(stem):
            stem = _SEQUENCE_TOKEN_RE.sub("[" + hashes + "]", stem)
        else:
            stem = "{}_[{}]".format(stem, hashes)
    elif _SEQUENCE_TOKEN_RE.search(stem):
        # A token in a single file preset is a configuration mistake. The
        # sequence flag wins, otherwise the name it produces is rejected by
        # the preset itself and Repair could never converge.
        stem = _SEQUENCE_TOKEN_RE.sub("", stem).rstrip("_-.")

    extension = extension or pattern_extension
    return stem + ("." + extension if extension else "")


def _real_extension(
    preset: Mapping[str, Any],
    actual: OutputName,
) -> str:
    """Return the extension without the frame number AE appended to it.

    A file name without a `[#####]` token gets the frame number after the
    extension, `comp.exr00835`, so the parsed extension carries it. Only
    strip it when the preset names the extension: a plain '.mp4' must never
    be shortened to '.mp'.

    Args:
        preset: Normalized preset.
        actual: Parsed current file name.

    Returns:
        Extension to write, without the dot.
    """
    extension = actual.ext
    if not extension or not preset["extensions"]:
        return extension

    if extension in preset["extensions"]:
        return extension

    stripped = _FRAME_SUFFIX_RE.sub("", extension)
    if stripped and stripped in preset["extensions"]:
        return stripped

    return extension


def _split_name(text: Any) -> tuple[str, str]:
    """Split a file name into stem and extension, keeping the case.

    Args:
        text: File name.

    Returns:
        Stem and extension without the dot, empty when there is none.
    """
    name = str(text or "").strip()
    stem, separator, extension = name.rpartition(".")
    if not separator or not extension.isalnum():
        return name, ""
    return stem, extension


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
        # Kept as written: `applyTemplate()` of the Repair action needs the
        # name in its original case. Matching folds the case itself.
        "template": str(_get(preset, "template", "") or "").strip(),
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
