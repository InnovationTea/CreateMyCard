"""直接读取 Compact 源模块，在内存中组装并缓存提示词；不生成文件。"""

import json
import re
from functools import lru_cache
from pathlib import Path

FRAGMENT = re.compile(r"<!-- prompt:([a-z0-9_-]+) -->\n(.*?)<!-- /prompt:\1 -->\n", re.S)
PROMPT_NAMES = frozenset(
    {
        "plan",
        "create",
        "edit",
        "repair",
        "argument_repair",
        "fewshot_2x2",
        "fewshot_2x4",
    }
)


def _inside(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"路径超出提示词目录：{relative}")
    return path


def _required(item: dict, key: str, value_type: type):
    if not isinstance(item, dict):
        raise ValueError("manifest 条目必须是对象")
    value = item.get(key)
    if not isinstance(value, value_type) or not value:
        raise ValueError(f"manifest 缺少有效 {key}：{item}")
    return value


def _read_sources(source_root: Path, modules: list) -> dict[str, dict[str, str]]:
    sources = {}
    for module in modules:
        filename = _required(module, "file", str)
        sizes = _required(module, "sizes", list)
        if not set(sizes).issubset({"2x2", "2x4"}):
            raise ValueError(f"未知适用尺寸：{filename}")
        if filename in sources:
            raise ValueError(f"模块重复：{filename}")
        content = _inside(source_root, filename).read_text(encoding="utf-8")
        fragments = {}
        for match in FRAGMENT.finditer(content):
            name, body = match.groups()
            if name in fragments:
                raise ValueError(f"片段重复：{filename}#{name}")
            fragments[name] = body
        remainder = FRAGMENT.sub("", content)
        if "<!-- prompt:" in remainder or "<!-- /prompt:" in remainder:
            raise ValueError(f"片段标记不闭合：{filename}")
        if not fragments:
            raise ValueError(f"模块没有提示词片段：{filename}")
        sources[filename] = fragments
    return sources


def assemble_prompts(source_root: Path, size: str | None = None) -> dict[str, str]:
    """按 manifest 顺序组装全部模型文本；维护说明和标记不进入正文。"""
    manifest = json.loads((source_root / "manifest.yaml").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("version") != 1:
        raise ValueError("不支持的 manifest 版本")
    if size is not None and size not in {"2x2", "2x4"}:
        raise ValueError(f"Unsupported Compact prompt size: {size}")
    modules = _required(manifest, "modules", list)
    sources = _read_sources(source_root, modules)
    module_sizes = {module["file"]: module["sizes"] for module in modules}
    for path in source_root.rglob("*.md"):
        if path.relative_to(source_root).as_posix() in sources:
            continue
        if "<!-- prompt:" in path.read_text(encoding="utf-8"):
            raise ValueError(f"源文件未登记：{path}")
    prompts = _required(manifest, "prompts", dict)
    if set(prompts) != PROMPT_NAMES:
        raise ValueError("manifest 必须声明全部七种 Compact 提示词")
    result = {}
    used = set()
    for prompt_name, references in prompts.items():
        if not isinstance(references, list) or not references:
            raise ValueError(f"提示词无片段：{prompt_name}")
        parts = []
        prompt_used = set()
        for reference in references:
            if not isinstance(reference, str):
                raise ValueError(f"提示词片段引用必须是字符串：{prompt_name}")
            file, separator, name = reference.partition("#")
            source = sources.get(file)
            if not separator or source is None or name not in source:
                raise ValueError(f"不存在的片段：{reference}")
            if reference in prompt_used:
                raise ValueError(f"片段重复加载：{reference}")
            prompt_used.add(reference)
            used.add(reference)
            if size is None or size in module_sizes[file]:
                parts.append(source[name])
        result[prompt_name] = "".join(parts)
    declared = set()
    for file, fragments in sources.items():
        for name in fragments:
            declared.add(f"{file}#{name}")
    if declared != used:
        raise ValueError(f"未加载的源片段：{sorted(declared - used)}")
    _check_fewshots(manifest, sources, prompts)
    return result


def _check_fewshots(manifest: dict, sources: dict[str, dict[str, str]], prompts: dict) -> None:
    index = _required(manifest, "fewshots", dict)
    for size in ("2x2", "2x4"):
        entries = _required(index, size, list)
        references = prompts.get(f"fewshot_{size}")
        if not isinstance(references, list):
            raise ValueError(f"缺少尺寸案例提示词：{size}")
        expected = []
        seen = set()
        for entry in entries:
            identifier = _required(entry, "id", str)
            reference = _required(entry, "source", str)
            if identifier in seen or not identifier.startswith(f"{size}-V"):
                raise ValueError(f"案例编号错误：{identifier}")
            seen.add(identifier)
            expected.append(reference)
            filename, separator, fragment = reference.partition("#")
            source = sources.get(filename)
            if not separator or source is None:
                raise ValueError(f"不存在的案例源：{reference}")
            content = source.get(fragment)
            if content is None:
                raise ValueError(f"不存在的案例片段：{reference}")
            if identifier not in content or "```json" not in content or "```genui" not in content:
                raise ValueError(f"案例缺少完整输入/输出：{identifier}")
        if references[1:] != expected:
            raise ValueError(f"案例索引与加载顺序不一致：{size}")


@lru_cache(maxsize=16)
def _cached_prompts(source_root: Path, size: str | None = None) -> dict[str, str]:
    try:
        return assemble_prompts(source_root, size)
    except OSError as error:
        raise ValueError(f"Compact prompt source not found or unreadable: {source_root}") from error


def read_prompt(source_root: Path, name: str, size: str | None = None) -> str:
    """同一源目录只加载一次；发布源模块后重启服务刷新缓存。"""
    if name not in PROMPT_NAMES:
        raise ValueError(f"Unknown Compact prompt: {name}")
    prompts = _cached_prompts(source_root.resolve(), size)
    content = prompts.get(name)
    if content is None:
        raise ValueError(f"Compact prompt not found: {name}")
    return content


@lru_cache(maxsize=32)
def read_static_prompt(source_root: Path, name: str, size: str) -> str:
    """独立装配静态增量，旧七种提示词的片段和返回内容不变。"""
    manifest = json.loads((source_root / "manifest.yaml").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("静态提示词 manifest 必须为对象。")
    profile = manifest.get("staticContent")
    if not isinstance(profile, dict) or profile.get("version") != "static-content-v1":
        raise ValueError("静态提示词资源未完整登记。")
    references = profile.get(name)
    if not isinstance(references, list) or not references:
        raise ValueError(f"缺少静态提示词 {name}。")
    if size not in {"2x2", "2x4"}:
        raise ValueError("静态提示词尺寸无效。")
    parts = []
    for reference in references:
        if not isinstance(reference, str):
            raise ValueError("静态提示词引用必须是字符串。")
        reference = reference.replace("{size}", size)
        filename, separator, fragment = reference.partition("#")
        content = _inside(source_root, filename).read_text(encoding="utf-8")
        if separator:
            found = None
            for match in FRAGMENT.finditer(content):
                if match.group(1) == fragment:
                    found = match.group(2)
                    break
            if found is None:
                raise ValueError(f"静态提示词共享片段不存在：{reference}")
            content = found
        if not content.strip():
            raise ValueError(f"静态提示词资源为空：{reference}")
        parts.append(content)
    result = "\n\n".join(parts)
    if name == "plan":
        from services.compact_reference_canvas import reference_dimension
        from services.static_text_capacity import static_content_contract

        contract = static_content_contract()
        budget = {
            "referenceOnly": True,
            "width": reference_dimension(size, "width"),
            "height": reference_dimension(size, "height"),
            "layout": contract.get("layout"),
            "text": contract.get("text"),
            "components": contract.get("components"),
        }
        result += (
            "\n\n# 本轮参考排版合同\n"
            "以下来自运行时共享合同，仅供云侧规划，不代表真实宿主尺寸。"
            "先扣安全区、标题和说明，再核算各字段与总高；字段分别合规不代表整卡可放。"
            "提交前在本次推理内压缩重复措辞和重组表达，不新增调用。\n"
            + json.dumps(budget, ensure_ascii=False, separators=(",", ":"))
        )
    if name == "fewshot":
        example_ids = profile.get("exampleIds")
        expected = example_ids.get(size) if isinstance(example_ids, dict) else None
        actual = re.findall(r"(?m)^## (2x[24]-V\d+)", result)
        if not expected or actual != expected:
            raise ValueError("静态案例登记与实际资源不一致。")
    return result
