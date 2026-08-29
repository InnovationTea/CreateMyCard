"""最终产物样式枚举校验回归（已场景金样化，Layer C）。

背景：日程模板曾在 ``alignItems`` 上写出 ``"Top"``（协议只允许小写
``top``），模板预览与公共 Compact 转换都未拦截，非法值随最终 A2UI 产物
下发。ComponentValidator 现按 ``data/validator_rules/config/style.json``
的 ``enumValues`` 对最终产物做硬校验（错误码 ``STYLE_ENUM_INVALID``）。

原先 4 个独立用例全部转为场景金样：全部模板预览产物的枚举清扫结果
（用例数 + 违例清单），以及大小写差分与 Row/Column 组件作用域差分的
诊断码，均由 ``tests/goldens/scenarios/`` 下的快照整体冻结。校验规则或
模板预览改动后按 golden 工作流 ``check --diff`` / ``bless --declared``
复核；本文件不再保留独立测试函数，pytest 仅通过导入完成场景注册。
"""

from __future__ import annotations

import json
from typing import Any

from services.card_validation import validate_card
from services.template_generation.engine.cardplan.preview_dataset import (
    build_template_preview_cases,
)
from services.template_generation.test_support.golden_scenarios import scenario

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


def _diagnostic_codes(dsl_text: str) -> list[str]:
    return sorted({item.code for item in validate_card(dsl_text=dsl_text).diagnostics})


@scenario("style_enum__preview_sweep")
def _build_preview_sweep() -> dict[str, Any]:
    cases = build_template_preview_cases()
    assert cases
    violations: dict[str, list[str]] = {}
    for case in cases:
        a2ui = "\n".join(
            json.dumps(message, ensure_ascii=False) for message in case.messages
        )
        reporter = validate_card(dsl_text=a2ui)
        codes = [
            item.code for item in reporter.diagnostics
            if item.code == "STYLE_ENUM_INVALID"
        ]
        if codes:
            violations[case.case_id] = codes
    return {"caseCount": len(cases), "styleEnumViolations": violations}


@scenario("style_enum__probes")
def _build_probes() -> dict[str, Any]:
    # 枚举按组件类型区分：Column.alignItems 只允许 start|center|end，因此
    # "top" 写在 Row 上合法、写在 Column 上必须被拦截。
    return {
        "row_align_top": _diagnostic_codes(_minimal_genui("top")),
        "row_align_wrong_case": _diagnostic_codes(_minimal_genui("Top")),
        "column_align_top": _diagnostic_codes(_minimal_genui("top", container="Column")),
    }
