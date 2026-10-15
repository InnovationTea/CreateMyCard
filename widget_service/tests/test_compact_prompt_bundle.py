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
    assert "不得绑定到 `InfoBlock`" in create_prompt
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
    assert "不使用 `dataIds` 或" in create_prompt
    assert "`S-title-dual-content` 的两个 `126×50vp` 槽" in create_prompt
    assert '"variant":"stacked","primaryText":"{{ \'明天 \' +' in create_prompt
    assert "每行只承载一个动态业务值" in create_prompt


def test_single_line_title_icon_uses_semantic_match_and_button_priority() -> None:
    create_prompt = assemble_prompts(DEFAULT_SOURCE).get("create")

    assert isinstance(create_prompt, str)
    assert "分配顺序固定为动作在前、标题在后" in create_prompt
    assert "再由 `SingleLineTitle` 从未占用候选中选择" in create_prompt
    assert "按钮与标题不得复用同一素材，但可分别使用不同的语义匹配素材" in create_prompt
    assert "没有剩余匹配素材时省略标题图标" in create_prompt
    assert "不得为了保留标题图标把可使用准确图标的动作改成纯文字按钮" in create_prompt
    assert "所有 `SingleLineTitle` 均不使用图标" not in create_prompt
    assert "只有两类按钮都不使用图标" not in create_prompt
    assert "与标题对象严格匹配的装饰性主题图标" not in create_prompt
    assert "不可承担状态或动作语义" not in create_prompt


def test_anchor_layout_requires_main_and_nonempty_support_information() -> None:
    prompts = assemble_prompts(DEFAULT_SOURCE)
    create_prompt = prompts.get("create")
    plan_prompt = prompts.get("plan")

    assert isinstance(create_prompt, str)
    assert isinstance(plan_prompt, str)
    assert "一个主信息组与至少一个独立其它信息组" in create_prompt
    assert "左下可以使用 `SecondaryBody` 承载辅助事实" in create_prompt
    assert "不要求固定三项，但至少一项" in create_prompt
    assert "只在标题中展示的地点、对象或范围上下文不计入" in create_prompt
    assert "没有独立支撑事实时排除 `S-title-anchor`" in create_prompt
    assert "`layoutHints` 必须排除 `S-title-anchor`" in plan_prompt
    assert "左下支撑必须分配至少一个未被标题或主信息消费的独立事实" in plan_prompt
    assert "无需先证明整宽文字按钮造成空间压力" in create_prompt
    assert "不以 `PillButton` 无法闭合为前提" in create_prompt
    assert "只有底部 `PillButton` 无法与必要内容共同闭合时才使用" not in create_prompt
    assert "不等于要求卡面显示动作文字" in create_prompt
    assert "不限制信息项数量" not in create_prompt
    assert "不设置最低信息项数" not in create_prompt
    assert "至少三项必要信息" not in create_prompt
    assert "存在至少三项必须展示的信息" not in create_prompt


def test_create_prompt_uses_unified_component_terms() -> None:
    create_prompt = assemble_prompts(DEFAULT_SOURCE).get("create")
    component_source = (DEFAULT_SOURCE / "components/common.md").read_text(encoding="utf-8")

    assert isinstance(create_prompt, str)
    assert "基础布局组件" in create_prompt
    assert "基础布局组件总表" in component_source
    assert "| `Row` | 横向排列子组件 |" in component_source
    for deprecated in ("基础组件", "高阶组件", "高级组件", "普通组件", "基础组合"):
        assert deprecated not in create_prompt


def test_secondary_body_contract_groups_related_items() -> None:
    prompt = read_prompt(DEFAULT_SOURCE, "create", size="2x4")

    assert "组件不区分 role" in prompt
    assert "多个短字段按原顺序放入一个实例" in prompt
    assert "两项同行用 14；两项 `columns:1` 分行用 12" in prompt
    assert "标题、按钮、布局容器和其它 `SecondaryBody` 都不满足搭配条件" in prompt


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
    assert "不只按操作数量选布局" in system
    if size == "2x4":
        assert "紧凑区容量不成立时仍比较其它合法布局，不强行分区" in system
def test_secondary_body_repair_does_not_add_non_core_companions() -> None:
    repair_prompt = read_prompt(DEFAULT_SOURCE, "repair", size="2x2")
    assert "`SecondaryBody` 只能辅助整卡中已存在的核心信息组件" in repair_prompt
    assert "不能通过增加按钮、标题或另一个" in repair_prompt


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
    create_prompt = read_prompt(DEFAULT_SOURCE, "create", size="2x4")

    assert "你是 HarmonyOS 桌面卡片生成 Agent" in create_prompt
    assert "最后出现的 `<agent_stage>...</agent_stage>` 标记决定" in create_prompt
    assert "`<agent_stage>plan</agent_stage>`：只按本轮工具 Schema 提交" in create_prompt
    assert "没有任何阶段标记时" in create_prompt
    assert "你的唯一任务是" not in create_prompt
    assert "你只生成 DSL" not in create_prompt


def test_core_does_not_repeat_final_prohibition_checklist() -> None:
    manifest = json.loads((DEFAULT_SOURCE / "manifest.yaml").read_text(encoding="utf-8"))
    create_references = manifest.get("prompts", {}).get("create")
    core_source = (DEFAULT_SOURCE / "core.md").read_text(encoding="utf-8")

    assert isinstance(create_references, list)
    assert "core.md#prohibitions-checks" not in create_references
    assert "prompt:prohibitions-checks" not in core_source
    assert "以下是输出前必须全部通过的零容错门禁" in read_prompt(
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
        "本章的genui片段只展示布局层，不是可直接提交的完整DSL",
        "先选父区，再按直属角色选variant",
        "第二、第三个是固定槽，不是另外两个Region",
        "children数量按直属组件ID计",
        "紧凑与宽版都支持的四种Region结构",
        "仅宽版支持的四种Region结构",
        "四行SecondaryBody至少占70vp",
        "四格，不是父布局W-four-slots",
        "否则形成多个父节点",
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
    core_source = (DEFAULT_SOURCE / "core.md").read_text(encoding="utf-8")
    fragments = dict(FRAGMENT.findall(source))
    core_fragments = dict(FRAGMENT.findall(core_source))

    assert list(fragments) == ["selection", "catalog"]
    selection = fragments.get("selection", "")
    catalog = fragments.get("catalog", "")
    for removed_heading in (
        "通用 props 字段",
        "通用布局与样式 props",
        "显式样式口径",
    ):
        assert removed_heading not in catalog
    for shared_component in (
        "SingleLineTitle",
        "DoubleLineTitle",
        "Badge",
        "EmphasizedData",
        "EmphasisText",
        "SecondaryBody",
        "DataDisplay",
        "InfoBlock",
        "TableText",
        "SummaryList",
        "ProgressCircle",
        "ProgressLine2",
        "H_BarChart",
        "ProgressCircleSingle",
        "NumericRatioStack",
        "EventCard",
        "PillButton",
    ):
        assert f"`{shared_component}`" in catalog
    for dedicated_heading in (
        "### `CircleButton`",
        "### `TopTextBottomValue`",
        "### `TextBlock`",
        "### `CardButton`",
    ):
        assert dedicated_heading not in catalog
    assert "新语义源不填写width、height、layoutWeight、flexShrink、margin" in catalog
    assert "fontColor" not in selection
    assert "fontColor" not in catalog
    assert "组件不声明文字颜色" in catalog
    assert "进度组件默认不生成" in catalog
    assert "所有作为组件图标使用的 SVG 均视为可染色图标" in core_fragments.get(
        "input-candidates",
        "",
    )
    assert "`Text` 仅由转换器展开为 A2UI 基础节点" in selection
    assert "多源时使用至少 2 个有序 PathBinding" in catalog
    assert "数组由转换器按顺序以 ` | ` 连接" in catalog
    assert '"secondaryText":[{"path":"/data/weather/location/prefectureName"}' in catalog
    assert "| `role` |" not in catalog
    assert "| `items[].label` | 显示值 | 静态 / Expression / PathBinding" in catalog
    progress_binding_contract = (
        "| `value` | number / string / PathBinding | 静态 / PathBinding；不接受 Expression"
    )
    assert progress_binding_contract in catalog
    assert "不输出 `role`" in catalog
    assert "仍保留至少 20% 水平余量" in core_fragments.get(
        "input-candidates",
        "",
    )
    core_typography = core_fragments.get("typography", "")
    assert "`12fp`：标题区" not in core_typography
    assert "格式化主读数例外" not in core_typography
    assert "具体组件的字号、字重、同行对齐和文本压力规则统一由后续组件合同定义" in core_typography


def test_size_component_rules_separate_shared_and_dedicated_components() -> None:
    two_by_two_source = (DEFAULT_SOURCE / "components/2x2.md").read_text(encoding="utf-8")
    two_by_four_source = (DEFAULT_SOURCE / "components/2x4.md").read_text(encoding="utf-8")
    two_by_two_fragments = dict(FRAGMENT.findall(two_by_two_source))
    two_by_four_fragments = dict(FRAGMENT.findall(two_by_four_source))

    assert list(two_by_two_fragments) == ["selection", "icon-gate", "size-components"]
    assert list(two_by_four_fragments) == ["selection", "wide-components", "backboard-alpha"]

    two_by_two_selection = two_by_two_fragments.get("selection", "")
    two_by_four_selection = two_by_four_fragments.get("selection", "")
    for shared in (
        "SingleLineTitle",
        "DoubleLineTitle",
        "Badge",
        "EmphasisText",
        "SecondaryBody",
        "H_BarChart",
        "NumericRatioStack",
        "ProgressCircleSingle",
        "TableText",
        "EventCard",
        "PillButton",
    ):
        assert f"`{shared}`" in two_by_two_selection
        assert f"`{shared}`" in two_by_four_selection

    assert "2x2 不使用 `ProgressLine2`" in two_by_two_selection
    assert "2x4 不使用 `DataDisplay`、`CircleButton`" in two_by_four_selection
    assert "2x2 专属组件：`CircleButton`" in two_by_two_fragments.get("size-components", "")
    for dedicated in ("TopTextBottomValue", "TextBlock", "CardButton"):
        assert f"2x4 专属组件：`{dedicated}`" in two_by_four_fragments.get(
            "wide-components",
            "",
        )
    assert "只允许进入 `W-top-bottom` 的 details" in two_by_four_fragments.get(
        "wide-components",
        "",
    )
    assert "整卡改选为 `W-top-bottom`" in two_by_four_fragments.get(
        "wide-components",
        "",
    )
    wide_components = two_by_four_fragments.get("wide-components", "")
    text_block_contract = wide_components.split(
        "### 2x4 专属组件：`TextBlock`",
        maxsplit=1,
    )[1].split("###", maxsplit=1)[0]
    assert (
        "| `items[].label` | 显示值 | 静态 / Expression / PathBinding"
        in text_block_contract
    )
    assert "2x4 专属组件：`SummaryList`" not in two_by_four_fragments.get(
        "wide-components",
        "",
    )


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
        "双占比",
        "三占比",
        "四占比",
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
    for layout_id in layout_ids_for_size("2x2"):
        assert layout_id in two_by_two
    for layout_id in layout_ids_for_size("2x4"):
        assert layout_id in two_by_four
    for sub_layout in (
        "Sub-118-A",
        "Sub-118-B",
        "Sub-118-C",
        "Sub-118-D",
        "Sub-140-A",
        "Sub-140-B",
        "Sub-140-C",
        "Sub-140-D",
        "Sub-140-F",
        "Sub-140-G",
        "Sub-140-H",
    ):
        assert sub_layout in two_by_four

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
