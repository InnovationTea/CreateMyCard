"""显式迁移历史批跑素材候选到新目录；不修改原始请求或线上能力注册表。"""

import argparse
import json
from pathlib import Path


def migrate(
    input_dir: Path, output_dir: Path, registry_file: Path, mapping: dict[str, str],
) -> list:
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists() or output_dir.is_relative_to(input_dir):
        raise ValueError("输出目录必须不存在且位于输入目录之外")
    registry = json.loads(registry_file.read_text(encoding="utf-8"))
    if not isinstance(registry, list):
        raise ValueError("素材注册表必须为数组")
    known = set()
    for entry in registry:
        if isinstance(entry, dict) and isinstance(entry.get("id"), str):
            known.add(entry.get("id"))
    if not mapping or any(target not in known for target in mapping.values()):
        raise ValueError("必须显式提供映射，且每个目标 ID 必须已注册")
    specs = sorted(input_dir.glob("Q*.json"))
    if not specs:
        raise ValueError("输入目录没有 Q*.json 用例")
    prepared = []
    changes = []
    for path in specs:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"{path.name}: 请求必须为对象")
        containers = [("", payload)]
        content = payload.get("content")
        if isinstance(content, dict):
            containers.append(("/content", content))
        for prefix, container in containers:
            candidates = container.get("candidateAssetIds")
            if candidates is None:
                continue
            if not isinstance(candidates, list) or not all(
                isinstance(item, str) for item in candidates
            ):
                raise ValueError(f"{path.name}: candidateAssetIds 必须为字符串数组")
            migrated = []
            for index, original in enumerate(candidates):
                target = mapping.get(original, original)
                if target not in known:
                    raise ValueError(f"{path.name}: 存在未映射且未注册的素材 {target}")
                migrated.append(target)
                if target != original:
                    changes.append({"file": path.name,
                                    "path": f"{prefix}/candidateAssetIds/{index}",
                                    "from": original, "to": target})
            container["candidateAssetIds"] = migrated
        prepared.append((path.name, payload))
    # 全部预检查完成才写新目录，存在的目录或文件绝不覆盖。
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, payload in prepared:
        with (output_dir / name).open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    with (output_dir / "asset_migration_report.json").open("x", encoding="utf-8") as stream:
        json.dump({"registry": registry_file.name, "changes": changes},
                  stream, ensure_ascii=False, indent=2)
    return changes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--asset-map", action="append", required=True, metavar="OLD=NEW")
    args = parser.parse_args()
    mapping = {}
    for item in args.asset_map:
        old, separator, new = item.partition("=")
        if not separator or not old or not new or old in mapping:
            parser.error("映射必须为唯一的 OLD=NEW")
        mapping[old] = new
    changes = migrate(args.input_dir, args.output_dir, args.registry, mapping)
    print(f"独立副本已生成：{len(changes)} 处素材替换；原始输入未修改")


if __name__ == "__main__":
    main()
