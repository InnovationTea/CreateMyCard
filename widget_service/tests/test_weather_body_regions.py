"""天气方图按实际正文/底部结构选图，两条生成链路共用规则。"""

import copy

import pytest

from photo_samples.common import expanded
from services import post_layout_theme as themes
from services.template_generation.engine.cardplan.photo_facts import template_photo_facts
from services.theme_body_regions import body_region_evidence
from services.theme_photo_eligibility import fusion_photo_facts
from services.theme_photo_matching import photo_reason
from test_shared_photo_postprocessing import template_source
from test_uniform_photo_eligibility import ACTION, PATHS, choose, evidence, photo, rejection
from test_wide_photo_focus import focus_sample

SUNSETS = ("photo-ux-mountain-sunset-lake-square", "photo-ux-pink-sunset-lake-square")
CLOUD = "photo-ux-cumulus-blue-square"


def weather_regions(main_lines=2, footer="text", *, pinned=True):
    children = ["main"]
    rows = [
        ["root", "Column", {"width": "matchParent", "height": "matchParent"},
         ["header", "body"]],
        ["header", "SingleLineTitle", {"title": "状态"}],
        ["body", "Column", {"width": "matchParent", "layoutWeight": 1}, children],
        ["main", "Column", {"width": "matchParent", "layoutWeight": 1 if pinned else 0},
         ["reading"]],
        ["reading", "Text", {"content": {"path": PATHS.get("weather")}, "maxLines": 10}],
        [PATHS.get("weather"), "\n".join(["正文"] * main_lines)],
    ]
    if footer:
        children.append("footer")
        if footer == "button":
            rows.append(["footer", "PillButton", {"label": "操作", "onClick": ACTION}])
        else:
            rows.append(["footer", "Text", {"content": footer.replace("text", "辅助"),
                                             "maxLines": 10}])
    return expanded(rows, {"size": "2x2", "appVersion": "99.0.0", "userQuery": "天气",
                           "dataModelSchema": {"data": {"unused": {}}}})


@pytest.mark.parametrize("main,footer,allowed", [
    (1, None, SUNSETS), (2, None, SUNSETS), (2, "text", SUNSETS),
    (2, "button", SUNSETS), (3, None, (CLOUD,)), (3, "button", (CLOUD,)),
    (3, "text", ()), (2, "text\ntext", ()), (0, "button", ()), (4, None, ()),
])
def test_shared_routes_apply_region_rules_and_keep_sources(main, footer, allowed):
    saved = weather_regions(main, footer)
    before = copy.deepcopy(saved.nodes)
    source, _ = template_source(saved)
    facts = [fusion_photo_facts(saved.task, evidence(saved), saved.compact),
             template_photo_facts(source, saved.task, "状态")]
    for current in facts:
        actual = []
        for identity in (*SUNSETS, CLOUD):
            if photo_reason(photo(identity), current) is None:
                actual.append(identity)
        assert set(actual) == set(allowed)
    assert saved.nodes == before


def test_unanchored_third_line_remains_in_main_region():
    saved = weather_regions(2, "text", pinned=False)
    assert all(rejection(saved, identity) for identity in SUNSETS)
    assert rejection(saved, CLOUD) is None


def test_unanchored_button_is_not_reported_as_bottom():
    saved = weather_regions(2, "button", pinned=False)
    assert all(rejection(saved, identity) for identity in (*SUNSETS, CLOUD))


def test_footer_text_and_button_are_not_one_accepted_footer():
    saved = weather_regions(1, "text")
    rows = themes.decode(saved.compact)
    body = next(row for row in rows if row[0] == "body")
    body[3].append("button")
    rows.append(["button", "PillButton", {"label": "操作", "onClick": ACTION}])
    saved = expanded(rows, saved.task)
    assert all(rejection(saved, identity) for identity in (*SUNSETS, CLOUD))


@pytest.mark.parametrize("layout", ["spaceBetween", "spacer", "ambiguous", "offset"])
def test_position_proof_uses_structure_not_ids(layout):
    saved = weather_regions()
    rows = themes.decode(saved.compact)
    body = next(row for row in rows if row[0] == "body")
    main = next(row for row in rows if row[0] == "main")
    main[2].pop("layoutWeight")
    if layout == "spaceBetween":
        body[2]["justifyContent"] = "spaceBetween"
    elif layout == "spacer":
        body[3].insert(1, "gap")
        rows.append(["gap", "Column", {"layoutWeight": 1}, []])
    elif layout == "ambiguous":
        body[2]["justifyContent"] = "spaceAround"
    else:
        main[2]["offset"] = {"x": 0, "y": 30}
    saved = expanded(rows, saved.task)
    assert (rejection(saved, SUNSETS[0]) is None) is (layout in {"spaceBetween", "spacer"})


@pytest.mark.parametrize("selected", SUNSETS)
def test_two_sunsets_share_the_same_uniform_pool(monkeypatch, selected):
    calls = []

    def pick(items):
        calls.append(items)
        assert set(items) == set(SUNSETS)
        return selected

    monkeypatch.setattr(themes.secrets, "choice", pick)
    saved = weather_regions()
    output, audit = choose(saved, monkeypatch)
    assert audit.get("themeId") == selected
    assert len(calls) == 1
    assert themes.foreground_signature(output) == themes.foreground_signature(saved.source)


@pytest.mark.parametrize("direction", ["left", "right", "top"])
def test_weather_wide_rules_do_not_change(direction):
    saved = focus_sample("weather", 4, direction)
    for identity in (*SUNSETS, CLOUD):
        assert rejection(saved, identity.replace("square", "wide")) is None


def test_unknown_text_or_nonleft_alignment_is_not_relaxed():
    saved = weather_regions()
    for node in saved.nodes:
        if node.get("id") == "reading":
            node["content"] = {"path": "/missing"}
    assert rejection(saved, SUNSETS[0])
    saved = weather_regions()
    for node in saved.nodes:
        if node.get("id") == "reading":
            node.setdefault("styles", {})["textAlign"] = "center"
    assert rejection(saved, SUNSETS[0])


@pytest.mark.parametrize("orientation,allowed", [("Row", True), ("Column", False)])
def test_footer_counts_button_rows_not_button_labels(orientation, allowed):
    saved = weather_regions(2, "button")
    rows = themes.decode(saved.compact)
    footer = next(row for row in rows if row[0] == "footer")
    footer[:] = ["footer", orientation, {}, ["a", "b"]]
    for identity in ("a", "b"):
        rows.append([identity, "PillButton", {"label": "操作", "onClick": ACTION}])
    saved = expanded(rows, saved.task)
    assert (rejection(saved, SUNSETS[0]) is None) is allowed


def test_region_evidence_does_not_depend_on_node_names():
    saved = weather_regions()
    records = themes.decode(saved.source)
    nodes = themes.components(records)
    replacements = {}
    for index, node in enumerate(nodes):
        identity = node.get("id")
        if identity != "root":
            replacements[identity] = f"node_{index}"
    for node in nodes:
        identity = node.get("id")
        node["id"] = replacements.get(identity, identity)
        if "children" in node:
            node["children"] = [replacements.get(child, child) for child in node.get("children")]
    original = evidence(saved)
    flows = {}
    for identity, value in original.get("photoBodyTextFlow", {}).items():
        flows[replacements.get(identity, identity)] = value
    title_ids = {replacements.get("header")}
    result = body_region_evidence(nodes, flows, title_ids, set())
    assert result == original.get("photoBodyRegions")
