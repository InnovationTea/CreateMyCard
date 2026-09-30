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


def test_assembled_prompts_are_model_facing() -> None:
    prompts = assemble_prompts(DEFAULT_SOURCE)
    assert set(prompts) == PROMPT_NAMES
    for content in prompts.values():
        assert "<!-- prompt:" not in content
        assert "维护源" not in content


def test_info_block_contract_is_noninteractive() -> None:
    create_prompt = assemble_prompts(DEFAULT_SOURCE).get("create")

    assert isinstance(create_prompt, str)
    assert "InfoBlock.onClick" not in create_prompt
    assert "合法可点击 InfoBlock" not in create_prompt
    assert "不得绑定到 `InfoBlock`" in create_prompt


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
        "CardHeader",
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
        "common.md": ["contract"],
        "2x2.md": ["mapping"],
        "2x4.md": ["mapping"],
    }
    bodies = {}
    for filename, expected in expected_fragments.items():
        source = (root / filename).read_text(encoding="utf-8")
        fragments = dict(FRAGMENT.findall(source))
        assert list(fragments) == expected
        body = fragments.get(expected[0])
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
    common_index = references.index("combinations/common.md#contract")
    information_index = references.index("information/2x4.md#capacity")
    assert common_index == information_index + 1
    two_by_two_index = references.index("combinations/2x2.md#mapping")
    layout_two_by_two_index = references.index("layouts/2x2.md#s-layouts")
    assert two_by_two_index == layout_two_by_two_index + 1
    two_by_four_index = references.index("combinations/2x4.md#mapping")
    layout_two_by_four_index = references.index("layouts/2x4.md#w-layouts")
    assert two_by_four_index == layout_two_by_four_index + 1


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
        references.pop(0)
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
