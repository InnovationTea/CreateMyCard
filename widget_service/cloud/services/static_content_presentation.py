"""按已接受展示角色构造有限候选，不解析用户语义或猜测字段边界。"""

from __future__ import annotations

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


def _attribute(item: _DisplayObject) -> dict[str, str]:
    label = item.caption()
    value = item.text(
        {"body", "value", "leading", "trailing", "detail"}, rendered_title=label,
    )
    result = {"value": item.text()}
    if label and value:
        value_role = "body" if item.has({"body", "detail"}) else "value"
        result = {"label": label, "value": value, "valueRole": value_role}
    elif item.identity and item.identity not in item.text():
        result = {"label": item.identity, "value": item.text()}
    return result


def _record(item: _DisplayObject) -> dict[str, str]:
    title = item.caption()
    result = {"title": title or item.facts[0].get("text", "")}
    if not title:
        remainder = _DisplayObject(item.facts[1:]).text()
        if remainder:
            result["description"] = remainder
        return result
    description = item.text({"body", "value", "detail"})
    if description:
        result["description"] = description
    for side in ("leading", "trailing"):
        value = item.text({side})
        if value:
            result[side] = value
    return result


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


def _variants(objects: list[_DisplayObject], size: str, presentation: str):
    variants = []
    if len(objects) == 1:
        item = objects[0]
        title = item.caption()
        body_roles = {"body", "value", "leading", "trailing", "detail"}
        if not title:
            body_roles.add("label")
        body = item.text(body_roles, rendered_title=title)
        props = {}
        if title:
            props["title"] = title
        if body:
            props["body"] = body
        variants.append(("content", "ContentBlock", props))
    if len(objects) <= 6:
        attributes = []
        for item in objects:
            attributes.append(_attribute(item))
        variants.append(("attributes", "ContentBlock", {"attributes": attributes}))
        inline_attributes = []
        for item in objects:
            text = item.text()
            if item.identity and item.identity not in text:
                text = item.identity + "：" + text
            inline_attributes.append({"value": text})
        if inline_attributes != attributes:
            variants.append(("attributes", "ContentBlock", {"attributes": inline_attributes}))
    if len(objects) <= 3:
        records = []
        for item in objects:
            records.append(_record(item))
        variants.append(("records", "RecordList", {"items": records, "variant": "plain"}))
    comparison = _preferred_style(objects, presentation) == "comparison"
    if size == "2x4" and 2 <= len(objects) <= 3 and comparison:
        items = []
        for item in objects:
            items.append(_comparison(item))
        variants.append(("comparison", "ComparisonGroup", {"items": items}))
    if presentation == "comparison":
        variants = [variant for variant in variants if variant[0] == "comparison"]
    return variants


def _encode(
    component: str, props: dict, shared: list[_DisplayObject], size: str, variant: str = "flow",
    font_size: int = 12, context_as_body: bool = False, separate_header: bool = False,
) -> str:
    titles = []
    notes = []
    for item in shared:
        for fact in item.facts:
            target = titles if fact.get("displayRole") == "title" else notes
            target.append(fact.get("text", ""))
    children = []
    rows = []
    if font_size != 12:
        props = {**props, "fontSize": font_size}
    if titles:
        title = "；".join(titles)
        inline_title = component == "ContentBlock" and "title" not in props and not separate_header
        if context_as_body:
            props = {**props, "body": title}
        elif inline_title:
            props = {**props, "title": title}
        else:
            children.append("header")
            rows.append(["header", "SingleLineTitle", {"title": title, "fontSize": 12}])
    children.append("body")
    rows.append(["body", component, props])
    if notes:
        children.append("note")
        rows.append([
            "note", "SecondaryBody",
            {"items": [{"value": "；".join(notes)}], "columns": 1, "fontSize": font_size},
        ])
    prefix = "S" if size == "2x2" else "W"
    layout_props = {"layout": f"{prefix}-static-content"}
    if variant != "flow":
        layout_props["variant"] = variant
    root = ["root", "Layout", layout_props, children]
    records = [root, *rows, ["/state/ready", True]]
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in records)


def static_presentation_candidates(
    plan: dict[str, Any], size: str, omitted_indexes: tuple[int, ...] = ()
) -> tuple[str, ...]:
    facts = plan.get("info_required", [])
    if any("actionId" in fact for fact in facts):
        return ()
    sources = []
    for font_size in (12, 11, 10):
        sources.extend(_candidate_sources(plan, size, omitted_indexes, font_size))
    optional = list(omitted_indexes)
    for index, fact in enumerate(facts):
        if fact.get("priority") != "should":
            continue
        if fact.get("protectedTexts") or fact.get("preserveVerbatim"):
            continue
        if index not in optional:
            optional.append(index)
    if len(optional) > len(omitted_indexes):
        for font_size in (12, 11, 10):
            for source in _candidate_sources(plan, size, tuple(optional), font_size):
                if source not in sources:
                    sources.append(source)
    return tuple(dict.fromkeys(sources))


def _candidate_sources(
    plan: dict, size: str, omitted_indexes: tuple[int, ...], font_size: int = 12,
) -> list[str]:
    objects, shared = _display_objects(plan, omitted_indexes)
    if not objects:
        return []
    presentation = plan.get("presentationStyle", "auto")
    if plan.get("staticHorizontal"):
        presentation = "comparison"  # 只兼容历史内部计划，不从用户原话识别。
    variants = _variants(objects, size, presentation)
    preferred = _preferred_style(objects, presentation)
    variants.sort(key=lambda variant: variant[0] != preferred)
    sources = []
    for _style, component, props in variants:
        sources.append(_encode(component, props, shared, size, font_size=font_size))
        sources.append(_encode(component, props, shared, size, "compact", font_size))
        has_context = any(item.has({"title"}) for item in shared)
        if component == "ContentBlock" and has_context and "title" not in props:
            for root_variant in ("flow", "compact"):
                sources.append(_encode(
                    component, props, shared, size, root_variant, font_size,
                    separate_header=True,
                ))
        can_use_context = component == "ContentBlock" and "attributes" in props
        if can_use_context and has_context and "body" not in props:
            for root_variant in ("flow", "compact"):
                sources.append(_encode(
                    component, props, shared, size, root_variant, font_size,
                    context_as_body=True,
                ))
    return sources


def _preferred_style(objects: list[_DisplayObject], presentation: str) -> str:
    if presentation != "auto":
        return presentation
    styles = {
        "ContentBlock": "attributes", "RecordList": "records", "ComparisonGroup": "comparison",
    }
    votes: dict[str, int] = {}
    for item in objects:
        for fact in item.facts:
            hints = fact.get("componentHints", [])
            if hints:
                preferred = styles.get(hints[0])
                if preferred:
                    votes[preferred] = votes.get(preferred, 0) + 1
    if len(objects) == 1:
        return "content"
    if all(item.has({"label", "value"}) and not item.has({"title"}) for item in objects):
        return "attributes"
    if all(item.has({"title"}) for item in objects):
        return "records"
    return max(votes, key=lambda name: votes.get(name, 0)) if votes else "attributes"


def trial_static_presentation(
    plan: dict[str, Any], query: str, size: str
) -> StaticPresentationTrial:
    from services.card_validation import CompactDslValidationError, validate_compact_dsl
    from services.compact_high_level_components import CompactDslConversionError

    if any("actionId" in fact for fact in plan.get("info_required", [])):
        return StaticPresentationTrial(None, 0, ())
    errors = []
    attempted = 0
    for source in static_presentation_candidates(plan, size):
        attempted += 1
        try:
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
            f"静态试排无可用候选：{count}个对象；属性表最多6项，记录/对比最多3项。"
            "请在Plan内按用途重新组织或精简，保留必要对象名称、数值与限定；"
            "有限候选未找到结构不代表所有合法排版均不可行。"
        )
    return StaticPresentationTrial(None, attempted, tuple(errors))
