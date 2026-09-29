"""将正式 Few-shot 作为真实生成输入，防止示例与转换协议漂移。"""

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.card_validation import validate_compact_dsl
from services.card_validation.contrast_validator import _composite, _contrast, _rgba
from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.compact_prompt_loader import assemble_prompts
from services.prompt_builder import PromptBuilder

PROMPT_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source"
)
PROMPTS = assemble_prompts(PROMPT_SOURCE)
HIGH_LEVEL_COMPONENTS = {
    "CardButton",
    "CardHeader",
    "CircleButton",
    "DataDisplay",
    "EmphasizedData",
    "EventCard",
    "InfoBlock",
    "PillButton",
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
    expected = [f"2x2-V{index:02d}" for index in range(10)]
    expected.extend(f"2x4-V{index:02d}" for index in range(7))
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
    for row in _rows(source):
        if len(row) < 3:
            continue
        _, component, props, *children = row
        assert "textOverflow" not in props, identifier
        if component == "Text":
            assert props.get("content") != "", identifier
            assert props.get("content") != " ", identifier
            assert props.get("fontSize", 12) >= 12, identifier
        if component in {"Row", "Column", "Stack", "List"}:
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
    assert set(actual_actions) == expected_actions, identifier
    assert actual_assets.issubset(expected_assets), identifier


@pytest.mark.parametrize(
    ("identifier", "required"),
    (
        ("2x2-V00", {"DataDisplay"}),
        ("2x2-V02", {"CardHeader", "EmphasizedData", "PillButton"}),
        ("2x2-V03", {"CardHeader", "CircleButton"}),
        ("2x2-V04", {"InfoBlock"}),
        ("2x2-V05", {"CardHeader", "PillButton"}),
        ("2x2-V06", {"PillButton"}),
        ("2x2-V07", {"CardHeader"}),
        ("2x2-V09", {"CardHeader", "PillButton"}),
        ("2x4-V03", {"InfoBlock", "CardButton"}),
        ("2x4-V04", {"CardButton"}),
        ("2x4-V05", {"InfoBlock", "CardButton"}),
    ),
)
def test_examples_use_available_high_level_components(
    identifier: str,
    required: set[str],
) -> None:
    _, source = _example(identifier)
    assert required.issubset(set(_component_types(source)))


@pytest.mark.parametrize(
    ("identifier", "absent", "required_base"),
    (
        ("2x2-V01", {"EventCard"}, {"Text", "Column"}),
        ("2x2-V05", {"ProgressCircle", "PairedMetric"}, {"Progress", "Stack"}),
        ("2x2-V08", {"Grid"}, {"Column", "Row", "Text"}),
        ("2x4-V01", {"EmphasisText", "TextBlock"}, {"Text", "Column"}),
        ("2x4-V02", {"PillButton", "CardButton"}, {"Button", "Column"}),
        ("2x4-V05", {"ProgressCircleSingle"}, {"Progress", "Stack"}),
        ("2x4-V06", {"H_BarChart", "NumericRatioStack"}, {"Progress", "Text"}),
    ),
)
def test_unavailable_or_incompatible_components_use_base_components(
    identifier: str,
    absent: set[str],
    required_base: set[str],
) -> None:
    _, source = _example(identifier)
    types = set(_component_types(source))
    assert absent.isdisjoint(types)
    assert required_base.issubset(types)


@pytest.mark.parametrize(
    ("identifier", "layout_scope"),
    (
        ("2x2-V00", "S-adaptive-single-business"),
        ("2x2-V01", "S-adaptive-single-business"),
        ("2x2-V02", "S-adaptive-single-business"),
        ("2x2-V03", "S-adaptive-single-business"),
        ("2x2-V04", "S-dual-info"),
        ("2x2-V05", "S-adaptive-single-business"),
        ("2x2-V06", "S-adaptive-single-business"),
        ("2x2-V07", "S-adaptive-single-business"),
        ("2x2-V08", "S-quad-content"),
        ("2x2-V09", "S-adaptive-single-business"),
        ("2x4-V00", "W-adaptive-single-business"),
        ("2x4-V01", "W-adaptive-single-business"),
        ("2x4-V02", "W-split-panels"),
        ("2x4-V03", "W-content-side-slots"),
        ("2x4-V04", "W-four-slots"),
        ("2x4-V05", "W-content-side-slots"),
        ("2x4-V06", "W-split-panels"),
    ),
)
def test_example_reaches_its_generation_route(
    identifier: str,
    layout_scope: str,
) -> None:
    task, _ = _example(identifier)
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
    assert selected == (identifier,)
    assert PromptBuilder._layout_scope(task_spec) == layout_scope

    document = PROMPTS[f"fewshot_{task['size']}"]
    selected_document = PromptBuilder._select_few_shot(document, task_spec)
    assert identifier in selected_document
    for other_id, _, _ in EXAMPLES:
        if other_id.startswith(task["size"]) and other_id != identifier:
            assert other_id not in selected_document

    assembled = PromptBuilder._with_size_few_shot(PROMPTS["create"], task_spec)
    assert identifier in assembled
    if "adaptive" not in layout_scope:
        assert f"### `{layout_scope}`" in assembled


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
    allowed_section = catalog.split("# 五、组件协议", maxsplit=1)[1]
    allowed_section = allowed_section.split("## 5.1", maxsplit=1)[0]
    for component_type in HIGH_LEVEL_COMPONENTS:
        assert f"`{component_type}`" in allowed_section
    for removed_type in ("ActionUnit", "Checkbox", "TimelineUnit"):
        assert f"`{removed_type}`" not in allowed_section


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
    retired = re.compile(r"(?:2x2-V(?:1[0-9]|[2-9][0-9])|2x4-V(?:0[7-9]|[1-9][0-9]))\b")
    for path in PROMPT_SOURCE.rglob("*.md"):
        assert not retired.search(path.read_text(encoding="utf-8")), path
