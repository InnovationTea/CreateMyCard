"""SecondaryBody layout snapshots from the existing JSX browser validation.

Snapshots describe the measured source and initial values, not a live resize
algorithm. Invalid/stale snapshots are infrastructure errors, not JSX repairs.
"""
from __future__ import annotations

import hashlib
import math
from decimal import Decimal

from .exceptions import A2UIProtocolOutputError
from .parser.jsx_ast import JSXElement


def _secondary_bodies(root: JSXElement) -> list[JSXElement]:
    nodes = [root] if root.tag == "SecondaryBody" else []
    for child in root.child_elements():
        nodes.extend(_secondary_bodies(child))
    return nodes


def _display(value: object) -> str:
    if type(value) in (int, float):
        # React renders JSON numbers as JavaScript Numbers, including exponent
        # spelling and integers beyond the exactly representable range.
        value = float(value)
        if value == 0:
            return "0"
        if 1e-6 <= abs(value) < 1e21:
            rendered = format(Decimal(str(value)), "f")
            return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered
        return str(value).replace("e-0", "e-").replace("e+0", "e+")
    return str(value)


def secondary_body_layouts(
    source: str, name: str, root: JSXElement, snapshot: object,
) -> dict[int, dict]:
    if snapshot is None:
        return {}

    def require(condition: bool, message: str) -> None:
        if not condition:
            raise A2UIProtocolOutputError(f"rendered SecondaryBody layout: {message}")

    require(isinstance(snapshot, dict), "snapshot must be an object")
    require(snapshot.get("version") == 1, "unsupported snapshot version")
    require(snapshot.get("componentName") == name, "component does not match")
    require(snapshot.get("sourceHash") == hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "source changed after measurement")
    nodes = _secondary_bodies(root)
    entries = snapshot.get("secondaryBodies")
    require(isinstance(entries, list) and len(entries) == len(nodes), "component count does not match")
    layouts: dict[int, dict] = {}
    seen: set[int] = set()
    for entry in entries:
        require(isinstance(entry, dict), "entry must be an object")
        index = entry.get("index")
        require(type(index) is int and 0 <= index < len(nodes) and index not in seen,
                "component identity is invalid or duplicated")
        seen.add(index)
        node = nodes[index]
        items = node.props.get("items", [])
        sizes = entry.get("rowSizes")
        require(isinstance(sizes, list) and bool(sizes)
                and all(type(size) is int and size in (1, 2) for size in sizes)
                and sum(sizes) == len(items), "row groups do not cover the fields")
        for key in ("width", "fontSize", "lineHeight", "rowGap"):
            value = entry.get(key)
            require(type(value) in (int, float) and math.isfinite(value)
                    and (value >= 0 if key == "rowGap" else value > 0), f"invalid {key}")
        require(entry["fontSize"] in (12, 14), "unexpected font size")
        expected_text = [str(item.get("label") or "") + _display(item["value"]) for item in items]
        require(entry.get("fieldTexts") == expected_text, "display values changed after measurement")
        layouts[id(node)] = entry
    return layouts
