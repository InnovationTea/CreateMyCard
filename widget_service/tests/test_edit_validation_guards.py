"""二次编辑结构、动态样式和非法字段值反例；兼顾正常重排及创建隔离。"""

import ast
import inspect
import json

import pytest

from core.errors import ErrorCode, GenerationStatus
from services.card_validation import (
    ValidationOptions,
    validate_card,
)
from services.card_validation.edit_validation import structure as edit_structure_validator
from services.card_validation.edit_validation import styles as edit_style_validator
from services.card_validation.edit_validation.artifact import validate_edit_artifact
from services.single_step_edit import source_digest
from services.widget_edit_contract import (
    apply_edit_output,
    dump_rows,
    edit_contract,
    validate_edit_source_structure,
    validate_intent,
)
from services.widget_generation_service import WidgetGenerationService
from test_semantic_widget_edit import (
    _intent,
    _nodes,
    _patch,
    _request,
    _rows,
)
from test_semantic_widget_edit import (
    edit_run as edit_run,
)
from test_semantic_widget_edit import (
    source as source,
)


def _grouped(source_text):
    rows = _rows(source_text)
    nodes = _nodes(rows)
    root = nodes[0]
    root["children"] = ["panel"]
    nodes.append({"id": "panel", "component": "Column", "children": ["title", "value"]})
    return rows


def _output(source_text, rows, mode, prop="shadow", value=None):
    if mode == "patch":
        payload = _patch(source_text, prop=prop, value=value)
    else:
        payload = {"sourceDigest": source_digest(source_text), "genui": rows}
    return json.dumps(payload, ensure_ascii=False)


@pytest.mark.parametrize(
    "mutation",
    [
        "container",
        "leaf",
        "multiple_parents",
        "cycle",
        "missing",
        "orphan",
    ],
)
def test_layout_rejects_invalid_mount_graph(source, mutation):
    rows = _grouped(source)
    original = dump_rows(rows)
    nodes = _nodes(rows)
    root, panel = nodes[0], nodes[-1]
    if mutation == "container":
        root["children"] = ["panel", "panel"]
    elif mutation == "leaf":
        panel["children"] = ["title", "value", "title"]
    elif mutation == "multiple_parents":
        root["children"] = ["panel", "second"]
        nodes.append({"id": "second", "component": "Column", "children": ["title"]})
    elif mutation == "cycle":
        panel["children"] = ["root"]
    elif mutation == "missing":
        panel["children"] = ["absent"]
    else:
        nodes.append({"id": "orphan", "component": "Column", "children": ["panel"]})
    intent = _intent(mode="layout", targets=["root"], dimensions=["layout"])
    with pytest.raises(ValueError):
        apply_edit_output(original, _output(original, rows, "layout"), intent)


def test_layout_allows_wrapper_and_reparenting(source):
    rows = _grouped(source)
    intent = _intent(mode="layout", targets=["root"], dimensions=["layout"])
    result = apply_edit_output(source, _output(source, rows, "layout"), intent)
    validate_edit_source_structure(result)
    assert "panel" in result


def test_existing_orphan_is_retained_but_visible_content_cannot_be_detached(source):
    rows = _rows(source)
    nodes = _nodes(rows)
    nodes.append({"id": "old_orphan", "component": "Column", "children": ["old_child"]})
    nodes.append({"id": "old_child", "component": "Text", "content": "历史孤立内容"})
    original = dump_rows(rows)
    nodes[0]["component"] = "Row"
    intent = _intent(mode="layout", targets=["root"], dimensions=["layout"])
    apply_edit_output(original, _output(original, rows, "layout"), intent)
    nodes[0]["children"] = ["title"]
    with pytest.raises(ValueError, match="不可达"):
        apply_edit_output(original, _output(original, rows, "layout"), intent)


def test_dynamic_list_template_is_one_structural_edge(source):
    rows = _rows(source)
    nodes = _nodes(rows)
    nodes[0]["children"] = ["list", "value"]
    template = {"componentId": "title", "path": "/items", "itemVar": "item"}
    nodes.append({"id": "list", "component": "List", "children": template})
    original = dump_rows(rows)
    validate_edit_source_structure(original)
    intent = _intent(dimensions=["typography"])
    result = apply_edit_output(original, json.dumps(_patch(original)), intent)
    assert _nodes(_rows(result))[-1].get("children") == template


@pytest.mark.parametrize("mode", ["patch", "layout"])
@pytest.mark.parametrize("operation", ["replace", "remove", "move", "add", "binding"])
def test_dynamic_style_cannot_change_without_declared_goal(source, mode, operation):
    rows = _rows(source)
    styles = _nodes(rows)[1].get("styles")
    assert isinstance(styles, dict)
    dynamic = "{{ ${/accent} }}"
    if operation != "add":
        styles["shadow"] = {"radius": 4, "color": dynamic}
    if operation == "binding":
        styles["shadow"] = {"radius": 4, "color": {"path": "/accent"}}
    original = dump_rows(rows)
    if operation == "replace" or operation == "binding":
        value = {"radius": 8, "color": "#FF111111"}
    elif operation == "remove":
        value = {"radius": 8}
    elif operation == "move":
        value = {"radius": dynamic, "color": "#FF111111"}
    else:
        value = {"radius": 4, "color": dynamic}
    styles["shadow"] = value
    dimensions = ["shape"] if mode == "patch" else ["layout", "shape"]
    intent = _intent(mode=mode, dimensions=dimensions)
    assert not intent.expectations
    with pytest.raises(ValueError, match="动态样式"):
        apply_edit_output(original, _output(original, rows, mode, value=value), intent)


@pytest.mark.parametrize("mode", ["patch", "layout"])
@pytest.mark.parametrize("dynamic", ["{{ ${/accent} }}", {"path": "/accent"}])
def test_dynamic_sibling_is_preserved_during_static_object_edit(source, mode, dynamic):
    rows = _rows(source)
    styles = _nodes(rows)[1].get("styles")
    assert isinstance(styles, dict)
    styles["shadow"] = {"radius": 4, "color": dynamic}
    original = dump_rows(rows)
    value = {"radius": 8, "color": dynamic}
    styles["shadow"] = value
    dimensions = ["shape"] if mode == "patch" else ["layout", "shape"]
    intent = _intent(
        mode=mode,
        dimensions=dimensions,
        expectations=[
            {
                "componentId": "title",
                "property": "styles.shadow",
                "operator": "equal",
                "value": value,
            }
        ],
    )
    validate_intent(intent, original, "2x4", None)
    result = apply_edit_output(original, _output(original, rows, mode, value=value), intent)
    assert _nodes(_rows(result))[1].get("styles", {}).get("shadow") == value


@pytest.mark.parametrize("mode", ["patch", "layout"])
@pytest.mark.parametrize(
    "prop,value",
    [
        ("shadow", "0 0 8px red"),
        ("shadow", {"radius": -1}),
        ("shadow", {"color": "#FF000000"}),
        ("shadow", {"radius": 1, "fill": 1}),
        ("shadow", {"radius": 1, "type": "bad"}),
        ("shadow", {"radius": 1, "color": "red"}),
        ("shadow", {"radius": 1, "extra": 1}),
        ("shadow", {"radius": float("inf")}),
        ("constraintSize", "invalid"),
        ("constraintSize", {"maxHeight": 20}),
        ("constraintSize", {"minWidth": 10, "maxWidth": "9vp", "minHeight": 0, "maxHeight": 20}),
        ("constraintSize", {"minWidth": -1, "maxWidth": 9, "minHeight": 0, "maxHeight": 20}),
        ("clip", "false"),
        ("clip", 1),
        ("padding", -1),
        ("padding", {"top": -1}),
        ("padding", {"typo": 1}),
        ("padding", [1, 2]),
        ("margin", {"left": float("nan")}),
        ("borderRadius", {"top": 1}),
        ("borderRadius", {"topLeft": -1}),
        ("flexShrink", 2),
        ("aspectRatio", 0),
        ("maxLines", 1.5),
        ("textAlign", True),
        ("linearGradient", {"colors": [["#FF000000", 0], ["#FFFFFFFF", 1]], "repeating": 1}),
    ],
)
def test_changed_style_values_obey_edit_contract(source, mode, prop, value):
    rows = _rows(source)
    styles = _nodes(rows)[1].get("styles")
    assert isinstance(styles, dict)
    styles[prop] = value
    intent = _intent(mode=mode, dimensions=["layout", "shape", "spacing", "typography", "palette"])
    with pytest.raises(ValueError):
        apply_edit_output(source, _output(source, rows, mode, prop, value), intent)


@pytest.mark.parametrize(
    "prop,value",
    [
        ("shadow", "outerDefaultSM"),
        (
            "shadow",
            {"radius": 4, "offsetX": -2, "color": "#66000000", "fill": True, "type": "blur"},
        ),
        ("clip", False),
        ("padding", {"top": 0, "left": 8}),
        ("margin", 0),
        ("borderRadius", {"topLeft": 2, "bottomRight": 4}),
        (
            "constraintSize",
            {"minWidth": "2vp", "maxWidth": 10, "minHeight": "1fp", "maxHeight": "2fp"},
        ),
        ("constraintSize", {"minWidth": "90%", "maxWidth": "2vp", "minHeight": 0, "maxHeight": 10}),
    ],
)
def test_legal_values_and_noncomparable_units_remain_supported(source, prop, value):
    intent = _intent(dimensions=["shape", "spacing", "layout"])
    result = apply_edit_output(source, json.dumps(_patch(source, prop=prop, value=value)), intent)
    assert _nodes(_rows(result))[1].get("styles", {}).get(prop) == value


def test_unchanged_legacy_style_does_not_require_cleanup(source):
    rows = _rows(source)
    styles = _nodes(rows)[1].get("styles")
    assert isinstance(styles, dict)
    styles["shadow"] = "legacy-compatible-value"
    original = dump_rows(rows)
    result = apply_edit_output(original, json.dumps(_patch(original)), _intent())
    assert _nodes(_rows(result))[1].get("styles", {}).get("shadow") == "legacy-compatible-value"


def test_value_rule_coverage_matches_editable_styles():
    contract = edit_contract()
    value_rules = contract.get("editableStyleValueRules", {})
    properties = value_rules.get("properties", {})
    for dimensions in contract.get("editableStylesByComponent", {}).values():
        for fields in dimensions.values():
            assert set(fields) <= set(properties)


@pytest.mark.parametrize("mode", ["patch", "layout"])
def test_removing_whole_dynamic_style_is_rejected(source, mode):
    rows = _rows(source)
    styles = _nodes(rows)[1].get("styles")
    assert isinstance(styles, dict)
    styles["fontColor"] = "{{ ${/accent} }}"
    original = dump_rows(rows)
    styles.pop("fontColor")
    intent = _intent(mode=mode, dimensions=["layout", "palette"])
    if mode == "patch":
        payload = {
            "sourceDigest": source_digest(original),
            "changes": [
                {
                    "componentId": "title",
                    "property": "styles.fontColor",
                    "operation": "remove",
                    "before": {"exists": True, "value": "{{ ${/accent} }}"},
                }
            ],
        }
        output = json.dumps(payload)
    else:
        output = _output(original, rows, mode)
    with pytest.raises(ValueError, match="动态样式"):
        apply_edit_output(original, output, intent)


def test_background_removal_cannot_bypass_dynamic_style_protection(source):
    rows = _rows(source)
    nodes = _nodes(rows)
    nodes[0]["children"] = ["background", "title", "value"]
    nodes.append(
        {
            "id": "background",
            "component": "Image",
            "src": "/registered.png",
            "styles": {
                "width": "matchParent",
                "height": "matchParent",
                "fillColor": {"call": "existingColor", "args": {}},
            },
        }
    )
    original = dump_rows(rows)
    nodes.pop()
    nodes[0]["children"] = ["title", "value"]
    intent = _intent(
        mode="layout",
        targets=["root"],
        dimensions=["layout", "palette"],
        backgroundTargets=["background"],
    )
    with pytest.raises(ValueError, match="动态样式"):
        apply_edit_output(original, _output(original, rows, "layout"), intent)


def test_preserved_dynamic_gradient_leaf_does_not_block_static_angle_edit(source):
    rows = _rows(source)
    styles = _nodes(rows)[1].get("styles")
    assert isinstance(styles, dict)
    original_gradient = {
        "angle": 90,
        "colors": [
            ["#FF000000", "{{ ${/offset} }}"],
            ["#FFFFFFFF", 1],
        ],
    }
    styles["linearGradient"] = original_gradient
    original = dump_rows(rows)
    value = {**original_gradient, "angle": 180}
    intent = _intent(dimensions=["palette"])
    result = apply_edit_output(
        original,
        json.dumps(_patch(original, prop="linearGradient", value=value)),
        intent,
    )
    assert _nodes(_rows(result))[1].get("styles", {}).get("linearGradient") == value


def test_edit_contract_copy_cannot_change_validation_rules():
    first = edit_contract()
    value_rules = first.get("editableStyleValueRules")
    assert isinstance(value_rules, dict)
    value_rules.clear()
    assert edit_contract().get("editableStyleValueRules")


def test_dynamic_schema_extension_does_not_modify_global_jsonschema_validator():
    from jsonschema import Draft202012Validator

    validator = Draft202012Validator({"type": "number"})
    assert not validator.is_valid("{{ ${/value} }}")


@pytest.mark.asyncio
async def test_invalid_source_structure_stops_before_model(edit_run):
    rows = _rows(edit_run.source.genui)
    _nodes(rows)[0]["children"] = ["title", "title", "value"]
    edit_run.source.genui = dump_rows(rows)
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert response.errorCode == ErrorCode.SOURCE_ARTIFACT_INVALID.value
    assert not edit_run.calls and not edit_run.saved


@pytest.mark.asyncio
async def test_invalid_value_repairs_against_original_and_saves_only_valid_result(edit_run):
    original = edit_run.source.genui
    edit_run.intent = _intent(dimensions=["shape"])
    edit_run.outputs = [
        json.dumps(_patch(original, prop="shadow", value="0 0 8px red")),
        json.dumps(_patch(original, prop="shadow", value={"radius": 4})),
    ]
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert response.status == GenerationStatus.SUCCESS
    assert len(edit_run.saved) == 1
    assert len(edit_run.calls) == 3
    assert _nodes(_rows(edit_run.source.genui)) == _nodes(_rows(original))
    saved_styles = _nodes(_rows(edit_run.saved[0].genui))[1].get("styles", {})
    assert saved_styles.get("shadow") == {"radius": 4}


@pytest.mark.asyncio
async def test_invalid_layout_exhaustion_never_saves_or_switches_to_creation(edit_run):
    original = edit_run.source.genui
    rows = _rows(original)
    _nodes(rows)[0]["children"] = ["title", "title", "value"]
    edit_run.intent = _intent(mode="layout", targets=["root"], dimensions=["layout"])
    edit_run.outputs = [_output(original, rows, "layout")]
    response = await WidgetGenerationService().generate_widget_card_compact_dsl(_request())
    assert response.errorCode == ErrorCode.WIDGET_EDIT_INVALID.value
    assert len(edit_run.calls) == 4
    assert not edit_run.saved


def test_final_edit_validation_cannot_bypass_dynamic_guard(edit_run):
    original = edit_run.source.model_copy(deep=True)
    rows = _rows(original.genui)
    styles = _nodes(rows)[1].get("styles")
    assert isinstance(styles, dict)
    styles["fontColor"] = "{{ ${/accent} }}"
    original.genui = dump_rows(rows)
    candidate = original.model_copy(deep=True)
    styles["fontColor"] = "#FF333333"
    candidate.genui = dump_rows(rows)
    result = validate_edit_artifact(original, candidate, _intent(dimensions=["palette"]))
    assert any("动态样式" in message for message in result.errors)


def test_static_shadow_edit_with_dynamic_color_passes_full_artifact_validation(edit_run):
    original = edit_run.source.model_copy(deep=True)
    rows = _rows(original.genui)
    data = rows[2].get("updateDataModel", {}).get("value")
    assert isinstance(data, dict)
    data["accent"] = "#FF111111"
    styles = _nodes(rows)[1].get("styles")
    assert isinstance(styles, dict)
    styles["shadow"] = {"radius": 4, "color": "{{ ${/accent} }}"}
    original.genui = dump_rows(rows)
    candidate = original.model_copy(deep=True)
    intent = _intent(dimensions=["shape"])
    candidate.genui = apply_edit_output(
        original.genui,
        json.dumps(
            _patch(
                original.genui,
                prop="shadow",
                value={"radius": 8, "color": "{{ ${/accent} }}"},
            )
        ),
        intent,
    )
    result = validate_edit_artifact(original, candidate, intent)
    assert not result.errors


@pytest.mark.parametrize("mutation", ["structure", "style"])
def test_final_artifact_validation_rechecks_structure_and_value_guards(edit_run, mutation):
    original = edit_run.source
    candidate = original.model_copy(deep=True)
    rows = _rows(candidate.genui)
    if mutation == "structure":
        _nodes(rows)[0]["children"] = ["title", "title", "value"]
    else:
        styles = _nodes(rows)[1].get("styles")
        assert isinstance(styles, dict)
        styles["clip"] = "invalid"
    candidate.genui = dump_rows(rows)
    intent = _intent(mode="layout", targets=["root"], dimensions=["layout", "shape"])
    result = validate_edit_artifact(original, candidate, intent)
    assert result.errors


def test_creation_validation_never_calls_edit_guards(source, monkeypatch):
    expected = validate_card(dsl_text=source).render_json()

    def forbidden(*_args, **_kwargs):
        pytest.fail("首次生成不得执行编辑专项校验")

    monkeypatch.setattr(edit_structure_validator, "validate_edit_structure", forbidden)
    monkeypatch.setattr(edit_style_validator, "validate_edit_style_value", forbidden)
    monkeypatch.setattr(edit_style_validator, "preserve_dynamic_styles", forbidden)
    actual = validate_card(dsl_text=source, options=ValidationOptions(edit_mode=False))
    assert actual.render_json() == expected


def test_new_guards_follow_codecheck_control_and_comprehension_rules():
    for module in (edit_structure_validator, edit_style_validator):
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While)):
                count = 1
                for expression in ast.walk(node.test):
                    if isinstance(expression, ast.BoolOp):
                        count += len(expression.values) - 1
                assert count <= 3, (module.__name__, node.lineno)
            if isinstance(node, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
                assert len(node.generators) == 1
                assert len(node.generators[0].ifs) <= 1
