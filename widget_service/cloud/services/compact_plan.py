# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact DSL 两阶段生成使用的信息计划合同。"""

from __future__ import annotations

import copy
import json
import math
import re
from dataclasses import dataclass, replace
from typing import Any

from core.json_pointer import parse_json_pointer
from models.generation import CompactDslRecoveryFact
from services.compact_action_instances import (
    action_instance_instruction,
    event_card_detail_action,
    event_card_item_handlers,
    plan_action_candidates,
    plan_action_handlers,
    prefers_event_card_item,
)
from services.compact_component_semantics import (
    CORE_INFORMATION_COMPONENT_TYPES,
    MODEL_COMPONENT_TYPES_BY_SIZE,
    SHARED_FACT_COMPONENTS,
)
from services.compact_composition_context import (
    composition_group_minimum_height,
    composition_implementation_conflicts,
    composition_region_capacity,
)
from services.compact_composition_planner import compound_duration_bindings
from services.compact_dsl_a2ui_converter import (
    MODEL_COMPACT_INPUT_COMPONENT_TYPES,
    ComponentRow,
    parse_compact_dsl_rows,
)
from services.compact_layout_runtime import (
    CompactLayoutRuntimeError,
    load_layout_contract,
    match_compact_layout,
)
from services.compact_plan_output import (
    PlanDuplicateKeyError,
    decode_plan_json,
    normalize_plan_output,
    normalize_plan_root_arguments,
)
from services.compact_whole_card_click import WHOLE_CARD_LAYOUTS, select_whole_card_click
from services.event_matching import event_handlers_match

SUBMIT_CARD_PLAN = "submit_card_plan"

_JSON_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL | re.IGNORECASE)
_BINDING_PATH = re.compile(r"\$\{(?P<path>/[^}\s]+)\}")
_FACT_KEYS = frozenset({"requirement", "priority", "dataId", "actionId", "text", "componentHints"})
_TARGET_KEYS = ("dataId", "actionId", "text")
_FACT_PRIORITIES = frozenset({"must", "should"})
_STATIC_DISPLAY_ROLES = ("title", "body", "label", "value", "leading", "trailing", "detail")
_STATIC_ROLE_ALIASES = {
    "description": "body",
    "primaryText": "value",
    "secondaryText": "title",
    "details": "detail",
}
_STATIC_FACT_SECTION_MARKER = "本轮卡片静态内容（用作展示的外部事实）："
_MAX_MUST_FACTS_BY_SIZE = {"2x2": 6, "2x4": 10}
_MAX_STATIC_OBJECT_GROUPS = 5
_FRESHNESS_METADATA_NAMES = frozenset(
    {
        "lastrefreshedat",
        "lastrefreshtime",
        "lastsyncedat",
        "lastsynctime",
        "lastupdatedat",
        "lastupdatetime",
        "refreshedat",
        "refreshtime",
        "updatedat",
        "updatetime",
    }
)
_FRESHNESS_REQUEST = re.compile(
    r"更新时间|更新于|最后更新|上次更新|刷新时间|最后刷新|同步时间|最后同步|"
    r"数据.{0,4}(?:新鲜|时效|过期)"
)
_PROGRESS_FACT_COMPONENTS = frozenset({"ProgressCircle", "ProgressLine2", "ProgressCircleSingle"})
_ACTION_FACT_COMPONENTS = frozenset({"PillButton", "CircleButton", "CardButton"})
_VISIBLE_PROP_NAMES = frozenset(
    {
        "content",
        "displayValue",
        "items",
        "label",
        "location",
        "mainText",
        "primaryText",
        "secondaryInfo",
        "secondaryLabel",
        "secondaryText",
        "supportingText",
        "time",
        "title",
        "total",
        "unit",
        "value",
        "externalText",
    }
)
_PROGRESS_VALUE_DRIVER_COMPONENTS = frozenset({"ProgressCircleSingle", "ProgressLine2"})
_LAYOUT_HINTS = {
    "2x2": (
        "S-center",
        "S-title-content",
        "S-title-content-action",
        "S-title-anchor",
        "S-content-dual-action",
        "S-dual-info",
        "S-title-dual-content",
        "S-title-dual-column-action",
        "S-title-primary-secondary-action",
        "S-quad-content",
    ),
    "2x4": (
        "W-top-bottom",
        "W-split-panels",
        "W-content-side-slots",
        "W-four-slots",
    ),
}


def _max_must_facts(size: Any) -> int:
    """返回当前尺寸 Plan 可接受的 must 事实与动作总数。"""
    return _MAX_MUST_FACTS_BY_SIZE.get(size, _MAX_MUST_FACTS_BY_SIZE["2x4"])


class CompactPlanValidationError(ValueError):
    """模型提交的 Compact Info Plan 不满足合同。"""

    def __init__(self, errors: list[str] | tuple[str, ...]) -> None:
        self.errors = tuple(dict.fromkeys(errors))
        super().__init__("; ".join(self.errors))


@dataclass(frozen=True)
class CompactPlanValidationResult:
    """标准化后的计划及不阻断生成的清理提示。"""

    plan: dict[str, Any]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompactOptionalDropCandidate:
    """描述一个可在最终兜底中删除的非 Action 组件。"""

    component_id: str
    component_type: str
    fact_indexes: tuple[int, ...]
    requirements: tuple[str, ...]
    contains_must_facts: bool
    partial: bool = False
    display_texts: tuple[str, ...] = ()
    item_indexes: tuple[int, ...] = ()
    item_signatures: tuple[str, ...] = ()
    requires_core_reattach: bool = False
    protected_core_component_ids: tuple[str, ...] = ()


def build_compact_plan_tool(
    task_spec: dict[str, Any],
    *,
    include_composition: bool = False,
    layout_scope: str | None = None,
    allowed_fact_targets: tuple[tuple[str, str], ...] | None = None,
    static_recovery_facts: tuple[CompactDslRecoveryFact, ...] = (),
) -> dict[str, Any]:
    """根据本次 TaskSpec 构造 submit_card_plan 的动态工具合同。"""
    size = task_spec.get("size")
    max_must_facts = _max_must_facts(size)
    data_paths = list(compact_plan_data_paths(task_spec))
    action_ids = list(compact_plan_action_ids(task_spec))
    allowed_texts: list[str] | None = None
    if allowed_fact_targets is not None:
        allowed = set(allowed_fact_targets)
        data_paths = [path for path in data_paths if ("dataId", path) in allowed]
        action_ids = [action_id for action_id in action_ids if ("actionId", action_id) in allowed]
        allowed_texts = [value for target, value in allowed_fact_targets if target == "text"]
    asset_ids = list(compact_plan_asset_ids(task_spec))
    target_variants: list[dict[str, Any]] = []
    if data_paths:
        target_variants.append({"required": ["dataId"]})
    if action_ids:
        target_variants.append({"required": ["actionId"]})
    if allowed_texts is None or allowed_texts:
        target_variants.append({"required": ["text"]})
    properties: dict[str, Any] = {
        "requirement": {
            "type": "string",
            "minLength": 1,
            "description": "一个需要规划可见落点的原子信息或操作。",
        },
        "priority": {
            "type": "string",
            "enum": ["must", "should"],
            "description": (
                "must 包括用户明确要求展示的每项内容、操作及用途成立必需的上下文；"
                "should 仅用于未明确要求、且省略后不改变主要用途的入选补充。"
                "不得为容量将明确要求降为 should。所有入选 actionId 必须为 must。"
                f"当前 {size} 最多可提交 {max_must_facts} 条 must 信息，Action 计入该数量。"
            ),
        },
        "componentHints": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": list(_component_hints(size)),
            },
            "minItems": 1,
            "maxItems": 3,
            "uniqueItems": True,
            "description": (
                "按优先级排列的组件候选；第一项是合同条件成立时应落实的首选，"
                "其余为不适配时的备选，不冻结实例数量。先按对象和信息关系合组，"
                "再给组内事实推荐可共同承载它们的组件，不默认逐字段拆成单文字组件。"
                "真实占比或进度可以绑定"
                "number/integer dataId，或已登记 numericSource 的展示 dataId；"
                "普通字符串、布尔值、静态正文和操作不推荐进度组件。"
                "SingleLineTitle 承担单行标题；DoubleLineTitle 承担标题加紧密相关的次信息。"
                "标题事实不得同时推荐正文或其它标题替代组件。"
                "CardButton 的图标可选：有语义匹配素材时优先使用真实图标；"
                "没有素材或没有准确匹配时仍可推荐 CardButton，并省略业务 icon；"
                "转换器会使用固定回退图标，不生成额外占位视觉。"
            ),
        },
    }
    if allowed_texts is None or allowed_texts:
        properties["text"] = {
            "type": "string",
            "minLength": 1,
            "description": (
                "逐字引用 userQuery 明确要求在卡面展示的静态正文；"
                "仅用于拨号、入会、导航等操作的参数不单独列为展示事实。"
            ),
        }
        if allowed_texts is not None:
            properties["text"]["enum"] = allowed_texts
    if data_paths:
        properties["dataId"] = {
            "type": "string",
            "enum": data_paths,
            "description": (
                "本轮实际选入展示的动态信息的真实 JSON Pointer，不因字段可用而全选；"
                "用户明确要求的每项内容必须保留，可选补充仅在相关且容量成立时选入。"
                "仅用于事件传参时不选。"
                "updatedAt、refreshTime 等刷新元数据默认不选；仅在用户明确要求、时效本身"
                "影响用途，或无动作且只有一个短文本核心信息导致卡面明显稀疏时选择。"
            ),
        }
    if action_ids:
        properties["actionId"] = {
            "type": "string",
            "enum": action_ids,
            "description": (
                "默认仅选择用户明确要求的操作，包括明确的点按查看详情；保留全部匹配操作。"
                "其它隐式只读详情仍是候选，不加入 info_required、不分配按钮素材。"
                "仅2x2单业务唯一天气城市或单条日程详情可按Plan例外选入，即使原query未提点击；"
                "须无用户禁止点击、明确按钮要求或其它必要动作，且同对象绑定符合登记合同。"
                "例外入选仍为must，由服务端复核整卡承载，不额外补按钮。"
                "副作用操作必须有明确授权。候选原有参数完整携带。"
                + action_instance_instruction(task_spec)
            ),
        }
    layout_hints = list(_layout_hints(size))
    max_layout_hints = 2
    layout_description = (
        "至多两个父布局软候选，不冻结最终骨架；仅填写枚举中的完整父布局 ID，"
        "不填写 Region/Group 变体，不使用简称。"
    )
    if size == "2x2" and layout_scope == "S-content-dual-action":
        layout_hints = ["S-content-dual-action"]
        max_layout_hints = 1
        layout_description = "两个必要动作只能使用 S-content-dual-action。"
    plan_properties: dict[str, Any] = {
        "info_required": {
            "type": "array",
            "description": (
                "提交前已完成取舍的实际展示与操作清单，不是全部候选。"
                "完整保留用户明确要求及必需上下文，主焦点遵从用户；"
                "未要求的额外补充不先全选再交 DSL 删除。"
            ),
            "minItems": 1,
            "maxItems": 24,
            "items": {
                "type": "object",
                "properties": properties,
                "required": ["requirement", "priority"],
                "oneOf": target_variants,
                "additionalProperties": False,
            },
        },
        "layoutHints": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": layout_hints,
            },
            "maxItems": max_layout_hints,
            "uniqueItems": True,
            "description": layout_description,
        },
    }
    required = ["info_required"]
    description = "提交卡片信息与操作的优先级；组件和布局只提供软候选。"
    description += (
        "Layout、Region、Group 的名称及 variant 只能逐字使用当前尺寸文档登记的完整值，"
        "不得自行缩写、拼接或增删后缀。选择布局候选前确认全部必要事实与动作都有合法落点。"
    )
    if size == "2x2" and not include_composition:
        description += (
            "单业务唯一天气城市详情或单条日程详情，未明确要求按钮时，由服务端判断整卡点击。"
            "仍提交该 actionId 且为 must，保留完整参数；不自行提交 wholeCardActionId。"
            "该详情无需按钮图标，可为动作分配 null 并说明整卡承载；拨号、导航、入会仍用按钮。"
        )
    if size == "2x4":
        description += (
            "标题＋主内容＋辅助内容使用 Region 的 title-hero-support，"
            "children 为 [title, hero, support]；Group 的 hero-support 只有 [hero, support]。"
            "Region 的 title-hero-support-action 必须包含第四项 PillButton；"
            "没有内部按钮时选择已登记的 title-hero-support。"
        )
    if asset_ids:
        assignment_properties = {
            "assetId": {
                "type": ["string", "null"],
                "enum": [*asset_ids, None],
                "description": "选择候选素材 ID；没有语义匹配素材时为 null。",
            },
            "reason": {
                "type": "string",
                "minLength": 1,
                "description": "assetId 为 null 时说明没有选择图标的具体原因。",
            },
        }
        title_assignment_properties = assignment_properties
        title_assignment_description = (
            "先完成动作图标分配，再从未使用素材中决定主 SingleLineTitle 图标。"
        )
        if size == "2x2" and layout_scope == "S-content-dual-action":
            title_assignment_properties = {
                "assetId": {
                    "type": "null",
                    "enum": [None],
                    "description": "固定双动作布局没有标题槽，必须为 null。",
                },
                "reason": assignment_properties["reason"],
            }
            title_assignment_description = (
                "S-content-dual-action 没有标题槽；剩余素材不分配给标题。"
            )
        plan_properties["assetAssignments"] = {
            "type": "object",
            "properties": {
                "actions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "actionId": {
                                "type": "string",
                                "enum": action_ids,
                            },
                            **assignment_properties,
                        },
                        "required": ["actionId", "assetId"],
                        "additionalProperties": False,
                    },
                    "maxItems": len(action_ids),
                    "description": (
                        "按 info_required 中的动作顺序逐项决定按钮图标。"
                        "先根据动作对象和完整操作语义，从 description 中选最匹配且"
                        "尚未使用的素材。没有准确匹配时 assetId 可以为 null；"
                        "CardButton 省略业务 icon，由转换器使用固定回退图标。"
                    ),
                },
                "title": {
                    "type": "object",
                    "properties": title_assignment_properties,
                    "required": ["assetId"],
                    "additionalProperties": False,
                    "description": title_assignment_description,
                },
            },
            "required": ["actions", "title"],
            "additionalProperties": False,
        }
        required.append("assetAssignments")
        if size == "2x2" and layout_scope == "S-content-dual-action":
            description += "存在素材候选时，优先分配给两个按钮；剩余素材不分配给标题。"
        else:
            description += "存在素材候选时，同时提交按钮优先、标题随后且不复用的素材分配。"
    if include_composition:
        plan_properties["composition"] = _composition_tool_schema(
            size,
            layout_scope=layout_scope,
        )
        required.append("composition")
        description += "同时提交可完整承载这些事实的分区、组件合组和容量计划。"
    tool = {
        "type": "function",
        "function": {
            "name": SUBMIT_CARD_PLAN,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": plan_properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }
    from services.generation_content_policy import current_content_policy

    if current_content_policy().is_static:
        _extend_static_plan_tool(tool, task_spec, static_recovery_facts)
    return tool


def _extend_static_plan_tool(
    tool: dict[str, Any], task: dict[str, Any],
    recovery_facts: tuple[CompactDslRecoveryFact, ...] = (),
) -> None:
    function = tool.get("function")
    if not isinstance(function, dict):
        raise ValueError("Plan 工具缺少 function。")
    parameters = function.get("parameters")
    if not isinstance(parameters, dict):
        raise ValueError("Plan 工具缺少 parameters。")
    properties = parameters.get("properties")
    if not isinstance(properties, dict):
        raise ValueError("Plan 工具缺少 properties。")
    facts = properties.get("info_required")
    if not isinstance(facts, dict):
        raise ValueError("Plan 工具缺少事实合同。")
    item = facts.get("items")
    fields = item.get("properties") if isinstance(item, dict) else None
    if not isinstance(fields, dict):
        raise ValueError("Plan 工具缺少事实字段。")
    fields["sourceTexts"] = {
        "type": "array",
        "minItems": 1,
        "maxItems": 3,
        "items": {"type": "string", "minLength": 1},
    }
    fields["protectedTexts"] = {
        "description": "仅用户明确要求逐字保留的原文片段；普通摘要填空数组。",
        "type": "array",
        "maxItems": 12,
        "items": {"type": "string", "minLength": 1},
    }
    fields["preserveVerbatim"] = {"type": "boolean"}
    fields["displayRole"] = {
        "enum": [*_STATIC_DISPLAY_ROLES, *_STATIC_ROLE_ALIASES],
        "description": (
            "可选展示角色；名称、正文、标签、值和侧栏分别作为事实，不从原句猜字段。"
            "共享正文说明使用body，共同标题使用title。兼容别名secondaryText在shared组"
            "归一为body，在object组保留原title语义；显式title不改。"
        ),
    }
    priority = fields.get("priority")
    if not isinstance(priority, dict):
        raise ValueError("Plan 工具缺少事实优先级合同。")
    priority["description"] = (
        "must 是本次选入的核心信息及使其独立可理解的主体、条件和范围；"
        "should 是可省略的入选补充。普通摘要按用途合理选择完整记录，"
        "不因输入提供了全部记录就全部标 must；未选内容记 omittedContents。"
        "用户明确要求全部、完整或逐字展示时不得擅自省略。"
        "计划接受后，不能为 DSL 容量任意把 must 降为 should。"
    )
    facts["description"] = (
        "本次选择的展示清单，不是全部原文清单。保留核心结论、必要主体与共同条件；"
        "普通摘要可按容量合理未选完整记录，并用 omittedContents 的空 factIndexes 记录。"
        "明确要求全部、完整或逐字展示的内容除外；未选内容不要放进无归属的事实条目。"
    )
    fields["text"] = {
        "type": "string",
        "minLength": 1,
        "description": (
            "模型按用途与容量总结后的最终展示版本，语义忠于sourceTexts，不要求逐字匹配。"
        ),
    }
    if recovery_facts:
        _restrict_static_recovery_facts(facts, item, fields, recovery_facts)
    properties["selectionNotes"] = {
        "type": "array",
        "maxItems": 8,
        "items": {"type": "string", "minLength": 1, "maxLength": 200},
        "description": "规划说明，不作为降级依据；实际删减另填omittedContents。",
    }
    properties["presentationStyle"] = {
        "enum": ["auto", "content", "rows", "records", "comparison"],
        "description": (
            "首次提交前按用户用途选择结构并核对实际槽位；活动、日程等名称加时地的"
            "多条同构记录优先records，"
            "每个object组对应一条真实记录，一项保留同一对象的主副信息；"
            "records/TextList带标题只能2项、无标题只能3项；"
            "rows/SingleLineList必须带标题且只能1到5条完整单行；"
            "短对象名加短月份、价格或状态能单行读完时优先rows；"
            "comparison仅2x4，带标题2到3项、无标题4项；"
            "content/EmphasisText只承载1个核心对象或结论。"
            "最多五个object组只是账本上限；shared标题会占标题区，"
            "shared公共说明仍须占所选正文组件的合法字段与高度；"
            "任何最终渲染为正文行的shared说明、例外或提示都计入组件实际条目数，"
            "不得因其不计object组数就在DSL中额外新增一行。"
        ),
    }
    properties["paletteFamily"] = {
        "enum": ["auto", "blue", "purple", "warm"],
        "description": "用户明确要求色系时登记；没有偏好用auto，由静态主题稳定分散。",
    }
    properties["omittedContents"] = {
        "type": "array",
        "maxItems": 24,
        "items": {
            "type": "object", "additionalProperties": False,
            "required": ["description", "factRefs"],
            "properties": {
                "description": {"type": "string", "minLength": 1, "maxLength": 200},
                "factRefs": {
                    "type": "array", "maxItems": 24, "uniqueItems": True,
                    "items": {
                        "type": "object", "additionalProperties": False,
                        "required": ["groupId", "factId"],
                        "properties": {
                            "groupId": {"type": "string", "minLength": 1},
                            "factId": {"type": "string", "minLength": 1},
                        },
                    },
                },
            },
        },
        "description": (
            "实际未选输入写description且factRefs为[]；计划内可能省略的should以groupId和factId"
            "稳定引用。最终覆盖决定是否确实遗漏。等义摘要、去重和按用户要求不展示均不算损失。"
        ),
    }
    nested_fact_fields = copy.deepcopy(fields)
    nested_fact_fields.pop("dataId", None)
    nested_fact_fields.pop("actionId", None)
    nested_fact_fields["id"] = {
        "type": "string", "minLength": 1,
        "description": "本组内稳定事实标识，仅供 omittedContents.factRefs 引用。",
    }
    nested_fact_item: dict[str, Any] = {
        "type": "object",
        "properties": nested_fact_fields,
        "required": ["id", "requirement", "priority", "text"],
        "additionalProperties": False,
    }
    item_constraints = item.get("allOf") if isinstance(item, dict) else None
    if isinstance(item_constraints, list):
        nested_fact_item["allOf"] = item_constraints
    properties.pop("info_required", None)
    required = parameters.get("required")
    if isinstance(required, list) and "info_required" in required:
        required.remove("info_required")
    properties["contentGroups"] = {
        "type": "array",
        "maxItems": 24,
        "description": (
            "这是完整事实账本，按数组顺序展示，每条facts内事实按数组顺序展开；"
            "每条保留text只属于一个object或shared组。"
            "按真实对象分组，不按类别合并不同记录。TextList最多三项的限制针对实际展示，"
            "不能据此漏掉账本组；先完成归属，再选择可承载的合法组件。"
            "共享标题使用独立且有来源的标题事实，不借用对象数值。"
        ),
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["id", "kind", "identity", "facts"],
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "kind": {"enum": ["object", "shared"]},
                "identity": {
                    "type": ["string", "null"], "minLength": 1, "maxLength": 120,
                    "description": (
                        "对象最终显示的短名称，忠于来源；无名称或shared填null。"
                        "若本组text已有同对象简称，同步统一名称版本，不能只写在内部ID中。"
                        "允许独立名称标签加正文；不必把identity重复写入每条text。"
                    ),
                },
                "facts": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 24,
                    "items": nested_fact_item,
                    "description": (
                        "本组事实，按顺序提交；不得输出factIndexes或依赖数组位置的数字引用。"
                    ),
                },
            },
        },
    }
    required = parameters.get("required")
    if isinstance(required, list):
        required.append("contentGroups")
        required.append("omittedContents")
    function["description"] = (
        "在同一次Plan中完成静态内容理解、摘要总结、must/should及对象分组。"
        "首次提交前按presentationStyle对应组件核算标题、对象条目和公共正文的实际容量。"
        "每个text必须在唯一contentGroups组的facts内提交；不输出info_required或factIndexes。"
        "Action不进入静态contentGroups；历史纯Action输入仅由兼容解析保留。"
        "同对象事实合组，共享标题或条件用shared；不同对象同文字不去重。"
        "优先可读出卡，按用途选择核心must和可省略补充should；取舍记selectionNotes。"
        "允许等义改写而不改变数值和关系含义；必要范围须进入展示文字，不能只写在规划中。"
        "用户要求完整或原文时不得省略；普通摘要不要求匹配原文片段。"
    )


def _restrict_static_recovery_facts(
    facts: dict[str, Any], item: dict[str, Any], fields: dict[str, Any],
    recovery_facts: tuple[CompactDslRecoveryFact, ...],
) -> None:
    """恢复阶段沿用已接受账本，Schema 与最终精确核对使用同一范围。"""
    variants = []
    texts = []
    for fact in recovery_facts:
        variants.append({
            "properties": {
                fact.target: {"const": fact.value},
                "priority": {"const": fact.priority},
            },
            "required": [fact.target, "priority"],
        })
        if fact.target == "text" and fact.value not in texts:
            texts.append(fact.value)
    fields["text"] = {
        "type": "string", "enum": texts,
        "description": "逐条复制 requiredFacts 的完整 text，不摘要、拆分或移入内部说明。",
    }
    facts["minItems"] = len(recovery_facts)
    facts["maxItems"] = len(recovery_facts)
    facts["description"] = (
        "逐项保留 requiredFacts 的 text 及其对应 priority；仅重新选择分组和展示组件。"
        "不得重加 excludedFacts，不能以同值重复条目替代其它事实。"
    )
    item["allOf"] = [{"anyOf": variants}]


@dataclass(frozen=True)
class _StaticPlanNormalization:
    facts: list[dict[str, Any]]
    warnings: list[str]
    groups: list[dict[str, Any]]
    selection_notes: list[str]
    omitted_contents: tuple[str, ...]
    presentation: str | None
    presentation_feedback: tuple[str, ...]
    index_map: dict[int, int]
    raw_facts: list[Any]
    omission_entries: list[Any]



@dataclass(frozen=True)
class _StaticOmissionDeclarations:
    descriptions: list[str]
    candidates: list[dict[str, Any]]
    warnings: list[str]


@dataclass(frozen=True)
class _StaticGroupNormalization:
    membership: dict[int, str]
    groups: list[dict[str, Any]]


def _static_omission_references_are_known(
    indexes: list[Any], raw_facts: list[Any], index_map: dict[int, int],
    accepted_facts: list[dict[str, Any]],
) -> bool:
    """拒绝授权后仍检查整条引用，不能把尾部未知内容当作已计划事实。"""
    if not indexes:
        return False
    seen: set[int] = set()
    for index in indexes:
        if type(index) is not int or not 0 <= index < len(raw_facts):
            return False
        if index in seen:
            return False
        seen.add(index)
        original = raw_facts[index]
        if not isinstance(original, dict) or not isinstance(original.get("text"), str):
            return False
        mapped = index_map.get(index)
        if type(mapped) is not int or not 0 <= mapped < len(accepted_facts):
            return False
        accepted = accepted_facts[mapped]
        if not isinstance(accepted, dict) or not isinstance(accepted.get("text"), str):
            return False
    return True


def _normalize_static_omissions(
    raw: Any, raw_facts: list[Any], index_map: dict[int, int], accepted_facts: list[dict[str, Any]],
    *, allow_legacy: bool = True,
) -> _StaticOmissionDeclarations:
    if not isinstance(raw, list) or len(raw) > 24:
        raise CompactPlanValidationError(["omittedContents 必须为最多24项的实际删减数组。"])
    descriptions = []
    candidates = []
    warnings = []
    for entry in raw:
        if not allow_legacy and not isinstance(entry, dict):
            raise CompactPlanValidationError([
                "新静态遗漏声明必须为{description,factIndexes}，不接受自由文字推断遗漏。"
            ])
        indexes = []
        description = entry
        if isinstance(entry, dict):
            if set(entry) != {"description", "factIndexes"}:
                raise CompactPlanValidationError(["遗漏声明只允许description、factIndexes。"])
            description = entry.get("description")
            indexes = entry.get("factIndexes")
        if not isinstance(description, str) or not description.strip():
            raise CompactPlanValidationError(["实际删减必须是非空文字。"])
        if len(description) > 200:
            raise CompactPlanValidationError(["每条实际删减最多200字符。"])
        if not isinstance(indexes, list) or len(indexes) > 24:
            raise CompactPlanValidationError(["遗漏事实引用必须为最多24项的索引数组。"])
        selected = []
        seen: set[int] = set()
        invalid_reason = None
        authorization_denied = False
        for index in indexes:
            if type(index) is not int or not 0 <= index < len(raw_facts):
                invalid_reason = "事实索引越界或类型错误"
                break
            if index in seen:
                raise CompactPlanValidationError(["遗漏事实索引不得重复。"])
            seen.add(index)
            original = raw_facts[index]
            if not isinstance(original, dict) or not isinstance(original.get("text"), str):
                raise CompactPlanValidationError(["遗漏引用仅支持静态text事实。"])
            protected = original.get("protectedTexts") or original.get("preserveVerbatim")
            if original.get("priority") != "should" or protected:
                invalid_reason = "引用了 must 或受保护事实"
                authorization_denied = True
                break
            mapped = index_map.get(index)
            if mapped is None:
                invalid_reason = "事实索引没有有效映射"
                break
            accepted_fact = accepted_facts[mapped]
            merged_protected = (
                accepted_fact.get("protectedTexts") or accepted_fact.get("preserveVerbatim")
            )
            if accepted_fact.get("priority") != "should" or merged_protected:
                invalid_reason = "去重后指向 must 或受保护事实"
                authorization_denied = True
                break
            if mapped not in selected:
                selected.append(mapped)
        if invalid_reason is not None:
            known_references = authorization_denied and _static_omission_references_are_known(
                indexes, raw_facts, index_map, accepted_facts,
            )
            if known_references:
                consequence = "已撤销删除授权；实际遗漏由最终覆盖核对。"
            else:
                descriptions.append(description)
                consequence = "已撤销删除授权并按未选入的 query 内容记录。"
            warnings.append(
                f"omittedContents「{description}」的 factIndexes {invalid_reason}，"
                f"{consequence}"
            )
            continue
        if selected:
            candidates.append({"description": description, "factIndexes": selected})
        else:
            descriptions.append(description)
    return _StaticOmissionDeclarations(descriptions, candidates, warnings)


def _normalize_static_groups(
    raw_groups: list[Any],
    raw_facts: list[Any],
    errors: list[str],
    warnings: list[str],
) -> _StaticGroupNormalization:
    """校验正文分组，并确定性移除误入分组的纯 Action。"""
    membership: dict[int, str] = {}
    identifiers: set[str] = set()
    normalized_groups: list[dict[str, Any]] = []
    warned_action_indexes: set[int] = set()
    for group_index, group in enumerate(raw_groups):
        path = f"contentGroups[{group_index}]"
        if not isinstance(group, dict):
            errors.append(f"{path}: contentGroups 必须为对象数组。")
            continue
        required_keys = {"id", "kind", "factIndexes"}
        if not required_keys.issubset(group) or set(group) - (required_keys | {"identity"}):
            errors.append(f"{path}: contentGroups 仅支持 id、kind、factIndexes、identity。")
        object_name = group.get("identity")
        if object_name is not None:
            if not isinstance(object_name, str):
                errors.append(f"{path}.identity: identity 必须为对象短名称或null。")
            elif not object_name.strip() or len(object_name) > 120:
                errors.append(f"{path}.identity: identity 必须为1–120字的对象短名称。")
            if group.get("kind") == "shared":
                errors.append(f"{path}.identity: shared的identity必须为null。")
        identifier = group.get("id")
        if not isinstance(identifier, str) or not identifier.strip():
            errors.append(f"{path}.id: 内容组 ID 必须非空。")
            continue
        kind = group.get("kind")
        if not isinstance(kind, str):
            errors.append(f"{path}.kind: 内容组 kind 必须是字符串。")
        elif kind not in {"object", "shared"}:
            errors.append(f"{path}.kind: 内容组 kind 必须为object或shared。")
        if identifier in identifiers:
            errors.append(f"{path}.id: 内容组 ID 重复。")
        identifiers.add(identifier)
        indexes = group.get("factIndexes")
        if not isinstance(indexes, list) or not indexes:
            errors.append(f"{path}.factIndexes: 内容组必须引用至少一条静态事实。")
            continue
        text_indexes: list[int] = []
        for position, index in enumerate(indexes):
            index_path = f"{path}.factIndexes[{position}]"
            if type(index) is not int or not 0 <= index < len(raw_facts):
                errors.append(
                    f"{index_path}: 内容组事实索引越界或类型错误。实际值={index!r}；"
                    f"本次info_required共{len(raw_facts)}条，"
                    f"有效整数索引为0–{len(raw_facts) - 1}；"
                    "不得使用来源条目编号，合并或删减事实后须同步引用。"
                )
                continue
            indexed_fact = raw_facts[index]
            is_action = (
                isinstance(indexed_fact, dict)
                and isinstance(indexed_fact.get("actionId"), str)
                and "text" not in indexed_fact
            )
            if is_action:
                if index not in warned_action_indexes:
                    warnings.append(
                        f"contentGroups 引用了 Action 事实索引 {index}，已自动移出正文分组。"
                    )
                    warned_action_indexes.add(index)
                continue
            if index in membership:
                errors.append(
                    f"{index_path}: 每条静态事实只能归属一个组，组内索引不得重复。"
                    f"索引{index}已归属{membership.get(index)!r}。"
                )
            else:
                membership[index] = identifier
                text_indexes.append(index)
        if text_indexes:
            normalized_group = dict(group)
            normalized_group["factIndexes"] = text_indexes
            normalized_groups.append(normalized_group)
    return _StaticGroupNormalization(membership, normalized_groups)


def _collect_static_source_errors(
    raw_facts: list[Any],
    source: str,
    membership: dict[int, str],
    errors: list[str],
    warnings: list[str],
    *,
    require_references: bool,
) -> None:
    from config.config import get_settings
    from services.card_validation.compact_validation.semantic.cross_file import static_source_errors

    reference_count = 0
    for index, raw_fact in enumerate(raw_facts):
        if not isinstance(raw_fact, dict) or "text" not in raw_fact:
            continue
        path = f"info_required[{index}]"
        references = raw_fact.get("sourceTexts")
        missing_references = references is None or references == []
        protected = raw_fact.get("protectedTexts") or raw_fact.get("preserveVerbatim") is True
        if missing_references:
            if require_references:
                errors.append(
                    f"{path}: 提供了静态事实段时，每条静态 text 必须引用该段中的非空 sourceTexts。"
                )
            elif protected:
                errors.append(f"{path}: 受保护或要求原文展示的静态 text 必须提交非空 sourceTexts。")
            else:
                warnings.append(f"静态 text 事实索引 {index} 缺少 sourceTexts，已保留为 warning。")
        else:
            for error in static_source_errors(raw_fact, source):
                errors.append(f"{path}: {error}")
        if index not in membership:
            errors.append(f"{path}: 每条静态text必须归属contentGroups。")
        if isinstance(references, list):
            reference_count += len(references)
            if len(references) > 3:
                errors.append(
                    f"{path}.sourceTexts: 单事实最多引用三段来源。实际{len(references)}段；"
                    "请引用1–3段连续原文上下文，或重新组织展示事实并同步分组索引。"
                )
    if reference_count > get_settings().static_content_max_source_references:
        errors.append("info_required: 静态来源引用数量超过预算。")


def static_fact_source(user_query: str) -> tuple[str, bool]:
    """提取显式附加的静态事实段，避免把用户期望误作已获事实。"""
    _, marker, fact_source = user_query.partition(_STATIC_FACT_SECTION_MARKER)
    if not marker:
        return user_query, False
    return fact_source.strip(), True


def _static_presentation_consistency_errors(
    facts: list[dict[str, Any]],
    groups: list[dict[str, Any]],
    presentation_style: str,
    *,
    presentation: str | None = None,
    size: str | None = None,
) -> list[str]:
    """拒绝模型已显式指定的正文组件与展示风格相互冲突的 Plan。"""
    expected_components = {
        "records": "TextList",
        "rows": "SingleLineList",
        "comparison": "ComparisonGroup",
    }
    expected = expected_components.get(presentation_style)
    if expected is None:
        return []
    body_components = set(expected_components.values())
    object_count = sum(group.get("kind") == "object" for group in groups)
    errors = []
    if presentation_style == "records" and object_count == 3:
        for group in groups:
            if group.get("kind") != "shared":
                continue
            for index in group.get("factIndexes", []):
                fact = facts[index]
                title_is_protected = bool(
                    fact.get("protectedTexts") or fact.get("preserveVerbatim")
                )
                title_is_required = fact.get("priority") != "should" or title_is_protected
                is_required_title = (
                    fact.get("displayRole") == "title"
                    and title_is_required
                )
                if is_required_title:
                    from services.card_validation.compact_validation.semantic.layout import (
                        text_capacity,
                    )

                    candidate_plan = {
                        "info_required": facts, "contentGroups": groups,
                        "staticPresentation": presentation,
                    }
                    if text_capacity.static_plan_candidate_preserves_required_content(
                        candidate_plan, size,
                    ):
                        continue
                    return [
                        "三条 records/TextList 优先不设共同标题：将可省略主题改为 should，"
                        "或把必要主题归入首条对象后再提交；不能减少核心记录。"
                    ]
    for group in groups:
        if group.get("kind") != "object":
            continue
        for index in group.get("factIndexes", []):
            hints = facts[index].get("componentHints", [])
            if not isinstance(hints, list):
                continue
            selected = next((hint for hint in hints if hint in body_components), None)
            if selected is not None and selected != expected:
                errors.append(
                    "presentationStyle 与 componentHints 冲突："
                    f"{presentation_style} 需要 {expected}，但对象事实首选 {selected}。"
                )
                return errors
    return errors


def _nested_static_plan_input(
    arguments: dict[str, Any],
) -> tuple[list[Any], list[Any], list[Any]]:
    """将模型侧嵌套分组确定性展开为内部索引账本的输入。"""
    submitted_groups = arguments.get("contentGroups")
    has_legacy_facts = "info_required" in arguments
    has_nested_facts = False
    if isinstance(submitted_groups, list):
        has_nested_facts = any(
            isinstance(group, dict) and "facts" in group for group in submitted_groups
        )
    if has_legacy_facts and has_nested_facts:
        raise CompactPlanValidationError([
            "静态Plan不能同时提交info_required和contentGroups.facts。"
        ])
    if has_legacy_facts:
        raw_facts = arguments.get("info_required")
        raw_omissions = arguments.get("omittedContents", [])
        if not isinstance(raw_facts, list):
            raise CompactPlanValidationError(["静态计划必须包含 1–24 条事实或动作。"])
        return raw_facts, submitted_groups, raw_omissions
    if not isinstance(submitted_groups, list):
        raise CompactPlanValidationError(["静态计划必须包含嵌套contentGroups。"])
    raw_facts: list[Any] = []
    raw_groups: list[dict[str, Any]] = []
    references: dict[tuple[str, str], int] = {}
    group_ids: set[str] = set()
    for group_index, group in enumerate(submitted_groups):
        path = f"contentGroups[{group_index}]"
        if not isinstance(group, dict):
            raise CompactPlanValidationError([f"{path}: contentGroups 必须为对象数组。"])
        required_keys = {"id", "kind", "identity", "facts"}
        if set(group) != required_keys:
            raise CompactPlanValidationError([f"{path}: 嵌套组只允许id、kind、identity、facts。"])
        group_id = group.get("id")
        if not isinstance(group_id, str) or not group_id.strip():
            raise CompactPlanValidationError([f"{path}.id: 内容组 ID 必须非空。"])
        if group_id in group_ids:
            raise CompactPlanValidationError([f"{path}.id: 内容组 ID 重复。"])
        group_ids.add(group_id)
        group_facts = group.get("facts")
        if not isinstance(group_facts, list) or not group_facts:
            raise CompactPlanValidationError([f"{path}.facts: 内容组必须包含至少一条事实。"])
        indexes: list[int] = []
        fact_ids: set[str] = set()
        for fact_index, fact in enumerate(group_facts):
            fact_path = f"{path}.facts[{fact_index}]"
            if not isinstance(fact, dict):
                raise CompactPlanValidationError([f"{fact_path}: 事实必须是对象。"])
            fact_id = fact.get("id")
            if not isinstance(fact_id, str) or not fact_id.strip():
                raise CompactPlanValidationError([f"{fact_path}.id: 组内事实 ID 必须非空。"])
            if fact_id in fact_ids:
                raise CompactPlanValidationError([f"{fact_path}.id: 组内事实 ID 重复。"])
            if "actionId" in fact or "dataId" in fact:
                raise CompactPlanValidationError([
                    f"{fact_path}: 静态嵌套正文不允许Action或动态数据事实。"
                ])
            fact_ids.add(fact_id)
            references[(group_id, fact_id)] = len(raw_facts)
            normalized_fact = dict(fact)
            normalized_fact.pop("id", None)
            raw_facts.append(normalized_fact)
            indexes.append(len(raw_facts) - 1)
        raw_groups.append({
            "id": group_id,
            "kind": group.get("kind"),
            "identity": group.get("identity"),
            "factIndexes": indexes,
        })
    raw_omissions = _nested_static_omissions(arguments.get("omittedContents", []), references)
    return raw_facts, raw_groups, raw_omissions


def _nested_static_omissions(
    raw: Any, references: dict[tuple[str, str], int],
) -> list[dict[str, Any]]:
    """把模型侧稳定引用转换成内部遗漏索引，不猜测未提交事实。"""
    if not isinstance(raw, list) or len(raw) > 24:
        raise CompactPlanValidationError(["omittedContents 必须为最多24项的实际删减数组。"])
    converted = []
    for entry_index, entry in enumerate(raw):
        path = f"omittedContents[{entry_index}]"
        if not isinstance(entry, dict) or set(entry) != {"description", "factRefs"}:
            raise CompactPlanValidationError([f"{path}: 遗漏声明只允许description、factRefs。"])
        refs = entry.get("factRefs")
        if not isinstance(refs, list) or len(refs) > 24:
            raise CompactPlanValidationError([f"{path}.factRefs: 必须为最多24项的数组。"])
        indexes: list[int] = []
        invalid_reference = False
        for ref_index, reference in enumerate(refs):
            ref_path = f"{path}.factRefs[{ref_index}]"
            if not isinstance(reference, dict) or set(reference) != {"groupId", "factId"}:
                raise CompactPlanValidationError([f"{ref_path}: 只允许groupId、factId。"])
            group_id = reference.get("groupId")
            fact_id = reference.get("factId")
            if not isinstance(group_id, str) or not isinstance(fact_id, str):
                raise CompactPlanValidationError([f"{ref_path}: groupId、factId必须为字符串。"])
            index = references.get((group_id, fact_id))
            if index is None:
                invalid_reference = True
                break
            if index in indexes:
                invalid_reference = True
                break
            indexes.append(index)
        if invalid_reference:
            indexes = []
        converted.append({"description": entry.get("description"), "factIndexes": indexes})
    return converted


def _normalize_static_plan(
    arguments: dict[str, Any], task: dict[str, Any]
) -> _StaticPlanNormalization:
    raw_facts, raw_groups, omission_entries = _nested_static_plan_input(arguments)
    user_query = task.get("userQuery")
    if not isinstance(user_query, str):
        raise CompactPlanValidationError(["静态来源需求必须是字符串。"])
    source_query, has_explicit_fact_source = static_fact_source(user_query)
    if not 1 <= len(raw_facts) <= 24:
        raise CompactPlanValidationError(["静态计划必须包含 1–24 条事实或动作。"])
    warnings: list[str] = []
    normalized_facts: list[Any] = []
    for index, raw_fact in enumerate(raw_facts):
        normalized_fact = raw_fact
        if isinstance(raw_fact, dict):
            has_action = isinstance(raw_fact.get("actionId"), str)
            if has_action and isinstance(raw_fact.get("text"), str):
                normalized_fact = dict(raw_fact)
                for field_name in (
                    "text",
                    "sourceTexts",
                    "protectedTexts",
                    "preserveVerbatim",
                    "displayRole",
                ):
                    normalized_fact.pop(field_name, None)
                warnings.append(
                    f"静态事实索引 {index} 同时包含 text 与 actionId，已优先保留 Action。"
                )
        normalized_facts.append(normalized_fact)
    raw_facts = normalized_facts
    pure_actions = True
    for raw_fact in raw_facts:
        if not isinstance(raw_fact, dict):
            pure_actions = False
            break
        if "text" in raw_fact or "dataId" in raw_fact:
            pure_actions = False
            break
        if not isinstance(raw_fact.get("actionId"), str):
            pure_actions = False
            break
    if raw_groups is None and pure_actions:
        raw_groups = []
    if not isinstance(raw_groups, list) or len(raw_groups) > 24:
        raise CompactPlanValidationError(["静态计划必须包含 contentGroups，最多24组。"])
    errors: list[str] = []
    group_normalization = _normalize_static_groups(raw_groups, raw_facts, errors, warnings)
    membership = group_normalization.membership
    raw_groups = group_normalization.groups
    object_count = sum(group.get("kind") == "object" for group in raw_groups)
    if object_count > _MAX_STATIC_OBJECT_GROUPS:
        errors.append(
            "静态正文最多五条完整对象信息（标题和shared公共说明不计入）；"
            "当前为"
            f"{object_count}条。请在Plan阶段按完整object组取舍，不能只删除对象的部分字段。"
        )
    _collect_static_source_errors(
        raw_facts,
        source_query,
        membership,
        errors,
        warnings,
        require_references=has_explicit_fact_source,
    )
    if errors:
        raise CompactPlanValidationError(errors)
    facts: list[dict[str, Any]] = []
    old_to_new: dict[int, int] = {}
    identities: dict[tuple[str, str, str, str | None], int] = {}
    extras = {"sourceTexts", "protectedTexts", "preserveVerbatim", "displayRole"}
    shared_group_ids = {
        group.get("id") for group in raw_groups if group.get("kind") == "shared"
    }
    for old_index, raw_fact in enumerate(raw_facts):
        if not isinstance(raw_fact, dict) or set(raw_fact) - (_FACT_KEYS | extras):
            raise CompactPlanValidationError(["静态事实包含非法结构或未知字段。"])
        if "dataId" in raw_fact:
            raise CompactPlanValidationError(["静态计划不得声明动态数据事实。"])
        hints = raw_fact.get("componentHints", [])
        if isinstance(hints, list):
            if any(hint not in _component_hints(task.get("size")) for hint in hints):
                raise CompactPlanValidationError(
                    ["静态计划仅允许文本列表、单行列表、强调文本、宽卡对比及标题。"]
                )
        basic = dict(raw_fact)
        for key in extras:
            basic.pop(key, None)
        is_text = "text" in raw_fact
        if is_text:
            display_role = raw_fact.get("displayRole")
            if "displayRole" in raw_fact:
                if not isinstance(display_role, str):
                    raise CompactPlanValidationError(["静态 displayRole 必须为已登记角色。"])
                if (
                    display_role == "secondaryText"
                    and membership.get(old_index) in shared_group_ids
                ):
                    display_role = "body"
                else:
                    display_role = _STATIC_ROLE_ALIASES.get(display_role, display_role)
                if display_role not in _STATIC_DISPLAY_ROLES:
                    raise CompactPlanValidationError(["静态 displayRole 不在已登记角色中。"])
        elif old_index in membership or extras.intersection(raw_fact):
            raise CompactPlanValidationError(["Action不得填写静态来源字段或加入正文组。"])
        accepted, notes = _validate_facts(
            [basic],
            task,
            static_text_source=None,
            static_content=True,
        )
        fact = accepted[0]
        if is_text:
            fact["text"] = raw_fact.get("text")
        for key in extras:
            if key in raw_fact:
                fact[key] = raw_fact.get(key)
        if is_text and "displayRole" in raw_fact:
            fact["displayRole"] = display_role
        warnings.extend(notes)
        target = fact.get("text") if is_text else fact.get("actionId")
        if not isinstance(target, str):
            raise CompactPlanValidationError(["静态事实必须包含展示文字或已登记动作。"])
        identity = (
            membership.get(old_index, "action"),
            target,
            json.dumps(fact.get("sourceTexts"), ensure_ascii=False),
            fact.get("displayRole"),
        )
        previous_index = identities.get(identity)
        if previous_index is not None:
            previous = facts[previous_index]
            if fact.get("priority") == "must":
                previous["priority"] = "must"
            if is_text:
                previous["preserveVerbatim"] = bool(
                    previous.get("preserveVerbatim") or fact.get("preserveVerbatim")
                )
                protected = list(previous.get("protectedTexts", []))
                for fragment in fact.get("protectedTexts", []):
                    if fragment not in protected:
                        protected.append(fragment)
                if protected:
                    previous["protectedTexts"] = protected
            old_to_new[old_index] = previous_index
            continue
        old_to_new[old_index] = len(facts)
        identities[identity] = len(facts)
        facts.append(fact)
    groups = []
    for group in raw_groups:
        indexes = []
        for old_index in group.get("factIndexes", []):
            new_index = old_to_new.get(old_index)
            if new_index is None:
                raise CompactPlanValidationError(["内容组索引映射丢失。"])
            if new_index not in indexes:
                indexes.append(new_index)
        normalized_group = {
            "id": group.get("id"), "kind": group.get("kind"), "factIndexes": indexes,
        }
        if "identity" in group:
            normalized_group["identity"] = group.get("identity")
        groups.append(normalized_group)
    from services.static_content_context import StaticContentContext
    from services.static_content_planning import select_static_plan_content

    selection = select_static_plan_content(
        facts, groups, source_query, task.get("size"),
        presentation_style=arguments.get("presentationStyle", "auto"),
    )
    facts = selection.facts
    groups = selection.groups
    consistency_errors = _static_presentation_consistency_errors(
        facts,
        groups,
        arguments.get("presentationStyle", "auto"),
        presentation=selection.presentation,
        size=task.get("size"),
    )
    if consistency_errors:
        raise CompactPlanValidationError(consistency_errors)

    try:
        StaticContentContext.from_plan(source_query, {"info_required": facts})
    except ValueError as exc:
        raise CompactPlanValidationError([str(exc)]) from exc
    return _StaticPlanNormalization(
        facts, warnings, groups, selection.notes, selection.omitted_contents,
        selection.presentation, selection.trial_errors, old_to_new, raw_facts, omission_entries,
    )


def _composition_tool_schema(
    size: Any,
    *,
    layout_scope: str | None = None,
) -> dict[str, Any]:
    """实例级实现计划；事实仍由 info_required 独立确定。"""
    integer = {"type": "integer", "minimum": 0, "maximum": 23}
    extent = {"type": "number", "minimum": 0}
    group = {
        "type": "object",
        "properties": {
            "component": {
                "type": "string",
                "enum": list(_component_hints(size)),
            },
            "factIndexes": {
                "type": "array",
                "items": integer,
                "minItems": 0,
                "maxItems": 24,
                "description": ("只有装饰 SingleLineTitle 可以为空；同事实多属性重复索引。"),
            },
            "placements": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 0,
                "maxItems": 24,
                "description": "逐条对应 factIndexes 的可见 Prop，如 items[0].value。",
            },
            "referenceHeight": {**extent, "description": "完整组件按实际条数/行数合计占高。"},
            "variant": {"type": "string"},
            "density": {"type": "string", "enum": ["compact"]},
            "columns": {"type": "integer", "enum": [1, 2]},
            "lines": {
                "type": "array",
                "items": {"type": "integer", "enum": [1, 2]},
                "description": "依每个实际文本 item 顺序记录行数，不一律设两行。",
            },
            "labelLines": {"type": "integer", "enum": [1, 2]},
        },
        "required": ["component", "factIndexes", "placements", "referenceHeight"],
        "additionalProperties": False,
    }
    region = {
        "type": "object",
        "properties": {
            "id": {"type": "string", "minLength": 1},
            "path": {
                "type": "array",
                "items": integer,
                "description": "选定布局内从 root 开始的子序号；全卡为[]。",
            },
            "referenceWidth": {**extent, "description": "已扣此区域内边距的可用宽度。"},
            "referenceHeight": {**extent, "description": "已扣此区域内边距的可用高度。"},
            "gap": {**extent, "description": "合同允许的组间距，不改组件内部间距。"},
            "groups": {"type": "array", "items": group, "minItems": 1, "maxItems": 24},
        },
        "required": ["id", "path", "referenceWidth", "referenceHeight", "gap", "groups"],
        "additionalProperties": False,
    }
    composition_layouts = list(_layout_hints(size))
    if size == "2x2" and layout_scope == "S-content-dual-action":
        composition_layouts = ["S-content-dual-action"]
    return {
        "type": "object",
        "properties": {
            "layout": {"type": "string", "enum": composition_layouts},
            "variant": {"type": "integer", "minimum": 1},
            "regions": {"type": "array", "items": region, "minItems": 1, "maxItems": 8},
        },
        "required": ["layout", "variant", "regions"],
        "additionalProperties": False,
        "description": (
            "实例级分区合组计划：覆盖全部必要事实与动作，核算横向文字与纵向占高，"
            "参考尺寸来自当前合同，不写成固定输出宽高；不能缩字或删信息。"
        ),
    }


def _finite_extent(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def _normalize_composition(
    value: Any,
    raw_facts: Any,
    facts: list[dict[str, Any]],
    size: Any,
) -> tuple[dict[str, Any] | None, list[str]]:
    """标准化实现方案；调用方根据运行模式决定是否阻断。"""
    if value is None:
        return None, []
    warning = "composition ignored: regroup all facts with valid layout, placements and budgets."
    schema = _composition_tool_schema(size)
    if not isinstance(value, dict) or set(value) != {"layout", "variant", "regions"}:
        return None, [warning]
    variant = value.get("variant")
    valid_variant = isinstance(variant, int) and not isinstance(variant, bool) and variant > 0
    if value.get("layout") not in _layout_hints(size) or not valid_variant:
        return None, [warning]
    layout = load_layout_contract().get("layouts", {}).get(value.get("layout"), {})
    if variant > len(layout.get("patterns", [])):
        return None, [warning]
    action_count = sum(1 for fact in facts if _requires_action_button(fact))
    action_range = layout.get("actionCount", {})
    if not action_range.get("min", 0) <= action_count <= action_range.get("max", action_count):
        return None, [
            "composition layout cannot carry all required actions; "
            "choose a compatible layout without removing any action."
        ]
    regions = value.get("regions")
    if not isinstance(regions, list) or not 1 <= len(regions) <= 8:
        return None, [warning]
    identities: list[tuple[str, str]] = []
    for fact in facts:
        for key in _TARGET_KEYS:
            if key in fact:
                identities.append((key, fact.get(key)))
                break
    index_map: dict[int, int] = {}
    for index, fact in enumerate(raw_facts):
        for key in _TARGET_KEYS:
            target = fact.get(key)
            if isinstance(target, str) and (key, target.strip()) in identities:
                index_map[index] = identities.index((key, target.strip()))
    region_schema = schema.get("properties", {}).get("regions", {}).get("items", {})
    group_schema = region_schema.get("properties", {}).get("groups", {}).get("items", {})
    covered: set[int] = set()
    normalized: list[dict[str, Any]] = []
    notes: list[str] = []
    for region in regions:
        if not _composition_region_shape(region, region_schema):
            return None, [warning]
        if size == "2x2":
            region, slot_note = _small_content_region(region, layout, variant)
            if slot_note is not None:
                notes.append(slot_note)
        capacity = composition_region_capacity(
            size,
            value.get("layout"),
            variant,
            region.get("path"),
        )
        region = dict(region)
        if capacity is not None:
            region.update(
                referenceWidth=capacity.get("width"), referenceHeight=capacity.get("height")
            )
            if capacity.get("fixedGap") is not None:
                region["gap"] = capacity.get("fixedGap")
            region["capacitySource"] = "layout_contract"
        else:
            region["capacitySource"] = "model_estimate"
            notes.append(
                f"region {region.get('id')} capacity must be checked against "
                "the complete layout contract before generating."
            )
        groups: list[dict[str, Any]] = []
        for group in region.get("groups"):
            normalized_group = _composition_group(
                group,
                group_schema,
                index_map,
                facts,
                size,
            )
            if normalized_group is None:
                return None, [warning]
            group_indexes = normalized_group.get("factIndexes")
            if not isinstance(group_indexes, list):
                return None, [warning]
            duplicate_data_indexes: set[int] = set()
            indexes_in_group: set[int] = set()
            for fact_index in group_indexes:
                is_duplicate = fact_index in indexes_in_group or fact_index in covered
                indexes_in_group.add(fact_index)
                if not is_duplicate or not 0 <= fact_index < len(facts):
                    continue
                if isinstance(facts[fact_index].get("dataId"), str):
                    duplicate_data_indexes.add(fact_index)
            if duplicate_data_indexes:
                return None, [
                    "composition duplicates an info_required data fact across visible "
                    "placements; assign every dataId to exactly one visible placement."
                ]
            covered.update(group_indexes)
            notes.extend(normalized_group.get("placementNotes", []))
            groups.append(normalized_group)
        height = sum(group.get("referenceHeight") for group in groups)
        height += region.get("gap") * (len(groups) - 1)
        remaining = region.get("referenceHeight") - height
        height_tolerance = 2.0 if size == "2x2" else 0.0
        if remaining < -height_tolerance:
            notes.append(
                f"region {region.get('id')} overflows by {-remaining:g}vp; "
                "replace this complete grouping, do not shrink or omit facts."
            )
        normalized.append(
            {**region, "groups": groups, "requiredHeight": height, "remainingHeight": remaining}
        )
    if covered != set(range(len(facts))):
        return None, [
            "composition incomplete: retain every info_required fact and action; "
            "rebuild complete region assignments before generating."
        ]
    return {"layout": value.get("layout"), "variant": variant, "regions": normalized}, notes


def _anchor_plan_errors(
    facts: list[dict[str, Any]],
    layout_hints: list[str],
    composition: dict[str, Any] | None,
) -> list[str]:
    """阻止没有独立左下支撑事实的 Anchor 进入生成阶段。"""
    composition_is_anchor = (
        isinstance(composition, dict) and composition.get("layout") == "S-title-anchor"
    )
    if not composition_is_anchor and "S-title-anchor" not in layout_hints:
        return []
    if not composition_is_anchor:
        body_facts: list[dict[str, Any]] = []
        for fact in facts:
            if "actionId" in fact:
                continue
            if fact.get("componentHints") == ["SingleLineTitle"]:
                continue
            body_facts.append(fact)
        if len(body_facts) >= 2:
            return []
        return [
            "S-title-anchor requires one primary body fact and at least one independent "
            "support fact; title-only context and actions do not count. Remove the Anchor "
            "hint and choose a text-action layout when support is empty."
        ]

    support_indexes: set[int] = set()
    other_visible_indexes: set[int] = set()
    for region in composition.get("regions", []):
        path = tuple(region.get("path", []))
        indexes: set[int] = set()
        for group in region.get("groups", []):
            for index in group.get("factIndexes", []):
                if not isinstance(index, int) or not 0 <= index < len(facts):
                    continue
                if "actionId" not in facts[index]:
                    indexes.add(index)
        if path[:3] == (1, 1, 0):
            support_indexes.update(indexes)
        elif path[:1] == (0,) or path[:2] == (1, 0):
            other_visible_indexes.update(indexes)
    independent_support = support_indexes - other_visible_indexes
    if independent_support:
        return []
    return [
        "S-title-anchor composition must assign at least one independent non-action fact "
        "to support path [1, 1, 0]; a title fact, duplicated primary fact, empty group or "
        "invented label cannot fill the left support region. Choose a text-action layout."
    ]


def _secondary_body_composition_errors(
    composition: dict[str, Any] | None,
) -> list[str]:
    """Require planned SecondaryBody groups to have a core group in the card."""
    if not isinstance(composition, dict):
        return []
    components: set[str] = set()
    for region in composition.get("regions", []):
        if not isinstance(region, dict):
            continue
        groups = region.get("groups", [])
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            component = group.get("component")
            if isinstance(component, str):
                components.add(component)
    if "SecondaryBody" not in components:
        return []
    if components & CORE_INFORMATION_COMPONENT_TYPES:
        return []
    return [
        "composition uses SecondaryBody without a core information component anywhere "
        "in the card; titles, buttons, layout containers and other SecondaryBody groups "
        "do not count."
    ]


def _small_content_region(
    region: dict[str, Any],
    layout: dict[str, Any],
    variant: int,
) -> tuple[dict[str, Any], str | None]:
    """正文误分到带嵌套动作的父区时，交接真实纯正文槽，不重复分配动作高度。"""
    groups = region.get("groups", [])
    if not groups or any(not isinstance(group, dict) for group in groups):
        return region, None
    if any(
        group.get("component") in {"SingleLineTitle", "DoubleLineTitle", *_ACTION_FACT_COMPONENTS}
        for group in groups
    ):
        return region, None
    path = tuple(region.get("path", []))
    rules = layout.get("patterns", [])[variant - 1].get("rules", [])
    action_paths = [
        tuple(rule.get("path", [])) for rule in rules if rule.get("eventPolicy") == "require"
    ]
    if not any(len(action) > len(path) and action[: len(path)] == path for action in action_paths):
        return region, None
    slots = []
    for rule in rules:
        slot = rule.get("path", [])
        if len(slot) != len(path) + 1 or tuple(slot)[: len(path)] != path:
            continue
        if rule.get("types") != ["Column"]:
            continue
        if any(action[: len(slot)] == tuple(slot) for action in action_paths):
            continue
        slots.append(slot)
    if len(slots) != 1:
        return region, None
    return {**region, "path": slots[0]}, (
        f"content assignment moved from parent {list(path)} to pure content slot {slots[0]}; "
        "its capacity excludes the separate action reservation. Keep all facts and original "
        "fonts; regroup short same-object auxiliary facts if the complete content overflows."
    )


def _composition_region_shape(value: Any, schema: dict[str, Any]) -> bool:
    if not isinstance(value, dict) or set(value) != set(schema.get("required")):
        return False
    if not isinstance(value.get("id"), str) or not value.get("id").strip():
        return False
    path = value.get("path")
    if not isinstance(path, list):
        return False
    for index in path:
        if not isinstance(index, int) or isinstance(index, bool) or index < 0:
            return False
    for key in ("referenceWidth", "referenceHeight", "gap"):
        if not _finite_extent(value.get(key)):
            return False
    groups = value.get("groups")
    return isinstance(groups, list) and 1 <= len(groups) <= 24


def _composition_group(
    value: Any,
    schema: dict[str, Any],
    index_map: dict[int, int],
    facts: list[dict[str, Any]],
    size: Any,
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if set(value) - set(schema.get("properties")) or not set(schema.get("required")) <= set(value):
        return None
    component = value.get("component")
    allowed_components = _component_hints(size)
    if component not in allowed_components or not _finite_extent(value.get("referenceHeight")):
        return None
    indexes, placements = value.get("factIndexes"), value.get("placements")
    if not isinstance(indexes, list) or not isinstance(placements, list):
        return None
    value = dict(value)
    placement_notes: list[str] = []
    if not indexes:
        if component != "SingleLineTitle" or placements not in ([], ["title"]):
            return None
        placements = []
    elif len(indexes) == 1 and placements == ["value", "unit"]:
        if component != "EmphasizedData":
            return None
        placements = ["value"]
        placement_notes.append(
            "EmphasizedData.unit is not another copy of its numeric fact: resolve the real "
            "unit from the field contract, never bind the numeric value to unit."
        )
    if len(indexes) != len(placements) or len(indexes) > 24:
        return None
    value["placements"] = placements
    remapped: list[int] = []
    for index, placement in zip(indexes, placements, strict=True):
        if not isinstance(index, int) or isinstance(index, bool) or index not in index_map:
            return None
        if not isinstance(placement, str) or not placement.strip():
            return None
        remapped.append(index_map[index])
    actions = [index for index in remapped if "actionId" in facts[index]]
    if actions and (len(remapped) != 1 or component not in _ACTION_FACT_COMPONENTS):
        return None
    if not actions and component in _ACTION_FACT_COMPONENTS:
        return None
    for key in ("columns", "labelLines"):
        number = value.get(key)
        if key in value and (type(number) is not int or number not in (1, 2)):
            return None
    lines = value.get("lines")
    if lines is not None:
        if not isinstance(lines, list) or not lines:
            return None
        for line in lines:
            if type(line) is not int or line not in (1, 2):
                return None
    for key in ("variant", "density"):
        if key in value and not isinstance(value.get(key), str):
            return None
        allowed = schema.get("properties", {}).get(key, {}).get("enum")
        if key in value and allowed is not None and value.get(key) not in allowed:
            return None
    height = composition_group_minimum_height(size, value)
    planned_height = value.get("referenceHeight")
    if height is not None:
        exact_small_readout = size == "2x2" and component in {"EmphasizedData", "EmphasisText"}
        planned_height = height if exact_small_readout else max(height, planned_height)
    group = {**value, "factIndexes": remapped, "referenceHeight": planned_height}
    if size == "2x2" and component == "TableText":
        item_indexes = set()
        for placement in placements:
            match = re.fullmatch(r"items\[(\d+)\]\.(?:label|value)", placement)
            if match is not None:
                item_indexes.add(int(match.group(1)))
        if item_indexes and (
            len(item_indexes) not in (2, 3) or item_indexes != set(range(len(item_indexes)))
        ):
            group["implementationConflict"] = (
                "TableText only supports two or three contiguous items, not "
                f"{len(item_indexes)}. Keep every fact; regroup ordinary information in "
                "SecondaryBody at its legal single-row/multiline font, combining short same-object "
                "attributes into full-width labelled lines when they fit. Do not copy "
                "the invalid table or shrink text to create a smaller table."
            )
    if placement_notes:
        group["placementNotes"] = placement_notes
    return group


def parse_compact_plan_call(
    raw_output: str,
    task_spec: dict[str, Any],
    *,
    static_text_source: str | None = None,
    require_composition: bool = False,
    require_static_identity: bool = False,
    require_static_omission_refs: bool = False,
) -> CompactPlanValidationResult:
    """解析命名工具调用包，并按当前 TaskSpec 标准化 Plan。"""
    syntax_warnings: list[str] = []
    if isinstance(raw_output, str):
        envelope = normalize_plan_output(raw_output)
        syntax_warnings.extend(envelope.warnings)
        raw_output = envelope.text
    payload = _parse_json_object(raw_output, syntax_warnings)
    normalized_envelope = normalize_plan_root_arguments(payload)
    payload = normalized_envelope.payload
    syntax_warnings.extend(normalized_envelope.warnings)
    if set(payload) != {"name", "arguments"}:
        raise CompactPlanValidationError(["Plan output must contain only name and arguments."])
    if payload.get("name") != SUBMIT_CARD_PLAN:
        raise CompactPlanValidationError([f"Plan output must call {SUBMIT_CARD_PLAN}."])
    arguments = payload.get("arguments")
    if isinstance(arguments, str):
        arguments = _parse_json_object(arguments, syntax_warnings)
    if not isinstance(arguments, dict):
        raise CompactPlanValidationError(["submit_card_plan.arguments must be an object."])
    asset_ids = compact_plan_asset_ids(task_spec)
    allowed_arguments = {"info_required", "layoutHints"}
    from services.generation_content_policy import current_content_policy

    static_mode = current_content_policy().is_static
    if static_mode:
        allowed_arguments.add("contentGroups")
        allowed_arguments.add("selectionNotes")
        allowed_arguments.add("omittedContents")
        allowed_arguments.add("presentationStyle")
        allowed_arguments.add("paletteFamily")
    if asset_ids:
        allowed_arguments.add("assetAssignments")
    if require_composition:
        allowed_arguments.add("composition")
    unknown_arguments = set(arguments) - allowed_arguments
    if unknown_arguments:
        names = ", ".join(sorted(unknown_arguments))
        raise CompactPlanValidationError([f"Unsupported Plan arguments: {names}."])
    static_groups = []
    if static_mode:
        if require_static_identity:
            groups = arguments.get("contentGroups", [])
            if isinstance(groups, list):
                for group in groups:
                    if isinstance(group, dict) and "identity" not in group:
                        raise CompactPlanValidationError([
                            "新静态计划每组须显式提交identity：object写对象短名称，无名称或shared写null；"
                            "不能只把名称写在requirement或组ID中。"
                        ])
        for preference, choices in (
            ("presentationStyle", {"auto", "content", "rows", "records", "comparison"}),
            ("paletteFamily", {"auto", "blue", "purple", "warm"}),
        ):
            selected = arguments.get(preference, "auto")
            if not isinstance(selected, str) or selected not in choices:
                raise CompactPlanValidationError([f"静态 {preference} 必须为已登记枚举。"])
        if arguments.get("presentationStyle") == "comparison" and task_spec.get("size") != "2x4":
            raise CompactPlanValidationError(["comparison 只支持2x4，请选择当前尺寸合法结构。"])
        normalized_static = _normalize_static_plan(arguments, task_spec)
        facts = normalized_static.facts
        warnings = normalized_static.warnings
        static_groups = normalized_static.groups
    else:
        facts, warnings = _validate_facts(
            arguments.get("info_required"),
            task_spec,
            static_text_source=static_text_source,
        )
    warnings[:0] = syntax_warnings
    plan: dict[str, Any] = {"info_required": facts}
    if static_mode:
        plan["contentGroups"] = static_groups
        for preference in ("presentationStyle", "paletteFamily"):
            if preference in arguments:
                plan[preference] = arguments.get(preference)
        notes = arguments.get("selectionNotes", [])
        if not isinstance(notes, list) or len(notes) > 8:
            raise CompactPlanValidationError(["selectionNotes 必须为最多8项的取舍说明数组。"])
        for note in notes:
            if not isinstance(note, str) or not note.strip():
                raise CompactPlanValidationError(["取舍说明必须为非空字符串。"])
            if len(note) > 200:
                raise CompactPlanValidationError(["每项取舍说明最多200字符。"])
        plan["selectionNotes"] = notes + normalized_static.selection_notes
        omissions = _normalize_static_omissions(
            normalized_static.omission_entries,
            normalized_static.raw_facts, normalized_static.index_map,
            normalized_static.facts, allow_legacy=not require_static_omission_refs,
        )
        warnings.extend(omissions.warnings)
        plan["omittedContents"] = omissions.descriptions + list(normalized_static.omitted_contents)
        if omissions.candidates:
            plan["omissionCandidates"] = omissions.candidates
        if normalized_static.presentation_feedback:
            plan["staticPresentationFeedback"] = list(normalized_static.presentation_feedback)
        if normalized_static.presentation is not None:
            plan["staticPresentation"] = normalized_static.presentation
        from services.card_validation.compact_validation.semantic.layout.text_capacity import (
            static_plan_capacity_errors,
        )

        static_errors = static_plan_capacity_errors(plan, task_spec.get("size"))
        if static_errors:
            raise CompactPlanValidationError(static_errors)
    whole_card_click = None if require_composition else select_whole_card_click(task_spec, facts)
    if whole_card_click is not None:
        plan["wholeCardActionId"] = whole_card_click.action_id
        for fact in facts:
            if fact.get("actionId") == whole_card_click.action_id:
                fact.pop("componentHints", None)
    if asset_ids:
        if "assetAssignments" not in arguments:
            raise CompactPlanValidationError(
                ["assetAssignments is required when TaskSpec provides asset candidates."]
            )
        plan["assetAssignments"] = _normalize_asset_assignments(
            arguments.get("assetAssignments"),
            facts,
            task_spec,
            whole_card_action_id=(
                whole_card_click.action_id if whole_card_click is not None else None
            ),
        )
    layout_hints, layout_warnings = _normalize_layout_hints(
        arguments.get("layoutHints"),
        task_spec.get("size"),
    )
    warnings.extend(layout_warnings)
    if whole_card_click is not None:
        layout_hints = [hint for hint in layout_hints if hint in WHOLE_CARD_LAYOUTS]
        if not layout_hints:
            layout_hints = list(WHOLE_CARD_LAYOUTS)
    layout_hints, dual_action_warnings = _normalize_dual_action_plan(
        facts,
        layout_hints,
        task_spec.get("size"),
    )
    warnings.extend(dual_action_warnings)
    layout_hints, action_layout_warnings = _normalize_two_by_four_action_layouts(
        facts,
        layout_hints,
        task_spec.get("size"),
    )
    warnings.extend(action_layout_warnings)
    if layout_hints:
        plan["layoutHints"] = layout_hints
    composition = None
    composition_warnings: list[str] = []
    if require_composition:
        if "composition" not in arguments:
            raise CompactPlanValidationError(
                ["composition is required when runtime prompt context is enabled."]
            )
        composition, composition_warnings = _normalize_composition(
            arguments.get("composition"),
            arguments.get("info_required"),
            facts,
            task_spec.get("size"),
        )
        if composition is None:
            errors = composition_warnings or ["composition is invalid or incomplete."]
            raise CompactPlanValidationError(errors)
        overflow_errors = []
        for region in composition.get("regions", []):
            remaining = region.get("remainingHeight")
            if isinstance(remaining, (int, float)) and remaining < 0:
                overflow_errors.append(
                    f"composition region {region.get('id')} has negative remainingHeight "
                    f"{remaining:g}vp; rebuild the complete grouping without omitting facts."
                )
        if overflow_errors:
            raise CompactPlanValidationError(overflow_errors)
    anchor_errors = _anchor_plan_errors(facts, layout_hints, composition)
    if anchor_errors:
        raise CompactPlanValidationError(anchor_errors)
    secondary_body_errors = _secondary_body_composition_errors(composition)
    if secondary_body_errors:
        raise CompactPlanValidationError(secondary_body_errors)
    freshness_errors = _freshness_metadata_plan_errors(facts, composition, task_spec)
    if freshness_errors:
        raise CompactPlanValidationError(freshness_errors)
    warnings.extend(composition_warnings)
    duration_paths = set(compound_duration_bindings(plan, task_spec))
    for fact in facts:
        if fact.get("dataId") not in duration_paths:
            continue
        hints = fact.get("componentHints", [])
        if "EmphasizedData" not in hints:
            continue
        corrected: list[str] = []
        for hint in hints:
            candidate = "EmphasisText" if hint == "EmphasizedData" else hint
            if candidate not in corrected:
                corrected.append(candidate)
        fact["componentHints"] = corrected
        warnings.append(
            "Compound duration text uses EmphasisText, not a numeric hero; "
            "retain the complete binding and all units."
        )
    if composition is not None:
        incompatible = False
        for region in composition.get("regions", []):
            for group in region.get("groups", []):
                if group.get("component") != "EmphasizedData":
                    continue
                for index in group.get("factIndexes", []):
                    if not isinstance(index, int) or not 0 <= index < len(facts):
                        continue
                    if facts[index].get("dataId") in duration_paths:
                        incompatible = True
        if incompatible:
            note = (
                "composition uses a numeric hero for compound duration text; regroup "
                "with EmphasisText and retain every fact, binding and unit."
            )
            if require_composition:
                raise CompactPlanValidationError([note])
            composition = None
            warnings.append(note)
    if composition is not None:
        plan["composition"] = composition
    if composition_warnings:
        plan["compositionNotes"] = composition_warnings
    return CompactPlanValidationResult(plan=plan, warnings=tuple(warnings))


def _freshness_metadata_plan_errors(
    facts: list[dict[str, Any]],
    composition: dict[str, Any] | None,
    task_spec: dict[str, Any],
) -> list[str]:
    """限制刷新元数据只在明确请求或单短文本稀疏卡中展示。"""

    freshness_indexes = [
        index for index, fact in enumerate(facts) if _is_freshness_metadata_fact(fact)
    ]
    if not freshness_indexes:
        return []
    query = task_spec.get("userQuery")
    if isinstance(query, str) and _FRESHNESS_REQUEST.search(query):
        return []
    action_indexes = [
        index for index, fact in enumerate(facts) if isinstance(fact.get("actionId"), str)
    ]
    content_indexes: list[int] = []
    for index, fact in enumerate(facts):
        if index in freshness_indexes or index in action_indexes:
            continue
        if _is_title_fact(fact):
            continue
        content_indexes.append(index)
    sparse = len(freshness_indexes) == 1 and not action_indexes and len(content_indexes) == 1
    freshness_index = freshness_indexes[0]
    freshness_fact = facts[freshness_index]
    if not sparse:
        return [
            "Freshness metadata is not a normal display fact. Remove updatedAt/refreshTime "
            "unless the user explicitly requests freshness or the card has no action and "
            "only one short text core fact."
        ]
    core_index = content_indexes[0]
    core_fact = facts[core_index]
    core_hints = core_fact.get("componentHints")
    freshness_hints = freshness_fact.get("componentHints")
    short_text_core = isinstance(core_hints, list) and core_hints[:1] == ["EmphasisText"]
    grouped_hint = isinstance(freshness_hints, list) and freshness_hints[:1] == ["EmphasisText"]
    if not short_text_core or not grouped_hint:
        return [
            "Sparse-card freshness metadata must be grouped into the single short text core: "
            "use EmphasisText for both the core fact and updatedAt/refreshTime, with the "
            "freshness value assigned to secondaryText; do not create a standalone "
            "SecondaryBody region."
        ]
    errors: list[str] = []
    if freshness_fact.get("priority") != "should":
        errors.append(
            "Unrequested freshness metadata is optional filler and must use priority should."
        )
    if composition is not None and not _composition_groups_freshness_with_core(
        composition,
        core_index,
        freshness_index,
    ):
        errors.append(
            "Sparse-card freshness metadata must share one EmphasisText group with the core "
            "fact and use secondaryText; do not allocate a separate region or component."
        )
    return errors


def _is_freshness_metadata_fact(fact: dict[str, Any]) -> bool:
    path = fact.get("dataId")
    if not isinstance(path, str):
        return False
    leaf = path.rsplit("/", maxsplit=1)[-1]
    normalized = re.sub(r"[^a-z0-9]", "", leaf.lower())
    return normalized in _FRESHNESS_METADATA_NAMES


def _is_title_fact(fact: dict[str, Any]) -> bool:
    hints = fact.get("componentHints")
    return isinstance(hints, list) and hints[:1] in (
        ["SingleLineTitle"],
        ["DoubleLineTitle"],
    )


def _is_title_action_plan(facts: list[Any]) -> bool:
    """判断标题加单动作变体是否只含可见标题和一个动作。"""
    if len(facts) not in {1, 2}:
        return False
    action_ids: set[str] = set()
    title_count = 0
    for fact in facts:
        if not isinstance(fact, dict):
            return False
        action_id = fact.get("actionId")
        if isinstance(action_id, str) and action_id:
            if "dataId" in fact or "text" in fact:
                return False
            action_ids.add(action_id)
            continue
        if not _is_title_action_fact(fact):
            return False
        title_count += 1
    return len(action_ids) == 1 and title_count <= 1


def _is_title_action_fact(fact: dict[str, Any]) -> bool:
    """标题加单动作变体的标题必须可由 Plan 明确识别。"""
    if "actionId" in fact or "dataId" in fact:
        return False
    text = fact.get("text")
    if not isinstance(text, str) or not text.strip():
        return False
    if fact.get("displayRole") == "title":
        return True
    hints = fact.get("componentHints")
    return isinstance(hints, list) and hints[:1] == ["SingleLineTitle"]


def _composition_groups_freshness_with_core(
    composition: dict[str, Any],
    core_index: int,
    freshness_index: int,
) -> bool:
    for region in composition.get("regions", []):
        if not isinstance(region, dict):
            continue
        for group in region.get("groups", []):
            if not isinstance(group, dict) or group.get("component") != "EmphasisText":
                continue
            indexes = group.get("factIndexes")
            placements = group.get("placements")
            if not isinstance(indexes, list) or not isinstance(placements, list):
                continue
            paired = list(zip(indexes, placements, strict=False))
            has_core = (core_index, "mainText") in paired
            has_freshness = (freshness_index, "secondaryText") in paired
            if has_core and has_freshness:
                return True
    return False


def compact_plan_context(
    plan: dict[str, Any],
    *,
    implementation_conflicts: list[str] | None = None,
    execution_selected: bool = False,
) -> str:
    """构造第二阶段使用的硬事实与软候选说明。"""
    conflicts = (
        composition_implementation_conflicts(plan)
        if implementation_conflicts is None
        else implementation_conflicts
    )
    context_plan = dict(plan)
    whole_card_instruction = ""
    if isinstance(plan.get("wholeCardActionId"), str):
        whole_card_instruction = (
            "wholeCardActionId 是服务端已确认的整卡详情动作，仍是必须保留的 Action。"
            "仅使用 S-title-content 或 S-title-dual-content，在 root Layout.onClick 放入该候选"
            "恰好一个完整 handler，call/args、Expression 和 PathBinding 原样保留。"
            "根内部不再生成按钮或其它点击节点，不预留按钮高度，不补动作提示文字；"
            "不能删动作、改为子节点点击或因修复补回按钮。该动作没有按钮图标。"
        )
    facts = plan.get("info_required")
    fixed_dual_action = (
        plan.get("layoutHints") == ["S-content-dual-action"]
        and _has_two_distinct_actions(facts)
    )
    fixed_title_action = plan.get("layoutHints") == ["S-title-content-action"]
    if conflicts:
        context_plan.pop("composition", None)
        context_plan["compositionNotes"] = conflicts
    asset_instruction = ""
    pure_action_instruction = ""
    title_action_only = False
    if fixed_dual_action and isinstance(facts, list):
        if len(facts) == 2 and all("actionId" in fact for fact in facts):
            pure_action_instruction = (
                "本轮只有两个必要动作、没有展示事实，使用 S-content-dual-action 的 "
                "actions-only 变体，children 仅为两个 CardButton；"
                "不生成内容槽、标题、占位正文、空容器或伪造状态。"
            )
    if fixed_title_action and isinstance(facts, list):
        title_action_only = _is_title_action_plan(facts)
        if title_action_only:
            pure_action_instruction = (
                "本轮只有一个必要动作，至多保留一个标题事实，使用 S-title-content-action 的 "
                "title-action 变体，children 仅为 SingleLineTitle 和 PillButton；"
                "保留稳定标题和真实动作，不生成内容槽、正文、占位正文、空容器或伪造状态。"
            )
    if "assetAssignments" in context_plan:
        asset_instruction = (
            "assetAssignments 冻结素材消费顺序与结果：先按 actionId 将分配落实到对应"
            "动作组件，再将 title 中的非空素材落实到主 SingleLineTitle.icon；"
            "assetId 为 null 时省略业务图标，由转换器使用固定回退图标。"
            "不得复用、互换或跳过已分配素材，也不得用"
            "未分配素材覆盖明确的空分配。动作 assetId 为 null 时仍可使用 CardButton，"
            "其原始 DSL 必须省略 icon。"
            "EventCard条目详情不使用按钮或按钮图标，分配为null并由对应items[].onClick履约。"
        )
        if whole_card_instruction:
            asset_instruction = (
                "assetAssignments 中整卡动作的 assetId 为 null，不生成按钮或消费按钮素材；"
                "title 的已分配素材仍按原标题合同落实。"
            )
    small_conflict = False
    if conflicts:
        for layout_hint in plan.get("layoutHints", []):
            if isinstance(layout_hint, str) and layout_hint.startswith("S-"):
                small_conflict = True
                break
    preference_instruction = (
        "componentHints 第一项是首选：语义、类型、素材、事件和容量成立时应落实；"
        "具体条件不成立才改选合法备选或组件组合。"
    )
    intent_context = _component_intent_context(plan)
    if small_conflict:
        preference_instruction = (
            "当前小卡compositionNotes已证明原合组或容量有冲突，原候选首项不再是实例清单。"
            "先重算完整信息组与动作的合法承载，再选匹配组件；不要按旧候选逐事实实例化，"
            "普通辅助状态不新增强调焦点。候选与全部硬事实保留，不靠降字或删事实过关。"
        )
        intent_context = ""
    payload = json.dumps(context_plan, ensure_ascii=False, separators=(",", ":"))
    if execution_selected:
        conflict_instruction = ""
        if small_conflict:
            conflict_instruction = (
                "本轮小卡旧分区已有明确合组或容量冲突，不能继续保留失效的body包装或"
                "按候选首项逐事实新增实例。按当前完整布局变体重新核算全部事实和动作，"
                "普通辅助状态不叠加强调焦点；只交接诊断与文字指导，不提供恢复蓝图。"
            )
        return (
            "# 已接受的 Compact Info Plan\n\n"
            "info_required 冻结全部 must/should 事实与真实动作；未明确进入"
            "drop_optional_component 阶段时，两种优先级都必须可见。组件候选不是新增实例清单；"
            "compositionRecovery 提供完整参考时实现其中已选方案，不再按 componentHints 第一项"
            "重做选型，也不照抄已经诊断为冲突的旧 composition。"
            "没有恢复参考时，合法composition保持原分区和合组；没有完整composition时"
            "按对象信息关系和当前尺寸完整案例组织，不能把候选第一项当作逐事实实例清单。"
            f"{conflict_instruction}"
            "普通时间、数量说明和状态不因候选排序新增强调焦点；标题与主值职责保持不变。"
            "局部修复保持待修树的合法结构，只处理明确错误。"
            f"{asset_instruction}"
            f"{whole_card_instruction}"
            f"{pure_action_instruction}"
            "按参考蓝图的父子关系和事实索引落实真实绑定、完整文案与所属动作；"
            "索引从0开始，不能把索引或压力样值写入最终 DSL。标题绑定保留指定标题职责。"
            "核对必要的对象标签、完整单位与全部动作，原字号不变，不能裁切或删信息。"
            "参考预算不代替标签与单位的核算；明确发现参考方案仍不成立时才整体重组。\n\n"
            f"```json\n{payload}\n```"
        )
    layout_instruction = (
        "本轮两个必要动作使 S-content-dual-action 成为固定布局，不得改选带标题或单动作布局。"
        "内容候选仍为软推荐，须按正文扣除两个按钮和间距后的容量重新核对。"
        "不按事实数量强制表格；TableText 先满足等权语义，再按实际行数核算 Recipe 高度。"
        "首选组件不适配时重组选型，保留全部事实、两个动作及其完整参数，不缩字或补造正文。"
        if fixed_dual_action
        else (
            "本轮唯一必要动作且至多一个标题事实时，S-title-content-action 必须使用 "
            "title-action 变体，不得生成正文槽。"
            if title_action_only
            else "componentHints 与 layoutHints 不冻结组件实例或最终骨架，但不能无理由忽略。"
        )
    )
    return (
        "# 已接受的 Compact Info Plan\n\n"
        "以下 Plan 冻结 must/should 信息、静态正文和操作；正常生成与修复都必须完整展示两种优先级，"
        "只有微服务明确进入 drop_optional_component 最终兜底时，"
        "才允许省略程序指定的非 Action 事实。"
        "除标题组件职责外，"
        f"{layout_instruction}"
        f"{pure_action_instruction}"
        "当 composition 已选中且合同、容量均成立时，它是本轮的执行选择；尤其"
        "S-title-anchor 不能仅因存在 PillButton 就被降级替换为底部文字动作布局。"
        f"{preference_instruction}先按对象和信息关系合组，再映射可见 Prop。"
        "不能因为完整案例使用了其它组件就将匹配的信息组拆成逐字段的单文字组件。"
        "每项事实必须在最终 Compact DSL 中有完整可读的落点；"
        "同组图形与对应读数允许共用绑定，禁止跨组无意义重复。"
        "不得为了布局或修复删除 Plan 事实；动作必须使用 "
        "TaskSpec 中对应 actionId 的完整事件候选。最终组件与布局仍按完整合同和容量选择。\n"
        f"{asset_instruction}\n"
        f"{whole_card_instruction}\n"
        "若有 composition，按它的 layout/variant、region.path 与顺序 groups 实现，"
        "factIndexes 引用下面去重后的 info_required，placements 指明每条事实的可见 Prop。"
        "空映射 SingleLineTitle 只是装饰标题的容量预留，不是遗漏事实；"
        "重复索引表示同一实例共用同一事实，不能据此增加实例或重复正文。"
        "placementNotes 中的单位必须按原字段合同解决，不能把数值当单位再次绑定。"
        "不要重新逐字段实例化组件，或把单列合组改回窄双列；动作保持完整目标名称。"
        "每区 sum(referenceHeight)+gap 必须小于可用高度，横排每列还须容纳完整文字。"
        "这些数字仅用于容量核算，区域输出仍为 matchParent/layoutWeight；"
        "正文必须承接扣除标题、动作、padding和间距后的剩余空间，不能向整父区撑高。"
        "compositionNotes 是需要纠正的组合诊断，不允许通过裁切、缩字或删事实处理。"
        "确有合同/容量冲突时整体重选可承载的分区合组并重新核算，不能盲从错误计划。\n"
        "一个语义分区可使用一个 SingleLineTitle；2x4 左右独立分区"
        "可分别使用 SingleLineTitle。componentHints 中的 SingleLineTitle 仍是软候选；"
        "最终布局或语义不适配时，可由其它合法语义组件承载该事实，但事实仍必须完整可见。"
        "需要标题加次信息时使用 DoubleLineTitle。\n"
        "逐项核对 dataId → 可见组件 Prop：标题、地区、更新时间也必须真实绑定；"
        "不能用用户原话或 sampleValue 写死，即使首帧文字相同。只写数据行、只在事件参数"
        "引用都不算可见。actionId → 所属对象的点击组件或用户明确要求的独立动作槽，"
        "两者都须有准确可见的动作名称；独立操作不要求同名数据根。入会不能挂在"
        "耳机等无关信息块，不能因槽位已满省略动作。数值图形不支持的格式化文本保留文字，"
        "不得从 sampleValue 提取数字写成静态进度。\n"
        "有路径引用不等于读数能看全。逐项检查标签、值、单位在扣除 padding 和图标后"
        "的实际文字区：使用当前路径所属对象的短名称加完整动态读数，不复制示例的对象标签。"
        "耳机数据不能标为手机，左右读数必须区分；长说明不能挤掉数值。"
        "平均、最高、最低各有独立统计含义，不能拼成无标签区间；动作短名保留必要目标限定。"
        "第二行只放另一项必要事实，不重复主行标签；取消可选图标仍放不下时改用基础组合。"
        "先按信息关系形成完整组件组合，再比较能容纳组合与全部动作的合法布局和内容槽；"
        "不先锁定辅助槽再压入事实，不把宽卡默认堆成单列。横排先核对完整文本所需宽度，"
        "纵排累加真实行数、固定行高和间距，使用当前组件合同而非照抄示例容量。"
        "动作先留足高度，环、状态、标题的总高度不能超出剩余正文；layoutWeight 不会让"
        "文字或环缩小。时间段、日期时间和带长单位的指标使用普通字号或分行，不套用大数字。\n\n"
        f"```json\n{payload}\n```"
        f"{intent_context}"
    )


def _component_intent_context(plan: dict[str, Any]) -> str:
    """把已接受的首选映射成核对表，不新增硬使用率门禁或模型调用。"""
    allowed: set[str] = set()
    for components in MODEL_COMPONENT_TYPES_BY_SIZE.values():
        allowed.update(components)
    groups: dict[str, list[int]] = {}
    for index, fact in enumerate(plan.get("info_required", []), start=1):
        if not isinstance(fact, dict):
            continue
        hints = fact.get("componentHints")
        if not isinstance(hints, list) or not hints:
            continue
        preferred = hints[0]
        if isinstance(preferred, str) and preferred in allowed:
            groups.setdefault(preferred, []).append(index)
    if not groups:
        return ""
    payload = json.dumps(groups, ensure_ascii=False, separators=(",", ":"))
    return (
        "\n\n# 本轮首选组件落点核对\n\n"
        "编号是 info_required 中从 1 开始的事实序号，不是组件数量。"
        "此表按候选组件类型汇总，不是信息分组结果；"
        "先按对象与信息关系确定实例，再逐事实核对覆盖。"
        "同对象、同事件或同级信息组才合并实例，不混合不同对象。"
        "生成和修复前核对首选是否落实，不适配时按具体语义、绑定、容量原因改选。"
        "此核对不输出解释、不添加协议字段、不删事实凑组件。"
        "保留正式骨架的父容器与层级，组件放在内容槽内；"
        "逐 Prop 核对自身绑定合同，不借用其它组件属性。\n\n"
        f"```json\n{payload}\n```"
    )


@dataclass(frozen=True)
class _CompactVisibleState:
    paths: frozenset[str]
    path_occurrences: tuple[_CompactVisiblePathOccurrence, ...]
    literals: tuple[str, ...]
    item_literals: tuple[str, ...]
    handlers: tuple[dict[str, Any], ...]
    value_unit_literals: tuple[str, ...] = ()


@dataclass(frozen=True)
class _CompactVisiblePathOccurrence:
    data_id: str
    component_id: str
    component_type: str
    property_path: str

    def to_payload(self) -> dict[str, str]:
        return {
            "componentId": self.component_id,
            "componentType": self.component_type,
            "property": self.property_path,
        }


@dataclass(frozen=True)
class CompactPlanCoverageResult:
    """区分阻断生成的 Plan 覆盖错误与按阶段降级的覆盖告警。"""

    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    duplicate_facts: tuple[dict[str, Any], ...] = ()
    duplicate_actions: tuple[dict[str, Any], ...] = ()


def _compact_visible_state(components: list[ComponentRow]) -> _CompactVisibleState:
    visible_paths: set[str] = set()
    path_occurrences: list[_CompactVisiblePathOccurrence] = []
    visible_literals: list[str] = []
    item_literals: list[str] = []
    value_unit_literals: list[str] = []
    handlers: list[dict[str, Any]] = []
    reachable_ids = _reachable_component_ids(tuple(components))
    for component in components:
        from services.generation_content_policy import current_content_policy

        visible_names = _VISIBLE_PROP_NAMES
        if current_content_policy().is_static:
            visible_names = visible_names | {"body", "attributes", "description", "details"}
        visible_props = {
            key: value for key, value in component.props.items() if key in visible_names
        }
        if component.component_type == "EventCard":
            items = visible_props.get("items")
            if isinstance(items, list):
                display_items = []
                for item in items:
                    if isinstance(item, dict):
                        display_items.append({k: v for k, v in item.items() if k != "onClick"})
                visible_props["items"] = display_items
            handlers.extend(event_card_item_handlers(component.props))
        has_separate_progress_readout = (
            component.component_type in _PROGRESS_VALUE_DRIVER_COMPONENTS
            and "displayValue" in visible_props
        )
        if has_separate_progress_readout:
            visible_props.pop("value", None)
        _collect_paths_and_literals(visible_props, visible_paths, visible_literals)
        _collect_structured_item_literals(
            component,
            item_literals,
            value_unit_literals=(
                value_unit_literals if component.component_id in reachable_ids else None
            ),
        )
        for property_name, value in visible_props.items():
            _collect_visible_path_occurrences(
                value,
                component_id=component.component_id,
                component_type=component.component_type,
                property_path=property_name,
                occurrences=path_occurrences,
            )
        on_click = component.props.get("onClick")
        if isinstance(on_click, list):
            handlers.extend(item for item in on_click if isinstance(item, dict))
    return _CompactVisibleState(
        paths=frozenset(visible_paths),
        path_occurrences=tuple(path_occurrences),
        literals=tuple(_normalize_text(value) for value in visible_literals),
        item_literals=tuple(_normalize_text(value) for value in item_literals),
        handlers=tuple(handlers),
        value_unit_literals=tuple(_normalize_text(value) for value in value_unit_literals),
    )


def compact_plan_overflow_action_ids(
    components: list[ComponentRow],
    plan: dict[str, Any] | None,
    task_spec: dict[str, Any],
) -> frozenset[str]:
    """已有两个合法按钮时，将第三个及后续未落位 Action 视为容量降级。"""
    if not isinstance(plan, dict):
        return frozenset()
    facts = plan.get("info_required")
    if not isinstance(facts, list):
        return frozenset()
    selected_action_ids: list[str] = []
    item_action_ids: set[str] = set()
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        action_id = fact.get("actionId")
        if isinstance(action_id, str) and action_id not in selected_action_ids:
            selected_action_ids.append(action_id)
            if prefers_event_card_item(fact):
                item_action_ids.add(action_id)
    if len(selected_action_ids) <= 2:
        return frozenset()

    reachable_ids = _reachable_component_ids(tuple(components))
    buttons = [
        component
        for component in components
        if component.component_id in reachable_ids
        and component.component_type in _ACTION_FACT_COMPONENTS
    ]
    if len(buttons) < 2:
        return frozenset()

    event_handlers = _event_handlers_by_id(task_spec)
    visible_action_ids: set[str] = set()
    for button in buttons:
        on_click = button.props.get("onClick")
        if not isinstance(on_click, list) or len(on_click) != 1:
            return frozenset()
        actual_handler = on_click[0]
        if not isinstance(actual_handler, dict):
            return frozenset()
        matches = []
        for action_id in selected_action_ids:
            expected_handler = event_handlers.get(action_id)
            if expected_handler is None:
                continue
            if event_handlers_match(actual_handler, expected_handler):
                matches.append(action_id)
        if len(matches) != 1:
            return frozenset()
        visible_action_ids.add(matches[0])
    if len(visible_action_ids) != len(buttons) or len(visible_action_ids) < 2:
        return frozenset()
    return frozenset(set(selected_action_ids) - visible_action_ids - item_action_ids)


def _collect_structured_item_literals(
    component: ComponentRow,
    literals: list[str],
    *,
    value_unit_literals: list[str] | None = None,
) -> None:
    """补充同一结构化条目内共同呈现的静态文本。"""
    if component.component_type == "EmphasizedData":
        if value_unit_literals is not None:
            _collect_emphasized_data_value_unit_literals(component, value_unit_literals)
        return
    items = component.props.get("items")
    if not isinstance(items, list):
        return
    if component.component_type == "EventCard":
        _collect_event_card_item_literals(items, literals)
        return
    if component.component_type not in {"SecondaryBody", "TextBlock"}:
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        label = item.get("label")
        value = item.get("value")
        if not isinstance(label, str) or not isinstance(value, str):
            continue
        if _BINDING_PATH.search(label) or _BINDING_PATH.search(value):
            continue
        literals.append(f"{label}{value}")


def _collect_emphasized_data_value_unit_literals(
    component: ComponentRow,
    literals: list[str],
) -> None:
    """只合并同一主读数的合法静态值与单位，供完整文字精确比较。"""
    value = component.props.get("value")
    unit = component.props.get("unit")
    if not isinstance(unit, str) or not unit.strip():
        return
    if "${" in unit or "{{" in unit:
        return
    valid_number = isinstance(value, (int, float)) and not isinstance(value, bool)
    if isinstance(value, float) and not math.isfinite(value):
        return
    if not valid_number:
        if not isinstance(value, str) or not value.strip():
            return
        if "${" in value or "{{" in value:
            return
    literals.append(f"{value}{unit}")


def _collect_event_card_item_literals(
    items: list[Any],
    literals: list[str],
) -> None:
    """保留同一事件内标题与时间共同表达的静态事实，不跨事件拼接。"""
    for item in items:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        time = item.get("time")
        if not isinstance(title, str) or not isinstance(time, str):
            continue
        if _BINDING_PATH.search(title) or _BINDING_PATH.search(time):
            continue
        literals.append(f"{time}{title}")
        literals.append(f"{title}{time}")


def _compact_fact_coverage_result(
    fact: dict[str, Any],
    state: _CompactVisibleState,
    event_handlers: dict[str, dict[str, Any]],
) -> CompactPlanCoverageResult:
    requirement = fact.get("requirement")
    label = requirement if isinstance(requirement, str) else "unknown requirement"
    data_id = fact.get("dataId")
    if isinstance(data_id, str):
        occurrences = tuple(item for item in state.path_occurrences if item.data_id == data_id)
        if not occurrences:
            return CompactPlanCoverageResult(
                errors=(f"Plan fact is missing from visible DSL: {label} ({data_id}).",),
                warnings=(),
            )
        if len(occurrences) > 1:
            locations = ", ".join(
                f"{item.component_id} ({item.component_type}).{item.property_path}"
                for item in occurrences
            )
            duplicate_fact = {
                "requirement": label,
                "dataId": data_id,
                "expectedVisibleCount": 1,
                "actualVisibleCount": len(occurrences),
                "occurrences": [item.to_payload() for item in occurrences],
            }
            return CompactPlanCoverageResult(
                errors=(
                    "Plan fact is displayed more than once in visible DSL: "
                    f"{label} ({data_id}); expected 1, got {len(occurrences)}; "
                    f"occurrences: {locations}.",
                ),
                warnings=(),
                duplicate_facts=(duplicate_fact,),
            )
    action_id = fact.get("actionId")
    if isinstance(action_id, str):
        expected = event_handlers.get(action_id)
        if expected is None or not any(
            event_handlers_match(handler, expected) for handler in state.handlers
        ):
            mismatch = _event_handler_mismatch(expected, state.handlers)
            return CompactPlanCoverageResult(
                errors=(
                    f"Plan action is missing from visible DSL: {label} ({action_id}).{mismatch}",
                ),
                warnings=(),
            )
        return CompactPlanCoverageResult(errors=(), warnings=())
    text = fact.get("text")
    if isinstance(text, str):
        expected_text = _normalize_text(text)
        literal_candidates = (*state.literals, *state.item_literals)
        literal_match = any(expected_text in actual for actual in literal_candidates)
        value_unit_match = expected_text in state.value_unit_literals
        if not expected_text or not (literal_match or value_unit_match):
            return CompactPlanCoverageResult(
                errors=(f"Plan static text is not fully visible in DSL: {label}.",),
                warnings=(),
            )
    return CompactPlanCoverageResult(errors=(), warnings=())


def evaluate_compact_plan_coverage(
    compact_dsl: str,
    plan: dict[str, Any] | None,
    task_spec: dict[str, Any],
    *,
    allowed_omitted_fact_indexes: tuple[int, ...] = (),
    information_errors_as_warnings: bool = False,
    check_duplicate_actions: bool = True,
) -> CompactPlanCoverageResult:
    """检查 Plan 覆盖；修复后可仅放宽非 Action 展示事实。"""
    from services.generation_content_policy import current_content_policy

    static_content = current_content_policy().is_static
    if not plan:
        if static_content:
            return CompactPlanCoverageResult(
                errors=("COMPACT_STATIC_CONTEXT_MISSING: 缺少已接受静态计划。",),
                warnings=(),
            )
        return CompactPlanCoverageResult(errors=(), warnings=())
    rows = parse_compact_dsl_rows(compact_dsl)
    components = [row for row in rows if isinstance(row, ComponentRow)]
    state = _compact_visible_state(components)
    event_handlers = _event_handlers_by_id(task_spec)
    overflow_action_ids = compact_plan_overflow_action_ids(components, plan, task_spec)
    allowed = set(allowed_omitted_fact_indexes)
    errors: list[str] = []
    if static_content:
        from services.card_validation.compact_validation.semantic.static_content import (
            static_group_errors,
        )

        errors.extend(static_group_errors(compact_dsl, plan, allowed_omitted_fact_indexes))
    warnings: list[str] = []
    duplicate_facts: list[dict[str, Any]] = []
    facts = plan.get("info_required")
    if not isinstance(facts, list):
        return CompactPlanCoverageResult(
            errors=("Accepted Compact Plan has no info_required facts.",),
            warnings=(),
        )
    duplicate_actions = ()
    if check_duplicate_actions:
        from services.card_validation.compact_validation.semantic.action_display import (
            find_duplicate_actions,
        )

        duplicate_actions = find_duplicate_actions(compact_dsl, plan, event_handlers)
        for action in duplicate_actions:
            positions = ", ".join(
                item.get("componentId", "") for item in action.get("occurrences", [])
            )
            errors.append(
                "Plan action is displayed more than once in visible DSL: "
                f"{action.get('actionId')}; expected 1, got {action.get('actualVisibleCount')}; "
                f"occurrences: {positions}."
            )
    for index, fact in enumerate(facts):
        if not isinstance(fact, dict):
            continue
        if static_content and "text" in fact:
            continue
        result = _compact_fact_coverage_result(fact, state, event_handlers)
        if index in allowed and "actionId" not in fact:
            continue
        if result.duplicate_facts:
            errors.extend(result.errors)
            duplicate_facts.extend(result.duplicate_facts)
        elif fact.get("actionId") in overflow_action_ids:
            requirement = fact.get("requirement")
            label = requirement if isinstance(requirement, str) else "unknown requirement"
            warnings.append(
                "Plan action was omitted after at least two distinct valid action buttons "
                f"were retained: {label} ({fact.get('actionId')})."
            )
        elif information_errors_as_warnings and "actionId" not in fact:
            warnings.extend(result.errors)
        else:
            errors.extend(result.errors)
        warnings.extend(result.warnings)
    required_layout = _required_anchor_layout(plan, task_spec)
    if required_layout is not None:
        try:
            match_compact_layout(
                components,
                size="2x2",
                layout_scope=required_layout,
            )
        except CompactLayoutRuntimeError:
            errors.append(
                "Accepted Compact Plan selected S-title-anchor as its executable "
                "composition; keep the CircleButton anchor layout instead of replacing it "
                "with a text-action layout that compresses the required content."
            )
    required_route = compact_plan_required_route(plan, task_spec)
    if required_route is not None:
        locked_layout = required_route.get("layout")
        if not isinstance(locked_layout, str):
            locked_layout = ""
        try:
            match_compact_layout(
                components,
                size="2x2",
                layout_scope=locked_layout,
            )
        except CompactLayoutRuntimeError:
            errors.append(
                "已接受 Plan 选择了 2x2 单焦点 S-center + DataDisplay；修复时必须保留"
                "该布局与组件，不得降级为 SingleLineTitle + EmphasisText 或 EmphasizedData。"
            )
    return CompactPlanCoverageResult(
        errors=tuple(errors),
        warnings=tuple(warnings),
        duplicate_facts=tuple(duplicate_facts),
        duplicate_actions=duplicate_actions,
    )


def compact_plan_coverage_errors(
    compact_dsl: str,
    plan: dict[str, Any] | None,
    task_spec: dict[str, Any],
    *,
    allowed_omitted_fact_indexes: tuple[int, ...] = (),
) -> tuple[str, ...]:
    """返回会阻断 Compact DSL 发布的 Plan 覆盖错误。"""
    return evaluate_compact_plan_coverage(
        compact_dsl,
        plan,
        task_spec,
        allowed_omitted_fact_indexes=allowed_omitted_fact_indexes,
    ).errors


def compact_plan_coverage_warnings(
    compact_dsl: str,
    plan: dict[str, Any] | None,
    task_spec: dict[str, Any],
    *,
    allowed_omitted_fact_indexes: tuple[int, ...] = (),
) -> tuple[str, ...]:
    """返回不阻断发布的普通静态文案覆盖告警。"""
    return evaluate_compact_plan_coverage(
        compact_dsl,
        plan,
        task_spec,
        allowed_omitted_fact_indexes=allowed_omitted_fact_indexes,
    ).warnings


def _recovery_fact(fact: dict[str, Any]) -> CompactDslRecoveryFact | None:
    for target in _TARGET_KEYS:
        value = fact.get(target)
        if not isinstance(value, str) or not value.strip():
            continue
        requirement = fact.get("requirement")
        priority = fact.get("priority")
        if not isinstance(requirement, str) or priority not in _FACT_PRIORITIES:
            return None
        return CompactDslRecoveryFact(
            target=target,
            value=value.strip(),
            requirement=requirement.strip(),
            priority=priority,
        )
    return None


def _static_recovery_omitted_indexes(
    compact_dsl: str,
    plan: dict[str, Any],
    allowed_indexes: tuple[int, ...],
) -> set[int]:
    from services.card_validation.compact_validation.semantic.static_content import (
        static_fact_coverage,
    )

    facts = plan.get("info_required", [])
    omitted = set()
    for coverage in static_fact_coverage(compact_dsl, plan, allowed_indexes):
        fact = facts[coverage.fact_index]
        if coverage.visible or coverage.text_present or "actionId" in fact:
            continue
        if fact.get("protectedTexts") or fact.get("preserveVerbatim"):
            continue
        optional = fact.get("priority") == "should"
        if optional or coverage.fact_index in allowed_indexes:
            omitted.add(coverage.fact_index)
    return omitted


def compact_plan_recovery_facts(
    compact_dsl: str,
    plan: dict[str, Any] | None,
    task_spec: dict[str, Any],
    *,
    allowed_omitted_fact_indexes: tuple[int, ...] = (),
) -> tuple[tuple[CompactDslRecoveryFact, ...], tuple[CompactDslRecoveryFact, ...]]:
    """划分恢复事实；静态链路不能把失败源的未授权遗漏固化为取舍。"""
    if not plan:
        return (), ()
    facts = plan.get("info_required")
    if not isinstance(facts, list):
        return (), ()
    from services.generation_content_policy import current_content_policy

    is_static = current_content_policy().is_static
    omitted_indexes: set[int] = set()
    omitted_targets = set()
    if is_static:
        omitted_indexes = _static_recovery_omitted_indexes(
            compact_dsl, plan, allowed_omitted_fact_indexes,
        )
    else:
        non_action_indexes = []
        for index, fact in enumerate(facts):
            if isinstance(fact, dict) and "actionId" not in fact:
                non_action_indexes.append(index)
        omitted = compact_plan_omitted_facts(
            compact_dsl, plan, task_spec, tuple(non_action_indexes),
        )
        for fact in omitted:
            recovery_fact = _recovery_fact(fact)
            if recovery_fact is not None:
                omitted_targets.add((recovery_fact.target, recovery_fact.value))
    retained_facts: list[CompactDslRecoveryFact] = []
    omitted_facts: list[CompactDslRecoveryFact] = []
    for index, fact in enumerate(facts):
        if not isinstance(fact, dict):
            continue
        recovery_fact = _recovery_fact(fact)
        if recovery_fact is None:
            continue
        target = (recovery_fact.target, recovery_fact.value)
        should_omit = index in omitted_indexes if is_static else target in omitted_targets
        if recovery_fact.target != "actionId" and should_omit:
            omitted_facts.append(recovery_fact)
        else:
            retained_facts.append(recovery_fact)
    return tuple(retained_facts), tuple(omitted_facts)


def build_compact_recovery_plan(
    plan: dict[str, Any] | None,
    required_facts: tuple[CompactDslRecoveryFact, ...],
) -> dict[str, Any] | None:
    """从首轮已接受 Plan 构造确定性的接口恢复 Plan。"""
    if not plan or not required_facts:
        return None
    facts = plan.get("info_required")
    if not isinstance(facts, list):
        return None
    expected = {(fact.target, fact.value) for fact in required_facts}
    retained: list[dict[str, Any]] = []
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        recovery_fact = _recovery_fact(fact)
        if recovery_fact is None:
            continue
        if (recovery_fact.target, recovery_fact.value) in expected:
            retained.append(copy.deepcopy(fact))
    recovery_plan = copy.deepcopy(plan)
    recovery_plan["info_required"] = retained
    recovery_plan.pop("composition", None)
    recovery_plan.pop("compositionNotes", None)
    if compact_recovery_plan_errors(recovery_plan, required_facts):
        return None
    return recovery_plan


def compact_recovery_plan_errors(
    plan: dict[str, Any],
    required_facts: tuple[CompactDslRecoveryFact, ...],
) -> tuple[str, ...]:
    """确保容量恢复 Plan 只规划第一轮最终保留的事实。"""
    if not required_facts:
        return ()
    expected = {(fact.target, fact.value): fact for fact in required_facts}
    actual: dict[tuple[str, str], dict[str, Any]] = {}
    for fact in plan.get("info_required", []):
        if not isinstance(fact, dict):
            continue
        recovery_fact = _recovery_fact(fact)
        if recovery_fact is not None:
            actual[(recovery_fact.target, recovery_fact.value)] = fact
    errors: list[str] = []
    for target, expected_fact in expected.items():
        actual_fact = actual.get(target)
        if actual_fact is None:
            errors.append(
                "容量恢复 Plan 缺少第一轮最终保留的信息："
                f"{expected_fact.requirement} ({expected_fact.value})。"
            )
            continue
        if actual_fact.get("priority") != expected_fact.priority:
            errors.append(
                "容量恢复 Plan 不得修改保留信息的优先级："
                f"{expected_fact.requirement} 必须保持 {expected_fact.priority}。"
            )
    for target, actual_fact in actual.items():
        if target in expected:
            continue
        errors.append(
            "容量恢复 Plan 不得重新加入第一轮最终已缺失的信息："
            f"{actual_fact.get('requirement') or target[1]} ({target[1]})。"
        )
    return tuple(errors)


def compact_plan_omitted_facts(
    compact_dsl: str,
    plan: dict[str, Any] | None,
    task_spec: dict[str, Any],
    allowed_omitted_fact_indexes: tuple[int, ...],
) -> tuple[dict[str, Any], ...]:
    """返回最终兜底后确实不再可见的非 Action 事实。"""
    if not plan:
        return ()
    facts = plan.get("info_required")
    if not isinstance(facts, list):
        return ()
    from services.generation_content_policy import current_content_policy

    if current_content_policy().is_static:
        from services.card_validation.compact_validation.semantic.static_content import (
            static_fact_coverage,
        )

        omitted_static = []
        for note in plan.get("omittedContents", []):
            omitted_static.append({"requirement": note, "omissionReason": "plan_selection"})
        for coverage in static_fact_coverage(compact_dsl, plan, allowed_omitted_fact_indexes):
            fact = facts[coverage.fact_index]
            optional = fact.get("priority") == "should"
            authorized = coverage.fact_index in allowed_omitted_fact_indexes or optional
            if authorized and not coverage.visible:
                omission_reason = "optional_omission" if optional else "bounded_drop"
                omitted_static.append({**fact, "omissionReason": omission_reason})
        return tuple(omitted_static)
    if not allowed_omitted_fact_indexes:
        return ()
    rows = parse_compact_dsl_rows(compact_dsl)
    components = [row for row in rows if isinstance(row, ComponentRow)]
    state = _compact_visible_state(components)
    event_handlers = _event_handlers_by_id(task_spec)
    omitted: list[dict[str, Any]] = []
    for index in allowed_omitted_fact_indexes:
        if not 0 <= index < len(facts):
            continue
        fact = facts[index]
        if not isinstance(fact, dict) or "actionId" in fact:
            continue
        result = _compact_fact_coverage_result(fact, state, event_handlers)
        if result.errors or result.warnings:
            omitted.append(fact)
    return tuple(omitted)


def _reachable_component_ids(rows: tuple[Any, ...]) -> set[str]:
    components = {
        row.component_id: row for row in rows if isinstance(row, ComponentRow)
    }
    pending = ["root"]
    reachable: set[str] = set()
    while pending:
        component_id = pending.pop()
        if component_id in reachable:
            continue
        component = components.get(component_id)
        if component is None:
            continue
        reachable.add(component_id)
        pending.extend(component.children)
    return reachable


def _reachable_core_component_ids(rows: tuple[Any, ...]) -> set[str]:
    components = {
        row.component_id: row for row in rows if isinstance(row, ComponentRow)
    }
    return {
        component_id
        for component_id in _reachable_component_ids(rows)
        if components[component_id].component_type in CORE_INFORMATION_COMPONENT_TYPES
    }


def _defined_core_component_ids(rows: tuple[Any, ...]) -> set[str]:
    return {
        row.component_id
        for row in rows
        if isinstance(row, ComponentRow)
        and row.component_type in CORE_INFORMATION_COMPONENT_TYPES
    }


def _drop_fact_matches(
    row: ComponentRow,
    facts: list[Any],
    event_handlers: dict[str, dict[str, Any]],
) -> tuple[list[int], list[str], bool]:
    state = _compact_visible_state([row])
    matched: list[int] = []
    priorities: list[str] = []
    for index, fact in enumerate(facts):
        if not isinstance(fact, dict):
            continue
        result = _compact_fact_coverage_result(fact, state, event_handlers)
        if result.errors or result.warnings:
            continue
        if "actionId" in fact:
            return [], [], True
        matched.append(index)
        priorities.append(str(fact.get("priority") or "must"))
    return matched, priorities, False


def _item_partial_drop_candidate(
    row: ComponentRow,
    facts: list[Any],
    event_handlers: dict[str, dict[str, Any]],
    allowed_fact_indexes: set[int] | None,
    max_fact_count: int | None,
    preserved_fact_indexes: set[int],
) -> CompactOptionalDropCandidate | None:
    """为 SecondaryBody 容量证据或至少三行 TableText 生成最小条目删减候选。"""
    secondary_body_candidate = (
        row.component_type == "SecondaryBody" and allowed_fact_indexes is not None
    )
    table_text_candidate = row.component_type == "TableText"
    if not secondary_body_candidate and not table_text_candidate:
        return None
    items = row.props.get("items")
    if not isinstance(items, list):
        return None
    if table_text_candidate and len(items) < 3:
        return None
    candidates: list[CompactOptionalDropCandidate] = []
    for item_index, item in enumerate(items):
        item_row = ComponentRow(
            row.component_id,
            row.component_type,
            {**row.props, "items": [item]},
            row.children,
        )
        item_matches, item_priorities, has_action_fact = _drop_fact_matches(
            item_row,
            facts,
            event_handlers,
        )
        if has_action_fact or not item_matches:
            continue
        omission_pairs = [
            (index, priority)
            for index, priority in zip(item_matches, item_priorities, strict=True)
            if index not in preserved_fact_indexes
        ]
        if not omission_pairs:
            continue
        omission_indexes = [index for index, _priority in omission_pairs]
        outside_allowed_scope = allowed_fact_indexes is not None and any(
            index not in allowed_fact_indexes for index in omission_indexes
        )
        if outside_allowed_scope:
            continue
        if max_fact_count is not None and len(omission_indexes) > max_fact_count:
            continue
        requirements = tuple(
            str(facts[index].get("requirement") or "") for index in omission_indexes
        )
        signature = json.dumps(
            item,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        candidates.append(
            CompactOptionalDropCandidate(
                component_id=row.component_id,
                component_type=row.component_type,
                fact_indexes=tuple(omission_indexes),
                requirements=requirements,
                contains_must_facts=any(
                    priority != "should" for _index, priority in omission_pairs
                ),
                partial=True,
                item_indexes=(item_index,),
                item_signatures=(signature,),
            )
        )
    should_candidates = [item for item in candidates if not item.contains_must_facts]
    selected = should_candidates or candidates
    if not selected:
        return None
    return max(selected, key=lambda item: max(item.fact_indexes, default=-1))


def compact_plan_optional_drop_candidate(
    compact_dsl: str,
    plan: dict[str, Any] | None,
    task_spec: dict[str, Any],
    *,
    allow_must_fallback: bool = True,
    max_fact_count: int | None = None,
    allowed_fact_indexes: set[int] | None = None,
    allow_invalid_table_text: bool = False,
    approved_omitted_fact_indexes: tuple[int, ...] = (),
) -> CompactOptionalDropCandidate | None:
    """优先选 should-only 组件，并按策略和损失上限决定是否允许 must 兜底。"""
    if not plan:
        return None
    facts = plan.get("info_required")
    if not isinstance(facts, list):
        return None
    from services.generation_content_policy import current_content_policy

    if current_content_policy().is_static:
        if max_fact_count is not None and max_fact_count < 1:
            return None
        return _static_optional_drop_candidate(
            compact_dsl,
            plan,
            allowed_fact_indexes,
            allow_must_fallback=allow_must_fallback,
            approved_indexes=approved_omitted_fact_indexes,
        )
    try:
        rows = parse_compact_dsl_rows(
            compact_dsl,
            expand_layouts=False,
            skip_compact_dsl_validation=allow_invalid_table_text,
            preserve_unreachable=True,
        )
    except (TypeError, ValueError):
        return None
    reachable_component_ids = _reachable_component_ids(rows)
    reachable_core_component_ids = _reachable_core_component_ids(rows)
    defined_core_component_ids = _defined_core_component_ids(rows)
    if not defined_core_component_ids:
        return None
    requires_core_reattach = not reachable_core_component_ids
    protected_core_component_ids = (
        defined_core_component_ids
        if requires_core_reattach
        else reachable_core_component_ids
    )
    event_handlers = _event_handlers_by_id(task_spec)
    preserved_fact_indexes: set[int] = set()
    if requires_core_reattach:
        for row in rows:
            if not isinstance(row, ComponentRow):
                continue
            if row.component_id not in protected_core_component_ids:
                continue
            matched, _priorities, has_action_fact = _drop_fact_matches(
                row,
                facts,
                event_handlers,
            )
            if not has_action_fact:
                preserved_fact_indexes.update(matched)
    should_only_candidates: list[CompactOptionalDropCandidate] = []
    fallback_candidates: list[CompactOptionalDropCandidate] = []
    for row in rows:
        if not isinstance(row, ComponentRow):
            continue
        if row.component_id not in reachable_component_ids:
            continue
        if allow_invalid_table_text:
            items = row.props.get("items")
            if row.component_type != "TableText" or not isinstance(items, list):
                continue
            if len(items) <= 3:
                continue
        if row.component_type in {"Row", "Column", "Stack"}:
            continue
        if row.component_type in _ACTION_FACT_COMPONENTS:
            continue
        if row.props.get("onClick"):
            continue
        partial_candidate = _item_partial_drop_candidate(
            row,
            facts,
            event_handlers,
            allowed_fact_indexes,
            max_fact_count,
            preserved_fact_indexes,
        )
        if partial_candidate is not None:
            partial_candidate = replace(
                partial_candidate,
                requires_core_reattach=requires_core_reattach,
                protected_core_component_ids=tuple(sorted(protected_core_component_ids)),
            )
            target = fallback_candidates
            if not partial_candidate.contains_must_facts:
                target = should_only_candidates
            target.append(partial_candidate)
            continue
        if row.component_type == "SecondaryBody" and allowed_fact_indexes is not None:
            continue
        if (
            row.component_id in protected_core_component_ids
            and len(protected_core_component_ids) <= 1
        ):
            continue
        matched, priorities, has_action_fact = _drop_fact_matches(
            row,
            facts,
            event_handlers,
        )
        if has_action_fact or not matched:
            continue
        omission_pairs = [
            (index, priority)
            for index, priority in zip(matched, priorities, strict=True)
            if index not in preserved_fact_indexes
        ]
        if not omission_pairs:
            continue
        omission_indexes = [index for index, _priority in omission_pairs]
        if max_fact_count is not None and len(omission_indexes) > max_fact_count:
            continue
        if allowed_fact_indexes is not None:
            carries_unrelated_fact = any(
                fact_index not in allowed_fact_indexes for fact_index in omission_indexes
            )
            if carries_unrelated_fact:
                continue
        requirements = tuple(
            str(facts[index].get("requirement") or "") for index in omission_indexes
        )
        candidate = CompactOptionalDropCandidate(
            component_id=row.component_id,
            component_type=row.component_type,
            fact_indexes=tuple(omission_indexes),
            requirements=requirements,
            contains_must_facts=any(
                priority != "should" for _index, priority in omission_pairs
            ),
            requires_core_reattach=requires_core_reattach,
            protected_core_component_ids=tuple(sorted(protected_core_component_ids)),
        )
        if candidate.contains_must_facts:
            fallback_candidates.append(candidate)
        else:
            should_only_candidates.append(candidate)
    candidates = should_only_candidates
    if not candidates and allow_must_fallback:
        candidates = fallback_candidates
    if not candidates:
        return None

    def candidate_key(item: CompactOptionalDropCandidate) -> tuple[bool, int]:
        return (
            item.component_id in protected_core_component_ids,
            len(item.fact_indexes),
        )

    return min(candidates, key=candidate_key)


def _static_optional_drop_candidate(
    source: str,
    plan: dict[str, Any],
    allowed_indexes: set[int] | None,
    *,
    allow_must_fallback: bool,
    approved_indexes: tuple[int, ...] = (),
) -> CompactOptionalDropCandidate | None:
    """静态删减按事实授权；优先 should，无候选时才允许 must 兜底。"""
    from services.card_validation.compact_validation.semantic.static_content import (
        static_fact_coverage,
    )

    facts = plan.get("info_required")
    if not isinstance(facts, list):
        return None
    try:
        coverage_rows = static_fact_coverage(source, plan, approved_indexes)
    except (TypeError, ValueError):
        return None
    visible_indexes = {
        coverage.fact_index for coverage in coverage_rows if coverage.visible
    }
    visible_indexes.difference_update(approved_indexes)
    object_groups = []
    for group in plan.get("contentGroups", []):
        if group.get("kind") != "object":
            continue
        indexes = {
            index
            for index in group.get("factIndexes", [])
            if type(index) is int and 0 <= index < len(facts)
        }
        if indexes:
            object_groups.append(indexes)
    should_candidates = []
    must_candidates = []
    for coverage in coverage_rows:
        index = coverage.fact_index
        if index in approved_indexes:
            continue
        if allowed_indexes is not None and index not in allowed_indexes:
            continue
        fact = facts[index]
        protected = fact.get("protectedTexts") or fact.get("preserveVerbatim")
        if protected:
            continue
        if not coverage.visible or coverage.component_id is None:
            continue
        remaining_visible_indexes = visible_indexes - {index}
        retains_body_object = any(
            bool(group_indexes.intersection(remaining_visible_indexes))
            for group_indexes in object_groups
        )
        if not retains_body_object:
            continue
        text = fact.get("text")
        if not isinstance(text, str):
            continue
        requirement = fact.get("requirement")
        if not isinstance(requirement, str):
            requirement = text
        candidate = CompactOptionalDropCandidate(
            component_id=coverage.component_id,
            component_type="static_content",
            fact_indexes=(index,),
            requirements=(requirement,),
            contains_must_facts=fact.get("priority") != "should",
            partial=True,
            display_texts=(text,),
        )
        if candidate.contains_must_facts:
            must_candidates.append(candidate)
        else:
            should_candidates.append(candidate)
    candidates = should_candidates
    if not candidates and allow_must_fallback:
        candidates = must_candidates
    if not candidates:
        return None
    shared_title_indexes = set()
    for group in plan.get("contentGroups", []):
        if group.get("kind") != "shared":
            continue
        for index in group.get("factIndexes", []):
            if facts[index].get("displayRole") == "title":
                shared_title_indexes.add(index)
    return max(
        candidates,
        key=lambda candidate: (
            not shared_title_indexes.intersection(candidate.fact_indexes), candidate.fact_indexes,
        ),
    )


def _required_anchor_layout(
    plan: dict[str, Any],
    task_spec: dict[str, Any],
) -> str | None:
    """已闭合的 anchor 方案是执行选择，不允许 DSL 阶段无理由降级为文字按钮。"""
    if task_spec.get("size") != "2x2":
        return None
    composition = plan.get("composition")
    if not isinstance(composition, dict) or composition.get("layout") != "S-title-anchor":
        return None
    if composition_implementation_conflicts(plan):
        return None
    for fact in plan.get("info_required", []):
        if not isinstance(fact, dict) or "actionId" not in fact:
            continue
        hints = fact.get("componentHints")
        if isinstance(hints, list) and hints and hints[0] == "CircleButton":
            return "S-title-anchor"
    return None


def compact_plan_required_route(
    plan: dict[str, Any],
    task_spec: dict[str, Any],
) -> dict[str, str] | None:
    """返回已接受 Plan 中可安全锁定的精确单焦点执行路线。"""
    if task_spec.get("size") != "2x2" or composition_implementation_conflicts(plan):
        return None
    facts = plan.get("info_required")
    if not isinstance(facts, list) or len(facts) != 1:
        return None
    fact = facts[0]
    if not isinstance(fact, dict) or "actionId" in fact:
        return None
    component_hints = fact.get("componentHints")
    layout_hints = plan.get("layoutHints")
    preferred_component = (
        component_hints[0] if isinstance(component_hints, list) and component_hints else None
    )
    preferred_layout = layout_hints[0] if isinstance(layout_hints, list) and layout_hints else None
    if preferred_component != "DataDisplay" or preferred_layout != "S-center":
        return None
    if not _data_display_route_fits_fact(fact, task_spec):
        return None
    return {"layout": "S-center", "component": "DataDisplay"}


def _data_display_route_fits_fact(
    fact: dict[str, Any],
    task_spec: dict[str, Any],
) -> bool:
    """仅在现有事实没有明确违反 DataDisplay 值容量时锁定路线。"""
    value: Any = fact.get("text")
    data_id = fact.get("dataId")
    if isinstance(data_id, str):
        value = _task_schema_sample(task_spec, data_id)
    if value is None:
        return isinstance(data_id, str)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return True
    if not isinstance(value, str) or not value.strip():
        return False
    normalized = value.strip()
    numeric_text = re.fullmatch(
        r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[%％])?",
        normalized,
    )
    if numeric_text is not None:
        return True
    character_count = len(re.sub(r"\s+", "", normalized))
    return 1 <= character_count <= 8


def _task_schema_sample(task_spec: dict[str, Any], data_id: str) -> Any:
    """读取 TaskSpec 展开 schema 的样例值；未知路径不伪造结论。"""
    parts = parse_json_pointer(data_id)
    current: Any = task_spec.get("dataModelSchema")
    if parts is None:
        return None
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
            continue
        if isinstance(current, list) and part.isdigit():
            index = int(part)
            current = current[index] if 0 <= index < len(current) else None
            continue
        return None
    return current.get("sampleValue") if isinstance(current, dict) else None


def compact_plan_data_paths(task_spec: dict[str, Any]) -> tuple[str, ...]:
    """按 TaskSpec 顺序列出可作为事实目标的叶子 JSON Pointer。"""
    schema = task_spec.get("dataModelSchema")
    if not isinstance(schema, dict):
        return ()
    paths: list[str] = []
    _collect_schema_paths(schema, (), paths)
    return tuple(dict.fromkeys(paths))


def compact_plan_action_ids(task_spec: dict[str, Any]) -> tuple[str, ...]:
    """列出本轮动作实例引用，重复的能力 ID 不覆盖不同参数。"""
    return tuple(plan_action_candidates(task_spec))


def compact_plan_asset_ids(task_spec: dict[str, Any]) -> tuple[str, ...]:
    """按 TaskSpec 顺序列出具有稳定 ID 和静态路径的素材候选。"""
    candidates = task_spec.get("assetCandidates")
    if not isinstance(candidates, list):
        return ()
    identifiers: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        identifier = candidate.get("id")
        source = candidate.get("src")
        if not isinstance(identifier, str) or not identifier.strip():
            continue
        if not isinstance(source, str) or not source.strip():
            continue
        identifiers.append(identifier.strip())
    return tuple(dict.fromkeys(identifiers))


def _normalize_asset_assignments(
    value: Any,
    facts: list[dict[str, Any]],
    task_spec: dict[str, Any],
    *,
    whole_card_action_id: str | None = None,
) -> dict[str, Any]:
    """校验按钮优先、标题随后且不复用素材的显式分配。"""
    if not isinstance(value, dict) or set(value) != {"actions", "title"}:
        raise CompactPlanValidationError(["assetAssignments must contain only actions and title."])
    asset_ids = set(compact_plan_asset_ids(task_spec))
    selected_action_ids = [
        fact.get("actionId") for fact in facts if isinstance(fact.get("actionId"), str)
    ]
    actions = value.get("actions")
    if not isinstance(actions, list):
        raise CompactPlanValidationError(["assetAssignments.actions must be an array."])
    normalized_actions: dict[str, dict[str, Any]] = {}
    action_assets: set[str] = set()
    errors: list[str] = []
    for index, assignment in enumerate(actions):
        location = f"assetAssignments.actions[{index}]"
        if not isinstance(assignment, dict):
            errors.append(f"{location} must be an object.")
            continue
        unknown_keys = set(assignment) - {"actionId", "assetId", "reason"}
        if unknown_keys:
            names = ", ".join(sorted(unknown_keys))
            errors.append(f"{location} contains unsupported fields: {names}.")
            continue
        action_id = assignment.get("actionId")
        if action_id not in selected_action_ids:
            errors.append(f"{location}.actionId is not selected by info_required.")
            continue
        if action_id in normalized_actions:
            errors.append(f"{location}.actionId is duplicated: {action_id}.")
            continue
        item_detail = False
        if isinstance(action_id, str) and event_card_detail_action(task_spec, action_id):
            for fact in facts:
                if fact.get("actionId") == action_id:
                    item_detail = prefers_event_card_item(fact)
                    break
        if item_detail:
            normalized = {"assetId": None, "reason": "EventCard item detail has no button icon."}
        elif action_id == whole_card_action_id:
            normalized = {"assetId": None, "reason": "Whole-card detail has no button icon."}
        else:
            normalized = _normalize_single_asset_assignment(
                assignment,
                asset_ids,
                location=location,
                used_assets=set(),
                errors=errors,
            )
            assigned_asset_id = normalized.get("assetId")
            if isinstance(assigned_asset_id, str):
                action_assets.add(assigned_asset_id)
        normalized["actionId"] = action_id
        normalized_actions[action_id] = normalized
    missing_actions = [
        action_id for action_id in selected_action_ids if action_id not in normalized_actions
    ]
    if missing_actions:
        errors.append(
            "assetAssignments.actions must decide every selected action: "
            + ", ".join(missing_actions)
            + "."
        )
    title = value.get("title")
    if not isinstance(title, dict):
        errors.append("assetAssignments.title must be an object.")
        normalized_title: dict[str, Any] = {"assetId": None, "reason": "invalid"}
    else:
        unknown_keys = set(title) - {"assetId", "reason"}
        if unknown_keys:
            names = ", ".join(sorted(unknown_keys))
            errors.append(f"assetAssignments.title contains unsupported fields: {names}.")
        if _is_two_by_two_dual_action_plan(facts, task_spec.get("size")):
            normalized_title = {
                "assetId": None,
                "reason": "S-content-dual-action has no title slot.",
            }
        else:
            normalized_title = _normalize_single_asset_assignment(
                title,
                asset_ids,
                location="assetAssignments.title",
                used_assets=action_assets,
                errors=errors,
            )
    if errors:
        raise CompactPlanValidationError(errors)
    ordered_actions = [normalized_actions[action_id] for action_id in selected_action_ids]
    return {"actions": ordered_actions, "title": normalized_title}


def _normalize_single_asset_assignment(
    value: dict[str, Any],
    asset_ids: set[str],
    *,
    location: str,
    used_assets: set[str],
    errors: list[str],
) -> dict[str, Any]:
    """标准化单个按钮或标题的素材决定。"""
    asset_id = value.get("assetId")
    reason = value.get("reason")
    if asset_id is None:
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"{location}.reason is required when assetId is null.")
            return {"assetId": None, "reason": "invalid"}
        return {"assetId": None, "reason": reason.strip()}
    if not isinstance(asset_id, str) or asset_id not in asset_ids:
        errors.append(f"{location}.assetId is not present in TaskSpec asset candidates.")
        return {"assetId": None, "reason": "invalid"}
    if asset_id in used_assets:
        errors.append(f"{location}.assetId reuses an already assigned asset: {asset_id}.")
    used_assets.add(asset_id)
    return {"assetId": asset_id}


def _validate_facts(
    value: Any,
    task_spec: dict[str, Any],
    *,
    static_text_source: str | None,
    static_content: bool = False,
) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(value, list) or not value:
        raise CompactPlanValidationError(
            ["info_required must be a non-empty array of atomic facts."]
        )
    if len(value) > 24:
        raise CompactPlanValidationError(["info_required must contain at most 24 facts."])
    data_paths = set(compact_plan_data_paths(task_spec))
    progress_paths: list[str] = []
    _collect_progress_schema_paths(
        task_spec.get("dataModelSchema"),
        (),
        progress_paths,
    )
    progress_data_paths = set(progress_paths)
    action_ids = set(compact_plan_action_ids(task_spec))
    allowed_hints = set(_component_hints(task_spec.get("size")))
    user_query = task_spec.get("userQuery")
    query_text = user_query if isinstance(user_query, str) else ""
    if static_text_source:
        query_text = f"{query_text}\n{static_text_source}"
    normalized: list[dict[str, Any]] = []
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    warnings: list[str] = []
    errors: list[str] = []
    for index, raw_fact in enumerate(value):
        location = f"info_required[{index}]"
        if not isinstance(raw_fact, dict):
            errors.append(f"{location} must be an object.")
            continue
        unknown_keys = set(raw_fact) - _FACT_KEYS
        if unknown_keys:
            names = ", ".join(sorted(unknown_keys))
            errors.append(f"{location} contains unsupported fields: {names}.")
            continue
        requirement = raw_fact.get("requirement")
        if not isinstance(requirement, str) or not requirement.strip():
            errors.append(f"{location}.requirement must be non-empty text.")
            continue
        targets = [name for name in _TARGET_KEYS if _non_empty(raw_fact.get(name))]
        if len(targets) != 1:
            errors.append(f"{location} must choose exactly one of dataId, actionId, or text.")
            continue
        target = targets[0]
        target_value = raw_fact[target].strip()
        if target == "dataId" and target_value not in data_paths:
            errors.append(f"{location}.dataId is not present in TaskSpec: {target_value}.")
            continue
        if target == "dataId" and _internal_action_parameter_fact(
            target_value,
            requirement,
            task_spec,
            query_text,
        ):
            errors.append(
                f"{location}: {target_value} is an internal identifier used only by an action, "
                "not a requested visible fact. Keep its original path in the complete event "
                "candidate and retain that action; rebuild this Plan with every real display "
                "requirement, without adding an identifier text row. Do not remove user facts."
            )
            continue
        if target == "actionId" and target_value not in action_ids:
            errors.append(f"{location}.actionId is not present in TaskSpec: {target_value}.")
            continue
        source_mismatch = _normalize_text(target_value) not in _normalize_text(query_text)
        if target == "text" and source_mismatch and not static_content:
            warnings.append(f"{location}.text must be copied from userQuery.")
        priority = raw_fact.get("priority", "must")
        if priority not in _FACT_PRIORITIES:
            errors.append(f"{location}.priority must be must or should.")
            continue
        if target == "actionId" and priority != "must":
            priority = "must"
            warnings.append(f"{location}.priority was forced to must for an action.")
        fact: dict[str, Any] = {
            "requirement": requirement.strip(),
            "priority": priority,
            target: target_value,
        }
        hints = raw_fact.get("componentHints")
        if hints is not None:
            if not isinstance(hints, list):
                warnings.append(
                    f"{location}.componentHints was ignored because it is not an array."
                )
            else:
                accepted_hints: list[str] = []
                removed_type_mismatch = False
                removed_target_mismatch = False
                for hint in hints:
                    if not isinstance(hint, str) or hint not in allowed_hints:
                        continue
                    item_detail = False
                    if target == "actionId" and hint == "EventCard":
                        item_detail = event_card_detail_action(task_spec, target_value)
                    is_action_hint = hint in _ACTION_FACT_COMPONENTS or item_detail
                    if (target == "actionId") != is_action_hint:
                        removed_target_mismatch = True
                        continue
                    if hint in _PROGRESS_FACT_COMPONENTS:
                        if target != "dataId" or target_value not in progress_data_paths:
                            removed_type_mismatch = True
                            continue
                    if hint not in accepted_hints:
                        accepted_hints.append(hint)
                removed_single_line_title_alternatives = False
                removed_single_line_title_backup = False
                allow_title_backup_removal = task_spec.get("size") == "2x2"
                if task_spec.get("size") == "2x4" and accepted_hints:
                    if accepted_hints[0] == "Badge":
                        allow_title_backup_removal = True
                if allow_title_backup_removal and accepted_hints:
                    title_is_backup = accepted_hints[0] != "SingleLineTitle"
                    if title_is_backup and "SingleLineTitle" in accepted_hints:
                        accepted_hints.remove("SingleLineTitle")
                        removed_single_line_title_backup = True
                if "SingleLineTitle" in accepted_hints and accepted_hints != ["SingleLineTitle"]:
                    accepted_hints = ["SingleLineTitle"]
                    removed_single_line_title_alternatives = True
                if accepted_hints:
                    fact["componentHints"] = accepted_hints[:3]
                if accepted_hints != hints:
                    reason = "unsupported or duplicate values."
                    if removed_single_line_title_backup:
                        reason = (
                            "a fallback SingleLineTitle cannot override the preferred "
                            "body component or create a new mandatory title role."
                        )
                    elif removed_single_line_title_alternatives:
                        reason = (
                            "alternatives because SingleLineTitle is the exclusive title component."
                        )
                    elif removed_target_mismatch:
                        reason = "unsupported, target-incompatible or duplicate values."
                    elif removed_type_mismatch:
                        reason = "unsupported, type-incompatible or duplicate values."
                    warnings.append(f"{location}.componentHints removed {reason}")
        identity = (target, target_value)
        previous = seen.get(identity)
        if previous is None:
            seen[identity] = fact
            normalized.append(fact)
            continue
        if fact["requirement"] not in previous["requirement"]:
            previous["requirement"] += "; " + fact["requirement"]
        if fact["priority"] == "must":
            previous["priority"] = "must"
        merged_hints = list(
            dict.fromkeys([*previous.get("componentHints", []), *fact.get("componentHints", [])])
        )
        if merged_hints:
            previous["componentHints"] = merged_hints[:3]
        warnings.append(f"{location} duplicated an existing target and was merged.")
    if errors:
        raise CompactPlanValidationError(errors)
    return normalized, warnings


def _internal_action_parameter_fact(
    path: str,
    requirement: str,
    task: dict[str, Any],
    query: str,
) -> bool:
    """仅反馈计划自己承认的内部传参标识错误；不推断普通字段不可见。"""
    if not re.search(r"仅供|仅用于|用于(?:打开|定位|识别|传参)", requirement):
        return False
    if re.search(
        r"(?:显示|展示|查看).{0,16}(?:编号|标识|(?<![a-z])ID(?![a-z])|entityId)", query, re.I
    ):
        return False
    from services.compact_composition_planner import _schema_value

    description = _schema_value(task, path).get("description", "")
    if not re.search(r"(?:唯一|内部).{0,12}(?:标识|(?<![a-z])ID(?![a-z]))", description, re.I):
        return False
    for candidate in task.get("eventCandidates", []):
        if not isinstance(candidate, dict):
            continue
        paths: set[str] = set()
        literals: list[str] = []
        _collect_paths_and_literals(candidate.get("args"), paths, literals)
        if path in paths:
            return True
    return False


def _normalize_layout_hints(
    value: Any,
    size: Any,
) -> tuple[list[str], list[str]]:
    if value is None:
        return [], []
    if not isinstance(value, list):
        return [], ["layoutHints was ignored because it is not an array."]
    allowed = set(_layout_hints(size))
    accepted: list[str] = []
    for item in value:
        if isinstance(item, str) and item in allowed and item not in accepted:
            accepted.append(item)
    accepted = accepted[:2]
    warnings = []
    if accepted != value:
        warnings.append("layoutHints removed unsupported, duplicate, or excess values.")
    return accepted, warnings


def _normalize_two_by_four_action_layouts(
    facts: list[dict[str, Any]],
    layout_hints: list[str],
    size: Any,
) -> tuple[list[str], list[str]]:
    """移除无法承载 2x4 显式动作的无动作布局软候选。"""
    has_action = any(_requires_action_button(fact) for fact in facts)
    if size != "2x4" or not has_action or "W-top-bottom" not in layout_hints:
        return layout_hints, []

    accepted = [layout for layout in layout_hints if layout != "W-top-bottom"]
    warning = (
        "W-top-bottom was removed from layoutHints because the 2x4 Plan contains "
        "an Action and this layout has no legal action slot."
    )
    return accepted, [warning]


def _normalize_dual_action_plan(
    facts: list[dict[str, Any]],
    layout_hints: list[str],
    size: Any,
) -> tuple[list[str], list[str]]:
    """统一 2x2 双必要动作的布局和按钮，保留内容事实与软候选。"""
    if not _is_two_by_two_dual_action_plan(facts, size):
        if size == "2x2" and "S-content-dual-action" in layout_hints:
            accepted = [hint for hint in layout_hints if hint != "S-content-dual-action"]
            return accepted, [
                "S-content-dual-action was removed from layoutHints because the Plan "
                "does not contain exactly two distinct actions; preserve the actual facts "
                "and actions without inventing a second action."
            ]
        return layout_hints, []

    warnings: list[str] = []
    normalized_layouts = ["S-content-dual-action"]
    if layout_hints != normalized_layouts:
        warnings.append("Two required 2x2 actions force layoutHints to S-content-dual-action.")

    for fact in facts:
        if not _requires_action_button(fact):
            continue
        hints = fact.get("componentHints")
        if hints != ["CardButton"]:
            fact["componentHints"] = ["CardButton"]
            warnings.append("A 2x2 dual-action fact uses CardButton in S-content-dual-action.")
    return normalized_layouts, warnings


def _is_two_by_two_dual_action_plan(
    facts: list[dict[str, Any]],
    size: Any,
) -> bool:
    if size != "2x2":
        return False
    return _has_two_distinct_actions(facts)


def _has_two_distinct_actions(facts: Any) -> bool:
    """固定双动作约束来自事实，不把模型候选或重复动作当作两个动作。"""
    if not isinstance(facts, list):
        return False
    action_ids: list[str] = []
    for fact in facts:
        if not isinstance(fact, dict):
            return False
        if not _requires_action_button(fact):
            continue
        action_id = fact.get("actionId")
        if isinstance(action_id, str) and action_id.strip():
            action_ids.append(action_id)
    return len(action_ids) == 2 and len(set(action_ids)) == 2


def _requires_action_button(fact: dict[str, Any]) -> bool:
    return (
        isinstance(fact.get("actionId"), str)
        and not prefers_event_card_item(fact)
    )


def _parse_json_object(
    raw_output: str,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(raw_output, str) or not raw_output.strip():
        raise CompactPlanValidationError(["Plan output must be non-empty JSON."])
    text = raw_output.strip()
    match = _JSON_FENCE.fullmatch(text)
    if match is not None:
        text = match.group(1).strip()
    try:
        payload = decode_plan_json(text)
    except PlanDuplicateKeyError as exc:
        raise CompactPlanValidationError([str(exc)]) from exc
    except json.JSONDecodeError as exc:
        repaired = _recover_plan_closers(text)
        if repaired is None:
            raise CompactPlanValidationError([
                "Plan output must be valid JSON. "
                f"line={exc.lineno}, column={exc.colno}, offset={exc.pos}: {exc.msg}. "
                "只修复JSON结构，不猜补事实；数组须完整闭合，数组元素之间使用逗号。"
            ]) from exc
        payload = repaired
        if warnings is not None:
            warnings.append("Plan JSON terminal closing delimiters recovered; facts unchanged.")
    if not isinstance(payload, dict):
        raise CompactPlanValidationError(["Plan output root must be an object."])
    return payload


def _recover_plan_closers(text: str) -> dict[str, Any] | None:
    """只恢复终端纯闭合串，不补值、不改字符串、不修内部结构。"""
    suffix = re.search(r"[\]}\s]+$", text)
    if suffix is None:
        return None
    prefix = text[: suffix.start()]
    stack: list[str] = []
    in_string = False
    escaped = False
    for char in prefix:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "[{":
            stack.append("]" if char == "[" else "}")
        elif char in "]}":
            if not stack or stack.pop() != char:
                return None
    if in_string or not stack:
        return None
    actual = re.sub(r"\s", "", suffix.group())
    expected = "".join(reversed(stack))
    if not 1 <= abs(len(actual) - len(expected)) <= 2:
        return None
    shorter, longer = sorted((actual, expected), key=len)
    cursor = iter(longer)
    for char in shorter:
        if char not in cursor:
            return None
    try:
        payload = decode_plan_json(prefix + expected)
    except (json.JSONDecodeError, PlanDuplicateKeyError):
        return None
    return payload if isinstance(payload, dict) else None


def _collect_schema_paths(
    value: Any,
    path: tuple[str | int, ...],
    output: list[str],
    *,
    numeric_only: bool = False,
) -> None:
    if isinstance(value, list):
        for index, item in enumerate(value):
            _collect_schema_paths(item, (*path, index), output, numeric_only=numeric_only)
        return
    if not isinstance(value, dict):
        if path and not numeric_only:
            output.append(_json_pointer(path))
        return
    if _is_schema_leaf(value):
        if path and (not numeric_only or value.get("type") in {"number", "integer"}):
            output.append(_json_pointer(path))
        return
    if value.get("type") == "array" and "items" in value:
        _collect_schema_paths(value["items"], (*path, 0), output, numeric_only=numeric_only)
        return
    if value.get("type") == "object" and isinstance(value.get("properties"), dict):
        for key, child in value["properties"].items():
            _collect_schema_paths(child, (*path, key), output, numeric_only=numeric_only)
        return
    for key, child in value.items():
        _collect_schema_paths(child, (*path, key), output, numeric_only=numeric_only)


def _collect_progress_schema_paths(
    value: Any,
    path: tuple[str | int, ...],
    output: list[str],
) -> None:
    if isinstance(value, list):
        for index, item in enumerate(value):
            _collect_progress_schema_paths(item, (*path, index), output)
        return
    if not isinstance(value, dict):
        return
    if _is_schema_leaf(value):
        field_type = value.get("type")
        numeric_field = field_type in {"number", "integer"}
        percentage_text = field_type == "string" and isinstance(value.get("numericSource"), str)
        if path and (numeric_field or percentage_text):
            output.append(_json_pointer(path))
        return
    if value.get("type") == "array" and "items" in value:
        _collect_progress_schema_paths(value["items"], (*path, 0), output)
        return
    if value.get("type") == "object" and isinstance(value.get("properties"), dict):
        for key, child in value["properties"].items():
            _collect_progress_schema_paths(child, (*path, key), output)
        return
    for key, child in value.items():
        _collect_progress_schema_paths(child, (*path, key), output)


def _is_schema_leaf(value: dict[str, Any]) -> bool:
    field_type = value.get("type")
    if isinstance(field_type, str) and field_type not in {"array", "object"}:
        return True
    return "sampleValue" in value and not isinstance(value.get("sampleValue"), dict)


def _json_pointer(path: tuple[str | int, ...]) -> str:
    tokens = [str(item).replace("~", "~0").replace("/", "~1") for item in path]
    return "/" + "/".join(tokens)


def _collect_paths_and_literals(
    value: Any,
    paths: set[str],
    literals: list[str],
) -> None:
    if isinstance(value, str):
        matches = list(_BINDING_PATH.finditer(value))
        if matches:
            paths.update(match.group("path") for match in matches)
        else:
            literals.append(value)
        return
    if isinstance(value, dict):
        if set(value) == {"path"} and isinstance(value.get("path"), str):
            paths.add(value["path"])
            return
        for child in value.values():
            _collect_paths_and_literals(child, paths, literals)
        return
    if isinstance(value, list):
        for child in value:
            _collect_paths_and_literals(child, paths, literals)


def _collect_visible_path_occurrences(
    value: Any,
    *,
    component_id: str,
    component_type: str,
    property_path: str,
    occurrences: list[_CompactVisiblePathOccurrence],
) -> None:
    if isinstance(value, str):
        for match in _BINDING_PATH.finditer(value):
            occurrences.append(
                _CompactVisiblePathOccurrence(
                    data_id=match.group("path"),
                    component_id=component_id,
                    component_type=component_type,
                    property_path=property_path,
                )
            )
        return
    if isinstance(value, dict):
        if set(value) == {"path"} and isinstance(value.get("path"), str):
            occurrences.append(
                _CompactVisiblePathOccurrence(
                    data_id=value["path"],
                    component_id=component_id,
                    component_type=component_type,
                    property_path=property_path,
                )
            )
            return
        for key, child in value.items():
            child_path = f"{property_path}.{key}"
            _collect_visible_path_occurrences(
                child,
                component_id=component_id,
                component_type=component_type,
                property_path=child_path,
                occurrences=occurrences,
            )
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            child_path = f"{property_path}[{index}]"
            _collect_visible_path_occurrences(
                child,
                component_id=component_id,
                component_type=component_type,
                property_path=child_path,
                occurrences=occurrences,
            )


def _event_handlers_by_id(task_spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return plan_action_handlers(task_spec)


def _event_handler_mismatch(
    expected: dict[str, Any] | None,
    actual_handlers: tuple[dict[str, Any], ...],
) -> str:
    """向修复模型说明同类事件的精确参数差异，避免按常识改写值。"""
    if expected is None:
        return ""
    expected_call = expected.get("call")
    expected_args = expected.get("args")
    expected_intent = None
    if isinstance(expected_args, dict):
        expected_intent = expected_args.get("intentName")
    closest = None
    for handler in actual_handlers:
        if handler.get("call") != expected_call:
            continue
        if closest is None:
            closest = handler
        handler_args = handler.get("args")
        if isinstance(handler_args, dict) and handler_args.get("intentName") == expected_intent:
            closest = handler
            break
    if closest is None:
        return " Copy the complete call and args from the matching TaskSpec event candidate."
    expected_text = json.dumps(expected, ensure_ascii=False, separators=(",", ":"))
    actual_text = json.dumps(closest, ensure_ascii=False, separators=(",", ":"))
    return (
        f" Expected exact onClick handler {expected_text}, but found {actual_text}."
        " Copy call and args exactly; do not infer, invert, or rewrite parameter values."
    )


def _component_hints(size: Any) -> tuple[str, ...]:
    candidates = MODEL_COMPONENT_TYPES_BY_SIZE.get(size, SHARED_FACT_COMPONENTS)
    from services.generation_content_policy import (
        current_content_policy,
        static_model_components,
    )

    if current_content_policy().is_static:
        return tuple(sorted(static_model_components(size)))
    return tuple(
        component for component in candidates if component in MODEL_COMPACT_INPUT_COMPONENT_TYPES
    )


def _layout_hints(size: Any) -> tuple[str, ...]:
    from services.generation_content_policy import current_content_policy, static_layout_ids

    if current_content_policy().is_static:
        return static_layout_ids(size)
    return _LAYOUT_HINTS.get(size, ())


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", "", value).casefold() if isinstance(value, str) else ""


def _non_empty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())
