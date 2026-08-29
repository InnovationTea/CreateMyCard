# -*- coding: utf-8 -*-
"""把 pipeline_combo 矩阵金样导出为端侧画廊数据集。

读取 ``tests/goldens/scenarios/1_pipeline/matrix/pipeline_combo/{normal,
fusion_ball}/`` 下的家庭金样（每个 2x2 模板 × 可选数据子集的端到端 DSL
快照，fusion_ball 为融球模式变体），在 eval 应用 rawfile 下生成
``pipeline_combo_gallery/`` 数据集：

    manifest.json                  schemaVersion ``pipeline-combo-gallery/2``，
                                   按业务分页签的组合清单
    families/<variant>/<family>.json   家庭金样逐字节拷贝（combinations 里
                                   每个组合携带 a2ui 消息数组与 templateIds）

`ProviderScenarioGalleryPage` 以 ``dataset: pipelineCombo`` 路由参数进入
组合画廊模式后，用该数据集把每个组合渲染成真实 A2UI 卡片；被管线拒绝的
组合（excludedCombinations）与结构性跳过的模板（_SKIPPED_TEMPLATES）以
失败瓦片展示原因。每个业务一个页签；每个用例通过 ``variantNormal`` /
``variantFusion`` 同时携带两个变体的金样来源，端侧「融球模式/原色模式」
按钮切换变体并就地把整批卡片重新渲染。每个用例另有简单顺序编号
``sampleId``（C001…，排序确定 → 编号确定），端侧瓦片标题优先显示它。

用法（在 cloud/ 目录下；genui_evaluation 与 CreateMyCard 是两个独立仓库，
必须显式给出画廊数据集的绝对路径）::

    python3 -m services.template_generation.test_support.golden_cli combo-gallery \\
        --dataset-dir <rawfile 绝对路径>/pipeline_combo_gallery
    # 或独立运行：
    python3 -m services.template_generation.test_support.combo_gallery \\
        --dataset-dir <rawfile 绝对路径>/pipeline_combo_gallery
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from services.template_generation.engine.cardplan.provider_bundle import (
    provider_template_layout_kind,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry

MATRIX_DIR = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "goldens"
    / "scenarios"
    / "1_pipeline"
    / "matrix"
    / "pipeline_combo"
)

# 画廊数据集目录名（位于 eval 应用仓库的 rawfile/ 下；两个仓库各自独立，
# 交叉路径一律由 --dataset-dir 显式传入，不做任何隐式拼接假设）。
GALLERY_DIRECTORY = "pipeline_combo_gallery"
SCHEMA_VERSION = "pipeline-combo-gallery/2"
OPERATION = "generateWidgetCardTerseDslNested2"

# 矩阵变体：金样子目录 → (清单内变体名, 显示名, 是否融球模式)。
VARIANTS: dict[str, tuple[str, str, bool]] = {
    "normal": ("normal", "原色", False),
    "fusion_ball": ("fusion", "融球", True),
}

# provider_id -> (显示名, slug)；与 provider_scenario_gallery manifest 一致。
PROVIDER_DISPLAY: dict[str, tuple[str, str]] = {
    "com.huawei.weather.cli": ("天气", "weather"),
    "com.huawei.battery.cli": ("设备电量", "battery"),
    "com.huawei.calendar.cli": ("日历日程", "calendar"),
    "com.huawei.countdown.cli": ("倒计时", "countdown"),
    "com.huawei.earphone.cli": ("蓝牙耳机", "earphone"),
    "com.huawei.health-sport.cli": ("运动健康", "health-sport"),
    "com.huawei.system-memory.cli": ("系统内存", "system-memory"),
    "com.huawei.app-usage.cli": ("应用时长", "app-usage"),
    "com.huawei.action.cli": ("动作", "action"),
}


def absent_fields(key: str, optional_names: list[str]) -> list[str]:
    """组合键 -> 缺席的可选字段名（与 golden_cli _cmd_template 同一语义）。"""
    if key == "all":
        return []
    if key == "none":
        return list(optional_names)
    if key.startswith("absent_"):
        return key[len("absent_"):].split("+")
    return []


def combo_label(key: str, absent: list[str]) -> str:
    if key == "all":
        return "全部字段"
    if key == "none":
        return "全部可选缺席"
    return "缺 " + "+".join(absent)


def natural_combo_key(key: str, absent: list[str]) -> tuple[int, str]:
    return (len(absent), key)


def _provider_meta(provider_id: str) -> tuple[str, str]:
    if provider_id in PROVIDER_DISPLAY:
        return PROVIDER_DISPLAY[provider_id]
    slug = provider_id.removeprefix("com.huawei.").removesuffix(".cli")
    return (provider_id, slug)


def build_combo_gallery() -> dict[str, Any]:
    """构建 manifest 数据结构（不写盘）；同时返回家庭文件拷贝计划。

    每个业务一个 Provider 页签；每个组合一条用例，通过 ``variantNormal`` /
    ``variantFusion`` 同时携带两个变体的金样来源（文件相对路径 + 状态 +
    拒绝原因），端侧切换变体时无需重载 manifest。
    """
    from services.template_generation.tests.test_template_pipeline_matrix import (
        _SKIPPED_TEMPLATES,
        combo_sample_ids,
    )

    registry = CardPlanRegistry(disabled_provider_ids=(), disabled_template_ids=())
    sub_dir_by_variant = {meta[0]: sub_dir for sub_dir, meta in VARIANTS.items()}
    # variant_name -> {template_id: (family_path, family_payload)}
    family_index: dict[str, dict[str, tuple[Path, dict[str, Any]]]] = {
        meta[0]: {} for meta in VARIANTS.values()
    }
    copy_plan: list[tuple[Path, str]] = []
    by_variant: dict[str, dict[str, int]] = {
        meta[0]: {"families": 0, "rendered": 0, "refused": 0, "skipped": 0}
        for meta in VARIANTS.values()
    }

    for sub_dir, (variant_name, _label, fusion_enabled) in VARIANTS.items():
        for family_path in sorted((MATRIX_DIR / sub_dir).glob("*.json")):
            family = json.loads(family_path.read_text(encoding="utf-8"))
            if bool(family.get("fusionBall")) != fusion_enabled:
                raise ValueError(
                    f"{sub_dir}/{family_path.name}: fusionBall={family.get('fusionBall')} "
                    f"与目录变体 {sub_dir} 不一致"
                )
            family_index[variant_name][family["templateId"]] = (family_path, family)
            copy_plan.append((family_path, f"families/{sub_dir}/{family_path.name}"))
            by_variant[variant_name]["families"] += 1

    def variant_source(
        variant_name: str, template_id: str, key: str, optional_names: list[str],
    ) -> dict[str, Any]:
        """单变体 × 单组合的金样来源（状态 + 相对文件 + 拒绝/缺失原因）。"""
        entry = family_index[variant_name].get(template_id)
        if entry is None:
            return {
                "a2uiFile": "",
                "messageCount": 0,
                "reason": "该变体缺少家庭金样",
                "status": "missing",
            }
        family_path, family = entry
        relative = f"families/{sub_dir_by_variant[variant_name]}/{family_path.name}"
        if key in family.get("combinations", {}):
            messages = family["combinations"][key].get("a2ui")
            if not isinstance(messages, list) or not messages:
                raise ValueError(
                    f"{relative}: combination {key!r} 没有可渲染的 a2ui 消息数组"
                )
            for index, message in enumerate(messages):
                if not isinstance(message, dict):
                    raise ValueError(
                        f"{relative}: combination {key!r} 消息 {index} 不是对象"
                    )
            return {
                "a2uiFile": relative,
                "messageCount": len(messages),
                "reason": "",
                "status": "success",
            }
        if key in family.get("excludedCombinations", {}):
            return {
                "a2uiFile": relative,
                "messageCount": 0,
                "reason": str(family["excludedCombinations"][key]),
                "status": "refused",
            }
        return {
            "a2uiFile": "",
            "messageCount": 0,
            "reason": "该变体无此组合金样",
            "status": "missing",
        }

    def provider_tab(provider_id: str, provider_name: str, provider_slug: str) -> dict[str, Any]:
        return providers.setdefault(
            provider_id,
            {
                "providerId": provider_id,
                "providerName": provider_name,
                "providerSlug": provider_slug,
                "cases": [],
            },
        )

    providers: dict[str, dict[str, Any]] = {}
    template_ids = sorted(
        set(family_index["normal"]) | set(family_index["fusion"])
    )
    for template_id in template_ids:
        normal_entry = family_index["normal"].get(template_id)
        fusion_entry = family_index["fusion"].get(template_id)
        reference = normal_entry or fusion_entry
        assert reference is not None
        _ref_path, ref_family = reference
        definition = registry.require_template(template_id)
        provider_id = definition.provider_id
        provider_name, provider_slug = _provider_meta(provider_id)
        layout_kind = provider_template_layout_kind(template_id)
        optional_names = sorted(definition.variants[0].optional_bindings)
        business_id = definition.business_id or ""
        provider = provider_tab(provider_id, provider_name, provider_slug)

        keys: set[str] = set()
        for entry in (normal_entry, fusion_entry):
            if entry is None:
                continue
            _path, family = entry
            keys.update(family.get("combinations", {}))
            keys.update(family.get("excludedCombinations", {}))
        if not keys:
            continue  # 两个变体都没有组合：按 _SKIPPED_TEMPLATES 伪用例兜底。
        for key in sorted(keys, key=lambda item: natural_combo_key(
            item, absent_fields(item, optional_names)
        )):
            variant_normal = variant_source("normal", template_id, key, optional_names)
            variant_fusion = variant_source("fusion", template_id, key, optional_names)
            statuses = {variant_normal["status"], variant_fusion["status"]}
            case_status = (
                "success" if "success" in statuses
                else "refused" if "refused" in statuses
                else "skipped"
            )
            for name, source in (
                ("normal", variant_normal), ("fusion", variant_fusion)
            ):
                if source["status"] == "success":
                    by_variant[name]["rendered"] += 1
                elif source["status"] == "refused":
                    by_variant[name]["refused"] += 1
            absent = absent_fields(key, optional_names)
            provider["cases"].append(
                {
                    "a2uiFile": variant_normal["a2uiFile"],
                    "absentFields": absent,
                    "businessId": business_id,
                    "businessName": provider_name,
                    "caseId": f"{template_id.split('@')[0].lower()}__{key}",
                    "comboKey": key,
                    "comboLabel": combo_label(key, absent),
                    "expectedLayout": ref_family.get("layout", ""),
                    "layoutKind": layout_kind,
                    "messageCount": variant_normal["messageCount"],
                    "providerId": provider_id,
                    "providerName": provider_name,
                    "providerSlug": provider_slug,
                    "size": ref_family.get("size", "2x2"),
                    "status": case_status,
                    "templateId": template_id,
                    "templateSuffix": layout_kind,
                    "variantFusion": variant_fusion,
                    "variantNormal": variant_normal,
                }
            )

    # 结构性跳过的模板没有家庭金样：以 skipped 瓦片说明原因，保证
    # “每个 2x2 模板”都在画廊里可见（两个变体同样标记）。
    for template_id in sorted(_SKIPPED_TEMPLATES):
        if template_id in family_index["normal"] or template_id in family_index["fusion"]:
            continue
        try:
            definition = registry.require_template(template_id)
            provider_id = definition.provider_id
            layout_kind = provider_template_layout_kind(template_id)
            business_id = definition.business_id or ""
        except Exception:
            provider_id = ""
            layout_kind = ""
            business_id = ""
        provider_name, provider_slug = _provider_meta(provider_id)
        provider = provider_tab(provider_id, provider_name, provider_slug)
        skip_source = {
            "a2uiFile": "",
            "messageCount": 0,
            "reason": str(_SKIPPED_TEMPLATES[template_id]),
            "status": "skipped",
        }
        provider["cases"].append(
            {
                "a2uiFile": "",
                "absentFields": [],
                "businessId": business_id,
                "businessName": provider_name,
                "caseId": f"{template_id.split('@')[0].lower()}__skipped",
                "comboKey": "",
                "comboLabel": "无组合金样",
                "expectedLayout": "",
                "layoutKind": layout_kind,
                "messageCount": 0,
                "providerId": provider_id,
                "providerName": provider_name,
                "providerSlug": provider_slug,
                "size": "2x2",
                "status": "skipped",
                "templateId": template_id,
                "templateSuffix": layout_kind,
                "variantFusion": dict(skip_source),
                "variantNormal": dict(skip_source),
            }
        )

    for provider in providers.values():
        provider["cases"].sort(key=lambda case: (case["templateId"], case["caseId"]))
        for name in by_variant:
            for case in provider["cases"]:
                source = (
                    case["variantNormal"] if name == "normal" else case["variantFusion"]
                )
                if source["status"] == "skipped":
                    by_variant[name]["skipped"] += 1
    # 简单稳定的顺序编号（C001…）：单一事实来源是矩阵模块的
    # combo_sample_ids()，同一编号已固化在家族金样顶层的 ``sampleIds``
    # 映射里；这里按 (templateId, comboKey) 查表复用，两侧不会漂移。
    sample_ids = combo_sample_ids()
    for provider_id in sorted(providers):
        for case in providers[provider_id]["cases"]:
            combo_key = (
                "skipped" if case["status"] == "skipped" else case["comboKey"]
            )
            case["sampleId"] = sample_ids[(case["templateId"], combo_key)]
    total_cases = sum(len(p["cases"]) for p in providers.values())
    totals = {
        "families": sum(stats["families"] for stats in by_variant.values()),
        "rendered": sum(stats["rendered"] for stats in by_variant.values()),
        "refused": sum(stats["refused"] for stats in by_variant.values()),
        "skipped": sum(stats["skipped"] for stats in by_variant.values()),
    }
    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "dataset": "pipelineCombo",
        "operation": OPERATION,
        "cardSize": "2x2",
        "counts": {
            **totals,
            "byVariant": by_variant,
            "cases": total_cases,
            "total": total_cases,
        },
        "providers": [providers[key] for key in sorted(providers)],
    }
    return {"manifest": manifest, "copyPlan": copy_plan}


def export_combo_gallery(dataset_dir: Path) -> dict[str, Any]:
    """导出数据集到指定的画廊数据集目录，清理不再存在的家庭文件。

    ``dataset_dir`` 是 ``<rawfile>/pipeline_combo_gallery`` 的绝对路径；
    其父目录（rawfile）必须已存在，避免拼写错误静默新建目录树。
    """
    built = build_combo_gallery()
    dataset_dir = dataset_dir.expanduser().resolve()
    if not dataset_dir.parent.is_dir():
        raise ValueError(
            f"dataset parent directory not found: {dataset_dir.parent} — "
            "pass the absolute path to the eval app's "
            "<rawfile>/pipeline_combo_gallery"
        )
    gallery_dir = dataset_dir
    families_dir = gallery_dir / "families"
    families_dir.mkdir(parents=True, exist_ok=True)
    for source, relative in built["copyPlan"]:
        target = gallery_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    keep = {relative for _source, relative in built["copyPlan"]}
    for stale in families_dir.rglob("*.json"):
        if f"families/{stale.relative_to(families_dir).as_posix()}" not in keep:
            stale.unlink()
    for variant_dir in ("normal", "fusion_ball"):
        (families_dir / variant_dir).mkdir(parents=True, exist_ok=True)
    manifest_path = gallery_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(built["manifest"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "manifestPath": manifest_path,
        "galleryDir": gallery_dir,
        "manifest": built["manifest"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="combo_gallery",
        description="Export the pipeline_combo golden matrix as the on-device combo gallery dataset.",
    )
    parser.add_argument(
        "--dataset-dir",
        required=True,
        metavar="PATH",
        help="absolute path to the eval app's gallery dataset directory "
        "(<rawfile>/pipeline_combo_gallery); the eval app is a separate "
        "repository, so no default is assumed",
    )
    args = parser.parse_args(argv)
    try:
        result = export_combo_gallery(Path(args.dataset_dir))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    counts = result["manifest"]["counts"]
    print(
        f"exported {counts['families']} families ({counts['cases']} combo cases) "
        f"-> {result['galleryDir']} "
        f"(rendered {counts['rendered']}, refused {counts['refused']}, "
        f"skipped {counts['skipped']})"
    )
    for name, stats in counts.get("byVariant", {}).items():
        print(
            f"  variant {name}: {stats['families']} families · "
            f"{stats['rendered']} rendered · {stats['refused']} refused · "
            f"{stats['skipped']} skipped"
        )
    print(f"manifest: {result['manifestPath']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
