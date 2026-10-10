# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Compact 校验职责模块：diagnostics。"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Any, Literal


class _Missing:
    """区别未知事实与合法的 None、0、false 或空容器。"""

    def __deepcopy__(self, memo: dict[int, Any]) -> _Missing:
        return self


MISSING = _Missing()


@dataclass(frozen=True)
class RuleLocation:
    """规则遍历时携带的位置候选；输出前仍须核对原文。"""

    component_id: str
    tokens: tuple[str | int, ...] = ()

    def child(self, token: str | int) -> RuleLocation:
        return replace(self, tokens=(*self.tokens, token))

    @property
    def property_path(self) -> str | None:
        result: str | None = None
        if self.tokens:
            escaped = []
            for token in self.tokens:
                escaped.append(str(token).replace("~", "~0").replace("/", "~1"))
            result = "/" + "/".join(escaped)
        return result


@dataclass(frozen=True)
class CompactDiagnostic:
    """一条规则产生的事实与约束；旧文案独立保存。"""

    code: str
    validation_class: Literal["syntax", "semantic"]
    category: str
    message: str
    legacy_message: str
    expected: Any = MISSING
    actual: Any = MISSING
    evidence_source: Literal["original", "validation"] = "validation"
    component_id: str | None = None
    property_path: str | None = None
    source_line: int | None = None
    fix_hint: str | None = None
    data_path: str | None = None

    def to_payload(self) -> dict[str, Any]:
        """创建可独立还原素材和序列化的副本。"""
        payload: dict[str, Any] = {
            "code": self.code,
            "validationClass": self.validation_class,
            "category": self.category,
            "severity": "error",
            "message": self.message,
            "legacyMessage": self.legacy_message,
        }
        for key, value in (
            ("expected", self.expected),
            ("actual", self.actual),
        ):
            if value is not MISSING:
                payload[key] = deepcopy(value)
        if self.actual is not MISSING:
            payload["evidenceSource"] = self.evidence_source
        for key, value in (
            ("componentId", self.component_id),
            ("propertyPath", self.property_path),
            ("sourceLine", self.source_line),
            ("fixHint", self.fix_hint),
        ):
            if value is not None:
                payload[key] = value
        return payload


@dataclass(frozen=True)
class DiagnosticGroup:
    """按旧文案形成一个兼容错误，部分迁移时保留旧说明。"""

    legacy_message: str
    diagnostics: tuple[CompactDiagnostic, ...] = ()
    has_legacy_record: bool = False

    def prompt_context(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if self.diagnostics and not self.has_legacy_record:
            result["compactDiagnostics"] = [item.to_payload() for item in self.diagnostics]
        return result


def group_records(records: list[str | CompactDiagnostic]) -> tuple[DiagnosticGroup, ...]:
    groups: dict[str, list[CompactDiagnostic]] = {}
    legacy_messages: set[str] = set()
    for record in records:
        if isinstance(record, str):
            groups.setdefault(record, [])
            legacy_messages.add(record)
        else:
            groups.setdefault(record.legacy_message, []).append(record)
    result: list[DiagnosticGroup] = []
    for message, diagnostics in groups.items():
        result.append(DiagnosticGroup(message, tuple(diagnostics), message in legacy_messages))
    return tuple(result)


class DiagnosticCollector(list[str]):
    """同时保留旧规则列表行为和逐次发布记录，不提前去重。"""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[str | CompactDiagnostic] = []

    def append(self, message: str) -> None:
        super().append(message)
        self.records.append(message)

    def emit(self, diagnostic: CompactDiagnostic) -> None:
        super().append(diagnostic.legacy_message)
        self.records.append(diagnostic)


def emit_error(errors: list[str], diagnostic: CompactDiagnostic) -> None:
    """内部调用保留诊断，旧的私有辅助函数调用仍可传入普通字符串列表。"""
    if isinstance(errors, DiagnosticCollector):
        errors.emit(diagnostic)
    else:
        errors.append(diagnostic.legacy_message)


@dataclass(frozen=True)
class CompactDslValidationResult:
    """Compact DSL validation warnings returned to the generation pipeline."""

    warnings: tuple[str, ...] = ()


class CompactDslValidationError(ValueError):
    """One or more Compact DSL contract violations."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = tuple(dict.fromkeys(errors))
        self.diagnostics: tuple[CompactDiagnostic, ...] = ()
        self.groups = tuple(
            DiagnosticGroup(message, has_legacy_record=True) for message in self.errors
        )
        details = "\n".join(f"- {message}" for message in self.errors)
        super().__init__(f"Compact DSL validation failed:\n{details}")

    @classmethod
    def from_records(cls, records: list[str | CompactDiagnostic]) -> CompactDslValidationError:
        groups = group_records(records)
        error = cls([group.legacy_message for group in groups])
        error.groups = groups
        error.diagnostics = tuple(item for item in records if isinstance(item, CompactDiagnostic))
        return error
