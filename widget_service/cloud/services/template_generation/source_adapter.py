"""将模板 A2UI 转换为当前公共 Processor 对应的源 DSL。"""

from __future__ import annotations

import ast
import json
import re
from typing import Any

from services.generation_pipeline import DslProcessorKind
from services.template_generation.engine.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    convert_a2ui_to_compact_dsl,
)


class TemplateSourceAdapterError(RuntimeError):
    """模板输出无法转换为当前路由要求的源 DSL。"""


_TERSE_DATA_PLACEHOLDER = re.compile(
    r"^\$\{(data(?:\.[A-Za-z_][A-Za-z0-9_]*|\.\d+)+)\}$"
)
_TERSE_DESIGN_ALIASES: dict[tuple[str, str], tuple[str, dict[str, Any]]] = {
    ("Text", "compact-title"): (
        "body",
        {"fontSize": 14, "fontWeight": 700, "fontColor": "font_primary"},
    ),
    ("Text", "compact-action"): (
        "body",
        {"fontSize": 12, "fontWeight": 600, "fontColor": "font_primary"},
    ),
    ("Image", "compact-icon"): (
        "icon",
        {"width": 16, "height": 16, "objectFit": "contain"},
    ),
}


def prepare_template_source_dsl(
    template_a2ui: str,
    template_terse_dsl: str,
    *,
    processor_kind: DslProcessorKind,
    size: str,
    protocol_profile: dict[str, Any],
) -> str:
    """返回与 Processor 匹配的源格式，使公共转换和校验链保持不变。"""
    if processor_kind == DslProcessorKind.TERSE_NESTED2:
        return _extract_terse_component_tree(template_terse_dsl)

    adapted_a2ui = _adapt_to_protocol_profile(template_a2ui, protocol_profile)
    if processor_kind == DslProcessorKind.STANDARD_A2UI:
        return adapted_a2ui
    if processor_kind != DslProcessorKind.DESIGN_COMPACT:
        raise TemplateSourceAdapterError(
            f"unsupported template processor kind: {processor_kind}"
        )
    try:
        return convert_a2ui_to_compact_dsl(adapted_a2ui, size=size)
    except CompactDslConversionError as exc:
        raise TemplateSourceAdapterError(
            "template A2UI cannot be converted to Compact DSL"
        ) from exc


def _extract_terse_component_tree(template_terse_dsl: str) -> str:
    """移除模板引擎的可选 data 语句，数据模型继续由公共 TaskSpec 产生。"""
    try:
        module = ast.parse(template_terse_dsl, mode="exec")
    except (SyntaxError, TypeError, ValueError) as exc:
        raise TemplateSourceAdapterError(
            "template Terse DSL cannot be parsed"
        ) from exc
    first_statement_is_component = bool(module.body) and isinstance(
        module.body[0],
        ast.Expr,
    )
    if not first_statement_is_component or len(module.body) not in {1, 2}:
        raise TemplateSourceAdapterError(
            "template Terse DSL must contain one component tree and optional data"
        )
    if len(module.body) == 2 and not _is_template_data_assignment(module.body[1]):
        raise TemplateSourceAdapterError(
            "template Terse DSL second statement must assign data"
        )
    expression = module.body[0]
    assert isinstance(expression, ast.Expr)
    normalized = _TerseSourceNormalizer().visit(expression.value)
    ast.fix_missing_locations(normalized)
    return ast.unparse(normalized)


def _is_template_data_assignment(statement: ast.stmt) -> bool:
    if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
        return False
    target = statement.targets[0]
    return isinstance(target, ast.Name) and target.id == "data"


class _TerseSourceNormalizer(ast.NodeTransformer):
    """把模板引擎的 Terse 扩展写法收敛为公共 Processor 输入。"""

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        if not isinstance(node.func, ast.Name) or len(node.args) < 2:
            return node
        design = node.args[1]
        if not isinstance(design, ast.Constant) or not isinstance(design.value, str):
            return node
        alias = _TERSE_DESIGN_ALIASES.get((node.func.id, design.value))
        if alias is None:
            return node
        base_design, default_options = alias
        node.args[1] = ast.Constant(value=base_design)
        self._merge_default_options(node, default_options)
        return node

    def visit_Dict(self, node: ast.Dict) -> ast.AST:
        self.generic_visit(node)
        entries = [
            (key, value)
            for key, value in zip(node.keys, node.values, strict=True)
            if not isinstance(key, ast.Constant) or key.value != "_id"
        ]
        node.keys = [key for key, _value in entries]
        node.values = [value for _key, value in entries]
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if not isinstance(node.value, str):
            return node
        match = _TERSE_DATA_PLACEHOLDER.fullmatch(node.value)
        if match is None:
            return node
        pointer = "/" + match.group(1).replace(".", "/")
        return ast.copy_location(ast.Constant(value=f"{{{{ ${{{pointer}}} }}}}"), node)

    @staticmethod
    def _merge_default_options(
        node: ast.Call,
        default_options: dict[str, Any],
    ) -> None:
        options = node.args[-1] if isinstance(node.args[-1], ast.Dict) else None
        if options is None:
            options = ast.Dict(keys=[], values=[])
            node.args.append(options)
        existing_keys = {
            key.value
            for key in options.keys
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        }
        for key, value in default_options.items():
            if key in existing_keys:
                continue
            options.keys.append(ast.Constant(value=key))
            options.values.append(ast.Constant(value=value))


def _adapt_to_protocol_profile(
    a2ui: str,
    protocol_profile: dict[str, Any],
) -> str:
    messages = _parse_three_messages(a2ui)
    create_surface = messages[0]["createSurface"]
    update_components = messages[1]["updateComponents"]
    update_data_model = messages[2]["updateDataModel"]
    surface_ids = {
        create_surface.get("surfaceId"),
        update_components.get("surfaceId"),
        update_data_model.get("surfaceId"),
    }
    surface_ids_match = len(surface_ids) == 1
    surface_ids_valid = all(isinstance(item, str) and item for item in surface_ids)
    if not surface_ids_match or not surface_ids_valid:
        raise TemplateSourceAdapterError("template A2UI surfaceId values do not match")
    create_surface["catalogId"] = protocol_profile["catalogId"]
    components = update_components.get("components")
    if not isinstance(components, list):
        raise TemplateSourceAdapterError("template A2UI components must be an array")
    root = next(
        (
            item
            for item in components
            if isinstance(item, dict) and item.get("id") == update_components.get("root")
        ),
        None,
    )
    if root is None:
        raise TemplateSourceAdapterError("template A2UI root component is missing")
    styles = root.setdefault("styles", {})
    if not isinstance(styles, dict):
        raise TemplateSourceAdapterError("template A2UI root styles must be an object")
    styles.update(
        {
            "width": "matchParent",
            "height": "matchParent",
            "borderRadius": 18,
            "clip": True,
        }
    )
    return "\n".join(
        json.dumps(item, ensure_ascii=False, separators=(",", ":"))
        for item in messages
    )


def _parse_three_messages(a2ui: str) -> list[dict[str, Any]]:
    lines = [line.strip() for line in a2ui.splitlines() if line.strip()]
    if len(lines) != 3:
        raise TemplateSourceAdapterError(
            "template A2UI must contain exactly three messages"
        )
    messages: list[dict[str, Any]] = []
    expected_keys = ("createSurface", "updateComponents", "updateDataModel")
    for line, expected_key in zip(lines, expected_keys, strict=True):
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            raise TemplateSourceAdapterError("template A2UI contains invalid JSON") from exc
        message_has_expected_body = isinstance(message, dict) and isinstance(
            message.get(expected_key),
            dict,
        )
        if not message_has_expected_body:
            raise TemplateSourceAdapterError(f"template A2UI is missing {expected_key}")
        if message.get("version") != "v0.9":
            raise TemplateSourceAdapterError("template A2UI wire version must be v0.9")
        messages.append(message)
    return messages
