"""模板内部商用契约回归：契约断言已固化为场景金样（Layer C）。

天气内建资产范围、日志摘要脱敏、cardtpl 编译/解析拒绝矩阵（废弃 Variant
语法、未知 Theme 引用、非法 children 槽位、非法 EventAction 用法、三参
Template 调用）、Theme 引用解析、索引 children 槽位展开、内置 7 个布局
蓝图骨架、HeroTitleContent 布局弹性高度、融合球主题 Compact 规则、动作
模板 props/onClick 契约、可选 EventAction 的 onClick 缺省矩阵、布局-动作
组合校验矩阵、双业务第二层布局选择投影与模型 JSON 提取，全部固化为
``internal_contracts__*`` 场景金样（错误路径冻结 ``errorType`` 与完整
message，正常路径冻结解析/实例化后的具体取值）。保留为普通测试的仅剩
注册表全量「内联样式、无设计令牌」结构不变量——它是对 checked-in 模板
源的结构 pin，不属于单一渲染产物契约。场景金样尚未固化时，统一门禁会
显示为待固化新增（``golden_cli bless --declared <场景ID>``）；引擎改动
后按 golden 工作流 ``check --diff`` / ``bless --declared`` 复核。
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from models.generation import EventAction, TaskSpec
from services.template_generation.engine.advanced.models import AdvancedScopeBrief
from services.template_generation.engine.advanced.ux_mixed_prompt import (
    _filter_positional_second_layer_template_candidates,
    _layout_output_option,
    _second_layer_layout_selection,
    _weather_builtin_assets_for_components,
)
from services.template_generation.engine.cardplan.compiler import (
    _instantiate_blueprint,
    _validate_provider_template_layout_action_requirements,
)
from services.template_generation.engine.cardplan.models import (
    TEMPLATE_CHILD_SLOT_COMPONENT,
    SourceSpan,
    TemplateNode,
)
from services.template_generation.engine.cardplan.parser import (
    ParsedCall,
    parse_hybrid_card,
)
from services.template_generation.engine.cardplan.provider_bundle import (
    compile_card_template,
)
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.pipeline import (
    _prompt_size_summary,
    _task_spec_log_summary,
)
from services.template_generation.engine.tersel_converter import Nested2Node
from services.template_generation.model_client import _parse_json_object
from services.template_generation.test_support.golden_scenarios import scenario


def _error_outcome(call: Any) -> dict[str, Any]:
    """把一次确定性调用的结果折叠成可冻结的错误契约载荷。"""
    try:
        call()
    except Exception as exc:  # 错误类型与完整 message 即契约本身
        return {"errorType": type(exc).__name__, "message": str(exc)}
    return {"error": "NO_ERROR"}


def _compile_source(
    source: str,
    *,
    wire_id: str,
    provider_id: str,
    description: str,
    supported_card_sizes: tuple[str, ...] = (),
) -> Any:
    return compile_card_template(
        source,
        provider_id=provider_id,
        business_id=None,
        expected_wire_id=wire_id,
        expected_capability_id=None,
        data_domain=None,
        description=description,
        supported_card_sizes=supported_card_sizes,
        primary_data=(),
        secondary_data=(),
        optional_data=(),
        output_schema={"type": "object", "properties": {}},
    )


_THEME_REFERENCE_SOURCE = """#Template ThemeReference@1(props: {})
data = {
}

Column(
  {"backgroundColor": $theme('actionStyle.backgroundColor')},
  Text("主内容", {"fontColor": $theme('primaryColor')}),
  Text("辅助内容", {"fontColor": $theme('supportContentColor')}),
  Progress({"value": 50, "total": 100, "color": $theme('progressColor')})
)
#End
"""

_HERO_ACTION_LAYOUT_SOURCE = """#Template HeroActionLayout@1(props: {}, ...children)
data = {
}

Column({
  "width": "matchParent",
  "height": "matchParent",
  "itemMargin": 8
},
  Column({
    "width": "matchParent",
    "layoutWeight": 1
  }, children[0]),
  Column({
    "width": "matchParent",
    "height": 36
  }, children[1])
)
#End
"""

_OPTIONAL_ACTION_SOURCE = """#Template OptionalAction@1(props: { actionId?: string })
data = {
}

Stack({
  "width": "matchParent",
  "onClick": EventAction(props?.actionId)
}, Text("动作", "body"))
#End
"""


@scenario("internal_contracts__weather_builtin_assets")
def _build_weather_builtin_assets() -> dict[str, Any]:
    template_weather = SimpleNamespace(
        name="WeatherOverview",
        implementation="template",
    )
    direct_weather = SimpleNamespace(
        name="WeatherOverview",
        implementation="terse-dsl",
    )
    return {
        "templateImplementation": list(
            _weather_builtin_assets_for_components((template_weather,))
        ),
        "terseDslImplementation": list(
            _weather_builtin_assets_for_components((direct_weather,))
        ),
    }


@scenario("internal_contracts__log_summaries")
def _build_log_summaries() -> dict[str, Any]:
    messages = [
        {"role": "system", "content": "system-contract"},
        {"role": "user", "content": "private-dynamic-contract"},
    ]
    prompt_summary = _prompt_size_summary(messages)
    task_spec = TaskSpec(
        userQuery="不应进入日志的用户原始请求",
        size="2x2",
        dataModelSchema={"privateDomain": {"secretField": "secretValue"}},
        eventCandidates=[],
        assetCandidates=[],
    )
    task_summary = _task_spec_log_summary(task_spec)
    prompt_text = json.dumps(prompt_summary, ensure_ascii=False)
    task_text = json.dumps(task_summary, ensure_ascii=False)
    return {
        "promptSizeSummary": prompt_summary,
        "promptSummaryLeaksContent": "private-dynamic-contract" in prompt_text,
        "taskSpecSummary": task_summary,
        "taskSpecSummaryLeaksQuery": "用户原始请求" in task_text,
        "taskSpecSummaryLeaksSchema": (
            "secretField" in task_text or "secretValue" in task_text
        ),
    }


@scenario("internal_contracts__cardtpl_rejections")
def _build_cardtpl_rejections() -> dict[str, Any]:
    legacy_variant_source = """#Template("Legacy@1", {"capability": "LegacyCapability"})
#Variant("2x2", {})
Column("section")
#EndVariant
#EndTemplate
"""
    unknown_theme_source = """#Template InvalidThemeReference@1(props: {})
data = {
}
Column({"backgroundColor": $theme('unknownColor')})
#End
"""
    invalid_optional_action_source = """#Template InvalidOptionalAction@1(props: { actionId: string })
data = {
}

Stack({
  "onClick": EventAction(props?.actionId)
}, Text("动作", "body"))
#End
"""

    def compile_case(
        source: str,
        wire_id: str,
        provider_id: str,
        description: str,
        sizes: tuple[str, ...] = (),
    ) -> Any:
        return lambda: _compile_source(
            source,
            wire_id=wire_id,
            provider_id=provider_id,
            description=description,
            supported_card_sizes=sizes,
        )

    return {
        "deprecated_variant_syntax": _error_outcome(
            compile_case(
                legacy_variant_source,
                "Legacy@1",
                "example.provider",
                "legacy syntax must be rejected",
                ("2x2",),
            )
        ),
        "unknown_theme_reference": _error_outcome(
            compile_case(
                unknown_theme_source,
                "InvalidThemeReference@1",
                "example.theme",
                "invalid theme reference",
            )
        ),
        "child_slot_duplicate_index": _error_outcome(
            compile_case(
                "#Template HeroActionLayout@1(props: {}, ...children)\ndata = {\n}\n\n"
                "Column(children[0], children[0])\n#End\n",
                "HeroActionLayout@1",
                "example.layout",
                "invalid indexed child slots",
            )
        ),
        "child_slot_non_contiguous_indexes": _error_outcome(
            compile_case(
                "#Template HeroActionLayout@1(props: {}, ...children)\ndata = {\n}\n\n"
                "Column(children[1])\n#End\n",
                "HeroActionLayout@1",
                "example.layout",
                "invalid indexed child slots",
            )
        ),
        "child_slot_mixed_spread_and_indexed": _error_outcome(
            compile_case(
                "#Template HeroActionLayout@1(props: {}, ...children)\ndata = {\n}\n\n"
                "Column(children, children[0])\n#End\n",
                "HeroActionLayout@1",
                "example.layout",
                "invalid indexed child slots",
            )
        ),
        "event_action_literal_event_value": _error_outcome(
            compile_case(
                '#Template InvalidAction@1(props: { actionId: string })\ndata = {\n}\n\n'
                'Stack({\n  "onClick": EventAction("event.open.weather")\n}, '
                'Text("动作", "body"))\n#End\n',
                "InvalidAction@1",
                "example.action",
                "invalid EventAction",
            )
        ),
        "event_action_outside_onclick_option": _error_outcome(
            compile_case(
                '#Template InvalidAction@1(props: { actionId: string })\ndata = {\n}\n\n'
                'Stack({\n  "width": EventAction(props.actionId)\n}, '
                'Text("动作", "body"))\n#End\n',
                "InvalidAction@1",
                "example.action",
                "invalid EventAction",
            )
        ),
        "event_action_required_prop": _error_outcome(
            compile_case(
                invalid_optional_action_source,
                "InvalidOptionalAction@1",
                "example.action",
                "invalid optional EventAction",
            )
        ),
        "parser_three_argument_template": _error_outcome(
            lambda: parse_hybrid_card(
                'Template("card@1",{},Column("section",'
                'Template("Legacy@1","2x2",{})));'
            )
        ),
    }


@scenario("internal_contracts__theme_resolution")
def _build_theme_resolution() -> dict[str, Any]:
    definition = _compile_source(
        _THEME_REFERENCE_SOURCE,
        wire_id="ThemeReference@1",
        provider_id="example.theme",
        description="theme references",
    )
    values = {
        "primaryColor": "#FFCCDDFF",
        "supportContentColor": "#99CCDDFF",
        "progressColor": "#FF445566",
        "actionStyle.backgroundColor": "#33FFFFFF",
        "actionStyle.contentColor": "#FFCCDDFF",
    }
    root = _instantiate_blueprint(
        definition.variants[0].root,
        {},
        theme_values=values,
    )
    return {
        "rootBackgroundColor": root.values[-1]["backgroundColor"],
        "primaryTextFontColor": root.children[0].values[-1]["fontColor"],
        "supportTextFontColor": root.children[1].values[-1]["fontColor"],
        "progressColor": root.children[2].values[-1]["color"],
    }


@scenario("internal_contracts__indexed_child_slots")
def _build_indexed_child_slots() -> dict[str, Any]:
    definition = _compile_source(
        _HERO_ACTION_LAYOUT_SOURCE,
        wire_id="HeroActionLayout@1",
        provider_id="example.layout",
        description="indexed child slots",
    )
    root = definition.variants[0].root
    hero = Nested2Node("Text", ("hero",), ())
    action = Nested2Node("Text", ("action",), ())
    instantiated = _instantiate_blueprint(root, {}, spread_children=(hero, action))
    return {
        "rootComponent": root.component,
        "rootItemMargin": root.values[0].properties["itemMargin"].value,
        "childSlotComponents": [
            child.children[0].component for child in root.children
        ],
        "instantiatedSlotChildren": [
            [
                {"component": node.component_type, "values": list(node.values)}
                for node in instantiated.children[index].children
            ]
            for index in (0, 1)
        ],
        "missingSecondChildError": _error_outcome(
            lambda: _instantiate_blueprint(root, {}, spread_children=(hero,))
        ),
    }


def _layout_child_slot_indexes(root: TemplateNode) -> list[int]:
    slot_indexes: list[int] = []
    pending = [root]
    while pending:
        node = pending.pop()
        if node.component == TEMPLATE_CHILD_SLOT_COMPONENT:
            slot_index = node.values[0].value
            assert isinstance(slot_index, int)
            slot_indexes.append(slot_index)
        pending.extend(reversed(node.children))
    return slot_indexes


_LAYOUT_BLUEPRINT_IDS = (
    "HeroActionLayout@1",
    "FullIconActionLayout@1",
    "CompactTwoActionLayout@1",
    "HeroTitleContentActionLayout@1",
    "TwoSupportLayout@1",
    "SingleFocusLayout@1",
    "WideSingleFocusLayout@1",
)


@scenario("internal_contracts__layout_blueprints")
def _build_layout_blueprints() -> dict[str, Any]:
    registry = get_cardplan_registry()
    payload: dict[str, Any] = {}
    for template_id in _LAYOUT_BLUEPRINT_IDS:
        root = registry.require_template(template_id).variants[0].root
        options = root.values[0].properties
        payload[template_id] = {
            "root": root.component,
            "width": options["width"].value,
            "height": options["height"].value,
            "slotIndexes": _layout_child_slot_indexes(root),
            "spreadChildren": root.spread_children,
        }
    return payload


@scenario("internal_contracts__hero_title_content_layout")
def _build_hero_title_content_layout() -> dict[str, Any]:
    root = get_cardplan_registry().require_template(
        "HeroTitleContentActionLayout@1"
    ).variants[0].root
    content_region, action_region = root.children
    content_options = content_region.values[0].properties
    return {
        "contentRegion": {
            "itemMargin": content_options["itemMargin"].value,
            "layoutWeight": content_options["layoutWeight"].value,
            "businessRegionCount": len(content_region.children),
            "businessRegions": [
                {
                    "width": business.values[0].properties["width"].value,
                    "justifyContent": business.values[0].properties[
                        "justifyContent"
                    ].value,
                    "alignItems": business.values[0].properties["alignItems"].value,
                    "hasHeight": "height" in business.values[0].properties,
                    "hasLayoutWeight": "layoutWeight" in business.values[0].properties,
                }
                for business in content_region.children
            ],
        },
        "actionRegionHeight": action_region.values[0].properties["height"].value,
    }


@scenario("internal_contracts__fusion_theme_compact_rules")
def _build_fusion_theme_compact_rules() -> dict[str, Any]:
    registry = get_cardplan_registry(enable_fusion_ball=True)
    compact_business_ids: set[str] = set()
    for template_id, definition in registry.templates.items():
        if not template_id.endswith("Compact@1"):
            continue
        if not registry.template_is_enabled(template_id):
            continue
        if definition.business_id is not None:
            compact_business_ids.add(definition.business_id)
    payload: dict[str, Any] = {}
    for theme_id, theme in registry.themes.items():
        fusion_style = theme.fusion_ball_style
        if fusion_style is None:
            continue
        compact_businesses = sorted(
            compact_business_ids.intersection(fusion_style.business_ids)
        )
        if not compact_businesses:
            continue
        payload[theme_id] = {
            "compactBusinesses": compact_businesses,
            "firstLayerRule": registry.theme_first_layer_rules.get(theme_id),
        }
    return payload


@scenario("internal_contracts__action_template_props")
def _build_action_template_props() -> dict[str, Any]:
    registry = get_cardplan_registry()
    payload: dict[str, Any] = {}
    for template_id in ("PillAction@1", "IconAction@1"):
        definition = registry.require_template(template_id)
        variant = definition.variants[0]
        schema = variant.parameters_schema
        properties = schema.get("properties") or {}
        root = variant.root
        options = root.values[-1].properties
        event = options.get("onClick")
        payload[template_id] = {
            "providerId": definition.provider_id,
            "required": schema.get("required"),
            "properties": sorted(properties),
            "root": root.component,
            "onClick": None
            if event is None
            else {
                "kind": event.kind,
                "parameterKind": event.items[0].kind,
                "parameterName": event.items[0].name,
            },
            "hasInternalActionIdOption": "_actionId" in options,
        }
    support = registry.require_template("WeatherOverviewTemperatureSupport@1")
    variant = support.variants[0]
    schema = variant.parameters_schema
    action_options = variant.root.values[0].properties
    payload["WeatherOverviewTemperatureSupport@1"] = {
        "actionIdType": schema["properties"]["actionId"]["type"],
        "actionIdRequired": "actionId" in schema["required"],
        "onClick": {
            "kind": action_options["onClick"].kind,
            "parameterKind": action_options["onClick"].items[0].kind,
            "parameterName": action_options["onClick"].items[0].name,
        },
    }
    return payload


_OPTIONAL_ACTION_CASES: tuple[tuple[str, dict[str, object]], ...] = (
    ("with_action_id", {"actionId": "event.open.weather"}),
    ("without_action_id", {}),
    ("null_action_id", {"actionId": None}),
)


@scenario("internal_contracts__optional_event_action")
def _build_optional_event_action() -> dict[str, Any]:
    definition = _compile_source(
        _OPTIONAL_ACTION_SOURCE,
        wire_id="OptionalAction@1",
        provider_id="example.action",
        description="optional EventAction",
    )
    blueprint = definition.variants[0].root
    action_value = blueprint.values[0].properties["onClick"]
    payload: dict[str, Any] = {
        "blueprint": {
            "onClickKind": action_value.kind,
            "parameterKind": action_value.items[0].kind,
        }
    }
    for key, params in _OPTIONAL_ACTION_CASES:
        root = _instantiate_blueprint(blueprint, params)
        payload[key] = root.values[0].get("onClick")
    return payload


@scenario("internal_contracts__layout_action_combinations")
def _build_layout_action_combinations() -> dict[str, Any]:
    span = SourceSpan(start=0, end=1)

    def template(template_id: str) -> ParsedCall:
        return ParsedCall("template", template_id, ({},), (), span)

    def action(template_id: str, action_id: str) -> ParsedCall:
        return ParsedCall(
            "template", template_id, ({"actionId": action_id},), (), span
        )

    pill_one = action("PillAction@1", "event.one")
    pill_two = action("PillAction@1", "event.two")
    icon = action("IconAction@1", "event.icon")

    cases: dict[str, tuple[Any, ...]] = {
        "compact_two_action_two_pills": (
            "CompactTwoActionLayout",
            (template("WeatherOverviewCompact@1"),),
            (pill_one, pill_two),
            "2x2",
        ),
        "two_support_two_supports": (
            "TwoSupportLayout",
            (
                template("WeatherOverviewTemperatureSupport@1"),
                template("ResourceUsageOverviewSupport@1"),
            ),
            (),
            "2x2",
        ),
        "hero_title_content_title_content_one_pill": (
            "HeroTitleContentActionLayout",
            (
                template("WeatherOverviewHeroTitle@1"),
                template("ScheduleOverviewHeroContent@1"),
            ),
            (pill_one,),
            "2x2",
        ),
        "hero_action_hero_one_pill": (
            "HeroActionLayout",
            (template("BatteryOverviewHero@1"),),
            (pill_one,),
            "2x2",
        ),
        "single_focus_full_no_action": (
            "SingleFocusLayout",
            (template("WeatherOverviewFull@1"),),
            (),
            "2x2",
        ),
        "full_icon_action_full_icon": (
            "FullIconActionLayout",
            (template("WeatherOverviewFull@1"),),
            (icon,),
            "2x2",
        ),
        "wide_single_focus_wide_hero_one_pill": (
            "WideSingleFocusLayout",
            (template("ActivityOverviewWideHero@1"),),
            (pill_one,),
            "2x4",
        ),
        "wide_single_focus_wide_full_no_action": (
            "WideSingleFocusLayout",
            (template("BatteryOverviewWideFull@1"),),
            (),
            "2x4",
        ),
        "hero_title_content_reversed_order": (
            "HeroTitleContentActionLayout",
            (
                template("ScheduleOverviewHeroContent@1"),
                template("WeatherOverviewHeroTitle@1"),
            ),
            (pill_one,),
            "2x2",
        ),
        "two_support_two_compacts": (
            "TwoSupportLayout",
            (
                template("WeatherOverviewCompact@1"),
                template("BatteryOverviewCompact@1"),
            ),
            (),
            "2x2",
        ),
        "hero_action_without_action": (
            "HeroActionLayout",
            (template("BatteryOverviewHero@1"),),
            (),
            "2x2",
        ),
        "single_focus_with_icon_action": (
            "SingleFocusLayout",
            (template("WeatherOverviewFull@1"),),
            (icon,),
            "2x2",
        ),
        "single_focus_with_wide_template": (
            "SingleFocusLayout",
            (template("BatteryOverviewWideFull@1"),),
            (),
            "2x4",
        ),
        "wide_single_focus_non_wide_template": (
            "WideSingleFocusLayout",
            (template("BatteryOverviewFull@1"),),
            (),
            "2x4",
        ),
        "single_focus_with_action_requires_hero": (
            "SingleFocusLayout",
            (template("BatteryOverviewHero@1"),),
            (pill_one,),
            "2x2",
        ),
    }
    return {
        key: _error_outcome(
            lambda case_args=case_args: (
                _validate_provider_template_layout_action_requirements(*case_args)
            )
        )
        for key, case_args in cases.items()
    }


@scenario("internal_contracts__dual_business_layout_selection")
def _build_dual_business_layout_selection() -> dict[str, Any]:
    registry = get_cardplan_registry()
    task_spec = TaskSpec(
        userQuery="显示天气和日程，并提供查看入口",
        size="2x2",
        eventCandidates=[
            EventAction(
                id="event.open.details",
                description="查看详情",
                call="clickToDeeplink",
                args={"uri": "example://details"},
            )
        ],
        dataModelSchema={"data": {}},
    )
    scope = AdvancedScopeBrief(
        themeId="family-weather-care-blue",
        advancedComponentIds=("WeatherOverview", "CalendarOverview"),
    )

    selection = _second_layer_layout_selection(scope, task_spec, registry)
    candidates = {
        "WeatherOverview": (
            "WeatherOverviewHeroTitle@1",
            "WeatherOverviewHero@1",
        ),
        "CalendarOverview": (
            "ScheduleOverviewHeroContent@1",
            "ScheduleOverviewNextEventHero@1",
        ),
    }
    filtered, groups = _filter_positional_second_layer_template_candidates(
        candidates,
        (
            ("WeatherOverviewHeroTitle@1", "WeatherOverviewHero@1"),
            (
                "ScheduleOverviewHeroContent@1",
                "ScheduleOverviewNextEventHero@1",
            ),
        ),
        selection.business_layout_kinds_by_position,
    )
    option = _layout_output_option(
        "HeroTitleContentActionLayout@1",
        groups,
        ({"actionId": "action-0", "label": "查看详情"},),
        ("PillAction@1",),
    )
    return {
        "layoutIds": list(selection.layout_ids),
        "businessLayoutKindsByPosition": list(
            selection.business_layout_kinds_by_position
        ),
        "filteredCandidates": {
            component_id: list(template_ids)
            for component_id, template_ids in filtered.items()
        },
        "outputOption": {
            "root": option["root"],
            "layoutKind": option["layoutKind"],
            "businessTemplateIdsByPosition": [
                list(group) for group in option["businessTemplateIdsByPosition"]
            ],
            "actionChildren": option["actionChildren"],
        },
    }


@scenario("internal_contracts__model_json_extraction")
def _build_model_json_extraction() -> dict[str, Any]:
    return {
        "outer_object_with_braces_inside_value": _parse_json_object(
            '说明：{"decision":"use {trusted}"}。'
        ),
    }


def test_provider_cardtpl_sources_use_inline_styles_without_design_tokens() -> None:
    """注册表全量结构 pin：布局容器与媒体/文本组件不得携带设计令牌字符串。"""
    registry = get_cardplan_registry()

    def assert_inline_only(node: TemplateNode) -> None:
        component = node.component
        values = node.values
        if component in {"Column", "Row", "List", "Stack"}:
            has_design_token = (
                bool(values)
                and values[0].kind == "literal"
                and isinstance(values[0].value, str)
            )
            assert not has_design_token, component
        if component in {"Text", "Image", "Button"}:
            has_design_token = (
                len(values) > 1
                and values[1].kind == "literal"
                and isinstance(values[1].value, str)
            )
            assert not has_design_token, component
        for child in node.children:
            assert_inline_only(child)

    for definition in registry.templates.values():
        for variant in definition.variants:
            assert_inline_only(variant.root)
