"""审计指定能力清单的字段语义与通用模板覆盖；不把叶字段覆盖等同于列表或真机覆盖。"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from services.template_generation.engine.cardplan.general_semantics import (
    field_presentation,
    general_family_is_eligible,
    general_field_is_allowed,
)
from services.template_generation.engine.cardplan.registry import CardPlanRegistry

CAPABILITIES = Path(__file__).resolve().parents[3] / (
    "data/capabilities/app-11.7.5.205_rom-6.0/data_capabilities.json"
)


def schema_leaves(node: dict[str, Any], path: str = "") -> list[tuple[str, dict[str, Any]]]:
    leaves: list[tuple[str, dict[str, Any]]] = []
    if node.get("type") == "object":
        for name, field in node.get("properties", {}).items():
            leaves.extend(schema_leaves(field, path + "/" + name))
    elif node.get("type") == "array":
        leaves.extend(schema_leaves(node.get("items", {}), path + "/*"))
    else:
        leaves.append((path, node))
    return leaves


def build_audit(registry: CardPlanRegistry, capabilities: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    by_capability: list[dict[str, Any]] = []
    for capability in capabilities:
        capability_id = capability.get("id")
        if not isinstance(capability_id, str):
            raise ValueError("Capability has no id")
        definitions = []
        for definition in registry.templates.values():
            if definition.fallback_only and definition.capability_id == capability_id:
                definitions.append(definition)
        fields = schema_leaves(capability.get("outputSchema", {}))
        counts: Counter[str] = Counter()
        for path, field in fields:
            role = field_presentation(path, field)
            actual_path = path.replace("*", "0")
            families: set[str] = set()
            businesses: set[str] = set()
            for definition in definitions:
                if not general_field_is_allowed(definition, actual_path):
                    continue
                if general_family_is_eligible(definition, (actual_path,), actual_path):
                    families.add(definition.general_content_kind or "unknown")
                    businesses.add(definition.business_id or "unknown")
            covered = bool(families)
            counts[role] += 1
            counts["covered"] += covered
            rows.append(
                {
                    "capability": capability_id,
                    "path": path,
                    "type": field.get("type"),
                    "description": field.get("description", ""),
                    "role": role,
                    "covered": covered,
                    "families": sorted(families),
                    "businesses": sorted(businesses),
                    "requiresConcreteIndex": "*" in path,
                }
            )
        by_capability.append({"capability": capability_id, "fields": len(fields), **counts})
    roles = Counter(row.get("role") for row in rows)
    return {
        "source": str(CAPABILITIES),
        "capabilities": len(capabilities),
        "leafPatterns": len(rows),
        "roles": dict(roles),
        "coveredLeafPatterns": sum(bool(row.get("covered")) for row in rows),
        "previousNumberSuitablePatterns": roles.get("number", 0),
        "byCapability": by_capability,
        "fields": rows,
        "limitations": [
            "叶字段模式覆盖不等于任意多字段组合都能放入当前尺寸。",
            "数组仅验证一个已批准的具体索引；整集合、自适应行数、滚动列表未实现。",
            "两项比较可使用 Pair，三个以上主指标仍需要选择摘要或现有专用模板。",
            "同一健康能力跨步数/睡眠等业务组合仍受现有 Planner 按能力分组的限制。",
            "7 项能力清单不含系统内存；内存模板属于既有 Provider 的补充范围，不计入分母。",
            "未进行真实 LLM 生成或真机验收。",
        ],
    }


def write_audit(output: Path, audit: dict[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "field-coverage.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n"
    )
    roles = audit.get("roles", {})
    content = (
        "# 通用模板字段覆盖审计\n\n"
        f"来源：`{CAPABILITIES}`。按叶字段模式统计，数组元素模式只计一次。\n\n"
        f"共 {audit.get('capabilities')} 项能力、{audit.get('leafPatterns')} 个叶字段模式。"
        f"原 Number 排版适合 {audit.get('previousNumberSuitablePatterns')} 项；"
        f"新增语义分类后可表达 {audit.get('coveredLeafPatterns')} 项，"
        f"另外 {roles.get('internal', 0)} 项为标识符、枚举控制或动作参数，不作通用展示。\n\n"
        "| 能力 | 叶字段 | 数值 | 文字 | 上下文 | 内部字段 | 可表达 |\n"
        "|---|---:|---:|---:|---:|---:|---:|\n"
    )
    for row in audit.get("byCapability", []):
        content += (
            "| "
            + " | ".join(
                str(row.get(key, 0))
                for key in (
                    "capability",
                    "fields",
                    "number",
                    "text",
                    "context",
                    "internal",
                    "covered",
                )
            )
            + " |\n"
        )
    content += (
        "\n## 逐字段归属\n\n| 能力 / 字段模式 | 展示分类 | 通用族 | 业务 | 说明 |\n"
        "|---|---|---|---|---|\n"
    )
    for row in audit.get("fields", []):
        description = str(row.get("description", "")).replace("|", "｜").replace("\n", " ")
        content += (
            f"| {row.get('capability')} `{row.get('path')}` | {row.get('role')} | "
            f"{', '.join(row.get('families', []))} | {', '.join(row.get('businesses', []))} | "
            f"{description} |\n"
        )
    content += (
        "\n## 限制\n\n" + "\n".join("- " + item for item in audit.get("limitations", [])) + "\n"
    )
    (output / "字段覆盖审计.md").write_text(content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    capabilities = json.loads(CAPABILITIES.read_text())
    audit = build_audit(CardPlanRegistry(), capabilities)
    write_audit(args.output, audit)
    print({key: value for key, value in audit.items() if key not in {"fields", "byCapability"}})


if __name__ == "__main__":
    main()
