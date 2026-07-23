from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "validators" / "validate_aesthetic.py"


def build_payload(
    *,
    font_color: str | None,
    font_size: int = 14,
    font_weight: int = 400,
    component_type: str = "Text",
    text: str = "需要看清的文字",
    root_styles: dict[str, object] | None = None,
    container_styles: dict[str, object] | None = None,
    component_styles: dict[str, object] | None = None,
) -> str:
    root_style_values: dict[str, object] = {
        "width": 146,
        "height": 146,
        "backgroundColor": "#ffffffff",
        **(root_styles or {}),
    }
    if root_styles and "backgroundColor" not in root_styles:
        root_style_values.pop("backgroundColor", None)

    text_styles: dict[str, object] = {
        "fontSize": font_size,
        "fontWeight": font_weight,
        **(component_styles or {}),
    }
    if font_color is not None:
        text_styles["fontColor"] = font_color
    subject: dict[str, object] = {
        "id": "subject",
        "component": component_type,
        "styles": text_styles,
        "label" if component_type == "Button" else "content": text,
    }

    root_children = ["panel"] if container_styles is not None else ["subject"]
    components: list[dict[str, object]] = [
        {
            "id": "root",
            "component": "Column",
            "children": root_children,
            "styles": root_style_values,
        },
        subject,
    ]
    if container_styles is not None:
        components.insert(
            1,
            {
                "id": "panel",
                "component": "Column",
                "children": ["subject"],
                "styles": container_styles,
            },
        )

    messages = [
        {
            "version": "v0.9",
            "createSurface": {
                "surfaceId": "aesthetic-test",
                "catalogId": "ohos.a2ui.extended.catalog",
                "width": 146,
                "height": 146,
            },
        },
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": "aesthetic-test",
                "root": "root",
                "components": components,
            },
        },
        {
            "version": "v0.9",
            "updateDataModel": {
                "surfaceId": "aesthetic-test",
                "path": "/",
                "value": {"state": "ready"},
            },
        },
    ]
    return "\n".join(json.dumps(item, ensure_ascii=False) for item in messages)


def run_case(payload: str) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    process = subprocess.run(
        [sys.executable, str(SCRIPT), "-", "--format", "json", "--strict"],
        input=payload,
        text=True,
        capture_output=True,
        check=False,
    )
    return process, json.loads(process.stdout)


def run_default_case(
    payload: str, *extra_args: str
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    process = subprocess.run(
        [sys.executable, str(SCRIPT), "-", "--format", "json", *extra_args],
        input=payload,
        text=True,
        capture_output=True,
        check=False,
    )
    return process, json.loads(process.stdout)


def add_stack_image_behind_subject(payload: str, *, nested: bool = False) -> str:
    messages = [json.loads(line) for line in payload.splitlines()]
    components = messages[1]["updateComponents"]["components"]
    root = next(component for component in components if component["id"] == "root")
    root["component"] = "Stack"
    if nested:
        root["children"] = ["backgroundGroup", "subject"]
        components[1:1] = [
            {
                "id": "backgroundGroup",
                "component": "Stack",
                "children": ["backgroundImage"],
                "styles": {"width": 146, "height": 146},
            },
            {
                "id": "backgroundImage",
                "component": "Image",
                "src": "resources/base/media/icon_weather1.svg",
                "styles": {"width": 146, "height": 146, "objectFit": "cover"},
            },
        ]
    else:
        root["children"] = ["backgroundImage", "subject"]
        components.insert(
            1,
            {
                "id": "backgroundImage",
                "component": "Image",
                "src": "resources/base/media/icon_weather1.svg",
                "styles": {"width": 146, "height": 146, "objectFit": "cover"},
            },
        )
    return "\n".join(json.dumps(item, ensure_ascii=False) for item in messages)


def add_stack_scrim(payload: str, extra_styles: dict[str, object] | None = None) -> str:
    messages = [json.loads(line) for line in payload.splitlines()]
    components = messages[1]["updateComponents"]["components"]
    root = next(component for component in components if component["id"] == "root")
    root["children"] = ["backgroundImage", "scrim", "subject"]
    components.insert(
        2,
        {
            "id": "scrim",
            "component": "Text",
            "content": " ",
            "styles": {
                "width": 146,
                "height": 146,
                "backgroundColor": "#ffffffff",
                **(extra_styles or {}),
            },
        },
    )
    return "\n".join(json.dumps(item, ensure_ascii=False) for item in messages)


def issues(report: dict[str, object], code: str) -> list[dict[str, object]]:
    return [item for item in report["diagnostics"] if item["code"] == code]


def resolve_json_pointer(document: object, pointer: str) -> object:
    current = document
    for raw_token in pointer.lstrip("/").split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        current = current[int(token)] if isinstance(current, list) else current[token]
    return current


class AestheticContrastCliTest(unittest.TestCase):
    def test_undetermined_background_requires_review_by_default(self) -> None:
        payload = build_payload(
            font_color="#ffffffff",
            root_styles={"backgroundImage": "resources/base/media/photo.png"},
        )
        process, report = run_default_case(payload)
        self.assertEqual(process.returncode, 1)
        self.assertEqual(report["status"], "needs_review")
        allowed, _ = run_default_case(payload, "--allow-undetermined")
        self.assertEqual(allowed.returncode, 0)

    def test_dynamic_font_size_is_not_silently_classified_as_16fp(self) -> None:
        _, report = run_case(
            build_payload(
                font_color="#ff777777",
                text="很长的动态字号文本不应按默认十六号误判",
                component_styles={
                    "fontSize": "{{ ${/style/fontSize} }}",
                    "width": 30,
                    "maxLines": 1,
                },
            )
        )
        self.assertFalse(issues(report, "AESTHETIC_COLOR_CONTRAST_LOW"))
        self.assertFalse(issues(report, "AESTHETIC_TEXT_CLIP_RISK"))
        self.assertTrue(issues(report, "AESTHETIC_COLOR_CONTRAST_UNDETERMINED"))

    def test_clickable_row_uses_its_own_static_hot_area(self) -> None:
        payload = build_payload(font_color="#ffffffff")
        messages = [json.loads(line) for line in payload.splitlines()]
        components = messages[1]["updateComponents"]["components"]
        root = next(component for component in components if component["id"] == "root")
        subject = next(component for component in components if component["id"] == "subject")
        root["children"] = ["actionRow"]
        components.remove(subject)
        components.extend(
            [
                {
                    "id": "actionRow", "component": "Row", "children": ["subject"],
                    "onClick": [{"call": "open", "args": {}}],
                    "styles": {"width": 20, "height": 20, "backgroundColor": "#ff007dff"},
                },
                {"id": "subject", "component": "Text", "content": "打开",
                 "styles": {"fontColor": "#ffffffff", "fontSize": 12}},
            ]
        )
        _, report = run_case("\n".join(json.dumps(item, ensure_ascii=False) for item in messages))
        issue = issues(report, "AESTHETIC_ACTION_TOO_SMALL")[0]
        self.assertEqual(issue["actual"]["componentId"], "actionRow")

    def test_text_inside_clickable_parent_is_not_false_affordance(self) -> None:
        payload = build_payload(font_color="#ff000000")
        messages = [json.loads(line) for line in payload.splitlines()]
        components = messages[1]["updateComponents"]["components"]
        root = next(component for component in components if component["id"] == "root")
        subject = next(component for component in components if component["id"] == "subject")
        root["children"] = ["actionRow"]
        components.remove(subject)
        components.extend(
            [
                {"id": "actionRow", "component": "Row", "children": ["subject"],
                 "onClick": [{"call": "open", "args": {}}], "styles": {"width": 56, "height": 28}},
                {"id": "subject", "component": "Text", "content": "查看",
                 "styles": {"fontColor": "#ff000000", "width": 56, "height": 28,
                            "backgroundColor": "#ffe8f2ff", "borderRadius": 14}},
            ]
        )
        _, report = run_case("\n".join(json.dumps(item, ensure_ascii=False) for item in messages))
        self.assertFalse(issues(report, "AESTHETIC_AFFORDANCE_FALSE_POSITIVE"))

    def test_three_chromatic_surface_families_trigger_palette_risk(self) -> None:
        payload = build_payload(font_color="#ff000000")
        messages = [json.loads(line) for line in payload.splitlines()]
        components = messages[1]["updateComponents"]["components"]
        root = next(component for component in components if component["id"] == "root")
        root["children"] = ["redPanel", "greenPanel", "bluePanel", "subject"]
        components[1:1] = [
            {
                "id": "redPanel",
                "component": "Column",
                "styles": {"width": 20, "height": 20, "backgroundColor": "#fff44336"},
            },
            {
                "id": "greenPanel",
                "component": "Column",
                "styles": {"width": 20, "height": 20, "backgroundColor": "#ff4caf50"},
            },
            {
                "id": "bluePanel",
                "component": "Column",
                "styles": {"width": 20, "height": 20, "backgroundColor": "#ff2196f3"},
            },
        ]

        _, report = run_case(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in messages)
        )

        issue = issues(report, "AESTHETIC_COLOR_PALETTE_TOO_COMPLEX")[0]
        self.assertEqual(issue["severity"], "warning")

    def test_multiple_gradient_surfaces_trigger_gradient_complexity_risk(self) -> None:
        gradient = {
            "direction": "RightBottom",
            "colors": [["#ff0a59f7", 0], ["#ff46b1e3", 1]],
        }
        _, report = run_case(
            build_payload(
                font_color="#ff000000",
                root_styles={"linearGradient": gradient},
                container_styles={"linearGradient": gradient},
            )
        )

        issue = issues(report, "AESTHETIC_COLOR_GRADIENT_OVERCOMPLEX")[0]
        self.assertEqual(issue["severity"], "warning")

    def test_three_translucent_surface_layers_trigger_alpha_stack_risk(self) -> None:
        payload = build_payload(font_color="#ff000000")
        messages = [json.loads(line) for line in payload.splitlines()]
        components = messages[1]["updateComponents"]["components"]
        root = next(component for component in components if component["id"] == "root")
        root["children"] = ["panelOne"]
        components[1:1] = [
            {
                "id": "panelOne",
                "component": "Column",
                "children": ["panelTwo"],
                "styles": {"backgroundColor": "#33000000"},
            },
            {
                "id": "panelTwo",
                "component": "Column",
                "children": ["panelThree"],
                "styles": {"backgroundColor": "#33000000"},
            },
            {
                "id": "panelThree",
                "component": "Column",
                "children": ["subject"],
                "styles": {"backgroundColor": "#33000000"},
            },
        ]

        _, report = run_case(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in messages)
        )

        issue = issues(report, "AESTHETIC_COLOR_ALPHA_STACK_COMPLEX")[0]
        self.assertEqual(issue["severity"], "warning")

    def test_too_many_font_sizes_trigger_typography_level_risk(self) -> None:
        payload = build_payload(font_color="#ff000000")
        messages = [json.loads(line) for line in payload.splitlines()]
        components = messages[1]["updateComponents"]["components"]
        root = next(component for component in components if component["id"] == "root")
        root["children"] = ["size10", "size12", "size16", "size18", "subject"]
        components[1:1] = [
            {
                "id": f"size{size}",
                "component": "Text",
                "content": "层级",
                "styles": {"fontSize": size, "fontColor": "#ff000000"},
            }
            for size in (10, 12, 16, 18)
        ]

        _, report = run_case(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in messages)
        )

        issue = issues(report, "AESTHETIC_TYPO_TOO_MANY_LEVELS")[0]
        self.assertEqual(issue["severity"], "warning")

    def test_all_bold_text_blocks_trigger_bold_overuse_risk(self) -> None:
        payload = build_payload(font_color="#ff000000", font_weight=700)
        messages = [json.loads(line) for line in payload.splitlines()]
        components = messages[1]["updateComponents"]["components"]
        root = next(component for component in components if component["id"] == "root")
        root["children"] = ["title", "meta", "subject"]
        components[1:1] = [
            {
                "id": component_id,
                "component": "Text",
                "content": "加粗信息",
                "styles": {"fontSize": 14, "fontWeight": 700, "fontColor": "#ff000000"},
            }
            for component_id in ("title", "meta")
        ]

        _, report = run_case(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in messages)
        )

        issue = issues(report, "AESTHETIC_TYPO_BOLD_OVERUSED")[0]
        self.assertEqual(issue["severity"], "warning")

    def test_four_radius_values_trigger_style_consistency_risk(self) -> None:
        payload = build_payload(font_color="#ff000000")
        messages = [json.loads(line) for line in payload.splitlines()]
        components = messages[1]["updateComponents"]["components"]
        root = next(component for component in components if component["id"] == "root")
        root["children"] = ["radius4", "radius8", "radius12", "radius20", "subject"]
        components[1:1] = [
            {
                "id": f"radius{radius}",
                "component": "Column",
                "styles": {
                    "width": 20,
                    "height": 20,
                    "backgroundColor": "#ffffffff",
                    "borderRadius": radius,
                },
            }
            for radius in (4, 8, 12, 20)
        ]

        _, report = run_case(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in messages)
        )

        issue = issues(report, "AESTHETIC_STYLE_RADIUS_INCONSISTENT")[0]
        self.assertEqual(issue["severity"], "warning")

    def test_three_shadowed_components_trigger_shadow_overuse_risk(self) -> None:
        payload = build_payload(font_color="#ff000000")
        messages = [json.loads(line) for line in payload.splitlines()]
        components = messages[1]["updateComponents"]["components"]
        root = next(component for component in components if component["id"] == "root")
        root["children"] = ["shadowOne", "shadowTwo", "shadowThree", "subject"]
        components[1:1] = [
            {
                "id": component_id,
                "component": "Column",
                "styles": {
                    "width": 20,
                    "height": 20,
                    "backgroundColor": "#ffffffff",
                    "shadow": {"radius": 8, "color": "#22000000", "offsetX": 0, "offsetY": 2},
                },
            }
            for component_id in ("shadowOne", "shadowTwo", "shadowThree")
        ]

        _, report = run_case(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in messages)
        )

        issue = issues(report, "AESTHETIC_STYLE_SHADOW_OVERUSED")[0]
        self.assertEqual(issue["severity"], "warning")

    def test_three_border_widths_trigger_stroke_consistency_risk(self) -> None:
        payload = build_payload(font_color="#ff000000")
        messages = [json.loads(line) for line in payload.splitlines()]
        components = messages[1]["updateComponents"]["components"]
        root = next(component for component in components if component["id"] == "root")
        root["children"] = ["stroke1", "stroke2", "stroke3", "subject"]
        components[1:1] = [
            {
                "id": f"stroke{width}",
                "component": "Column",
                "styles": {
                    "width": 20,
                    "height": 20,
                    "backgroundColor": "#ffffffff",
                    "borderColor": "#33000000",
                    "borderWidth": width,
                },
            }
            for width in (1, 2, 3)
        ]

        _, report = run_case(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in messages)
        )

        issue = issues(report, "AESTHETIC_STYLE_STROKE_INCONSISTENT")[0]
        self.assertEqual(issue["severity"], "warning")

    def test_nested_surface_layers_trigger_card_in_card_risk(self) -> None:
        payload = build_payload(font_color="#ff000000")
        messages = [json.loads(line) for line in payload.splitlines()]
        components = messages[1]["updateComponents"]["components"]
        root = next(component for component in components if component["id"] == "root")
        root["children"] = ["surfaceOne"]
        components[1:1] = [
            {
                "id": "surfaceOne",
                "component": "Column",
                "children": ["surfaceTwo"],
                "styles": {"backgroundColor": "#fff1f3f5"},
            },
            {
                "id": "surfaceTwo",
                "component": "Column",
                "children": ["surfaceThree"],
                "styles": {"backgroundColor": "#ffe5e5ea"},
            },
            {
                "id": "surfaceThree",
                "component": "Column",
                "children": ["subject"],
                "styles": {"backgroundColor": "#ffffffff"},
            },
        ]

        _, report = run_case(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in messages)
        )

        issue = issues(report, "AESTHETIC_STYLE_SURFACE_NESTING_EXCESSIVE")[0]
        self.assertEqual(issue["severity"], "warning")

    def test_non_token_spacing_triggers_layout_rhythm_risk(self) -> None:
        payload = build_payload(
            font_color="#ff000000",
            root_styles={"padding": {"left": 5, "right": 5}},
        )
        messages = [json.loads(line) for line in payload.splitlines()]
        root = next(
            component
            for component in messages[1]["updateComponents"]["components"]
            if component["id"] == "root"
        )
        root["itemMargin"] = 7
        _, report = run_case(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in messages)
        )

        issue = issues(report, "AESTHETIC_LAYOUT_SPACING_NON_TOKEN")[0]
        self.assertEqual(issue["severity"], "warning")

    def test_fixed_row_child_width_overflow_is_detected(self) -> None:
        payload = build_payload(
            font_color="#ff000000",
            root_styles={"width": 100, "height": 40},
            component_styles={"width": 120},
        )
        messages = [json.loads(line) for line in payload.splitlines()]
        root = next(
            component
            for component in messages[1]["updateComponents"]["components"]
            if component["id"] == "root"
        )
        root["component"] = "Row"

        _, report = run_case(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in messages)
        )

        issue = issues(report, "AESTHETIC_LAYOUT_BOUNDS_OVERFLOW")[0]
        self.assertEqual(issue["severity"], "warning")

    def test_static_text_that_cannot_fit_triggers_clip_risk(self) -> None:
        _, report = run_case(
            build_payload(
                font_color="#ff000000",
                text="这是一段无法在窄区域完整显示的长文本",
                component_styles={"width": 28, "maxLines": 1},
            )
        )

        issue = issues(report, "AESTHETIC_TEXT_CLIP_RISK")[0]
        self.assertEqual(issue["severity"], "warning")

    def test_static_button_below_minimum_touch_target_is_detected(self) -> None:
        _, report = run_case(
            build_payload(
                font_color="#ffffffff",
                component_type="Button",
                component_styles={
                    "width": 20,
                    "height": 20,
                    "backgroundColor": "#ff007dff",
                },
            )
        )
        self.assertEqual(issues(report, "AESTHETIC_ACTION_TOO_SMALL")[0]["severity"], "warning")

    def test_static_pill_without_action_is_flagged_as_false_affordance(self) -> None:
        _, report = run_case(
            build_payload(
                font_color="#ff000000",
                text="查看",
                component_styles={
                    "width": 56,
                    "height": 28,
                    "backgroundColor": "#ffe8f2ff",
                    "borderRadius": 14,
                },
            )
        )
        self.assertEqual(
            issues(report, "AESTHETIC_AFFORDANCE_FALSE_POSITIVE")[0]["severity"],
            "warning",
        )

    def test_three_equal_text_levels_trigger_missing_hierarchy_risk(self) -> None:
        payload = build_payload(font_color="#ff000000")
        messages = [json.loads(line) for line in payload.splitlines()]
        components = messages[1]["updateComponents"]["components"]
        root = next(component for component in components if component["id"] == "root")
        subject = next(component for component in components if component["id"] == "subject")
        root["children"] = ["title", "state", "detail"]
        components.remove(subject)
        components.extend(
            [
                {"id": item_id, "component": "Text", "content": text,
                 "styles": {"fontColor": "#ff000000", "fontSize": 14}}
                for item_id, text in (("title", "标题"), ("state", "状态"), ("detail", "详情"))
            ]
        )
        _, report = run_case("\n".join(json.dumps(item, ensure_ascii=False) for item in messages))
        self.assertEqual(issues(report, "AESTHETIC_HIERARCHY_NO_PRIMARY")[0]["severity"], "warning")

    def test_three_equal_large_text_levels_trigger_too_many_primary_risk(self) -> None:
        payload = build_payload(font_color="#ff000000")
        messages = [json.loads(line) for line in payload.splitlines()]
        components = messages[1]["updateComponents"]["components"]
        root = next(component for component in components if component["id"] == "root")
        subject = next(component for component in components if component["id"] == "subject")
        root["children"] = ["one", "two", "three"]
        components.remove(subject)
        components.extend(
            [
                {"id": item_id, "component": "Text", "content": text,
                 "styles": {"fontColor": "#ff000000", "fontSize": 20, "fontWeight": 700}}
                for item_id, text in (("one", "一"), ("two", "二"), ("three", "三"))
            ]
        )
        _, report = run_case("\n".join(json.dumps(item, ensure_ascii=False) for item in messages))
        self.assertEqual(issues(report, "AESTHETIC_HIERARCHY_TOO_MANY_PRIMARY")[0]["severity"], "warning")

    def test_oversized_action_over_primary_text_is_detected(self) -> None:
        payload = build_payload(font_color="#ff000000", font_size=14)
        messages = [json.loads(line) for line in payload.splitlines()]
        components = messages[1]["updateComponents"]["components"]
        root = next(component for component in components if component["id"] == "root")
        root["children"] = ["subject", "action"]
        components.append(
            {
                "id": "action", "component": "Button", "label": "立即查看",
                "styles": {"fontColor": "#ffffffff", "fontSize": 24, "fontWeight": 700,
                           "backgroundColor": "#ff007dff"},
            }
        )
        _, report = run_case("\n".join(json.dumps(item, ensure_ascii=False) for item in messages))
        self.assertEqual(issues(report, "AESTHETIC_HIERARCHY_ACTION_OVER_PRIMARY")[0]["severity"], "warning")

    def test_small_card_with_too_many_visible_items_triggers_density_risk(self) -> None:
        payload = build_payload(font_color="#ff000000")
        messages = [json.loads(line) for line in payload.splitlines()]
        components = messages[1]["updateComponents"]["components"]
        root = next(component for component in components if component["id"] == "root")
        subject = next(component for component in components if component["id"] == "subject")
        root["children"] = [f"item{index}" for index in range(11)]
        components.remove(subject)
        components.extend(
            [
                {"id": f"item{index}", "component": "Text", "content": str(index),
                 "styles": {"fontColor": "#ff000000", "fontSize": 12}}
                for index in range(11)
            ]
        )
        _, report = run_case("\n".join(json.dumps(item, ensure_ascii=False) for item in messages))
        self.assertEqual(issues(report, "AESTHETIC_LAYOUT_DENSITY_HIGH")[0]["severity"], "warning")

    def test_four_accent_surfaces_trigger_accent_overuse_risk(self) -> None:
        payload = build_payload(font_color="#ff000000")
        messages = [json.loads(line) for line in payload.splitlines()]
        components = messages[1]["updateComponents"]["components"]
        root = next(component for component in components if component["id"] == "root")
        subject = next(component for component in components if component["id"] == "subject")
        root["children"] = ["red", "blue", "green", "purple"]
        components.remove(subject)
        components.extend(
            [
                {"id": item_id, "component": "Text", "content": "色",
                 "styles": {"fontColor": "#ff000000", "backgroundColor": color}}
                for item_id, color in (("red", "#ffff3b30"), ("blue", "#ff007dff"),
                                       ("green", "#ff34c759"), ("purple", "#ffaf52de"))
            ]
        )
        _, report = run_case("\n".join(json.dumps(item, ensure_ascii=False) for item in messages))
        self.assertEqual(issues(report, "AESTHETIC_COLOR_ACCENT_OVERUSED")[0]["severity"], "warning")

    def test_three_buttons_with_competing_color_roles_trigger_role_drift(self) -> None:
        payload = build_payload(font_color="#ffffffff", component_type="Button")
        messages = [json.loads(line) for line in payload.splitlines()]
        components = messages[1]["updateComponents"]["components"]
        root = next(component for component in components if component["id"] == "root")
        subject = next(component for component in components if component["id"] == "subject")
        root["children"] = ["redAction", "blueAction", "greenAction"]
        components.remove(subject)
        components.extend(
            [
                {"id": item_id, "component": "Button", "label": "操作",
                 "styles": {"fontColor": "#ffffffff", "backgroundColor": color}}
                for item_id, color in (("redAction", "#ffff3b30"), ("blueAction", "#ff007dff"),
                                       ("greenAction", "#ff34c759"))
            ]
        )
        _, report = run_case("\n".join(json.dumps(item, ensure_ascii=False) for item in messages))
        self.assertEqual(issues(report, "AESTHETIC_COLOR_ROLE_INCONSISTENT")[0]["severity"], "warning")

    def test_solid_low_contrast_is_error(self) -> None:
        process, report = run_case(build_payload(font_color="#ffe5e5ea"))
        self.assertEqual(process.returncode, 1)
        self.assertEqual(issues(report, "AESTHETIC_COLOR_CONTRAST_LOW")[0]["severity"], "error")

    def test_translucent_text_is_composited_before_checking(self) -> None:
        _, report = run_case(build_payload(font_color="#99ffffff"))
        self.assertEqual(issues(report, "AESTHETIC_COLOR_CONTRAST_LOW")[0]["severity"], "error")

    def test_translucent_panel_is_composited_over_root(self) -> None:
        _, report = run_case(
            build_payload(
                font_color="#ffffffff",
                container_styles={"backgroundColor": "#33000000"},
            )
        )
        self.assertEqual(issues(report, "AESTHETIC_COLOR_CONTRAST_LOW")[0]["severity"], "error")

    def test_rounded_layer_keeps_exposed_parent_background_candidate(self) -> None:
        payloads = (
            build_payload(
                font_color="#ff000000",
                root_styles={"backgroundColor": "#ff000000"},
                container_styles={
                    "backgroundColor": "#ffffffff",
                    "borderRadius": 24,
                },
            ),
            build_payload(
                font_color="#ff000000",
                root_styles={"backgroundColor": "#ff000000"},
                component_styles={
                    "backgroundColor": "#ffffffff",
                    "borderRadius": 24,
                },
            ),
            build_payload(
                font_color="#ff000000",
                root_styles={"backgroundColor": "#ff000000"},
                container_styles={
                    "backgroundColor": "#80ffffff",
                    "borderRadius": 24,
                },
            ),
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                _, report = run_case(payload)
                self.assertEqual(
                    issues(report, "AESTHETIC_COLOR_CONTRAST_LOW")[0]["severity"],
                    "error",
                )

    def test_gradient_uses_worst_stop(self) -> None:
        _, report = run_case(
            build_payload(
                font_color="#ffffffff",
                root_styles={
                    "linearGradient": {
                        "direction": "RightBottom",
                        "colors": [["#ffffffff", 0], ["#ffe5e5ea", 1]],
                    }
                },
            )
        )
        self.assertEqual(issues(report, "AESTHETIC_COLOR_CONTRAST_LOW")[0]["severity"], "error")

    def test_gradient_does_not_drop_worst_stop_after_first_32(self) -> None:
        colors = [["#ff000000", index / 32] for index in range(32)]
        colors.append(["#ffffffff", 1])
        _, report = run_case(
            build_payload(
                font_color="#ffffffff",
                root_styles={
                    "linearGradient": {
                        "direction": "RightBottom",
                        "colors": colors,
                    }
                },
            )
        )
        self.assertEqual(
            issues(report, "AESTHETIC_COLOR_CONTRAST_LOW")[0]["severity"],
            "error",
        )

    def test_excessive_translucent_gradient_combinations_are_undetermined(self) -> None:
        root_colors = [
            ["#ff000000", index / 64]
            for index in range(65)
        ]
        overlay_colors = [
            ["#80000000", index / 64]
            for index in range(65)
        ]
        _, report = run_case(
            build_payload(
                font_color="#ffffffff",
                root_styles={
                    "linearGradient": {
                        "direction": "RightBottom",
                        "colors": root_colors,
                    }
                },
                container_styles={
                    "linearGradient": {
                        "direction": "RightBottom",
                        "colors": overlay_colors,
                    }
                },
            )
        )
        self.assertEqual(
            issues(report, "AESTHETIC_COLOR_CONTRAST_UNDETERMINED")[0]["severity"],
            "warning",
        )

    def test_button_uses_its_own_background(self) -> None:
        _, report = run_case(
            build_payload(
                font_color="#ffffffff",
                component_type="Button",
                component_styles={"backgroundColor": "#ffe5e5ea"},
            )
        )
        self.assertEqual(issues(report, "AESTHETIC_COLOR_CONTRAST_LOW")[0]["severity"], "error")

    def test_normal_text_between_three_and_four_point_five_is_warning(self) -> None:
        _, report = run_case(build_payload(font_color="#ff317af7"))
        self.assertEqual(issues(report, "AESTHETIC_COLOR_CONTRAST_LOW")[0]["severity"], "warning")

    def test_large_text_uses_three_to_one_threshold(self) -> None:
        process, report = run_case(build_payload(font_color="#ff317af7", font_size=18))
        self.assertEqual(process.returncode, 0)
        self.assertEqual(issues(report, "AESTHETIC_COLOR_CONTRAST_LOW"), [])

    def test_missing_font_size_uses_protocol_default_16fp(self) -> None:
        payload = build_payload(font_color="#ffe5e5ea")
        messages = [json.loads(line) for line in payload.splitlines()]
        subject = next(
            component
            for component in messages[1]["updateComponents"]["components"]
            if component["id"] == "subject"
        )
        subject["styles"].pop("fontSize")
        payload = "\n".join(json.dumps(item, ensure_ascii=False) for item in messages)

        _, report = run_case(payload)

        issue = issues(report, "AESTHETIC_COLOR_CONTRAST_LOW")[0]
        self.assertEqual(issue["actual"]["normalizedFontSize"], 16.0)

    def test_invalid_thresholds_cannot_disable_algorithm_or_emit_nan_json(self) -> None:
        invalid_arguments = (
            ["--normal-min", "0"],
            ["--large-min", "-1"],
            ["--normal-min", "nan"],
            ["--large-min", "inf"],
            ["--normal-min", "2", "--large-min", "3"],
            ["--large-min", "3", "--critical-min", "4"],
        )
        payload = build_payload(font_color="#ffffffff")
        for arguments in invalid_arguments:
            with self.subTest(arguments=arguments):
                process = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPT),
                        "-",
                        "--format",
                        "json",
                        *arguments,
                    ],
                    input=payload,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(process.returncode, 2)
                self.assertEqual(process.stdout, "")
                self.assertNotIn("NaN", process.stdout)

    def test_button_string_font_weights_are_normalized(self) -> None:
        for weight in ("bold", "bolder"):
            with self.subTest(weight=weight):
                process, report = run_case(
                    build_payload(
                        font_color="#ff317af7",
                        font_size=14,
                        component_type="Button",
                        component_styles={
                            "backgroundColor": "#ffffffff",
                            "fontWeight": weight,
                        },
                    )
                )
                self.assertEqual(process.returncode, 0)
                self.assertEqual(
                    issues(report, "AESTHETIC_COLOR_CONTRAST_LOW"), []
                )

        _, report = run_case(
            build_payload(
                font_color="#ff317af7",
                font_size=14,
                component_type="Button",
                component_styles={
                    "backgroundColor": "#ffffffff",
                    "fontWeight": "medium",
                },
            )
        )
        issue = issues(report, "AESTHETIC_COLOR_CONTRAST_LOW")[0]
        self.assertEqual(issue["actual"]["fontWeight"], "medium")
        self.assertEqual(issue["actual"]["normalizedFontWeight"], 500.0)

    def test_adaptive_font_uses_smallest_possible_size_for_threshold(self) -> None:
        for component_type in ("Text", "Button"):
            with self.subTest(component_type=component_type):
                component_styles: dict[str, object] = {
                    "width": 40,
                    "maxLines": 1,
                    "minFontSize": 12,
                    "maxFontSize": 18,
                }
                if component_type == "Button":
                    component_styles["backgroundColor"] = "#ffffffff"
                _, report = run_case(
                    build_payload(
                        font_color="#ff317af7",
                        font_size=18,
                        component_type=component_type,
                        component_styles=component_styles,
                    )
                )
                issue = issues(report, "AESTHETIC_COLOR_CONTRAST_LOW")[0]
                self.assertEqual(issue["severity"], "warning")
                self.assertEqual(issue["actual"]["classificationFontSize"], 12.0)

        _, report = run_case(
            build_payload(
                font_color="#ff317af7",
                font_size=18,
                component_styles={"minFontSize": "{{ ${/font/min} }}"},
            )
        )
        issue = issues(report, "AESTHETIC_COLOR_CONTRAST_LOW")[0]
        self.assertEqual(issue["severity"], "warning")
        self.assertTrue(issue["actual"]["adaptiveFontSizeUncertain"])

    def test_background_image_is_undetermined_without_multimodal_model(self) -> None:
        process, report = run_case(
            build_payload(
                font_color="#ffffffff",
                root_styles={"backgroundImage": "resources/base/media/icon_weather1.svg"},
            )
        )
        self.assertEqual(process.returncode, 1)
        self.assertEqual(
            issues(report, "AESTHETIC_COLOR_CONTRAST_UNDETERMINED")[0]["severity"],
            "warning",
        )

    def test_opaque_panel_can_cover_unknown_image_background(self) -> None:
        process, report = run_case(
            build_payload(
                font_color="#ffffffff",
                root_styles={"backgroundImage": "resources/base/media/icon_weather1.svg"},
                container_styles={"backgroundColor": "#ff000000"},
            )
        )
        self.assertEqual(process.returncode, 0)
        self.assertEqual(report["diagnostics"], [])

    def test_opaque_gradient_does_not_clear_image_dependency(self) -> None:
        _, report = run_case(
            build_payload(
                font_color="#ffffffff",
                root_styles={"backgroundImage": "resources/base/media/icon_weather1.svg"},
                container_styles={
                    "linearGradient": {
                        "direction": "RightBottom",
                        "colors": [["#ff000000", 0], ["#ff111111", 1]],
                    }
                },
            )
        )
        self.assertEqual(
            issues(report, "AESTHETIC_COLOR_CONTRAST_UNDETERMINED")[0]["severity"],
            "warning",
        )

    def test_rounded_solid_layer_does_not_clear_image_dependency(self) -> None:
        payloads = (
            build_payload(
                font_color="#ffffffff",
                root_styles={"backgroundImage": "resources/base/media/icon_weather1.svg"},
                container_styles={
                    "backgroundColor": "#ff000000",
                    "borderRadius": 73,
                },
            ),
            build_payload(
                font_color="#ffffffff",
                root_styles={"backgroundImage": "resources/base/media/icon_weather1.svg"},
                component_styles={
                    "backgroundColor": "#ff000000",
                    "borderRadius": 73,
                },
            ),
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                _, report = run_case(payload)
                self.assertEqual(
                    issues(report, "AESTHETIC_COLOR_CONTRAST_UNDETERMINED")[0][
                        "severity"
                    ],
                    "warning",
                )

    def test_full_size_opaque_solid_stack_scrim_can_cover_image(self) -> None:
        payload = add_stack_scrim(
            add_stack_image_behind_subject(build_payload(font_color="#ff000000"))
        )

        process, report = run_case(payload)

        self.assertEqual(process.returncode, 0)
        self.assertEqual(report["diagnostics"], [])

    def test_numeric_scrim_cannot_clear_image_when_stack_constraint_can_expand(self) -> None:
        payload = add_stack_scrim(
            add_stack_image_behind_subject(
                build_payload(
                    font_color="#ff000000",
                    root_styles={
                        "width": 100,
                        "height": 100,
                        "constraintSize": {"minWidth": 146, "minHeight": 146},
                    },
                )
            ),
            {"width": 100, "height": 100},
        )

        process, report = run_case(payload)

        self.assertEqual(process.returncode, 1)
        self.assertEqual(
            issues(report, "AESTHETIC_COLOR_CONTRAST_UNDETERMINED")[0]["severity"],
            "warning",
        )

    def test_match_parent_scrim_can_cover_constrained_stack_without_reading_image(self) -> None:
        payload = add_stack_scrim(
            add_stack_image_behind_subject(
                build_payload(
                    font_color="#ff000000",
                    root_styles={
                        "width": 100,
                        "height": 100,
                        "constraintSize": {"minWidth": 146, "minHeight": 146},
                    },
                )
            ),
            {"width": "matchParent", "height": "matchParent"},
        )

        process, report = run_case(payload)

        self.assertEqual(process.returncode, 0)
        self.assertEqual(report["diagnostics"], [])

    def test_stack_scrim_must_be_visible_and_pure_solid_to_cover_image(self) -> None:
        invalid_scrims = (
            {"visibility": "hidden"},
            {"backgroundImage": "resources/base/media/icon_watermark.svg"},
            {
                "linearGradient": {
                    "direction": "RightBottom",
                    "colors": [["#ffffffff", 0], ["#fff5f5f5", 1]],
                }
            },
            {"borderRadius": 24},
            {"constraintSize": {"maxWidth": 100, "maxHeight": 100}},
        )
        for extra_styles in invalid_scrims:
            with self.subTest(extra_styles=extra_styles):
                payload = add_stack_scrim(
                    add_stack_image_behind_subject(
                        build_payload(font_color="#ff000000")
                    ),
                    extra_styles,
                )
                _, report = run_case(payload)
                self.assertEqual(
                    issues(report, "AESTHETIC_COLOR_CONTRAST_UNDETERMINED")[0][
                        "severity"
                    ],
                    "warning",
                )

    def test_dynamic_font_color_is_undetermined(self) -> None:
        _, report = run_case(build_payload(font_color="{{ ${/theme/fontColor} }}"))
        self.assertEqual(
            issues(report, "AESTHETIC_COLOR_CONTRAST_UNDETERMINED")[0]["severity"],
            "warning",
        )

    def test_high_contrast_text_passes(self) -> None:
        process, report = run_case(build_payload(font_color="#ff000000"))
        self.assertEqual(process.returncode, 0)
        self.assertEqual(report["diagnostics"], [])

    def test_blank_decorative_text_is_ignored(self) -> None:
        process, report = run_case(build_payload(font_color=None, text=" "))
        self.assertEqual(process.returncode, 0)
        self.assertEqual(report["diagnostics"], [])

    def test_static_hidden_text_or_ancestor_is_ignored_but_dynamic_is_checked(self) -> None:
        for visibility in ("hidden", "none"):
            for location in ("self", "ancestor"):
                with self.subTest(visibility=visibility, location=location):
                    payload = build_payload(
                        font_color="#ffffffff",
                        component_styles=(
                            {"visibility": visibility} if location == "self" else None
                        ),
                        container_styles=(
                            {"visibility": visibility} if location == "ancestor" else None
                        ),
                    )
                    process, report = run_case(payload)
                    self.assertEqual(process.returncode, 0)
                    self.assertEqual(report["summary"]["textLikeCount"], 0)
                    self.assertEqual(report["summary"]["checkedCount"], 0)
                    self.assertEqual(report["diagnostics"], [])

        _, report = run_case(
            build_payload(
                font_color="#ffffffff",
                component_styles={"visibility": "{{ ${/state/visible} }}"},
            )
        )
        self.assertEqual(
            issues(report, "AESTHETIC_COLOR_CONTRAST_LOW")[0]["severity"],
            "error",
        )

    def test_static_hidden_stack_image_does_not_taint_visible_text(self) -> None:
        payload = add_stack_image_behind_subject(
            build_payload(font_color="#ff000000")
        )
        messages = [json.loads(line) for line in payload.splitlines()]
        image = next(
            component
            for component in messages[1]["updateComponents"]["components"]
            if component["id"] == "backgroundImage"
        )
        image["styles"]["visibility"] = "hidden"
        payload = "\n".join(json.dumps(item, ensure_ascii=False) for item in messages)

        process, report = run_case(payload)

        self.assertEqual(process.returncode, 0)
        self.assertEqual(report["diagnostics"], [])

    def test_stack_image_sibling_behind_text_is_undetermined(self) -> None:
        _, report = run_case(
            add_stack_image_behind_subject(build_payload(font_color="#ffffffff"))
        )
        self.assertEqual(
            issues(report, "AESTHETIC_COLOR_CONTRAST_UNDETERMINED")[0]["severity"],
            "warning",
        )

    def test_nested_stack_image_branch_behind_text_is_undetermined(self) -> None:
        _, report = run_case(
            add_stack_image_behind_subject(
                build_payload(font_color="#ff000000"), nested=True
            )
        )
        self.assertEqual(
            issues(report, "AESTHETIC_COLOR_CONTRAST_UNDETERMINED")[0]["severity"],
            "warning",
        )

    def test_reported_json_pointer_resolves_in_source_message(self) -> None:
        payload = build_payload(font_color="#ffe5e5ea")
        _, report = run_case(payload)
        pointer = issues(report, "AESTHETIC_COLOR_CONTRAST_LOW")[0]["jsonPointer"]
        update_message = next(
            message
            for message in (json.loads(line) for line in payload.splitlines())
            if "updateComponents" in message
        )
        self.assertEqual(resolve_json_pointer(update_message, pointer), "#ffe5e5ea")


if __name__ == "__main__":
    unittest.main()
