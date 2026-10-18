"""按生产入口处理模板 Compact DSL 的共用测试断言。"""

from typing import Any

from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext


def assert_template_compact_processing(
    compact_dsl: str, *, task_spec: dict[str, Any], card_spec: dict[str, Any],
) -> None:
    size = card_spec.get("suggestSize")
    if not isinstance(size, str):
        raise AssertionError("card_spec.suggestSize must be a string")
    result = DesignCompactProcessor().process(
        compact_dsl,
        DslProcessingContext(
            size=size, task_spec=task_spec, card_spec=card_spec,
            protocol_profile={"version": "v0.9"}, skip_compact_dsl_validation=True,
        ),
    )
    if result.errors:
        raise AssertionError(result.errors)
    if not result.standard_dsl:
        raise AssertionError("Compact processing must produce standard DSL")
