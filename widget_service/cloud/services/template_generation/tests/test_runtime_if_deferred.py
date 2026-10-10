"""运行时 IF 暂缓后各入口的拒绝产物（已场景金样化，Layer C）。

原先 8 个独立用例全部转为场景金样：Provider 模板、Tersel 转换、模板侧
Compact 转换、归档逆向转换与模板源适配器对 ``IF/If`` 的报错类型与文案、
公共 Compact 管道与 A2UI 校验器的诊断码、既有 Expr 仍通过公共处理链的
完整 standard DSL（按 4 种示例值参数化），均由
``tests/goldens/scenarios/`` 下的快照整体冻结。入口或校验规则改动后按
golden 工作流 ``check --diff`` / ``bless --declared`` 复核；本文件不再
保留独立测试函数，pytest 仅通过导入完成场景注册。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from services.card_validation import validate_card, validate_compact_dsl
from services.generation_pipeline import (
    DslProcessingContext,
    DslProcessorKind,
    get_dsl_processor,
)
from services.protocol_registry import A2UIProtocolRegistry
from services.template_generation.engine.cardplan.compiler import (
    _instantiate_blueprint,
    _serialize_node,
)
from services.template_generation.engine.cardplan.models import TemplateDefinition
from services.template_generation.engine.cardplan.provider_bundle import compile_card_template
from services.template_generation.engine.compact_dsl_a2ui_converter import (
    CompactDslConversionError as TemplateCompactError,
)
from services.template_generation.engine.compact_dsl_a2ui_converter import (
    convert_a2ui_to_compact_dsl,
)
from services.template_generation.engine.compact_dsl_a2ui_converter import (
    convert_compact_dsl_to_a2ui as convert_template_compact,
)
from services.template_generation.engine.tersel_converter import (
    convert_tersel_to_a2ui,
)
from services.template_generation.source_adapter import (
    prepare_template_source_dsl,
)
from services.template_generation.test_support.golden_scenarios import scenario


def _definition(body: str) -> TemplateDefinition:
    source = (
        "#Template CalendarConditionFull@1(props: {})\n"
        'data = { eventCont: $path("/eventCount") }\n'
        f"Column({body})\n#End\n"
    )
    return compile_card_template(
        source,
        provider_id="example.calendar",
        business_id="CalendarCondition",
        expected_wire_id="CalendarConditionFull@1",
        expected_capability_id="GetCalendarEvents",
        data_domain="/data/calendar",
        description="日程条件表达式",
        supported_card_sizes=("2x2",),
        primary_data=("/eventCount",),
        secondary_data=(),
        optional_data=(),
        output_schema={"type": "object", "properties": {"eventCount": {"type": "integer"}}},
    )


def _task(sample: Any = 0) -> dict[str, Any]:
    return {
        "userQuery": "日程状态",
        "appVersion": "11.7.5.206",
        "size": "2x2",
        "eventCandidates": [],
        "assetCandidates": [],
        "dataModelSchema": {
            "data": {"calendar": {"eventCount": {"type": "integer", "sampleValue": sample}}},
        },
    }


def _a2ui_with_if() -> str:
    a2ui = convert_tersel_to_a2ui(
        'Column(Text("有日程"),Text("暂无日程"))',
        size="2x2",
        protocol_profile=A2UIProtocolRegistry().get_profile(),
        task_spec=_task(),
    )
    rows = [json.loads(line) for line in a2ui.splitlines()]
    update = rows[1].get("updateComponents")
    assert isinstance(update, dict)
    components = update.get("components")
    assert isinstance(components, list)
    root = components[0]
    assert root.get("id") == "root"
    root["children"] = ["if"]
    components.insert(1, {
        "id": "if",
        "component": "If",
        "condition": "{{ ${/data/calendar/eventCount} > 0 }}",
        "childrenIf": ["root_0"],
        "childrenElse": ["root_1"],
    })
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def _compact_with_if(component: str) -> str:
    return "\n".join([
        '["root","Column",{},["if"]]',
        json.dumps(["if", component, {
            "condition": "{{ ${/data/calendar/eventCount} > 0 }}", "childrenIf": ["text"],
        }]),
        '["text","Text",{"content":"true"}]',
        '["/data/calendar/eventCount",0]',
    ])


def _error(build: Callable[[], Any]) -> dict[str, str]:
    """执行构建并冻结错误类型与报错文案；未抛错时返回哨兵。"""
    try:
        build()
    except Exception as exc:  # noqa: BLE001 - 错误本身就是被冻结的产物
        return {"errorType": type(exc).__name__, "message": str(exc)}
    return {"error": "NO_ERROR"}


_PROVIDER_IF_BODIES: tuple[tuple[str, str], ...] = (
    ("ternary", "IF(data.eventCont, Text('true'), Text('false'))"),
    ("no_else", "IF(data.eventCont, Text('true'))"),
    ("expr_condition", "IF(Expr(data.eventCont > 0), Text('true'), Text('false'))"),
    ("nested", "IF(data.eventCont, IF(data.eventCont, Text('true')), Text('false'))"),
    ("camelcase", "If(data.eventCont, Text('true'), Text('false'))"),
    ("directive", "\n#if data.eventCont\nIF(data.eventCont, Text('true'))\n#endif\n"),
)


@scenario("runtime_if__entry_errors")
def _build_entry_errors() -> dict[str, Any]:
    profile = A2UIProtocolRegistry().get_profile()
    entries: dict[str, Any] = {}
    for key, body in _PROVIDER_IF_BODIES:
        entries[f"provider:{key}"] = _error(lambda body=body: _definition(body))
    for component in ("If", "IF"):
        entries[f"tersel:{component}"] = _error(
            lambda component=component: convert_tersel_to_a2ui(
                f'Column({component}("{{{{ true }}}}",Text("true"),Text("false")))',
                size="2x2", protocol_profile=profile,
            )
        )
        entries[f"compact:{component}"] = _error(
            lambda component=component: convert_template_compact(
                _compact_with_if(component), size="2x2", protocol_profile=profile,
            )
        )
    entries["archive"] = _error(
        lambda: convert_a2ui_to_compact_dsl(_a2ui_with_if(), size="2x2")
    )
    entries["source_adapter"] = _error(lambda: prepare_template_source_dsl(
        _a2ui_with_if(),
        processor_kind=DslProcessorKind.DESIGN_COMPACT,
        size="2x2",
        protocol_profile=profile,
    ))
    return entries


def _public_pipeline_outcome(component: str) -> dict[str, Any]:
    source = _compact_with_if(component)
    context = DslProcessingContext(
        size="2x2", card_spec={"dataBindings": []}, task_spec=_task(),
        protocol_profile=A2UIProtocolRegistry().get_profile(),
    )
    # 上游已把 If 移出 compact DSL 契约（childrenIf 链接不再可达）：
    # 公共校验直接抛 CompactDslValidationError，处理器则把同一拒绝原因
    # 记入 QualityIssue issues 后返回空 DSL。
    compact_error = _error(lambda: validate_compact_dsl(
        source, task_spec=context.task_spec, card_spec=context.card_spec,
    ))
    result = get_dsl_processor(DslProcessorKind.DESIGN_COMPACT).process(source, context)
    card_report = validate_card(dsl_text=result.standard_dsl)
    return {
        "compactDslOutcome": compact_error,
        # 上游 DslProcessingResult.errors 已从字符串升级为 QualityIssue；
        # 用 to_prompt_payload() 固化稳定结构。
        "processorErrors": [
            issue.to_prompt_payload() for issue in result.errors
        ],
        "cardCodes": sorted({item.code for item in card_report.diagnostics}),
    }


@scenario("runtime_if__public_pipeline_outcomes")
def _build_public_pipeline_outcomes() -> dict[str, Any]:
    payload: dict[str, Any] = {
        f"compact:{component}": _public_pipeline_outcome(component)
        for component in ("If", "IF")
    }
    report = validate_card(dsl_text=_a2ui_with_if())
    payload["a2ui_validator"] = {
        "codes": sorted({item.code for item in report.diagnostics}),
    }
    return payload


_EXPR_SAMPLES: tuple[tuple[str, Any], ...] = (
    ("zero", 0), ("one", 1), ("none", None), ("empty_string", ""),
)


@scenario("runtime_if__expr_still_passes")
def _build_expr_still_passes() -> dict[str, Any]:
    definition = _definition('Text(Expr(data.eventCont > 0 ? "有日程" : "暂无日程"))')
    root = _instantiate_blueprint(
        definition.variants[0].root, {}, {"eventCont": "${data.calendar.eventCount}"},
    )
    profile = A2UIProtocolRegistry().get_profile()
    payload: dict[str, Any] = {}
    for key, sample in _EXPR_SAMPLES:
        a2ui = convert_tersel_to_a2ui(
            _serialize_node(root), size="2x2", protocol_profile=profile,
            task_spec=_task(sample),
        )
        source = prepare_template_source_dsl(
            a2ui, processor_kind=DslProcessorKind.DESIGN_COMPACT,
            size="2x2", protocol_profile=profile,
        )
        context = DslProcessingContext(
            size="2x2",
            card_spec={"title": "日程", "description": "日程状态", "suggestSize": "2x2"},
            task_spec=_task(sample), protocol_profile=profile,
            design_profile_id="design-compact-dsl",
        )
        result = get_dsl_processor(DslProcessorKind.DESIGN_COMPACT).process(source, context)
        report = validate_card(dsl_text=result.standard_dsl, cardspec=context.card_spec)
        payload[key] = {
            "standardDsl": result.standard_dsl,
            "processorErrors": [
                issue.to_prompt_payload() for issue in result.errors
            ],
            "errorCodes": sorted({
                item.code for item in report.diagnostics if item.severity == "error"
            }),
        }
    return payload
