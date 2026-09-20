"""将正式 few-shot 作为真实生成输入，防止示例与转换协议漂移。"""

import json
import re
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.card_validation.contrast_validator import _composite, _contrast, _rgba
from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.prompt_builder import PromptBuilder

PROFILE = Path(__file__).resolve().parents[1] / "cloud/data/protocol_profiles/design-compact-dsl"


def _examples() -> list[tuple[str, dict, str]]:
    examples = []
    for size in ("2x2", "2x4"):
        document = (PROFILE / f"FEWSHOT_{size}.md").read_text(encoding="utf-8")
        for section in re.split(r"(?m)^## ", document)[1:]:
            task_match = re.search(r"```json\s*\n(.*?)\n```", section, re.S)
            source_match = re.search(r"```genui\s*\n(.*?)\n```", section, re.S)
            assert task_match is not None, section.splitlines()[0]
            assert source_match is not None, section.splitlines()[0]
            examples.append(
                (section.splitlines()[0], json.loads(task_match.group(1)), source_match.group(1))
            )
    return examples


EXAMPLES = _examples()


@pytest.mark.parametrize("name,task,source", EXAMPLES, ids=[item[0] for item in EXAMPLES])
def test_few_shot_validates_and_converts(name: str, task: dict, source: str, monkeypatch) -> None:
    """检查动态路径、事件、布局门禁和高级组件展开，而非仅检查 JSON 语法。"""
    settings = SimpleNamespace(CONFIG={"fusion_ball_min_prd_version": "1.0"})
    monkeypatch.setattr("services.fusion_ball_expander.get_settings", lambda: settings)
    size = task.get("size")
    assert size in ("2x2", "2x4"), name
    result = validate_compact_dsl(source, task_spec=task, card_spec={"suggestSize": size})
    assert not result.warnings, name
    converted = convert_compact_dsl_to_a2ui(
        source,
        size=size,
        protocol_profile={"version": "v0.9", "appVersion": "99.0"},
    )
    messages = [json.loads(line) for line in converted.splitlines()]
    assert len(messages) == 3, name
    for message, operation in zip(
        messages, ("createSurface", "updateComponents", "updateDataModel"), strict=True
    ):
        assert operation in message, name


@pytest.mark.parametrize("name,task,source", EXAMPLES, ids=[item[0] for item in EXAMPLES])
def test_few_shot_has_readable_nonempty_content(name: str, task: dict, source: str) -> None:
    """示例不能借截断、微小文字或空容器掩盖布局问题。"""
    del task
    for line in source.splitlines():
        row = json.loads(line)
        if len(row) < 3:
            continue
        _, component, props, *children = row
        assert "textOverflow" not in props, name
        if component == "Text":
            assert props.get("content") not in ("", " "), name
            assert props.get("fontSize", 12) >= 12, name
        if component in ("Row", "Column", "Stack", "List"):
            assert children and children[0], name


def _palette_rows() -> list[list[str]]:
    palettes = []
    for line in (PROFILE / "PROMPT.md").read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        colors = re.findall(r"#[A-F0-9]{8}", line)
        if len(colors) == 6:
            palettes.append(colors)
    assert palettes, "主提示词必须包含可检查的浅色配色表"
    return palettes


@pytest.mark.parametrize("colors", _palette_rows())
def test_palette_preserves_text_hierarchy_across_gradient(colors: list[str]) -> None:
    """检查合成后的主次层级；不以旧对比度阈值覆盖 UX 指定的透明色。"""
    start, end, primary, secondary, button, _ = colors
    start_rgb = _rgba(start)[:3]
    end_rgb = _rgba(end)[:3]
    for step in range(11):
        fraction = step / 10.0
        channels = []
        for left, right in zip(start_rgb, end_rgb, strict=True):
            channels.append(left + (right - left) * fraction)
        background = tuple(channels)
        backboard = _composite(background, _rgba("#CCFFFFFF"))
        for surface in (background, backboard):
            assert _contrast(primary, surface) > _contrast(secondary, surface)
            button_surface = _composite(surface, _rgba(button))
            assert _contrast(primary, button_surface) > 1.0


@pytest.mark.parametrize("example_id", ("2x2-V01", "2x2-V02", "2x2-V04", "2x4-V09"))
def test_examples_ignore_unrelated_candidates(example_id: str) -> None:
    """正式示例必须包含干扰候选，但输出不得消费它们。"""
    name, task, source = next(item for item in EXAMPLES if example_id in item[0])
    candidates = task.get("assetCandidates")
    assert isinstance(candidates, list), name
    distractors = []
    for candidate in candidates:
        description = candidate.get("description", "")
        if any(word in description for word in ("音乐音符", "闹钟实心", "样式：日历实心")):
            src = candidate.get("src")
            assert isinstance(src, str), name
            distractors.append(src)
    assert distractors, name
    for src in distractors:
        assert src not in source, name
    if example_id != "2x2-V04":
        events = task.get("eventCandidates")
        assert isinstance(events, list), name
        assert any(event.get("args", {}).get("intentName") == "Music" for event in events)
        assert '"intentName":"Music"' not in source, name


@pytest.mark.parametrize("name,task,source", EXAMPLES, ids=[item[0] for item in EXAMPLES])
def test_examples_do_not_duplicate_shared_actions(name: str, task: dict, source: str) -> None:
    """完整参数参与去重，不能将相同函数的不同目标误合并。"""
    del task
    seen = set()
    for line in source.splitlines():
        row = json.loads(line)
        if len(row) < 3:
            continue
        for handler in row[2].get("onClick", []):
            identity = json.dumps(handler, ensure_ascii=False, sort_keys=True)
            assert identity not in seen, name
            seen.add(identity)


def test_explicit_music_pair_preserves_distinct_targets() -> None:
    """用户明确的双歌单动作保留两个目标，且音符不迁移到内容区域。"""
    _, task, source = next(item for item in EXAMPLES if "2x2-V03" in item[0])
    expected = task.get("eventCandidates")
    assert isinstance(expected, list) and len(expected) == 2
    actual = []
    for line in source.splitlines():
        row = json.loads(line)
        if len(row) < 3:
            continue
        if row[2].get("icon"):
            assert row[1] == "ActionUnit"
        actual.extend(row[2].get("onClick", []))
    assert actual == expected


def test_countdown_with_unrelated_event_keeps_display_only() -> None:
    """即使恰好提供一个事件，也不能给纯倒计时补歌单按钮或整卡点击。"""
    _, task, source = next(item for item in EXAMPLES if "2x2-V01" in item[0])
    events = task.get("eventCandidates")
    assert isinstance(events, list) and len(events) == 1
    for line in source.splitlines():
        row = json.loads(line)
        if len(row) < 3:
            continue
        assert row[1] not in ("Button", "ActionUnit", "Image")
        assert not row[2].get("onClick")
        assert not row[2].get("icon")


UX_GRADIENTS = (
    ("#FFCBDDFE", "#FFF1F6FE", "1F4799"),
    ("#FFDBCCFF", "#FFF6F2FF", "563D99"),
    ("#FFFFE0CC", "#FFFFF7F2", "8C4B1C"),
    ("#FFCCFCFF", "#FFF2FEFF", "1C838C"),
    ("#FFCCFFDD", "#FFF2FFF6", "1C8C41"),
    ("#FFFFCCD5", "#FFFFF2F4", "991F33"),
)


def test_palette_matches_exact_ux_specification() -> None:
    expected = []
    for start, end, ink in UX_GRADIENTS:
        expected.append([start, end, "#FF" + ink, "#99" + ink, "#33" + ink, "#FF" + ink])
    assert _palette_rows() == expected


@pytest.mark.parametrize("name,task,source", EXAMPLES, ids=[item[0] for item in EXAMPLES])
def test_example_gradients_preserve_ux_direction_and_stops(
    name: str, task: dict, source: str
) -> None:
    """检查真正送给模型的示例，拦截端点互换、旧颜色或角度覆盖。"""
    del task
    allowed = []
    for start, end, _ in UX_GRADIENTS:
        allowed.append([[start, 0], [end, 1]])
    for line in source.splitlines():
        row = json.loads(line)
        if len(row) < 3:
            continue
        gradient = row[2].get("linearGradient")
        if gradient is None:
            continue
        assert gradient.get("direction") == "RightBottom", name
        assert "angle" not in gradient, name
        assert gradient.get("colors") in allowed, name


@pytest.mark.parametrize("change", ["font", "width", "height", "expression", "roots", "padding"])
def test_formatted_readout_rejects_unsafe_layout(change: str) -> None:
    _, original_task, source = next(item for item in EXAMPLES if "2x2-V09" in item[0])
    task = deepcopy(original_task)
    rows = [json.loads(line) for line in source.splitlines()]
    row = next(row for row in rows if row[0] == "temperature")
    props = row[2]
    if change == "font":
        props["fontSize"] = 30
    elif change == "width":
        props["width"] = 112
    elif change == "height":
        props["height"] = 20
    elif change == "padding":
        props["padding"] = 4
    elif change == "expression":
        content = props.get("content")
        assert isinstance(content, dict)
        path = content.get("path")
        assert isinstance(path, str)
        props["content"] = "{{ ${" + path + "} }}"
    else:
        schema = task.get("dataModelSchema")
        assert isinstance(schema, dict)
        data = schema.get("data")
        assert isinstance(data, dict)
        data["other"] = {}
    changed_source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    with pytest.raises(CompactDslValidationError, match="fontSize"):
        validate_compact_dsl(changed_source, task_spec=task, card_spec={"suggestSize": "2x2"})


@pytest.mark.parametrize("identifier", ["2x2-V09", "2x2-V10", "2x2-V01"])
def test_new_examples_reach_their_generation_route(identifier: str) -> None:
    _, task, _ = next(item for item in EXAMPLES if identifier in item[0])
    document = (PROFILE / "FEWSHOT_2x2.md").read_text(encoding="utf-8")
    selected = PromptBuilder._select_few_shot(document, SimpleNamespace(**task))
    assert identifier in selected
    if identifier == "2x2-V09":
        assert "2x2-V10" not in selected
        assert "2x2-V05" not in selected
    if identifier == "2x2-V10":
        assert "2x2-V05" in selected
        assert "2x2-V09" not in selected
