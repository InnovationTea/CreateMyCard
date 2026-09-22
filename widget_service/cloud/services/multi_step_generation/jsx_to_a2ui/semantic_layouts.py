"""Model-owned content inside program-owned 2x4 layout shells.

Lower once in the Runner, before compilation and browser measurement. The
runtime and A2UI renderer continue to consume ordinary Card/Stack/Grid only.
"""
from __future__ import annotations

from copy import deepcopy

from .exceptions import ValidationError
from .parser.jsx_ast import JSXElement


LAYOUTS = {
    "top-bottom": ("上下双区", ("title", "primary", "details")),
    "split-panels": ("左右双区", ("left", "right")),
    "main-right-double": ("左内容右侧双槽", ("main", "side-top", "side-bottom")),
    "double-left-main": ("左侧双槽右内容", ("side-top", "side-bottom", "main")),
    "four-blocks": ("四槽宫格", ("top-left", "bottom-left", "top-right", "bottom-right")),
}
VARIANTS = {
    "compact-center": "Sub-118-A 核心居中",
    "compact-title-content": "Sub-118-B 标题单内容",
    "compact-title-primary-secondary": "Sub-118-C 标题双内容",
    "compact-title-content-action": "Sub-118-D 标题内容单按钮",
    "compact-two-column-action": "Sub-118-E 标题双列内容可选按钮",
    "compact-content-two-actions": "Sub-118-F 内容双按钮",
    "wide-center": "Sub-140-A 核心居中",
    "wide-title-content": "Sub-140-B 标题单内容",
    "wide-title-content-action": "Sub-140-C 标题内容单按钮",
    "wide-title-double-progress": "Sub-140-D 标题双列内容可选按钮",
    "wide-title-primary-secondary-action": "Sub-140-F 标题主次内容单按钮",
    "wide-title-primary-secondary": "Sub-140-G 标题双内容",
    "wide-quad-progress": "Sub-140-H 内容四宫格",
    "wide-quad-content": "Sub-140-H 内容四宫格",
    "wide-two-column-action": "Sub-140-I 标题双列内容可选按钮",
    "wide-content-two-actions": "Sub-140-J 内容双按钮",
}
_TITLES = {"SingleLineTitle", "DoubleLineTitle"}
_ACTIONS = {"PillButton", "CardButton", "CircleButton"}


def _children(node: JSXElement) -> list[JSXElement]:
    if any(isinstance(c, str) and c.strip() for c in node.children):
        raise ValidationError(f"<{node.tag}> layout slots accept components, not raw text")
    return node.child_elements()


def _walk(node: JSXElement):
    yield node
    for child in _children(node):
        yield from _walk(child)


def _stack(*children: JSXElement, **props) -> JSXElement:
    return JSXElement("Stack", {"direction": "column", **props}, list(children))


def _title(children: list[JSXElement], width) -> tuple[JSXElement, list[JSXElement]]:
    if not children or children[0].tag not in _TITLES:
        raise ValidationError("titled Region must start with a title, followed by an optional Badge")
    count = 2 if len(children) > 1 and children[1].tag == "Badge" else 1
    return _stack(*children[:count], direction="row" if count == 2 else "column",
                  flex=0, width=width, **({"gap": 8, "align": "center"} if count == 2 else {})), children[count:]


def _content(node: JSXElement) -> JSXElement:
    """Accept one semantic business component; layout containers are program-owned."""
    for item in _walk(node):
        if item.tag in _TITLES | _ACTIONS | {"Card", "Region", "InfoBlock"}:
            raise ValidationError(f"content slot cannot contain <{item.tag}>; use its dedicated layout slot")
        if item.tag in {"Stack", "Grid"}:
            raise ValidationError(
                "semantic Region content cannot contain raw Stack/Grid; choose the Region.variant "
                "whose content slots match the business components, or use NumericRatioStack for "
                "multiple ratio values"
            )
    return node


def _one(region: JSXElement, allowed: set[str] | None = None) -> JSXElement:
    children = _children(region)
    if len(children) != 1 or (allowed is not None and children[0].tag not in allowed):
        expected = sorted(allowed) if allowed else "content group"
        raise ValidationError(
            f"Region slot={region.props.get('slot')!r} requires one {expected}"
        )
    return children[0]


def _region(region: JSXElement) -> JSXElement:
    variant = region.props.get("variant")
    if not isinstance(variant, str) or variant not in VARIANTS:
        raise ValidationError(f"Region slot={region.props.get('slot')!r} requires a documented variant")
    compact = variant.startswith("compact-")
    width, height = (116, 110) if compact else (132, 126)
    title_gap = 4 if compact else 6
    content_gap = 6 if compact else 8
    children = _children(region)
    shell = dict(flex=0, width=width, height=height, gap=0)
    if variant.endswith("center"):
        return _stack(_content(_one(region)), **shell, align="center", justify="center")
    if variant in {"wide-quad-progress", "wide-quad-content"}:
        if len(children) != 4:
            raise ValidationError(f"{variant} requires four content components")
        if variant == "wide-quad-progress" and any(c.tag != "ProgressCircle" for c in children):
            raise ValidationError("wide-quad-progress requires four ProgressCircle components")
        return JSXElement("Grid", {"columns": 2, "rows": "59px 59px", "gap": 8, "width": 132, "height": 126}, [
            _stack(_content(c), width=62, height=59, align="center", justify="center") for c in children
        ])
    if variant in {"compact-two-column-action", "wide-two-column-action"}:
        if not children or children[0].tag != "SingleLineTitle":
            raise ValidationError(f'{variant} requires SingleLineTitle as its first child')
        title, contents = _title(children, width)
        title.props["mb"] = title_gap
        button = None
        if contents and contents[-1].tag == "PillButton":
            button = _stack(contents.pop(), flex=0, width=width, height=36)
        if len(contents) != 2 or any(child.tag != "ProgressCircle" for child in contents):
            raise ValidationError(
                f'{variant} requires a title, two ProgressCircle components, and an optional PillButton'
            )
        if any(child.props.get("size") != "sm" for child in contents):
            raise ValidationError(f'{variant} requires ProgressCircle size="sm"')
        column_width = 54 if compact else 62
        content_row = _stack(
            *[_stack(_content(c), flex=0, width=column_width, height="full",
                     align="center", justify="center") for c in contents],
            direction="row", flex=1, minHeight=0, width=width, gap=8,
        )
        body_children = [content_row] + ([button] if button is not None else [])
        body = _stack(*body_children, flex=1, minHeight=0, width=width,
                      gap=content_gap if button is not None else 0)
        return _stack(title, body, **shell)
    if variant in {"compact-content-two-actions", "wide-content-two-actions"}:
        if len(children) != 3 or any(c.tag != "PillButton" for c in children[1:]):
            raise ValidationError(f"{variant} requires one content slot followed by two PillButtons")
        content_height = 26 if compact else 38
        content = _stack(_content(children[0]), flex=0, width=width, height=content_height)
        buttons = [_stack(c, flex=0, width=width, height=36) for c in children[1:]]
        return _stack(content, *buttons, **{**shell, "gap": content_gap})
    title, contents = _title(children, width)
    title.props["mb"] = title_gap
    button = None
    if variant.endswith("action") or (variant == "wide-title-double-progress" and len(contents) == 3):
        if not contents or contents[-1].tag != "PillButton":
            raise ValidationError(f"{variant} requires a final PillButton in the Action slot")
        button = _stack(contents.pop(), flex=0, width=width, height=36)
    count = 2 if "primary-secondary" in variant or variant == "wide-title-double-progress" else 1
    if len(contents) != count:
        raise ValidationError(
            f"{variant} requires {count} content slots; choose the Region.variant whose documented "
            "content-slot count matches the business components; raw Stack/Grid grouping is not supported"
        )
    contents = [_content(c) for c in contents]
    if variant == "wide-title-double-progress":
        if any(c.tag != "ProgressCircle" for c in contents):
            raise ValidationError("wide-title-double-progress requires two ProgressCircle components")
        body = _stack(*[_stack(c, flex=1, align="center", justify="center") for c in contents],
                      direction="row", flex=1, minHeight=0, width=width, gap=8)
    elif "primary-secondary" in variant:
        body = _stack(
            _stack(contents[0], flex=0 if button else 1, **({} if button else {"minHeight": 0}),
                   width=width, align="flex-start", justify="flex-start"),
            _stack(contents[1], flex=0, width=width, align="flex-start"),
            flex=1, minHeight=0, width=width, gap=2 if button else content_gap,
        )
    else:
        body = _stack(contents[0], flex=1, minHeight=0, width=width,
                      align="flex-start", justify="flex-start" if button else "flex-end")
    if button:
        body.props["mb"] = content_gap
    return _stack(title, body, *([button] if button else []), **shell)


def lower_semantic_card(card: JSXElement) -> tuple[JSXElement, dict]:
    """Return an independent lowered tree and its derived Chinese decision."""
    if card.tag != "Card" or card.props.get("size") != "2x4":
        raise ValidationError("semantic layouts require <Card size=\"2x4\">")
    layout = card.props.get("layout")
    if not isinstance(layout, str) or layout not in LAYOUTS:
        raise ValidationError(f"Card.layout must be one of {list(LAYOUTS)}")
    # Only non-layout Card attributes survive; the existing contract validates them.
    forbidden = set(card.props) - {"size", "appearance", "aria-label", "layout", "flow"}
    if forbidden:
        raise ValidationError(f"semantic Card geometry is program-owned; remove {sorted(forbidden)}")
    flow = card.props.get("flow", "footer")
    if flow not in ("continuous", "footer", "equal") or ("flow" in card.props and layout != "top-bottom"):
        raise ValidationError("Card.flow is only supported by top-bottom: continuous, footer, equal")
    card = deepcopy(card)
    name, slots = LAYOUTS[layout]
    regions = {}
    for region in _children(card):
        slot = region.props.get("slot")
        invalid_slot = region.tag != "Region" or not isinstance(slot, str)
        if not invalid_slot:
            invalid_slot = slot not in slots or slot in regions
        if invalid_slot:
            raise ValidationError(f"{layout} requires unique Region slots {slots}")
        extra = set(region.props) - {"slot", "variant"}
        if extra:
            raise ValidationError(f"Region slot={slot!r} geometry is program-owned; remove {sorted(extra)}")
        regions[slot] = region
    if layout == "top-bottom":
        if "details" not in regions:
            raise ValidationError("top-bottom requires the details Region")
    elif set(regions) != set(slots):
        raise ValidationError(f"{layout} is missing Region slots {sorted(set(slots) - set(regions))}")
    decision = {"layoutPattern": name, "subPattern": {}}
    props = {k: v for k, v in card.props.items() if k not in {"layout", "flow"}}

    def expand(slot):
        region = regions[slot]
        try:
            result = _region(region)
        except ValidationError as exc:
            raise ValidationError(f"Region[{slot}]: {exc}") from exc
        decision["subPattern"]["content" if slot == "main" else slot] = VARIANTS[region.props["variant"]]
        return result

    if layout == "split-panels":
        if any(str(r.props.get("variant", "")).startswith("wide-") for r in regions.values()):
            raise ValidationError("split-panels Type 13 regions require compact 116×110vp variants")
        children = [_stack(expand(slot), flex=0, width=132, height=126,
                           align="center", justify="center", surface="backplate")
                    for slot in slots]
        props.update(direction="row", gap=12)
    elif layout in {"main-right-double", "double-left-main"}:
        if not str(regions["main"].props.get("variant", "")).startswith("wide-"):
            raise ValidationError(f"{layout} main Region requires a wide variant")
        main = expand("main")
        side_slots = ("side-top", "side-bottom")
        side = [_one(regions[slot], {"InfoBlock", "CardButton"}) for slot in side_slots]
        side_column = _stack(*[_stack(c, flex=0, width=132, height=57) for c in side],
                             flex=0, width=132, height=126, gap=12)
        main_column = _stack(main, flex=0, width=132, height=126)
        children = [main_column, side_column] if layout == "main-right-double" else [side_column, main_column]
        props.update(direction="row", gap=12)
    elif layout == "four-blocks":
        grid_slots = ("top-left", "top-right", "bottom-left", "bottom-right")
        cells = [_one(regions[slot], {"InfoBlock", "CardButton"}) for slot in grid_slots]
        children = [JSXElement(
            "Grid",
            {"columns": 2, "rows": "57px 57px", "gap": 12, "width": "full", "height": "full"},
            [_stack(c, flex=0, width=132, height=57) for c in cells],
        )]
        props.update(direction="column", gap=0)
    else:
        title = None
        if "title" in regions:
            title, rest = _title(_children(regions["title"]), "full")
            if rest:
                raise ValidationError("top-bottom title Region only accepts a title and optional Badge")
        primary = _content(_one(regions["primary"])) if "primary" in regions else None
        details = _one(regions["details"], {"TextBlock", "TopTextBottomValue"})
        primary_props = {"flex": 0 if flow == "continuous" else 1}
        detail_props = {"flex": 0 if flow == "footer" else 1}
        # TextBlock needs an explicit finite slot to shrink below its 64vp default.
        if flow == "footer":
            detail_props["height"] = 48 if details.tag == "TextBlock" else 68
        body_children = []
        if primary is not None:
            body_children.append(_stack(
                primary, **primary_props, **({"minHeight": 0} if primary_props["flex"] else {}),
                width="full", align="flex-start", justify="flex-start",
            ))
        body_children.append(_stack(
            details, **detail_props, **({"minHeight": 0} if detail_props["flex"] else {}),
            width="full", align="flex-start", justify="flex-start",
        ))
        body = _stack(
            *body_children, flex=1, minHeight=0, width="full", gap=8,
            align="flex-start", justify="space-between" if flow == "footer" else "flex-start",
        )
        children = ([title] if title is not None else []) + [body]
        # The title always owns a 6vp gap to the first following content slot.
        # The 8vp primary/details gap lives inside ``body`` and is independent.
        props.update(direction="column", gap=6 if title is not None else 0)
    fixed_slots = set(regions) - ({"left", "right"} if layout == "split-panels" else {"main"})
    if any("variant" in regions[slot].props for slot in fixed_slots):
        raise ValidationError("fixed Regions do not take variant")
    return JSXElement("Card", props, children, card.offset), decision
