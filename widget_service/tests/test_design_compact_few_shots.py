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
)


def test_palette_matches_exact_ux_specification() -> None:
    expected = []
    for start, end, ink in UX_GRADIENTS:
        expected.append([start, end, "#FF" + ink, "#99" + ink, "#33" + ink, "#FF" + ink])
    assert _palette_rows() == expected


def test_default_palette_is_limited_to_blue_purple_and_warm() -> None:
    """默认 root 背景收敛为三套，避免分区卡继续放大高饱和青绿粉。"""
    prompt = (PROFILE / "PROMPT.md").read_text(encoding="utf-8")
    deprecated_background_starts = ("#FFCCFCFF", "#FFCCFFDD", "#FFFFCCD5")
    for color in deprecated_background_starts:
        assert color not in prompt

    allowed_starts = {start for start, _, _ in UX_GRADIENTS}
    for _, _, source in EXAMPLES:
        root = json.loads(source.splitlines()[0])
        gradient = root[2].get("linearGradient")
        if gradient is None:
            continue
        colors = gradient.get("colors")
        assert isinstance(colors, list) and colors
        assert colors[0][0] in allowed_starts


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


def test_formatted_readout_allows_single_field_expression_in_large_2x4_panel() -> None:
    """2x4 大分区允许单字段加真实单位的 24fp 主读数。"""
    _, original_task, source = next(item for item in EXAMPLES if "2x4-V10" in item[0])
    task = deepcopy(original_task)
    rows = [json.loads(line) for line in source.splitlines()]
    row = next(row for row in rows if row[0] == "weatherValue")
    row[2].update(
        {
            "content": "{{ " + "$" + "{/data/weather/current/temperatureC}" + " + '°C' }}",
            "width": 120,
            "height": 34,
            "fontSize": 24,
        }
    )
    changed_source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    result = validate_compact_dsl(
        changed_source,
        task_spec=task,
        card_spec={"suggestSize": "2x4"},
    )
    assert not result.warnings


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


@pytest.mark.parametrize(
    ("identifier", "expected_ids", "excluded_ids"),
    [
        ("2x2-V02", ("2x2-V02",), ("2x2-V03", "2x2-V04")),
        ("2x2-V03", ("2x2-V03",), ("2x2-V02",)),
        ("2x4-V01", ("2x4-V01", "2x4-V07"), ("2x4-V09", "2x4-V10")),
        ("2x4-V11", ("2x4-V11",), ("2x4-V01", "2x4-V09")),
        ("2x4-V12", ("2x4-V12",), ("2x4-V02", "2x4-V09")),
    ],
)
def test_few_shot_selection_uses_visual_route(
    identifier: str,
    expected_ids: tuple[str, ...],
    excluded_ids: tuple[str, ...],
) -> None:
    """按业务和主焦点选择少量互补示例，避免 2x4 注入整份示例集。"""
    size = identifier[:3]
    document = (PROFILE / f"FEWSHOT_{size}.md").read_text(encoding="utf-8")
    _, task, _ = next(item for item in EXAMPLES if identifier in item[0])
    selected = PromptBuilder._select_few_shot(document, SimpleNamespace(**task))
    for expected_id in expected_ids:
        assert expected_id in selected
    for excluded_id in excluded_ids:
        assert excluded_id not in selected


def test_visual_route_instruction_requires_single_focus() -> None:
    """组装后的提示词明确要求单一重心和示例值隔离。"""
    _, task, _ = next(item for item in EXAMPLES if "2x4-V11" in item[0])
    instruction = PromptBuilder._visual_route_instruction(SimpleNamespace(**task))
    assert "唯一第一焦点" in instruction or "第一焦点" in instruction
    assert "禁止复制示例业务值" in instruction


def test_multi_business_instruction_prefers_icons_only_when_candidates_match() -> None:
    _, task, _ = next(item for item in EXAMPLES if "2x4-V09" in item[0])
    instruction = PromptBuilder._visual_route_instruction(SimpleNamespace(**task))
    assert "稀疏分区放大主值或核心状态" in instruction
    assert "语义精确且状态安全" in instruction
    assert "不留空槽" in instruction


def test_simple_supported_2x2_route_recommends_fusion_ball() -> None:
    _, task, _ = next(item for item in EXAMPLES if "2x2-V02" in item[0])
    recommendation = PromptBuilder._fusion_ball_recommendation(SimpleNamespace(**task))
    assert "本次融球推荐" in recommendation
    assert "不得为融球删除用户必需内容" in recommendation


@pytest.mark.parametrize(
    "identifier",
    ("2x2-V05", "2x2-V03", "2x4-V02"),
)
def test_dense_or_multi_object_routes_do_not_recommend_fusion_ball(identifier: str) -> None:
    _, task, _ = next(item for item in EXAMPLES if identifier in item[0])
    recommendation = PromptBuilder._fusion_ball_recommendation(SimpleNamespace(**task))
    assert recommendation == ""


@pytest.mark.parametrize("query", ("用青色做耳机卡片", "展示三个耳机指标"))
def test_custom_color_or_dense_query_does_not_recommend_fusion_ball(query: str) -> None:
    _, source_task, _ = next(item for item in EXAMPLES if "2x2-V02" in item[0])
    task = {**source_task, "userQuery": query}
    recommendation = PromptBuilder._fusion_ball_recommendation(SimpleNamespace(**task))
    assert recommendation == ""


def test_s4_example_uses_available_business_icons() -> None:
    _, _, source = next(item for item in EXAMPLES if "2x2-V05" in item[0])
    rows = [json.loads(line) for line in source.splitlines()]
    icons = [row for row in rows if len(row) >= 3 and row[1] == "Image"]
    assert [row[0] for row in icons] == ["phone_icon", "ear_icon"]


def test_calendar_route_does_not_promote_candidate_actions_without_user_intent() -> None:
    """候选事件存在但用户未要求操作时，不能注入双按钮示例。"""
    _, task, _ = next(item for item in EXAMPLES if "2x4-V01" in item[0])
    route, selected = PromptBuilder._visual_route(SimpleNamespace(**task))
    assert route == "calendar-event"
    assert selected == ("2x4-V01", "2x4-V07")


def test_calendar_route_uses_action_variant_only_for_explicit_actions() -> None:
    """明确要求按钮时才引入 W6 双入口示例。"""
    _, task, _ = next(item for item in EXAMPLES if "2x4-V08" in item[0])
    route, selected = PromptBuilder._visual_route(SimpleNamespace(**task))
    assert route == "calendar-event"
    assert selected == ("2x4-V08", "2x4-V07")
    instruction = PromptBuilder._visual_route_instruction(SimpleNamespace(**task))
    assert "action-led" in instruction


def test_short_query_keeps_matching_read_only_entry_without_visible_button() -> None:
    """简短 query 仍可保留同业务的无副作用详情入口。"""
    _, original_task, _ = next(item for item in EXAMPLES if "2x4-V11" in item[0])
    task = deepcopy(original_task)
    task["userQuery"] = "做一张天气卡片"
    task["eventCandidates"] = [
        {
            "call": "clickToDeeplink",
            "args": {"intentName": "Weather_CityCode", "uri": "weather"},
        }
    ]
    instruction = PromptBuilder._visual_route_instruction(SimpleNamespace(**task))
    assert "唯一点击入口" in instruction
    assert "不要为了显示入口额外增加按钮" in instruction


def test_short_query_does_not_promote_settings_to_implicit_entry() -> None:
    """设置类副作用候选不能因 query 简短而自动变成入口。"""
    _, original_task, _ = next(item for item in EXAMPLES if "2x4-V12" in item[0])
    task = deepcopy(original_task)
    task["userQuery"] = "做一张耳机卡片"
    instruction = PromptBuilder._visual_route_instruction(SimpleNamespace(**task))
    assert "没有高置信的同业务隐式入口" in instruction


def test_short_query_keeps_read_only_earphone_entry() -> None:
    """耳机只读详情候选可在简短 query 下成为整卡隐式入口。"""
    _, original_task, _ = next(item for item in EXAMPLES if "2x4-V12" in item[0])
    task = deepcopy(original_task)
    task["userQuery"] = "做一张耳机卡片"
    task["eventCandidates"] = [
        {"call": "viewEarphoneStatus", "args": {"uri": "earphone"}}
    ]
    instruction = PromptBuilder._visual_route_instruction(SimpleNamespace(**task))
    assert "唯一点击入口" in instruction
    assert "不要为了显示入口额外增加按钮" in instruction


def test_unknown_single_business_uses_neutral_size_fallback() -> None:
    task = SimpleNamespace(
        size="2x2",
        userQuery="做一张项目状态卡片",
        eventCandidates=[],
        dataModelSchema={"data": {"project": {"status": {"type": "string"}}}},
    )
    route, selected = PromptBuilder._visual_route(task)
    assert route == "generic"
    assert selected == ("2x2-V00",)


def test_unknown_multi_business_uses_neutral_size_fallback() -> None:
    task = SimpleNamespace(
        size="2x4",
        userQuery="做一张综合信息卡片",
        eventCandidates=[],
        dataModelSchema={
            "data": {
                "project": {"status": {"type": "string"}},
                "finance": {"balance": {"type": "number"}},
            }
        },
    )
    route, selected = PromptBuilder._visual_route(task)
    assert route == "multi-business"
    assert selected == ("2x4-V13",)
