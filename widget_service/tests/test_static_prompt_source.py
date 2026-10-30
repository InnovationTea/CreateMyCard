"""静态职责、尺寸、阶段与维护元信息的装配回归。"""

import json
import re
import shutil
from pathlib import Path

import pytest

from models.generation import TaskSpec
from services.compact_dsl_a2ui_converter import convert_compact_dsl_to_a2ui
from services.compact_prompt_loader import read_static_prompt
from services.generation_content_policy import STATIC_CONTENT_POLICY, content_policy_scope
from services.prompt_builder import PromptBuilder
from services.static_prompt_source import STATIC_STAGES, _static_prompts

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source"
)


@pytest.fixture
def source_root(tmp_path):
    root = tmp_path / "source"
    shutil.copytree(SOURCE, root)
    _static_prompts.cache_clear()
    yield root
    _static_prompts.cache_clear()


def edit_manifest(root, edit):
    path = root / "manifest.yaml"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    profile = manifest.get("staticContent")
    assert isinstance(profile, dict)
    edit(profile)
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")


def field(profile, name, value_type):
    value = profile.get(name)
    assert isinstance(value, value_type)
    return value


def first_module(profile):
    modules = field(profile, "modules", list)
    assert modules
    module = next(iter(modules))
    assert isinstance(module, dict)
    return module


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_shared_contract_and_stage_boundaries(size):
    prompts = {name: read_static_prompt(SOURCE, name, size) for name in STATIC_STAGES}
    create = prompts.get("create")
    assert isinstance(create, str)
    assert "# 信息理解与组织" in create
    assert "# 内容组织流程" in create
    assert "24事实总预算" not in create
    plan = prompts.get("plan")
    assert isinstance(plan, str)
    assert "24事实总预算" in plan
    assert "# 组件" not in plan
    assert "## 变体" not in plan
    assert "完整Compact JSONL" in prompts.get("dsl", "")
    assert "# 静态修复" in prompts.get("repair", "")
    for prompt in prompts.values():
        assert "description:" not in prompt
        assert "name: static-" not in prompt


def test_size_specific_components_layouts_and_composition_are_isolated():
    small = read_static_prompt(SOURCE, "create", "2x2")
    wide = read_static_prompt(SOURCE, "create", "2x4")
    assert "ComparisonGroup" not in small
    assert "W-static-content" not in small
    assert "宽卡优先" not in small
    assert "S-static-content" in small
    assert "title-action" not in small
    assert "小卡采用全宽信息" in small
    assert "ComparisonGroup" in wide
    assert "S-static-content" not in wide
    assert "title-action" not in wide
    assert "宽卡比较可使用2–3栏" in wide


@pytest.mark.parametrize("size,count", [("2x2", 6), ("2x4", 11)])
def test_loaded_examples_match_current_static_contract(size, count):
    content = read_static_prompt(SOURCE, "fewshot", size)
    assert content.count("```genui") == count
    assert "ContentBlock" not in content
    assert "RecordList" not in content
    assert "onClick" not in content
    assert "fontSize" not in content


def test_wide_examples_are_grouped_by_body_component():
    content = read_static_prompt(SOURCE, "fewshot", "2x4")
    components = re.findall(r'\["body","([A-Za-z]+)"', content)
    assert components == [
        "EmphasisText",
        "EmphasisText",
        "TextList",
        "TextList",
        "TextList",
        "TextList",
        "TextList",
        "ComparisonGroup",
        "ComparisonGroup",
        "ComparisonGroup",
        "SingleLineList",
    ]


def test_single_line_list_guidance_always_requires_title():
    required = "SingleLineList必须与SingleLineTitle标题配套使用"
    for stage in ("plan", "create", "repair"):
        assert required in read_static_prompt(SOURCE, stage, "2x2")
        assert required in read_static_prompt(SOURCE, stage, "2x4")


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_shared_body_line_always_counts_toward_component_capacity(size):
    subject = "任何最终渲染为正文行的shared说明、例外或提示"
    accounting = "都计入所选组件的实际条目数"
    for stage in ("plan", "create", "repair"):
        prompt = read_static_prompt(SOURCE, stage, size)
        assert subject in prompt
        assert accounting in prompt


def test_text_list_guidance_requires_title_for_two_items_only():
    required = "TextList为2项时必须与SingleLineTitle标题配套使用；3项时允许无标题"
    for stage in ("plan", "create", "repair"):
        assert required in read_static_prompt(SOURCE, stage, "2x2")
        assert required in read_static_prompt(SOURCE, stage, "2x4")


def test_comparison_group_guidance_requires_title_for_two_or_three_items():
    required = (
        "ComparisonGroup为2或3项时必须与SingleLineTitle标题配套使用；"
        "4项宫格允许无标题"
    )
    for stage in ("plan", "create", "repair"):
        assert required in read_static_prompt(SOURCE, stage, "2x4")


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_single_line_list_capacity_repair_requires_legal_text_list(size):
    repair = read_static_prompt(SOURCE, "repair", size)
    assert "仅在记录数为2–3、含标题最多两项且主副字段均能承载时，才改用TextList" in repair
    assert "先在同对象内重新分配主副字段，保持已接受分组和必要公共标题" in repair
    assert "不得删header或合并不同对象来凑项数" in repair
    assert "未收到optionalDrop时保留全部事实" in repair
    assert "SingleLineList的text或assist无法完整单行展示时，改用TextList" not in repair


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_component_guidance_only_switches_lists_with_matching_capacity(size):
    prompt = read_static_prompt(SOURCE, "create", size)
    assert "仅在记录数为2–3、含标题最多两项且主副字段均能承载时，才改用TextList" in prompt
    assert "修复时保持已接受分组及必要公共标题" in prompt
    assert "使用TextList的主副记录结构，不继续选择SingleLineList" not in prompt


def test_small_fewshots_expand_under_current_static_contract():
    content = (SOURCE / "static_content/fewshots/2x2.md").read_text(encoding="utf-8")
    for example_id in range(91, 97):
        match = re.search(
            rf"## 2x2-V{example_id}\n\n```json\n.*?\n```\n\n```genui\n(.*?)\n```",
            content,
            re.S,
        )
        assert match is not None
        with content_policy_scope(STATIC_CONTENT_POLICY):
            converted = convert_compact_dsl_to_a2ui(match.group(1), size="2x2")
        assert converted


def test_reading_other_stages_does_not_reread_shared_files(source_root, monkeypatch):
    original = Path.read_text
    reads = []

    def tracked(path, *args, **kwargs):
        reads.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", tracked)
    for name in STATIC_STAGES:
        read_static_prompt(source_root, name, "2x2")
    assert reads.count(source_root / "manifest.yaml") == 1
    assert reads.count(source_root / "core.md") == 1
    assert reads.count(source_root / "static_content/information/common.md") == 1
    assert source_root / "static_content/components/2x4.md" not in reads


def test_small_request_does_not_read_unrelated_wide_files(source_root):
    path = source_root / "static_content/components/2x4.md"
    path.unlink()
    assert "S-static-content" in read_static_prompt(source_root, "create", "2x2")
    with pytest.raises(FileNotFoundError):
        read_static_prompt(source_root, "create", "2x4")


@pytest.mark.parametrize("name,size", [("unknown", "2x2"), ("create", "4x4")])
def test_unknown_stage_or_size_fails(name, size):
    with pytest.raises(ValueError):
        read_static_prompt(SOURCE, name, size)


@pytest.mark.parametrize(
    "change,message",
    [
        (lambda p: field(p, "modules", list).append(first_module(p)), "重复登记"),
        (lambda p: field(p, "create", list).append("core.md#identity"), "重复加载"),
        (lambda p: field(p, "plan", list).append("core.md#identity"), "跨阶段重复"),
        (lambda p: field(p, "create", list).append("unknown.md"), "未登记"),
        (lambda p: first_module(p).update(sizes=["4x4"]), "尺寸无效"),
        (lambda p: first_module(p).update(sizes=["2x2", "2x2"]), "尺寸重复"),
        (lambda p: field(p, "plan", list).clear(), "缺少有效"),
        (lambda p: field(p, "exampleIds", dict).update({"2x2": ["2x2-V999"]}), "案例登记"),
    ],
)
def test_invalid_manifest_is_rejected(source_root, change, message):
    edit_manifest(source_root, change)
    with pytest.raises(ValueError, match=message):
        read_static_prompt(source_root, "create", "2x2")


def test_unregistered_source_fragment_does_not_escape_directory(source_root):
    def change(profile):
        modules = profile.get("modules")
        references = profile.get("plan")
        assert isinstance(modules, list)
        assert isinstance(references, list)
        modules.append({"file": "../outside.md", "sizes": ["2x2"]})
        references.append("../outside.md")

    edit_manifest(source_root, change)
    with pytest.raises(ValueError, match="路径超出"):
        read_static_prompt(source_root, "create", "2x2")


def test_unclosed_metadata_is_not_sent_to_model(source_root):
    path = source_root / "static_content/core.md"
    path.write_text("---\nname: incomplete\n正文", encoding="utf-8")
    with pytest.raises(ValueError, match="维护头未闭合"):
        read_static_prompt(source_root, "create", "2x2")


def test_complete_capacity_and_shared_rules_are_loaded_once_across_history(monkeypatch):
    from config.config import get_settings

    monkeypatch.setattr(get_settings(), "enable_design_compact_few_shots", True)
    monkeypatch.setattr(get_settings(), "enable_design_compact_few_shot_selection", False)
    task = TaskSpec(userQuery="制作备忘：带证件", size="2x2", dataModelSchema={"data": {}})
    builder = PromptBuilder()
    with content_policy_scope(STATIC_CONTENT_POLICY):
        initial = builder.build_design_token(task, "", "design-compact-dsl")
        assert len(initial) == 2
        plan_system = initial[0]["content"] + "\n\n" + read_static_prompt(SOURCE, "plan", "2x2")
        plan_messages = builder.build_compact_plan(task, plan_system, initial[1]["content"])
        assert len(plan_messages) == 3
        assert "2x2-V91" not in str(plan_messages)
        plan = {
            "info_required": [], "contentGroups": [], "layoutHints": ["S-static-content"],
        }
        plan_messages.append({"role": "assistant", "content": json.dumps(plan)})
        continued = builder.build_compact_dsl_continuation(plan_messages, task, plan)
        repaired = builder.build_repair(
            continued, "invalid", [], task_spec=task, compact_plan=plan,
            dsl_format="design-compact-dsl",
        )
    history = "\n".join(message.get("content", "") for message in repaired)
    assert history.count("# 信息理解与组织") == 1
    assert history.count("# 首次Plan组件容量预算") == 1
    assert history.count("# 静态Plan提交") == 1
    assert history.count("## 2x2-V91") == 1
    assert "# 静态修复" in history
    assert history.count("仅在记录数为2–3、含标题最多两项且主副字段均能承载时") == 2
    assert "不得删header或合并不同对象来凑项数" in history
    assert "使用TextList的主副记录结构，不继续选择SingleLineList" not in history
    assert "description: 静态" not in history
