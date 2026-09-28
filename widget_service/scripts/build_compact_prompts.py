"""从模块化源构建 Compact 提示词；--check 只校验，不写文件。

manifest 使用 YAML 1.2 的 JSON 子集，构建只依赖 Python 标准库。
运行：python scripts/build_compact_prompts.py [--check]
"""

import argparse
import json
import re
from pathlib import Path

DEFAULT_BUNDLE = (
    Path(__file__).resolve().parents[1] / "cloud/data/protocol_profiles/design-compact-dsl-fusion"
)
FRAGMENT = re.compile(r"<!-- prompt:([a-z0-9_-]+) -->\n(.*?)<!-- /prompt:\1 -->\n", re.S)


def _inside(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"路径超出提示词目录：{relative}")
    return path


def _required(item: dict, key: str, value_type: type):
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
            raise ValueError(f"模块没有可构建片段：{filename}")
        sources[filename] = fragments
    return sources


def compile_bundle(bundle: Path = DEFAULT_BUNDLE) -> dict[str, str]:
    """构建全部模型文本；维护说明和 manifest 不进入返回值。"""
    source_root = bundle / "prompt_source"
    manifest = json.loads((source_root / "manifest.yaml").read_text(encoding="utf-8"))
    if manifest.get("version") != 1:
        raise ValueError("不支持的 manifest 版本")
    sources = _read_sources(source_root, _required(manifest, "modules", list))
    for path in source_root.rglob("*.md"):
        if path.relative_to(source_root).as_posix() in sources:
            continue
        if "<!-- prompt:" in path.read_text(encoding="utf-8"):
            raise ValueError(f"源文件未登记：{path}")
    products = _required(manifest, "products", dict)
    result = {}
    used = set()
    for filename, references in products.items():
        if Path(filename).name != filename or not filename.endswith(".md"):
            raise ValueError(f"非法产物文件名：{filename}")
        if not isinstance(references, list) or not references:
            raise ValueError(f"产物无片段：{filename}")
        parts = []
        for reference in references:
            file, separator, name = reference.partition("#")
            source = sources.get(file)
            if not separator or source is None or name not in source:
                raise ValueError(f"不存在的片段：{reference}")
            if reference in used:
                raise ValueError(f"片段重复加载：{reference}")
            used.add(reference)
            parts.append(source[name])
        result[filename] = "".join(parts)
    declared = set()
    for file, fragments in sources.items():
        for name in fragments:
            declared.add(f"{file}#{name}")
    if declared != used:
        raise ValueError(f"未加载的源片段：{sorted(declared - used)}")
    _check_fewshots(manifest, source_root, products)
    return result


def _check_fewshots(manifest: dict, source_root: Path, products: dict) -> None:
    index = _required(manifest, "fewshots", dict)
    for size in ("2x2", "2x4"):
        entries = _required(index, size, list)
        references = products.get(f"FEWSHOT_{size}.md")
        if not isinstance(references, list):
            raise ValueError(f"缺少尺寸案例产物：{size}")
        expected = []
        seen = set()
        for entry in entries:
            identifier = _required(entry, "id", str)
            reference = _required(entry, "source", str)
            if identifier in seen or not identifier.startswith(f"{size}-V"):
                raise ValueError(f"案例编号错误：{identifier}")
            seen.add(identifier)
            expected.append(reference)
            filename = reference.partition("#")[0]
            content = _inside(source_root, filename).read_text(encoding="utf-8")
            if identifier not in content or "```json" not in content or "```genui" not in content:
                raise ValueError(f"案例缺少完整输入/输出：{identifier}")
        if references[1:] != expected:
            raise ValueError(f"案例索引与加载顺序不一致：{size}")


def build(bundle: Path = DEFAULT_BUNDLE, *, check: bool = False) -> list[str]:
    """返回不同步的产物；正常构建时覆盖这些确定性的产物。"""
    products = compile_bundle(bundle)
    destination = bundle / "generated"
    changed = []
    for filename, content in products.items():
        path = destination / filename
        encoded = content.encode("utf-8")
        if path.is_file() and path.read_bytes() == encoded:
            continue
        changed.append(filename)
        if not check:
            destination.mkdir(parents=True, exist_ok=True)
            path.write_bytes(encoded)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="只检查源与产物一致性")
    args = parser.parse_args()
    changed = build(check=args.check)
    if args.check and changed:
        print("提示词产物未同步：" + ", ".join(changed))
        return 1
    print("提示词产物一致" if args.check else f"已更新 {len(changed)} 个提示词产物")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
