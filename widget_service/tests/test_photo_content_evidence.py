"""Regression coverage for distributed columns and current conditional body text."""

import copy

import pytest

from photo_samples.common import expanded
from services import post_layout_theme as themes
from services.theme_content_regions import body_text_flow_evidence
from test_uniform_photo_eligibility import PURPLE, choose, evidence, rejection, sample


def sleep_peer_pair():
    prefix = "/data/healthSport/"
    rows = [
        ["root", "Layout", {"layout": "S-title-content"}, ["title", "content"]],
        ["title", "SingleLineTitle", {"title": "Sleep"}],
        ["content", "Group", {"variant": "peer-pair"}, ["left", "right"]],
        ["left", "Group", {"variant": "hero-support"}, ["status", "duration"]],
        ["status", "EmphasisText", {
            "mainText": {"path": prefix + "sleepStatus"},
            "secondaryText": "{{ 'Score ' + ${" + prefix + "sleepScore} }}",
        }],
        ["duration", "SecondaryBody", {"items": [
            {"label": "Sleep", "value": {"path": prefix + "nightSleepDurationText"}},
        ]}],
        ["right", "Group", {"variant": "hero-support"}, ["deep", "times"]],
        ["deep", "SecondaryBody", {"items": [
            {"label": "Deep", "value": {"path": prefix + "deepSleepDurationText"}},
        ]}],
        ["times", "SecondaryBody", {"columns": 1, "items": [
            {"label": "Start", "value": {"path": prefix + "fallAsleepTimeText"}},
            {"label": "End", "value": {"path": prefix + "wakeupTimeText"}},
        ]}],
        [prefix + "sleepStatus", "Good"], [prefix + "sleepScore", 82],
        [prefix + "nightSleepDurationText", "7h1m"],
        [prefix + "deepSleepDurationText", "2h15m"],
        [prefix + "fallAsleepTimeText", "23:15"], [prefix + "wakeupTimeText", "07:30"],
    ]
    return expanded(rows, {"size": "2x2", "userQuery": "Sleep", "appVersion": "99.0.0"})


def test_sleep_peer_pair_is_three_rows_but_not_globally_left():
    saved = sleep_peer_pair()
    before = copy.deepcopy(saved.nodes)
    flow = evidence(saved).get("photoBodyTextFlow", {})
    assert flow.get("left", {}).get("lineCount") == 3
    assert flow.get("right", {}).get("lineCount") == 3
    assert flow.get("root", {}).get("lineCount") == 3
    assert flow.get("root", {}).get("leftAligned") is False
    assert rejection(saved, "photo-ux-sleep-square")
    assert rejection(saved, PURPLE) is None
    assert saved.nodes == before


def test_peer_pair_selection_falls_back_to_texture_without_changing_layout(monkeypatch):
    saved = sleep_peer_pair()
    result, audit = choose(saved, monkeypatch)
    assert audit.get("themeId") in {
        PURPLE, "photo-ux-texture-purple-diagonal-square",
    }
    assert themes.foreground_signature(result) == themes.foreground_signature(saved.source)


@pytest.mark.parametrize("first,last,allowed", [
    ({}, {}, True),
    ({}, {"layoutWeight": 1}, True),
    ({"layoutWeight": 1}, {"layoutWeight": 1}, False),
    ({"width": "50%"}, {"width": "50%"}, False),
    ({"width": "matchParent"}, {}, False),
    ({"width": "wrapContent"}, {}, True),
])
def test_row_alignment_uses_allocation_not_only_child_text_alignment(first, last, allowed):
    nodes = [
        {"id": "root", "component": "Row", "children": ["label", "value"],
         "styles": {"justifyContent": "start"}},
        {"id": "label", "component": "Text", "content": "Battery", "styles": first},
        {"id": "value", "component": "Text", "content": "80%", "styles": last},
    ]
    flow = body_text_flow_evidence(nodes, {}).get("root", {})
    assert flow.get("lineCount") == 1
    assert flow.get("leftAligned") is allowed


@pytest.mark.parametrize("weight,allowed", [(0, True), (1, False)])
def test_stretching_spacer_before_text_is_not_globally_left(weight, allowed):
    nodes = [
        {"id": "root", "component": "Row", "children": ["spacer", "value"]},
        {"id": "spacer", "component": "Column", "children": [],
         "styles": {"layoutWeight": weight}},
        {"id": "value", "component": "Text", "content": "80%"},
    ]
    assert body_text_flow_evidence(nodes, {}).get("root", {}).get("leftAligned") is allowed


def conditional_wide(condition, extra_lines):
    path = "/data/earphone/isConnected"
    saved = sample(path, wide=True, button=False)
    rows = themes.decode(saved.compact)
    for row in rows:
        if row[0] == path:
            row[1] = condition
        elif row[0] == "reading":
            row[2]["content"] = "{{ ${" + path + "} ? 'Connected' : 'Not connected' }}"
        elif row[0] == "main":
            row[2]["variant"] = "title-hero-support"
            row[3].append("details")
    rows.append(["details", "Text", {"content": "\n".join(["Detail"] * extra_lines),
                                      "maxLines": 20}])
    return expanded(rows, saved.task)


@pytest.mark.parametrize("condition", [True, False])
@pytest.mark.parametrize("extra_lines,allowed", [(2, True), (3, True), (4, False)])
def test_wide_conditional_body_counts_current_branch_with_four_line_limit(
    condition, extra_lines, allowed,
):
    saved = conditional_wide(condition, extra_lines)
    before = copy.deepcopy(saved.nodes)
    flow = evidence(saved).get("photoBodyTextFlow", {}).get("main", {})
    assert flow.get("lineCount") == 1 + extra_lines
    reason = rejection(saved, "photo-ux-concert-stage-wide")
    assert (reason is None) is allowed
    reason = rejection(saved, PURPLE.replace("square", "wide"))
    assert (reason is None) is (extra_lines <= 2)
    assert saved.nodes == before


@pytest.mark.parametrize("condition", [None, "false", 0, 1])
def test_unresolved_boolean_body_still_fails_closed(condition):
    saved = conditional_wide(condition, 1)
    flow = evidence(saved).get("photoBodyTextFlow", {}).get("main", {})
    assert flow.get("lineCount") is None
    assert rejection(saved, "photo-ux-concert-stage-wide")
    assert rejection(saved, PURPLE.replace("square", "wide"))


@pytest.mark.parametrize("connected,lines", [(True, 1), (False, 2)])
def test_conditional_counts_selected_newlines_not_max_lines(connected, lines):
    nodes = [{"id": "root", "component": "Text", "styles": {"maxLines": 20},
              "content": "{{ ${/connected} ? 'One' : 'One\\nTwo' }}"}]
    assert body_text_flow_evidence(nodes, {"connected": connected}).get("root", {}).get(
        "lineCount"
    ) == lines
