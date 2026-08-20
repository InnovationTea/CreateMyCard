"""模板内部商用契约的回归测试。"""

from __future__ import annotations

import pytest

from models.generation import TaskSpec
from services.template_generation.engine.cardplan.parser import parse_hybrid_card
from services.template_generation.engine.cardplan.provider_bundle import compile_card_template
from services.template_generation.engine.pipeline import _task_spec_log_summary
from services.template_generation.engine.terse_dsl_nested2_converter import (
    TerseDslNested2ConversionError,
)
from services.template_generation.model_client import _parse_json_object


def test_provider_compiler_rejects_deprecated_variant_syntax() -> None:
    legacy_source = """#Template(\"Legacy@1\", {\"capability\": \"LegacyCapability\"})
#Variant(\"2x2\", {})
Column(\"section\")
#EndVariant
#EndTemplate
"""

    with pytest.raises(ValueError, match="must use the cardtpl/1 UI syntax"):
        compile_card_template(
            legacy_source,
            provider_id="example.provider",
            business_id="Legacy",
            expected_wire_id="Legacy@1",
            expected_capability_id="LegacyCapability",
            data_domain="/data/legacy",
            description="legacy syntax must be rejected",
            supported_card_sizes=("2x2",),
            required_data=(),
            optional_data=(),
            output_schema={"type": "object", "properties": {}},
            bundle_digest="sha256:test",
        )


def test_parser_rejects_deprecated_three_argument_template_call() -> None:
    source = (
        'Template("card@1",{},Column("section",'
        'Template("Legacy@1","2x2",{})));'
    )

    with pytest.raises(
        TerseDslNested2ConversionError,
        match="requires a versioned ID, one props object and optional children",
    ):
        parse_hybrid_card(source)


def test_task_spec_log_summary_omits_user_content_and_schema_details() -> None:
    task_spec = TaskSpec(
        userQuery="不应进入日志的用户原始请求",
        size="2x2",
        dataModelSchema={"privateDomain": {"secretField": "secretValue"}},
        eventCandidates=[],
        assetCandidates=[],
    )

    summary = _task_spec_log_summary(task_spec)

    assert summary == {
        "size": "2x2",
        "dataModelRootKeys": ["privateDomain"],
        "eventCandidateCount": 0,
        "assetCandidateCount": 0,
    }
    assert "用户原始请求" not in repr(summary)
    assert "secretField" not in repr(summary)
    assert "secretValue" not in repr(summary)


def test_model_response_json_extraction_uses_complete_outer_object() -> None:
    assert _parse_json_object('说明：{"decision":"use {trusted}"}。') == {
        "decision": "use {trusted}"
    }
