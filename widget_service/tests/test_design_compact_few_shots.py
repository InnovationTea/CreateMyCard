"""将正式 Few-shot 作为真实生成输入，防止示例与转换协议漂移。"""

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from config.config import get_settings
from services.card_validation import validate_compact_dsl
from services.card_validation.contrast_validator import _composite, _contrast, _rgba
from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.compact_prompt_loader import assemble_prompts
from services.prompt_builder import PromptBuilder
from services.protocol_registry import A2UIProtocolRegistry

PROMPT_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source"
)
PROMPTS = assemble_prompts(PROMPT_SOURCE)
HIGH_LEVEL_COMPONENTS = {
    "CardButton",
    "SingleLineTitle",
    "CircleButton",
    "DataDisplay",
    "DoubleLineTitle",
    "Badge",
    "EmphasizedData",
    "EmphasisText",
    "SecondaryBody",
    "EventCard",
    "H_BarChart",
    "InfoBlock",
    "NumericRatioStack",
    "PillButton",
    "ProgressCircle",
    "ProgressCircleSingle",
    "ProgressLine2",
    "SummaryList",
    "TableText",
    "TextBlock",
    "TopTextBottomValue",
}
BASE_COMPONENTS = {
    "Button",
    "Column",
    "Divider",
    "Image",
    "List",
    "Progress",
    "Row",
    "Stack",
    "Text",
}


def _examples() -> list[tuple[str, dict, str]]:
    examples = []
    for size in ("2x2", "2x4"):
        document = PROMPTS[f"fewshot_{size}"]
        for section in re.split(r"(?m)^## ", document)[1:]:
            identifier = re.search(rf"({size}-V\d\d)", section)
            task_match = re.search(r"```json\s*\n(.*?)\n```", section, re.S)
            source_match = re.search(r"```genui\s*\n(.*?)\n```", section, re.S)
            assert identifier is not None, section.splitlines()[0]
            assert task_match is not None, section.splitlines()[0]
            assert source_match is not None, section.splitlines()[0]
            examples.append(
                (
                    identifier.group(1),
                    json.loads(task_match.group(1)),
                    source_match.group(1),
                )
            )
    return examples


EXAMPLES = _examples()


def _example(identifier: str) -> tuple[dict, str]:
    _, task, source = next(item for item in EXAMPLES if item[0] == identifier)
    return task, source


def _rows(source: str) -> list[list]:
    return [json.loads(line) for line in source.splitlines()]


def _component_types(source: str) -> list[str]:
    return [row[1] for row in _rows(source) if len(row) >= 3]


def _is_ring_external_readout(component_id: str, rows: list[list]) -> bool:
    rows_by_id = {}
    for row in rows:
        if len(row) >= 3 and isinstance(row[0], str):
            rows_by_id[row[0]] = row

    for parent in rows:
        if len(parent) < 4 or parent[1] != "Column":
            continue
        children = parent[3]
        if not isinstance(children, list) or component_id not in children:
            continue
        for sibling_id in children:
            sibling = rows_by_id.get(sibling_id)
            if not sibling or len(sibling) < 4 or sibling[1] != "Stack":
                continue
            stack_children = sibling[3]
            if not isinstance(stack_children, list):
                continue
            for child_id in stack_children:
                child = rows_by_id.get(child_id)
                if child and len(child) >= 3 and child[1] == "Progress":
                    return child[2].get("type") == "ring"
    return False


@pytest.mark.parametrize("identifier,task,source", EXAMPLES, ids=[item[0] for item in EXAMPLES])
def test_few_shot_validates_and_converts(
    identifier: str,
    task: dict,
    source: str,
    monkeypatch,
) -> None:
    """检查动态路径、事件、布局门禁和高阶组件展开，而非只检查 JSON。"""
    settings = SimpleNamespace(CONFIG={"fusion_ball_min_prd_version": "1.0"})
    monkeypatch.setattr("services.fusion_ball_expander.get_settings", lambda: settings)
    size = task.get("size")
    assert size in {"2x2", "2x4"}, identifier

    result = validate_compact_dsl(
        source,
        task_spec=task,
        card_spec={"suggestSize": size},
    )
    assert not result.warnings, identifier

    converted = convert_compact_dsl_to_a2ui(
        source,
        size=size,
        protocol_profile={"version": "v0.9", "appVersion": "99.0"},
    )
    messages = [json.loads(line) for line in converted.splitlines()]
    assert len(messages) == 3, identifier
    operations = ("createSurface", "updateComponents", "updateDataModel")
    for message, operation in zip(messages, operations, strict=True):
        assert operation in message, identifier

    components = messages[1]["updateComponents"]["components"]
    assert all(component["component"] in BASE_COMPONENTS for component in components)


def test_example_ids_are_contiguous_and_unique() -> None:
    expected = [f"2x2-V{index:02d}" for index in range(33)]
    expected.extend(f"2x4-V{index:02d}" for index in range(27))
    assert [item[0] for item in EXAMPLES] == expected


def test_two_by_two_examples_cover_every_declared_layout() -> None:
    document = PROMPTS["fewshot_2x2"]
    expected = {
        "S-center",
        "S-title-content",
        "S-title-dual-content",
        "S-quad-content",
        "S-title-content-action",
        "S-title-primary-secondary-action",
        "S-title-dual-column-action",
        "S-title-anchor",
        "S-content-dual-action",
        "S-dual-info",
    }

    actual = set(re.findall(r"`(S-[a-z-]+)`", document))

    assert actual == expected


@pytest.mark.parametrize("identifier,task,source", EXAMPLES, ids=[item[0] for item in EXAMPLES])
def test_few_shot_has_readable_nonempty_content(
    identifier: str,
    task: dict,
    source: str,
) -> None:
    del task
    rows = _rows(source)
    for row in rows:
        if len(row) < 3:
            continue
        component_id, component, props, *children = row
        assert "textOverflow" not in props, identifier
        if component == "Text":
            assert props.get("content") != "", identifier
            assert props.get("content") != " ", identifier
            font_size = props.get("fontSize", 12)
            if font_size < 12:
                assert _is_ring_external_readout(component_id, rows), identifier
                assert font_size == 10, identifier
                assert props.get("fontWeight") == 500, identifier
                assert props.get("height") == 14, identifier
                assert props.get("textAlign") == "center", identifier
                assert props.get("maxLines") == 1, identifier
        if component in {"Row", "Column", "Stack"}:
            assert children and children[0], identifier


@pytest.mark.parametrize("identifier,task,source", EXAMPLES, ids=[item[0] for item in EXAMPLES])
def test_examples_use_only_declared_actions_and_assets(
    identifier: str,
    task: dict,
    source: str,
) -> None:
    expected_actions = {
        json.dumps(action, ensure_ascii=False, sort_keys=True)
        for action in task.get("eventCandidates", [])
    }
    expected_assets = {
        candidate["src"]
        for candidate in task.get("assetCandidates", [])
        if isinstance(candidate.get("src"), str)
    }
    actual_actions: list[str] = []
    actual_assets: set[str] = set()
    for row in _rows(source):
        if len(row) < 3:
            continue
        props = row[2]
        for action in props.get("onClick", []):
            actual_actions.append(json.dumps(action, ensure_ascii=False, sort_keys=True))
        for key in ("src", "icon"):
            value = props.get(key)
            if isinstance(value, str) and value.startswith("resources/"):
                actual_assets.add(value)

    assert len(actual_actions) == len(set(actual_actions)), identifier
    assert set(actual_actions).issubset(expected_actions), identifier
    assert actual_assets.issubset(expected_assets), identifier


@pytest.mark.parametrize(
    ("identifier", "required"),
    (
        ("2x2-V06", {"EventCard", "PillButton"}),
        ("2x2-V14", {"SingleLineTitle", "TableText"}),
        ("2x2-V15", {"SingleLineTitle", "CircleButton"}),
        ("2x2-V16", {"DataDisplay"}),
        ("2x2-V18", {"SingleLineTitle", "EmphasizedData", "PillButton"}),
        ("2x2-V20", {"InfoBlock"}),
        ("2x2-V21", {"ProgressCircle", "PillButton"}),
        ("2x2-V31", {"ProgressCircle", "PillButton"}),
        ("2x4-V01", {"SingleLineTitle", "SummaryList"}),
        ("2x4-V02", {"ProgressCircleSingle"}),
        ("2x4-V03", {"ProgressLine2", "TextBlock"}),
        ("2x4-V05", {"SingleLineTitle", "TopTextBottomValue"}),
        ("2x4-V18", {"InfoBlock", "CardButton"}),
        ("2x4-V20", {"ProgressCircle", "InfoBlock", "CardButton"}),
        ("2x4-V21", {"H_BarChart"}),
    ),
)
def test_examples_use_available_high_level_components(
    identifier: str,
    required: set[str],
) -> None:
    _, source = _example(identifier)
    assert required.issubset(set(_component_types(source)))


@pytest.mark.parametrize(
    "identifier,task,source",
    EXAMPLES,
    ids=[item[0] for item in EXAMPLES],
)
def test_examples_use_only_supported_component_types(
    identifier: str,
    task: dict,
    source: str,
) -> None:
    del task
    types = set(_component_types(source))
    assert "Progress" not in types, identifier
    assert types.issubset(BASE_COMPONENTS | HIGH_LEVEL_COMPONENTS), identifier


@pytest.mark.parametrize(
    "identifier,task,source",
    EXAMPLES,
    ids=[item[0] for item in EXAMPLES],
)
def test_example_reaches_its_generation_route(
    identifier: str,
    task: dict,
    source: str,
) -> None:
    del source
    task_spec = SimpleNamespace(**task)
    route, selected = PromptBuilder._visual_route(task_spec)
    assert route in {
        "battery-readout",
        "calendar-event",
        "countdown",
        "earphone-status",
        "focus-aux",
        "generic",
        "health-readout",
        "multi-business",
        "weather-readout",
    }
    assert selected
    available_ids = {item[0] for item in EXAMPLES}
    assert set(selected).issubset(available_ids)
    layout_scope = PromptBuilder._layout_scope(task_spec)

    document = PROMPTS[f"fewshot_{task['size']}"]
    selected_document = PromptBuilder._select_few_shot(document, task_spec)
    for selected_id in selected:
        assert selected_id in selected_document
    for other_id, _, _ in EXAMPLES:
        if other_id.startswith(task["size"]) and other_id not in selected:
            assert other_id not in selected_document

    assembled = PromptBuilder._with_size_few_shot(PROMPTS["create"], task_spec)
    for selected_id in selected:
        assert selected_id in assembled
    if "adaptive" not in layout_scope:
        assert f"### `{layout_scope}`" in assembled


def test_few_shot_switch_skips_document_loading(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "enable_design_compact_few_shots", False)

    def reject_few_shot_read(*_args, **_kwargs) -> str:
        raise AssertionError("Few-shot 文档不应在开关关闭时读取")

    monkeypatch.setattr(
        A2UIProtocolRegistry,
        "read_design_few_shot",
        reject_few_shot_read,
    )
    task_spec = SimpleNamespace(**EXAMPLES[0][1])

    assembled = PromptBuilder._with_size_few_shot(PROMPTS["create"], task_spec)

    assert "本轮实现参考" not in assembled
    assert "# 本轮组件与布局选择" in assembled
    assert "基础布局组件和组件" in assembled
    for deprecated in ("基础组件", "高阶组件", "高级组件", "普通组件", "基础组合"):
        assert deprecated not in assembled


def _palette_rows() -> list[list[str]]:
    palettes = []
    for line in PROMPTS["create"].splitlines():
        if not line.startswith("|"):
            continue
        colors = re.findall(r"#[A-F0-9]{8}", line)
        if len(colors) == 6:
            palettes.append(colors)
    assert palettes
    return palettes


@pytest.mark.parametrize("colors", _palette_rows())
def test_palette_preserves_text_hierarchy(colors: list[str]) -> None:
    start, end, primary, secondary, button, _ = colors
    start_rgb = _rgba(start)[:3]
    end_rgb = _rgba(end)[:3]
    for step in range(11):
        fraction = step / 10.0
        background = tuple(
            left + (right - left) * fraction
            for left, right in zip(start_rgb, end_rgb, strict=True)
        )
        backboard = _composite(background, _rgba("#CCFFFFFF"))
        for surface in (background, backboard):
            assert _contrast(primary, surface) > _contrast(secondary, surface)
            button_surface = _composite(surface, _rgba(button))
            assert _contrast(primary, button_surface) > 1.0


@pytest.mark.parametrize("identifier,task,source", EXAMPLES, ids=[item[0] for item in EXAMPLES])
def test_example_gradients_use_registered_direction_and_stops(
    identifier: str,
    task: dict,
    source: str,
) -> None:
    del task
    allowed = []
    for start, end, _ in (
        ("#FFCBDDFE", "#FFF1F6FE", "1F4799"),
        ("#FFDBCCFF", "#FFF6F2FF", "563D99"),
        ("#FFFFE0CC", "#FFFFF7F2", "8C4B1C"),
    ):
        allowed.append([[start, 0], [end, 1]])
    for row in _rows(source):
        if len(row) < 3:
            continue
        gradient = row[2].get("linearGradient")
        if gradient is None:
            continue
        assert gradient.get("direction") == "RightBottom", identifier
        assert gradient.get("colors") in allowed, identifier
        assert "angle" not in gradient, identifier


def test_component_catalog_excludes_removed_legacy_components() -> None:
    catalog = PROMPTS["create"]
    allowed_section = catalog.split("# 2. Compact DSL 组件合同", maxsplit=1)[1]
    allowed_section = allowed_section.split("## 2.1", maxsplit=1)[0]
    for component_type in HIGH_LEVEL_COMPONENTS:
        assert f"`{component_type}`" in allowed_section
    for removed_type in ("ActionUnit", "Checkbox", "TimelineUnit"):
        assert f"`{removed_type}`" not in allowed_section
    for removed_base_type in ("Button", "Divider", "Image", "List"):
        assert f"| `{removed_base_type}` |" not in allowed_section

    for removed_input_type in ("Divider", "Image"):
        assert f"`{removed_input_type}`" not in allowed_section


def test_unknown_routes_use_current_neutral_examples() -> None:
    small = SimpleNamespace(
        size="2x2",
        userQuery="展示项目状态",
        eventCandidates=[],
        dataModelSchema={"data": {"project": {"status": {"type": "string"}}}},
    )
    wide = SimpleNamespace(
        size="2x4",
        userQuery="展示项目状态",
        eventCandidates=[],
        dataModelSchema={"data": {"project": {"status": {"type": "string"}}}},
    )
    assert PromptBuilder._visual_route(small) == ("generic", ("2x2-V00",))
    assert PromptBuilder._visual_route(wide) == ("generic", ("2x4-V00",))


def test_prompt_source_has_no_out_of_range_formal_example_references() -> None:
    known_ids = {item[0] for item in EXAMPLES}
    pattern = re.compile(r"2x[24]-V\d\d")
    for path in PROMPT_SOURCE.rglob("*.md"):
        references = set(pattern.findall(path.read_text(encoding="utf-8")))
        assert references.issubset(known_ids), path
