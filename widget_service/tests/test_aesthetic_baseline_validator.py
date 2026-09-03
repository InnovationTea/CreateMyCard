import json

from services.card_validation import validate_card


def _dsl(components: list[dict]) -> str:
    rows = [
        {
            "version": "v0.9",
            "createSurface": {
                "surfaceId": "card",
                "catalogId": "ohos.a2ui.extended.catalog.form",
            },
        },
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": "card",
                "root": "root",
                "components": components,
            },
        },
        {"version": "v0.9", "updateDataModel": {"surfaceId": "card", "path": "/", "value": {}}},
    ]
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def _root(*children: str) -> dict:
    return {
        "id": "root",
        "component": "Column",
        "children": list(children),
        "styles": {},
    }


def test_aesthetic_baseline_rejects_emoji_content() -> None:
    reporter = validate_card(
        dsl_text=_dsl([_root("icon"), {"id": "icon", "component": "Text", "content": "☀️"}])
    )

    diagnostics = [item for item in reporter.diagnostics if item.code == "ASSET.EMOJI_ICON"]
    assert len(diagnostics) == 1
    assert diagnostics[0].severity == "error"
    assert diagnostics[0].stage == "hard"


def test_aesthetic_baseline_rejects_small_text_and_button_fonts() -> None:
    components = [
        _root("text", "button"),
        {
            "id": "text",
            "component": "Text",
            "content": "label",
            "styles": {"fontSize": "7vp"},
        },
        {
            "id": "button",
            "component": "Button",
            "label": "go",
            "styles": {"fontSize": 0},
        },
    ]
    reporter = validate_card(dsl_text=_dsl(components))

    diagnostics = [item for item in reporter.diagnostics if item.code == "TYPE.FONT_SIZE_MIN"]
    assert len(diagnostics) == 2
    assert all(item.severity == "error" for item in diagnostics)


def test_aesthetic_baseline_allows_dynamic_and_readable_values() -> None:
    components = [
        _root("text", "button"),
        {
            "id": "text",
            "component": "Text",
            "content": "{{ ${/data/label} }}",
            "styles": {"fontSize": "8vp"},
        },
        {
            "id": "button",
            "component": "Button",
            "label": "go",
            "styles": {"fontSize": "{{ ${/data/fontSize} }}"},
        },
    ]
    reporter = validate_card(dsl_text=_dsl(components))

    assert not any(
        item.code in {"ASSET.EMOJI_ICON", "TYPE.FONT_SIZE_MIN"}
        for item in reporter.diagnostics
    )
