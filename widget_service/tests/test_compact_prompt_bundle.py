"""Compact 提示词源模块加载、路由与完整性回归；不调用线上模型。"""

import json
import shutil
from pathlib import Path

import pytest

from config.config import get_settings
from models.generation import TaskSpec
from services.compact_layout_runtime import layout_ids_for_size
from services.compact_prompt_loader import (
    FRAGMENT,
    PROMPT_NAMES,
    _cached_prompts,
    assemble_prompts,
    read_prompt,
)
from services.prompt_builder import PromptBuilder
from services.protocol_registry import (
    DESIGN_COMPACT_PROFILE_ID,
    A2UIProtocolRegistry,
)

DEFAULT_BUNDLE = (
    Path(__file__).resolve().parents[1] / "cloud/data/protocol_profiles/design-compact-dsl-fusion"
)
DEFAULT_SOURCE = DEFAULT_BUNDLE / "prompt_source"

CREATE_SOURCE_ORDER = (
    "core.md",
    "information/common.md",
    "information/2x2.md",
    "information/2x4.md",
    "components/common.md",
    "components/2x2.md",
    "components/2x4.md",
    "combinations/common.md",
    "combinations/2x2.md",
    "combinations/2x4.md",
    "composition.md",
    "layouts/common.md",
    "layouts/2x2.md",
    "layouts/2x4.md",
)


def test_assembled_prompts_are_model_facing() -> None:
    prompts = assemble_prompts(DEFAULT_SOURCE)
    assert set(prompts) == PROMPT_NAMES
    for content in prompts.values():
        assert "<!-- prompt:" not in content
        assert "维护源" not in content


def test_create_prompt_loads_each_source_as_one_complete_block() -> None:
    manifest = json.loads((DEFAULT_SOURCE / "manifest.yaml").read_text(encoding="utf-8"))
    prompts = manifest.get("prompts")
    assert isinstance(prompts, dict)
    references = prompts.get("create")
    assert isinstance(references, list)

    expected_references = []
    for filename in CREATE_SOURCE_ORDER:
        content = (DEFAULT_SOURCE / filename).read_text(encoding="utf-8")
        fragment_names = [name for name, _body in FRAGMENT.findall(content)]
        assert fragment_names
        expected_references.extend(f"{filename}#{name}" for name in fragment_names)

    assert references == expected_references


def test_info_block_contract_is_noninteractive() -> None:
    create_prompt = assemble_prompts(DEFAULT_SOURCE).get("create")

    assert isinstance(create_prompt, str)
    assert "InfoBlock.onClick" not in create_prompt
    assert "合法可点击 InfoBlock" not in create_prompt
    assert "外层和内部均不得写 `onClick`" in create_prompt
    plain_example = (
        '["weather","InfoBlock",'
        '{"primaryText":{"path":"/data/weather/current/temperatureText"}'
    )
    icon_example = (
        '"visual":{"type":"icon",'
        '"icon":"resources/base/media/moon_z_fill_1.svg"}'
    )
    progress_example = (
        '"visual":{"type":"progressCircle",'
        '"icon":"resources/base/media/battery_leaf_fill.svg"}'
    )
    assert plain_example in create_prompt
    assert icon_example in create_prompt
    assert progress_example in create_prompt
    assert "每行只承载一个动态业务值" in create_prompt
    assert "`S-title-dual-content` 的两个 `126×50vp` 槽" in create_prompt
    assert '"variant":"stacked","primaryText":"{{ \'明天 \' +' in create_prompt
    assert "每行只承载一个动态业务值" in create_prompt


def test_single_line_title_icon_uses_semantic_match_and_button_priority() -> None:
    source = (DEFAULT_SOURCE / "core.md").read_text(encoding="utf-8")
    fragments = dict(FRAGMENT.findall(source))
    rules = fragments.get("input-candidates", "")
    assert "先给按钮分配准确动作图标" in rules
    assert "未占用候选给标题选匹配图标" in rules
    assert "不为标题撤掉准确按钮图标" in rules
    assert "默认同一 src 只用一次" in rules
    assert "同类对象" in rules
    assert "可选图标无匹配时省略" in rules

def test_anchor_layout_requires_main_and_nonempty_support_information() -> None:
    create = read_prompt(DEFAULT_SOURCE, "create", size="2x2")
    plan = read_prompt(DEFAULT_SOURCE, "plan", size="2x2")
    for rule in (
        "没有独立支撑事实时排除", "准确SVG", "至少有一个独立左下事实",
        "左下可用SecondaryBody", "其它位置已有核心信息组件", "标题、动作及只在标题",
    ):
        assert rule in create
    assert "缺独立支撑事实时排除它" in plan
    assert "不以 `PillButton` 无法闭合为前提" in create
    assert "不等于要求卡面显示动作文字" in create

def test_create_prompt_uses_unified_component_terms() -> None:
    create = read_prompt(DEFAULT_SOURCE, "create", size="2x2")
    assert "Row/Column/Stack" in create
    assert "| `Row` | 横向排列子组件 |" not in create
    for deprecated in ("基础组件", "高阶组件", "高级组件", "普通组件", "基础组合"):
        assert deprecated not in create

def test_secondary_body_contract_groups_related_items() -> None:
    prompt = read_prompt(DEFAULT_SOURCE, "create", size="2x4")

    assert "组件不区分 role" in prompt
    assert "多个短字段按原顺序放入一个实例" in prompt
    assert "两项同行用 14；两项 `columns:1` 分行用 12" in prompt
    assert "标题、Badge、按钮、布局容器和其它 `SecondaryBody`" in prompt


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_owned_action_layout_comparison_is_size_scoped_and_reaches_plan(size: str) -> None:
    create = read_prompt(DEFAULT_SOURCE, "create", size=size)
    rule = "先比较内容组与直属操作的归属，再比较操作数量"
    task = TaskSpec(userQuery="查看设备状态及操作", size=size, dataModelSchema={"data": {}})
    plan = read_prompt(DEFAULT_SOURCE, "plan", size=size)
    messages = PromptBuilder().build_compact_plan(task, create + "\n\n" + plan, "{}")
    system = messages[0].get("content")
    assert isinstance(system, str)
    assert (rule in create) == (size == "2x4")
    assert (rule in system) == (size == "2x4")
    assert "先判断事实在同组中是主值、标签、单位、补充还是事件要素" in system
    if size == "2x4":
        assert "紧凑区容量不成立时仍比较其它合法布局，不强行分区" in system
def test_secondary_body_repair_does_not_add_non_core_companions() -> None:
    repair_prompt = read_prompt(DEFAULT_SOURCE, "repair", size="2x2")
    assert "SecondaryBody 不能成为整卡唯一正文核心" in repair_prompt
    assert "不用按钮/标题假充核心" in repair_prompt


def test_agent_stage_instruction_does_not_forbid_registered_semantic_layout() -> None:
    task = TaskSpec(userQuery="查看设备状态", size="2x4", dataModelSchema={"data": {}})
    scope = PromptBuilder._compact_generation_scope(task)
    assert "最终 DSL 使用 Layout" in scope
    assert "Region 选择内容变体" in scope
    assert "不输出布局 ID、Card 或 Region 节点" not in scope


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_plan_prompt_contains_only_incremental_contract(size: str) -> None:
    plan_prompt = read_prompt(DEFAULT_SOURCE, "plan", size=size)

    assert "# Compact Info Plan" in plan_prompt
    assert "submit_card_plan" in plan_prompt
    assert "你是 HarmonyOS 桌面卡片极简协议 DSL 生成模型" not in plan_prompt
    assert "## 1. 组件总表" not in plan_prompt
    assert "## 2x2 组件选型" not in plan_prompt
    assert "## 2x4 组件选型" not in plan_prompt


def test_plan_manifest_only_registers_incremental_contract() -> None:
    manifest = json.loads((DEFAULT_SOURCE / "manifest.yaml").read_text(encoding="utf-8"))
    prompts = manifest.get("prompts")
    assert isinstance(prompts, dict)
    plan_references = prompts.get("plan")
    assert isinstance(plan_references, list)

    assert plan_references == ["plan.md#contract"]


def test_create_prompt_defers_output_format_to_latest_agent_stage() -> None:
    create = read_prompt(DEFAULT_SOURCE, "create", size="2x4")
    assert "最后一个 `<agent_stage>` 决定输出" in create
    assert "`plan`：按本轮工具 Schema 提交一次" in create
    assert "`compact_dsl` 或无标记" in create
    assert "两个阶段共用输入、组件和布局合同" in create

def test_core_does_not_repeat_final_prohibition_checklist() -> None:
    manifest = json.loads((DEFAULT_SOURCE / "manifest.yaml").read_text(encoding="utf-8"))
    create_references = manifest.get("prompts", {}).get("create")
    core_source = (DEFAULT_SOURCE / "core.md").read_text(encoding="utf-8")

    assert isinstance(create_references, list)
    assert "core.md#prohibitions-checks" not in create_references
    assert "prompt:prohibitions-checks" not in core_source
    assert "整卡编排与提交检查" in read_prompt(
        DEFAULT_SOURCE,
        "create",
        size="2x4",
    )


def test_two_by_two_layout_prompt_delegates_geometry_to_semantic_templates() -> None:
    source = (DEFAULT_SOURCE / "layouts/2x2.md").read_text(encoding="utf-8")
    layouts = dict(FRAGMENT.findall(source)).get("s-layouts", "")

    for removed_budget in (
        "20 + 6 + 100",
        "20 + 6 + 46 + 8 + 46",
        "20 + 6 + 56 + 8 + 36",
        "20 + 4 + 58 + 8 + 36",
        "38 + 8 + 36 + 8 + 36",
        '"layoutWeight":13',
        '"layoutWeight":10',
        '"height":20',
        "82vp` 文字组",
    ):
        assert removed_budget not in layouts

    for retained_contract in (
        "Layout是root",
        "不输出Row/Column/Stack",
        "padding8",
        "40×40槽居中",
        "按钮36vp",
        '"Layout"',
    ):
        assert retained_contract in layouts


def test_two_by_four_layout_prompt_delegates_geometry_to_semantic_templates() -> None:
    source = (DEFAULT_SOURCE / "layouts/2x4.md").read_text(encoding="utf-8")
    fragments = dict(FRAGMENT.findall(source))
    layouts = fragments.get("w-layouts", "")

    assert list(fragments) == ["w-layouts"]
    for removed_budget in (
        "132 + 12 + 132",
        "57 + 12 + 57",
        "70vp` 正文 + `4vp`",
        "4×16+3×2",
        "26 + 6 + 36 + 6 + 36",
        "38 + 8 + 36 + 8 + 36",
        "title 20 + 4 + body 86",
        '"layoutWeight":15',
        '"layoutWeight":8',
        '"height":20',
    ):
        assert removed_budget not in layouts

    for retained_contract in (
        "132×126vp",
        "132×57vp",
        "116×110vp",
        "紧凑版主要角色间距6vp",
        "宽版8vp",
        '"Layout"',
        '"Region"',
    ):
        assert retained_contract in layouts

    for sub_layout in (
        "center",
        "title-content",
        "title-hero-support",
        "title-content-action",
        "title-two-ratios",
        "title-hero-support-action",
        "four-ratios",
        "four-items",
    ):
        assert sub_layout in layouts

    create_prompt = assemble_prompts(DEFAULT_SOURCE, size="2x4").get("create")
    assert isinstance(create_prompt, str)
    for naming_rule in (
        "不自行缩写、拼接或增删后缀",
        "Group 的 `hero-support` 只有 `[hero, support]`",
        "第四项 PillButton",
        "没有内部按钮时选择已登记的 `title-hero-support`",
    ):
        assert naming_rule in layouts
        assert naming_rule in create_prompt

    for example_rule in (
        "以下最小代码模板已定义全部引用节点",
        "先选父区，再按直属角色选variant",
        "第二、第三个是固定槽，不是另外两个Region",
        "children数量按直属组件ID计",
        "紧凑与宽版都支持的四种Region结构",
        "仅宽版支持的四种Region结构",
        "四行SecondaryBody至少占70vp",
        "四格，不是父布局W-four-slots",
    ):
        assert example_rule in layouts
        assert example_rule in create_prompt

    for removed_preset in (
        "neutral-footer",
        "text-footer",
        "value-led",
        "metric-triple",
        "progress-detail",
        "ring-summary",
        "list-rows",
        "ring-detail",
        "agenda-cta",
        "受控内容预设",
    ):
        assert removed_preset not in layouts


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_plan_prompt_does_not_duplicate_create_contract(size: str) -> None:
    create_prompt = read_prompt(DEFAULT_SOURCE, "create", size=size)
    plan_prompt = read_prompt(DEFAULT_SOURCE, "plan", size=size)

    heading = "## 1. 组件总表"
    assert create_prompt.count(heading) == 1
    assert plan_prompt.count(heading) == 0
    assert plan_prompt not in create_prompt


def test_common_component_contract_separates_shared_and_size_specific_rules() -> None:
    source = (DEFAULT_SOURCE / "components/common.md").read_text(encoding="utf-8")
    fragments = dict(FRAGMENT.findall(source))
    assert list(fragments) == ["selection", "catalog"]
    catalog = fragments.get("catalog", "")
    for shared in (
        "SingleLineTitle", "DoubleLineTitle", "Badge", "EmphasizedData", "EmphasisText",
        "SecondaryBody", "InfoBlock", "TableText", "ProgressCircle", "H_BarChart",
        "ProgressCircleSingle", "NumericRatioStack", "EventCard", "PillButton",
    ):
        assert f"`{shared}`" in catalog
    for exclusive in ("DataDisplay", "SummaryList", "ProgressLine2"):
        assert f" `{exclusive}`\n" not in catalog
    for forbidden in ("| `width`", "| `height`", "| `role`", "fontColor"):
        assert forbidden not in catalog
    assert "内部次字号、字重、颜色和几何不用输出" in catalog
    assert "多源时使用至少 2 个有序 PathBinding" in catalog
    assert "数组由转换器按顺序以 ` | ` 连接" in catalog
    assert "静态 / PathBinding；不接受 Expression" in catalog
    assert "| `items[].label` | 显示值 |" in catalog

def test_size_component_rules_separate_shared_and_dedicated_components() -> None:
    common = read_prompt(DEFAULT_SOURCE, "create", size="2x2")
    wide = read_prompt(DEFAULT_SOURCE, "create", size="2x4")
    for name in ("DataDisplay", "CircleButton"):
        assert f" `{name}`\n" in common
        assert f" `{name}`\n" not in wide
    for name in ("TextBlock", "CardButton", "TopTextBottomValue", "ProgressLine2", "SummaryList"):
        assert f" `{name}`\n" in wide
        assert f" `{name}`\n" not in common
    assert "只允许进入 `W-top-bottom` 的 details" in wide
    assert "整卡改选为 `W-top-bottom`" in wide
    assert "合法可点击 Row/Column" not in wide
    assert "写 `height:50`" not in common
    assert "| `items[].label` | 显示值 |" in wide

def test_runtime_does_not_depend_on_generated_products() -> None:
    assert not list((DEFAULT_BUNDLE / "generated").glob("*.md"))
    assert not (Path(__file__).resolve().parents[1] / "scripts/build_compact_prompts.py").exists()
    assert read_prompt(DEFAULT_SOURCE, "create") == assemble_prompts(DEFAULT_SOURCE).get("create")


def test_information_modules_keep_semantic_boundary() -> None:
    root = DEFAULT_BUNDLE / "prompt_source/information"
    expected_fragments = {
        "common.md": ["contract"],
        "2x2.md": ["capacity"],
        "2x4.md": ["capacity"],
    }
    prompt_bodies = []
    for filename, expected in expected_fragments.items():
        source = (root / filename).read_text(encoding="utf-8")
        fragments = dict(FRAGMENT.findall(source))
        assert list(fragments) == expected
        prompt_bodies.extend(fragments.values())

    information_prompt = "\n".join(prompt_bodies)
    for forbidden in (
        "SingleLineTitle",
        "Sub-118",
        "Sub-140",
        "S-dual-info",
        "W-content-side-slots",
        "fontSize",
        "fillColor",
        "vp",
        "fp",
    ):
        assert forbidden not in information_prompt

    for required in ("汇总—明细", "主体—属性", "同级并列", "事件—要素", "内容—操作"):
        assert required in information_prompt

    manifest_path = DEFAULT_BUNDLE / "prompt_source/manifest.yaml"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    prompts = manifest.get("prompts")
    assert isinstance(prompts, dict)
    references = prompts.get("create")
    assert isinstance(references, list)
    start = references.index("information/common.md#contract")
    assert references[start : start + 3] == [
        "information/common.md#contract",
        "information/2x2.md#capacity",
        "information/2x4.md#capacity",
    ]


def test_combination_modules_separate_semantics_from_size_mapping() -> None:
    root = DEFAULT_BUNDLE / "prompt_source/combinations"
    expected_fragments = {
        "common.md": ["selection", "contract"],
        "2x2.md": ["mapping"],
        "2x4.md": ["mapping"],
    }
    bodies = {}
    for filename, expected in expected_fragments.items():
        source = (root / filename).read_text(encoding="utf-8")
        fragments = dict(FRAGMENT.findall(source))
        assert list(fragments) == expected
        body_name = "contract" if filename == "common.md" else "mapping"
        body = fragments.get(body_name)
        assert isinstance(body, str)
        bodies[filename] = body

    common = bodies.get("common.md")
    assert isinstance(common, str)
    for required in (
        "标题与数量",
        "核心与补充",
        "核心、补充与操作",
        "单内容与操作",
        "双/三/四占比",
        "双信息块",
        "双操作",
    ):
        assert required in common
    for forbidden in (
        "S-dual-info",
        "W-content-side-slots",
        "Sub-118",
        "Sub-140",
        "fontSize",
        "backgroundColor",
        "vp",
        "fp",
    ):
        assert forbidden not in common

    combined = "\n".join(bodies.values())
    for forbidden in (
        "<Card",
        "<Region",
        '"composition":',
        '"Card"',
        '"Region"',
    ):
        assert forbidden not in combined

    two_by_two = bodies.get("2x2.md")
    two_by_four = bodies.get("2x4.md")
    assert isinstance(two_by_two, str)
    assert isinstance(two_by_four, str)
    for name in ("hero-support", "label-value", "peer-pair", "supporting-items"):
        assert name in two_by_two
    for name in ("hero-support", "label-value", "peer-pair", "title-count"):
        assert name in two_by_four
    for legacy in ("Sub-118", "Sub-140"):
        assert legacy not in combined
    for size in ("2x2", "2x4"):
        layouts = read_prompt(DEFAULT_SOURCE, "create", size=size)
        for layout_id in layout_ids_for_size(size):
            assert layout_id in layouts

    manifest_path = DEFAULT_BUNDLE / "prompt_source/manifest.yaml"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    prompts = manifest.get("prompts")
    assert isinstance(prompts, dict)
    references = prompts.get("create")
    assert isinstance(references, list)
    start = references.index("combinations/common.md#selection")
    assert references[start : start + 4] == [
        "combinations/common.md#selection",
        "combinations/common.md#contract",
        "combinations/2x2.md#mapping",
        "combinations/2x4.md#mapping",
    ]


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_fewshot_source_is_one_document_per_size(size: str) -> None:
    source = DEFAULT_SOURCE / "fewshots" / f"{size}.md"
    assert not list((DEFAULT_SOURCE / "fewshots" / size).rglob("*.md"))
    source_content = source.read_text(encoding="utf-8")
    assert "fontColor" not in source_content
    fragments = dict(FRAGMENT.findall(source_content))
    expected = ["preamble"]
    if size == "2x2":
        expected.extend(
            f"example-v{index:02d}"
            for index in (1, 9, 10, 12, 4, 11, 13, 5, 6, 2, 8, 14, 3, 7)
        )
    else:
        expected.extend(f"example-v{index:02d}" for index in (3, 16, 28, 9, 8, 10, 23, 6, 19, 38))
    assert list(fragments) == expected
    manifest = json.loads((DEFAULT_SOURCE / "manifest.yaml").read_text(encoding="utf-8"))
    modules = manifest.get("modules")
    assert isinstance(modules, list)
    size_sources = []
    for module in modules:
        filename = module.get("file")
        assert isinstance(filename, str)
        if filename.startswith(f"fewshots/{size}"):
            size_sources.append(filename)
    assert size_sources == [f"fewshots/{size}.md"]


@pytest.mark.parametrize("size", ["2x2", "2x4"])
@pytest.mark.parametrize("mutation", ["input", "output", "identifier"])
def test_merged_fewshot_checks_each_fragment(tmp_path: Path, size: str, mutation: str) -> None:
    source_root = tmp_path / "prompt_source"
    shutil.copytree(DEFAULT_SOURCE, source_root)
    source = source_root / "fewshots" / f"{size}.md"
    original = source.read_text(encoding="utf-8")
    fragments = dict(FRAGMENT.findall(original))
    example = "v01" if size == "2x2" else "v03"
    identifier = f"{size}-V{example[1:]}"
    body = fragments.get(f"example-{example}")
    assert isinstance(body, str)
    if mutation == "input":
        broken = body.replace("```json", "```text")
    elif mutation == "output":
        broken = body.replace("```genui", "```text")
    else:
        broken = body.replace(identifier, f"{size}-V99")
    assert broken != body
    source.write_text(original.replace(body, broken, 1), encoding="utf-8")
    with pytest.raises(ValueError, match=f"案例缺少完整输入/输出：{identifier}"):
        assemble_prompts(source_root)


@pytest.mark.parametrize(
    "method,name",
    [
        ("read_design_plan_prompt", "plan"),
        ("read_design_prompt", "create"),
        ("read_design_edit_prompt", "edit"),
        ("read_design_repair_prompt", "repair"),
        ("read_design_argument_repair_prompt", "argument_repair"),
    ],
)
def test_registry_reads_prompt_source(method: str, name: str, tmp_path: Path) -> None:
    old = tmp_path / DESIGN_COMPACT_PROFILE_ID
    old.mkdir()
    (old / "PROMPT.md").write_text("旧路径不得回退", encoding="utf-8")
    source = tmp_path / "design-compact-dsl-fusion/prompt_source"
    shutil.copytree(DEFAULT_SOURCE, source)
    read = getattr(A2UIProtocolRegistry, method)
    assert read(DESIGN_COMPACT_PROFILE_ID, tmp_path) == assemble_prompts(source).get(name)


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_fewshot_uses_prompt_source(size: str) -> None:
    actual = A2UIProtocolRegistry.read_design_few_shot(DESIGN_COMPACT_PROFILE_ID, size)
    expected = assemble_prompts(DEFAULT_SOURCE).get(f"fewshot_{size}")
    assert actual == expected


def test_unknown_fewshot_size_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        A2UIProtocolRegistry.read_design_few_shot(DESIGN_COMPACT_PROFILE_ID, "../PROMPT")


def test_default_config_uses_same_source_prompts() -> None:
    settings = get_settings()
    for key, method in (
        ("system.prompt", "read_design_prompt"),
        ("edit.system.prompt", "read_design_edit_prompt"),
        ("repair.system.prompt", "read_design_repair_prompt"),
    ):
        assert settings.CONFIG.get(key) == getattr(A2UIProtocolRegistry, method)(
            DESIGN_COMPACT_PROFILE_ID
        )


def test_source_edit_takes_effect_after_loader_restart(tmp_path: Path) -> None:
    source = tmp_path / "prompt_source"
    shutil.copytree(DEFAULT_SOURCE, source)
    original = read_prompt(source, "create")
    core = source / "core.md"
    content = core.read_text(encoding="utf-8")
    core.write_text(content.replace("你是 HarmonyOS", "你是测试 HarmonyOS", 1), encoding="utf-8")
    assert read_prompt(source, "create") == original
    _cached_prompts.cache_clear()
    assert read_prompt(source, "create") != original


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "escape", "size", "orphan"])
def test_invalid_manifest_is_rejected(tmp_path: Path, mutation: str) -> None:
    source = tmp_path / "prompt_source"
    shutil.copytree(DEFAULT_SOURCE, source)
    path = source / "manifest.yaml"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    prompts = manifest.get("prompts")
    modules = manifest.get("modules")
    assert isinstance(prompts, dict) and isinstance(modules, list)
    references = prompts.get("create")
    assert isinstance(references, list)
    if mutation == "missing":
        references[0] = "core.md#does-not-exist"
    elif mutation == "duplicate":
        references.append(references[0])
    elif mutation == "escape":
        modules[0]["file"] = "../../escape.md"
    elif mutation == "size":
        modules[0]["sizes"] = ["4x4"]
    else:
        orphaned_reference = references.pop(0)
        for prompt_name, prompt_references in prompts.items():
            if prompt_name == "create" or not isinstance(prompt_references, list):
                continue
            prompts[prompt_name] = [
                reference for reference in prompt_references if reference != orphaned_reference
            ]
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError):
        assemble_prompts(source)


def test_unclosed_fragment_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "prompt_source"
    shutil.copytree(DEFAULT_SOURCE, source)
    core = source / "core.md"
    original = core.read_text(encoding="utf-8")
    core.write_text(original.replace("<!-- /prompt:identity -->", "", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="不闭合"):
        assemble_prompts(source)


def test_unregistered_source_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "prompt_source"
    shutil.copytree(DEFAULT_SOURCE, source)
    unregistered = source / "unregistered.md"
    unregistered.write_text(
        "<!-- prompt:new -->\n规则\n<!-- /prompt:new -->\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="未登记"):
        assemble_prompts(source)
