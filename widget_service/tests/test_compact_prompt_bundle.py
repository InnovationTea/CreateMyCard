"""Compact 提示词源模块加载、路由与完整性回归；不调用线上模型。"""

import json
import shutil
from pathlib import Path

import pytest

from config.config import get_settings
from services.compact_layout_runtime import layout_ids_for_size
from services.compact_prompt_loader import (
    FRAGMENT,
    PROMPT_NAMES,
    _cached_prompts,
    assemble_prompts,
    read_prompt,
)
from services.protocol_registry import (
    DESIGN_COMPACT_PROFILE_ID,
    A2UIProtocolRegistry,
)

DEFAULT_BUNDLE = (
    Path(__file__).resolve().parents[1]
    / "cloud/data/protocol_profiles/design-compact-dsl-fusion"
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


def test_create_prompt_uses_unified_component_terms() -> None:
    create_prompt = assemble_prompts(DEFAULT_SOURCE).get("create")
    component_source = (DEFAULT_SOURCE / "components/common.md").read_text(encoding="utf-8")

    assert isinstance(create_prompt, str)
    assert "基础布局组件" in create_prompt
    assert "基础布局组件总表" in component_source
    assert "| `Row` | 横向排列子组件 |" in component_source
    for deprecated in ("基础组件", "高阶组件", "高级组件", "普通组件", "基础组合"):
        assert deprecated not in create_prompt


@pytest.mark.parametrize(
    ("size", "included", "excluded"),
    [
        ("2x2", "## 2x2 组件选型", "## 2x4 组件选型"),
        ("2x4", "## 2x4 组件选型", "## 2x2 组件选型"),
    ],
)
def test_plan_prompt_reuses_full_create_contract_for_size(
    size: str,
    included: str,
    excluded: str,
) -> None:
    plan_prompt = read_prompt(DEFAULT_SOURCE, "plan", size=size)

    assert "你是 HarmonyOS 桌面卡片极简协议 DSL 生成模型" in plan_prompt
    assert "## 1. 组件总表" in plan_prompt
    assert "| 标题 | `SingleLineTitle` | 单行标题 |" in plan_prompt
    assert "| 多项属性 | `TableText` | 多行标签—值 |" in plan_prompt
    assert "# 2. Compact DSL 组件合同" in plan_prompt
    assert "### 7.1 `EventCard`" in plan_prompt
    assert "## 从事实到组件组合" in plan_prompt
    assert "# Compact Info Plan" in plan_prompt
    assert "2x4 左右独立分区可分别使用" in plan_prompt
    assert "标题事实不推荐正文组件" in plan_prompt
    assert "时间、metadata 和补充说明使用 SecondaryBody" in plan_prompt
    assert included in plan_prompt
    assert excluded not in plan_prompt


def test_plan_prompt_appends_contract_after_complete_create_prompt() -> None:
    manifest = json.loads((DEFAULT_SOURCE / "manifest.yaml").read_text(encoding="utf-8"))
    prompts = manifest.get("prompts")
    assert isinstance(prompts, dict)
    create_references = prompts.get("create")
    plan_references = prompts.get("plan")
    assert isinstance(create_references, list)
    assert isinstance(plan_references, list)

    assert plan_references == [*create_references, "plan.md#contract"]


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_create_and_plan_share_common_component_catalog(size: str) -> None:
    create_prompt = read_prompt(DEFAULT_SOURCE, "create", size=size)
    plan_prompt = read_prompt(DEFAULT_SOURCE, "plan", size=size)

    heading = "## 1. 组件总表"
    assert plan_prompt.startswith(create_prompt)
    assert create_prompt.count(heading) == 1
    assert plan_prompt.count(heading) == 1


def test_common_component_contract_separates_shared_and_size_specific_rules() -> None:
    source = (DEFAULT_SOURCE / "components/common.md").read_text(encoding="utf-8")
    core_source = (DEFAULT_SOURCE / "core.md").read_text(encoding="utf-8")
    fragments = dict(FRAGMENT.findall(source))
    core_fragments = dict(FRAGMENT.findall(core_source))

    assert list(fragments) == ["selection", "catalog"]
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
    assert "`width`、`height`、`layoutWeight`、`flexShrink`、`margin`" in catalog
    assert "进度组件默认不生成" in catalog
    assert "SVG 默认视为可通过 `fillColor` 染色" in core_fragments.get(
        "input-candidates",
        "",
    )
    assert "`Text` 只由转换器在展开语义组件时生成" in catalog
    assert "| `role` | string | 仅静态 | 单项必填" in catalog
    assert "| `items[].label` | 显示值 | 静态 / Expression / PathBinding" in catalog
    progress_binding_contract = (
        "| `value` | number / string / PathBinding | 静态 / PathBinding；不接受 Expression"
    )
    assert progress_binding_contract in catalog
    assert '`role:"body"`' in catalog
    assert "单行内容保留约 20% 宽度余量" in catalog
    core_typography = core_fragments.get("typography", "")
    assert "`12fp`：标题区" not in core_typography
    assert "格式化主读数例外" not in core_typography
    assert (
        "具体组件的字号、字重、同行对齐和文本压力规则统一由后续组件合同定义"
        in core_typography
    )


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
    fragments = dict(FRAGMENT.findall(source.read_text(encoding="utf-8")))
    expected = ["preamble"]
    example_count = 33 if size == "2x2" else 27
    expected.extend(f"example-v{index:02d}" for index in range(example_count))
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
    body = fragments.get("example-v00")
    assert isinstance(body, str)
    if mutation == "input":
        broken = body.replace("```json", "```text")
    elif mutation == "output":
        broken = body.replace("```genui", "```text")
    else:
        broken = body.replace(f"{size}-V00", f"{size}-V99")
    assert broken != body
    source.write_text(original.replace(body, broken, 1), encoding="utf-8")
    with pytest.raises(ValueError, match=f"案例缺少完整输入/输出：{size}-V00"):
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
                reference
                for reference in prompt_references
                if reference != orphaned_reference
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
