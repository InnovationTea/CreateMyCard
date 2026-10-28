"""按职责和尺寸装配静态阶段合同；维护元信息不进入模型上下文。"""

import json
import re
from functools import lru_cache
from pathlib import Path

from services.compact_prompt_loader import FRAGMENT, _inside, _required

STATIC_STAGES = ("create", "plan", "dsl", "repair", "fewshot")
_HEADER = re.compile(r"\A---\r?\n.*?\r?\n---(?:\r?\n|\Z)", re.S)


def _model_body(content: str) -> str:
    if content.startswith("---\n") or content.startswith("---\r\n"):
        match = _HEADER.match(content)
        if match is None:
            raise ValueError("静态模块维护头未闭合。")
        return content.removeprefix(match.group()).lstrip("\r\n")
    return content


def _module_sizes(profile: dict) -> dict[str, list[str]]:
    sizes_by_file = {}
    for module in _required(profile, "modules", list):
        filename = _required(module, "file", str)
        sizes = _required(module, "sizes", list)
        for size in sizes:
            if not isinstance(size, str) or size not in {"2x2", "2x4"}:
                raise ValueError(f"静态模块尺寸无效：{filename}")
        if len(sizes) != len(set(sizes)):
            raise ValueError(f"静态模块尺寸重复：{filename}")
        if filename in sizes_by_file:
            raise ValueError(f"静态模块重复登记：{filename}")
        sizes_by_file[filename] = sizes
    return sizes_by_file


def _reference_content(root: Path, reference: str, cache: dict[str, str]) -> str:
    filename, separator, fragment = reference.partition("#")
    if filename not in cache:
        cache[filename] = _model_body(_inside(root, filename).read_text(encoding="utf-8"))
    content = cache.get(filename)
    if not isinstance(content, str):
        raise ValueError(f"静态模块内容无效：{filename}")
    if separator:
        content = next(
            (match.group(2) for match in FRAGMENT.finditer(content) if match.group(1) == fragment),
            None,
        )
        if content is None:
            raise ValueError(f"静态提示词共享片段不存在：{reference}")
    if not content.strip():
        raise ValueError(f"静态提示词资源为空：{reference}")
    return content


def _stage_content(root, profile, sizes_by_file, name, size, cache, used, references) -> str:
    parts = []
    seen = set()
    for reference in _required(profile, name, list):
        if not isinstance(reference, str):
            raise ValueError("静态提示词引用必须是字符串。")
        reference = reference.replace("{size}", size)
        filename = reference.partition("#")[0]
        sizes = sizes_by_file.get(filename)
        if sizes is None:
            raise ValueError(f"静态提示词模块未登记：{filename}")
        if reference in seen:
            raise ValueError(f"静态提示词重复加载：{reference}")
        seen.add(reference)
        if size not in sizes:
            continue
        if reference in references:
            raise ValueError(f"静态提示词跨阶段重复加载：{reference}")
        references.add(reference)
        parts.append(_reference_content(root, reference, cache))
        used.add(filename)
    if not parts:
        raise ValueError(f"当前尺寸没有静态提示词：{name}/{size}")
    return "\n\n".join(parts)


def _plan_reference(size: str) -> str:
    from services.compact_reference_canvas import reference_dimension

    budget = {
        "referenceOnly": True,
        "width": reference_dimension(size, "width"),
        "height": reference_dimension(size, "height"),
    }
    return (
        "\n\n# 本轮参考画布\n"
        "沿用初始共享文字与容量合同；先扣安全区、标题和说明，再核算字段与总高。"
        "参考画布不代表真实宿主尺寸；字段分别合规不代表整卡可放。\n"
        + json.dumps(budget, ensure_ascii=False, separators=(",", ":"))
    )


@lru_cache(maxsize=16)
def _static_prompts(root: Path, size: str) -> dict[str, str]:
    manifest = json.loads((root / "manifest.yaml").read_text(encoding="utf-8"))
    profile = manifest.get("staticContent") if isinstance(manifest, dict) else None
    if not isinstance(profile, dict) or profile.get("version") != "static-content-v1":
        raise ValueError("静态提示词资源未完整登记。")
    sizes_by_file = _module_sizes(profile)
    cache = {}
    used = set()
    references = set()
    prompts = {}
    for name in STATIC_STAGES:
        prompts[name] = _stage_content(
            root, profile, sizes_by_file, name, size, cache, used, references,
        )
    expected = {filename for filename, sizes in sizes_by_file.items() if size in sizes}
    if used != expected:
        raise ValueError(f"静态模块未加载：{sorted(expected - used)}")
    example_ids = profile.get("exampleIds")
    identifiers = example_ids.get(size) if isinstance(example_ids, dict) else None
    actual = re.findall(r"(?m)^## (2x[24]-V\d+)", prompts.get("fewshot", ""))
    if not identifiers or actual != identifiers:
        raise ValueError("静态案例登记与实际资源不一致。")
    prompts["plan"] += _plan_reference(size)
    return prompts


def read_static_source(root: Path, name: str, size: str) -> str:
    if name not in STATIC_STAGES:
        raise ValueError(f"未知静态提示词阶段：{name}")
    if size not in {"2x2", "2x4"}:
        raise ValueError("静态提示词尺寸无效。")
    content = _static_prompts(root.resolve(), size).get(name)
    if not isinstance(content, str) or not content:
        raise ValueError(f"静态提示词资源为空：{name}")
    return content
