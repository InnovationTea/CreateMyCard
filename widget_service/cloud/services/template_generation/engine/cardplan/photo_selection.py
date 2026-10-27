"""模板定稿后调用公共图片匹配和后处理；不再按图片重新编译模板。"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

from app.logger import json_for_log, logger
from config.config import get_settings
from models.generation import TaskSpec
from services.generation_trace_recorder import trace_record
from services.post_layout_theme_registry import load_theme_registry
from services.theme_photo_assets import excluded_foreground_assets
from services.theme_photo_matching import eligible_photos, select_equivalent_photo
from services.theme_photo_processing import apply_template_photo
from services.theme_user_preferences import prioritize_candidates

from .compiler import HybridCompilation
from .models import HybridBodyContract
from .photo_facts import template_photo_facts
from .photo_preference import photo_preference_reason
from .registry import CardPlanRegistry


def finalize_template_photo(
    original: HybridCompilation, *, task_spec: TaskSpec, contract: HybridBodyContract,
    registry: CardPlanRegistry, compile_options: dict[str, Any],
) -> tuple[HybridCompilation, str]:
    theme_id = contract.theme_profile_id
    result = original
    rejected = {}
    selection = {}
    failure = None
    exclusion = []
    preference = photo_preference_reason(task_spec.userQuery)
    if not get_settings().enable_photo_background_theme:
        preference = "图片主题已关闭"
    photos = []
    if preference is None:
        task = task_spec.model_dump(mode="json")
        facts = template_photo_facts(
            original.a2ui, task, compile_options.get("business_title"),
            button_ids=(original.photo_style_context.button_ids
                        if original.photo_style_context is not None else frozenset()),
        )
        photos, rejected = eligible_photos(facts)
        records = [json.loads(line) for line in original.a2ui.splitlines() if line.strip()]
        nodes = []
        data_model = None
        for record in records:
            nodes.extend(record.get("updateComponents", {}).get("components", []))
            update = record.get("updateDataModel", {})
            if update.get("path") == "/":
                data_model = update.get("value")
        excluded = load_theme_registry().get("photoEligibility", {}).get(
            "excludedForegroundAssets", [],
        )
        exclusion = excluded_foreground_assets(
            nodes, excluded, get_settings().asset_src_url_mapping, data_model,
        )
        if exclusion:
            for photo in photos:
                rejected[photo.get("id")] = "前景使用图片排除表中的图标，整卡禁用图片背景"
            photos = []
    candidates = prioritize_candidates(photos, [], None)
    selected, selection = select_equivalent_photo(theme_id, candidates)
    chosen = next((photo for photo in candidates if photo.get("id") == selected), None)
    if chosen is not None:
        try:
            if original.photo_style_context is None:
                raise ValueError("模板缺少编译器记录的主题样式归属")
            themed = apply_template_photo(
                original.a2ui, chosen, task_spec.model_dump(mode="json"),
                original.photo_style_context,
            )
            nodes = []
            for line in themed.splitlines():
                nodes.extend(json.loads(line).get("updateComponents", {}).get("components", []))
            if len(nodes) > contract.limits.max_expanded_components:
                raise ValueError("Photo background exceeds the existing component budget")
            stats = original.stats.model_copy(update={"expanded_component_count": len(nodes)})
            result = replace(original, a2ui=themed, stats=stats)
            theme_id = selected
        except ValueError as exc:
            failure = f"{type(exc).__name__}: {exc}"
            logger.warning(f"template_photo_postprocess_fallback detail={failure}")
    audit = {
        "planId": original.stats.matched_plan_id,
        "candidates": [photo.get("id") for photo in photos],
        "rejected": rejected, "selection": selection, "selected": theme_id,
        "originalTheme": contract.theme_profile_id, "fallback": result is original,
        "compileFailure": failure, "preferenceReason": preference,
        "photoAssetExclusions": exclusion,
    }
    logger.info(f"template_photo_selection {json_for_log(audit)}")
    trace_record("template_photo_selection", detail=audit)
    return result, theme_id
