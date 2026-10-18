"""最终产物样式枚举校验回归：非法枚举值不得进入端侧。

背景：日程模板曾在 ``alignItems`` 上写出 ``"Top"``（协议只允许小写
``top``），模板预览与公共 Compact 转换都未拦截，非法值随最终 A2UI 产物
下发。ComponentValidator 现按 ``data/validator_rules/config/style.json``
的 ``enumValues`` 对最终产物做硬校验（错误码 ``STYLE_ENUM_INVALID``），
本文件保证：
1. 全部模板预览产物不含非法样式枚举；
2. 大小写错误的枚举值会被校验拦截，合法值放行。
"""

from __future__ import annotations

import json

from services.card_validation import validate_card
from services.template_generation.engine.cardplan.preview_dataset import (
    build_template_preview_cases,
)

_ROOT_ROW_ID = "header_row"


def _minimal_genui(align_items: str, container: str = "Row") -> str:
    """构造一张仅含一个头部容器的最小合法 A2UI 卡片。"""
    components = [
        {
            "id": "root",
            "component": "Column",
            "children": [_ROOT_ROW_ID],
            "styles": {"width": "matchParent", "height": "matchParent"},
        },
        {
            "id": _ROOT_ROW_ID,
            "component": container,
            "children": ["title_text"],
            "styles": {
                "width": "matchParent",
                "height": 20,
                "justifyContent": "start",
                "alignItems": align_items,
            },
        },
        {
            "id": "title_text",
            "component": "Text",
            "content": "日程详情",
            "styles": {
                "height": 16,
                "fontSize": 12,
                "fontColor": "#FF000000",
                "maxLines": 1,
                "textOverflow": "ellipsis",
            },
        },
    ]
    lines = [
        {
            "version": "v0.9",
            "createSurface": {
                "surfaceId": "style_enum_probe",
                "catalogId": "ohos.a2ui.extended.catalog.form",
            },
        },
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": "style_enum_probe",
                "root": "root",
                "components": components,
            },
        },
        {
            "version": "v0.9",
            "updateDataModel": {
                "surfaceId": "style_enum_probe",
                "path": "/",
                "value": {},
            },
        },
    ]
    return "\n".join(json.dumps(line, ensure_ascii=False) for line in lines)


def test_all_template_previews_pass_style_enum_validation() -> None:
    cases = build_template_preview_cases()
    assert cases
    for case in cases:
        a2ui = "\n".join(json.dumps(message, ensure_ascii=False) for message in case.messages)
        reporter = validate_card(dsl_text=a2ui)
        assert not reporter.has_code("STYLE_ENUM_INVALID"), case.case_id


def test_style_enum_validation_rejects_wrong_case_value() -> None:
    reporter = validate_card(dsl_text=_minimal_genui("Top"))
    assert reporter.has_code("STYLE_ENUM_INVALID")


def test_style_enum_validation_accepts_protocol_enum_value() -> None:
    reporter = validate_card(dsl_text=_minimal_genui("top"))
    assert not reporter.has_code("STYLE_ENUM_INVALID")


def test_style_enum_rules_are_component_scoped() -> None:
    # 枚举按组件类型区分：Column.alignItems 只允许 start|center|end，因此
    # "top" 写在 Row 上合法、写在 Column 上必须被拦截。
    assert not validate_card(dsl_text=_minimal_genui("top")).has_code(
        "STYLE_ENUM_INVALID"
    )
    assert validate_card(
        dsl_text=_minimal_genui("top", container="Column")
    ).has_code("STYLE_ENUM_INVALID")
