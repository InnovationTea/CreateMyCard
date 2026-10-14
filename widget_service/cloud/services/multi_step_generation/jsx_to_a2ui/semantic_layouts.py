"""Model-owned content inside program-owned 2x2 and 2x4 layout shells.

Lower once in the Runner, before compilation and browser measurement. The
runtime and A2UI renderer continue to consume ordinary Card/Stack/Grid only.
"""
from __future__ import annotations

from copy import deepcopy

from .exceptions import ValidationError
from .parser.jsx_ast import JSXElement


LAYOUTS_2X4 = {
    "top-bottom": ("上下双区", ("title", "primary", "details")),
    "split-panels": ("左右双区", ("left", "right")),
    "main-right-double": ("左内容右侧双槽", ("main", "side-top", "side-bottom")),
    "four-blocks": ("四槽宫格", ("top-left", "bottom-left", "top-right", "bottom-right")),
}
LAYOUTS_2X2 = {
    "single": ("单区", ("main",)),
    "double-blocks": ("双信息块", ("top", "bottom")),
}
LAYOUTS = {**LAYOUTS_2X4, **LAYOUTS_2X2}
VARIANTS = {
    "compact-center": "compact-center",
    "compact-title-content": "compact-title-content",
    "compact-title-primary-secondary": "compact-title-primary-secondary",
    "compact-title-content-action": "compact-title-content-action",
    "wide-center": "wide-center",
    "wide-title-content": "wide-title-content",
    "wide-title-content-action": "wide-title-content-action",
    "wide-title-double-progress": "wide-title-double-progress",
    "wide-title-primary-secondary-action": "wide-title-primary-secondary-action",
    "wide-title-primary-secondary": "wide-title-primary-secondary",
    "wide-quad-progress": "wide-quad-progress",
}
SPLIT_PANEL_WIDE_VARIANTS = frozenset({
    "wide-title-double-progress",
    "wide-quad-progress",
})
VARIANT_2X2_LAYOUT_NAMES = {
    "wide-center": "核心居中",
    "wide-title-content": "标题单内容",
    "wide-title-primary-secondary": "标题双内容",
    "wide-quad-content": "内容四宫格",
    "wide-title-content-action": "标题内容单按钮",
    "wide-title-primary-secondary-action": "标题主次内容单按钮",
    "wide-two-column-action": "标题双列内容可选按钮",
    "wide-title-anchor-action": "标题锚点内容",
    "wide-content-two-actions": "紧凑内容双按钮",
}
_TITLES = {"SingleLineTitle", "DoubleLineTitle"}
_ACTIONS = {"PillButton", "CardButton", "CircleButton"}
_DETAILS_ONLY = {"TextBlock", "TopTextBottomValue"}


def _minimum_content_height(node: JSXElement) -> int | None:
    """Conservative rendered-height floor for the tight 2x2 titled Action slot."""
    if node.tag == "EmphasizedData":
        return 32
    if node.tag == "EmphasisText":
        return 42 if node.props.get("secondaryText") else 24
    if node.tag == "SecondaryBody":
        items = node.props.get("items")
        if not isinstance(items, list) or not items:
            return None
        if len(items) <= 2:
            return 19
        rows = (len(items) + 1) // 2
        return rows * 16 + (rows - 1) * 2
    if node.tag == "TableText":
        items = node.props.get("items")
        return len(items) * 18 if isinstance(items, list) and items else None
    return None


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


def _content(
    node: JSXElement,
    *,
    allow_data_display: bool = False,
    allow_progress_circle: bool = False,
) -> JSXElement:
    """Accept one semantic business component; layout containers are program-owned."""
    for item in _walk(node):
        if item.tag in _TITLES | _ACTIONS | {"Card", "Region", "InfoBlock", "Badge"}:
            raise ValidationError(f"content slot cannot contain <{item.tag}>; use its dedicated layout slot")
        if item.tag == "DataDisplay" and not allow_data_display:
            raise ValidationError("DataDisplay is only allowed in a center Region.variant")
        if item.tag == "ProgressCircle" and not allow_progress_circle:
            raise ValidationError(
                "ProgressCircle is only allowed in the documented two- or four-circle Region.variant"
            )
        if item.tag in _DETAILS_ONLY:
            raise ValidationError(
                f"<{item.tag}> is only allowed in the 2x4 top-bottom details Region"
            )
        if item.tag in {"Stack", "Grid"}:
            raise ValidationError(
                "semantic Region content cannot contain raw Stack/Grid; choose the Region.variant "
                "whose content slots match the business components, or use NumericRatioStack for "
                "multiple ratio values"
            )
    return node


def _validate_model_component_limits(card: JSXElement) -> None:
    """Apply model-facing Badge and InfoBlock limits without changing legacy JSX.

    The lower-level converter still accepts older multi-ID JSX. Semantic cards
    use the narrower model-facing contract so extra facts must find another slot.
    """
    for node in _walk(card):
        if node.tag == "Badge":
            data_ids = node.props.get("dataIds")
            value_id = data_ids.get("value") if isinstance(data_ids, dict) else None
            if not isinstance(value_id, str) or not value_id.strip():
                raise ValidationError(
                    "<Badge> must bind one real count through dataIds.value "
                    "and immediately follow its collection title"
                )
        if node.tag != "InfoBlock":
            continue
        data_ids = node.props.get("dataIds")
        if not isinstance(data_ids, dict):
            continue  # The ordinary component contract reports malformed dataIds.
        secondary = data_ids.get("secondaryText")
        if isinstance(secondary, list):
            raise ValidationError(
                "<InfoBlock> dataIds.secondaryText accepts one data ID only; "
                "use another component or layout slot for additional facts"
            )


def _one(region: JSXElement, allowed: set[str] | None = None) -> JSXElement:
    children = _children(region)
    if len(children) != 1 or (allowed is not None and children[0].tag not in allowed):
        expected = sorted(allowed) if allowed else "content group"
        raise ValidationError(
            f"Region slot={region.props.get('slot')!r} requires one {expected}"
        )
    return children[0]


def _region(region: JSXElement, *, card_size: str = "2x4") -> JSXElement:
    variant = region.props.get("variant")
    allowed_variants = set(VARIANT_2X2_LAYOUT_NAMES) if card_size == "2x2" else set(VARIANTS)
    if not isinstance(variant, str) or variant not in allowed_variants:
        raise ValidationError(f"Region slot={region.props.get('slot')!r} requires a documented variant")
    if card_size == "2x2" and variant not in VARIANT_2X2_LAYOUT_NAMES:
        raise ValidationError(f"2x2 Region does not support variant {variant!r}")
    compact = variant.startswith("compact-")
    if card_size == "2x2":
        width, height = 126, 126
        title_gap, content_gap = 6, 8
    else:
        width, height = (116, 110) if compact else (132, 126)
        title_gap = 4 if compact else 6
        content_gap = 6 if compact else 8
    children = _children(region)
    if card_size == "2x4":
        compact_single = [child for child in children if child.tag == "ProgressCircleSingle"]
        if any(child.props.get("size") != "compact" for child in compact_single):
            raise ValidationError(
                f'{variant} requires ProgressCircleSingle size="compact" in 2x4 content Regions'
            )
    shell = dict(flex=0, width=width, height=height, gap=0)
    if variant.endswith("center"):
        content = _one(region)
        if card_size == "2x2" and content.tag != "DataDisplay":
            raise ValidationError("2x2 wide-center requires exactly one DataDisplay")
        return _stack(
            _content(content, allow_data_display=True),
            **shell,
            align="center",
            justify="center",
        )
    if variant in {"wide-quad-progress", "wide-quad-content"}:
        if len(children) != 4:
            raise ValidationError(f"{variant} requires four content components")
        if any(c.tag != "ProgressCircle" for c in children):
            raise ValidationError(f"{variant} requires four ProgressCircle components")
        if any(c.props.get("size") != "sm" for c in children):
            raise ValidationError(f'{variant} requires ProgressCircle size="sm"')
        cell_width, cell_height = (59, 59) if card_size == "2x2" else (62, 59)
        return JSXElement("Grid", {
            "columns": 2,
            "rows": f"{cell_height}px {cell_height}px",
            "gap": 8,
            "width": width,
            "height": height,
        }, [
            _stack(
                _content(c, allow_progress_circle=True),
                width=cell_width,
                height=cell_height,
                align="center",
                justify="center",
            )
            for c in children
        ])
    if variant == "wide-two-column-action":
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
        column_width = 59 if card_size == "2x2" else (54 if compact else 62)
        content_row = _stack(
            *[_stack(_content(c, allow_progress_circle=True), flex=0, width=column_width, height="full",
                     align="center", justify="center") for c in contents],
            direction="row", flex=1, minHeight=0, width=width, gap=8,
        )
        body_children = [content_row] + ([button] if button is not None else [])
        body = _stack(*body_children, flex=1, minHeight=0, width=width,
                      gap=content_gap if button is not None else 0)
        return _stack(title, body, **shell)
    if variant == "wide-content-two-actions":
        if len(children) != 3 or any(c.tag != "PillButton" for c in children[1:]):
            raise ValidationError(f"{variant} requires one content slot followed by two PillButtons")
        if card_size == "2x2" and children[0].tag == "ProgressCircleSingle":
            raise ValidationError(
                "2x2 wide-content-two-actions has a 38vp content slot, but "
                "ProgressCircleSingle needs at least 44vp even with size=\"compact\"; "
                "choose a shorter text/value component while preserving both Actions"
            )
        content_height = 38 if card_size == "2x2" else (26 if compact else 38)
        content = _stack(_content(children[0]), flex=0, width=width, height=content_height)
        buttons = [_stack(c, flex=0, width=width, height=36) for c in children[1:]]
        return _stack(content, *buttons, **{**shell, "gap": content_gap})
    if variant == "wide-title-anchor-action":
        if len(children) != 4 or children[-1].tag != "CircleButton":
            raise ValidationError(
                "wide-title-anchor-action requires a title, primary content, secondary content, "
                "and a final CircleButton"
            )
        title, contents = _title(children, width)
        title.props["mb"] = title_gap
        if len(contents) != 3 or contents[-1].tag != "CircleButton":
            raise ValidationError(
                "wide-title-anchor-action requires two content components followed by CircleButton"
            )
        primary, secondary = (_content(contents[0]), _content(contents[1]))
        action = contents[2]
        bottom = _stack(
            _stack(secondary, flex=1, minWidth=0, height=40,
                   align="flex-start", justify="flex-end"),
            _stack(action, flex=0, width=40, height=40, align="center", justify="center"),
            direction="row", flex=0, width=width, height=40, gap=8, align="flex-end",
        )
        body = _stack(
            _stack(primary, flex=1, minHeight=0, width=width),
            bottom,
            flex=1, minHeight=0, width=width, gap=8,
        )
        return _stack(title, body, **shell)
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
    contents = [
        _content(c, allow_progress_circle=variant == "wide-title-double-progress")
        for c in contents
    ]
    if card_size == "2x2" and variant == "wide-title-primary-secondary-action":
        minimums = [_minimum_content_height(content) for content in contents]
        # 126 - title(16) - title gap(6) - button(36) - button gap(8)
        # - inter-content gap(2) = 58vp. Keep 2vp of breathing room for
        # font metrics and segmented-text measurement in Chromium.
        if all(value is not None for value in minimums) and sum(minimums) > 56:
            raise ValidationError(
                "2x2 wide-title-primary-secondary-action has at most 56vp safe "
                f"height for its two content slots, but these components need at least {sum(minimums)}vp; "
                "use a denser component or another variant while preserving the Action"
            )
    if variant == "wide-title-double-progress":
        if any(c.tag != "ProgressCircle" for c in contents):
            raise ValidationError("wide-title-double-progress requires two ProgressCircle components")
        if any(c.props.get("size") != "sm" for c in contents):
            raise ValidationError('wide-title-double-progress requires ProgressCircle size="sm"')
        body = _stack(
            *[
                _stack(
                    c,
                    flex=1,
                    align="center",
                    justify="center",
                )
                for c in contents
            ],
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
    card_size = card.props.get("size")
    if card.tag != "Card" or card_size not in {"2x2", "2x4"}:
        raise ValidationError('semantic layouts require <Card size="2x2"> or <Card size="2x4">')
    layouts = LAYOUTS_2X2 if card_size == "2x2" else LAYOUTS_2X4
    layout = card.props.get("layout")
    if not isinstance(layout, str) or layout not in layouts:
        raise ValidationError(f"Card.layout for {card_size} must be one of {list(layouts)}")
    # Only non-layout Card attributes survive; the existing contract validates them.
    forbidden = set(card.props) - {"size", "appearance", "aria-label", "layout", "flow"}
    if forbidden:
        raise ValidationError(f"semantic Card geometry is program-owned; remove {sorted(forbidden)}")
    flow = card.props.get("flow", "footer")
    if flow not in ("continuous", "footer", "equal") or ("flow" in card.props and layout != "top-bottom"):
        raise ValidationError("Card.flow is only supported by top-bottom: continuous, footer, equal")
    card = deepcopy(card)
    _validate_model_component_limits(card)
    name, slots = layouts[layout]
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
    if card_size == "2x2":
        if set(regions) != set(slots):
            raise ValidationError(f"{layout} is missing Region slots {sorted(set(slots) - set(regions))}")
    elif layout == "top-bottom":
        if set(regions) != set(slots):
            raise ValidationError(
                f"top-bottom requires Region slots {slots}; "
                f"missing {sorted(set(slots) - set(regions))}"
            )
    elif set(regions) != set(slots):
        raise ValidationError(f"{layout} is missing Region slots {sorted(set(slots) - set(regions))}")
    decision = {"layoutPattern": name, "subPattern": {}} if card_size == "2x4" else {"layoutPattern": name}
    props = {k: v for k, v in card.props.items() if k not in {"layout", "flow"}}

    def expand(slot):
        region = regions[slot]
        try:
            result = _region(region, card_size=card_size)
        except ValidationError as exc:
            raise ValidationError(f"Region[{slot}]: {exc}") from exc
        if card_size == "2x4":
            decision["subPattern"]["content" if slot == "main" else slot] = VARIANTS[region.props["variant"]]
        return result

    if card_size == "2x2":
        if layout == "single":
            variant = regions["main"].props.get("variant")
            if variant not in VARIANT_2X2_LAYOUT_NAMES:
                raise ValidationError(f"2x2 single layout does not support variant {variant!r}")
            children = [expand("main")]
            decision["layoutPattern"] = VARIANT_2X2_LAYOUT_NAMES[variant]
            props.update(direction="column", gap=0)
        else:
            if any("variant" in regions[slot].props for slot in slots):
                raise ValidationError("2x2 double-blocks fixed Regions do not take variant")
            blocks = [_one(regions[slot], {"InfoBlock"}) for slot in slots]
            children = [_stack(block, flex=0, width=134, height=63) for block in blocks]
            props.update(direction="column", padding=8, gap=8)
    elif layout == "split-panels":
        variants = {
            slot: str(regions[slot].props.get("variant", ""))
            for slot in slots
        }
        wide = [
            (slot, variant)
            for slot, variant in variants.items()
            if variant.startswith("wide-")
        ]
        if len(wide) > 1:
            raise ValidationError("split-panels allows at most one wide Region")
        unsupported = [
            variant for _, variant in wide
            if variant not in SPLIT_PANEL_WIDE_VARIANTS
        ]
        if unsupported:
            raise ValidationError(
                "split-panels wide Region only supports "
                "wide-title-double-progress or wide-quad-progress"
            )
        children = [
            _stack(
                expand(slot),
                flex=0,
                width=132,
                height=126,
                align="center",
                justify="center",
                **(
                    {}
                    if variants[slot] in SPLIT_PANEL_WIDE_VARIANTS
                    else {"surface": "backplate"}
                ),
            )
            for slot in slots
        ]
        props.update(direction="row", gap=12)
    elif layout == "main-right-double":
        if not str(regions["main"].props.get("variant", "")).startswith("wide-"):
            raise ValidationError(f"{layout} main Region requires a wide variant")
        main = expand("main")
        side_slots = ("side-top", "side-bottom")
        side = [_one(regions[slot], {"InfoBlock", "CardButton"}) for slot in side_slots]
        side_kinds = tuple(item.tag for item in side)
        allowed_side_kinds = {
            ("InfoBlock", "InfoBlock"),
            ("InfoBlock", "CardButton"),
            ("CardButton", "CardButton"),
        }
        if side_kinds not in allowed_side_kinds:
            raise ValidationError(
                f"{layout} fixed side Regions allow two InfoBlock components, "
                "an upper InfoBlock with a lower CardButton, or two CardButton components"
            )
        side_column = _stack(*[_stack(c, flex=0, width=132, height=57) for c in side],
                             flex=0, width=132, height=126, gap=12)
        main_column = _stack(main, flex=0, width=132, height=126)
        children = [main_column, side_column]
        props.update(direction="row", gap=12)
    elif layout == "four-blocks":
        grid_slots = ("top-left", "top-right", "bottom-left", "bottom-right")
        cells = [_one(regions[slot], {"InfoBlock", "CardButton"}) for slot in grid_slots]
        if cells[0].tag != cells[2].tag or cells[1].tag != cells[3].tag:
            raise ValidationError(
                "four-blocks mixed InfoBlock/CardButton modules must keep each component type "
                "in one complete column"
            )
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
    if card_size == "2x4":
        fixed_slots = set(regions) - ({"left", "right"} if layout == "split-panels" else {"main"})
        if any("variant" in regions[slot].props for slot in fixed_slots):
            raise ValidationError("fixed Regions do not take variant")
    return JSXElement("Card", props, children, card.offset), decision
