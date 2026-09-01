import json

from services.card_validation import validate_card


def _dsl(text_color: str, background_color: str) -> str:
    rows = [
        {"version": "v0.9", "createSurface": {"surfaceId": "card"}},
        {
            "version": "v0.9",
            "updateComponents": {
                "root": "root",
                "components": [
                    {
                        "id": "root",
                        "component": "Column",
                        "children": ["label"],
                        "styles": {"backgroundColor": background_color},
                    },
                    {
                        "id": "label",
                        "component": "Text",
                        "content": "Readable label",
                        "styles": {"fontColor": text_color},
                    },
                ],
            },
        },
        {"version": "v0.9", "updateDataModel": {"path": "/", "value": {}}},
    ]
    return "\n".join(json.dumps(row) for row in rows)


def test_contrast_validator_reports_low_contrast_text() -> None:
    reporter = validate_card(dsl_text=_dsl("#FF777777", "#FFFFFFFF"))

    contrast = [item for item in reporter.diagnostics if item.code == "VISUAL.CONTRAST"]
    assert len(contrast) == 1
    assert contrast[0].severity == "warning"
    assert contrast[0].actual < 4.5


def test_contrast_validator_accepts_high_contrast_text() -> None:
    reporter = validate_card(dsl_text=_dsl("#FF000000", "#FFFFFFFF"))

    assert not any(item.code == "VISUAL.CONTRAST" for item in reporter.diagnostics)
