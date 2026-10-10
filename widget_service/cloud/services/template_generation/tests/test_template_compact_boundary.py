"""模板回转可使用内部组件，模型输入不可借模板标记绕过白名单。"""

import json

import pytest

from services.card_validation.compact_dsl_validator import (
    CompactDslValidationError,
    validate_compact_dsl,
)
from services.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    convert_compact_dsl_to_a2ui,
    repair_compact_dsl_binding_paths,
)


def _source(component_type: str, props: dict) -> str:
    rows = [
        ["root", "Stack", {}, ["template_root"]],
        ["template_root", "Column", {}, ["item"]],
        ["item", component_type, props],
    ]
    return "\n".join(json.dumps(row) for row in rows)


@pytest.mark.parametrize(("component_type", "props"), [
    ("Image", {"src": "resources/base/media/drop_1.svg", "fillColor": "#FF123456"}),
    ("Progress", {"value": 68, "total": 100, "type": "ring", "width": 36, "height": 36}),
    ("Divider", {"strokeWidth": 1, "color": "#FF123456"}),
    ("Button", {"label": "查看", "onClick": [{"call": "openDetails", "args": {}}]}),
])
def test_internal_components_require_explicit_trusted_conversion(
    component_type: str, props: dict,
) -> None:
    source = _source(component_type, props)
    with pytest.raises(CompactDslConversionError, match="unsupported component type"):
        convert_compact_dsl_to_a2ui(source, size="2x2")
    repaired = repair_compact_dsl_binding_paths(
        source, task_spec={}, card_spec={}, allow_internal_components=True,
    )
    output = convert_compact_dsl_to_a2ui(
        repaired, size="2x2", allow_internal_components=True,
    )
    update = json.loads(output.splitlines()[1]).get("updateComponents")
    assert isinstance(update, dict)
    components = update.get("components")
    assert isinstance(components, list)
    item = next(component for component in components if component.get("id") == "item")
    assert item.get("component") == component_type
    with pytest.raises(CompactDslValidationError, match="cannot be generated directly"):
        validate_compact_dsl(
            source, task_spec={"size": "2x2"}, card_spec={},
            allow_internal_components=True, enforce_model_component_types=True,
        )


def test_trusted_conversion_still_rejects_unregistered_components() -> None:
    with pytest.raises(CompactDslConversionError, match="unsupported component type"):
        convert_compact_dsl_to_a2ui(
            _source("UnknownComponent", {}), size="2x2", allow_internal_components=True,
        )
