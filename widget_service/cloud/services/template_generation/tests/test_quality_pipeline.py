"""确保目录内的美学校验器接入公共卡片校验流程。"""

from __future__ import annotations

import json
from typing import Any

from services.card_validation import validate_card


def _genui(*, template_root: bool = False) -> str:
    components: list[dict[str, Any]] = [
        {
            "id": "root",
            "component": "Column",
            "children": ["template_root" if template_root else "title_text"],
            "styles": {"width": "matchParent", "height": "matchParent"},
        },
    ]
    if template_root:
        components.append(
            {
                "id": "template_root",
                "component": "Column",
                "children": ["title_text"],
                "styles": {"width": "matchParent", "height": "matchParent"},
            }
        )
    components.append(
        {
            "id": "title_text",
            "component": "Text",
            "content": "天气",
            "styles": {"fontSize": 13, "fontColor": "#FF000000"},
        }
    )
    messages = [
        {
            "version": "v0.9",
            "createSurface": {
                "surfaceId": "quality_pipeline_test",
                "catalogId": "ohos.a2ui.extended.catalog.form",
            },
        },
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": "quality_pipeline_test",
                "root": "root",
                "components": components,
            },
        },
        {
            "version": "v0.9",
            "updateDataModel": {
                "surfaceId": "quality_pipeline_test",
                "path": "/",
                "value": {},
            },
        },
    ]
    return "\n".join(json.dumps(message) for message in messages)


def test_public_validation_runs_quality_directory_validators() -> None:
    reporter = validate_card(dsl_text=_genui())

    assert reporter.has_code("TYPE.FONT_SIZE_STEP")


def test_template_root_still_skips_the_whole_quality_stage() -> None:
    reporter = validate_card(dsl_text=_genui(template_root=True))

    assert not any(item.stage == "quality" for item in reporter.diagnostics)
