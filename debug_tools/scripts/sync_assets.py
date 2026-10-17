"""按云侧素材清单同步浏览器预览与真机工程的图片，保留未登记的工程资源。"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CAPABILITIES_ROOT = Path("widget_service/cloud/data/capabilities")
TARGETS = {
    "browser": Path("render/platform/public"),
    "device": Path("debug_tools/a2ui_render/entry/src/main"),
}


@dataclass(frozen=True)
class Asset:
    relative: Path
    source: Path
    sha256: str


@dataclass
class Result:
    target: str
    checked: int = 0
    missing: list[str] = field(default_factory=list)
    different: list[str] = field(default_factory=list)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def registered_assets(root: Path) -> list[Asset]:
    manifests = sorted((root / CAPABILITIES_ROOT).glob("*/asset_capabilities.json"))
    if not manifests:
        raise ValueError("云侧素材清单不存在")
    assets: list[Asset] = []
    seen: set[str] = set()
    for manifest in manifests:
        records = json.loads(manifest.read_text(encoding="utf-8-sig"))
        if not isinstance(records, list):
            raise ValueError(f"素材清单必须是数组：{manifest}")
        for record in records:
            if not isinstance(record, dict):
                raise ValueError(f"素材记录必须是对象：{manifest}")
            src = record.get("src")
            if not isinstance(src, str) or not src:
                raise ValueError(f"素材缺少 src：{manifest}")
            relative = PurePosixPath(src)
            valid_prefix = relative.parts[:3] == ("resources", "base", "media")
            if not valid_prefix or ".." in relative.parts or "\\" in src:
                raise ValueError(f"素材路径必须位于 resources/base/media：{src}")
            if src in seen:
                continue
            seen.add(src)
            source = (root / src).resolve()
            if not source.is_relative_to(root.resolve()) or not source.is_file():
                raise ValueError(f"登记素材源文件不存在或越界：{src}")
            assets.append(Asset(Path(src), source, digest(source)))
    return assets


def synchronize(root: Path, assets: list[Asset], *, write: bool) -> list[Result]:
    results: list[Result] = []
    # 先检查所有目标边界，避免非法目标造成部分同步。
    for target in TARGETS.values():
        base = (root / target).resolve()
        for asset in assets:
            destination = (base / asset.relative).resolve()
            if not destination.is_relative_to(base):
                raise ValueError(f"素材目标越界：{destination}")
            if destination.exists() and not destination.is_file():
                raise ValueError(f"素材目标不是文件：{destination}")
    for name, target in TARGETS.items():
        result = Result(name)
        base = root / target
        for asset in assets:
            destination = base / asset.relative
            result.checked += 1
            if not destination.is_file():
                result.missing.append(asset.relative.as_posix())
            elif digest(destination) != asset.sha256:
                result.different.append(asset.relative.as_posix())
            else:
                continue
            if write:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(asset.source, destination)
                if digest(destination) != asset.sha256:
                    raise OSError(f"素材同步后摘要不一致：{destination}")
        results.append(result)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="只核对清单、文件与 SHA-256")
    mode.add_argument("--sync", action="store_true", help="补齐或覆盖登记素材，保留其它文件")
    arguments = parser.parse_args()
    assets = registered_assets(REPOSITORY_ROOT)
    results = synchronize(REPOSITORY_ROOT, assets, write=arguments.sync)
    changed = False
    for result in results:
        print(f"{result.target}: 检查 {result.checked}，缺失 {len(result.missing)}，"
              f"内容不同 {len(result.different)}")
        for src in result.missing + result.different:
            print(f"  {src}")
        changed = changed or bool(result.missing or result.different)
    if arguments.sync:
        print("素材同步完成，未删除清单外的工程资源。")
    return int(changed and arguments.check)


if __name__ == "__main__":
    raise SystemExit(main())
