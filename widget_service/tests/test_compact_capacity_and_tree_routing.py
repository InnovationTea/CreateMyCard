"""组件能力、实际槽宽与结构修复责任的交叉边界回归。"""

import pytest

import services.compact_component_runtime as component_runtime
import services.compact_composition_context as composition_context
from config.config import get_settings
from models.generation import TaskSpec
from services.compact_component_runtime import text_block_width_contract
from services.compact_composition_context import compact_text_block_capacity_context
from services.compact_composition_planner import _text_block
from services.compact_repair_strategy import CompactRepairStrategyTracker
from services.prompt_builder import PromptBuilder


@pytest.mark.parametrize(
    "width, capacity",
    [(0.0, 0), (135.0, 0), (136.0, 2), (207.0, 2), (208.0, 3),
     (276.0, 3), (279.9, 3), (280.0, 4), (500.0, 4)],
)
def test_text_block_capacity_depends_on_available_width(width: float, capacity: int) -> None:
    contract = text_block_width_contract()
    assert contract.capacity_for_width(width) == capacity
    assert contract.maximum_items == 4


@pytest.mark.parametrize("count", [2, 3, 4])
def test_planner_uses_same_recipe_minimum_width(count: int) -> None:
    items = []
    for index in range(count):
        items.append({"index": index, "sample": "1", "object": "test", "fieldContract": {}})
    group = _text_block("2x4", items)
    assert group.get("minimumWidth") == text_block_width_contract().required_width(count)
    assert group.get("factIndexes") == list(range(count))


@pytest.mark.parametrize("runtime_context", [False, True])
def test_plan_and_generation_always_receive_slot_capacity(
    monkeypatch, runtime_context: bool,
) -> None:
    monkeypatch.setattr(
        get_settings(), "enable_design_compact_runtime_prompt_context", runtime_context
    )
    task = TaskSpec(size="2x4", userQuery="显示设备状态", dataModelSchema={"data": {}})
    builder = PromptBuilder()
    prompt = builder.build_design_compact(task, "创建合同")
    system = prompt[0].get("content")
    assert isinstance(system, str)
    assert "4项至少280vp" in system
    assert "实际槽宽为276vp" in system
    assert "280vp，最多容纳4项" in system
    plan_prompt = builder.build_compact_plan(task, system, prompt[1].get("content", ""))
    plan_system = plan_prompt[0].get("content")
    assert isinstance(plan_system, str)
    assert plan_system.count("# TextBlock 槽位容量合同") == 1
    assert compact_text_block_capacity_context("2x2") == ""


@pytest.mark.parametrize(
    "message",
    [
        "Component rows must form one tree rooted at root. Unreachable component(s): detail.",
        "component item has multiple parents: left and right.",
        "component panel.children references value more than once.",
        "The root component is missing; model output may be truncated.",
        "cyclic component reference",
        "missing component reference",
        "语义布局不符合合同：节点 body：引用了不存在的组件。",
    ],
)
def test_tree_failures_recompose_parent_before_capacity(message: str) -> None:
    errors = [
        {"code": "COMPACT_DSL_VALIDATION_FAILED", "message": message},
        {"code": "COMPACT_DSL_VALIDATION_FAILED", "message": "overflows by 4vp"},
    ]
    tracker = CompactRepairStrategyTracker()
    first = tracker.next_directive("initial", errors)
    assert first.category == "layout_structure"
    assert first.scope == "parent_layout"
    assert first.repair_strategy == "parent_layout_recompose"
    assert "不接受该角色的 Region" in first.instruction
    assert "不通过删除孤立业务节点" in first.instruction
    second = tracker.next_directive("changed", errors)
    assert second.scope == "full_dsl"
    assert second.repair_strategy == "plan_guided_recompose"


@pytest.mark.parametrize(
    "code",
    ["COMPACT_COMPONENT_DUPLICATE_CHILD", "COMPACT_COMPONENT_MULTIPLE_PARENTS",
     "COMPACT_COMPONENT_EMPTY_CONTAINER"],
)
@pytest.mark.parametrize("nested", [False, True])
def test_structured_tree_codes_do_not_depend_on_english_message(code: str, nested: bool) -> None:
    issue = {"code": code, "message": "组件结构异常"}
    if nested:
        issue = {
            "code": "COMPACT_DSL_VALIDATION_FAILED", "message": "组件结构异常",
            "compactDiagnostics": [{"code": code}],
        }
    directive = CompactRepairStrategyTracker().next_directive("source", [issue])
    assert directive.category == "layout_structure"
    assert directive.scope == "parent_layout"


@pytest.mark.parametrize(
    "code, message, category",
    [
        (
            "COMPACT_DSL_VALIDATION_FAILED",
            "component value: unsupported prop",
            "component_contract",
        ),
        ("COMPACT_DSL_VALIDATION_FAILED", "component root: overflows by 4vp", "layout_capacity"),
        ("COMPACT_PLAN_COVERAGE_FAILED", "Plan fact is missing from visible DSL", "plan_coverage"),
        ("COMPACT_PLAN_COVERAGE_FAILED", "Plan fact is displayed more than once", "plan_coverage"),
    ],
)
def test_non_tree_failures_keep_existing_route(code: str, message: str, category: str) -> None:
    directive = CompactRepairStrategyTracker().next_directive(
        "source", [{"code": code, "message": message}]
    )
    assert directive.category == category


def test_recipe_changes_reach_capacity_planner_and_prompt(monkeypatch) -> None:
    payload = component_runtime.load_visual_recipe_contract()
    components = payload.get("components")
    assert isinstance(components, dict)
    recipe = components.get("TextBlock")
    assert isinstance(recipe, dict)
    parts = recipe.get("parts")
    assert isinstance(parts, dict)
    item = parts.get("item")
    root = parts.get("root")
    assert isinstance(item, dict)
    assert isinstance(root, dict)
    item_styles = item.get("styles")
    root_styles = root.get("styles")
    assert isinstance(item_styles, dict)
    assert isinstance(root_styles, dict)
    constraints = item_styles.get("constraintSize")
    assert isinstance(constraints, dict)
    metrics = recipe.get("metrics")
    assert isinstance(metrics, dict)
    metrics["minimumItemWidth"] = 80
    root_styles["itemMargin"] = 12
    monkeypatch.setattr(component_runtime, "_load_contract", lambda: payload)
    contract = text_block_width_contract()
    assert contract.required_width(4) == 356.0
    items = []
    for index in range(4):
        items.append({"index": index, "sample": "1", "object": "test", "fieldContract": {}})
    group = _text_block("2x4", items)
    assert group.get("minimumWidth") == 356.0
    assert "4项至少356vp" in compact_text_block_capacity_context("2x4")


@pytest.mark.parametrize(
    "extra_width, available, capacity", [(0.0, 280, 4), (4.0, 280, 4)]
)
def test_capacity_follows_reference_canvas_without_global_three_item_limit(
    monkeypatch, extra_width: float, available: int, capacity: int,
) -> None:
    original = composition_context.reference_dimension

    def reference(size: str, axis: str) -> float:
        value = original(size, axis)
        return value + extra_width if axis == "width" else value

    monkeypatch.setattr(composition_context, "reference_dimension", reference)
    context = compact_text_block_capacity_context("2x4")
    assert f"{available}vp，最多容纳{capacity}项" in context
