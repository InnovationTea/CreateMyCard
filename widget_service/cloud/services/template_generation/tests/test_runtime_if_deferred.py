"""运行时 IF 暂缓后，各入口拒绝组件，既有 Expr 仍通过公共处理链。"""

from __future__ import annotations

import json
from typing import Any

import pytest

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
    TerselConversionError,
    convert_tersel_to_a2ui,
)
from services.template_generation.source_adapter import (
    TemplateSourceAdapterError,
    prepare_template_source_dsl,
)


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


@pytest.mark.parametrize("body", (
    "IF(data.eventCont, Text('true'), Text('false'))",
    "IF(data.eventCont, Text('true'))",
    "IF(Expr(data.eventCont > 0), Text('true'), Text('false'))",
    "IF(data.eventCont, IF(data.eventCont, Text('true')), Text('false'))",
    "If(data.eventCont, Text('true'), Text('false'))",
    "\n#if data.eventCont\nIF(data.eventCont, Text('true'))\n#endif\n",
))
def test_provider_rejects_deferred_runtime_if(body: str) -> None:
    with pytest.raises(ValueError, match="unsupported Provider Template component: (IF|If)"):
        _definition(body)


@pytest.mark.parametrize("component", ("If", "IF"))
def test_tersel_rejects_deferred_runtime_if(component: str) -> None:
    source = f'Column({component}("{{{{ true }}}}",Text("true"),Text("false")))'
    with pytest.raises(TerselConversionError, match="Unsupported component type"):
        convert_tersel_to_a2ui(
            source, size="2x2", protocol_profile=A2UIProtocolRegistry().get_profile(),
        )


def _compact_with_if(component: str) -> str:
    return "\n".join([
        '["root","Column",{},["if"]]',
        json.dumps(["if", component, {
            "condition": "{{ ${/data/calendar/eventCount} > 0 }}", "childrenIf": ["text"],
        }]),
        '["text","Text",{"content":"true"}]',
        '["/data/calendar/eventCount",0]',
    ])


@pytest.mark.parametrize("component", ("If", "IF"))
def test_template_compact_rejects_deferred_runtime_if(component: str) -> None:
    with pytest.raises(TemplateCompactError, match="unsupported component type"):
        convert_template_compact(
            _compact_with_if(component), size="2x2",
            protocol_profile=A2UIProtocolRegistry().get_profile(),
        )


@pytest.mark.parametrize("component", ("If", "IF"))
def test_public_compact_pipeline_rejects_deferred_runtime_if(component: str) -> None:
    source = _compact_with_if(component)
    context = DslProcessingContext(
        size="2x2", card_spec={"dataBindings": []}, task_spec=_task(),
        protocol_profile=A2UIProtocolRegistry().get_profile(),
    )
    # 公共转换器保持基线职责：数据契约合法，但最终 A2UI 校验拒绝未知组件。
    validate_compact_dsl(source, task_spec=context.task_spec, card_spec=context.card_spec)
    result = get_dsl_processor(DslProcessorKind.DESIGN_COMPACT).process(source, context)
    assert not result.errors
    report = validate_card(dsl_text=result.standard_dsl)
    assert any(item.code == "DSL_COMPONENT_UNKNOWN" for item in report.diagnostics)


def test_public_a2ui_validator_rejects_deferred_runtime_if() -> None:
    report = validate_card(dsl_text=_a2ui_with_if())
    assert any(item.code == "DSL_COMPONENT_UNKNOWN" for item in report.diagnostics)


def test_template_archive_rejects_deferred_runtime_if() -> None:
    with pytest.raises(TemplateCompactError, match="unsupported A2UI component type"):
        convert_a2ui_to_compact_dsl(_a2ui_with_if(), size="2x2")


def test_template_source_adapter_rejects_deferred_runtime_if() -> None:
    with pytest.raises(TemplateSourceAdapterError, match="cannot be converted"):
        prepare_template_source_dsl(
            _a2ui_with_if(),
            processor_kind=DslProcessorKind.DESIGN_COMPACT,
            size="2x2",
            protocol_profile=A2UIProtocolRegistry().get_profile(),
        )


@pytest.mark.parametrize("sample", (0, 1, None, ""))
def test_runtime_expression_still_passes_public_processor(sample: Any) -> None:
    definition = _definition('Text(Expr(data.eventCont > 0 ? "有日程" : "暂无日程"))')
    root = _instantiate_blueprint(
        definition.variants[0].root, {}, {"eventCont": "${data.calendar.eventCount}"},
    )
    profile = A2UIProtocolRegistry().get_profile()
    a2ui = convert_tersel_to_a2ui(
        _serialize_node(root), size="2x2", protocol_profile=profile, task_spec=_task(sample),
    )
    source = prepare_template_source_dsl(
        a2ui, processor_kind=DslProcessorKind.DESIGN_COMPACT, size="2x2", protocol_profile=profile,
    )
    context = DslProcessingContext(
        size="2x2",
        card_spec={"title": "日程", "description": "日程状态", "suggestSize": "2x2"},
        task_spec=_task(sample), protocol_profile=profile, design_profile_id="design-compact-dsl",
    )
    result = get_dsl_processor(DslProcessorKind.DESIGN_COMPACT).process(source, context)
    assert not result.errors
    assert "{{ ${/data/calendar/eventCount} > 0 ? '有日程' : '暂无日程' }}" in result.standard_dsl
    report = validate_card(dsl_text=result.standard_dsl, cardspec=context.card_spec)
    assert not [item for item in report.diagnostics if item.severity == "error"]
