"""只从原文中提取可证明的位置；不替代解析器或修复原始输入。"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Any

from app.logger import logger

from .context import ValidationContext, component_index
from .diagnostics import MISSING, CompactDiagnostic


@dataclass(frozen=True)
class SourceRecord:
    line: int
    value: list[Any]


class SourceLocations:
    """重复 ID、未知行结构、修复后属性不一致时保守省略定位。"""

    def __init__(self, context: ValidationContext) -> None:
        self._context = context
        self._records = self._read_records(context.original_source)

    @staticmethod
    def _read_records(source: str) -> dict[str, list[SourceRecord]]:
        records: dict[str, list[SourceRecord]] = {}
        for line_number, raw_line in enumerate(source.splitlines(), 1):
            line = raw_line.strip()
            if not line or line.startswith("```"):
                continue
            try:
                value = json.loads(line)
            except (TypeError, ValueError) as exc:
                logger.debug("Compact source location unavailable: {}: {}", type(exc).__name__, exc)
                return {}
            if not isinstance(value, list) or not value:
                return {}
            identity = value[0]
            if not isinstance(identity, str):
                return {}
            records.setdefault(identity, []).append(SourceRecord(line_number, value))
        return records

    def locate(self, diagnostic: CompactDiagnostic) -> CompactDiagnostic:
        result = replace(diagnostic, component_id=None, property_path=None, source_line=None)
        component_id = diagnostic.component_id
        if component_id is not None:
            result = self._locate_component(diagnostic, result, component_id)
        elif diagnostic.data_path is not None:
            result = self._locate_data(diagnostic, result)
        return result

    def _unique_record(self, identity: str) -> SourceRecord | None:
        records = self._records.get(identity, [])
        record: SourceRecord | None = None
        if len(records) == 1:
            record = records[0]
        return record

    def _locate_component(
        self,
        diagnostic: CompactDiagnostic,
        result: CompactDiagnostic,
        component_id: str,
    ) -> CompactDiagnostic:
        record = self._unique_record(component_id)
        component = component_index(self._context.components).get(component_id)
        if record is None or component is None:
            return result
        value = record.value
        if len(value) not in {3, 4} or value[1] != component.component_type:
            return result
        result = replace(result, component_id=component_id, source_line=record.line)
        path = diagnostic.property_path
        if path is not None:
            original_value = _property_value(value[2], path)
            validated_value = _property_value(component.props, path)
            if original_value is not MISSING and original_value == validated_value:
                result = replace(result, property_path=path)
        return result

    def _locate_data(
        self, diagnostic: CompactDiagnostic, result: CompactDiagnostic
    ) -> CompactDiagnostic:
        path = diagnostic.data_path
        if path is None:
            return result
        record = self._unique_record(path)
        if record is None or len(record.value) != 2:
            return result
        matching = [row for row in self._context.data_rows if row.path == path]
        if len(matching) == 1 and record.value[1] == matching[0].value:
            result = replace(result, source_line=record.line)
        return result


def _property_value(props: Any, path: str) -> Any:
    value: Any = props
    if not path.startswith("/"):
        value = MISSING
    else:
        for token in path.removeprefix("/").split("/"):
            key = token.replace("~1", "/").replace("~0", "~")
            if isinstance(value, dict):
                value = value.get(key, MISSING)
            elif isinstance(value, list) and key.isdecimal():
                index = int(key)
                value = value[index] if index < len(value) else MISSING
            else:
                value = MISSING
            if value is MISSING:
                break
    return value
