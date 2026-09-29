"""Browser-evidenced omission of decorative InfoBlock icons.

This only rewrites semantic JSX after the browser proves that InfoBlock text
is clipped. Progress circles are information-bearing and are never removed.
"""

from __future__ import annotations

from typing import Any

if "." in (__package__ or ""):
    from ..jsx_to_a2ui.parser import JSXElement, extract_card_functions
else:
    from jsx_to_a2ui.parser import JSXElement, extract_card_functions

from .workflow import _serialize_jsx


_TEXT_CLASSES = frozenset({"info-block-primary-value", "info-block-secondary"})
_RENDER_SLOT_ORDER = {
    "single": ("main",),
    "double-blocks": ("top", "bottom"),
    "split-panels": ("left", "right"),
    "main-right-double": ("main", "side-top", "side-bottom"),
    "four-blocks": ("top-left", "top-right", "bottom-left", "bottom-right"),
    "top-bottom": ("title", "primary", "details"),
}


def info_block_text_clipping(report: dict[str, Any]) -> dict[int, float]:
    """Return visible text-width deficits keyed by rendered InfoBlock index."""

    browser = report.get("browser")
    clips = browser.get("horizontalClipping") if isinstance(browser, dict) else None
    if not isinstance(clips, list):
        return {}
    deficits: dict[int, float] = {}
    for item in clips:
        if not isinstance(item, dict) or item.get("component") != "InfoBlock":
            continue
        index = item.get("componentIndex")
        element = item.get("element")
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            continue
        classes = str(element.get("className") or "").split() if isinstance(element, dict) else []
        if not _TEXT_CLASSES.intersection(classes):
            continue
        required = item.get("requiredSize")
        available = item.get("availableSize")
        if not isinstance(required, dict) or not isinstance(available, dict):
            continue
        try:
            deficit = float(required["width"]) - float(available["width"])
        except (KeyError, TypeError, ValueError):
            continue
        if deficit > 1:
            deficits[index] = max(deficits.get(index, 0), deficit)
    return deficits


def _walk(node: JSXElement):
    yield node
    for child in node.children:
        if isinstance(child, JSXElement):
            yield from _walk(child)


def _info_blocks_in_render_order(card: JSXElement) -> list[JSXElement]:
    slots = _RENDER_SLOT_ORDER.get(str(card.props.get("layout") or ""))
    if slots is None:
        return []
    regions = {
        str(child.props.get("slot")): child
        for child in card.children
        if isinstance(child, JSXElement) and child.tag == "Region"
    }
    if set(regions) != set(slots):
        return []
    return [
        node
        for slot in slots
        for node in _walk(regions[slot])
        if node.tag == "InfoBlock"
    ]


def omit_clipped_info_block_icons(
    semantic_source: str | None,
    component_name: str,
    report: dict[str, Any],
) -> tuple[str | None, tuple[int, ...]]:
    """Remove only icons belonging to clipped InfoBlocks; keep all text/IDs."""

    deficits = info_block_text_clipping(report)
    if not deficits or not semantic_source:
        return None, ()
    cards = extract_card_functions(semantic_source)
    card = cards.get(component_name)
    if card is None:
        return None, ()
    blocks = _info_blocks_in_render_order(card)
    removed: list[int] = []
    for index in sorted(deficits):
        if index >= len(blocks):
            continue
        visual = blocks[index].props.get("visual")
        if isinstance(visual, dict) and visual.get("type") == "icon":
            blocks[index].props.pop("visual", None)
            removed.append(index)
    if not removed:
        return None, ()
    return _serialize_jsx(card), tuple(removed)


def icon_omission_improves_text(
    before: dict[str, Any], after: dict[str, Any], removed: tuple[int, ...],
) -> bool:
    """Require a clean revalidation and less clipping in every changed block."""

    if not after.get("ok") or not removed:
        return False
    old = info_block_text_clipping(before)
    new = info_block_text_clipping(after)
    return all(
        index in old and new.get(index, 0) + 0.5 < old[index]
        for index in removed
    )
