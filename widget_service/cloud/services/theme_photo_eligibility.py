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
    if policy.get("kind") == "sleep-capsule-square":
        return _sleep_capsule_reason(policy, task, by_id)
    if policy.get("kind") == "weather-square":
        return _weather_reason(policy, task, evidence, root, by_id)
    if policy.get("kind") == "running-main":
        return _running_reason(policy, root, by_id, values)
    if policy.get("kind") == "left-main-wide":
        return _left_main_reason(policy, evidence, root, by_id)
    if policy.get("kind") == "calendar-square":
        return _calendar_reason(policy, task, evidence, root, by_id)
    if policy.get("kind") == "calendar-text-square":
        return _calendar_text_reason(task, evidence, root, by_id)
    if policy.get("kind") == "countdown-square":
        return _countdown_reason(policy, task, evidence, root, by_id, values)
    if policy.get("kind") in {"music-square", "music-dual-buttons-square"}:
        return _music_reason(policy, evidence, root, by_id)
    if policy.get("kind") in {"battery-square", "battery-wide"}:
        return _battery_reason(policy, evidence, root, by_id)
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
    if policy.get("buttonPolicy") == "none" and _has_independent_control(rows, evidence):
        return "卧室睡眠图片不允许按钮或独立可点击控件"
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
    if placement == "left" and not _sleep_content_left_aligned(root, by_id, flow):
        return "睡眠图片内容未居左"
    return None


def _sleep_content_left_aligned(root: ComponentRow, by_id: dict, flow: dict) -> bool:
    for identity in root.children:
        child = by_id.get(identity)
        if child is None:
            return False
        if not flow.get(identity, {}).get("leftAligned"):
            return False
    return True


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
    placement = policy.get("layouts", {}).get(root.props.get("layout"))
    header = by_id.get(root.children[0]) if root.children else None
    reason: str | None = None
    if not isinstance(data, dict) or set(data) != {"calendar"}:
        reason = "拱门图片仅用于日程会议单业务"
    elif not _business_paths_match(_compact_visible_state(rows).paths, "calendar"):
        reason = "拱门图片需要真实日程内容且不能混入其它业务"
    elif placement != "left" or len(root.children) < 2:
        reason = "拱门图片需要内容区居左的布局"
    elif header is None or header.component_type != "SingleLineTitle":
        reason = "无法确认拱门卡片的顶部标题"
    flow = evidence.get("textFlow", {})
    lines = 0
    for identity in root.children[1:]:
        if reason is not None:
            break
        child = by_id.get(identity)
        if child is None:
            reason = "拱门图片缺少完整内容证据"
            break
        item = flow.get(identity, {})
        limit = item.get("maxLines")
        if type(limit) is not int or limit < 0:
            reason = "拱门图片缺少文字行数证据"
            break
        is_button = child.component_type in {"CircleButton", "PillButton", "CardButton", "Button"}
        if limit > 0 and not is_button and not item.get("leftAligned"):
            reason = "拱门图片内容未居左"
            break
        lines += limit
    if reason is None:
        if lines <= 0:
            reason = "拱门图片需要可见的日程文字"
        elif lines > policy.get("maxTextLines", 0):
            reason = "拱门图片内容区文字超过两行"
    return reason


def _countdown_reason(policy: dict, task: dict, evidence: dict,
                      root: ComponentRow, by_id: dict, values: dict) -> str | None:
    state = _compact_visible_state(_subtree("root", by_id))
    texts = list(state.literals)
    subjects = set()
    for path in state.paths:
        value = values.get(path)
        if isinstance(value, str):
            texts.append(value)
        parent, _, field_name = path.rpartition("/")
        if field_name == "countdownDays":
            subjects.add(parent)
    text = " ".join(texts)
    reason: str | None = None
    if not state.paths or any(not path.startswith("/data/countdown/") for path in state.paths):
        reason = "秋色图片需要真实倒计时且不能混入其它业务"
    elif re.search(r"运动|马拉松|跑步|训练|赛事|比赛|\b(?:marathon|running|sports?|workout|race)\b",
                   text + " " + task.get("userQuery", ""), re.I):
        reason = "秋色图片不用于运动或马拉松倒计时"
    elif root.props.get("layout") == policy.get("dualLayout"):
        reason = _dual_countdown_reason(policy, evidence, root, by_id)
    elif len(subjects) != 1:
        reason = "秋色单倒计时图片要求一个真实倒计时"
    elif re.search(r"生日|考试|纪念|约会|约饭|聚餐|旅行|出游|出行|出差|婚礼|面试|会议|开会|"
                   r"演唱会|音乐会|\b(?:birthday|exam|anniversary|meeting|wedding|trip)\b",
                   text, re.I):
        reason = "其它单倒计时不能仅因日期含节假日而使用秋色图片"
    elif not re.search(r"节|假期|假日|放假|休假|寒假|暑假|年假|调休|元旦|新年|中秋|国庆|"
                       r"清明|端午|重阳|除夕|跨年|周末|周日|周天|星期日|星期天|"
                       r"holiday|vacation|festival|weekend|sunday|christmas|new year", text, re.I):
        reason = "秋色单倒计时仅用于可见的假期或节日内容"
    return reason


def _dual_countdown_reason(policy: dict, evidence: dict,
                           root: ComponentRow, by_id: dict) -> str | None:
    reason: str | None = None
    if root.props.get("layout") != policy.get("dualLayout") or len(root.children) != 2:
        reason = "双倒计时图片需要上下两个信息背板"
    subjects = set()
    for identity in root.children:
        if reason is not None:
            break
        panel = by_id.get(identity)
        if panel is None or panel.component_type != "InfoBlock":
            reason = "双倒计时图片需要两个InfoBlock背板"
            break
        if identity not in evidence.get("panelIds", []):
            reason = "双倒计时图片缺少可见信息背板"
            break
        state = _compact_visible_state(_subtree(identity, by_id))
        if not state.paths or any(not path.startswith("/data/countdown/") for path in state.paths):
            reason = "每个背板必须展示真实倒计时且不能混入其它业务"
            break
        entries = set()
        for path in state.paths:
            parent, _, field_name = path.rpartition("/")
            if field_name == "countdownDays":
                entries.add(parent)
        if len(entries) != 1:
            reason = "每个背板必须展示一个倒计时天数"
            break
        subjects.update(entries)
    if reason is None and len(subjects) != 2:
        reason = "两个背板必须对应不同倒计时"
    return reason


def _calendar_text_reason(task: dict, evidence: dict,
                          root: ComponentRow, by_id: dict) -> str | None:
    data = task.get("dataModelSchema", {}).get("data", {})
    rows = _subtree("root", by_id)
    header = by_id.get(root.children[0]) if root.children else None
    reason: str | None = None
    if not isinstance(data, dict) or set(data) != {"calendar"}:
        reason = "纯文字会议图片仅用于日程会议单业务"
    elif not _business_paths_match(_compact_visible_state(rows).paths, "calendar"):
        reason = "纯文字会议图片需要真实日程内容且不能混入其它业务"
    elif header is None or header.component_type != "SingleLineTitle":
        reason = "纯文字会议图片需要可识别的顶部标题与内容区"
    elif _has_independent_control(rows, evidence):
        reason = "纯文字会议图片不允许按钮或独立点击控件"
    else:
        body = []
        for identity in root.children[1:]:
            body.extend(_subtree(identity, by_id))
        if not _business_paths_match(_compact_visible_state(body).paths, "calendar"):
            reason = "纯文字会议图片内容区需要真实日程文字"
        ancestors = evidence.get("nonTextAncestors", {})
        for identity in evidence.get("nonTextIds", []):
            if header.component_id not in ancestors.get(identity, []):
                reason = "纯文字会议图片仅允许标题装饰图标，内容区必须纯文字"
                break
    return reason


def _has_independent_control(rows: list[ComponentRow], evidence: dict) -> bool:
    if evidence.get("buttonIds"):
        return True
    for row in rows:
        if row.component_type in {"PillButton", "CircleButton", "CardButton", "Button"}:
            return True
        if row.component_id != "root" and row.props.get("onClick"):
            return True
    return False


def _sleep_capsule_reason(policy: dict, task: dict, by_id: dict) -> str | None:
    rows = _subtree("root", by_id)
    state = _compact_visible_state(rows)
    reason: str | None = None
    if expansion_business(task) != "sleep" or not _business_paths_match(state.paths, "sleep"):
        reason = "银河图片仅用于真实睡眠单业务"
    else:
        has_capsule = False
        for row in rows:
            if row.component_type == policy.get("requiredComponent") and row.props.get("onClick"):
                has_capsule = True
        if not has_capsule:
            reason = "银河睡眠图片必须带可点击胶囊按钮"
    return reason


def _music_reason(policy: dict, evidence: dict, root: ComponentRow, by_id: dict) -> str | None:
    rows = _subtree("root", by_id)
    state = _compact_visible_state(rows)
    reason: str | None = None
    if state.paths:
        if any(not path.startswith("/data/earphone/") for path in state.paths):
            reason = "音乐图片仅用于耳机单业务或纯音乐入口"
    elif not _only_music_actions(rows):
        reason = "音乐图片需要真实耳机内容或音乐跳转动作"
    if reason is None:
        button_count = _clickable_button_count(rows)
        if policy.get("kind") == "music-dual-buttons-square":
            if button_count != policy.get("buttonCount"):
                reason = "节拍器图片要求恰好两个可点击按钮"
        elif button_count == policy.get("excludedButtonCount"):
            reason = "两个按钮的耳机音乐场景使用节拍器图片"
        else:
            lines = _content_lines(policy, evidence, root, by_id)
            if lines is None:
                reason = "无法确认耳机音乐卡片的内容区文字行数上界"
            elif lines <= 0 or lines > policy.get("maxTextLines", 0):
                reason = "小提琴图片要求内容区1至4行文字"
    return reason


def _clickable_button_count(rows: list[ComponentRow]) -> int:
    count = 0
    for row in rows:
        if row.component_type not in {"PillButton", "CircleButton", "CardButton", "Button"}:
            continue
        if row.props.get("onClick"):
            count += 1
    return count


def _battery_reason(policy: dict, evidence: dict,
                    root: ComponentRow, by_id: dict) -> str | None:
    rows = _subtree("root", by_id)
    state = _compact_visible_state(rows)
    reason: str | None = None
    if not any(path.startswith("/data/phoneBattery/") for path in state.paths):
        reason = "电量图片需要实际展示手机电量相关数据"
    elif policy.get("allowRingProgress") is False and _has_ring_progress(rows):
        reason = "方版电量图片不允许环状进度条"
    elif policy.get("kind") == "battery-wide":
        reason = _wide_battery_reason(policy, evidence, root, by_id)
    else:
        lines = _content_lines(policy, evidence, root, by_id)
        if lines is None:
            reason = "无法确认电量卡片的内容区文字行数上界"
        elif lines <= 0 or lines > policy.get("maxTextLines", 0):
            reason = "方版电量图片要求内容区1至3行文字"
    return reason


def _wide_battery_reason(policy: dict, evidence: dict,
                         root: ComponentRow, by_id: dict) -> str | None:
    main = by_id.get(root.children[0]) if root.children else None
    reason: str | None = None
    if main is None or main.component_type != "Region":
        reason = "宽版电量图片需要左侧主业务区域"
    else:
        primary_index = 0 if main.props.get("variant") == "center" else 1
        if len(main.children) <= primary_index:
            reason = "宽版电量图片缺少左侧主焦点"
        else:
            primary = _compact_visible_state(_subtree(main.children[primary_index], by_id))
            whole = _compact_visible_state(_subtree(main.component_id, by_id))
            if not primary.paths:
                reason = "宽版电量图片要求左侧主焦点实际展示电量"
            elif any(not path.startswith("/data/phoneBattery/") for path in whole.paths):
                reason = "宽版电量图片左侧主业务必须为电量"
            else:
                lines = _content_lines(policy, evidence, main, by_id)
                if lines is None:
                    reason = "无法确认左侧电量正文行数"
                elif lines <= 0 or lines > policy.get("maxTextLines", 0):
                    reason = "宽版电量图片左侧正文最多3行"
    return reason


def _has_ring_progress(rows: list[ComponentRow]) -> bool:
    for row in rows:
        if row.component_type in {"ProgressCircle", "ProgressCircleSingle"}:
            return True
        if row.component_type == "Progress" and row.props.get("type") == "ring":
            return True
        visual = row.props.get("visual")
        if row.component_type == "InfoBlock" and isinstance(visual, dict):
            if visual.get("type") == "progressCircle":
                return True
    return False


def _content_lines(policy: dict, evidence: dict,
                   root: ComponentRow, by_id: dict) -> int | None:
    flow = evidence.get("textFlow", {})
    lines = flow.get(root.component_id, {}).get("maxLines")
    result: int | None = None
    if type(lines) is int and lines > 0:
        result = lines
        header = by_id.get(root.children[0]) if root.children else None
        exclude_title = not policy.get("includeTitle", True) and header is not None
        if exclude_title and header.component_type == "SingleLineTitle":
            title_lines = flow.get(header.component_id, {}).get("maxLines")
            if type(title_lines) is not int or title_lines <= 0:
                result = None
            else:
                result -= title_lines
    return result


def _only_music_actions(rows: list[ComponentRow]) -> bool:
    found = False
    for row in rows:
        for action in row.props.get("onClick", []):
            if not isinstance(action, dict):
                return False
            arguments = action.get("args", {})
            if not isinstance(arguments, dict) or action.get("call") != "clickToDeeplink":
                return False
            if arguments.get("intentName") != "Music":
                return False
            found = True
    return found
