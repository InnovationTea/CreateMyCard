"""Project trusted scope and TaskSpec data into a bounded Hybrid Body prompt."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from app.logger import json_for_log, logger
from models.generation import TaskSpec
from services.template_generation.engine.advanced.content_selectors import (
    extract_battery_overview_facts,
    extract_bluetooth_device_overview_facts,
)

from .generated.prompts import BODY_SYSTEM_PROMPT_KERNEL, UX_MIXED_SYSTEM_PROMPT_KERNEL
from .models import ActionBinding, Fact, HybridBodyContract, HybridLimits
from .provider_bundle import (
    provider_template_admission,
    provider_template_family_identity,
    provider_template_layout_kind,
    provider_template_variant_admission,
)
from .registry import CardPlanRegistry

_PLAIN_DESIGNS = (
    "title",
    "body",
    "subtitle",
    "success",
    "warning",
    "primary",
    "icon",
)
_PLAIN_LAYOUTS = ("card", "section", "compact", "between", "actions", "list", "dense", "overlay")
_ACTION_TEMPLATE_IDS = ("PillAction@1", "IconAction@1")
_ACTION_PROVIDER_ID = "com.huawei.action.cli"
_ACTION_LABELS = {
    "event.call.phone": "联系家人",
    "event.clean.memory": "一键清理",
    "event.enter.meeting": "加入会议",
    "event.open.settings.dnd": "免打扰",
    "event.open.settings.bluetooth": "蓝牙设置",
    "event.open.settings.battery": "电池设置",
    "event.open.settings.batteryHealth": "电池健康",
    "event.open.settings.parentControl": "管控时间",
    "event.open.settings.storage": "存储设置",
    "event.open.weather": "天气详情",
    "event.open.clock.alarm": "设置闹钟",
    "event.open.music.daily": "每日推荐",
    "event.open.music.favorite": "心动歌单",
    "event.open.health.sport": "今日训练",
    "event.open.health.sleep": "睡眠详情",
    "event.viewCalendarEvent": "查看日程",
    "event.startNavigate": "开始导航",
    "event.setPowerSavingMode": "省电模式",
}
_ASSET_SEMANTIC_TERMS = {
    "calendar": ("calendar", "schedule", "日程", "日历"),
    "schedule": ("schedule", "日程"),
    "meeting": ("meeting", "conference", "会议", "入会"),
    "time": ("time", "clock", "时间", "时钟"),
    "location": ("location", "place", "room", "地点", "位置", "会议室"),
    "focus": ("focus", "dnd", "专注", "勿扰"),
    "sport": ("sport", "training", "run", "运动", "训练", "跑步"),
    "run": ("run", "running", "跑步"),
    "activity": ("activity", "steps", "walk", "活动", "步数", "步行"),
    "steps": ("steps", "step count", "walk", "步数", "步行"),
    "calories": ("calorie", "calories", "kcal", "热量", "卡路里"),
    "energy": ("energy", "flame", "fire", "能量", "火焰"),
    "distance": ("distance", "mileage", "距离", "里程"),
    "route": ("route", "path", "路线", "路径"),
    "workout": ("workout", "exercise", "training", "锻炼", "训练", "运动"),
    "heart": ("heart", "cardiac", "心脏", "心率"),
    "heart-rate": ("heart rate", "heartrate", "心率"),
    "pulse": ("pulse", "bpm", "脉搏", "心率"),
    "call": ("call", "phone", "电话", "拨打"),
    "weather": ("weather", "天气"),
    "alert": ("alert", "warning", "预警", "警告"),
    "product": ("product", "earphone", "headphone", "耳机"),
    "audio": ("audio", "music", "earphone", "headphone", "音频", "音乐", "耳机"),
    "earphone": ("earphone", "earbud", "headphone", "耳机", "耳塞"),
    "phone-device": ("smartphone", "phone icon", "icon_phone", "手机图标"),
    "music": ("music", "playlist", "音乐", "歌单"),
    "favorite": ("favorite", "like", "heart", "收藏", "心动", "心形"),
    "battery": ("battery", "charge", "charging", "电池", "电量", "充电"),
    "power": ("power", "charge", "charging", "省电", "电量", "充电"),
    "power-saving": (
        "power saving",
        "power-saving",
        "battery saver",
        "save power",
        "leaf",
        "省电",
        "节电",
        "节能",
        "绿叶",
        "叶片",
        "叶子",
    ),
    "memory": ("memory", "ram", "内存"),
    "resource": ("system resource", "resource usage", "系统资源", "资源占用"),
    "clean": ("clean", "cleanup", "clear", "清理", "释放"),
    "app": ("app", "application", "应用", "软件"),
    "timer": ("timer", "timing", "hourglass", "计时", "时长", "时间"),
    "settings": ("settings", "setting", "设置"),
    "parental-control": (
        "parental control",
        "parent control",
        "digital wellbeing",
        "家长控制",
        "健康使用",
        "管控时间",
    ),
}


@dataclass(frozen=True)
class HybridPromptProjection:
    messages: list[dict[str, str]]
    contract: HybridBodyContract
    facts: tuple[Fact, ...]
    requested_template_ids: tuple[str, ...]
    theme_id: str


def build_hybrid_prompt(
    *,
    task_spec: TaskSpec,
    card_spec: dict[str, Any],
    ui_brief: Any,
    registry: CardPlanRegistry,
    ux_layout_root_ids: tuple[str, ...] = (),
    expose_data_facts: bool = True,
) -> HybridPromptProjection:
    facts = (
        tuple(_collect_facts(task_spec.dataModelSchema))
        if expose_data_facts
        else ()
    )
    theme_id = _resolve_theme(task_spec, ui_brief, registry)
    requested = _resolve_templates(
        task_spec,
        card_spec,
        ui_brief,
        theme_id,
        registry,
    )
    asset_sources = tuple(
        str(item["src"])
        for item in task_spec.assetCandidates
        if isinstance(item, dict) and isinstance(item.get("src"), str)
    )
    asset_semantic_tags_by_source = {
        str(item["src"]): _asset_semantic_tags(item)
        for item in task_spec.assetCandidates
        if isinstance(item, dict) and isinstance(item.get("src"), str)
    }
    card_literals = (
        [str(card_spec.get("title", ""))]
        if ux_layout_root_ids
        else [str(card_spec.get("title", "")), str(card_spec.get("description", ""))]
    )
    trusted_literals = _unique(
        [
            *((task_spec.userQuery,) if expose_data_facts else ()),
            *card_literals,
            *(str(fact.value) for fact in facts if isinstance(fact.value, str)),
            *(_action_label(event) for event in task_spec.eventCandidates),
        ]
    )
    trusted_numbers = tuple(
        dict.fromkeys(
            fact.value
            for fact in facts
            if isinstance(fact.value, (int, float)) and not isinstance(fact.value, bool)
        )
    )
    required_numbers = tuple(
        fact.value
        for fact in facts
        if isinstance(fact.value, (int, float)) and not isinstance(fact.value, bool)
    )
    actions = _build_action_bindings(task_spec)
    if getattr(ui_brief, "action_placement", "auto") == "none":
        actions = ()
    selected_definitions = [registry.require_template(wire_id) for wire_id in requested]
    if ux_layout_root_ids:
        # Layout contracts select the exact cardinality. The compact two-action
        # layout is the only family that consumes both approved controls.
        content_action_ids = tuple(action.action_id for action in actions[:2])
    else:
        content_action_ids = _resolve_content_action_ids(
            ui_brief=ui_brief,
            actions=actions,
            definitions=selected_definitions,
        )
    if ux_layout_root_ids and content_action_ids:
        requested = tuple(dict.fromkeys((*requested, *_ACTION_TEMPLATE_IDS)))
    selected_definitions = [registry.require_template(wire_id) for wire_id in requested]
    design_tokens = _unique(
        [
            *_PLAIN_DESIGNS,
            *(token for item in selected_definitions for token in item.allowed_design_tokens),
        ]
    )
    layout_tokens = _unique(
        [
            *_PLAIN_LAYOUTS,
            *(token for item in selected_definitions for token in item.allowed_layout_tokens),
            *(item.recommended_container_layout_token or "" for item in selected_definitions),
            *(
                item.recommended_variant_layout.inline_layout_token
                for item in selected_definitions
                if item.recommended_variant_layout is not None
            ),
        ]
    )
    string_facts = [
        str(fact.value)
        for fact in facts
        if isinstance(fact.value, str) and fact.value.strip() and fact.value != "示例"
    ]
    limits = HybridLimits(
        max_raw_components=18 if task_spec.size == "2x2" else 28,
        max_expanded_components=36 if task_spec.size == "2x2" else 52,
        max_nesting_depth=9 if ux_layout_root_ids else 7,
        vertical_budget_vp=126,
    )
    contract = HybridBodyContract(
        theme_profile_id=theme_id,
        allowed_components=tuple(
            dict.fromkeys(
                (
                    "Text",
                    "Image",
                    "Divider",
                    "Progress",
                    "Button",
                    "Checkbox",
                    "Row",
                    "Column",
                    "List",
                    "Stack",
                    *ux_layout_root_ids,
                )
            )
        ),
        allowed_design_tokens=design_tokens,
        allowed_layout_tokens=layout_tokens,
        allowed_template_ids=requested,
        allowed_asset_sources=asset_sources,
        asset_semantic_tags_by_source=asset_semantic_tags_by_source,
        trusted_literals=trusted_literals,
        trusted_numbers=trusted_numbers,
        required_numbers=required_numbers,
        required_literals=tuple(dict.fromkeys(string_facts)),
        protected_literals=tuple(dict.fromkeys(string_facts)),
        action_bindings=actions,
        content_action_ids=content_action_ids,
        allowed_layout_component_ids=ux_layout_root_ids,
        limits=limits,
    )
    system = _system_prompt(
        contract,
        requested,
        registry,
        task_spec=task_spec,
        card_spec=card_spec,
        ux_layout_root=bool(ux_layout_root_ids),
    )
    card_composition = _card_composition_payload(
        task_spec=task_spec,
        card_spec=card_spec,
        actions=actions,
        content_action_ids=content_action_ids,
        ux_layout_root=bool(ux_layout_root_ids),
    )
    user_lines = [
        f"card={json.dumps({'size': task_spec.size, 'theme': theme_id}, ensure_ascii=False)}",
        f"requestedTemplate={json.dumps(requested, ensure_ascii=False)}",
        f"cardComposition={json.dumps(card_composition, ensure_ascii=False)}",
    ]
    if expose_data_facts:
        user_lines[:0] = [f"request={json.dumps(task_spec.userQuery, ensure_ascii=False)}"]
        user_lines.extend(
            (
                "dataFacts="
                + json.dumps(
                    [fact.model_dump() for fact in facts],
                    ensure_ascii=False,
                ),
                f"mustKeep={json.dumps(contract.required_literals, ensure_ascii=False)}",
                f"mustKeepNumbers={json.dumps(contract.required_numbers, ensure_ascii=False)}",
                "advancedComposition="
                + json.dumps(
                    {
                        "primaryDomain": getattr(ui_brief, "primary_domain", None),
                        "adaptiveTemplateId": getattr(ui_brief, "adaptive_template_id", None),
                        "advancedComponentIds": getattr(ui_brief, "advanced_component_ids", []),
                    },
                    ensure_ascii=False,
                ),
            )
        )
    user_lines.append(
        "只输出一个以分号结束、以批准布局高级组件为根的完整 Card。"
        if ux_layout_root_ids
        else '只输出一个以分号结束、以 Template("card@1", ...) 为根的完整 Card。'
    )
    user = "\n".join(user_lines)
    if len(system) + len(user) > 80_000:
        raise ValueError("Hybrid Body Prompt exceeds the service input budget")
    return HybridPromptProjection(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        contract=contract,
        facts=facts,
        requested_template_ids=requested,
        theme_id=theme_id,
    )


def _card_composition_payload(
    *,
    task_spec: TaskSpec,
    card_spec: dict[str, Any],
    actions: tuple[ActionBinding, ...],
    content_action_ids: tuple[str, ...],
    ux_layout_root: bool,
) -> dict[str, Any]:
    action_candidates = [
        {
            "id": action.action_id,
            "label": action.display_label,
            "importance": action.importance,
            "materialHint": action.material_hint,
        }
        for action in actions
    ]
    if ux_layout_root:
        return {
            "headerPolicy": "no-independent-card-header",
            "businessTitleCandidate": card_spec.get("title"),
            "layoutActionCandidates": action_candidates[:4],
            "required": {},
            "actionIconCandidates": [
                {"src": item.get("src"), "description": item.get("description", "")}
                for item in task_spec.assetCandidates
                if item.get("src")
            ],
        }
    return {
        "titleCandidates": [
            {"role": "title", "text": card_spec.get("title")},
            {"role": "subtitle", "text": card_spec.get("description")},
        ],
        "titleIconCandidates": [
            {"src": item.get("src"), "description": item.get("description", "")}
            for item in task_spec.assetCandidates
            if item.get("src")
        ],
        "cardActionCandidates": [
            item for item in action_candidates if item["id"] not in content_action_ids
        ],
        "contentActionCandidates": [
            item for item in action_candidates if item["id"] in content_action_ids
        ],
        "required": (
            {"actionId": actions[0].action_id}
            if len(actions) == 1 and not content_action_ids
            else {}
        ),
        "cardParamsPolicy": (
            "independent-chrome-without-action" if content_action_ids else "candidate-chrome"
        ),
    }


def _system_prompt(
    contract: HybridBodyContract,
    requested: tuple[str, ...],
    registry: CardPlanRegistry,
    *,
    task_spec: TaskSpec,
    card_spec: dict[str, Any],
    ux_layout_root: bool = False,
) -> str:
    signatures: list[str] = []
    for wire_id in requested:
        definition = registry.require_template(wire_id)
        for variant in admitted_provider_template_variants(
            definition,
            task_spec,
            card_spec,
        ):
            is_action_template = wire_id in _ACTION_TEMPLATE_IDS
            if ux_layout_root and _variant_requires_action(variant) and not is_action_template:
                continue
            if not _variant_has_available_required_assets(variant, definition, contract):
                continue
            if (
                not ux_layout_root
                and not contract.content_action_ids
                and _variant_requires_action(variant)
            ):
                continue
            properties = variant.parameters_schema.get("properties", {})
            params: dict[str, dict[str, Any]] = {}
            for name, value in properties.items():
                value_kind = _parameter_value_kind(name, value)
                parameter: dict[str, Any] = {
                    "type": value.get("type", "value"),
                    "description": value.get("description", ""),
                    "valueKind": value_kind,
                }
                if value_kind == "asset-source":
                    parameter["allowedSources"] = _parameter_allowed_asset_sources(
                        name,
                        definition,
                        contract,
                    )
                params[name] = parameter
            if definition.source_format != "cardtpl/1" or variant.size != "default":
                raise ValueError(
                    f"Template is outside the supported cardtpl/1 contract: {wire_id}"
                )
            call = f"Template({wire_id!r}, props)"
            if ux_layout_root:
                layout_kind = provider_template_layout_kind(wire_id)
                template_summary = f"layoutKind={layout_kind or 'control'}"
            else:
                template_summary = definition.description
            signatures.append(
                f"- {call}: "
                f"{template_summary}; params={json.dumps(params, ensure_ascii=False)}; "
                "parameterRelations="
                + json.dumps(
                    [item.model_dump(by_alias=True) for item in variant.parameter_relations],
                    ensure_ascii=False,
                )
            )
    content_actions = [
        item for item in contract.action_bindings if item.action_id in contract.content_action_ids
    ]
    action_templates = [
        registry.require_template(wire_id).wire_id
        for wire_id in requested
        if registry.require_template(wire_id).action_policy != "none"
    ]
    if ux_layout_root:
        action_rule = _ux_layout_action_rule(contract)
    elif content_actions:
        content_action_json = json.dumps(
            [item.model_dump() for item in content_actions],
            ensure_ascii=False,
        )
        action_rule = (
            "card params 必须省略 action。title、subtitle、titleIcon 仅在表达未被 content "
            "消费的独立上下文时使用；否则一并省略。"
            f"contentActionCandidates={content_action_json}；"
            "每个批准 ID 必须由一个 actionPolicy!=none 的局部 Template 恰好消费一次，"
            f"可用 Action Template={json.dumps(action_templates, ensure_ascii=False)}；"
            "content 禁止标准 Button。"
        )
    elif contract.action_bindings:
        action_rule = (
            "card action 必须从 cardActionCandidates 的批准 label/id 对中选择；"
            "content 禁止 Button 和事件。"
        )
    else:
        action_rule = "本次没有批准 Action；card params 省略 action，content 禁止 Button 和事件。"
    if ux_layout_root:
        return "\n".join(
            (
                UX_MIXED_SYSTEM_PROMPT_KERNEL,
                "",
                f"允许素材 src={json.dumps(contract.allowed_asset_sources, ensure_ascii=False)}",
                "素材语义标签="
                + json.dumps(contract.asset_semantic_tags_by_source, ensure_ascii=False),
                action_rule,
                "批准的布局、业务与 Action Template：",
                *signatures,
                f"预算：raw<={contract.limits.max_raw_components}, "
                f"expanded<={contract.limits.max_expanded_components}, "
                f"depth<={contract.limits.max_nesting_depth}, "
                f"body<={contract.limits.vertical_budget_vp}vp。",
            )
        )
    composition_rules = _composition_rules(ux_layout_root)
    return "\n".join(
        (
            BODY_SYSTEM_PROMPT_KERNEL,
            "",
            "标准组件投影：Text/Image/Button 使用批准 DesignToken；"
            "Column/Row/List/Stack 使用批准 LayoutToken；Progress 使用字面量对象。",
            "基础容器的规范组合为 Column(section|compact)、Row(between|actions)、"
            "List(list|dense)、Stack(overlay)；Registry 展开的专用别名由服务端静态归一化。",
            'Text 严格写成 Text("可见文字", "designToken")，可见文字在前、DesignToken '
            "在后，禁止交换两个位置。",
            '容器严格写成 Column("layoutToken", child1, child2)；不要把 layoutToken '
            "包装成对象，不要用数组包装 children。",
            "Template 参数必须逐项遵守签名中的 JSON type；看起来像数字的 string 仍需加引号。",
            *composition_rules,
            "素材 src 只能填入参数名或描述明确表示 icon/image/asset/source/src 的字段；"
            "symbol、文字、标签和数值字段禁止使用素材。",
            "局部 Template 与标准组件可以混排，但禁止重复展示同一事实；"
            "多个局部 Template 的 title/time/value/status 等主要参数不得复用相同字面量。"
            "只选覆盖独立信息所需的最小组合。",
            f"允许 DesignToken={json.dumps(contract.allowed_design_tokens)}",
            f"允许 LayoutToken={json.dumps(contract.allowed_layout_tokens)}",
            f"允许素材 src={json.dumps(contract.allowed_asset_sources, ensure_ascii=False)}",
            "素材语义标签="
            + json.dumps(contract.asset_semantic_tags_by_source, ensure_ascii=False),
            "若某个素材带有 product 语义标签，且已批准局部 Template 的某个 variant 提供"
            "product/image/asset/source/src 图片参数，优先选择能把该素材作为主视觉完整展示的"
            "variant；同一 product 素材不要再放入 card titleIcon。只有没有匹配图片参数时，"
            "才允许把它作为普通 Image 或标题图标使用。",
            action_rule,
            "局部 Template：",
            *signatures,
            f"预算：raw<={contract.limits.max_raw_components}, "
            f"expanded<={contract.limits.max_expanded_components}, "
            f"depth<={contract.limits.max_nesting_depth}, "
            f"body<={contract.limits.vertical_budget_vp}vp。",
        )
    )


def build_template_prompt_contracts(
    requested: tuple[str, ...],
    contract: HybridBodyContract,
    registry: CardPlanRegistry,
    *,
    task_spec: TaskSpec,
    card_spec: dict[str, Any],
    ux_layout_root: bool,
) -> tuple[dict[str, Any], ...]:
    """Build complete dynamic Template signatures for the active model candidates."""
    prompt_contracts: list[dict[str, Any]] = []
    for wire_id in dict.fromkeys(requested):
        definition = registry.require_template(wire_id)
        variants = admitted_provider_template_variants(
            definition,
            task_spec,
            card_spec,
        )
        if not variants:
            # Search has already selected a trusted concrete Template ID. Avoid
            # rejecting it by guessing the business state again while building
            # the signature; data-binding admission still remains mandatory.
            admitted_variants = []
            for variant in definition.variants:
                admission = provider_template_variant_admission(
                    definition,
                    variant,
                    task_spec,
                    card_spec,
                )
                if admission.admitted:
                    admitted_variants.append(variant)
            variants = tuple(admitted_variants)
        for variant in variants:
            is_action_template = wire_id in _ACTION_TEMPLATE_IDS
            if ux_layout_root and _variant_requires_action(variant) and not is_action_template:
                continue
            if not _variant_has_available_required_assets(variant, definition, contract):
                continue
            if definition.source_format != "cardtpl/1" or variant.size != "default":
                raise ValueError(
                    f"Template is outside the supported cardtpl/1 contract: {wire_id}"
                )
            properties = variant.parameters_schema.get("properties", {})
            parameter_sources: dict[str, dict[str, Any]] = {}
            for name, schema in properties.items():
                value_kind = _parameter_value_kind(name, schema)
                source_contract: dict[str, Any] = {"valueKind": value_kind}
                if value_kind == "asset-source":
                    source_contract["allowedSources"] = _parameter_allowed_asset_sources(
                        name,
                        definition,
                        contract,
                    )
                parameter_sources[name] = source_contract
            prompt_contracts.append(
                {
                    "templateId": wire_id,
                    "callSyntax": (
                        f'Template("{wire_id}", <props matching propsSchema>)'
                    ),
                    "description": definition.description,
                    "layoutKind": (
                        provider_template_layout_kind(wire_id) if ux_layout_root else None
                    ),
                    "propsSchema": variant.parameters_schema,
                    "parameterSources": parameter_sources,
                    "parameterRelations": [
                        item.model_dump(by_alias=True) for item in variant.parameter_relations
                    ],
                }
            )
    return tuple(prompt_contracts)


def _composition_rules(ux_layout_root: bool) -> tuple[str, ...]:
    if ux_layout_root:
        return (
            '根必须直接是一个批准的布局高级组件；禁止 Template("card@1", ...)。',
            "布局调用可省略配置；需要覆盖默认重排时，"
            "只能把 Contract 声明的一个闭合配置对象"
            "放在第一个 child 前。布局的 businessChildren 数量不含 Action；"
            "除 TwoSupportLayout 外，所有 Action 必须是布局根的连续末尾直接 children，"
            "禁止放进 Column/Row/Stack/List/业务 Template；整卡最多两个 Action。"
            "TwoSupportLayout 禁止 Action child，批准事件只能各一次写入 Support 业务"
            "Template 的可选 actionId Prop。HeroTitleContentActionLayout 必须恰好按位置放置 "
            "HeroTitle、HeroContent、PillAction 三个直接 children，不得交换、重复或嵌套。",
            "禁止独立整卡 Header。若 cardComposition.businessTitleCandidate 能准确命名"
            "当前业务，"
            "可在业务内容区使用；若局部 Template 或事实已表达则省略，"
            "禁止从 request 截取标题。",
            "Action 类型由业务模板后缀和布局共同决定：Compact/Hero/WideHero 使用 "
            'Template("PillAction@1", props)，Full 仅在 FullIconActionLayout 中使用 '
            'Template("IconAction@1", props)，WideFull 不允许 Action；Support 仅使用内部 '
            "actionId Prop。Action 不得被改写、丢弃或重复；Support 内部事件需按语义归属业务；"
            "HeroTitle/HeroContent 仅允许按位置组合到 HeroTitleContentActionLayout；"
            "禁止直接调用 PillAction/IconAction/ActionTile、标准 Button 和事件对象。",
        )
    return (
        'Card 外壳必须是 Template("card@1", cardParams, content)。',
        "cardParams 只允许 title、subtitle、titleIcon、action；禁止 icon 等别名。"
        "title/subtitle 必须逐字来自候选或 dataFacts，否则省略。",
        '整卡 Action 直接写成 action: { label: "批准文案", id: "批准ID" }；'
        "禁止写成 action: { action: {...} } 或增加任何包装层。",
    )


def _ux_layout_action_rule(contract: HybridBodyContract) -> str:
    actions = [
        {"actionId": item.action_id, "label": item.display_label}
        for item in contract.action_bindings
        if item.action_id in contract.content_action_ids
    ]
    if not actions:
        return "本次没有批准 Action；必须选择 actionPolicy=none/optional 的布局并省略 Action。"
    action_rule = (
        "layoutActionCandidates="
        + json.dumps(actions, ensure_ascii=False)
        + "；按所选布局的 Action 数量范围选择且不得重复 actionId；"
        "PillAction@1 的 actionId/label 必须来自同一候选，icon 可从 "
        "actionIconCandidates 选择；IconAction@1 必须填写批准的 actionId/icon。"
    )
    two_support_allowed = "TwoSupportLayout" in contract.allowed_layout_component_ids
    if two_support_allowed:
        action_rule += (
            "TwoSupportLayout 不生成 Action child，批准 actionId 必须各一次写入语义匹配的 "
            "Support Template；"
        )
    action_rule += "事件由服务端可信 Lowering 注入，禁止输出 call/args/onClick。"
    return action_rule


def _resolve_theme(task_spec: TaskSpec, ui_brief: Any, registry: CardPlanRegistry) -> str:
    requested = getattr(ui_brief, "theme_id", None)
    if getattr(ui_brief, "preserve_search_candidates", False):
        if isinstance(requested, str) and requested in registry.themes:
            return requested
        raise ValueError("Search route requires a first-layer Theme")
    requested_templates = [
        registry.templates[item]
        for item in (getattr(ui_brief, "local_template_ids", []) or [])
        if item in registry.templates
    ]
    themed_templates = [item for item in requested_templates if item.compatible_theme_profile_ids]
    if themed_templates:
        support = {
            theme_id: sum(
                theme_id in definition.compatible_theme_profile_ids
                for definition in themed_templates
            )
            for theme_id in registry.themes
        }
        best_support = max(support.values(), default=0)
        requested_support = support.get(requested, 0) if isinstance(requested, str) else 0
        if best_support > requested_support:
            return min(theme_id for theme_id, score in support.items() if score == best_support)
    if isinstance(requested, str) and requested in registry.themes:
        return requested
    text = _semantic_text(task_spec, ui_brief)
    ranked = sorted(
        registry.themes.values(),
        key=lambda item: (
            -_token_overlap(text, f"{item.theme_profile_id} {item.description}"),
            item.theme_profile_id,
        ),
    )
    return ranked[0].theme_profile_id


def _resolve_templates(
    task_spec: TaskSpec,
    card_spec: dict[str, Any],
    ui_brief: Any,
    theme_id: str,
    registry: CardPlanRegistry,
) -> tuple[str, ...]:
    requested = getattr(ui_brief, "local_template_ids", []) or []
    if getattr(ui_brief, "preserve_search_candidates", False):
        unknown = [wire_id for wire_id in requested if wire_id not in registry.templates]
        if unknown:
            raise ValueError("Search route contains an unknown Template candidate")
        return tuple(dict.fromkeys(requested))
    allowed: list[str] = []
    for wire_id in requested:
        definition = registry.templates.get(wire_id)
        if definition is None:
            continue
        if not _provider_template_is_admitted(
            definition,
            task_spec,
            card_spec,
            log_mismatch=True,
        ):
            continue
        themes = definition.compatible_theme_profile_ids
        if not themes or theme_id in themes:
            allowed.append(wire_id)
    if not allowed and not getattr(ui_brief, "disable_template_fallback", False):
        text = _semantic_text(task_spec, ui_brief)
        for definition in _eligible_ranked_templates(
            text,
            registry,
            task_spec,
            card_spec,
        ):
            themes = definition.compatible_theme_profile_ids
            if not themes or theme_id in themes:
                allowed.append(definition.wire_id)
            if len(allowed) >= 6:
                break
    resolved = tuple(dict.fromkeys(allowed))
    resolved = _supplement_action_only_templates(
        resolved,
        task_spec=task_spec,
        ui_brief=ui_brief,
        theme_id=theme_id,
        registry=registry,
        card_spec=card_spec,
    )
    return _prune_redundant_action_templates(resolved, registry)


def _supplement_action_only_templates(
    requested: tuple[str, ...],
    *,
    task_spec: TaskSpec,
    ui_brief: Any,
    theme_id: str,
    registry: CardPlanRegistry,
    card_spec: dict[str, Any],
) -> tuple[str, ...]:
    if not requested:
        return requested
    definitions = [registry.require_template(item) for item in requested]
    if any(definition.action_policy == "none" for definition in definitions):
        return requested
    text = _semantic_text(task_spec, ui_brief)
    supplement = next(
        (
            definition.wire_id
            for definition in _eligible_ranked_templates(
                text,
                registry,
                task_spec,
                card_spec,
            )
            if definition.action_policy == "none"
            and theme_id in definition.compatible_theme_profile_ids
        ),
        None,
    )
    return (*requested, supplement) if supplement is not None else requested


def _prune_redundant_action_templates(
    requested: tuple[str, ...],
    registry: CardPlanRegistry,
) -> tuple[str, ...]:
    definitions = [registry.require_template(item) for item in requested]
    covered_content_parameters = {
        name.casefold()
        for definition in definitions
        if definition.action_policy == "none"
        for variant in definition.variants
        for name in variant.parameters_schema.get("required", [])
        if isinstance(name, str)
    }
    covered_domain_tags = {
        tag.casefold()
        for definition in definitions
        if definition.action_policy == "none"
        for tag in definition.domain_tags
    }
    retained: list[str] = []
    has_content_template = any(definition.action_policy == "none" for definition in definitions)
    for definition in definitions:
        if definition.action_policy == "none" or definition.compatible_theme_profile_ids:
            retained.append(definition.wire_id)
            continue
        semantic_parameters = {
            name.casefold()
            for variant in definition.variants
            for name in variant.parameters_schema.get("required", [])
            if isinstance(name, str) and not _is_action_or_asset_parameter(name)
        }
        semantic_tags = {
            tag.casefold() for tag in definition.domain_tags if tag.casefold() != "action"
        }
        if has_content_template and not definition.compatible_theme_profile_ids:
            continue
        content_is_covered = (
            semantic_parameters and semantic_parameters <= covered_content_parameters
        ) or (semantic_tags and semantic_tags <= covered_domain_tags)
        if content_is_covered:
            continue
        retained.append(definition.wire_id)
    return tuple(retained)


def _is_action_or_asset_parameter(name: str) -> bool:
    normalized = name.casefold()
    return any(
        token in normalized
        for token in ("action", "event", "icon", "image", "asset", "source", "src")
    )


def _parameter_value_kind(name: str, schema: dict[str, Any]) -> str:
    semantic_text = f"{name} {schema.get('description', '')}".casefold()
    if any(
        token in semantic_text
        for token in (
            "icon",
            "image",
            "asset",
            "source",
            "src",
            "图标",
            "图片",
            "素材",
            "资源",
        )
    ):
        return "asset-source"
    if any(token in semantic_text for token in ("action", "event", "操作", "事件")):
        return "action-id"
    return "literal"


def _variant_requires_action(variant: Any) -> bool:
    required = variant.parameters_schema.get("required", [])
    return any(
        _parameter_value_kind(name, variant.parameters_schema.get("properties", {}).get(name, {}))
        == "action-id"
        for name in required
    )


def _variant_has_available_required_assets(
    variant: Any,
    definition: Any,
    contract: HybridBodyContract,
) -> bool:
    properties = variant.parameters_schema.get("properties", {})
    for name in variant.parameters_schema.get("required", []):
        schema = properties.get(name, {})
        if _parameter_value_kind(name, schema) != "asset-source":
            continue
        if not _parameter_allowed_asset_sources(name, definition, contract):
            return False
    return True


def _parameter_allowed_asset_sources(
    name: str,
    definition: Any,
    contract: HybridBodyContract,
) -> tuple[str, ...]:
    required_tags = set(definition.asset_parameter_semantic_tags.get(name, ()))
    if not required_tags:
        return contract.allowed_asset_sources
    return tuple(
        source
        for source in contract.allowed_asset_sources
        if required_tags.issubset(set(contract.asset_semantic_tags_by_source.get(source, ())))
    )


def _ranked_templates(text: str, registry: CardPlanRegistry):
    return sorted(
        registry.templates.values(),
        key=lambda item: (
            -_token_overlap(
                text,
                " ".join((item.template_id, item.description, *item.domain_tags)),
            ),
            item.wire_id,
        ),
    )


def _eligible_ranked_templates(
    text: str,
    registry: CardPlanRegistry,
    task_spec: TaskSpec,
    card_spec: dict[str, Any] | None,
):
    eligible_templates = []
    for definition in _ranked_templates(text, registry):
        if definition.provider_id == _ACTION_PROVIDER_ID:
            continue
        admitted = _provider_template_is_admitted(
            definition,
            task_spec,
            card_spec,
            log_mismatch=False,
        )
        if admitted:
            eligible_templates.append(definition)
    return eligible_templates


def _provider_template_is_admitted(
    definition: Any,
    task_spec: TaskSpec,
    card_spec: dict[str, Any] | None,
    *,
    log_mismatch: bool,
) -> bool:
    admission = provider_template_admission(definition, task_spec, card_spec)
    if admission.admitted:
        return True
    if log_mismatch:
        logger.warning(
            "[Provider Template] provider_template_disabled "
            f"provider_id={definition.provider_id or 'unknown'} "
            f"template_id={definition.wire_id} "
            f"capability_id={definition.capability_id or 'unknown'} "
            f"reason={admission.reason} "
            f"binding_name={admission.binding_name or 'none'} "
            f"path={json_for_log(admission.path or '')} "
            f"expected_type={admission.expected_type or 'none'} "
            f"actual_type={admission.actual_type or 'none'} "
            "action=template_disabled business_payload_logged=false"
        )
    return False


def admitted_provider_template_variants(
    definition: Any,
    task_spec: TaskSpec,
    card_spec: dict[str, Any] | None,
) -> tuple[Any, ...]:
    """返回与生产 Prompt 完全相同的当前数据状态可用 Provider Variant。"""
    admitted = tuple(
        variant
        for variant in definition.variants
        if provider_template_variant_admission(
            definition,
            variant,
            task_spec,
            card_spec,
        ).admitted
        and _provider_variant_matches_trusted_state(
            definition.wire_id,
            variant.size,
            task_spec,
            card_spec,
        )
    )
    return tuple(
        variant
        for variant in admitted
        if not any(
            _variant_binding_set_is_dominated(variant, other, definition)
            for other in admitted
            if other is not variant
        )
    )


def _provider_variant_matches_trusted_state(
    wire_id: str,
    variant_name: str,
    task_spec: TaskSpec,
    card_spec: dict[str, Any] | None,
) -> bool:
    identity = provider_template_family_identity(wire_id)
    if identity is not None:
        wire_id, variant_name = identity
    capabilities = {
        item.get("capabilityId")
        for item in (card_spec or {}).get("dataBindings", ())
        if isinstance(item, dict)
    }
    if wire_id == "BatteryOverview@1":
        state_independent_variants = {
            "compact",
            "chargingDiagnosticsHero",
            "chargingProgressFull",
            "chargingProgressHero",
            "chargingRingHero",
            "full",
            "hero",
            "healthLevelHero",
            "percentRingHero",
            "progressCompact",
            "statusIconCompact",
            "temperatureIconCompact",
            "temperatureFull",
            "wideFull",
        }
        if variant_name in state_independent_variants:
            return True
        facts = extract_battery_overview_facts(task_spec.dataModelSchema)
        if facts is None:
            return False
        if not variant_name.startswith(facts.state):
            return False
        if "GetEarphoneInfo" in capabilities:
            return variant_name == f"{facts.state}Phone"
        return True
    if wire_id == "BluetoothDeviceOverview@1":
        facts = extract_bluetooth_device_overview_facts(task_spec.dataModelSchema)
        if facts is None:
            return False
        if variant_name in {"caseStatus", "caseStatusCompact"}:
            return (
                facts.case_battery_level is not None
                and facts.case_charging_status is not None
            )
        has_left = facts.left_battery_level is not None
        has_right = facts.right_battery_level is not None
        has_case = facts.case_battery_level is not None
        if variant_name == "earbudsSupport":
            return has_left and has_right
        if facts.is_connected is None or facts.earphone_name is None:
            return False
        if variant_name == "hero":
            return True
        if variant_name == "earbudPairCompact":
            return has_left and has_right
        if variant_name == "earbudPairFull":
            return has_case and has_left and has_right
        paired_with_phone = {
            "GetEarphoneInfo",
            "GetPhoneBatteryInfo",
        } <= capabilities
        if variant_name in {"earbudsPhoneWideFull", "completePhoneWideFull"}:
            return paired_with_phone
        if variant_name in {"earbudsDynamicWideFull", "completeWideFull"}:
            return not paired_with_phone
        return False
    return True


def _variant_binding_set_is_dominated(
    variant: Any,
    other: Any,
    definition: Any,
) -> bool:
    asset_params = set(definition.asset_parameter_semantic_tags)
    variant_params = {
        item for item in variant.parameters_schema.get("required", ()) if item not in asset_params
    }
    other_params = {
        item for item in other.parameters_schema.get("required", ()) if item not in asset_params
    }
    same_slot = (
        variant.supported_card_sizes == other.supported_card_sizes
        and variant.supported_roles == other.supported_roles
        and _variant_requires_action(variant) == _variant_requires_action(other)
    )
    binding_subset = set(variant.required_bindings) <= set(other.required_bindings)
    parameter_subset = variant_params <= other_params
    strictly_more_complete = (
        set(variant.required_bindings) < set(other.required_bindings)
        or variant_params < other_params
    )
    return same_slot and binding_subset and parameter_subset and strictly_more_complete


def _semantic_text(task_spec: TaskSpec, ui_brief: Any) -> str:
    values = [task_spec.userQuery, json.dumps(task_spec.dataModelSchema, ensure_ascii=False)]
    if ui_brief is not None:
        values.append(json.dumps(ui_brief.model_dump(by_alias=True), ensure_ascii=False))
    return " ".join(values).casefold()


def _token_overlap(left: str, right: str) -> int:
    overlap = _semantic_tokens(left) & _semantic_tokens(right)
    return sum(max(1, len(token) - 1) for token in overlap)


def _semantic_tokens(value: str) -> set[str]:
    normalized = value.casefold()
    tokens = set(re.findall(r"[a-z0-9]+", normalized))
    for run in re.findall(r"[\u4e00-\u9fff]+", normalized):
        for width in range(2, min(4, len(run)) + 1):
            tokens.update(
                run[slice(index, index + width)] for index in range(len(run) - width + 1)
            )
    return tokens


def _resolve_content_action_ids(
    *,
    ui_brief: Any,
    actions: tuple[ActionBinding, ...],
    definitions: list[Any],
) -> tuple[str, ...]:
    if not actions:
        return ()
    placement = getattr(ui_brief, "action_placement", "auto")
    if placement in {"card", "none"}:
        return ()
    has_action_template = any(definition.action_policy != "none" for definition in definitions)
    if has_action_template and placement in {"content", "auto"}:
        return tuple(action.action_id for action in actions)
    return ()


def _collect_facts(value: Any, path: str = "", source: str = "task") -> list[Fact]:
    if isinstance(value, dict) and "sampleValue" in value:
        sample = value["sampleValue"]
        if sample is None or isinstance(sample, (str, int, float, bool)):
            return [Fact(source=source, path=path or "/", value=sample)]
    if isinstance(value, dict):
        result: list[Fact] = []
        for key, child in value.items():
            result.extend(_collect_facts(child, f"{path}/{key}", source))
        return result
    if isinstance(value, list) and value:
        return _collect_facts(value[0], f"{path}/0", source)
    return []


def _unique(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _action_label(event: Any) -> str:
    if getattr(event, "id", "") == "event.open.settings.parentControl":
        return "管控时间"
    display_label = getattr(event, "displayLabel", None)
    if isinstance(display_label, str) and display_label.strip():
        return display_label.strip()
    return _ACTION_LABELS.get(getattr(event, "id", "") or "", "打开详情")


def _build_action_bindings(task_spec: TaskSpec) -> tuple[ActionBinding, ...]:
    event_counts: dict[str, int] = {}
    for event in task_spec.eventCandidates:
        if not event.id:
            continue
        event_counts[event.id] = event_counts.get(event.id, 0) + 1

    event_occurrences: dict[str, int] = {}
    actions: list[ActionBinding] = []
    reserved_action_ids = set(event_counts)
    for event in task_spec.eventCandidates:
        event_id = event.id
        if not event_id:
            continue
        occurrence = event_occurrences.get(event_id, 0) + 1
        event_occurrences[event_id] = occurrence
        action_id = event_id
        event_count = event_counts.get(event_id)
        if event_count is None:
            raise ValueError("Event count is unavailable")
        if event_count > 1:
            action_id = f"{event_id}#{occurrence}"
            if action_id in reserved_action_ids:
                raise ValueError("Generated Action instance ID collides with an event ID")
        actions.append(
            ActionBinding(
                action_id=action_id,
                event_id=event_id,
                display_label=_action_label(event),
                call=event.call,
                args=event.args,
            )
        )
    return tuple(actions)


def _asset_semantic_tags(asset: dict[str, Any]) -> tuple[str, ...]:
    explicit = [
        str(tag).casefold()
        for tag in asset.get("sceneTags", [])
        if isinstance(tag, str) and tag.strip()
    ]
    searchable = " ".join(
        str(asset.get(key, "")) for key in ("id", "src", "description")
    ).casefold()
    inferred = [
        tag
        for tag, terms in _ASSET_SEMANTIC_TERMS.items()
        if any(term in searchable for term in terms)
    ]
    return tuple(dict.fromkeys([*explicit, *inferred]))
