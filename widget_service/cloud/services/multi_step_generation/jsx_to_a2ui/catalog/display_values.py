from __future__ import annotations

import copy
import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..exceptions import ValidationError

# Keep this list intentionally explicit.  A full match is safer than guessing
# that arbitrary copy surrounding a number is a unit.
_UNIT_PATTERN = re.compile(
    r"\s*([+-]?\d+(?:\.\d+)?)\s*"
    r"(次/分|公里/小时|千米/小时|毫秒|分钟|小时|千卡|公里|千米|"
    r"GB可用|TB|GB|MB|KB|mA|mV|A|V|W|秒|分|天|步|米|克|升|元|次|个|%|％)"
)
_CELSIUS_PATTERN = re.compile(
    r"^\s*([+-]?\d+(?:\.\d+)?)\s*(?:℃|°\s*C)\s*$",
    re.IGNORECASE,
)
_PERCENTAGE_VALUE_PATTERN = re.compile(
    r"^\s*([+-]?\d+(?:\.\d+)?)\s*[%％]?\s*$"
)


@dataclass(frozen=True, slots=True)
class DisplayPart:
    value: Any
    unit: str | None = None

    def data_model_value(self) -> dict[str, Any]:
        result = {"value": copy.deepcopy(self.value)}
        if self.unit is not None:
            result["unit"] = self.unit
        return result


@dataclass(frozen=True, slots=True)
class DisplayPlan:
    mode: str
    raw: Any
    parts: tuple[DisplayPart, ...]

    def data_model_value(self) -> dict[str, Any]:
        result = {
            "mode": self.mode,
            "raw": copy.deepcopy(self.raw),
            "parts": [part.data_model_value() for part in self.parts],
        }
        progress_value = normalize_percentage_value(self.raw)
        if progress_value is not None:
            result["progressValue"] = progress_value
            # JSX percentage components use Math.trunc() for visible numeric
            # text while retaining the original precision for progress bars.
            # Keep both forms in the derived model so A2UI can bind each use
            # to one ordinary path without a FunctionCall.
            result["visiblePercentage"] = math.trunc(progress_value)
        return result

    @property
    def shape(self) -> tuple[str, int, tuple[bool, ...]]:
        """Describe the component-tree shape required by this display plan."""
        return (
            self.mode,
            len(self.parts),
            tuple(part.unit is not None for part in self.parts),
        )


def _number_value(token: str) -> str:
    # These values only feed Text nodes.  Keeping the original token preserves
    # intentional precision and formatting such as ``4.60`` and ``-151``.
    return token


def normalize_display_value(raw_value: Any) -> DisplayPlan:
    """Split a complete formatted metric without ever duplicating its raw unit.

    Celsius is a deliberate product exception: ``29.0 ℃`` becomes one value
    part containing ``"29.0°"`` and no unit part.  Other supported strings must
    be fully parseable as repeated ``number + unit`` groups.  Failed parses use
    one raw-only part.
    """
    if not isinstance(raw_value, str):
        return DisplayPlan("raw", raw_value, (DisplayPart(raw_value),))

    celsius = _CELSIUS_PATTERN.fullmatch(raw_value)
    if celsius is not None:
        # Preserve textual precision (29.0 must not become 29).
        return DisplayPlan("parts", raw_value, (DisplayPart(f"{celsius.group(1)}°"),))

    position = 0
    parts: list[DisplayPart] = []
    while position < len(raw_value):
        match = _UNIT_PATTERN.match(raw_value, position)
        if match is None:
            break
        parts.append(DisplayPart(_number_value(match.group(1)), match.group(2)))
        position = match.end()

    if parts and not raw_value[position:].strip():
        return DisplayPlan("parts", raw_value, tuple(parts))
    return DisplayPlan("raw", raw_value, (DisplayPart(raw_value),))


def normalize_percentage_value(raw_value: Any) -> int | float | None:
    """Return a clamped numeric percentage from a number or numeric text.

    ``68``, ``"68"``, ``"68%"`` and ``"68％"`` all become the number 68.
    Arbitrary copy surrounding the number is intentionally rejected so a
    Progress value never receives formatted business text.
    """
    if isinstance(raw_value, bool):
        return None
    if isinstance(raw_value, int | float):
        number = float(raw_value)
    elif isinstance(raw_value, str):
        match = _PERCENTAGE_VALUE_PATTERN.fullmatch(raw_value)
        if match is None:
            return None
        number = float(match.group(1))
    else:
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    clamped = min(100.0, max(0.0, number))
    return int(clamped) if clamped.is_integer() else clamped


def derived_path_for_source(source_path: str) -> str:
    """Mirror an original JSON Pointer below the private ``/__display`` root."""
    if not isinstance(source_path, str) or not source_path.startswith("/") or source_path == "/":
        raise ValidationError(
            f"source path must be an absolute non-root JSON Pointer; found {source_path!r}"
        )
    return "/__display" + source_path


def _pointer_segments(path: str) -> list[str]:
    if not isinstance(path, str) or not path.startswith("/") or path == "/":
        raise ValidationError(
            f"data path must be an absolute non-root JSON Pointer; found {path!r}"
        )
    segments: list[str] = []
    for raw in path[1:].split("/"):
        if re.search(r"~(?![01])", raw):
            raise ValidationError(f"data path has an invalid JSON Pointer escape: {path!r}")
        segments.append(raw.replace("~1", "/").replace("~0", "~"))
    return segments


def set_pointer_value(root: dict[str, Any], path: str, value: Any) -> None:
    """Set a JSON-Pointer value in a data-model object."""
    segments = _pointer_segments(path)
    node: Any = root
    for index, segment in enumerate(segments):
        last = index == len(segments) - 1
        if isinstance(node, list):
            if not segment.isdigit():
                raise ValidationError(f"data path expects an array index at {path!r}")
            item_index = int(segment)
            while len(node) <= item_index:
                node.append(None)
            if last:
                node[item_index] = copy.deepcopy(value)
                return
            if node[item_index] is None:
                node[item_index] = [] if segments[index + 1].isdigit() else {}
            elif not isinstance(node[item_index], dict | list):
                raise ValidationError(f"data path conflicts with a scalar parent at {path!r}")
            node = node[item_index]
            continue

        if not isinstance(node, dict):
            raise ValidationError(f"data path conflicts with a scalar parent at {path!r}")
        if last:
            node[segment] = copy.deepcopy(value)
            return
        if segment not in node:
            node[segment] = [] if segments[index + 1].isdigit() else {}
        elif not isinstance(node[segment], dict | list):
            raise ValidationError(f"data path conflicts with a scalar parent at {path!r}")
        node = node[segment]


def merge_data_models(*models: dict[str, Any] | None) -> dict[str, Any]:
    """Merge disjoint source and private display models without aliasing them."""
    result: dict[str, Any] = {}

    def merge(target: dict[str, Any], source: dict[str, Any], where: str) -> None:
        for key, value in source.items():
            child_where = f"{where}/{key}"
            if key not in target:
                target[key] = copy.deepcopy(value)
            elif isinstance(target[key], dict) and isinstance(value, dict):
                merge(target[key], value, child_where)
            elif target[key] != value:
                raise ValidationError(f"conflicting data-model values at {child_where}")

    for model in models:
        if model:
            merge(result, model, "")
    return result


def apply_source_update(
    update_data_model: Callable[[str, Any], None],
    source_path: str,
    raw_value: Any,
) -> DisplayPlan:
    """Synchronize one real path and its private display path.

    Hosts must use this entry point for later source updates.  If the returned
    plan's ``shape`` differs from the previous plan, the EmphasizedData
    component tree must also be rebuilt because A2UI paths cannot add/remove
    Text nodes by themselves.
    """
    plan = normalize_display_value(raw_value)
    update_data_model(source_path, copy.deepcopy(raw_value))
    update_data_model(derived_path_for_source(source_path), plan.data_model_value())
    return plan
