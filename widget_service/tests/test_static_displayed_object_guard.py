"""仅防全文已展示的完整对象消失，不冻结 should 的忠实摘要。"""

import copy
import json

import pytest

from services.generation_content_policy import STATIC_CONTENT_POLICY, content_policy_scope
from services.static_content_components import complete_static_text_trial
from services.static_content_presentation import static_candidate_expansion_error
from services.static_plan_review import (
    static_review_lost_displayed_object_indexes,
    static_review_lost_must_indexes,
)


@pytest.fixture(autouse=True)
def static_scope():
    with content_policy_scope(STATIC_CONTENT_POLICY):
        yield


def _source(items, *, title="共同主题", size="2x4"):
    children = ["header", "body"] if title is not None else ["body"]
    layout = "S-static-content" if size == "2x2" else "W-static-content"
    rows = [["root", "Layout", {"layout": layout}, children]]
    if title is not None:
        rows.append(["header", "SingleLineTitle", {"title": title}])
    values = []
    for name, content in items:
        values.append({"primaryText": name, "secondaryText": content})
    rows.extend([["body", "TextList", {"items": values}], ["/state/ready", True]])
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)


def _plan(items=None, *, title="共同主题", title_priority="should", size="2x4"):
    if items is None:
        items = [("对象甲", "完整说明甲"), ("对象乙", "完整说明乙")]
    facts = []
    groups = []
    if title is not None:
        facts.append({"text": title, "priority": title_priority, "displayRole": "title"})
        groups.append({"id": "theme", "kind": "shared", "identity": None, "factIndexes": [0]})
    for name, text in items:
        index = len(facts)
        facts.append({"text": text, "priority": "should", "displayRole": "body"})
        groups.append({
            "id": f"object-{index}", "kind": "object", "identity": name, "factIndexes": [index],
        })
    return {
        "info_required": facts,
        "contentGroups": groups,
        "staticPresentation": _source(items, title=title, size=size),
    }


@pytest.mark.parametrize("size", ["2x2", "2x4"])
def test_same_two_objects_do_not_require_another_object(size):
    original = _plan(size=size)
    before = copy.deepcopy(original)
    assert static_review_lost_displayed_object_indexes(original, before, size=size) == ()
    assert original == before


def test_three_to_two_detects_the_missing_previously_displayed_should_object():
    original = _plan([
        ("对象甲", "完整说明甲"), ("对象乙", "完整说明乙"), ("对象丙", "完整说明丙"),
    ], title=None)
    corrected = _plan()
    assert static_review_lost_displayed_object_indexes(original, corrected) == (2,)


def test_more_new_objects_do_not_mask_the_disappearance_of_an_old_object():
    original = _plan()
    corrected = _plan([
        ("对象甲", "完整说明甲"), ("对象丙", "完整说明丙"), ("对象丁", "完整说明乙"),
    ], title=None)
    assert static_review_lost_displayed_object_indexes(original, corrected) == (2,)


def test_same_object_can_use_a_faithful_shorter_summary():
    original = _plan([("对象甲", "完整说明甲"), ("对象乙", "周六、周日开放")])
    corrected = _plan([("对象甲", "完整说明甲"), ("对象乙", "周末开放")])
    assert static_review_lost_displayed_object_indexes(original, corrected) == ()


def test_clipped_old_candidate_does_not_block_a_new_shorter_candidate():
    original = _plan([("对象甲", "完整说明甲"), ("对象乙", "补充说明" * 20)])
    old_source = original.get("staticPresentation")
    assert isinstance(old_source, str)
    with complete_static_text_trial():
        assert static_candidate_expansion_error(old_source, "2x4") is not None
    assert static_review_lost_displayed_object_indexes(original, _plan([
        ("对象甲", "完整说明甲"),
    ])) == ()


def test_anonymous_old_object_is_not_hard_matched_by_position_or_text():
    original = _plan()
    groups = original.get("contentGroups")
    assert isinstance(groups, list)
    groups[2]["identity"] = None
    corrected = _plan([("对象甲", "完整说明甲")])
    assert static_review_lost_displayed_object_indexes(original, corrected) == ()


def test_duplicate_old_identities_are_ambiguous():
    original = _plan([("同名对象", "说明甲"), ("同名对象", "说明乙")])
    corrected = _plan([("其它对象", "说明丙")])
    assert static_review_lost_displayed_object_indexes(original, corrected) == ()


def test_one_old_display_cannot_establish_two_unique_object_owners():
    original = _plan()
    original["staticPresentation"] = _source([
        ("对象甲、对象乙", "完整说明甲"), ("对象乙", "完整说明乙"),
    ])
    corrected = _plan([("其它对象", "说明丙")])
    assert static_review_lost_displayed_object_indexes(original, corrected) == ()


def test_originally_undisplayed_object_is_not_newly_locked():
    original = _plan()
    original["staticPresentation"] = _source([("对象甲", "完整说明甲")])
    assert static_review_lost_displayed_object_indexes(original, copy.deepcopy(original)) == ()


def test_optional_header_can_yield_without_displacing_objects():
    original = _plan()
    corrected = _plan(title=None)
    assert static_review_lost_displayed_object_indexes(original, corrected) == ()


def test_required_header_remains_the_existing_must_guards_responsibility():
    original = _plan(title_priority="must")
    corrected = _plan(title=None)
    assert static_review_lost_displayed_object_indexes(original, corrected) == ()
    assert 0 in static_review_lost_must_indexes(original, corrected)


@pytest.mark.parametrize("missing", ["original", "corrected"])
def test_missing_presentation_preserves_existing_fallback(missing):
    original = _plan()
    corrected = copy.deepcopy(original)
    target = original if missing == "original" else corrected
    target.pop("staticPresentation")
    assert static_review_lost_displayed_object_indexes(original, corrected) == ()


@pytest.mark.parametrize("unreadable", ["original", "corrected"])
def test_unreadable_presentation_preserves_existing_fallback(unreadable):
    original = _plan()
    corrected = copy.deepcopy(original)
    target = original if unreadable == "original" else corrected
    target["staticPresentation"] = "此前可行候选"
    assert static_review_lost_displayed_object_indexes(original, corrected) == ()


def test_single_object_identity_can_be_displayed_in_the_header():
    rows = [
        ["root", "Layout", {"layout": "W-static-content"}, ["header", "body"]],
        ["header", "SingleLineTitle", {"title": "设备甲"}],
        ["body", "EmphasisText", {"mainText": "已连接"}],
        ["/state/ready", True],
    ]
    original = {
        "info_required": [
            {"text": "设备甲", "priority": "must", "displayRole": "title"},
            {"text": "已连接", "priority": "should", "displayRole": "body"},
        ],
        "contentGroups": [
            {"id": "one", "kind": "object", "identity": "设备甲", "factIndexes": [0, 1]},
        ],
        "staticPresentation": "\n".join(json.dumps(row, ensure_ascii=False) for row in rows),
    }
    corrected = copy.deepcopy(original)
    assert static_review_lost_displayed_object_indexes(original, corrected) == ()
    rows[1][2]["title"] = "设备乙"
    corrected["staticPresentation"] = "\n".join(
        json.dumps(row, ensure_ascii=False) for row in rows
    )
    assert static_review_lost_displayed_object_indexes(original, corrected) == (0, 1)
