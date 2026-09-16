"""通用垂域模板的路径准入、模型签名和编译后覆盖检查。"""

from __future__ import annotations

import re
from typing import Any

from models.generation import TaskSpec
from services.template_generation.engine.a2ui_expression import normalize_wrapped_expression
from services.template_generation.engine.tersel_converter import Nested2Node, TerselConversionError

from .general_semantics import general_field_is_allowed
from .models import HybridBodyContract, TemplateDefinition


def parameter_data_paths(definition: TemplateDefinition, task_spec: TaskSpec) -> dict[str, str]:
    """只暴露所属能力、真实声明且类型相符的路径，不向二层传样例值。"""
    from .provider_bundle import _schema_leaf, _task_spec_schema_leaf

    domain = definition.data_domain
    if domain is None:
        return {}
    current: Any = task_spec.dataModelSchema
    for part in domain.removeprefix("/").split("/"):
        current = current.get(part) if isinstance(current, dict) else None
    paths: dict[str, str] = {}

    def visit(value: Any, path: str) -> None:
        if isinstance(value, dict):
            data_type = value.get("type")
            if isinstance(data_type, str) and data_type in {
                "string",
                "number",
                "integer",
                "boolean",
            }:
                declared = _schema_leaf(definition.data_source_schema, path)
                actual = _task_spec_schema_leaf(task_spec.dataModelSchema, domain + path)
                if declared is not None and actual is not None:
                    type_matches = declared.get("type") == data_type
                    if type_matches and general_field_is_allowed(definition, path):
                        paths[path] = data_type
                return
            for key, item in value.items():
                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                    visit(item, f"{path}/{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, f"{path}/{index}")

    visit(current, "")
    return paths


def general_prompt_contract(
    definition: TemplateDefinition,
    task_spec: TaskSpec,
    contract: HybridBodyContract,
) -> dict[str, Any]:
    from .provider_bundle import _schema_leaf

    if not definition.data_parameters_schema:
        return {}
    paths = parameter_data_paths(definition, task_spec)
    required = required_parameter_paths(definition, contract)
    sources: dict[str, Any] = {}
    for path, data_type in paths.items():
        if required and path not in required:
            continue
        field = _schema_leaf(definition.data_source_schema, path)
        metadata: dict[str, Any] = {"type": data_type}
        if field is not None:
            for key in ("description", "displayUnits", "unitIncluded"):
                if key in field:
                    metadata[key] = field[key]
        sources[path] = metadata
    return {
        "callSyntax": f'Template("{definition.wire_id}", {{data: <dataSchema>, ...props}})',
        "dataSchema": definition.data_parameters_schema,
        "contentKind": definition.general_content_kind,
        "requiredMainFields": sorted(required_parameter_paths(definition, contract, primary=True)),
        "mainValueRules": (
            "Number 主值只放数值或数值加单位，不放指标名称、等级或状态句子；"
            "指标名称放 mainLabel。Text 主值放状态或叙述，mainLabel 可作分类说明；"
            "Pair 两项值分别填写标签，适用于并列比较。不得将 ID 或动作链接作为展示数据。"
            "progressValue 仅接受 0–100 的纯数值或批准的百分比/睡眠评分路径；"
            "没有相应字段时省略，不能从数值文本反推进度。"
        ),
        "dataSources": sources,
        "dataRules": (
            "data 接受纯数据、$path(相对路径) 或 Expr(表达式)。路径只能来自 dataSources；"
            "Expr 用 data.xxx 引用相对路径，或唯一的叶字段名。"
            "用户要求的动态字段必须通过路径或表达式显示，不得用样例值替换；"
            "所有 coveredExplicitFields 必须出现在最终 UI。"
            "数字字段用于字符串槽时用 Expr('标签' + data.xxx + '单位')。"
            "supportValues 必须是本轮有限参数数组，不是运行时数组路径。"
            "data 外的字段仍按 propsSchema 填写，省略未提供的可选 Props。"
        ),
    }


def required_parameter_paths(
    definition: TemplateDefinition,
    contract: HybridBodyContract,
    *,
    primary: bool = False,
) -> set[str]:
    required: set[str] = set()
    for plan in contract.allowed_template_plans:
        for slot in plan.business_slots:
            if slot.template_id == definition.wire_id:
                fields = slot.primary_matched_fields if primary else slot.covered_explicit_fields
                required.update(fields)
    return required


def validate_parameter_coverage(
    root: Nested2Node,
    definition: TemplateDefinition,
    contract: HybridBodyContract,
) -> None:
    required = required_parameter_paths(definition, contract)
    if not required:
        return
    referenced: set[str] = set()

    def visit(node: Nested2Node) -> None:
        # 只有可见文本算展示覆盖；样式和事件参数的引用不算。
        if node.component_type == "Text" and node.values:
            value = node.values[0]
            if isinstance(value, str):
                if value.startswith("{{"):
                    referenced.update(normalize_wrapped_expression(value).references)
                elif re.fullmatch(r"\$\{data(?:\.[A-Za-z0-9_]+)+\}", value):
                    path = value.removeprefix("${").removesuffix("}").replace(".", "/")
                    referenced.add("/" + path)
        for child in node.children:
            visit(child)

    visit(root)
    domain = definition.data_domain or ""
    missing = sorted(path for path in required if domain + path not in referenced)
    if missing:
        raise TerselConversionError(f"General Template omits explicit data fields: {missing}")
