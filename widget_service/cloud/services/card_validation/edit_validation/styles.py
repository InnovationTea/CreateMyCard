"""编辑动态样式保护与字段值检查；规则与编辑提示词共享。"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, validators

from ..base import expression_like

_RULE_PATH = (
    Path(__file__).resolve().parents[3] / "data/validator_rules/config/edit_style_values.json"
)
_DIMENSION = re.compile(r"(?P<number>\d+(?:\.\d+)?)(?P<unit>vp|fp|%)")


def _dynamic_atom(value: Any) -> bool:
    if isinstance(value, dict):
        return "path" in value or "call" in value
    return expression_like(value)


def _dynamic_values(value: Any, path: tuple = ()) -> dict[tuple, Any]:
    result: dict[tuple, Any] = {}
    if _dynamic_atom(value):
        result[path] = value
    elif isinstance(value, dict):
        for key, child in value.items():
            result.update(_dynamic_values(child, (*path, key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            result.update(_dynamic_values(child, (*path, index)))
    return result


def preserve_dynamic_styles(before: dict, after: dict) -> None:
    old = _dynamic_values(before)
    new = _dynamic_values(after)
    if set(old) != set(new):
        raise ValueError("动态样式不能新增、移动、删除或静态化")
    for path, value in old.items():
        current = new.get(path)
        if json.dumps(value, sort_keys=True) != json.dumps(current, sort_keys=True):
            raise ValueError("原有动态样式必须在原位置原样保留")


def _preserved_dynamic_keyword(validator_function: Callable) -> Callable:
    def validate(validator, keyword_value, instance, schema):
        # 调用方先检查动态位置及原值；保留的原绑定不能按静态字段类型误拒绝。
        if not _dynamic_atom(instance):
            yield from validator_function(validator, keyword_value, instance, schema)

    return validate


_KEYWORDS = {}
for _keyword, _validator_function in Draft202012Validator.VALIDATORS.items():
    _KEYWORDS[_keyword] = _preserved_dynamic_keyword(_validator_function)
_EditValueValidator = validators.extend(Draft202012Validator, _KEYWORDS)


@lru_cache(maxsize=1)
def edit_style_value_rules() -> dict[str, Any]:
    rules = json.loads(_RULE_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(rules)
    return rules


def _finite_values(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("样式数值必须有限")
    if isinstance(value, dict):
        for child in value.values():
            _finite_values(child)
    elif isinstance(value, list):
        for child in value:
            _finite_values(child)


def _comparable_dimension(value: Any) -> tuple[Decimal, str] | None:
    result: tuple[Decimal, str] | None = None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        result = (Decimal(str(value)), "vp")
    elif isinstance(value, str):
        match = _DIMENSION.fullmatch(value)
        if match is not None:
            result = (Decimal(match.group("number")), match.group("unit"))
    return result


def _constraint_order(value: dict) -> None:
    for minimum_key, maximum_key in (("minWidth", "maxWidth"), ("minHeight", "maxHeight")):
        minimum = _comparable_dimension(value.get(minimum_key))
        maximum = _comparable_dimension(value.get(maximum_key))
        if minimum is None or maximum is None:
            continue
        if minimum[1] == maximum[1] and minimum[0] > maximum[0]:
            raise ValueError(f"constraintSize 的 {minimum_key} 不得大于 {maximum_key}")


def validate_edit_style_value(key: str, value: Any, kind: str, rules: dict) -> None:
    """只验证已变化属性；不重校未修改的历史样式，不授权新动态值。"""
    value_rules = edit_style_value_rules()
    schema = value_rules.get("properties", {}).get(key)
    if schema is None:
        raise ValueError(f"编辑字段缺少值校验规则：{key}")
    _finite_values(value)
    effective_schema = {"$defs": value_rules.get("$defs", {}), **schema}
    error = next(_EditValueValidator(effective_schema).iter_errors(value), None)
    if error is not None:
        raise ValueError(f"{key} 编辑值不符合类型、结构或范围：{error.message}")
    if _dynamic_atom(value):
        return
    enum_values = rules.get("enumValues", {})
    allowed = enum_values.get(f"{kind}.{key}", enum_values.get(key))
    if allowed is not None and value not in allowed:
        raise ValueError(f"{kind}.{key} 必须使用端侧协议枚举")
    if key == "constraintSize":
        _constraint_order(value)
    if key == "linearGradient":
        previous = -1.0
        for _color, offset in value.get("colors", []):
            if _dynamic_atom(offset):
                continue
            if offset < previous:
                raise ValueError("渐变位置必须在 0..1 中递增")
            previous = float(offset)
    if key == "fontColor" and isinstance(value, str):
        if len(value) == 9 and int(value[1:3], 16) == 0:
            raise ValueError("不能通过透明文字隐藏原卡事实")
