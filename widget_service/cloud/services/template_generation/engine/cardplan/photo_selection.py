"""定稿后复用图片准入与随机选择；任何不合格结果保留同一模板原主题。"""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from typing import Any

from app.logger import json_for_log, logger
from config.config import get_settings
from models.generation import TaskSpec
from services.generation_trace_recorder import trace_record
from services.post_layout_theme import select_equivalent_photo
from services.post_layout_theme_registry import registered_themes
from services.theme_style_roles import COLOR_FIELDS

from .compiler import HybridCompilation, compile_ux_layout_card
from .models import HybridBodyContract
from .photo_content import template_photo_reason
from .photo_delivery import deliver_photo_source
from .photo_preference import photo_preference_reason
from .photo_theme import normalize_photo_styles
from .registry import CardPlanRegistry


def _foreground(source: str) -> dict:
    nodes = []
    records = []
    for line in source.splitlines():
        record = json.loads(line)
        update = record.get("updateComponents")
        if update is None:
            records.append(record)
        else:
            nodes.extend(update.get("components", []))
    by_id = {node.get("id"): node for node in nodes}
    if len(by_id) != len(nodes):
        raise ValueError("Template foreground contains duplicate component IDs")

    def visit(identity: str, ancestors: set[str]) -> dict:
        node = by_id.get(identity)
        if node is None or identity in ancestors:
            raise ValueError("Template foreground tree is incomplete")
        result = copy.deepcopy(node)
        styles = normalize_photo_styles(result.get("styles", {}))
        result["styles"] = styles
        for key in COLOR_FIELDS | {"linearGradient", "backdropBlur"}:
            styles.pop(key, None)
        children = result.get("children")
        if children is not None:
            result["children"] = [visit(child, ancestors | {identity}) for child in children]
        return result

    root = by_id.get("root", {})
    root_children = root.get("children", [])
    if "template_root" not in root_children:
        raise ValueError("Template foreground must be a direct child of root")
    root_signature = copy.deepcopy(root)
    root_signature["children"] = [
        identity for identity in root_children
        if identity not in {"fusionBallBackground", "__post_theme_background"}
    ]
    for key in COLOR_FIELDS | {"linearGradient", "backdropBlur"}:
        root_signature.get("styles", {}).pop(key, None)
    return {"root": root_signature, "content": visit("template_root", set()), "records": records}


def finalize_template_photo(
    original: HybridCompilation, *, task_spec: TaskSpec, contract: HybridBodyContract,
    registry: CardPlanRegistry, compile_options: dict[str, Any],
) -> tuple[HybridCompilation, str]:
    result = original
    theme_id = contract.theme_profile_id
    matched = next((plan for plan in contract.allowed_template_plans
                    if plan.plan_id == original.stats.matched_plan_id), None)
    candidate_ids = matched.photo_theme_ids if matched is not None else ()
    rejected = {}
    eligible = []
    photos = {item.get("id"): item for item in registered_themes()}
    preference = photo_preference_reason(task_spec.userQuery)
    if not get_settings().enable_photo_background_theme:
        preference = "图片主题已关闭"
    for identity in candidate_ids:
        photo = photos.get(identity)
        reason = preference
        if photo is None or identity not in registry.photo_themes:
            reason = "图片主题已停用或不存在"
        elif photo.get("size") != task_spec.size:
            reason = "尺寸不匹配"
        elif photo.get("contentEligibility", {}).get("kind") != "uniform":
            reason = "图片缺少统一准入配置"
        elif reason is None:
            reason = template_photo_reason(
                photo, original.a2ui, task_spec.size, compile_options.get("business_title"),
            )
        if reason:
            rejected[identity] = reason
        else:
            eligible.append(photo)
    subjects = [item for item in eligible if item.get("pool") == "photos"]
    selected, selection = select_equivalent_photo(theme_id, subjects or eligible)
    failure = None
    if selected != theme_id:
        try:
            local_registry = copy.copy(registry)
            local_registry.photo_themes = dict(registry.photo_themes)
            theme = registry.require_theme(selected)
            original_theme = registry.require_theme(theme_id)
            root_style = dict(original_theme.root_style)
            root_style.pop("linearGradient", None)
            root_style["backgroundColor"] = theme.root_style.get("backgroundColor")
            support_style = theme.support_content_style
            if support_style is not None:
                support_style = support_style.model_copy(update={
                    "border_radius": original_theme.reference_values.get(
                        "supportContentStyle.borderRadius",
                    ),
                })
            local_registry.photo_themes[selected] = theme.model_copy(update={
                "root_style": root_style,
                "support_content_style": support_style,
                "fusion_ball_style": original_theme.fusion_ball_style,
            })
            themed = compile_ux_layout_card(
                original.raw_output, task_spec=task_spec, registry=local_registry,
                contract=contract.model_copy(update={"theme_profile_id": selected}),
                **compile_options,
            )
            if _foreground(themed.a2ui) != _foreground(original.a2ui):
                raise ValueError("图片主题改变了原模板内容、动作或几何")
            themed = replace(themed, a2ui=deliver_photo_source(themed.a2ui, selected))
            result, theme_id = themed, selected
        except ValueError as exc:
            failure = f"{type(exc).__name__}: {exc}"
            logger.warning(f"template_photo_compile_fallback detail={failure}")
    audit = {
        "planId": original.stats.matched_plan_id, "candidates": candidate_ids,
        "rejected": rejected, "selection": selection, "selected": theme_id,
        "originalTheme": contract.theme_profile_id, "fallback": result is original,
        "compileFailure": failure,
    }
    logger.info(f"template_photo_selection {json_for_log(audit)}")
    trace_record("template_photo_selection", detail=audit)
    return result, theme_id
