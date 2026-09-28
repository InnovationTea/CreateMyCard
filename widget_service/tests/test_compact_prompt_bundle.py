"""提示词拆分的构建、路由与模型输入等价回归；不调用线上模型。"""

import json
import shutil
from pathlib import Path

import pytest
from scripts.build_compact_prompts import DEFAULT_BUNDLE, FRAGMENT, build, compile_bundle

from config.config import get_settings
from services.protocol_registry import (
    DESIGN_COMPACT_PROFILE_ID,
    A2UIProtocolRegistry,
)


def test_compiled_prompts_are_model_facing() -> None:
    products = compile_bundle()
    assert products
    for content in products.values():
        assert "<!-- prompt:" not in content
        assert "维护源" not in content


def test_generated_files_are_current() -> None:
    assert build(check=True) == []


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_fewshot_source_is_one_document_per_size(size: str) -> None:
    root = DEFAULT_BUNDLE / "prompt_source"
    source = root / "fewshots" / f"{size}.md"
    assert not list((root / "fewshots" / size).rglob("*.md"))
    fragments = dict(FRAGMENT.findall(source.read_text(encoding="utf-8")))
    expected = ["preamble"]
    example_count = 16 if size == "2x2" else 15
    expected.extend(f"example-v{index:02d}" for index in range(example_count))
    assert list(fragments) == expected
    manifest = json.loads((root / "manifest.yaml").read_text(encoding="utf-8"))
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
    bundle = tmp_path / "bundle"
    shutil.copytree(DEFAULT_BUNDLE, bundle)
    source = bundle / "prompt_source/fewshots" / f"{size}.md"
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
        compile_bundle(bundle)


@pytest.mark.parametrize(
    "method,filename",
    [
        ("read_design_prompt", "PROMPT.md"),
        ("read_design_edit_prompt", "EDIT_SYSTEM_PROMPT.md"),
        ("read_design_repair_prompt", "REPAIR_SYSTEM_PROMPT.md"),
        ("read_design_argument_repair_prompt", "ARGUMENT_REPAIR_SYSTEM_PROMPT.md"),
    ],
)
def test_registry_uses_generated_only(method: str, filename: str, tmp_path: Path) -> None:
    old = tmp_path / DESIGN_COMPACT_PROFILE_ID
    old.mkdir()
    (old / filename).write_text("旧路径不得回退", encoding="utf-8")
    read = getattr(A2UIProtocolRegistry, method)
    with pytest.raises(ValueError, match="not found"):
        read(DESIGN_COMPACT_PROFILE_ID, tmp_path)
    new = A2UIProtocolRegistry.design_prompt_directory(DESIGN_COMPACT_PROFILE_ID, tmp_path)
    new.mkdir(parents=True)
    (new / filename).write_text("新产物", encoding="utf-8")
    assert read(DESIGN_COMPACT_PROFILE_ID, tmp_path) == "新产物"


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_fewshot_uses_generated_only(size: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not found"):
        A2UIProtocolRegistry.read_design_few_shot(DESIGN_COMPACT_PROFILE_ID, size, tmp_path)
    actual = A2UIProtocolRegistry.read_design_few_shot(DESIGN_COMPACT_PROFILE_ID, size)
    expected = (DEFAULT_BUNDLE / "generated" / f"FEWSHOT_{size}.md").read_text(encoding="utf-8")
    assert actual == expected


def test_unknown_fewshot_size_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        A2UIProtocolRegistry.read_design_few_shot(DESIGN_COMPACT_PROFILE_ID, "../PROMPT")


def test_legacy_prompt_files_are_removed() -> None:
    old = DEFAULT_BUNDLE.with_name(DESIGN_COMPACT_PROFILE_ID)
    assert (old / "protocol.json").is_file()
    for filename in compile_bundle():
        assert not (old / filename).exists()


def test_default_config_uses_same_generated_prompts() -> None:
    settings = get_settings()
    for key, method in (
        ("system.prompt", "read_design_prompt"),
        ("edit.system.prompt", "read_design_edit_prompt"),
        ("repair.system.prompt", "read_design_repair_prompt"),
    ):
        assert settings.CONFIG.get(key) == getattr(A2UIProtocolRegistry, method)(
            DESIGN_COMPACT_PROFILE_ID
        )


def test_check_detects_source_edit_without_writing(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    shutil.copytree(DEFAULT_BUNDLE, bundle)
    source = bundle / "prompt_source/core.md"
    original = source.read_text(encoding="utf-8")
    source.write_text(original.replace("你是 HarmonyOS", "你是测试 HarmonyOS", 1), encoding="utf-8")
    generated = bundle / "generated/PROMPT.md"
    before = generated.read_bytes()
    assert build(bundle, check=True) == ["PROMPT.md"]
    assert generated.read_bytes() == before
    assert build(bundle) == ["PROMPT.md"]
    assert build(bundle, check=True) == []


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "escape", "size", "orphan"])
def test_invalid_manifest_is_rejected(tmp_path: Path, mutation: str) -> None:
    bundle = tmp_path / "bundle"
    shutil.copytree(DEFAULT_BUNDLE, bundle)
    path = bundle / "prompt_source/manifest.yaml"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    products = manifest.get("products")
    modules = manifest.get("modules")
    assert isinstance(products, dict) and isinstance(modules, list)
    references = products.get("PROMPT.md")
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
        compile_bundle(bundle)


def test_unclosed_fragment_is_rejected(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    shutil.copytree(DEFAULT_BUNDLE, bundle)
    source = bundle / "prompt_source/core.md"
    original = source.read_text(encoding="utf-8")
    source.write_text(original.replace("<!-- /prompt:identity -->", "", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="不闭合"):
        compile_bundle(bundle)


def test_unregistered_source_is_rejected(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    shutil.copytree(DEFAULT_BUNDLE, bundle)
    source = bundle / "prompt_source/unregistered.md"
    source.write_text("<!-- prompt:new -->\n规则\n<!-- /prompt:new -->\n", encoding="utf-8")
    with pytest.raises(ValueError, match="未登记"):
        compile_bundle(bundle)
