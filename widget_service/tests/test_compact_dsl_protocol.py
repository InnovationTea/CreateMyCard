# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from services.compact_dsl_protocol import (
    COMPONENT_WHITELIST,
    FORM_FONT_SIZES,
    FORM_SPACING,
    apply_compact_dsl_data_bindings,
    build_compact_binding_context,
    build_compact_dsl_system_prompt,
    build_compact_generation_context,
    preflight_compact_dsl,
    validate_compact_dsl,
)


class CompactDslFormParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1] / "cloud"
        profile_root = cls.root / "data" / "protocol_profiles" / "compact-dsl-v1"
        cls.documents = {}
        for name in (
            "protocol.md",
            "component-catalog.md",
            "data-binding.md",
            "system-prompt.md",
        ):
            cls.documents[name] = (profile_root / name).read_text(encoding="utf-8")

    def test_component_scope_matches_a2ui_form(self) -> None:
        self.assertEqual(
            COMPONENT_WHITELIST,
            (
                "Text",
                "Image",
                "Divider",
                "Progress",
                "Button",
                "Checkbox",
                "Row",
                "Column",
                "List",
                "Stack",
            ),
        )
        a2ui_catalog = (
            self.root
            / "data"
            / "protocol_profiles"
            / "a2ui-form-rom6.0-v1"
            / "component-catalog.md"
        ).read_text(encoding="utf-8")
        allowed_line = re.search(r"允许组件：(.+)", a2ui_catalog)
        self.assertIsNotNone(allowed_line)
        a2ui_components = re.findall(r"`([^`]+)`", allowed_line.group(1))
        self.assertEqual(set(COMPONENT_WHITELIST), set(a2ui_components))
        compact_line = re.search(r"允许组件：(.+)", self.documents["component-catalog.md"])
        self.assertIsNotNone(compact_line)
        compact_components = re.findall(r"`([^`]+)`", compact_line.group(1))
        self.assertEqual(list(COMPONENT_WHITELIST), compact_components)
        self.assertEqual(FORM_FONT_SIZES, {10, 12, 14, 16, 18, 20, 32, 40})
        self.assertEqual(FORM_SPACING, {0, 2, 4, 6, 8, 10, 12, 14, 16})

    def test_prompt_uses_profile_instead_of_independent_design_rules(self) -> None:
        profile = {
            "componentWhitelist": list(COMPONENT_WHITELIST),
            "documents": self.documents,
        }
        prompt = build_compact_dsl_system_prompt(profile)

        self.assertIn("2x2 最多 3 个主区域", prompt)
        self.assertIn("最多展示 4 项用户字段", prompt)
        self.assertIn("常用 light hex", prompt)
        self.assertIn("orb、bokeh", prompt)
        self.assertIn("必显文字不用 ellipsis", prompt)
        self.assertIn("只能靠短序列化提速", prompt)
        self.assertIn("task.requiredContent", prompt)
        self.assertIn("task.requiredActions", prompt)
        self.assertIn("“降水概率 + 动态值”", prompt)
        self.assertIn("不能只靠图标、位置或颜色", prompt)
        self.assertIn("不因候选多就生成多个按钮", prompt)
        self.assertIn("湿度可用水滴图标和百分号共同表达", prompt)
        self.assertIn("没有匹配素材就省略主图", prompt)
        self.assertIn("没有 Dynamic binding context 时", prompt)
        self.assertIn("不显示未请求的地点或更新时间", prompt)
        self.assertIn("不缩成“去公司”", prompt)
        self.assertIn("白色圆形承载面", prompt)
        self.assertIn("导航、打开和打车不用绿色", prompt)
        self.assertIn("Compact DSL 完整示例", prompt)
        self.assertIn("2x4 通常\n  10-16 个、最多 20 个组件行", prompt)
        self.assertIn("不为凑数量添加组件", prompt)
        self.assertIn("短且有语义的 ASCII", prompt)
        self.assertIn("固定 `height`、`borderRadius`、`clip`、`constraintSize`", prompt)
        self.assertIn("默认 `objectFit:\"contain\"` 由服务补齐", prompt)
        self.assertIn("必须把 `task.title` 作为字面量标题显示", prompt)
        self.assertIn("静态值和单位合并在一个 Text", prompt)
        self.assertIn('intentName:"ViewCalendarEvent"', prompt)
        self.assertIn("label 必须是“查看日程”", prompt)
        self.assertIn("才增加 description 或 eventLocation", prompt)
        self.assertIn("不改用无关字段", prompt)
        self.assertIn("聚合统计只保留一个主值", prompt)
        self.assertIn("不生成第二个时间或重复摘要", prompt)
        self.assertIn("不用泛化的", prompt)
        self.assertIn("Text, Image, Divider", prompt)
        for component_name in ("TextInput", "Toggle", "Radio", "Select", "Web", "Grid", "If"):
            self.assertNotIn(component_name, prompt)
        self.assertNotIn("## protocol.md", prompt)
        self.assertNotIn("## component-catalog.md", prompt)
        self.assertIn("action 不能出现在组件行闭合", prompt)
        self.assertIn("不输出 Image.filter", prompt)
        example_blocks = re.findall(r"```text\n(.*?)\n```", prompt, re.DOTALL)
        self.assertTrue(example_blocks)
        weather_example = example_blocks[-1]
        self.assertIn('"#86C5E3"', weather_example)
        self.assertIn('"label":"看天气"', weather_example)
        self.assertNotIn('"content":"实时温度"', weather_example)
        self.assertNotIn('"content":"24° / 32°"', weather_example)
        self.assertIn('"src":"resources/base/media/drop_1.svg"', weather_example)
        self.assertNotIn("/data/weather/current/feelsLikeC", weather_example)
        weather_rows = [json.loads(line) for line in weather_example.splitlines()]
        component_rows = [row for row in weather_rows if len(row) >= 3]
        components_by_id = {row[0]: row for row in component_rows}
        self.assertEqual(len(component_rows), 12)
        self.assertLess(len(weather_example), 2200)
        self.assertLess(len(prompt), 8200)
        self.assertNotIn('"constraintSize"', weather_example)
        self.assertNotIn('"objectFit"', weather_example)
        self.assertEqual(
            components_by_id["root"][3],
            ["head", "main", "humidity", "action"],
        )
        self.assertEqual(
            components_by_id["action"][2]["backgroundColor"],
            "#FF0A59F7",
        )
        self.assertEqual(components_by_id["action"][2]["label"], "看天气")
        cardspec = {"suggestSize": "2x2"}
        preflight = preflight_compact_dsl(
            weather_example,
            cardspec,
            [],
            [
                {
                    "call": "clickToDeeplink",
                    "args": {
                        "uri": "hww://www.huawei.com/totemweather?"
                        "enterType=share&cityCode="
                    },
                }
            ],
        )
        self.assertTrue(preflight.passed)
        self.assertIn("FORM_CONTRACT_REPAIRED", preflight.repairs)
        normalized_rows = [
            json.loads(line)
            for line in preflight.genui.splitlines()
        ]
        normalized_by_id = {
            row[0]: row
            for row in normalized_rows
            if len(row) >= 3
        }
        self.assertIn("constraintSize", normalized_by_id["root"][2])
        self.assertEqual(normalized_by_id["weatherIcon"][2]["objectFit"], "contain")
        report = validate_compact_dsl(
            preflight.genui,
            cardspec,
            list(COMPONENT_WHITELIST),
        )
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])

    def test_weather_content_is_enforced_without_business_semantic_hard_failures(self) -> None:
        example_blocks = re.findall(
            r"```text\n(.*?)\n```",
            self.documents["system-prompt.md"],
            re.DOTALL,
        )
        source_rows = [json.loads(line) for line in example_blocks[-1].splitlines()]
        cardspec = {
            "suggestSize": "2x2",
            "dataBindings": [
                {
                    "capabilityId": "ViewWeather",
                    "writeResultTo": "/data/weather",
                }
            ],
        }
        source = "\n".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":"))
            for row in source_rows
        )
        preflight = preflight_compact_dsl(
            source,
            cardspec,
            [],
            [
                {
                    "call": "clickToDeeplink",
                    "args": {
                        "uri": "hww://www.huawei.com/totemweather?"
                        "enterType=share&cityCode="
                    },
                }
            ],
        )
        self.assertTrue(preflight.passed)
        source_rows = [
            json.loads(line)
            for line in preflight.genui.splitlines()
        ]
        weather_task = {
            "userQuery": "青浦天气桌卡",
            "title": "青浦天气",
            "description": "实时天气",
        }
        baseline = "\n".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":"))
            for row in source_rows
        )
        baseline_report = validate_compact_dsl(
            baseline,
            cardspec,
            task_spec=weather_task,
        )

        self.assertEqual(baseline_report.errors, [])

        missing_humidity_value_rows: list[list[object]] = []
        for source_row in source_rows:
            row = json.loads(json.dumps(source_row, ensure_ascii=False))
            if row[0] == "/data/weather/current/humidityPercent":
                continue
            if row[0] == "humidityValue":
                row[2]["content"] = "62"
            missing_humidity_value_rows.append(row)
        missing_humidity_value = "\n".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":"))
            for row in missing_humidity_value_rows
        )
        missing_humidity_report = validate_compact_dsl(
            missing_humidity_value,
            cardspec,
            task_spec=weather_task,
        )

        self.assertTrue(
            any(
                'userQuery content "湿度" requires a visible dynamic value' in error
                for error in missing_humidity_report.errors
            )
        )

        cloudy_rows = json.loads(json.dumps(source_rows, ensure_ascii=False))
        for row in cloudy_rows:
            if row[0] == "/data/weather/current/condition":
                row[1] = "多云"
        cloudy = "\n".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":"))
            for row in cloudy_rows
        )
        cloudy_report = validate_compact_dsl(
            cloudy,
            cardspec,
            task_spec=weather_task,
        )

        self.assertFalse(
            any("does not match preview condition" in error for error in cloudy_report.errors)
        )
        self.assertTrue(
            any("does not match preview condition" in warning for warning in cloudy_report.warnings)
        )

        forecast_report = validate_compact_dsl(
            baseline,
            cardspec,
            task_spec=weather_task | {"userQuery": "青浦天气预报桌卡"},
        )

        self.assertTrue(
            any(
                'userQuery content "天气预报" requires a visible dynamic value' in error
                for error in forecast_report.errors
            )
        )

        forecast_rows = json.loads(json.dumps(source_rows, ensure_ascii=False))
        for row in forecast_rows:
            if row[0] == "main":
                row[3] = ["forecast_temp", "temp"]
        forecast_rows = [row for row in forecast_rows if row[0] != "weatherIcon"]
        action_index = next(
            index
            for index, row in enumerate(forecast_rows)
            if row[0] == "action"
        )
        forecast_rows[action_index:action_index] = [
            [
                "forecast_temp",
                "Text",
                {
                    "width": 40,
                    "height": 16,
                    "content": {"path": "/data/weather/daily/0/temperatureRangeText"},
                    "fontSize": 10,
                    "maxLines": 1,
                },
            ],
            ["/data/weather/daily/0/temperatureRangeText", "24° / 32°"],
        ]
        forecast_with_value = "\n".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":"))
            for row in forecast_rows
        )
        forecast_value_report = validate_compact_dsl(
            forecast_with_value,
            cardspec,
            task_spec=weather_task | {"userQuery": "青浦天气预报桌卡"},
        )

        self.assertFalse(
            any("天气预报" in error for error in forecast_value_report.errors)
        )

    def test_rain_probability_query_requires_label_and_dynamic_value(self) -> None:
        genui = "\n".join(
            (
                '["root","Column",{"width":"matchParent","height":140,"padding":12,'
                '"borderRadius":18,"clip":true,"space":6,"linearGradient":'
                '{"direction":"RightBottom","colors":[["#FF61CFBE",0],["#FF92C48D",1]]}},'
                '["title","main_row","action"]]',
                '["title","Text",{"width":116,"height":20,"content":"雨天打车",'
                '"fontSize":14,"fontWeight":700,"fontColor":"#E5000000","maxLines":1}]',
                '["main_row","Row",{"width":116,"height":52,"alignItems":"center",'
                '"space":8},["rain_icon","rain_column"]]',
                '["rain_icon","Image",{"width":40,"height":40,'
                '"src":"resources/base/media/drop_1.svg","objectFit":"contain"}]',
                '["rain_column","Column",{"width":68,"height":52,"space":4},'
                '["condition_text","rain_label","rain_value"]]',
                '["condition_text","Text",{"width":68,"height":12,'
                '"content":{"path":"/data/weather/current/condition"},'
                '"fontSize":12,"fontWeight":500,"fontColor":"#99000000","maxLines":1}]',
                '["/data/weather/current/condition","小雨"]',
                '["rain_label","Text",{"width":68,"height":12,"content":"降水概率",'
                '"fontSize":12,"fontWeight":500,"fontColor":"#99000000","maxLines":1}]',
                '["rain_value","Text",{"width":68,"height":20,'
                '"content":{"path":"/data/weather/daily/0/rainProbabilityPercent"},'
                '"fontSize":20,"fontWeight":700,"fontColor":"#E5000000","maxLines":1}]',
                '["/data/weather/daily/0/rainProbabilityPercent","73%"]',
                '["action","Button",{"width":116,"height":32,"label":"打车去公司",'
                '"fontSize":12,"fontWeight":600,"fontColor":"#FFFFFFFF",'
                '"backgroundColor":"#FF0A59F7","borderRadius":16,'
                '"action":{"functionCall":{"call":"clickToIntent",'
                '"args":{"intentName":"StartNavigate"}}}}]',
            )
        )
        cardspec = {
            "suggestSize": "2x2",
            "dataBindings": [
                {
                    "capabilityId": "ViewWeather",
                    "writeResultTo": "/data/weather",
                }
            ],
        }
        task_spec = {
            "userQuery": "做一个雨天打车卡片，显示今天天气状况和降水概率，支持一键打车去公司",
        }

        report = validate_compact_dsl(genui, cardspec, task_spec=task_spec)

        self.assertEqual([], report.errors)

        missing_label_rows: list[str] = []
        for line in genui.splitlines():
            row = json.loads(line)
            if row[0] == "rain_label":
                continue
            if row[0] == "rain_column":
                row[3] = ["rain_value"]
            missing_label_rows.append(
                json.dumps(row, ensure_ascii=False, separators=(",", ":"))
            )
        missing_label = "\n".join(missing_label_rows)

        missing_label_report = validate_compact_dsl(
            missing_label,
            cardspec,
            task_spec=task_spec,
        )

        self.assertTrue(
            any("visible semantic label" in error for error in missing_label_report.errors)
        )

        missing_value_rows: list[str] = []
        for line in genui.splitlines():
            row = json.loads(line)
            if row[0] == "/data/weather/daily/0/rainProbabilityPercent":
                continue
            if row[0] == "rain_value":
                row[2]["content"] = "73%"
            missing_value_rows.append(
                json.dumps(row, ensure_ascii=False, separators=(",", ":"))
            )
        missing_value = "\n".join(missing_value_rows)

        missing_value_report = validate_compact_dsl(
            missing_value,
            cardspec,
            task_spec=task_spec,
        )

        self.assertTrue(
            any("visible dynamic value" in error for error in missing_value_report.errors)
        )

    def test_all_a2ui_baseline_scenarios_publish_required_content(self) -> None:
        cases = (
            (
                "青浦天气桌卡",
                ("天气状况", "温度", "湿度"),
                (),
            ),
            (
                "做一个雨天打车卡片，显示今天天气状况和降水概率，支持一键打车去公司",
                ("天气状况", "降水概率"),
                ("打车去公司",),
            ),
            (
                "创建一个低电模式卡片，看看电量和电池状态，能开启省电模式吗",
                ("电量", "电池状态"),
                ("开启省电模式",),
            ),
            (
                "创建一个戴耳机播控卡片，展示耳机电量和华为音乐每日推荐",
                ("耳机电量", "华为音乐每日推荐"),
                ("打开华为音乐每日推荐",),
            ),
            (
                "创建一个睡眠卡片，展示睡眠状态、睡眠时长占比，支持设置闹钟提醒",
                ("睡眠状态", "睡眠时长", "睡眠时长占比"),
                ("设置闹钟提醒",),
            ),
            (
                "创建一个专注模式卡片，展示下一场会议名称和时间",
                ("下一场会议名称", "下一场会议开始时间"),
                (),
            ),
            (
                "创建一个当下日程卡片，展示今天的日程安排和会议跳转入口",
                ("今日日程名称", "今日日程开始时间"),
                ("查看日程",),
            ),
            (
                "做一个防沉迷卡片，看看本周APP使用时长",
                ("本周APP使用时长",),
                (),
            ),
            (
                "创建一个清理无忧卡片，看看剩余空间和占用占比",
                ("剩余空间", "占用占比"),
                (),
            ),
        )

        for user_query, expected_content, expected_actions in cases:
            with self.subTest(user_query=user_query):
                context = build_compact_generation_context(
                    {
                        "userQuery": user_query,
                        "size": "2x4",
                        "title": "测试卡片",
                        "description": "测试",
                    }
                )
                self.assertEqual(
                    list(expected_content),
                    context["task"]["requiredContent"],
                )
                if expected_actions:
                    self.assertEqual(
                        list(expected_actions),
                        context["task"]["requiredActions"],
                    )
                else:
                    self.assertNotIn("requiredActions", context["task"])

    def test_unavailable_scenario_action_is_not_required(self) -> None:
        task_spec = {
            "userQuery": "低电模式，显示电量和电池状态，开启省电模式",
            "size": "2x2",
            "title": "低电模式",
            "description": "电量与电池状态",
            "eventCandidates": [],
        }
        context = build_compact_generation_context(task_spec)

        self.assertNotIn("requiredActions", context["task"])

        genui = "\n".join(
            (
                '["root","Column",{"width":"matchParent","height":140,'
                '"padding":12,"borderRadius":18,"clip":true,'
                '"backgroundColor":"#FFFFFFFF"},["title"]]',
                '["title","Text",{"content":"低电模式","fontSize":14,'
                '"fontWeight":700,"fontColor":"#E5000000","maxLines":1}]',
            )
        )
        report = validate_compact_dsl(
            genui,
            {"suggestSize": "2x2"},
            task_spec=task_spec,
        )

        self.assertFalse(
            any("userQuery action" in error for error in report.errors)
        )

    def test_all_a2ui_baseline_scenarios_reject_missing_content(self) -> None:
        cases = (
            ("青浦天气桌卡", ("天气状况", "温度", "湿度"), ()),
            (
                "雨天打车，显示天气状况和降水概率，打车去公司",
                ("天气状况", "降水概率"),
                ("打车去公司",),
            ),
            (
                "低电模式，显示电量和电池状态，开启省电模式",
                ("电量", "电池状态"),
                ("开启省电模式",),
            ),
            (
                "耳机播控，显示耳机电量和华为音乐每日推荐",
                ("耳机电量", "华为音乐每日推荐"),
                ("打开华为音乐每日推荐",),
            ),
            (
                "睡眠卡片，显示睡眠状态、睡眠时长占比并设置闹钟提醒",
                ("睡眠状态", "睡眠时长", "睡眠时长占比"),
                ("设置闹钟提醒",),
            ),
            ("专注模式，显示下一场会议名称和时间", ("下一场会议名称", "下一场会议开始时间"), ()),
            (
                "当下日程，显示今日日程和会议跳转入口",
                ("今日日程名称", "今日日程开始时间"),
                ("查看日程",),
            ),
            ("防沉迷，显示本周APP使用时长", ("本周范围", "APP使用时长"), ()),
            ("清理无忧，显示剩余空间和占用占比", ("剩余空间", "占用占比"), ()),
        )
        genui = "\n".join(
            (
                '["root","Column",{"width":"matchParent","height":140,'
                '"padding":12,"borderRadius":22,"clip":true,'
                '"backgroundColor":"#FFFFFFFF"},["title"]]',
                '["title","Text",{"width":116,"height":20,'
                '"content":"测试卡片","fontSize":14,"fontWeight":700,'
                '"fontColor":"#E5000000","maxLines":1}]',
            )
        )

        for user_query, missing_content, missing_actions in cases:
            with self.subTest(user_query=user_query):
                report = validate_compact_dsl(
                    genui,
                    {
                        "suggestSize": "2x4",
                        "dataBindings": [
                            {
                                "capabilityId": "test.capability",
                                "writeResultTo": "/data",
                            }
                        ],
                    },
                    task_spec={"userQuery": user_query},
                )
                for name in missing_content:
                    self.assertTrue(
                        any(
                            f'userQuery content "{name}"' in error
                            for error in report.errors
                        )
                    )
                for name in missing_actions:
                    self.assertTrue(
                        any(
                            f'userQuery action "{name}"' in error
                            for error in report.errors
                        )
                    )

    def test_visible_dynamic_preview_satisfies_sleep_semantics(self) -> None:
        genui = "\n".join(
            (
                '["root","Column",{"width":"matchParent","height":140,'
                '"padding":12,"borderRadius":22,"clip":true,'
                '"backgroundColor":"#FF202224"},["status","duration","ratio"]]',
                '["status","Text",{"content":{"path":"/data/sleep/items/0/title"},'
                '"fontSize":14}]',
                '["/data/sleep/items/0/title","\u6df1\u5ea6\u7761\u7720"]',
                '["duration","Text",{"content":"\u7761\u7720\u65f6\u957f 7\u5c0f\u65f630\u5206",'
                '"fontSize":14}]',
                '["ratio","Text",{"content":"\u5360\u6bd4 68%","fontSize":14}]',
            )
        )
        task_spec = {
            "userQuery": "\u521b\u5efa\u4e00\u4e2a\u7761\u7720\u5361\u7247\uff0c"
            "\u5c55\u793a\u7761\u7720\u72b6\u6001\u3001"
            "\u7761\u7720\u65f6\u957f\u5360\u6bd4\uff0c\u652f\u6301\u8bbe\u7f6e\u95f9\u949f\u63d0\u9192",
            "eventCandidates": [],
        }

        report = validate_compact_dsl(
            genui,
            {"suggestSize": "2x4", "dataBindings": []},
            task_spec=task_spec,
        )

        self.assertFalse(any("userQuery content" in item for item in report.errors))

    def test_unavailable_dynamic_binding_is_not_a_hard_requirement(self) -> None:
        genui = "\n".join(
            (
                '["root","Column",{"width":"matchParent","height":140,'
                '"padding":12,"borderRadius":18,"clip":true,'
                '"backgroundColor":"#FFFFFFFF"},["title"]]',
                '["title","Text",{"content":"青浦天气","fontSize":14,'
                '"fontWeight":700,"fontColor":"#E5000000","maxLines":1}]',
            )
        )

        report = validate_compact_dsl(
            genui,
            {"suggestSize": "2x2", "dataBindings": []},
            task_spec={"userQuery": "青浦天气桌卡"},
        )

        self.assertFalse(
            any("userQuery content" in error for error in report.errors)
        )

    def test_compact_prompt_context_omits_duplicate_metadata(self) -> None:
        task_spec = {
            "userQuery": "青浦天气桌卡",
            "size": "2x2",
            "title": "青浦天气",
            "description": "实时天气与预报",
            "eventCandidates": [
                {
                    "id": "event.open.weather",
                    "call": "clickToDeeplink",
                    "args": {"uri": "weather://detail"},
                }
            ],
            "dataModel": {"value": {"data": {}}},
            "assetCandidates": [
                {
                    "id": "asset.sun",
                    "src": "resources/base/media/sun.svg",
                    "description": "天气太阳图标",
                }
            ],
        }
        generation_context = build_compact_generation_context(task_spec)

        self.assertNotIn("userQuery", generation_context["task"])
        self.assertNotIn("dataModel", generation_context["task"])
        self.assertNotIn("description", generation_context["task"])
        self.assertEqual(
            generation_context["task"]["requiredContent"],
            ["天气状况", "温度", "湿度"],
        )
        forecast_context = build_compact_generation_context(
            task_spec | {"userQuery": "青浦天气预报桌卡"}
        )
        self.assertEqual(
            forecast_context["task"]["requiredContent"],
            ["天气状况", "温度", "湿度", "天气预报"],
        )
        self.assertNotIn("id", generation_context["task"]["events"][0])
        self.assertNotIn("id", generation_context["task"]["assets"][0])
        self.assertNotIn("protocolProfile", generation_context)
        self.assertNotIn("degradation", generation_context)
        degraded_context = build_compact_generation_context(task_spec, "removed")
        self.assertEqual(degraded_context["degradation"], "removed")

        cardspec = {
            "title": "青浦天气",
            "description": "实时天气与预报",
            "suggestSize": "2x2",
            "dataBindings": [
                {
                    "capabilityId": "ViewWeather",
                    "writeResultTo": "/data/weather",
                    "arguments": {"districtName": "青浦区", "forecastDays": 3},
                    "updateModel": {},
                }
            ],
        }
        output_schema = {
            "type": "object",
            "properties": {
                "current": {
                        "type": "object",
                        "properties": {
                            "temperatureText": {
                                "type": "string",
                                "description": "当前温度文本",
                            }
                        },
                }
            },
        }
        binding_context = build_compact_binding_context(
            cardspec,
            [{"id": "ViewWeather", "outputSchema": output_schema}],
        )

        self.assertEqual(
            binding_context,
            {
                "bindings": [
                    {
                        "id": "ViewWeather",
                        "root": "/data/weather",
                        "args": {"districtName": "青浦区", "forecastDays": 3},
                        "fields": [
                            ["/current/temperatureText", "string", "当前温度文本"]
                        ],
                    }
                ]
            },
        )
        serialized_context = json.dumps(binding_context, ensure_ascii=False)
        self.assertNotIn("suggestSize", serialized_context)
        self.assertNotIn("updateModel", serialized_context)
        self.assertNotIn("properties", serialized_context)
        self.assertNotIn("schemas", serialized_context)
        self.assertIsNone(build_compact_binding_context(cardspec | {"dataBindings": []}, []))

    def test_compact_binding_context_flattens_array_paths(self) -> None:
        cardspec = {
            "dataBindings": [
                {
                    "capabilityId": "items.search",
                    "writeResultTo": "/data/results",
                }
            ]
        }
        capabilities = [
            {
                "id": "items.search",
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {
                                        "type": "string",
                                        "description": (
                                            "用于验证描述会被限制到固定长度的测试文本字段，"
                                            "并且不会把完整冗长说明发送给模型"
                                        ),
                                    }
                                },
                            },
                        }
                    },
                },
            }
        ]

        context = build_compact_binding_context(cardspec, capabilities)
        field = context["bindings"][0]["fields"][0]

        self.assertEqual(field[:2], ["/items/0/title", "string"])
        self.assertEqual(len(field[2]), 32)

    def test_compact_weather_example_survives_binding_pipeline(self) -> None:
        example_blocks = re.findall(
            r"```text\n(.*?)\n```",
            self.documents["system-prompt.md"],
            re.DOTALL,
        )
        source = example_blocks[-1]
        cardspec = {
            "suggestSize": "2x2",
            "dataBindings": [
                {
                    "capabilityId": "ViewWeather",
                    "writeResultTo": "/data/weather",
                    "arguments": {},
                    "updateModel": {},
                }
            ],
        }
        capabilities = [
            {
                "id": "ViewWeather",
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "current": {
                            "type": "object",
                            "properties": {
                                "condition": {"type": "string"},
                                "temperatureText": {"type": "string"},
                                "humidityPercent": {"type": "number"},
                            },
                        }
                    },
                },
            }
        ]
        event_candidates = [
            {
                "call": "clickToDeeplink",
                "args": {
                    "uri": "hww://www.huawei.com/totemweather?enterType=share&cityCode="
                },
            }
        ]

        normalized = apply_compact_dsl_data_bindings(
            source,
            cardspec,
            capabilities,
            event_candidates,
        )
        report = validate_compact_dsl(normalized, cardspec)
        rows = [json.loads(line) for line in normalized.splitlines()]
        component_rows = [row for row in rows if len(row) >= 3]
        components_by_id = {row[0]: row for row in component_rows}

        self.assertEqual(len(component_rows), 12)
        self.assertNotIn("tempLabel", components_by_id)
        self.assertNotIn("humidityLabel", components_by_id)
        self.assertEqual(
            components_by_id["drop"][2]["src"],
            "resources/base/media/drop_1.svg",
        )
        self.assertNotIn("humidityValue_value", components_by_id)
        self.assertIs(components_by_id["action"][2]["enabled"], True)
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])

    def test_weather_mock_passes_binding_and_layout_validation(self) -> None:
        cardspec = {
            "title": "Weather",
            "description": "Current weather",
            "suggestSize": "2x2",
            "dataBindings": [
                {
                    "capabilityId": "ViewWeather",
                    "writeResultTo": "/data/weather",
                    "arguments": {},
                    "updateModel": {},
                }
            ],
        }
        capabilities = [
            {
                "id": "ViewWeather",
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "current": {
                            "type": "object",
                            "properties": {
                                "temperatureText": {"type": "string"},
                                "condition": {"type": "string"},
                                "humidityPercent": {"type": "number"},
                            },
                        }
                    },
                },
            }
        ]
        events = [
            {
                "call": "clickToDeeplink",
                "args": {
                    "uri": "hww://www.huawei.com/totemweather?enterType=share&cityCode="
                },
            }
        ]
        source = (self.root / "custom" / "mock.compact-dsl.dat").read_text(
            encoding="utf-8"
        )

        normalized = apply_compact_dsl_data_bindings(
            source,
            cardspec,
            capabilities,
            events,
        )
        report = validate_compact_dsl(
            normalized,
            cardspec,
            list(COMPONENT_WHITELIST),
        )

        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])

    def test_rain_taxi_bindings_receive_non_empty_weather_previews(self) -> None:
        cardspec = {
            "suggestSize": "2x2",
            "dataBindings": [
                {
                    "capabilityId": "ViewWeather",
                    "writeResultTo": "/data/weather",
                    "updateModel": {},
                }
            ],
        }
        capabilities = [
            {
                "id": "ViewWeather",
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "current": {
                            "type": "object",
                            "properties": {
                                "condition": {"type": "string"},
                                "temperatureText": {"type": "string"},
                            },
                        },
                        "daily": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "rainProbabilityPercent": {"type": "string"}
                                },
                            },
                        },
                    },
                },
            }
        ]
        source = "\n".join(
            [
                '["root","Column",{"width":"matchParent","height":140,"padding":12,'
                '"borderRadius":18,"clip":true,"space":4},'
                '["condition_text","main_row","support_text"]]',
                '["condition_text","Text",{"width":116,"height":20,'
                '"content":{"path":"/data/weather/current/condition"},"fontSize":12}]',
                '["main_row","Row",{"width":116,"height":52,"space":4},'
                '["rain_icon","primary_value"]]',
                '["rain_icon","Image",{"width":40,"height":40,"src":"rain.svg"}]',
                '["primary_value","Text",{"width":72,"height":40,'
                '"content":{"path":"/data/weather/daily/0/rainProbabilityPercent"},'
                '"fontSize":32}]',
                '["support_text","Text",{"width":116,"height":32,'
                '"content":{"path":"/data/weather/current/temperatureText"},"fontSize":12}]',
            ]
        )

        normalized = apply_compact_dsl_data_bindings(source, cardspec, capabilities)
        rows = [json.loads(line) for line in normalized.splitlines()]
        data_rows = {row[0]: row[1] for row in rows if len(row) == 2}
        report = validate_compact_dsl(normalized, cardspec)

        self.assertEqual(data_rows["/data/weather/current/condition"], "小雨")
        self.assertEqual(data_rows["/data/weather/daily/0/rainProbabilityPercent"], "72%")
        self.assertEqual(data_rows["/data/weather/current/temperatureText"], "26°C")
        self.assertEqual(report.errors, [])

    def test_weather_literals_and_relative_day_paths_are_repaired(self) -> None:
        cardspec = {
            "suggestSize": "2x2",
            "dataBindings": [
                {
                    "capabilityId": "ViewWeather",
                    "writeResultTo": "/data/weather",
                    "arguments": {},
                    "updateModel": {},
                }
            ],
        }
        capabilities = [
            {
                "id": "ViewWeather",
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "current": {
                            "type": "object",
                            "properties": {
                                "feelsLikeC": {"type": "number"},
                            },
                        },
                        "daily": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "weekday": {"type": "string"},
                                    "temperatureRangeText": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            }
        ]
        source = "\n".join(
            [
                '["root","Column",{"width":"matchParent","height":140,'
                '"padding":12,"borderRadius":18,"clip":true,"space":6},'
                '["feels_text","forecast_chip"]]',
                '["feels_text","Text",{"content":"体感 31°","fontSize":12}]',
                '["forecast_chip","Column",{"space":2},'
                '["forecast_day","forecast_temp"]]',
                '["forecast_day","Text",{"content":'
                '{"path":"/data/weather/daily/0/weekday"},"fontSize":12}]',
                '["/data/weather/daily/0/weekday","明日"]',
                '["forecast_temp","Text",{"content":'
                '{"path":"/data/weather/daily/1/temperatureRangeText"},'
                '"fontSize":12}]',
                '["/data/weather/daily/1/temperatureRangeText","24° / 32°"]',
            ]
        )

        normalized = apply_compact_dsl_data_bindings(
            source,
            cardspec,
            capabilities,
        )
        rows = [json.loads(line) for line in normalized.splitlines()]
        rows_by_id = {row[0]: row for row in rows if len(row) >= 3}
        data_values = {row[0]: row[1] for row in rows if len(row) == 2}

        self.assertEqual(rows_by_id["feels_text"][1], "Row")
        self.assertEqual(
            rows_by_id["feels_text_value"][2]["content"],
            {"path": "/data/weather/current/feelsLikeC"},
        )
        self.assertEqual(data_values["/data/weather/current/feelsLikeC"], 31)
        self.assertEqual(
            rows_by_id["forecast_day"][2]["content"],
            {"path": "/data/weather/daily/1/weekday"},
        )
        self.assertNotIn("/data/weather/daily/0/weekday", data_values)
        self.assertEqual(data_values["/data/weather/daily/1/weekday"], "明日")

    def test_existing_weather_decorations_are_not_expanded_twice(self) -> None:
        cardspec = {
            "suggestSize": "2x2",
            "dataBindings": [
                {
                    "capabilityId": "ViewWeather",
                    "writeResultTo": "/data/weather",
                    "arguments": {},
                    "updateModel": {},
                }
            ],
        }
        capabilities = [
            {
                "id": "ViewWeather",
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "current": {
                            "type": "object",
                            "properties": {
                                "feelsLikeC": {"type": "number"},
                                "humidityPercent": {"type": "number"},
                            },
                        }
                    },
                },
            }
        ]
        source = "\n".join(
            [
                '["root","Column",{"width":"matchParent"},["feels_row","humidity_row"]]',
                '["feels_row","Row",{"space":0},'
                '["feels_prefix","feels_value","feels_suffix"]]',
                '["feels_prefix","Text",{"content":"体感 "}]',
                '["feels_value","Text",{"content":'
                '{"path":"/data/weather/current/feelsLikeC"}}]',
                '["/data/weather/current/feelsLikeC",31]',
                '["feels_suffix","Text",{"content":"°"}]',
                '["humidity_row","Row",{"space":0},'
                '["humidity_value","humidity_suffix"]]',
                '["humidity_value","Text",{"content":'
                '{"path":"/data/weather/current/humidityPercent"}}]',
                '["/data/weather/current/humidityPercent",68]',
                '["humidity_suffix","Text",{"content":"%"}]',
            ]
        )

        normalized = apply_compact_dsl_data_bindings(source, cardspec, capabilities)
        rows = [json.loads(line) for line in normalized.splitlines()]
        rows_by_id = {row[0]: row for row in rows if len(row) >= 3}
        feels_data_rows = [
            row
            for row in rows
            if len(row) == 2 and row[0] == "/data/weather/current/feelsLikeC"
        ]
        humidity_data_rows = [
            row
            for row in rows
            if len(row) == 2 and row[0] == "/data/weather/current/humidityPercent"
        ]

        self.assertEqual(rows_by_id["feels_value"][1], "Text")
        self.assertEqual(rows_by_id["humidity_value"][1], "Text")
        self.assertEqual(rows_by_id["feels_prefix"][2]["content"], "体感 ")
        self.assertEqual(rows_by_id["feels_suffix"][2]["content"], "°")
        self.assertEqual(rows_by_id["humidity_suffix"][2]["content"], "%")
        self.assertNotIn("feels_value_value", rows_by_id)
        self.assertNotIn("humidity_value_value", rows_by_id)
        self.assertEqual(feels_data_rows, [["/data/weather/current/feelsLikeC", 31]])
        self.assertEqual(humidity_data_rows, [["/data/weather/current/humidityPercent", 68]])

    def test_preflight_repairs_missing_closers_without_model(self) -> None:
        source = "\n".join(
            [
                '["root","Stack",'
                '{"width":"matchParent","height":140,"padding":12},["title"]',
                '["title","Text",'
                '{"width":100,"height":20,"content":"Weather","fontSize":14}',
            ]
        )

        result = preflight_compact_dsl(
            source,
            {"suggestSize": "2x2", "dataBindings": []},
            [],
            [],
        )
        rows = [json.loads(line) for line in result.genui.splitlines()]
        report = validate_compact_dsl(
            result.genui,
            {"suggestSize": "2x2", "dataBindings": []},
        )

        self.assertTrue(result.passed)
        self.assertIn("JSON_SYNTAX_REPAIRED", result.repairs)
        self.assertEqual([row[0] for row in rows], ["root", "title"])
        self.assertEqual(report.errors, [])

    def test_preflight_splits_concatenated_component_rows(self) -> None:
        source = (
            '["root","Stack",'
            '{"width":"matchParent","height":140,"padding":12},["title"]]'
            '["title","Text",'
            '{"width":100,"height":20,"content":"Weather","fontSize":14}]'
        )

        result = preflight_compact_dsl(
            source,
            {"suggestSize": "2x2", "dataBindings": []},
            [],
            [],
        )
        rows = [json.loads(line) for line in result.genui.splitlines()]
        report = validate_compact_dsl(
            result.genui,
            {"suggestSize": "2x2", "dataBindings": []},
        )

        self.assertTrue(result.passed)
        self.assertIn("CONCATENATED_ROWS_SPLIT", result.repairs)
        self.assertEqual([row[0] for row in rows], ["root", "title"])
        self.assertEqual(report.errors, [])

    def test_preflight_adds_missing_required_forecast_without_model_retry(self) -> None:
        example_blocks = re.findall(
            r"```text\n(.*?)\n```",
            self.documents["system-prompt.md"],
            re.DOTALL,
        )
        source = example_blocks[-1]
        cardspec = {
            "suggestSize": "2x2",
            "dataBindings": [
                {
                    "capabilityId": "ViewWeather",
                    "writeResultTo": "/data/weather",
                    "arguments": {"forecastDays": 3},
                    "updateModel": {},
                }
            ],
        }
        capabilities = [
            {
                "id": "ViewWeather",
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "current": {
                            "type": "object",
                            "properties": {
                                "condition": {"type": "string"},
                                "temperatureText": {"type": "string"},
                                "humidityPercent": {"type": "number"},
                            },
                        },
                        "daily": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "weekday": {"type": "string"},
                                    "temperatureRangeText": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            }
        ]
        event_candidates = [
            {
                "id": "event.open.weather",
                "call": "clickToDeeplink",
                "args": {
                    "uri": "hww://www.huawei.com/totemweather?enterType=share&cityCode="
                },
            }
        ]
        task_spec = {
            "userQuery": "青浦天气预报桌卡",
            "title": "青浦天气",
            "description": "实时天气与预报",
        }

        result = preflight_compact_dsl(
            source,
            cardspec,
            capabilities,
            event_candidates,
            task_spec,
        )
        rows = [json.loads(line) for line in result.genui.splitlines()]
        component_rows = [row for row in rows if len(row) >= 3]
        target_content = {
            "path": "/data/weather/daily/0/temperatureRangeText"
        }

        forecast_components = []

        for row in component_rows:
            content = row[2].get("content")

            if content == target_content:
                forecast_components.append(row)
        report = validate_compact_dsl(
            result.genui,
            cardspec,
            task_spec=task_spec,
        )

        self.assertTrue(result.passed)
        self.assertIn("REQUIRED_CONTENT_REPAIRED", result.repairs)
        self.assertEqual(len(forecast_components), 1)
        self.assertEqual(report.errors, [])

    def test_preflight_reuses_optional_binding_when_required_row_is_full(self) -> None:
        example_blocks = re.findall(
            r"```text\n(.*?)\n```",
            self.documents["system-prompt.md"],
            re.DOTALL,
        )
        source_rows = [json.loads(line) for line in example_blocks[-1].splitlines()]
        for row in source_rows:
            if row[0] == "humidity":
                row[3].append("humidity_meta")
        action_index = next(
            index
            for index, row in enumerate(source_rows)
            if row[0] == "action"
        )
        source_rows[action_index:action_index] = [
            [
                "humidity_meta",
                "Text",
                {
                    "width": 48,
                    "height": 16,
                    "content": {"path": "/data/weather/daily/0/weekday"},
                    "fontSize": 12,
                },
            ],
            ["/data/weather/daily/0/weekday", "星期日"],
        ]
        source = "\n".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":"))
            for row in source_rows
        )
        cardspec = {
            "suggestSize": "2x2",
            "dataBindings": [
                {
                    "capabilityId": "ViewWeather",
                    "writeResultTo": "/data/weather",
                    "arguments": {"forecastDays": 3},
                    "updateModel": {},
                }
            ],
        }
        capabilities = [
            {
                "id": "ViewWeather",
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "current": {
                            "type": "object",
                            "properties": {
                                "condition": {"type": "string"},
                                "temperatureText": {"type": "string"},
                                "humidityPercent": {"type": "number"},
                            },
                        },
                        "daily": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "weekday": {"type": "string"},
                                    "temperatureRangeText": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            }
        ]
        task_spec = {
            "userQuery": "青浦天气预报桌卡",
            "title": "青浦天气",
            "description": "实时天气与预报",
        }
        event_candidates = [
            {
                "id": "event.open.weather",
                "call": "clickToDeeplink",
                "args": {
                    "uri": "hww://www.huawei.com/totemweather?enterType=share&cityCode="
                },
            }
        ]

        result = preflight_compact_dsl(
            source,
            cardspec,
            capabilities,
            event_candidates,
            task_spec,
        )
        rows = [json.loads(line) for line in result.genui.splitlines()]
        humidity_meta = next(row for row in rows if row[0] == "humidity_meta")

        self.assertIn("REQUIRED_CONTENT_REPAIRED", result.repairs)
        self.assertEqual(
            humidity_meta[2]["content"],
            {"path": "/data/weather/daily/0/temperatureRangeText"},
        )

    def test_preflight_and_validator_report_deterministic_categories(self) -> None:
        cardspec = {"suggestSize": "2x2", "dataBindings": []}
        preflight = preflight_compact_dsl(
            '["root","Column",{"content":"unterminated}',
            cardspec,
            [],
            [],
        )
        syntax_report = validate_compact_dsl("not-json", cardspec)
        structure_report = validate_compact_dsl(
            '["item","Text",{"content":"Text","fontSize":14}]',
            cardspec,
        )
        layout_source = "\n".join(
            [
                '["root","Column",'
                '{"width":"matchParent","height":140,"padding":12,'
                '"borderRadius":18,"clip":true,"backgroundColor":"#FFFFFFFF"},'
                '["text"]]',
                '["text","Text",'
                '{"width":100,"height":20,"content":"Text","fontSize":14}]',
            ]
        )
        layout_report = validate_compact_dsl(layout_source, cardspec)
        binding_source = "\n".join(
            [
                '["root","Stack",'
                '{"width":"matchParent","height":140,"padding":12,'
                '"borderRadius":18,"clip":true,"backgroundColor":"#FFFFFFFF"},'
                '["text"]]',
                '["text","Text",'
                '{"width":100,"height":20,"content":{"path":"/data/missing"},'
                '"fontSize":14}]',
            ]
        )
        binding_report = validate_compact_dsl(binding_source, cardspec)

        self.assertFalse(preflight.passed)
        self.assertEqual(preflight.diagnostics[0].category, "SYNTAX")
        self.assertIn("SYNTAX", self._error_categories(syntax_report))
        self.assertIn("STRUCTURE", self._error_categories(structure_report))
        self.assertIn("LAYOUT", self._error_categories(layout_report))
        self.assertIn("BINDING", self._error_categories(binding_report))

    @staticmethod
    def _error_categories(report: object) -> set[str]:
        diagnostics = getattr(report, "diagnostics", ())
        return {
            item.category
            for item in diagnostics
            if item.severity == "error"
        }

    def test_malformed_action_tail_reports_button_contract(self) -> None:
        source = "\n".join(
            [
                '["root","Column",{"width":"matchParent","height":140,'
                '"padding":12},["footer"]]',
                '["footer","Row",{"width":116,"height":32},'
                '["bluetooth_button"]]',
                '["bluetooth_button","Row",{"width":116,"height":32},'
                '["bluetooth_text"]]',
                '["bluetooth_text","Text",{"width":100,'
                '"content":"蓝牙设置"}],"action":{"functionCall":'
                '{"call":"clickToDeeplink","args":{"uri":"bluetooth_entry"}}}}',
            ]
        )
        event_candidates = [
            {
                "call": "clickToDeeplink",
                "args": {"uri": "bluetooth_entry"},
            }
        ]

        with self.assertRaisesRegex(ValueError, "available eventCandidate in a Button"):
            apply_compact_dsl_data_bindings(
                source,
                {"suggestSize": "2x2", "dataBindings": []},
                [],
                event_candidates,
            )

    def test_button_like_action_row_uses_single_static_event_candidate(self) -> None:
        source = "\n".join(
            [
                '["root","Stack",{"width":"matchParent","height":140,'
                '"padding":12},["action_button"]]',
                '["action_button","Row",{"width":276,"height":32,'
                '"padding":{"top":0,"right":12,"bottom":0,"left":12},'
                '"borderRadius":16,"backgroundColor":"#33FFFFFF",'
                '"alignItems":"center","space":6},["action_icon","action_label"]]',
                '["action_icon","Image",{"width":18,"height":18,'
                '"src":"resources/base/media/bell_slash_fill.svg"}]',
                '["action_label","Text",{"width":228,"height":18,'
                '"content":"开启勿扰","fontSize":14,"fontWeight":600,'
                '"fontColor":"#FFFFFFFF","maxLines":1}]',
            ]
        )
        event_candidates = [
            {
                "call": "clickToDeeplink",
                "args": {
                    "abilityName": "com.huawei.hmos.settings.MainAbility",
                    "bundleName": "com.huawei.hmos.settings",
                    "uri": "intelligent_scene_entry",
                },
            }
        ]
        cardspec = {"suggestSize": "2x4", "dataBindings": []}

        normalized = apply_compact_dsl_data_bindings(
            source,
            cardspec,
            [],
            event_candidates,
        )
        rows = [json.loads(line) for line in normalized.splitlines()]
        rows_by_id = {row[0]: row for row in rows if len(row) >= 3}
        report = validate_compact_dsl(normalized, cardspec)

        action = rows_by_id["action_button"]
        self.assertEqual(action[1], "Button")
        self.assertEqual(action[2]["label"], "开启勿扰")
        self.assertEqual(
            action[2]["action"]["functionCall"],
            event_candidates[0],
        )
        self.assertNotIn("action_icon", rows_by_id)
        self.assertNotIn("action_label", rows_by_id)
        self.assertEqual(report.errors, [])

    def test_earphone_action_rows_with_embedded_calls_become_buttons(self) -> None:
        music_args = {
            "abilityName": "",
            "bundleName": "",
            "uri": "hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4",
        }
        bluetooth_args = {
            "abilityName": "com.huawei.hmos.settings.MainAbility",
            "bundleName": "com.huawei.hmos.settings",
            "uri": "bluetooth_entry",
        }
        music_args_json = json.dumps(music_args, ensure_ascii=False, separators=(",", ":"))
        bluetooth_args_json = json.dumps(
            bluetooth_args,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        source = "\n".join(
            [
                '["root","Column",{"width":"matchParent","height":140},["actions"]]',
                '["actions","Row",{"width":276,"height":32,"space":8},'
                '["play_button","settings_button"]]',
                (
                    '["play_button","Row",{"width":134,"height":32,"padding":[0,8,0,8],'
                    '"borderRadius":16,"backgroundColor":"#FFFFFFFF","action":'
                    '{"functionCall":{"call":"clickToDeeplink","args":'
                    + music_args_json
                    + '}}],"play_icon","play_label"]]'
                ),
                '["play_icon","Image",{"width":20,"height":20,"src":"play.svg"}]',
                '["play_label","Text",{"content":"开始播放","fontSize":12}]',
                (
                    '["settings_button","Row",{"width":134,"height":32,"padding":[0,8,0,8],'
                    '"borderRadius":16,"backgroundColor":"#33FFFFFF","action":'
                    '{"functionCall":{"call":"clickToDeeplink","args":'
                    + bluetooth_args_json
                    + '}}],"settings_icon","settings_label"]]'
                ),
                '["settings_icon","Image",{"width":20,"height":20,"src":"settings.svg"}]',
                '["settings_label","Text",{"content":"耳机设置","fontSize":12}]',
            ]
        )
        event_candidates = [
            {"call": "clickToDeeplink", "args": music_args},
            {"call": "clickToDeeplink", "args": bluetooth_args},
        ]

        normalized = apply_compact_dsl_data_bindings(
            source,
            {"suggestSize": "2x4", "dataBindings": []},
            [],
            event_candidates,
        )
        rows = [json.loads(line) for line in normalized.splitlines()]
        rows_by_id = {row[0]: row for row in rows if len(row) >= 3}

        self.assertEqual(rows_by_id["play_button"][1], "Button")
        self.assertEqual(rows_by_id["settings_button"][1], "Button")
        self.assertEqual(rows_by_id["play_button"][2]["label"], "开始播放")
        self.assertEqual(rows_by_id["settings_button"][2]["label"], "耳机设置")
        self.assertEqual(
            rows_by_id["play_button"][2]["action"]["functionCall"]["args"],
            music_args,
        )
        self.assertEqual(
            rows_by_id["settings_button"][2]["action"]["functionCall"]["args"],
            bluetooth_args,
        )
        self.assertNotIn("play_icon", rows_by_id)
        self.assertNotIn("settings_icon", rows_by_id)

    def test_earphone_concatenated_components_recover_complete_tree(self) -> None:
        music_args = {
            "abilityName": "",
            "bundleName": "",
            "uri": "hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4",
        }
        bluetooth_args = {
            "abilityName": "com.huawei.hmos.settings.MainAbility",
            "bundleName": "com.huawei.hmos.settings",
            "uri": "bluetooth_entry",
        }
        music_args_json = json.dumps(music_args, ensure_ascii=False, separators=(",", ":"))
        bluetooth_args_json = json.dumps(
            bluetooth_args,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        source = "\n".join(
            [
                '["root","Column",{"width":"matchParent","height":140,"padding":12,'
                '"space":6},["top_row","divider","bottom_row"]]',
                '["top_row","Row",{"width":276,"height":68,"space":8},'
                '["hero_panel","info_panel"]]',
                '["hero_panel","Column",{"width":104,"height":68,"padding":6,"space":4},'
                '["icon","battery_value","battery_hint"]]',
                '["icon","Image",{"width":28,"height":28,"src":"earphone.svg"}]',
                '["battery_value","Text",{"width":92,"height":22,"content":"78%",'
                '"fontSize":20}],"battery_hint","Text",{"width":92,"height":14,'
                '"content":"电量充足","fontSize":12}],"info_panel","Column",'
                '{"width":164,"height":68,"space":4},["title","recommend","music_row"]]',
                '["title","Text",{"width":164,"height":18,"content":"耳机播控",'
                '"fontSize":14}],"recommend","Text",{"width":164,"height":18,'
                '"content":"每日推荐","fontSize":12}],"music_row","Row",'
                '{"width":164,"height":24,"space":6},["music_icon","music_state"]]',
                '["music_icon","Image",{"width":20,"height":20,"src":"music.svg"}]',
                '["music_state","Text",{"width":138,"height":18,"content":"准备播放",'
                '"fontSize":12}],"divider","Divider",{"width":276,"height":2},'
                '"bottom_row","Row",{"width":276,"height":38,"space":8},'
                '["play_button","bluetooth_button"]]',
                (
                    '["play_button","Button",{"width":164,"height":32,"label":"播放音乐",'
                    '"action":{"functionCall":{"call":"clickToDeeplink","args":'
                    + music_args_json
                    + '}}}],"bluetooth_button","Button",{"width":104,"height":32,'
                    '"label":"蓝牙设置","action":{"functionCall":'
                    '{"call":"clickToDeeplink","args":'
                    + bluetooth_args_json
                    + '}}}]'
                ),
            ]
        )
        cardspec = {"suggestSize": "2x4", "dataBindings": []}
        event_candidates = [
            {"call": "clickToDeeplink", "args": music_args},
            {"call": "clickToDeeplink", "args": bluetooth_args},
        ]

        normalized = apply_compact_dsl_data_bindings(
            source,
            cardspec,
            [],
            event_candidates,
        )
        rows = [json.loads(line) for line in normalized.splitlines()]
        rows_by_id = {row[0]: row for row in rows if len(row) >= 3}
        report = validate_compact_dsl(normalized, cardspec)

        self.assertEqual(rows_by_id["root"][3], ["top_row", "divider", "bottom_row"])
        self.assertEqual(rows_by_id["info_panel"][3], ["title", "recommend", "music_row"])
        self.assertEqual(rows_by_id["bottom_row"][3], ["play_button", "bluetooth_button"])
        self.assertEqual(rows_by_id["play_button"][1], "Button")
        self.assertEqual(rows_by_id["bluetooth_button"][1], "Button")
        self.assertEqual(rows_by_id["hero_panel"][2]["space"], 2)
        self.assertEqual(report.errors, [])

    def test_two_action_earphone_card_stays_within_compact_budget(self) -> None:
        music_args = {
            "abilityName": "",
            "bundleName": "",
            "uri": "hwmusic://com.huawei.hmsapp.music/showMusicList?code=a001&type=4",
        }
        bluetooth_args = {
            "abilityName": "com.huawei.hmos.settings.MainAbility",
            "bundleName": "com.huawei.hmos.settings",
            "uri": "bluetooth_entry",
        }
        source_rows = [
            [
                "root",
                "Column",
                {
                    "width": "matchParent",
                    "height": 140,
                    "padding": 12,
                    "borderRadius": 22,
                    "clip": True,
                    "space": 4,
                    "justifyContent": "start",
                    "linearGradient": {
                        "direction": "RightBottom",
                        "colors": [["#FFFFFFFF", 0], ["#D1BC64", 1]],
                    },
                },
                ["header", "content", "actions"],
            ],
            [
                "header",
                "Row",
                {
                    "width": 276,
                    "height": 18,
                    "space": 4,
                    "justifyContent": "spaceBetween",
                },
                ["title", "status"],
            ],
            [
                "title",
                "Text",
                {
                    "width": 180,
                    "height": 18,
                    "content": "耳机播控",
                    "fontSize": 14,
                    "fontWeight": 700,
                    "maxLines": 1,
                },
            ],
            [
                "status",
                "Text",
                {
                    "width": 92,
                    "height": 18,
                    "content": "已连接",
                    "fontSize": 12,
                    "fontWeight": 600,
                    "maxLines": 1,
                    "textAlign": "end",
                },
            ],
            [
                "content",
                "Row",
                {"width": 276, "height": 52, "space": 6, "alignItems": "center"},
                ["earphone_icon", "battery_col", "music_icon", "music_col"],
            ],
            [
                "earphone_icon",
                "Image",
                {
                    "width": 32,
                    "height": 32,
                    "src": "resources/base/media/earphone_case_16644.svg",
                    "objectFit": "contain",
                },
            ],
            [
                "battery_col",
                "Column",
                {"width": 72, "height": 50, "space": 2},
                ["battery_value", "battery_bar", "battery_status"],
            ],
            [
                "battery_value",
                "Text",
                {
                    "width": 72,
                    "height": 24,
                    "content": "78%",
                    "fontSize": 20,
                    "fontWeight": 700,
                    "maxLines": 1,
                },
            ],
            [
                "battery_bar",
                "Progress",
                {
                    "width": 72,
                    "height": 8,
                    "value": 78,
                    "total": 100,
                    "type": "linear",
                    "color": "#61CFBE",
                },
            ],
            [
                "battery_status",
                "Text",
                {
                    "width": 72,
                    "height": 14,
                    "content": "耳机电量",
                    "fontSize": 12,
                    "maxLines": 1,
                },
            ],
            [
                "music_icon",
                "Image",
                {
                    "width": 24,
                    "height": 24,
                    "src": "resources/base/media/music_fill.svg",
                    "objectFit": "contain",
                },
            ],
            [
                "music_col",
                "Column",
                {"width": 130, "height": 50, "space": 4},
                ["music_title", "recommend_text"],
            ],
            [
                "music_title",
                "Text",
                {
                    "width": 130,
                    "height": 20,
                    "content": "华为音乐",
                    "fontSize": 14,
                    "fontWeight": 700,
                    "maxLines": 1,
                },
            ],
            [
                "recommend_text",
                "Text",
                {
                    "width": 130,
                    "height": 18,
                    "content": "每日推荐已更新",
                    "fontSize": 12,
                    "fontWeight": 500,
                    "maxLines": 1,
                },
            ],
            [
                "actions",
                "Row",
                {"width": 276, "height": 34, "space": 8},
                ["music_button", "bluetooth_button"],
            ],
            [
                "music_button",
                "Button",
                {
                    "width": 134,
                    "height": 34,
                    "label": "打开每日推荐",
                    "enabled": True,
                    "fontSize": 12,
                    "fontWeight": 600,
                    "action": {
                        "functionCall": {
                            "call": "clickToDeeplink",
                            "args": music_args,
                        }
                    },
                },
            ],
            [
                "bluetooth_button",
                "Button",
                {
                    "width": 134,
                    "height": 34,
                    "label": "蓝牙设置",
                    "enabled": True,
                    "fontSize": 12,
                    "fontWeight": 600,
                    "action": {
                        "functionCall": {
                            "call": "clickToDeeplink",
                            "args": bluetooth_args,
                        }
                    },
                },
            ],
        ]
        source = "\n".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":"))
            for row in source_rows
        )
        cardspec = {"suggestSize": "2x4", "dataBindings": []}
        event_candidates = [
            {"call": "clickToDeeplink", "args": music_args},
            {"call": "clickToDeeplink", "args": bluetooth_args},
        ]

        normalized = apply_compact_dsl_data_bindings(
            source,
            cardspec,
            [],
            event_candidates,
        )
        report = validate_compact_dsl(normalized, cardspec)
        rows = [json.loads(line) for line in normalized.splitlines()]
        component_rows = [row for row in rows if len(row) >= 3]

        self.assertLessEqual(len(component_rows), 20)
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])

    def test_extra_compact_components_remain_rejected(self) -> None:
        genui = "\n".join(
            [
                '["root","Column",'
                '{"width":"matchParent","height":140,"padding":12,'
                '"borderRadius":18,"clip":true,"space":0},["grid"]]',
                '["grid","Grid",{},[]]',
            ]
        )

        report = validate_compact_dsl(genui, {"suggestSize": "2x2"})

        self.assertTrue(any("unsupported component Grid" in item for item in report.errors))

    def test_form_progress_binding_and_checkbox_semantics_are_preserved(self) -> None:
        genui = "\n".join(
            [
                '["root","Column",'
                '{"width":"matchParent","height":140,"padding":12,'
                '"borderRadius":18,"clip":true,"space":8,'
                '"backgroundColor":"#FFFFFFFF"},["progress","check"]]',
                '["progress","Progress",'
                '{"value":{"path":"/progress/value"},'
                '"total":{"path":"/progress/total"},"type":"ring"}]',
                '["/progress/value",60]',
                '["/progress/total",100]',
                '["check","Checkbox",{"label":"Enabled","select":false}]',
            ]
        )

        report = validate_compact_dsl(genui, {"suggestSize": "2x2"})

        self.assertEqual(report.errors, [])

    def test_dynamic_text_uses_tool3_scale_overflow_and_fit_rules(self) -> None:
        genui = "\n".join(
            [
                '["root","Stack",'
                '{"width":"matchParent","height":140,"padding":12,'
                '"borderRadius":18,"clip":true},["title"]]',
                '["title","Text",'
                '{"width":30,"content":{"path":"/title"},"fontSize":15,'
                '"maxLines":1,"textOverflow":"ellipsis"}]',
                '["/title","A long title"]',
            ]
        )

        report = validate_compact_dsl(genui, {"suggestSize": "2x2"})

        self.assertTrue(any("outside the approved scale" in item for item in report.errors))
        self.assertTrue(any("textOverflow ellipsis" in item for item in report.errors))
        self.assertTrue(any("estimated width" in item for item in report.errors))

    def test_storage_value_uses_smallest_allowed_fitting_font(self) -> None:
        cardspec = {"suggestSize": "2x2", "dataBindings": []}
        source = "\n".join(
            [
                '["root","Stack",{"width":"matchParent","height":140,"padding":12,'
                '"borderRadius":18,"clip":true,"backgroundColor":"#FFFFFFFF"},'
                '["primary_value"]]',
                '["primary_value","Text",{"width":64,"height":22,'
                '"content":"32.4 GB","fontSize":20,"fontWeight":700,'
                '"fontColor":"#E5000000","maxLines":1}]',
            ]
        )

        normalized = apply_compact_dsl_data_bindings(source, cardspec, [])
        rows = [json.loads(line) for line in normalized.splitlines()]
        primary_value = next(row for row in rows if row[0] == "primary_value")
        report = validate_compact_dsl(normalized, cardspec)

        self.assertEqual(primary_value[2]["fontSize"], 16)
        self.assertEqual(report.errors, [])

    def test_sleep_metric_row_redistributes_width_before_over_shrinking(self) -> None:
        cardspec = {"suggestSize": "2x4", "dataBindings": []}
        source = "\n".join(
            [
                '["root","Stack",{"width":"matchParent","height":140,"padding":12,'
                '"borderRadius":22,"clip":true,"backgroundColor":"#FF202224"},'
                '["metric_value_row"]]',
                '["metric_value_row","Row",{"width":212,"height":24,"space":8},'
                '["primary_value","primary_unit"]]',
                '["primary_value","Text",{"width":72,"height":24,'
                '"content":"7小时32分","fontSize":20,"fontWeight":700,'
                '"fontColor":"#FFFFFFFF","maxLines":1}]',
                '["primary_unit","Text",{"width":132,"height":20,'
                '"content":"目标 8小时","fontSize":12,"fontWeight":500,'
                '"fontColor":"#99FFFFFF","maxLines":1}]',
            ]
        )

        normalized = apply_compact_dsl_data_bindings(source, cardspec, [])
        rows = [json.loads(line) for line in normalized.splitlines()]
        rows_by_id = {row[0]: row for row in rows if len(row) >= 3}
        report = validate_compact_dsl(normalized, cardspec)

        self.assertEqual(rows_by_id["primary_value"][2]["fontSize"], 20)
        self.assertEqual(rows_by_id["primary_value"][2]["width"], 96)
        self.assertEqual(rows_by_id["primary_unit"][2]["width"], 108)
        self.assertEqual(report.errors, [])

    def test_three_item_row_rebalances_width_and_uses_safe_smaller_font(self) -> None:
        cardspec = {"suggestSize": "2x2", "dataBindings": []}
        source = "\n".join(
            [
                '["root","Stack",{"width":"matchParent","height":140,"padding":12,'
                '"borderRadius":18,"clip":true,"backgroundColor":"#FFFFFFFF"},'
                '["forecast_row"]]',
                '["forecast_row","Row",{"width":116,"height":16,"space":4},'
                '["forecast_day","forecast_condition","forecast_temp"]]',
                '["forecast_day","Text",{"width":28,"height":16,'
                '"content":"星期日","fontSize":12,"maxLines":1}]',
                '["forecast_condition","Text",{"width":30,"height":16,'
                '"content":"多云","fontSize":12,"maxLines":1}]',
                '["forecast_temp","Text",{"width":50,"height":16,'
                '"content":"24° / 32°","fontSize":12,"maxLines":1}]',
            ]
        )

        normalized = apply_compact_dsl_data_bindings(source, cardspec, [])
        rows = [json.loads(line) for line in normalized.splitlines()]
        rows_by_id = {row[0]: row for row in rows if len(row) >= 3}
        report = validate_compact_dsl(normalized, cardspec)

        self.assertEqual(rows_by_id["forecast_day"][2]["fontSize"], 10)
        self.assertEqual(rows_by_id["forecast_day"][2]["width"], 30)
        self.assertEqual(rows_by_id["forecast_condition"][2]["width"], 28)
        self.assertEqual(report.errors, [])

    def test_image_button_and_spacing_rules_match_tool3(self) -> None:
        image_genui = "\n".join(
            [
                '["root","Stack",'
                '{"width":"matchParent","height":140,"padding":12,'
                '"borderRadius":18,"clip":true},["image"]]',
                '["image","Image",{"src":"resources/base/media/sun_max.svg",'
                '"objectFit":"cover","filter":"invert(1)"}]',
            ]
        )
        image_report = validate_compact_dsl(image_genui, {"suggestSize": "2x2"})
        self.assertTrue(any("explicit numeric width" in item for item in image_report.errors))
        self.assertTrue(any("Image.filter is unsupported" in item for item in image_report.errors))
        self.assertTrue(any("objectFit contain" in item for item in image_report.warnings))

        button_genui = "\n".join(
            [
                '["root","Stack",'
                '{"width":"matchParent","height":140,"padding":12,'
                '"borderRadius":18,"clip":true},["button"]]',
                '["button","Button",'
                '{"width":30,"height":20,"label":"Confirm","fontSize":14}]',
            ]
        )
        button_report = validate_compact_dsl(button_genui, {"suggestSize": "2x2"})
        self.assertTrue(any("height must be at least 24" in item for item in button_report.errors))
        self.assertTrue(any("may not fit width" in item for item in button_report.errors))

        spacing_genui = "\n".join(
            [
                '["root","Stack",'
                '{"width":"matchParent","height":140,"padding":12,'
                '"borderRadius":18,"clip":true,'
                '"backgroundColor":"#FFFFFFFF"},["text"]]',
                '["text","Text",'
                '{"width":100,"content":"Text","fontSize":14,"margin":3}]',
            ]
        )
        spacing_report = validate_compact_dsl(spacing_genui, {"suggestSize": "2x2"})
        self.assertEqual(spacing_report.errors, [])
        self.assertTrue(
            any("outside the spacing scale" in item for item in spacing_report.warnings)
        )

    def test_column_bottom_gap_rule_matches_tool3(self) -> None:
        genui = "\n".join(
            [
                '["root","Column",'
                '{"width":"matchParent","height":140,"padding":12,'
                '"borderRadius":18,"clip":true,"space":0},["text"]]',
                '["text","Text",'
                '{"width":100,"height":20,"content":"Text","fontSize":14}]',
            ]
        )

        report = validate_compact_dsl(genui, {"suggestSize": "2x2"})

        self.assertTrue(any("bottom gap" in item for item in report.errors))

    def test_small_bottom_gap_overage_is_repaired_before_validation(self) -> None:
        genui = "\n".join(
            [
                '["root","Column",'
                '{"width":"matchParent","height":140,"padding":12,'
                '"borderRadius":18,"clip":true,"space":8,'
                '"backgroundColor":"#FFFFFFFF"},["title","main","footer"]]',
                '["title","Text",'
                '{"width":116,"height":18,"content":"Title","fontSize":14}]',
                '["main","Text",'
                '{"width":116,"height":48,"content":"73%","fontSize":20}]',
                '["footer","Text",'
                '{"width":116,"height":28,"content":"Action","fontSize":14}]',
            ]
        )

        normalized = apply_compact_dsl_data_bindings(
            genui,
            {"suggestSize": "2x2", "dataBindings": []},
            [],
        )
        rows = [json.loads(line) for line in normalized.splitlines()]
        root = next(row for row in rows if row[0] == "root")
        report = validate_compact_dsl(normalized, {"suggestSize": "2x2"})

        self.assertEqual(root[2]["space"], 10)
        self.assertFalse(any("bottom gap" in item for item in report.errors))

    def test_large_bottom_gap_is_not_hidden_by_spacing_repair(self) -> None:
        genui = "\n".join(
            [
                '["root","Column",'
                '{"width":"matchParent","height":140,"padding":12,'
                '"borderRadius":18,"clip":true,"space":8},["one","two"]]',
                '["one","Text",'
                '{"width":116,"height":20,"content":"One","fontSize":14}]',
                '["two","Text",'
                '{"width":116,"height":20,"content":"Two","fontSize":14}]',
            ]
        )

        normalized = apply_compact_dsl_data_bindings(
            genui,
            {"suggestSize": "2x2", "dataBindings": []},
            [],
        )
        rows = [json.loads(line) for line in normalized.splitlines()]
        root = next(row for row in rows if row[0] == "root")
        report = validate_compact_dsl(normalized, {"suggestSize": "2x2"})

        self.assertEqual(root[2]["space"], 8)
        self.assertTrue(any("bottom gap" in item for item in report.errors))

    def test_common_direct_generation_style_drift_is_repaired(self) -> None:
        cardspec = {"suggestSize": "2x2", "dataBindings": []}
        source = "\n".join(
            [
                '["root","Stack",{"width":"140","height":"140",'
                '"padding":12},["temp","icon","button"]]',
                '["temp","Text",{"width":60,"height":24,"content":"28 C",'
                '"fontSize":22,"fontWeight":700}]',
                '["icon","Image",{"width":20,"height":20,'
                '"src":"resources/base/media/sun_max.svg"}]',
                '["button","Button",{"width":52,"height":26,"padding":[0,8,0,8],'
                '"label":"Open",'
                '"style":{"backgroundColor":"#191A1C","borderRadius":13}}]',
            ]
        )

        normalized = apply_compact_dsl_data_bindings(source, cardspec, [])
        rows = [json.loads(line) for line in normalized.splitlines()]
        rows_by_id = {row[0]: row for row in rows if len(row) >= 3}
        report = validate_compact_dsl(normalized, cardspec)

        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])
        self.assertEqual(rows_by_id["root"][2]["borderRadius"], 18)
        self.assertIs(rows_by_id["root"][2]["clip"], True)
        self.assertEqual(
            rows_by_id["root"][2]["constraintSize"],
            {
                "minWidth": 140,
                "maxWidth": 140,
                "minHeight": 140,
                "maxHeight": 140,
            },
        )
        self.assertEqual(rows_by_id["temp"][2]["fontSize"], 20)
        self.assertEqual(rows_by_id["icon"][2]["objectFit"], "contain")
        self.assertEqual(rows_by_id["button"][2]["backgroundColor"], "#191A1C")
        self.assertEqual(
            rows_by_id["button"][2]["padding"],
            {"top": 0, "right": 8, "bottom": 0, "left": 8},
        )
        self.assertNotIn("style", rows_by_id["button"][2])

    def test_light_foreground_without_surface_background_is_repaired(self) -> None:
        cardspec = {"suggestSize": "2x2", "dataBindings": []}
        source = "\n".join(
            [
                '["root","Stack",{"width":"matchParent","height":140,'
                '"padding":12,"borderRadius":18,"clip":true},["title","meta"]]',
                '["title","Text",{"content":"Weather","fontSize":16,'
                '"fontColor":"#FFFFFFFF"}]',
                '["meta","Text",{"content":"Updated","fontSize":10,'
                '"fontColor":"#99FFFFFF"}]',
            ]
        )

        raw_report = validate_compact_dsl(source, cardspec)
        normalized = apply_compact_dsl_data_bindings(source, cardspec, [])
        rows = [json.loads(line) for line in normalized.splitlines()]
        root = next(row for row in rows if row[0] == "root")
        normalized_report = validate_compact_dsl(normalized, cardspec)

        self.assertTrue(any("light foreground" in item for item in raw_report.errors))
        self.assertEqual(
            root[2]["linearGradient"],
            {
                "direction": "RightBottom",
                "colors": [["#FF3B4A54", 0], ["#FF202326", 1]],
            },
        )
        self.assertEqual(normalized_report.errors, [])
        self.assertEqual(normalized_report.warnings, [])

    def test_dark_foreground_without_surface_receives_light_gradient(self) -> None:
        cardspec = {"suggestSize": "2x2", "dataBindings": []}
        source = "\n".join(
            [
                '["root","Stack",{"width":"matchParent","height":140,'
                '"padding":12,"borderRadius":18,"clip":true},["title"]]',
                '["title","Text",{"content":"Weather","fontSize":16,'
                '"fontColor":"#FF000000"}]',
            ]
        )

        raw_report = validate_compact_dsl(source, cardspec)
        normalized = apply_compact_dsl_data_bindings(source, cardspec, [])
        root = json.loads(normalized.splitlines()[0])
        normalized_report = validate_compact_dsl(normalized, cardspec)

        self.assertNotIn("backgroundColor", root[2])
        self.assertEqual(
            root[2]["linearGradient"],
            {
                "direction": "RightBottom",
                "colors": [["#FFE8F1F5", 0], ["#FFE2ECE4", 1]],
            },
        )
        self.assertTrue(any("is required" in item for item in raw_report.errors))
        self.assertEqual(normalized_report.errors, [])

    def test_low_power_flat_surface_is_upgraded_to_green_gradient(self) -> None:
        cardspec = {"suggestSize": "2x2", "dataBindings": []}
        source = "\n".join(
            [
                '["root","Column",{"width":"matchParent","height":140,"padding":12,'
                '"borderRadius":18,"clip":true,"space":4,'
                '"backgroundColor":"#FFF1F3F5"},'
                '["title_text","main_row","action_button"]]',
                '["title_text","Text",{"width":116,"height":20,"content":"低电模式",'
                '"fontSize":14,"fontWeight":700,"fontColor":"#E5000000"}]',
                '["main_row","Row",{"width":116,"height":52,"space":4},'
                '["battery_icon","power_text"]]',
                '["battery_icon","Image",{"width":40,"height":40,'
                '"src":"resources/base/media/battery_leaf_fill.svg"}]',
                '["power_text","Text",{"width":72,"height":36,"content":"18%",'
                '"fontSize":32,"fontWeight":700,"fontColor":"#E5000000"}]',
                '["action_button","Button",{"width":116,"height":32,'
                '"label":"开启省电","fontSize":12,"fontWeight":600,'
                '"fontColor":"#FFFFFFFF","backgroundColor":"#FF64BB5C"}]',
            ]
        )

        normalized = apply_compact_dsl_data_bindings(source, cardspec, [])
        root = json.loads(normalized.splitlines()[0])
        report = validate_compact_dsl(normalized, cardspec)

        self.assertNotIn("backgroundColor", root[2])
        self.assertEqual(
            root[2]["linearGradient"],
            {
                "direction": "RightBottom",
                "colors": [["#FF61CFBE", 0], ["#FF92C48D", 1]],
            },
        )
        self.assertEqual(report.errors, [])

    def test_sleep_flat_surface_is_upgraded_to_purple_gradient(self) -> None:
        cardspec = {"suggestSize": "2x4", "dataBindings": []}
        source = "\n".join(
            [
                '["root","Column",{"width":"matchParent","height":140,"padding":12,'
                '"borderRadius":22,"clip":true,"space":4,'
                '"backgroundColor":"#FF191A1C"},'
                '["title_text","main_row","action_button"]]',
                '["title_text","Text",{"width":276,"height":20,"content":"睡眠助手",'
                '"fontSize":14,"fontWeight":700,"fontColor":"#FFFFFFFF"}]',
                '["main_row","Row",{"width":276,"height":52,"space":4},'
                '["sleep_value"]]',
                '["sleep_value","Text",{"width":276,"height":36,"content":"7小时20分",'
                '"fontSize":20,"fontWeight":700,"fontColor":"#FFFFFFFF"}]',
                '["action_button","Button",{"width":276,"height":32,'
                '"label":"睡眠报告","fontSize":12,"fontWeight":600,'
                '"fontColor":"#FFFFFFFF","backgroundColor":"#19FFFFFF"}]',
            ]
        )

        normalized = apply_compact_dsl_data_bindings(source, cardspec, [])
        root = json.loads(normalized.splitlines()[0])
        report = validate_compact_dsl(normalized, cardspec)

        self.assertNotIn("backgroundColor", root[2])
        self.assertEqual(
            root[2]["linearGradient"],
            {
                "direction": "RightBottom",
                "colors": [
                    ["#FF202224", 0],
                    ["#FF634794", 0.58],
                    ["#FF5F58C7", 1],
                ],
            },
        )
        self.assertEqual(report.errors, [])

    def test_visible_string_binding_requires_preview_value(self) -> None:
        cardspec = {"suggestSize": "2x2", "dataBindings": []}
        source = "\n".join(
            [
                '["root","Stack",{"width":"matchParent","height":140,'
                '"padding":12,"borderRadius":18,"clip":true},["title"]]',
                '["title","Text",{"content":{"path":"/weather/condition"},'
                '"fontSize":16,"fontColor":"#FF000000"}]',
                '["/weather/condition",""]',
            ]
        )

        report = validate_compact_dsl(source, cardspec)

        self.assertTrue(any("non-empty preview value" in item for item in report.errors))

    def test_unbacked_display_paths_materialize_without_changing_event_paths(self) -> None:
        cardspec = {"suggestSize": "2x2", "dataBindings": []}
        source = "\n".join(
            [
                '["root","Column",{"width":"matchParent","height":140,'
                '"padding":12,"borderRadius":18,"clip":true},'
                '["status","level","action"]]',
                '["status","Text",{"content":{"path":"/data/battery/status"}}]',
                '["/data/battery/status","放电中"]',
                '["level","Text",{"content":{"path":"/data/battery/level"}}]',
                '["/data/battery/level",18]',
                '["action","Button",{"label":"开启省电模式",'
                '"action":{"functionCall":{"call":"clickToIntent",'
                '"args":{"target":{"path":"/destination/id"}}}}}]',
                '["/destination/id","power-saving"]',
            ]
        )

        normalized = apply_compact_dsl_data_bindings(source, cardspec, [])
        rows = [json.loads(line) for line in normalized.splitlines()]
        rows_by_id = {row[0]: row for row in rows if len(row) >= 3}
        data_rows = {row[0]: row[1] for row in rows if len(row) == 2}

        self.assertEqual(rows_by_id["status"][2]["content"], "放电中")
        self.assertEqual(rows_by_id["level"][2]["content"], "18")
        self.assertEqual(
            rows_by_id["action"][2]["action"]["functionCall"]["args"]["target"],
            {"path": "/destination/id"},
        )
        self.assertNotIn("/data/battery/status", data_rows)
        self.assertNotIn("/data/battery/level", data_rows)
        self.assertEqual(data_rows["/destination/id"], "power-saving")

    def test_capability_backed_display_path_stays_dynamic(self) -> None:
        cardspec = {
            "suggestSize": "2x2",
            "dataBindings": [
                {
                    "capabilityId": "ViewWeather",
                    "writeResultTo": "/data/weather",
                }
            ],
        }
        source = "\n".join(
            [
                '["root","Column",{"width":"matchParent","height":140,'
                '"padding":12,"borderRadius":18,"clip":true},["condition"]]',
                '["condition","Text",'
                '{"content":{"path":"/data/weather/current/condition"}}]',
                '["/data/weather/current/condition","小雨"]',
            ]
        )

        normalized = apply_compact_dsl_data_bindings(source, cardspec, [])
        rows = [json.loads(line) for line in normalized.splitlines()]

        self.assertEqual(
            rows[1][2]["content"],
            {"path": "/data/weather/current/condition"},
        )
        self.assertEqual(rows[2], ["/data/weather/current/condition", "小雨"])

    def test_sleep_duration_font_is_repaired_to_fit(self) -> None:
        cardspec = {"suggestSize": "2x4", "dataBindings": []}
        source = "\n".join(
            [
                '["root","Stack",{"width":"matchParent","height":140,'
                '"padding":12,"borderRadius":22,"clip":true},["duration_text"]]',
                '["duration_text","Text",{"width":92,"height":24,'
                '"content":"7小时24分","fontSize":20,"fontWeight":700,'
                '"fontColor":"#FFFFFFFF","maxLines":1}]',
            ]
        )

        normalized = apply_compact_dsl_data_bindings(source, cardspec, [])
        rows = [json.loads(line) for line in normalized.splitlines()]
        report = validate_compact_dsl(normalized, cardspec)

        self.assertEqual(rows[1][2]["fontSize"], 18)
        self.assertEqual(report.errors, [])

    def test_flat_sleep_output_is_repaired_without_model_retry(self) -> None:
        cardspec = {
            "suggestSize": "2x4",
            "dataBindings": [
                {
                    "capabilityId": "calendar.events.search",
                    "writeResultTo": "/data/sleep",
                    "updateModel": {},
                }
            ],
        }
        capabilities = [
            {
                "id": "calendar.events.search",
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {"title": {"type": "string"}},
                            },
                        }
                    },
                },
            }
        ]
        source_rows = [
            [
                "root",
                "Column",
                {
                    "width": "matchParent",
                    "height": 140,
                    "padding": 12,
                    "space": 4,
                    "backgroundColor": "#FF191A1C",
                },
            ],
            ["header_row", "Row", {"width": 276, "height": 20, "space": 4}],
            ["title_group", "Row", {"width": 132, "height": 20, "space": 4}],
            ["sleep_icon", "Image", {"width": 18, "height": 18, "src": "sleep.svg"}],
            [
                "title_text",
                "Text",
                {"width": 110, "height": 20, "content": "\u7761\u7720\u52a9\u624b", "fontSize": 14},
            ],
            ["mode_badge", "Row", {"width": 140, "height": 20, "space": 4}],
            [
                "mode_dot",
                "Text",
                {"width": 6, "height": 6, "backgroundColor": "#5BA854"},
            ],
            [
                "mode_text",
                "Text",
                {"width": 100, "height": 16, "content": "\u653e\u677e\u6a21\u5f0f", "fontSize": 12},
            ],
            ["main_row", "Row", {"width": 276, "height": 64, "space": 8}],
            ["meter_stack", "Stack", {"width": 64, "height": 64}],
            [
                "sleep_ring",
                "Progress",
                {"width": 64, "height": 64, "value": 72, "total": 100},
            ],
            ["meter_icon", "Image", {"width": 28, "height": 28, "src": "moon.svg"}],
            ["primary_info", "Column", {"width": 136, "height": 64, "space": 2}],
            [
                "primary_value",
                "Text",
                {"width": 136, "height": 34, "content": "7h 24m", "fontSize": 32},
            ],
            [
                "primary_caption",
                "Text",
                {
                    "width": 136,
                    "height": 16,
                    "content": "\u5df2\u5165\u7761\u65f6\u957f",
                    "fontSize": 12,
                },
            ],
            ["status_row", "Row", {"width": 136, "height": 12, "space": 4}],
            [
                "status_dot",
                "Text",
                {"width": 6, "height": 6, "backgroundColor": "#5BA854"},
            ],
            [
                "status_text",
                "Text",
                {"width": 126, "height": 12, "content": "\u6df1\u5ea6\u7761\u7720", "fontSize": 12},
            ],
            ["support_card", "Row", {"width": 276, "height": 24, "space": 8}],
            [
                "support_text",
                "Text",
                {
                    "width": 180,
                    "height": 16,
                    "content": "\u4e0b\u4e00\u4e2a\u95f9\u949f 06:30",
                    "fontSize": 12,
                },
            ],
            ["action_row", "Row", {"width": 276, "height": 32, "space": 8}],
            [
                "sleep_action",
                "Button",
                {"width": 134, "height": 32, "label": "\u7761\u7720\u8be6\u60c5", "fontSize": 12},
            ],
            [
                "alarm_action",
                "Button",
                {"width": 134, "height": 32, "label": "\u8bbe\u7f6e\u95f9\u949f", "fontSize": 12},
            ],
        ]
        serialized_rows = [
            json.dumps(row, ensure_ascii=True, separators=(",", ":"))
            for row in source_rows
        ]
        source_lines = [f"{serialized_rows[0]},"]
        source_lines.extend(f'{row},"' for row in serialized_rows[1:])
        source = "\n".join(source_lines)

        normalized = apply_compact_dsl_data_bindings(source, cardspec, capabilities)
        rows = [json.loads(line) for line in normalized.splitlines()]
        rows_by_id = {row[0]: row for row in rows if len(row) >= 3}
        data_rows = {row[0]: row[1] for row in rows if len(row) == 2}
        report = validate_compact_dsl(normalized, cardspec)

        self.assertEqual(
            rows_by_id["root"][3],
            ["header_row", "main_row", "action_row"],
        )
        self.assertEqual(rows_by_id["meter_stack"][3], ["sleep_ring", "meter_icon"])
        self.assertEqual(rows_by_id["primary_info"][3], ["primary_value", "status_row"])
        self.assertEqual(rows_by_id["mode_dot"][2]["content"], "")
        self.assertEqual(rows_by_id["status_dot"][2]["content"], "")
        self.assertEqual(
            rows_by_id["status_text"][2]["content"],
            {"path": "/data/sleep/items/0/title"},
        )
        self.assertEqual(data_rows["/data/sleep/items/0/title"], "\u6df1\u5ea6\u7761\u7720")
        self.assertNotIn("primary_caption", rows_by_id)
        self.assertNotIn("support_card", rows_by_id)
        self.assertEqual(report.errors, [])

    def test_sleep_binding_accepts_status_pill_text(self) -> None:
        cardspec = {
            "suggestSize": "2x4",
            "dataBindings": [
                {
                    "capabilityId": "calendar.events.search",
                    "writeResultTo": "/data/sleep",
                }
            ],
        }
        capabilities = [
            {
                "id": "calendar.events.search",
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {"title": {"type": "string"}},
                            },
                        }
                    },
                },
            }
        ]
        source = "\n".join(
            [
                '["root","Stack",{"width":"matchParent","height":140,'
                '"padding":12},["status_pill","alarm_status"]]',
                '["status_pill","Text",{"width":92,"height":24,'
                '"content":"\u6df1\u5ea6\u7761\u7720","fontSize":12,"maxLines":1}]',
                '["alarm_status","Text",{"width":84,"height":12,'
                '"content":"\u5df2\u8bbe\u7f6e","fontSize":10,"maxLines":1}]',
            ]
        )

        normalized = apply_compact_dsl_data_bindings(source, cardspec, capabilities)
        rows = [json.loads(line) for line in normalized.splitlines()]
        rows_by_id = {row[0]: row for row in rows if len(row) >= 3}
        data_rows = {row[0]: row[1] for row in rows if len(row) == 2}
        report = validate_compact_dsl(normalized, cardspec)

        self.assertEqual(
            rows_by_id["status_pill"][2]["content"],
            {"path": "/data/sleep/items/0/title"},
        )
        self.assertEqual(rows_by_id["alarm_status"][2]["content"], "\u5df2\u8bbe\u7f6e")
        self.assertEqual(data_rows["/data/sleep/items/0/title"], "\u6df1\u5ea6\u7761\u7720")
        self.assertEqual(report.errors, [])

    def test_chinese_button_label_is_repaired_without_ellipsis(self) -> None:
        cardspec = {"suggestSize": "2x2", "dataBindings": []}
        source = "\n".join(
            [
                '["root","Stack",{"width":"matchParent","height":140,'
                '"padding":12,"borderRadius":18,"clip":true},["action_button"]]',
                '["action_button","Button",{"width":61,"height":32,'
                '"label":"看天气","fontSize":12,"fontWeight":600}]',
            ]
        )

        normalized = apply_compact_dsl_data_bindings(source, cardspec, [])
        rows = [json.loads(line) for line in normalized.splitlines()]
        report = validate_compact_dsl(normalized, cardspec)

        self.assertEqual(rows[1][2]["label"], "看天气")
        self.assertEqual(rows[1][2]["fontSize"], 10)
        self.assertEqual(report.errors, [])

    def test_dense_header_preserves_text_before_decorative_icons(self) -> None:
        cardspec = {"suggestSize": "2x4", "dataBindings": []}
        source = "\n".join(
            [
                '["root","Stack",{"width":"matchParent","height":140,'
                '"padding":12,"borderRadius":22,"clip":true},["header_row"]]',
                '["header_row","Row",{"width":276,"height":22,"space":4},'
                '["title_group","status_pill"]]',
                '["title_group","Row",{"width":184,"height":22,"space":6},'
                '["title_icon","title_text","subtitle_text"]]',
                '["title_icon","Image",{"width":18,"height":18,'
                '"src":"resources/base/media/clock_fill.svg"}]',
                '["title_text","Text",{"width":72,"height":22,'
                '"content":"防沉迷助手","fontSize":14,"maxLines":1}]',
                '["subtitle_text","Text",{"width":82,"height":18,'
                '"content":"本周使用时长监控","fontSize":12,"maxLines":1}]',
                '["status_pill","Row",{"width":88,"height":22,'
                '"padding":{"top":2,"right":8,"bottom":2,"left":8},'
                '"space":4},["status_icon","status_text"]]',
                '["status_icon","Image",{"width":14,"height":14,'
                '"src":"resources/base/media/bell_slash_fill.svg"}]',
                '["status_text","Text",{"width":54,"height":16,'
                '"content":"护眼模式已开启","fontSize":12,"maxLines":1}]',
            ]
        )

        normalized = apply_compact_dsl_data_bindings(source, cardspec, [])
        rows = [json.loads(line) for line in normalized.splitlines()]
        rows_by_id = {row[0]: row for row in rows if len(row) >= 3}
        report = validate_compact_dsl(normalized, cardspec)

        self.assertEqual(rows_by_id["subtitle_text"][2]["fontSize"], 10)
        self.assertEqual(rows_by_id["status_text"][2]["content"], "护眼模式已开启")
        self.assertEqual(rows_by_id["status_text"][2]["fontSize"], 10)
        self.assertEqual(rows_by_id["status_text"][2]["width"], 72)
        self.assertEqual(rows_by_id["status_pill"][3], ["status_text"])
        self.assertNotIn("status_icon", rows_by_id)
        self.assertEqual(report.errors, [])

    def test_requested_size_sets_fixed_root_surface_constraint(self) -> None:
        source = "\n".join(
            [
                '["root","Stack",{"width":"matchParent","height":140,'
                '"padding":12},["title"]]',
                '["title","Text",{"content":"耳机播控","fontSize":14}]',
            ]
        )
        expected_widths = {"2x2": 140, "2x4": 300}

        for size, expected_width in expected_widths.items():
            cardspec = {"suggestSize": size, "dataBindings": []}
            normalized = apply_compact_dsl_data_bindings(source, cardspec, [])
            root = json.loads(normalized.splitlines()[0])

            self.assertEqual(
                root[2]["constraintSize"],
                {
                    "minWidth": expected_width,
                    "maxWidth": expected_width,
                    "minHeight": 140,
                    "maxHeight": 140,
                },
            )

    def test_storage_usage_label_uses_next_smaller_font(self) -> None:
        cardspec = {"suggestSize": "2x2", "dataBindings": []}
        source = "\n".join(
            [
                '["root","Stack",{"width":"matchParent","height":140,'
                '"padding":12},["usage_label"]]',
                '["usage_label","Text",{"width":20,"height":16,'
                '"content":"占用","fontSize":12,"maxLines":1}]',
            ]
        )

        normalized = apply_compact_dsl_data_bindings(source, cardspec, [])
        rows = [json.loads(line) for line in normalized.splitlines()]
        report = validate_compact_dsl(normalized, cardspec)

        self.assertEqual(rows[1][2]["content"], "占用")
        self.assertEqual(rows[1][2]["fontSize"], 10)
        self.assertEqual(report.errors, [])

    def test_row_spacing_reduces_to_largest_fitting_scale_value(self) -> None:
        cardspec = {"suggestSize": "2x4", "dataBindings": []}
        source = "\n".join(
            [
                '["root","Stack",{"width":"matchParent","height":140,'
                '"padding":12},["header_row"]]',
                '["header_row","Row",{"width":276,"height":24,"space":8},'
                '["mode_icon","title_text","status_text"]]',
                '["mode_icon","Image",{"width":20,"height":20,'
                '"src":"resources/base/media/bell_slash_fill.svg"}]',
                '["title_text","Text",{"width":152,"height":24,'
                '"content":"专注模式","fontSize":16,"maxLines":1}]',
                '["status_text","Text",{"width":96,"height":16,'
                '"content":"通知静音","fontSize":12,"maxLines":1}]',
            ]
        )

        normalized = apply_compact_dsl_data_bindings(source, cardspec, [])
        rows = [json.loads(line) for line in normalized.splitlines()]
        rows_by_id = {row[0]: row for row in rows if len(row) >= 3}
        report = validate_compact_dsl(normalized, cardspec)

        self.assertEqual(rows_by_id["header_row"][2]["space"], 4)
        self.assertEqual(report.errors, [])

    def test_capability_id_prefix_is_removed_from_calendar_paths(self) -> None:
        cardspec = {
            "suggestSize": "2x4",
            "dataBindings": [
                {
                    "capabilityId": "calendar.events.search",
                    "writeResultTo": "/data/calendar",
                    "updateModel": {},
                }
            ],
        }
        item_schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "dtStart": {"type": "string"},
            },
        }
        capabilities = [
            {
                "id": "calendar.events.search",
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "items": {"type": "array", "items": item_schema},
                    },
                },
            }
        ]
        source = "\n".join(
            [
                '["root","Stack",{"width":"matchParent","height":140,'
                '"padding":12},["event_title","event_time"]]',
                '["event_title","Text",{"width":228,"height":24,'
                '"content":{"path":"/data/calendar/events/search/items/0/title"},'
                '"fontSize":18,"maxLines":1}]',
                '["event_time","Text",{"width":228,"height":18,'
                '"content":{"path":"/data/calendar/events/search/items/0/dtStart"},'
                '"fontSize":14,"maxLines":1}]',
            ]
        )

        normalized = apply_compact_dsl_data_bindings(source, cardspec, capabilities)
        rows = [json.loads(line) for line in normalized.splitlines()]
        rows_by_id = {row[0]: row for row in rows if len(row) >= 3}
        data_rows = {row[0]: row[1] for row in rows if len(row) == 2}
        report = validate_compact_dsl(normalized, cardspec)

        self.assertEqual(
            rows_by_id["event_title"][2]["content"],
            {"path": "/data/calendar/items/0/title"},
        )
        self.assertEqual(
            rows_by_id["event_time"][2]["content"],
            {"path": "/data/calendar/items/0/dtStart"},
        )
        self.assertEqual(data_rows["/data/calendar/items/0/title"], "下一场日程")
        self.assertEqual(data_rows["/data/calendar/items/0/dtStart"], "09:00")
        self.assertEqual(report.errors, [])

    def test_calendar_event_action_and_description_are_repaired(self) -> None:
        cardspec = {
            "title": "\u5f53\u4e0b\u65e5\u7a0b",
            "description": "\u4eca\u65e5\u65e5\u7a0b\u4e0e\u4f1a\u8bae\u5165\u53e3",
            "suggestSize": "2x4",
            "dataBindings": [
                {
                    "capabilityId": "calendar.events.search",
                    "writeResultTo": "/data/calendarEvents",
                }
            ],
        }
        item_schema = {
            "type": "object",
            "properties": {
                "entityId": {"type": "string"},
                "title": {"type": "string"},
                "dtStart": {"type": "string"},
                "description": {"type": "string"},
            },
        }
        capabilities = [
            {
                "id": "calendar.events.search",
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "items": {"type": "array", "items": item_schema},
                    },
                },
            }
        ]
        source = "\n".join(
            [
                '["root","Column",{"width":"matchParent","height":140,'
                '"padding":12,"space":4},["header","main","action"]]',
                '["header","Row",{"width":276,"height":20},["title_text"]]',
                '["title_text","Text",{"width":276,"height":20,'
                '"content":"\u5f53\u4e0b\u65e5\u7a0b","fontSize":14,"maxLines":1}]',
                '["main","Row",{"width":276,"height":52,"space":8},'
                '["time_block","event_column"]]',
                '["time_block","Column",{"width":68,"height":52},["time_text"]]',
                '["time_text","Text",{"width":60,"height":24,'
                '"content":{"path":"/data/calendarEvents/items/0/dtStart"},'
                '"fontSize":20,"maxLines":1}]',
                '["/data/calendarEvents/items/0/dtStart","09:00"]',
                '["event_column","Column",{"width":192,"height":52,"space":4},'
                '["event_title","event_meta"]]',
                '["event_title","Text",{"width":192,"height":22,'
                '"content":{"path":"/data/calendarEvents/items/0/title"},'
                '"fontSize":16,"maxLines":1,"textOverflow":"ellipsis"}]',
                '["/data/calendarEvents/items/0/title","\u4e0b\u4e00\u573a\u65e5\u7a0b"]',
                '["event_meta","Text",{"width":192,"height":18,'
                '"content":{"path":"/data/calendarEvents/items/0/description"},'
                '"fontSize":12,"maxLines":1}]',
                '["/data/calendarEvents/items/0/description","\u65e5\u7a0b\u8be6\u60c5"]',
                '["action","Button",{"width":276,"height":32,"label":"\u5165\u4f1a",'
                '"action":{"functionCall":{"call":"clickToIntent","args":'
                '{"intentName":"ViewCalendarEvent","params":{"entityId":'
                '{"path":"/data/calendarEvents/items/0/entityId"}}}}}}]',
                '["/data/calendarEvents/items/0/entityId","event-1"]',
            ]
        )
        event_candidates = [
            {
                "call": "clickToIntent",
                "args": {
                    "intentName": "ViewCalendarEvent",
                    "params": {"entityId": {"path": "entityId"}},
                },
            }
        ]

        normalized = apply_compact_dsl_data_bindings(
            source,
            cardspec,
            capabilities,
            event_candidates,
        )
        rows = [json.loads(line) for line in normalized.splitlines()]
        rows_by_id = {row[0]: row for row in rows if len(row) >= 3}
        data_rows = {row[0]: row[1] for row in rows if len(row) == 2}
        report = validate_compact_dsl(normalized, cardspec)

        self.assertEqual(rows_by_id["action"][2]["label"], "\u67e5\u770b\u65e5\u7a0b")
        self.assertEqual(rows_by_id["event_title"][2]["textOverflow"], "none")
        self.assertEqual(rows_by_id["event_column"][3], ["event_title"])
        self.assertEqual(rows_by_id["event_column"][2]["justifyContent"], "center")
        self.assertNotIn("event_meta", rows_by_id)
        self.assertNotIn("/data/calendarEvents/items/0/description", data_rows)
        self.assertEqual(report.errors, [])

        detailed_source = source.replace(
            "\u65e5\u7a0b\u8be6\u60c5",
            "\u9879\u76ee\u8bc4\u5ba1\u6750\u6599",
        )
        detailed = apply_compact_dsl_data_bindings(
            detailed_source,
            cardspec,
            capabilities,
            event_candidates,
        )
        detailed_rows = [json.loads(line) for line in detailed.splitlines()]
        detailed_ids = {row[0] for row in detailed_rows if len(row) >= 3}
        self.assertIn("event_meta", detailed_ids)

    def test_large_text_overflow_still_requires_model_retry(self) -> None:
        cardspec = {"suggestSize": "2x4", "dataBindings": []}
        source = "\n".join(
            [
                '["root","Stack",{"width":"matchParent","height":140,'
                '"padding":12,"borderRadius":22,"clip":true},["title"]]',
                '["title","Text",{"width":30,"content":"很长的标题文本",'
                '"fontSize":20,"maxLines":1}]',
            ]
        )

        normalized = apply_compact_dsl_data_bindings(source, cardspec, [])
        report = validate_compact_dsl(normalized, cardspec)

        self.assertTrue(any("estimated width" in item for item in report.errors))

    def test_flat_schedule_output_rebuilds_tree_and_preview_values(self) -> None:
        cardspec = {
            "suggestSize": "2x4",
            "dataBindings": [
                {
                    "capabilityId": "calendar.events.search",
                    "writeResultTo": "/data/calendarEvents",
                    "updateModel": {},
                }
            ],
        }
        item_schema = {
            "type": "object",
            "properties": {
                "entityId": {"type": "string"},
                "title": {"type": "string"},
                "dtStart": {"type": "string"},
                "eventLocation": {"type": "string"},
            },
        }
        capabilities = [
            {
                "id": "calendar.events.search",
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "items": {"type": "array", "items": item_schema},
                    },
                },
            }
        ]
        source = "\n".join(
            [
                '["root","Column",{"width":"matchParent","height":140,'
                '"padding":12,"borderRadius":22,"clip":true,"space":4}]',
                '["header_row","Row",{"width":276,"height":22,"space":4}]',
                '["title_text","Text",{"width":176,"height":20,'
                '"content":"当下日程","fontSize":14,"maxLines":1}]',
                '["date_text","Text",{"width":96,"height":20,'
                '"content":"今天","fontSize":12,"maxLines":1}]',
                '["event_panel","Column",{"width":276,"height":58,'
                '"padding":8,"space":4}]',
                '["event_title","Text",{"width":260,"height":20,'
                '"content":{"path":"/data/calendarEvents/items/0/title"},'
                '"fontSize":14,"maxLines":1}]',
                '["event_meta","Row",{"width":260,"height":18,"space":8}]',
                '["time_text","Text",{"width":114,"height":16,'
                '"content":{"path":"/data/calendarEvents/items/0/dtStart"},'
                '"fontSize":12,"maxLines":1}]',
                '["location_text","Text",{"width":138,"height":16,'
                '"content":{"path":"/data/calendarEvents/items/0/eventLocation"},'
                '"fontSize":12,"maxLines":1}]',
                '["bottom_row","Row",{"width":276,"height":28,"space":8}]',
                '["status_text","Text",{"width":108,"height":16,'
                '"content":"会前准备","fontSize":12,"maxLines":1}]',
                '["action_button","Button",{"width":160,"height":28,'
                '"label":"进入会议","fontSize":12,'
                '"action":{"functionCall":{"call":"clickToIntent",'
                '"args":{"intentName":"ViewCalendarEvent","params":'
                '{"entityId":{"path":"/data/calendarEvents/items/0/entityId"}}}}}}]',
            ]
        )

        event_candidates = [
            {
                "call": "clickToIntent",
                "args": {
                    "intentName": "ViewCalendarEvent",
                    "params": {"entityId": {"path": "entityId"}},
                },
            }
        ]
        normalized = apply_compact_dsl_data_bindings(
            source,
            cardspec,
            capabilities,
            event_candidates,
        )
        rows = [json.loads(line) for line in normalized.splitlines()]
        rows_by_id = {row[0]: row for row in rows if len(row) >= 3}
        data_rows = {row[0]: row[1] for row in rows if len(row) == 2}
        report = validate_compact_dsl(normalized, cardspec)

        self.assertEqual(
            rows_by_id["root"][3],
            ["header_row", "event_panel", "bottom_row"],
        )
        self.assertEqual(rows_by_id["event_meta"][3], ["time_text", "location_text"])
        self.assertEqual(data_rows["/data/calendarEvents/items/0/title"], "下一场日程")
        self.assertEqual(data_rows["/data/calendarEvents/items/0/dtStart"], "09:00")
        self.assertEqual(data_rows["/data/calendarEvents/items/0/eventLocation"], "待确认")
        self.assertEqual(report.errors, [])

    def test_relative_event_path_cannot_escape_data_binding_root(self) -> None:
        cardspec = {
            "suggestSize": "2x2",
            "dataBindings": [
                {
                    "capabilityId": "calendar.events.search",
                    "writeResultTo": "/data/calendarEvents",
                }
            ],
        }
        source = "\n".join(
            [
                '["root","Column",{"width":"matchParent","height":140,'
                '"padding":12},["action_button"]]',
                '["action_button","Button",{"width":116,"height":32,'
                '"label":"进入会议","action":{"functionCall":'
                '{"call":"clickToIntent","args":{"intentName":'
                '"ViewCalendarEvent","params":{"entityId":'
                '{"path":"/outside/entityId"}}}}}}]',
                '["/outside/entityId","event-1"]',
            ]
        )
        event_candidates = [
            {
                "call": "clickToIntent",
                "args": {
                    "intentName": "ViewCalendarEvent",
                    "params": {"entityId": {"path": "entityId"}},
                },
            }
        ]

        with self.assertRaisesRegex(ValueError, "outside eventCandidates"):
            apply_compact_dsl_data_bindings(
                source,
                cardspec,
                [],
                event_candidates,
            )


if __name__ == "__main__":
    unittest.main()
