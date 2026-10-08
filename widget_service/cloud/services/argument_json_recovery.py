"""参数恢复的严格片段提取与受限 JSON 语法修复；不裁决业务能力。"""

import copy
import json
import math
import re
from dataclasses import dataclass, field
from typing import Any

from json_repair import repair_json


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON value: {value}")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("non-finite JSON number")
    return number


DECODER = json.JSONDecoder(
    object_pairs_hook=_unique_object,
    parse_constant=_reject_constant,
    parse_float=_finite_float,
)
_TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false|null')


@dataclass
class ArgumentFragments:
    fields: dict[str, Any] = field(default_factory=dict)
    array_prefixes: dict[str, list[Any]] = field(default_factory=dict)
    damaged_fields: list[str] = field(default_factory=list)


def extract_fragments(raw: str) -> ArgumentFragments:
    """只沿可证明的根对象边界解析；遇损坏停止，不匹配嵌套/字符串中的同名键。"""
    result = ArgumentFragments()
    position = len(raw) - len(raw.lstrip())
    if raw[position:position + 1] != "{":
        return result
    position += 1
    while position < len(raw):
        position = _skip_space(raw, position)
        if raw[position:position + 1] == ",":
            position = _skip_space(raw, position + 1)
        try:
            key, end = DECODER.raw_decode(raw, position)
        except ValueError:
            break
        if not isinstance(key, str):
            break
        position = _skip_space(raw, end)
        if raw[position:position + 1] != ":":
            break
        position = _skip_space(raw, position + 1)
        if key in result.fields:
            # 重复键有歧义，不选取其中任何一个作为不可变事实。
            result.fields.pop(key)
            result.damaged_fields.append(key)
            break
        try:
            value, end = DECODER.raw_decode(raw, position)
            _check_value_end(raw, end)
        except ValueError:
            result.damaged_fields.append(key)
            if raw[position:position + 1] == "[":
                result.array_prefixes[key] = _array_prefix(raw, position + 1)
            break
        result.fields[key] = value
        position = end
    return result


def _skip_space(raw: str, position: int) -> int:
    while position < len(raw) and raw[position].isspace():
        position += 1
    return position


def _check_value_end(raw: str, end: int) -> None:
    position = _skip_space(raw, end)
    if position < len(raw) and raw[position] not in ",}]":
        raise ValueError("value is not independently delimited")


def _array_prefix(raw: str, position: int) -> list[Any]:
    values: list[Any] = []
    while position < len(raw):
        position = _skip_space(raw, position)
        try:
            value, end = DECODER.raw_decode(raw, position)
            _check_value_end(raw, end)
        except ValueError:
            break
        values.append(value)
        position = _skip_space(raw, end)
        if raw[position:position + 1] != ",":
            break
        position += 1
    return values


def _scalar_tokens(raw: str) -> list[Any]:
    """拒绝未加引号文本；标量顺序/类型/值必须不变，不能接受猜测或静默删除。"""
    values: list[Any] = []
    position = 0
    for match in _TOKEN.finditer(raw):
        if raw[position:match.start()].strip(" \r\n\t{}[]:,"):
            raise ValueError("JSON repair would change unrecognized text")
        token = match.group()
        value = DECODER.decode(token)
        values.append((type(value).__name__, value))
        position = match.end()
    if raw[position:].strip(" \r\n\t{}[]:,"):
        raise ValueError("JSON repair would discard trailing text")
    return values


def repair_syntax(raw: str) -> str:
    """json_repair 只修标点；修复后仍须严格解析和业务校验，不使用 schema 补默认值。"""
    original_tokens = _scalar_tokens(raw)
    repaired = repair_json(raw, skip_json_loads=True, ensure_ascii=False)
    if not isinstance(repaired, str):
        raise ValueError("JSON repair did not return text")
    DECODER.decode(repaired)
    if original_tokens != _scalar_tokens(repaired):
        raise ValueError("JSON repair changed or removed fields/values")
    return repaired


@dataclass
class PreservedArguments:
    fields: dict[str, Any] = field(default_factory=dict)
    items: dict[str, dict[int, Any]] = field(default_factory=dict)
    required_fields: list[str] = field(default_factory=list)

    def merge(self, repaired: dict[str, Any]) -> dict[str, Any]:
        result = copy.deepcopy(repaired)
        result.update(copy.deepcopy(self.fields))
        for name, indexed_items in self.items.items():
            values = result.get(name)
            if not isinstance(values, list):
                raise ValueError(f"repair must return array: {name}")
            for index, value in indexed_items.items():
                if index >= len(values):
                    raise ValueError(f"repair lost array item: {name}/{index}")
                values[index] = copy.deepcopy(value)
        for name in self.required_fields:
            if name not in result:
                raise ValueError(f"repair omitted damaged field: {name}")
            if result.get(name) in (None, [], {}):
                raise ValueError(f"repair erased damaged field: {name}")
        return result

    def assert_retained(self, normalized: dict[str, Any]) -> None:
        for name, value in self.fields.items():
            if not _contains_original(normalized.get(name), value):
                raise ValueError(f"validation changed preserved field: {name}")
        for name, indexed_items in self.items.items():
            values = normalized.get(name)
            if not isinstance(values, list):
                raise ValueError(f"validation lost preserved array: {name}")
            for index, value in indexed_items.items():
                if index >= len(values) or not _contains_original(values[index], value):
                    raise ValueError(f"validation changed preserved item: {name}/{index}")


def _contains_original(actual: Any, original: Any) -> bool:
    if isinstance(original, dict):
        if not isinstance(actual, dict):
            return False
        for key, value in original.items():
            if key not in actual or not _contains_original(actual.get(key), value):
                return False
        return True
    if isinstance(original, list):
        if not isinstance(actual, list) or len(actual) != len(original):
            return False
        return all(
            _contains_original(item, value) for item, value in zip(actual, original, strict=True)
        )
    return type(actual) is type(original) and actual == original
