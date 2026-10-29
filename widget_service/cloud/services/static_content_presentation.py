"""按已接受展示角色构造有限候选，不解析用户语义或猜测字段边界。"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StaticPresentationTrial:
    source: str | None
    attempted: int
    errors: tuple[str, ...]


@dataclass(frozen=True)
class _DisplayObject:
    facts: tuple[dict[str, Any], ...]
    identity: str | None = None

    def text(self, roles: set[str] | None = None, *, rendered_title: str = "") -> str:
        parts = []
        for fact in self.facts:
            if roles is not None and fact.get("displayRole", "body") not in roles:
                continue
            text = fact.get("text", "")
            if rendered_title and text == rendered_title:
                continue
            parts.append(text)
        return "；".join(parts)

    def has(self, roles: set[str]) -> bool:
        return any(fact.get("displayRole") in roles for fact in self.facts)

    def caption(self) -> str:
        title = self.text({"title", "label"})
        if self.identity and self.identity not in self.text():
            return " · ".join(part for part in (self.identity, title) if part)
        return title


def _display_objects(plan, omitted_indexes):
    facts = plan.get("info_required", [])
    omitted = set(omitted_indexes)
    objects = []
    shared = []
    for group in plan.get("contentGroups", []):
        selected = []
        for index in group.get("factIndexes", []):
            if index in omitted:
                continue
            fact = facts[index]
            if isinstance(fact.get("text"), str):
                selected.append(fact)
        if selected:
            target = objects if group.get("kind") == "object" else shared
            target.append(_DisplayObject(tuple(selected), group.get("identity")))
    return objects, shared


def _comparison(item: _DisplayObject) -> dict[str, Any]:
    primary = item.text({"value"})
    title = item.text({"title"})
    if not primary and not title:
        return {"primaryText": item.text()}
    result: dict[str, Any] = {"primaryText": primary or title}
    secondary = item.caption() if primary else item.identity or item.text({"label"})
    if secondary:
        result["secondaryText"] = secondary
    details = item.text({"body", "leading", "trailing", "detail"})
    if details:
        result["details"] = [details]
    return result


def _parts(item: _DisplayObject, *, split_identity: bool = False) -> tuple[str, str]:
    primary = item.caption()
    if primary:
        secondary = item.text({"body", "value", "leading", "trailing", "detail"})
    else:
        primary = item.facts[0].get("text", "")
        secondary = _DisplayObject(item.facts[1:]).text()
        if item.identity and item.identity not in primary:
            primary = item.identity + " · " + primary
    protected = any(
        fact.get("preserveVerbatim") or fact.get("protectedTexts") for fact in item.facts
    )
    if protected:
        split_identity = False
    if split_identity and not secondary and item.identity:
        text = item.text()
        if text.startswith(item.identity):
            secondary = text.removeprefix(item.identity).lstrip(" ：:；;·")
        elif text.endswith(item.identity):
            secondary = text.removesuffix(item.identity).rstrip(" ：:；;·")
        elif item.identity not in text:
            secondary = text
        if secondary:
            primary = item.identity
    return primary, secondary


def _variants(objects: list[_DisplayObject], size: str, presentation: str, *, fallback=False):
    variants = []
    if len(objects) == 1:
        values = []
        for fact in objects[0].facts:
            if fact.get("displayRole", "body") not in {"title", "label"}:
                values.append(fact.get("text", ""))
        if values:
            props = {"mainText": values[0]}
            if len(values) > 1:
                props["secondaryText"] = "；".join(values[1:])
            variants.append(("content", "EmphasisText", props))
    single_items = []
    list_items = []
    for item in objects:
        primary, secondary = _parts(item, split_identity=fallback)
        if not secondary:
            break
        single_items.append({"text": primary, "assist": secondary})
        list_items.append({"primaryText": primary, "secondaryText": secondary})
    if len(single_items) == len(objects):
        variants.append(("rows", "SingleLineList", {"items": single_items}))
        if 2 <= len(list_items) <= 3:
            variants.append(("records", "TextList", {"items": list_items}))
    if size == "2x4" and 2 <= len(objects) <= 4:
        if presentation == "comparison" or fallback:
            variants.append(("comparison", "ComparisonGroup",
                             {"items": [_comparison(item) for item in objects]}))
    if presentation == "comparison" and not fallback:
        variants = [variant for variant in variants if variant[0] == "comparison"]
    preferred = presentation
    if presentation == "auto":
        styles = {"TextList": "records", "SingleLineList": "rows",
                  "EmphasisText": "content", "ComparisonGroup": "comparison"}
        for item in objects:
            for fact in item.facts:
                hints = fact.get("componentHints", [])
                if hints and hints[0] in styles:
                    preferred = styles.get(hints[0])
                    break
    variants.sort(key=lambda variant: variant[0] != preferred)
    return variants


def _encode(
    component: str, props: dict, shared: list[_DisplayObject], size: str, *, heading: str = "",
    note_index: int | None = None, shared_header: bool = False,
) -> str | None:
    titles = []
    notes = []
    shared_texts = []
    for item in shared:
        for fact in item.facts:
            if shared_header and fact.get("displayRole", "body") not in {"title", "body"}:
                return None
            target = titles if fact.get("displayRole") == "title" else notes
            target.append(fact.get("text", ""))
            shared_texts.append(fact.get("text", ""))
    if shared_header:
        if not titles or not notes:
            return None
        titles = shared_texts
        notes = []
    if not titles and heading:
        titles.append(heading)
    items = props.get("items")
    four_item_comparison = component == "ComparisonGroup" and isinstance(items, list)
    if four_item_comparison and len(items) == 4 and titles:
        return None
    if notes:
        if component == "EmphasisText":
            supplemental = props.get("secondaryText")
            values = [supplemental] if supplemental else []
            props = {**props, "secondaryText": "；".join([*values, *notes])}
        else:
            if not isinstance(items, list) or note_index is None:
                return None
            if not 0 <= note_index < len(items):
                return None
            item = items[note_index]
            if not isinstance(item, dict):
                return None
            key = "assist" if component == "SingleLineList" else "secondaryText"
            supplemental = item.get(key)
            if supplemental is not None and not isinstance(supplemental, str):
                return None
            values = [supplemental] if supplemental else []
            updated_items = copy.deepcopy(items)
            updated_items[note_index][key] = "；".join([*values, *notes])
            props = {**props, "items": updated_items}
    children = []
    rows = []
    if titles:
        children.append("header")
        rows.append(["header", "SingleLineTitle", {"title": "；".join(titles)}])
    children.append("body")
    rows.append(["body", component, props])
    prefix = "S" if size == "2x2" else "W"
    root = ["root", "Layout", {"layout": f"{prefix}-static-content"}, children]
    return "\n".join(json.dumps(row, ensure_ascii=False)
                      for row in [root, *rows, ["/state/ready", True]])


def _candidate_sources(
    plan: dict, size: str, omitted_indexes: tuple[int, ...], *, fallback=False,
    shared_header=False,
) -> list[str]:
    objects, shared = _display_objects(plan, omitted_indexes)
    if not objects:
        return []
    variants = _variants(objects, size, plan.get("presentationStyle", "auto"), fallback=fallback)
    sources = []
    for _style, component, props in variants:
        heading = ""
        if component == "EmphasisText" and len(objects) == 1:
            heading = objects[0].caption()
        source = _encode(
            component, props, shared, size, heading=heading, shared_header=shared_header,
        )
        if source is not None:
            sources.append(source)
        elif fallback and component != "EmphasisText" and not shared_header:
            items = props.get("items")
            if not isinstance(items, list):
                continue
            for index in reversed(range(len(items))):
                source = _encode(component, props, shared, size, note_index=index)
                if source is not None:
                    sources.append(source)
    return sources


def static_presentation_candidates(
    plan: dict[str, Any], size: str, omitted_indexes: tuple[int, ...] = (),
    *, include_fallback: bool = False,
) -> tuple[str, ...]:
    facts = plan.get("info_required", [])
    if any("actionId" in fact for fact in facts):
        return ()
    sources = _candidate_sources(plan, size, omitted_indexes)
    optional = list(omitted_indexes)
    for index, fact in enumerate(facts):
        if fact.get("priority") != "should":
            continue
        if fact.get("protectedTexts") or fact.get("preserveVerbatim"):
            continue
        if index not in optional:
            optional.append(index)
    if len(optional) > len(omitted_indexes):
        sources.extend(_candidate_sources(plan, size, tuple(optional)))
    if include_fallback:
        # 原已验证候选（含原可选省略）保持优先，只在其均失败后验证额外无损组合。
        sources.extend(_candidate_sources(plan, size, omitted_indexes, fallback=True))
        if len(optional) > len(omitted_indexes):
            sources.extend(_candidate_sources(plan, size, tuple(optional), fallback=True))
        # 公共说明只能在所有旧候选之后尝试已有标题；完整字号容量检查仍由调用方执行。
        sources.extend(_candidate_sources(
            plan, size, omitted_indexes, fallback=True, shared_header=True,
        ))
        if len(optional) > len(omitted_indexes):
            sources.extend(_candidate_sources(
                plan, size, tuple(optional), fallback=True, shared_header=True,
            ))
    return tuple(dict.fromkeys(sources))


def trial_static_presentation(
    plan: dict[str, Any], query: str, size: str
) -> StaticPresentationTrial:
    from services.card_validation import CompactDslValidationError, validate_compact_dsl
    from services.compact_high_level_components import CompactDslConversionError
    from services.static_content_components import complete_static_text_trial

    if any("actionId" in fact for fact in plan.get("info_required", [])):
        return StaticPresentationTrial(None, 0, ())
    errors = []
    attempted = 0
    original_sources = set(static_presentation_candidates(plan, size))
    for source in static_presentation_candidates(plan, size, include_fallback=True):
        attempted += 1
        try:
            with complete_static_text_trial(source not in original_sources):
                validate_compact_dsl(
                    source,
                    task_spec={
                        "userQuery": query, "size": size,
                        "dataModelSchema": {"data": {}},
                        "eventCandidates": [], "assetCandidates": [],
                    },
                    card_spec={"suggestSize": size}, compact_plan=plan,
                    layout_scope=f"{'S' if size == '2x2' else 'W'}-static-content-guided",
                )
        except (CompactDslValidationError, CompactDslConversionError) as exc:
            message = str(exc)
            if message not in errors:
                errors.append(message)
        else:
            from services.card_validation.compact_validation.semantic.static_content import (
                static_fact_coverage,
            )

            omitted = []
            for coverage in static_fact_coverage(source, plan):
                if not coverage.visible:
                    omitted.append(coverage.fact_index)
            feedback: tuple[str, ...] = ()
            if omitted:
                message = (
                    f"完整内容尚未排下，当前合法候选省略了事实索引{omitted}。"
                    "请优先精简冗余措辞以保留这些信息；必要适用范围、条件和例外不能降为可选。"
                    "原候选保留供后续DSL使用，不代表必须接受信息损失。"
                )
                feedback = (message, *errors)
            return StaticPresentationTrial(source, attempted, feedback)
    if not attempted:
        count = sum(group.get("kind") == "object" for group in plan.get("contentGroups", []))
        errors.append(
            f"静态试排无可用候选：{count}个对象；单行列表须完整单行，文本列表2–3项且含标题最多2项，"
            "对比仅宽卡2–4项，四项宫格不能带公共标题。"
            "请在Plan内按用途重新组织或精简，保留必要对象名称、数值与限定；"
            "有限候选未找到结构不代表所有合法排版均不可行。"
        )
    return StaticPresentationTrial(None, attempted, tuple(errors))
