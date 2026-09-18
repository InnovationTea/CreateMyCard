"""通用模板的内容语义；类型与展示语义分别判断，不从样例推导。"""

from __future__ import annotations

import ast
import re
from typing import Any

from services.template_generation.engine.a2ui_expression import (
    _tokenize,
    normalize_wrapped_expression,
)
from services.template_generation.engine.tersel_converter import TerselConversionError

from .models import TemplateDefinition

_INTERNAL = frozenset(
    {
        "cityCode",
        "entityName",
        "entityId",
        "importantEventType",
        "oneClickServiceType",
        "oneClickServiceLink",
        "isServiceValid",
    }
)
_CONTEXT = frozenset(
    {
        "districtName",
        "prefectureName",
        "updatedAt",
        "targetDateText",
        "appName",
        "earphoneName",
        "senderName",
        "timeZone",
        "date",
        "weekday",
        "startDate",
        "dtStart",
        "dtEnd",
        "fallAsleepTimeText",
        "wakeupTimeText",
        "exerciseStartTimeText",
        "exerciseEndTimeText",
        "remindTime",
    }
)


def field_presentation(path: str, field: dict[str, Any]) -> str:
    """返回 internal/context/number/text；数组叶字段模式只按字段定义判断。"""
    name = path.rstrip("/*").rsplit("/", 1)[-1]
    if name in _INTERNAL:
        return "internal"
    if name in _CONTEXT:
        return "context"
    if field.get("type") in {"number", "integer"}:
        return "number"
    if field.get("displayUnits"):
        # 温度区间是两个量的组合；时长仍是一个量，字号由业务模板决定。
        if "Range" in name:
            return "text"
        return "number"
    return "text"


def general_field_is_allowed(definition: TemplateDefinition, path: str) -> bool:
    from .provider_bundle import _schema_leaf

    if definition.general_data_paths and path not in definition.general_data_paths:
        return False
    field = _schema_leaf(definition.data_source_schema, path)
    return field is not None and field_presentation(path, field) != "internal"


def general_family_is_eligible(
    definition: TemplateDefinition,
    fields: tuple[str, ...],
    primary: str | None,
) -> bool:
    from .provider_bundle import _schema_leaf

    kinds: dict[str, str] = {}
    for path in fields:
        field = _schema_leaf(definition.data_source_schema, path)
        if field is not None:
            kinds[path] = field_presentation(path, field)
    focus = (kinds.get(primary),) if primary is not None else tuple(kinds.values())
    kind = definition.general_content_kind
    eligible = True
    if kind == "number":
        eligible = "number" in focus
    elif kind == "text":
        eligible = bool(kinds)
    elif kind == "pair":
        eligible = len(kinds) >= 2
    return eligible


def general_family_preference(
    definition: TemplateDefinition, fields: tuple[str, ...], primary: str | None,
) -> int:
    from .provider_bundle import _schema_leaf

    if not definition.fallback_only:
        return 3
    preferred = "text"
    focus_paths = (primary,) if primary is not None else fields
    for path in focus_paths:
        field = _schema_leaf(definition.data_source_schema, path)
        if field is None:
            continue
        role = field_presentation(path, field)
        if role in {"number", "text"}:
            preferred = role
            break
    if definition.general_content_kind == preferred:
        return 0
    return 2 if definition.general_content_kind == "pair" else 1


def validate_general_main_value(
    definition: TemplateDefinition,
    values: dict[str, Any],
    allowed_paths: dict[str, str],
) -> None:
    """Number 主值只接收数值或单位表达式；状态句子应交由 Text/Pair。"""
    from .provider_bundle import _schema_leaf

    if definition.general_content_kind != "number":
        return
    progress = values.get("progressValue")
    if progress is not None:
        _validate_progress_value(definition, progress)
    value = values.get("mainNumberValue")
    if not isinstance(value, str):
        raise TerselConversionError("Number main value must be numeric display text")
    units = {"", " ", ",", ".", "+", "-", "分"}
    number_paths: set[str] = set()
    domain = definition.data_domain or ""
    for path in allowed_paths:
        field = _schema_leaf(definition.data_source_schema, path)
        if field is not None and field_presentation(path, field) == "number":
            number_paths.add(domain + path)
            units.update(field.get("displayUnits", ()))
    if value.startswith("${"):
        path = "/" + value.removeprefix("${").removesuffix("}").replace(".", "/")
        if path not in number_paths:
            raise TerselConversionError("Number main value references non-numeric content")
    elif value.startswith("{{"):
        normalized = normalize_wrapped_expression(value)
        if not set(normalized.references).issubset(number_paths):
            raise TerselConversionError("Number main expression references non-numeric content")
        body = normalized.value.removeprefix("{{").removesuffix("}}")
        for token in _tokenize(body):
            if token.kind == "literal":
                literal = ast.literal_eval(token.value)
                if literal.strip() not in units:
                    raise TerselConversionError("Number main value cannot contain a label sentence")
            elif token.kind not in {"binding", "number"}:
                if token.value not in {"+", "-", "*", "/", "%", "(", ")"}:
                    raise TerselConversionError("Number main expression must be numeric formatting")
    else:
        unit_pattern = "|".join(re.escape(unit) for unit in sorted(units, key=len, reverse=True))
        number = r"[+-]?[0-9][0-9,]*(?:\.[0-9]+)?"
        single = re.fullmatch(number + r"\s*(?:" + unit_pattern + ")", value)
        time_units = units.intersection({"天", "小时", "分钟", "分", "秒"})
        time_pattern = "|".join(
            re.escape(unit) for unit in sorted(time_units, key=len, reverse=True)
        )
        duration: re.Match[str] | None = None
        if time_units:
            duration_pattern = r"(?:" + number + r"\s*(?:" + time_pattern + r")\s*){1,3}"
            duration = re.fullmatch(duration_pattern, value)
        if single is None and duration is None:
            raise TerselConversionError("Number main value requires a number with an optional unit")


def _validate_progress_value(definition: TemplateDefinition, value: Any) -> None:
    from .provider_bundle import _schema_leaf

    if isinstance(value, (float, int)) and not isinstance(value, bool):
        if not 0 <= value <= 100:
            raise TerselConversionError("General progress must be in the range 0 to 100")
        return
    if isinstance(value, str) and value.startswith("${"):
        domain = definition.data_domain or ""
        path = "/" + value.removeprefix("${").removesuffix("}").replace(".", "/")
        field = _schema_leaf(definition.data_source_schema, path.removeprefix(domain))
        if field is not None:
            percent = "%" in field.get("displayUnits", ())
            score = path.endswith("/sleepScore")
            if percent or score:
                return
    raise TerselConversionError("General progress requires a declared percentage or sleep score")


def general_preview_data(definition: TemplateDefinition) -> dict[str, Any]:
    title = "location" if definition.business_id == "WeatherOverview" else "title"
    result: dict[str, Any] = {title: "通用数据预览", "supportValues": ["辅助信息一", "辅助信息二"]}
    if definition.general_content_kind == "pair":
        result.update(
            firstLabel="第一项", firstValue="68%", secondLabel="第二项", secondValue="正常"
        )
    elif definition.general_content_kind == "text":
        result.update(mainTextValue="状态说明", mainLabel="当前状态")
    else:
        result.update(mainNumberValue="68", mainLabel="当前指标")
        if "progressValue" in definition.data_parameters_schema.get("properties", {}):
            result["progressValue"] = 68
    return result


def validate_general_focus(
    definition: TemplateDefinition, values: dict[str, Any], required: set[str],
) -> None:
    if not required:
        return
    main_names = {
        "number": ("mainNumberValue",), "text": ("mainTextValue",),
        "pair": ("firstValue", "secondValue"),
    }
    names = main_names.get(definition.general_content_kind or "", ())
    referenced: set[str] = set()
    for name in names:
        value = values.get(name)
        if isinstance(value, str) and value.startswith("${"):
            referenced.add("/" + value.removeprefix("${").removesuffix("}").replace(".", "/"))
        elif isinstance(value, str) and value.startswith("{{"):
            referenced.update(normalize_wrapped_expression(value).references)
    domain = definition.data_domain or ""
    if any(domain + field not in referenced for field in required):
        raise TerselConversionError(
            "General main value must display the requested primary field: "
            f"{sorted(required)}. Use unquoted $path(...) or Expr(...) calls, not string literals."
        )
