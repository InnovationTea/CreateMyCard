"""按生产入口处理模板 Compact DSL 的共用测试断言。"""

from typing import Any

from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext


def assert_template_compact_processing(
    compact_dsl: str, *, task_spec: dict[str, Any], card_spec: dict[str, Any],
) -> None:
    size = card_spec.get("suggestSize")
    assert isinstance(size, str)
    result = DesignCompactProcessor().process(
        compact_dsl,
        DslProcessingContext(
            size=size, task_spec=task_spec, card_spec=card_spec,
            protocol_profile={"version": "v0.9"}, skip_compact_dsl_validation=True,
        ),
    )
    assert not result.errors, result.errors
    assert result.standard_dsl
