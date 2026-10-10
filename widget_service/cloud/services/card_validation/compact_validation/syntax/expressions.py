# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责模块：syntax.expressions。"""

from __future__ import annotations

import re
from typing import Any

from services.card_validation.compact_validation.diagnostics import CompactDiagnostic, emit_error

from ..diagnostics import RuleLocation

_EXPRESSION_PATTERN = re.compile(r"^\{\{\s*(?P<body>.*?)\s*\}\}$")


_REFERENCE_PATTERN = re.compile(r"\$\{(?P<path>[^{}]*)\}")


_STRING_LITERAL_PATTERN = re.compile(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"")


def _collect_binding_context(
    value: Any,
    location: str,
    binding_paths: list[str],
    errors: list[str],
    *,
    source_location: RuleLocation | None = None,
) -> None:
    if isinstance(value, str):
        _collect_expression_context(
            value, location, binding_paths, errors, source_location=source_location
        )
        return
    if isinstance(value, dict):
        if set(value) == {"path"}:
            _collect_path_binding(
                value.get("path"),
                location,
                binding_paths,
                errors,
                source_location=source_location,
            )
            return
        for key, child_value in value.items():
            _collect_binding_context(
                child_value,
                f"{location}.{key}",
                binding_paths,
                errors,
                source_location=source_location.child(key) if source_location else None,
            )
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _collect_binding_context(
                item,
                f"{location}[{index}]",
                binding_paths,
                errors,
                source_location=source_location.child(index) if source_location else None,
            )


def _collect_expression_context(
    value: str,
    location: str,
    binding_paths: list[str],
    errors: list[str],
    *,
    source_location: RuleLocation | None = None,
) -> None:
    markers = ("{{", "}}", "${")
    if not any(marker in value for marker in markers):
        return

    stripped = value.strip()
    match = _EXPRESSION_PATTERN.fullmatch(stripped)
    has_one_opening = stripped.count("{{") == 1
    has_one_closing = stripped.count("}}") == 1
    if match is None or not has_one_opening or not has_one_closing:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_EXPRESSION_WRAPPER",
                validation_class="syntax",
                category="expression",
                message="表达式没有以唯一一对 {{ ... }} 包装整个属性字符串。",
                expected={"wrapper": "{{ ... }}", "wrapperCount": 1, "occupiesFullString": True},
                actual=value,
                component_id=source_location.component_id if source_location else None,
                property_path=source_location.property_path if source_location else None,
                legacy_message=f"{location}: expression must occupy the full string as "
                '"{{ ... }}" and contain exactly one wrapper.',
            ),
        )
        return

    body = match.group("body").strip()
    quoted_paths = _quoted_expression_paths(body)
    for path in quoted_paths:
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_EXPRESSION_QUOTED_POINTER",
                validation_class="syntax",
                category="expression",
                message=f"表达式把数据路径 {path} 写成了带引号的静态文本。",
                expected={
                    "dynamicReference": "${" + path + "}",
                    "plainStaticValueNeedsNoWrapper": True,
                },
                actual={"expression": value, "quotedPath": path},
                component_id=source_location.component_id if source_location else None,
                property_path=source_location.property_path if source_location else None,
                legacy_message=f'{location}: expression wraps quoted JSON Pointer "{path}"; '
                f"use ${{{path}}} for a dynamic binding, or use a plain "
                "static value without {{ }}.",
            ),
        )

    references = list(_REFERENCE_PATTERN.finditer(body))
    if not references:
        if not quoted_paths:
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_EXPRESSION_REFERENCE_MISSING",
                    validation_class="syntax",
                    category="expression",
                    message="表达式中没有动态 JSON Pointer 引用。",
                    expected={
                        "requiresReference": "${/json/pointer}",
                        "staticValueMustBePlain": True,
                    },
                    actual=value,
                    component_id=source_location.component_id if source_location else None,
                    property_path=source_location.property_path if source_location else None,
                    legacy_message=f"{location}: expression has no ${{/json/pointer}} reference; "
                    "use a plain static value instead.",
                ),
            )
        return

    if body.count("${") != len(references):
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_EXPRESSION_REFERENCE_INCOMPLETE",
                validation_class="syntax",
                category="expression",
                message="表达式含有未闭合或不完整的 ${...} 引用。",
                expected={"completeReference": "${/json/pointer}"},
                actual=value,
                component_id=source_location.component_id if source_location else None,
                property_path=source_location.property_path if source_location else None,
                legacy_message=f"{location}: expression contains an incomplete ${{...}} reference.",
            ),
        )
    for reference in references:
        path = reference.group("path").strip()
        if not _is_json_pointer(path):
            emit_error(
                errors,
                CompactDiagnostic(
                    code="COMPACT_EXPRESSION_REFERENCE_ABSOLUTE",
                    validation_class="syntax",
                    category="expression",
                    message=f"表达式引用路径 {path} 不是绝对 JSON Pointer。",
                    expected={"absoluteJsonPointer": True},
                    actual={"path": path},
                    component_id=source_location.component_id if source_location else None,
                    property_path=source_location.property_path if source_location else None,
                    legacy_message=f'{location}: expression reference "{path}" '
                    "must be an absolute JSON Pointer.",
                ),
            )
            continue
        binding_paths.append(path)


def _quoted_expression_paths(body: str) -> list[str]:
    """Collect JSON Pointer-looking string literals from an expression body."""
    paths: list[str] = []
    index = 0
    while index < len(body):
        quote = body[index]
        if quote not in {"'", '"'}:
            index += 1
            continue

        index += 1
        literal: list[str] = []
        escaped = False
        while index < len(body):
            char = body[index]
            index += 1
            if escaped:
                literal.append(char)
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char != quote:
                literal.append(char)
                continue

            candidate = "".join(literal)
            is_binding_path = candidate in {"/data", "/state"}
            is_binding_descendant = candidate.startswith(("/data/", "/state/"))
            if (is_binding_path or is_binding_descendant) and candidate not in paths:
                paths.append(candidate)
            break
    return paths


def _collect_path_binding(
    path: Any,
    location: str,
    binding_paths: list[str],
    errors: list[str],
    *,
    source_location: RuleLocation | None = None,
) -> None:
    if not isinstance(path, str) or not _is_json_pointer(path):
        emit_error(
            errors,
            CompactDiagnostic(
                code="COMPACT_PATH_BINDING_ABSOLUTE",
                validation_class="syntax",
                category="expression",
                message="PathBinding.path 不是绝对 JSON Pointer 字符串。",
                expected={"type": "string", "absoluteJsonPointer": True},
                actual=path,
                component_id=source_location.component_id if source_location else None,
                property_path=source_location.property_path if source_location else None,
                legacy_message=f"{location}: PathBinding.path must be an absolute JSON Pointer.",
            ),
        )
        return
    binding_paths.append(path)


def _is_json_pointer(path: str) -> bool:
    return isinstance(path, str) and path.startswith("/")


def _decode_json_pointer(path: str) -> list[str]:
    if path == "/":
        return []
    if not _is_json_pointer(path):
        return []
    return [
        token.replace("~1", "/").replace("~0", "~") for token in path.removeprefix("/").split("/")
    ]
