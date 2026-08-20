# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import json

from services.card_validation import validate_card


def _calendar_genui(click_index: int) -> str:
    messages = [
        {
            "version": "v0.9",
            "createSurface": {
                "surfaceId": "calendar-card",
                "catalogId": "ohos.a2ui.extended.catalog.form",
            },
        },
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": "calendar-card",
                "root": "root",
                "components": [
                    {
                        "id": "root",
                        "component": "Column",
                        "children": ["eventItem1"],
                        "styles": {
                            "width": "matchParent",
                            "height": "matchParent",
                            "padding": 12,
                            "borderRadius": 18,
                            "clip": True,
                            "backgroundColor": "#FFFFFFFF",
                        },
                    },
                    {
                        "id": "eventItem1",
                        "component": "Column",
                        "children": ["eventTitle1", "eventTime1"],
                        "onClick": [
                            {
                                "call": "clickToIntent",
                                "args": {
                                    "intentName": "ViewCalendarEvent",
                                    "params": {
                                        "entityId": (
                                            "{{ ${/data/calendar/events/"
                                            f"{click_index}/entityId}} }}"
                                        ),
                                    },
                                },
                            },
                        ],
                    },
                    {
                        "id": "eventTitle1",
                        "component": "Text",
                        "content": "{{ ${/data/calendar/events/1/title} }}",
                    },
                    {
                        "id": "eventTime1",
                        "component": "Text",
                        "content": "{{ ${/data/calendar/events/1/dtStart} }}",
                    },
                ],
            },
        },
        {
            "version": "v0.9",
            "updateDataModel": {
                "surfaceId": "calendar-card",
                "path": "/",
                "value": {
                    "data": {
                        "calendar": {
                            "events": [
                                {
                                    "title": "项目例会",
                                    "dtStart": "14:00",
                                    "entityId": "event-0",
                                },
                                {
                                    "title": "产品评审",
                                    "dtStart": "16:00",
                                    "entityId": "event-1",
                                },
                            ],
                        },
                    },
                },
            },
        },
    ]
    return "\n".join(
        json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        for message in messages
    )


def _cardspec() -> dict:
    return {
        "title": "日程安排",
        "description": "今日日程",
        "suggestSize": "2x2",
        "dataBindings": [
            {
                "capabilityId": "GetCalendarEvents",
                "arguments": {},
                "writeResultTo": "/data/calendar",
            },
        ],
    }


def test_validator_rejects_click_index_different_from_displayed_item() -> None:
    reporter = validate_card(
        dsl_text=_calendar_genui(click_index=0),
        cardspec=_cardspec(),
    )

    mismatch = [
        item
        for item in reporter.diagnostics
        if item.code == "EVENT_ITEM_INDEX_MISMATCH"
    ]
    assert len(mismatch) == 1
    assert mismatch[0].actual == ["/data/calendar/events/0"]
    assert mismatch[0].expected == "/data/calendar/events/1"


def test_validator_accepts_click_index_matching_displayed_item() -> None:
    reporter = validate_card(
        dsl_text=_calendar_genui(click_index=1),
        cardspec=_cardspec(),
    )

    assert not reporter.has_code("EVENT_ITEM_INDEX_MISMATCH")
