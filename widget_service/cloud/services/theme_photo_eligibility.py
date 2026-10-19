"""图片内容准入只读定稿语义和行数合同，不推测端侧像素或改动布局。"""

import re

from services.compact_dsl_a2ui_converter import ComponentRow, DataRow, parse_compact_dsl_rows
from services.compact_plan import _compact_visible_state
from services.square_photo_expansion import SLEEP_FIELDS, expansion_business


def photo_content_reason(photo: dict, task: dict, evidence: dict,
                         final_layout: str | None) -> str | None:
    policy = photo.get("contentEligibility")
    if not policy:
        return None
    if not final_layout:
        return "图片内容限制需要定稿布局"
    try:
        parsed = parse_compact_dsl_rows(final_layout, expand_layouts=False)
    except ValueError:
        return "无法解析图片内容限制所需的定稿布局"
    by_id = {}
    values = {}
    for row in parsed:
        if isinstance(row, ComponentRow):
            by_id[row.component_id] = row
        elif isinstance(row, DataRow):
            values[row.path] = row.value
    root = by_id.get("root")
    if root is None or root.component_type != "Layout":
        return "图片内容限制需要语义布局根节点"
    if policy.get("kind") == "sleep-square":
        return _sleep_reason(policy, task, evidence, root, by_id)
    if policy.get("kind") == "weather-square":
        return _weather_reason(policy, task, evidence, root, by_id)
    if policy.get("kind") == "running-main":
        return _running_reason(policy, root, by_id, values)
    if policy.get("kind") == "left-main-wide":
        return _left_main_reason(policy, evidence, root, by_id)
    if policy.get("kind") == "calendar-square":
        return _calendar_reason(policy, task, evidence, root, by_id)
    return "未知图片内容限制"


def _subtree(identity: str, by_id: dict) -> list[ComponentRow]:
    result = []
    pending = [identity]
    visited = set()
    while pending:
        current = pending.pop()
        row = by_id.get(current)
        if row is None or current in visited:
            return []
        visited.add(current)
        result.append(row)
        pending.extend(reversed(row.children))
    return result


def _sleep_reason(policy: dict, task: dict, evidence: dict,
                  root: ComponentRow, by_id: dict) -> str | None:
    rows = _subtree("root", by_id)
    if not rows or expansion_business(task) != "sleep":
        return "睡眠图片仅用于睡眠单业务"
    state = _compact_visible_state(rows)
    allowed = SLEEP_FIELDS | {"targetDateText", "updatedAt"}
    for path in state.paths:
        if not path.startswith("/data/healthSport/") or path.rsplit("/", 1)[-1] not in allowed:
            return "睡眠图片不能混入其它业务或健康指标"
    if any(row.component_type in policy.get("excludeComponents", []) for row in rows):
        return "睡眠图片不允许胶囊按钮"
    layout = root.props.get("layout")
    placements = policy.get("layouts", {})
    placement = placements.get(layout)
    if placement not in {"left", "bottom"}:
        return "睡眠图片需要内容居左或贴底的布局"
    flow = evidence.get("textFlow", {})
    root_flow = flow.get("root", {})
    lines = root_flow.get("maxLines")
    if type(lines) is not int or lines <= 0:
        return "无法确认睡眠卡片的文字行数上界"
    if not policy.get("includeTitle", True):
        title_lines = flow.get(root.children[0], {}).get("maxLines") if root.children else None
        if type(title_lines) is not int:
            return "无法确认睡眠卡片标题行数"
        lines -= title_lines
    if lines > policy.get("maxTextLines", 0):
        return "睡眠卡片文字超过图片允许的行数"
    if placement == "left" and not root_flow.get("leftAligned"):
        return "睡眠图片内容未居左"
    return None


def _weather_reason(policy: dict, task: dict, evidence: dict,
                    root: ComponentRow, by_id: dict) -> str | None:
    data = task.get("dataModelSchema", {}).get("data", {})
    if not isinstance(data, dict) or set(data) != {"weather"}:
        return "小花图片仅用于普通天气单业务"
    rows = _subtree("root", by_id)
    state = _compact_visible_state(rows)
    if not state.paths or any(not path.startswith("/data/weather/") for path in state.paths):
        return "小花图片需要真实天气内容且不能混入其它业务"
    if re.search(r"alert|warning|rainProbability|precipitation", " ".join(state.paths), re.I):
        return "小花图片不用于预警或降雨专题"
    placement = policy.get("layouts", {}).get(root.props.get("layout"))
    if placement != "left":
        return "小花图片需要内容区整体居左的天气布局"
    reason = _weather_actions_reason(rows, evidence)
    if reason:
        return reason
    flow = evidence.get("textFlow", {})
    content = []
    for identity in root.children[1:]:
        row = by_id.get(identity)
        if row is None:
            return "小花图片缺少完整内容证据"
        content_flow = flow.get(identity, {})
        lines = content_flow.get("maxLines")
        if type(lines) is not int or lines <= 0:
            return "无法确认天气内容的文本布局"
        content.append(content_flow)
    if not content:
        return "小花图片缺少天气内容区"
    if not all(item.get("leftAligned") for item in content):
        return "小花图片的天气内容未居左"
    return None


def _weather_actions_reason(rows: list[ComponentRow], evidence: dict) -> str | None:
    if evidence.get("buttonIds"):
        return "小花图片不允许任何按钮或独立可点击控件"
    for row in rows:
        if row.component_type in {"CircleButton", "PillButton", "CardButton", "Button"}:
            return "小花图片不允许任何按钮或独立可点击控件"
        if row.component_id != "root" and row.props.get("onClick"):
            return "小花图片不允许任何按钮或独立可点击控件"
    return None


def _running_reason(policy: dict, root: ComponentRow, by_id: dict, values: dict) -> str | None:
    if not root.children:
        return "缺少左侧主业务内容"
    main = by_id.get(root.children[0])
    if main is None or main.component_type != "Region":
        return "缺少左侧主业务区域"
    variant = main.props.get("variant")
    supported = {"center", "title-content", "title-hero-support", "title-content-action",
                 "title-hero-support-action"}
    if variant not in supported:
        return "无法确认左侧主业务角色"
    primary_index = 0 if variant == "center" else 1
    if len(main.children) <= primary_index:
        return "缺少左侧主焦点"
    primary = _subtree(main.children[primary_index], by_id)
    if not primary:
        return "无法确认左侧主焦点"
    state = _compact_visible_state(primary)
    context = list(primary)
    if primary_index:
        context.extend(_subtree(main.children[0], by_id))
    visible = _compact_visible_state(context)
    texts = list(visible.literals)
    for path in visible.paths:
        value = values.get(path)
        if isinstance(value, str):
            texts.append(value)
    text = " ".join(texts)
    matches = set()
    countdown = "/data/countdown/countdownDays" in state.paths and all(
        path.startswith("/data/countdown/") for path in state.paths)
    if countdown and re.search(r"马拉松|marathon", text, re.I):
        matches.add("marathon-countdown")
    running = bool(re.search(r"跑步|跑了|晨跑|夜跑|长跑|慢跑|越野跑|running|jogging", text, re.I))
    activity_pattern = r"/data/healthSport/(?:exercise|run)"
    only_activity = bool(state.paths) and all(
        re.match(activity_pattern, path) for path in state.paths)
    if running and only_activity:
        matches.add("running")
    if not matches.intersection(policy.get("mainBusinesses", [])):
        return "运动图片要求左侧主业务为马拉松倒计时或跑步"
    return None


def _business_paths_match(paths: frozenset[str], business: str) -> bool:
    if not paths:
        return False
    if business == "sleep":
        allowed = SLEEP_FIELDS | {"targetDateText", "updatedAt"}
        for path in paths:
            if not path.startswith("/data/healthSport/") or path.rsplit("/", 1)[-1] not in allowed:
                return False
        return any(path.rsplit("/", 1)[-1] in SLEEP_FIELDS for path in paths)
    prefix = {"weather": "/data/weather/", "calendar": "/data/calendar/"}.get(business)
    return prefix is not None and all(path.startswith(prefix) for path in paths)


def _left_main_reason(policy: dict, evidence: dict,
                      root: ComponentRow, by_id: dict) -> str | None:
    if not root.children:
        return "缺少左侧主业务"
    main = by_id.get(root.children[0])
    if main is None or main.component_type != "Region":
        return "缺少左侧主业务区域"
    variant = main.props.get("variant")
    if variant not in {"title-content", "title-hero-support", "title-content-action",
                       "title-hero-support-action"} or len(main.children) < 2:
        return "左侧主业务需要居左的标题内容布局"
    primary = _subtree(main.children[1], by_id)
    whole = _subtree(main.component_id, by_id)
    business = policy.get("mainBusiness")
    if not _business_paths_match(_compact_visible_state(primary).paths, business):
        return "左侧主内容不是图片要求的业务"
    if not _business_paths_match(_compact_visible_state(whole).paths, business):
        return "左侧主业务混入其它业务指标"
    flow = evidence.get("textFlow", {}).get(main.component_id, {})
    lines = flow.get("maxLines")
    if type(lines) is not int or lines <= 0 or not flow.get("leftAligned"):
        return "左侧主业务内容未整体居左或缺少文字布局证据"
    return None


def _calendar_reason(policy: dict, task: dict, evidence: dict,
                     root: ComponentRow, by_id: dict) -> str | None:
    data = task.get("dataModelSchema", {}).get("data", {})
    rows = _subtree("root", by_id)
    if not isinstance(data, dict) or set(data) != {"calendar"}:
        return "拱门图片仅用于日程会议单业务"
    if not _business_paths_match(_compact_visible_state(rows).paths, "calendar"):
        return "拱门图片需要真实日程内容且不能混入其它业务"
    placement = policy.get("layouts", {}).get(root.props.get("layout"))
    if placement != "left" or len(root.children) < 2:
        return "拱门图片需要内容区居左的布局"
    for row in rows:
        if row.props.get("onClick") and row.component_id != "root":
            return "拱门图片内容区必须纯文字且不能有按钮"
        if row.component_type in {"CircleButton", "PillButton", "CardButton", "Button"}:
            return "拱门图片内容区必须纯文字且不能有按钮"
    if evidence.get("buttonIds"):
        return "拱门图片不允许按钮或独立可点击控件"
    if "nonTextIds" not in evidence or "nonTextAncestors" not in evidence:
        return "无法确认拱门卡片为纯文字"
    header = by_id.get(root.children[0])
    if header is None or header.component_type != "SingleLineTitle":
        return "无法确认拱门卡片的顶部标题"
    ancestors = evidence.get("nonTextAncestors", {})
    for identity in evidence.get("nonTextIds", []):
        if header.component_id not in ancestors.get(identity, []):
            return "拱门图片内容区只能包含文字，图标仅允许出现在顶部标题"
    flow = evidence.get("textFlow", {})
    lines = 0
    for identity in root.children[1:]:
        item = flow.get(identity, {})
        limit = item.get("maxLines")
        if type(limit) is not int or limit <= 0 or not item.get("leftAligned"):
            return "拱门图片内容未居左或缺少文字行数证据"
        lines += limit
    if lines > policy.get("maxTextLines", 0):
        return "拱门图片内容区文字超过两行"
    return None
