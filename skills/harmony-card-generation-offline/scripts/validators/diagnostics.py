from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class Diagnostic:
    severity: str
    code: str
    stage: str
    file_kind: str
    message: str
    fix_hint: str = ""
    line: int | None = None
    json_pointer: str = ""
    actual: Any = None
    expected: Any = None
    source: str = ""

    def to_json(self) -> dict[str, Any]:
        result = asdict(self)
        return {key: value for key, value in result.items() if value not in (None, "", [])}


class Reporter:
    def __init__(self, templates: dict[str, Any] | None = None, max_errors: int = 50) -> None:
        self.templates = templates or {}
        self.max_errors = max_errors
        self.diagnostics: list[Diagnostic] = []
        self.quality_score: int | None = None
        self.status: str | None = None

    def add(
        self,
        severity: str,
        code: str,
        stage: str,
        file_kind: str,
        message: str | None = None,
        fix_hint: str | None = None,
        line: int | None = None,
        json_pointer: str = "",
        actual: Any = None,
        expected: Any = None,
        source: str = "",
    ) -> None:
        if severity == "error" and self.error_count >= self.max_errors:
            return
        template = self.templates.get(code, {})
        self.diagnostics.append(
            Diagnostic(
                severity=severity,
                code=code,
                stage=stage,
                file_kind=file_kind,
                line=line,
                json_pointer=json_pointer,
                message=message or template.get("message", code),
                actual=actual,
                expected=expected,
                fix_hint=fix_hint if fix_hint is not None else template.get("fixHint", ""),
                source=source,
            )
        )

    @property
    def error_count(self) -> int:
        return sum(1 for item in self.diagnostics if item.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for item in self.diagnostics if item.severity == "warning")

    def has_error(self, stage: str | None = None) -> bool:
        return any(item.severity == "error" and (stage is None or item.stage == stage) for item in self.diagnostics)

    def has_code(self, *codes: str) -> bool:
        code_set = set(codes)
        return any(item.code in code_set for item in self.diagnostics)

    def set_quality(self, score: int) -> None:
        self.quality_score = max(0, min(100, score))
        if self.error_count:
            self.status = "invalid"
        elif self.quality_score < 70:
            self.status = "valid_with_quality_risks"
        elif self.quality_score < 90:
            self.status = "valid"
        else:
            self.status = "polished"

    def render_text(self) -> str:
        lines: list[str] = []
        for item in self.diagnostics:
            location = item.file_kind
            if item.line is not None:
                location += f":{item.line}"
            if item.json_pointer:
                location += f" {item.json_pointer}"
            lines.append(f"{item.severity.upper()} {item.code}")
            lines.append(f"位置: {location}")
            lines.append(f"问题: {item.message}")
            if item.actual is not None:
                lines.append(f"当前: {json.dumps(item.actual, ensure_ascii=False)}")
            if item.expected is not None:
                lines.append(f"期望: {json.dumps(item.expected, ensure_ascii=False)}")
            if item.fix_hint:
                lines.append(f"建议: {item.fix_hint}")
            lines.append("")
        if self.quality_score is not None:
            lines.append(f"qualityScore: {self.quality_score}")
            lines.append(f"status: {self.status}")
        if not self.diagnostics:
            lines.append("OK: no issues found")
            if self.quality_score is not None:
                lines.append(f"qualityScore: {self.quality_score}")
                lines.append(f"status: {self.status}")
        return "\n".join(lines).rstrip()

    def render_json(self) -> str:
        return json.dumps(
            {
                "status": self.status or ("invalid" if self.error_count else "valid"),
                "qualityScore": self.quality_score,
                "errorCount": self.error_count,
                "warningCount": self.warning_count,
                "diagnostics": [item.to_json() for item in self.diagnostics],
            },
            ensure_ascii=False,
            indent=2,
        )

    def render_model(self) -> str:
        if not self.diagnostics:
            score = f"，qualityScore={self.quality_score}" if self.quality_score is not None else ""
            return f"校验通过{score}。"
        lines = [f"需要修复 {self.error_count} 个 error，另有 {self.warning_count} 个 warning："]
        for index, item in enumerate(self.diagnostics[: self.max_errors], 1):
            location = item.file_kind
            if item.line is not None:
                location += f":{item.line}"
            if item.json_pointer:
                location += f" {item.json_pointer}"
            hint = item.fix_hint or item.message
            lines.append(f"{index}. [{item.severity}] {location}")
            lines.append(f"   {hint}")
        if self.quality_score is not None:
            lines.append(f"qualityScore={self.quality_score}, status={self.status}")
        return "\n".join(lines)
