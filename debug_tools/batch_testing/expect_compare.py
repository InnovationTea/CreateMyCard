"""按「尺寸 + 数据 + 动作 + 图标」指纹自动匹配期望输出与真实输出。

期望侧来自 ``quality_import`` 导入的 ``purpose=expect`` 批次（DSL＋可选截图与显式数据/动作）；
实际侧有三种来源，全部用同一套匹配规则：
批跑运行的最终 attempt genui、``quality_import`` 导入的 ``purpose=actual`` 批次（两者都走
``compare``，按 runId 区分），以及浏览器会话里端到端／接口调试拿到的真实输出
（``compare_live``，由页面提交 query 与 genui DSL，不要求先跑批）。
两侧指纹用同一提取逻辑，保证口径一致。
匹配是确定性纯函数计算，不依赖模型；显式上传的数据/动作 token 优先作为需求项。
导入时附带 CardSpec 且其中含有数据绑定、事件或资产时，对应维度改用 CardSpec 指纹，缺失维度回退 DSL。

数据、动作、图标三个维度可分别启用（默认全部启用），启用的维度是**筛选条件**而不是评分：
实际输出必须包含期望侧在该维度下的全部数据、动作与图标才算命中，任一缺失都不匹配。
尺寸仍是已匹配的硬门槛。同一实际输出可以同时匹配多个期望样本（多对一），页面按实际样本分组展示。
中文标签只用于展示，由 ``capability_labels`` 从能力声明提取，不参与匹配计算。

动作识别按**位置**判定，而不是按 `{"call","args"}` 形状：协议里同一形状出现在属性值位置
是 FunctionCall 绑定（值函数 `formatString`/`formatNumber`/`formatDate`/`pluralize`/`size`），
出现在事件槽才是动作。卡片子集只开放 `onClick` 一个事件类型，因此只有 `onClick` 数组里的
每个 handler（`args` 可省略）计为动作；嵌套在 handler 参数内的 `call` 属于触发时一次性求值，
不再计为动作。依据见 `docs/鸿蒙桌面卡片A2UI协议完整规范.md` §1.2、§3.5、§3.8 与 §4.2.1.3。
"""

from __future__ import annotations

import json
import re
from typing import Any, Protocol
from urllib.parse import urlsplit

from .capability_labels import asset_key, build_labels, declared_asset_keys
from .card_size import derive_from_genui, judge, normalize
from .quality_import import PURPOSE_ACTUAL, PURPOSE_EXPECT, import_purpose

_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_TEMPLATE_PATH = re.compile(r"\$\{\s*(/[A-Za-z0-9_./~+ -]*)", re.IGNORECASE)
_DATA_MODEL_PATH = re.compile(r"\$__dataModel\.([A-Za-z0-9_.$\[\]]+)")
_EXPRESSION = re.compile(r"\{\{(.+?)\}\}", re.DOTALL)
_ACTUAL_STATES = {"success", "degraded", "imported"}
_DIMENSIONS = ("data", "actions", "icons")
_DEFAULT_DIMENSIONS = ("data", "actions", "icons")
_IMAGE_MEDIA = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}

# 卡片子集唯一的事件槽：通用事件仅 onClick，组件私有事件全部排除（规范 §1.2／§4.2.1.3）。
# 属性值位置的 {"call","args"} 一律按 FunctionCall 绑定处理（值函数如 formatString、
# formatNumber、formatDate、pluralize、size），因此不需要维护函数名黑名单。
_EVENT_KEYS = frozenset({"onClick"})
# 规格文件里常见的资产列表字段；值形如 asset.sun_max。
_SPEC_ASSET_KEYS = frozenset({"assets", "assetIds", "candidateAssetIds"})

# 实际侧的另一种来源：浏览器会话里的端到端／接口调试真实输出（不落盘，由页面提交）。
_LIVE_RUN_ID = "session-live"
_LIVE_SOURCE_NAME = "本次会话调试记录"
_LIVE_MAX_ITEMS = 100
_LIVE_MAX_GENUI_BYTES = 2 * 1024 * 1024
_LIVE_MAX_TOTAL_BYTES = 8 * 1024 * 1024


class RunReader(Protocol):
    """runner.get_run / get_sample 的读取接口，测试可用内存实现替换。"""

    def list_runs(self) -> list[dict[str, Any]]: ...

    def get_run(self, run_id: str) -> dict[str, Any]: ...

    def get_sample(self, run_id: str, sample_id: str) -> dict[str, Any]: ...


def _iter_rows(text: str):
    """genui 行：先整篇解析，再退回 JSONL。

    模板文件常是缩进过的 JSON 数组（同一份内容既可以是一行一份 JSONL，
    也可以是整篇数组），只按行解析会一行都读不到，导致识别预览与比对口径不一致。
    """
    whole = text.strip().lstrip("\ufeff")
    if whole:
        try:
            value = json.loads(whole)
        except json.JSONDecodeError:
            value = None
        if isinstance(value, dict):
            yield value
            return
        if isinstance(value, list):
            yield from value
            return
    for line in text.splitlines():
        stripped = line.strip().lstrip("\ufeff")
        if not stripped:
            continue
        try:
            yield json.loads(stripped)
        except json.JSONDecodeError:
            continue


def _static_uri(raw: str) -> str:
    """去掉模板动态段，保留 deeplink 的可比较静态前缀。"""
    text = re.sub(r"\$\{[^}]*\}", "*", raw)
    text = text.replace("{{", "").replace("}}", "")
    text = re.sub(r"[\"']", "", text)
    text = text.split("*", 1)[0]
    text = re.sub(r"\s*\+\s*$", "", text).strip()
    if "://" in text:
        parts = urlsplit(text)
        return f"{parts.scheme}://{parts.netloc}{parts.path}".rstrip("/")
    return text


def _normalize_action(call: str, args: dict[str, Any]) -> str:
    """动作 token = 函数名 + 最可辨认的目标标识；标识缺失时只留函数名。"""
    for key in ("intentName", "abilityName", "bundleName"):
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return f"{call}:{value.strip()}"
    uri = args.get("uri")
    if isinstance(uri, str) and uri.strip():
        static = _static_uri(uri)
        return f"{call}:uri:{static}" if static else call
    return call


def _as_handler(node: Any) -> dict[str, Any] | None:
    """把 onClick 槽位的元素归一为 EventHandler；不是 handler 形态时返回 None。"""
    if isinstance(node, dict):
        call = node.get("call")
        return node if isinstance(call, str) and call.strip() else None
    if (
        isinstance(node, list)
        and len(node) == 2
        and isinstance(node[0], str)
        and node[0].strip()
        and isinstance(node[1], dict)
    ):
        args = node[1]
        if set(args) == {"args"} and isinstance(args.get("args"), dict):
            args = args["args"]
        return {"call": node[0].strip(), "args": args}
    return None


def _normalize_pointer(raw: str) -> str:
    """把 `/a/b` 指针与 `$__dataModel.a.b` 点路径统一到同一种斜杠路径。"""
    text = str(raw).strip()
    if not text:
        return ""
    if not text.startswith("/"):
        text = re.sub(r"\[[^\]]*\]", "/", text).replace(".", "/")
        text = "/" + text
    text = re.sub(r"/{2,}", "/", text).rstrip("/")
    return text if text and text != "/" else ""


def _collect_text(value: str, data: set[str], actions: set[str]) -> None:
    for match in _TEMPLATE_PATH.findall(value):
        pointer = _normalize_pointer(match.rstrip(" /"))
        if pointer:
            data.add(pointer)
    for expression in _EXPRESSION.findall(value):
        for raw in _DATA_MODEL_PATH.findall(expression):
            pointer = _normalize_pointer(raw)
            if pointer:
                data.add(pointer)


def _collect_event(value: Any, data: set[str], actions: set[str]) -> None:
    """事件槽内每个合法 handler 记一次动作，`args` 可以省略。"""
    items = value if isinstance(value, list) else [value]
    for item in items:
        handler = _as_handler(item)
        if handler is None:
            _collect(item, data, actions, False)
            continue
        call = str(handler["call"]).strip()
        args = handler.get("args")
        args = args if isinstance(args, dict) else {}
        actions.add(_normalize_action(call, args))
        # handler 参数是触发时一次性求值：可以引用数据，但其中的 call 不再是动作。
        _collect(args, data, actions, True)


def _collect(node: Any, data: set[str], actions: set[str], in_handler: bool) -> None:
    if isinstance(node, dict):
        handled: set[str] = set()
        call = node.get("call")
        if isinstance(call, str) and call.strip():
            args = node.get("args")
            if isinstance(args, dict):
                _collect(args, data, actions, True)
                handled.add("args")
            handled.add("call")
        path = node.get("path")
        if isinstance(path, str) and path.startswith("/"):
            pointer = _normalize_pointer(path)
            if pointer:
                data.add(pointer)
                handled.add("path")
        for key, value in node.items():
            if key in handled:
                continue
            if key in _EVENT_KEYS and not in_handler:
                _collect_event(value, data, actions)
                continue
            _collect(value, data, actions, in_handler)
    elif isinstance(node, list):
        if (
            len(node) == 2
            and isinstance(node[0], str)
            and isinstance(node[1], str)
            and node[0].startswith("/")
        ):
            pointer = _normalize_pointer(node[0])
            if pointer:
                data.add(pointer)
        for item in node:
            _collect(item, data, actions, in_handler)
    elif isinstance(node, str):
        _collect_text(node, data, actions)


def _add_icon(value: Any, icons: set[str]) -> None:
    """记下能力表声明过的静态图标资源；模板动态绑定的 src 没有固定标识，不纳入指纹。

    未在 ``asset_capabilities.json`` 声明过的资源不算我们要识别的素材（模板私有图片、
    外链图片等），直接忽略：留着它们只会以「需求项」身份让两侧都判缺失。
    能力目录不可读时不过滤，避免把图标维度静默清空。
    """
    if not isinstance(value, str):
        return
    text = value.strip()
    if not text or "${" in text or "{{" in text:
        return
    text = re.split(r"[?#]", text, maxsplit=1)[0].strip()
    if not text:
        return
    declared = declared_asset_keys()
    if declared and asset_key(text) not in declared:
        return
    icons.add(text.lstrip("/"))


def _collect_semantic_icons(props: dict[str, Any], icons: set[str]) -> None:
    """语义组件把图标写在属性里，不生成 ``Image`` 行。

    正式紧凑 DSL 的模型词汇表里没有 ``Image``：标题与按钮写 ``icon``，InfoBlock 写
    ``visual.icon``，NumericRatioStack 写 ``items[].icon``，展开成基础组件由转换器负责。
    只看 ``Image`` 会让合法输出的图标维度恒为空，图标筛选必然误判不匹配。
    """
    _add_icon(props.get("icon"), icons)
    visual = props.get("visual")
    if isinstance(visual, dict):
        _add_icon(visual.get("icon"), icons)
    items = props.get("items")
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                _add_icon(item.get("icon"), icons)


def _collect_icons(node: Any, icons: set[str]) -> None:
    """兼容 A2UI 组件对象、紧凑 DSL 的 ``Image`` 行与语义组件的图标属性。"""
    if isinstance(node, dict):
        if str(node.get("component") or "") == "Image":
            _add_icon(node.get("src"), icons)
        for value in node.values():
            _collect_icons(value, icons)
    elif isinstance(node, list):
        if len(node) >= 2 and isinstance(node[0], str) and node[1] == "Image":
            props = node[2] if len(node) > 2 and isinstance(node[2], dict) else {}
            _add_icon(props.get("src"), icons)
        elif (
            len(node) >= 3
            and isinstance(node[0], str)
            and isinstance(node[1], str)
            and isinstance(node[2], dict)
        ):
            _collect_semantic_icons(node[2], icons)
        for item in node:
            _collect_icons(item, icons)


def _asset_slots(rows: Any) -> dict[str, str]:
    """读 DSL 里 ``updateDataModel`` 登记的素材槽位：``meetingIcon`` → 资源路径。

    模板把素材写成 ``Image.src = {"path": "/asset/meetingIcon"}``，真正的资源在同一条
    ``updateDataModel`` 的 ``asset`` 里登记。槽位名由模板自己起（不同模板可能不同），
    资源文件名才是素材身份，能解析时优先用资源名，与 CardSpec 的 ``asset.icon_meeting`` 对齐。
    """
    slots: dict[str, str] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            value = node.get("asset")
            if isinstance(value, dict):
                for slot, src in value.items():
                    if isinstance(src, str) and src.strip():
                        slots.setdefault(str(slot).strip(), src.strip())
            for item in node.values():
                walk(item)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(rows)
    return slots


def _fingerprint_of_rows(rows: Any) -> dict[str, Any]:
    """对已经解析好的 JSON 行求「数据＋动作＋图标」集合，与文本来源无关。"""
    # 调用方可能直接传 _iter_rows 的生成器，而行要遍历两遍（槽位登记 + 收集）。
    rows = list(rows)
    data: set[str] = set()
    actions: set[str] = set()
    icons: set[str] = set()
    slots = _asset_slots(rows)
    for row in rows:
        _collect(row, data, actions, False)
        _collect_icons(row, icons)
    # `/asset/<槽位>` 是素材而不是业务数据：归到图标维度，数据维度只留真实业务字段。
    for pointer in sorted(item for item in data if item.startswith("/asset/")):
        data.discard(pointer)
        slot = pointer[len("/asset/"):]
        _add_icon(slots.get(slot, slot), icons)
    return {
        "data": sorted(data, key=str.casefold),
        "actions": sorted(actions, key=str.casefold),
        "icons": sorted(icons, key=str.casefold),
    }


def fingerprint(genui: str) -> dict[str, Any]:
    """从 genui 文本提取「数据＋动作＋图标」指纹集合。

    尺寸不进指纹：同一组数据、动作与图标既可以落成 2x2 也可以落成 2x4，
    它是渲染结果属性，不是可比对的内容需求，因此只在两侧作展示。
    """
    return _fingerprint_of_rows(_iter_rows(genui))


def _add_spec_asset(value: Any, icons: set[str]) -> None:
    """规格里的 ``asset.sun_max`` 记为 ``sun_max``，与 DSL 资源文件名对齐。"""
    if not isinstance(value, str):
        return
    text = value.strip()
    if not text:
        return
    if text.startswith("asset."):
        text = text[len("asset."):]
    if text:
        icons.add(text)


def _collect_spec(node: Any, data: set[str], actions: set[str], icons: set[str]) -> None:
    """递归读取 CardSpec／设计计划中可比较的数据、动作与图标字段。"""
    if isinstance(node, dict):
        call = node.get("call")
        if isinstance(call, str) and call.strip():
            args = node.get("args")
            args = args if isinstance(args, dict) else {}
            actions.add(_normalize_action(call.strip(), args))
        for key in ("writeResultTo", "path"):
            value = node.get(key)
            # 只收 DataModel 路径；设计计划里的 /card/title 等模板槽位不是运行时数据。
            if isinstance(value, str) and value.startswith("/data/"):
                pointer = _normalize_pointer(value)
                if pointer:
                    data.add(pointer)
        for key, value in node.items():
            if key in _SPEC_ASSET_KEYS:
                for item in value if isinstance(value, list) else [value]:
                    _add_spec_asset(item, icons)
                continue
            _collect_spec(value, data, actions, icons)
    elif isinstance(node, list):
        for item in node:
            _collect_spec(item, data, actions, icons)
    elif isinstance(node, str):
        _collect_text(node, data, actions)


def fingerprint_from_spec(spec: Any) -> dict[str, list[str]]:
    """从 CardSpec（或包含 cardSpec／设计计划的 JSON）提取数据、动作与图标。

    CardSpec 的 ``dataBindings[].writeResultTo`` 是数据指纹；事件计划里的
    ``handler``／``action`` 是动作指纹；``candidateAssetIds`` 与 Image 的静态
    ``src`` 是图标指纹。某个维度没有可用字段时返回空列表，期望侧会回退到 DSL。
    """
    data: set[str] = set()
    actions: set[str] = set()
    icons: set[str] = set()
    _collect_spec(spec, data, actions, icons)
    # 兼容规格里直接内嵌 Image 组件的情况；非 Image 的 src 不当作图标。
    _collect_icons(spec, icons)
    return {
        "data": sorted(data, key=str.casefold),
        "actions": sorted(actions, key=str.casefold),
        "icons": sorted(icons, key=str.casefold),
    }


# 导入文件的用途只看结构，不看文件名：文件名靠人工整理，``*.json`` 既可能是规格也可能是 DSL。
_SPEC_KEYS = frozenset({
    "dataBindings", "suggestSize", "capabilityId", "writeResultTo",
    "candidateAssetIds", "assets", "imageDomainWhitelist", "interactions", "events",
})
_GENUI_KEYS = frozenset({
    "component", "components", "createSurface", "updateComponents", "updateDataModel",
    "children", "layout", "root", "surfaceId",
})


def _looks_like_spec(value: Any) -> bool:
    """带规格字段且没有任何组件树字段，才认定是 CardSpec／设计计划。"""
    if not isinstance(value, dict):
        return False
    keys = set(value)
    return bool(_SPEC_KEYS & keys) and not (_GENUI_KEYS & keys)


def _json_values(text: str) -> list[Any]:
    """解析导入文本：整篇 JSON 优先（格式化过的规格是多行的），否则按 JSONL 逐行取。"""
    try:
        return [json.loads(text)]
    except (json.JSONDecodeError, ValueError):
        pass
    return list(_iter_rows(text))


def _merged(items: list[dict[str, Any]]) -> dict[str, list[str]]:
    merged: dict[str, set[str]] = {key: set() for key in ("data", "actions", "icons")}
    for item in items:
        for key in merged:
            merged[key].update(str(value) for value in item.get(key) or [])
    return {key: sorted(values, key=str.casefold) for key, values in merged.items()}


def detect_payload(text: str) -> dict[str, Any]:
    """判断导入的内容是 CardSpec 还是 genui DSL，并给出自动提取的数据／动作／图标。

    导入页据此把文件放对位置、把指纹自动填进需求项，避免让人手抄字段名。
    判定与提取都用比对时的同一套口径：CardSpec 走 ``fingerprint_from_spec``，
    DSL 走 ``fingerprint``，尺寸只作展示（不进指纹）。
    """
    # BOM 可能出现在开头（Windows 记事本），行首带空格时也要认出来，否则空文件会被判成 unknown。
    raw = str(text or "").replace("\ufeff", "")
    if not raw.strip():
        return {"kind": "empty", "fingerprint": _merged([]), "size": "", "note": "内容为空"}
    values = _json_values(raw)
    if not values:
        return {
            "kind": "unknown", "fingerprint": _merged([]), "size": "",
            "note": "既不是 JSON／JSONL，也不是可解析的 genui DSL",
        }
    if all(_looks_like_spec(value) for value in values):
        fingerprints = [fingerprint_from_spec(value) for value in values]
        size = next((
            normalize(value.get("suggestSize"))
            for value in values
            if normalize(value.get("suggestSize") or "")
        ), "")
        return {
            "kind": "cardspec", "fingerprint": _merged(fingerprints), "size": size,
            "note": "识别为 CardSpec：含数据绑定／规格字段，导入后填到 cardSpec",
        }
    return {
        "kind": "dsl",
        "fingerprint": _merged([_fingerprint_of_rows(values)]),
        "size": derive_from_genui(raw)[0],
        "note": "识别为 genui DSL：数据、动作与图标按比对用的同一套口径提取",
    }


def normalize_options(options: Any = None) -> dict[str, Any]:
    """校验筛选维度；页面未提交时默认三个维度全部启用。"""
    raw = options if isinstance(options, dict) else {}
    dimensions = raw.get("dimensions")
    if dimensions is None:
        picked = list(_DEFAULT_DIMENSIONS)
    else:
        if not isinstance(dimensions, (list, tuple)):
            raise ValueError("筛选维度必须是数组")
        picked = []
        for item in dimensions:
            name = str(item).strip().lower()
            if name not in _DIMENSIONS:
                raise ValueError("筛选维度只支持数据、动作与图标")
            if name not in picked:
                picked.append(name)
        if not picked:
            raise ValueError("至少启用一个筛选维度")
    return {"dimensions": picked}


def _data_match(left: str, right: str) -> bool:
    a, b = left.rstrip("/"), right.rstrip("/")
    if a.lower() == b.lower():
        return True
    # 路径层级包含视为同一数据项的不同粒度（如 /data/weather 与 /data/weather/current）。
    return b.startswith(a + "/") or a.startswith(b + "/")


def _token_hit(token: str, data_items: list[str], action_items: list[str]) -> bool:
    value = token.strip()
    low = value.lower()
    if not value:
        return True
    if value.startswith("/"):
        return any(_data_match(value, item) for item in data_items)
    if low in {item.lower() for item in action_items} | {item.lower() for item in data_items}:
        return True
    if any(low == item.lower().rsplit("/", 1)[-1] for item in data_items):
        return True
    return any(low in item.lower() or item.lower() in low for item in action_items)


def _coverage(
    requirements: list[str], data_items: list[str], action_items: list[str],
) -> tuple[int, list[str]]:
    covered = 0
    missing: list[str] = []
    for token in requirements:
        if _token_hit(token, data_items, action_items):
            covered += 1
        else:
            missing.append(token)
    return covered, missing


def _diff_side(expected: list[str], actual: list[str], comparator) -> dict[str, list[str]]:
    missing = [item for item in expected if not any(comparator(item, other) for other in actual)]
    extra = [item for item in actual if not any(comparator(other, item) for other in expected)]
    return {"missing": missing, "extra": extra}


def _action_match(left: str, right: str) -> bool:
    a, b = left.strip().lower(), right.strip().lower()
    if a == b:
        return True
    call_a, _, identity_a = a.partition(":")
    call_b, _, identity_b = b.partition(":")
    if call_a != call_b:
        return False
    # 同一动作函数下标识允许粒度差异（如只有 intentName 与 intent+ability 全量）。
    return bool(identity_a and identity_b and (
        identity_a in identity_b or identity_b in identity_a
    ))


def _icon_match(left: str, right: str) -> bool:
    """图标按资源标识比较；忽略目录、扩展名与规格里的 ``asset.`` 前缀。"""
    a, b = asset_key(left), asset_key(right)
    return bool(a and b and a == b)


def _requirements(
    expected_fp: dict[str, Any],
    explicit_data: list[str],
    explicit_actions: list[str],
    explicit_icons: list[str],
    dimensions: list[str],
) -> tuple[list[str], list[str], list[str]]:
    """只取已启用维度的需求项；显式上传的数据/动作/图标优先于 DSL 指纹。"""
    data = (explicit_data or expected_fp["data"]) if "data" in dimensions else []
    actions = (
        explicit_actions or expected_fp["actions"]
    ) if "actions" in dimensions else []
    icons = (
        explicit_icons or expected_fp.get("icons") or []
    ) if "icons" in dimensions else []
    return data, actions, icons


def _icon_coverage(
    requirements: list[str], actual_icons: list[str],
) -> tuple[int, list[str]]:
    covered = 0
    missing: list[str] = []
    for token in requirements:
        if any(_icon_match(token, item) for item in actual_icons):
            covered += 1
        else:
            missing.append(token)
    return covered, missing


def match_pair(
    expected_fp: dict[str, Any],
    actual_fp: dict[str, Any],
    explicit_data: list[str],
    explicit_actions: list[str],
    dimensions: list[str] | None = None,
    explicit_icons: list[str] | None = None,
) -> dict[str, Any]:
    """按启用的维度筛选一个期望/实际组合。

    只有数据、动作与图标的需求项全部命中才返回 ``matched``；任一需求项缺失返回 ``none``；
    期望侧本来就没有需求项返回 ``no-fingerprint``。尺寸不参与判定，也不计算权重、
    覆盖率或综合分——同一组内容在 2x2 与 2x4 上都成立。
    """
    enabled = list(dimensions) if dimensions is not None else list(_DEFAULT_DIMENSIONS)
    requirements_data, requirements_actions, requirements_icons = _requirements(
        expected_fp, explicit_data, explicit_actions, list(explicit_icons or []), enabled
    )
    _, data_missing = _coverage(
        requirements_data, actual_fp["data"], actual_fp["actions"]
    )
    _, action_missing = _coverage(
        requirements_actions, actual_fp["data"], actual_fp["actions"]
    )
    _, icon_missing = _icon_coverage(
        requirements_icons, actual_fp.get("icons") or []
    )
    has_requirements = bool(requirements_data or requirements_actions or requirements_icons)
    missing = bool(data_missing or action_missing or icon_missing)
    if not has_requirements:
        tier = "no-fingerprint"
    elif missing:
        tier = "none"
    else:
        tier = "matched"
    return {
        "tier": tier,
        "missingData": data_missing,
        "missingActions": action_missing,
        "missingIcons": icon_missing,
    }


def _final_genui(detail: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    """取最终 genui、它所在的 attempt 名，以及导入批次附带的 input 元数据。

    导入的样本落在 ``input/`` 里（attempt 名为 ``input``），批跑样本落在 ``attempt_*/``；
    两侧都取最后一个可用的 attempt，因此读法完全一致。

    判据是「有 genui 或带 input 元数据」：只导入 ID＋截图时 ``input/genui.jsonl`` 是空的，
    若只按 genui 非空筛选，这条样本连 input.json 里的截图与显式期望项都会一起丢掉。
    """
    attempts = [
        item for item in detail.get("attempts", [])
        if isinstance(item, dict) and (item.get("genui") or item.get("input"))
    ]
    if not attempts:
        return "", "", {}
    chosen = attempts[-1]
    input_meta = chosen.get("input")
    return (
        str(chosen.get("genui", "")),
        str(chosen.get("name", "")),
        input_meta if isinstance(input_meta, dict) else {},
    )


def _sample_list(summary: dict[str, Any]) -> list[dict[str, Any]]:
    samples = summary.get("samples")
    return [item for item in samples if isinstance(item, dict)] if isinstance(samples, list) else []


def _binding_items(expected: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    """期望侧声明的三个「强绑定」项：数据分类、数据、动作。"""
    category = str(expected.get("category") or "").strip()
    data = list(dict.fromkeys([
        *(expected["fingerprint"].get("data") or []),
        *(expected.get("explicit", {}).get("data") or []),
    ]))
    actions = list(dict.fromkeys([
        *(expected["fingerprint"].get("actions") or []),
        *(expected.get("explicit", {}).get("actions") or []),
    ]))
    return category, data, actions


def _strong_binding(expected: dict[str, Any], actual: dict[str, Any]) -> bool:
    """数据分类、数据、动作是否构成强绑定。

    期望声明的每一项都要在实际里成立：分类相等（双方都有分类时）、期望的数据与动作都被
    实际指纹包含。三项全空的期望不算强绑定——否则任何一张实际卡片都会「命中」，
    又回到无关卡片被硬配的老问题。
    """
    category, data, actions = _binding_items(expected)
    if not (category or data or actions):
        return False
    if category and category != str(actual.get("category") or "").strip():
        return False
    actual_fp = actual["fingerprint"]
    for requirement in (data, actions):
        if requirement and _coverage(
            requirement, actual_fp["data"], actual_fp["actions"]
        )[1]:
            return False
    return True


def _same_case(expected: dict[str, Any], actual: dict[str, Any]) -> bool:
    """同一条用例才可比。

    判据三条，满足其一即可：
    1. 样本 ID 同名——ID 只是标识（导入可留空按内容哈希生成），但它仍是明确的同名信号；
    2. Query 完全相同（非空）；
    3. 「数据分类＋数据＋动作」强绑定全部成立——这才是期望与真实输出之间的强绑定条件。
    """
    if str(expected["sampleId"]).casefold() == str(actual["sampleId"]).casefold():
        return True
    query = str(expected.get("query") or "").strip()
    if query and query == str(actual.get("query") or "").strip():
        return True
    return _strong_binding(expected, actual)


def expectation_runs(reader: RunReader) -> list[dict[str, Any]]:
    """列出全部期望导入批次，新的在前；对比与画廊共用同一份批次口径。

    导入的「实际输出」批次（``purpose=actual``）不属于期望池，否则它会自己和自己配对。
    """
    runs = [
        run for run in reader.list_runs()
        if isinstance(run, dict) and import_purpose(run) == PURPOSE_EXPECT
    ]
    # 修改过的批次（updatedAt）优先于按导入时间排序，否则「二次修改」不会体现在期望池里。
    return sorted(
        runs,
        key=lambda item: str(item.get("updatedAt") or item.get("startedAt", "")),
        reverse=True,
    )


def _expected_side(
    reader: RunReader, import_run_id: str,
) -> tuple[str, str, list[dict[str, Any]], list[str]]:
    """取期望侧：指定批次用指定批次，没指定就把全部已导入的期望汇成一池。"""
    chosen = str(import_run_id or "").strip()
    if chosen:
        if not _ID_PATTERN.fullmatch(chosen):
            raise KeyError(f"非法批次标识: {chosen}")
        summary = reader.get_run(chosen)
        if import_purpose(summary) != PURPOSE_EXPECT:
            raise ValueError(
                "指定的批次必须是导入的期望输出批次；导入的实际输出请在「实际来源」里选择"
            )
        items, warnings = _expected_items(reader, chosen, summary)
        return chosen, str(summary.get("name") or chosen), items, warnings
    runs = expectation_runs(reader)
    if not runs:
        raise ValueError("还没有导入任何期望输出：先在「导入期望输出」上传 DSL＋截图＋Query")
    items, warnings = _pooled_expected_items(reader, runs)
    if not items:
        raise ValueError("已导入的期望批次里没有可用样本，请重新导入")
    return "", f"已导入的期望输出（{len(items)} 条 / {len(runs)} 个批次）", items, warnings


def _pooled_expected_items(
    reader: RunReader, runs: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """汇总所有导入批次的期望，按样本 ID 去重（新批次优先），不再要求用户挑批次。"""
    items: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for summary in runs:
        run_id = str(summary.get("runId") or "")
        rows, notes = _expected_items(reader, run_id, summary)
        warnings.extend(notes)
        for item in rows:
            key = str(item["sampleId"]).casefold()
            if key in seen:
                continue
            seen.add(key)
            items.append(item)
    return items, warnings


def _expected_items(
    reader: RunReader, import_run_id: str, import_summary: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    """读取期望批次样本并生成指纹项；导入阶段判定的尺寸沿用其来源标签。"""
    expected_items: list[dict[str, Any]] = []
    warnings: list[str] = []
    for meta in _sample_list(import_summary):
        sample_id = str(meta.get("id", ""))
        detail = reader.get_sample(import_run_id, sample_id)
        genui, attempt_name, input_meta = _final_genui(detail)
        fp = fingerprint(genui)
        # 导入时附带的 CardSpec 是显式规格：命中的维度以它为准，缺失维度回退 DSL。
        spec_fp = fingerprint_from_spec(input_meta.get("cardSpec") or {})
        if any(spec_fp.values()):
            fp = {
                "data": spec_fp["data"] or fp["data"],
                "actions": spec_fp["actions"] or fp["actions"],
                "icons": spec_fp["icons"] or fp["icons"],
            }
        explicit_actions = list(dict.fromkeys(
            [str(x) for x in (input_meta.get("expectedActions") or [])]
            + [str(x) for x in (input_meta.get("expectedIntents") or [])]
        ))
        explicit_data = [str(x) for x in (input_meta.get("expectedData") or [])]
        explicit_icons = [str(x) for x in (input_meta.get("expectedIcons") or [])]
        size_verdict = judge(
            meta.get("size") or input_meta.get("size") or "",
            genui,
            default_when_unknown="",
        )
        # 导入判定出的尺寸回读后形状上等同声明值；沿用导入时的来源标签，
        # 界面才能区分「导入时判定」与「人工声明」。
        recorded = str(meta.get("sizeSource") or input_meta.get("sizeSource") or "")
        declared = str(meta.get("size") or input_meta.get("size") or "")
        if recorded in {"derived", "fallback"} and declared == size_verdict["size"]:
            size_verdict = {**size_verdict, "source": recorded}
        if size_verdict["warning"]:
            warnings.append(f"期望样本 {sample_id}：{size_verdict['warning']}")
        expected_items.append({
            "sampleId": sample_id,
            "title": meta.get("title") or sample_id,
            "query": meta.get("query") or input_meta.get("query") or "",
            "size": size_verdict["size"],
            "sizeSource": size_verdict["source"],
            "sizeDerived": size_verdict["derived"],
            "attempt": attempt_name,
            "genui": genui,
            "fingerprint": fp,
            "explicit": {
                "data": explicit_data, "actions": explicit_actions,
                "icons": explicit_icons,
            },
            "category": str(
                meta.get("category") or input_meta.get("category") or ""
            ).strip(),
            "imageUrl": (
                f"/debug/expect/runs/{import_run_id}/samples/{sample_id}/input-image"
                if input_meta.get("imageFile") else None
            ),
        })
    return expected_items, warnings


def _actual_items(
    reader: RunReader, run_id: str, actual_summary: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    """读取实际侧样本；只纳入 success／degraded／imported 且有 genui 的条目。

    批跑运行与导入的实际输出批次共用这一套读法：导入样本的 status 是 ``imported``，
    genui 与截图在 ``input/`` 下，因此同样要回读 input 元数据把参考截图带进页面。
    """
    actual_items: list[dict[str, Any]] = []
    warnings: list[str] = []
    for meta in _sample_list(actual_summary):
        if str(meta.get("status", "")) not in _ACTUAL_STATES:
            continue
        sample_id = str(meta.get("id", ""))
        detail = reader.get_sample(run_id, sample_id)
        genui, attempt_name, input_meta = _final_genui(detail)
        if not genui:
            warnings.append(f"实际样本 {sample_id} 没有可解析的 genui，已跳过")
            continue
        fp = fingerprint(genui)
        size_verdict = judge(meta.get("size") or "", genui, default_when_unknown="")
        if size_verdict["warning"]:
            warnings.append(f"实际样本 {sample_id}：{size_verdict['warning']}")
        actual_items.append({
            "sampleId": sample_id,
            "title": meta.get("title") or sample_id,
            "query": str(meta.get("query") or input_meta.get("query") or ""),
            "size": size_verdict["size"],
            "sizeSource": size_verdict["source"],
            "sizeDerived": size_verdict["derived"],
            "status": meta.get("status"),
            "attempt": attempt_name,
            "genui": genui,
            "fingerprint": fp,
            "category": str(meta.get("category") or input_meta.get("category") or "").strip(),
            "imageUrl": (
                f"/debug/expect/runs/{run_id}/samples/{sample_id}/input-image"
                if input_meta.get("imageFile") else None
            ),
        })
    return actual_items, warnings


def _public_side(item: dict[str, Any]) -> dict[str, Any]:
    """对外输出一侧样本，附带只用于展示的中文标签。"""
    fp = item["fingerprint"]
    explicit = item.get("explicit") or {}
    public = {key: value for key, value in item.items() if key != "requirements"}
    # 期望侧展示的是显式需求项，标签也必须覆盖这些 token，而不只是自动指纹。
    public["labels"] = build_labels(
        [*(fp.get("data") or []), *(explicit.get("data") or [])],
        [*(fp.get("actions") or []), *(explicit.get("actions") or [])],
        [*(fp.get("icons") or []), *(explicit.get("icons") or [])],
    )
    return public


def _assemble(
    import_run_id: str,
    import_name: str,
    run_id: str,
    run_name: str,
    expected_items: list[dict[str, Any]],
    actual_items: list[dict[str, Any]],
    warnings: list[str],
    options: Any = None,
) -> dict[str, Any]:
    """把两侧指纹项按筛选条件配成对；批跑与调试记录两种来源共用这一套规则。

    **只在同一条用例内配对**：实际样本必须与期望同名，或带完全相同的 Query；
    没有对应实际输出的期望记 ``no-actual``，不拿无关卡片硬凑。
    候选内再按缺失最少挑选，因此多个期望可以落在同一个实际样本上；
    全部筛选条件命中且尺寸一致才会标为已匹配。页面按实际样本分组展示。
    """
    settings = normalize_options(options)
    dimensions = settings["dimensions"]
    used_by: dict[str, list[str]] = {}
    orphan: list[str] = []
    pairs: list[dict[str, Any]] = []
    for expected in expected_items:
        candidates = [item for item in actual_items if _same_case(expected, item)]
        ranked = []
        for actual in candidates:
            result = match_pair(
                expected["fingerprint"], actual["fingerprint"],
                expected["explicit"]["data"], expected["explicit"]["actions"],
                dimensions=dimensions,
                explicit_icons=expected["explicit"].get("icons") or [],
            )
            missing = (
                len(result["missingData"]) + len(result["missingActions"])
                + len(result["missingIcons"])
            )
            same_id = actual["sampleId"].lower() == expected["sampleId"].lower()
            same_query = bool(actual["query"] and actual["query"] == expected["query"])
            # 优先：缺失项最少 → 同 ID → 同 Query。尺寸不参与排序与判定。
            ranked.append((
                missing, not same_id, not same_query, actual, result,
            ))
        ranked.sort(key=lambda item: item[:3])
        chosen = ranked[0][3] if ranked else None
        result = ranked[0][4] if ranked else None
        if chosen is None:
            orphan.append(expected["sampleId"])
            pairs.append({"expected": _public_side(expected), "actual": None,
                          "match": None, "diff": None, "tier": "no-actual"})
            continue
        used_by.setdefault(chosen["sampleId"], []).append(expected["sampleId"])
        diff = {
            "data": _diff_side(
                expected["fingerprint"]["data"], chosen["fingerprint"]["data"], _data_match
            ),
            "actions": _diff_side(
                expected["fingerprint"]["actions"], chosen["fingerprint"]["actions"],
                _action_match,
            ),
            "icons": _diff_side(
                expected["fingerprint"].get("icons") or [],
                chosen["fingerprint"].get("icons") or [], _icon_match,
            ),
        }
        pairs.append({
            "expected": _public_side(expected),
            "actual": _public_side(chosen),
            "match": result,
            "diff": diff,
            "tier": (result or {}).get("tier", "none"),
        })

    shared = [f"{sid} ← {owners}" for sid, owners in used_by.items() if len(owners) > 1]
    if shared:
        warnings.append(
            "多个期望样本对应同一实际样本（多对一）：" + "；".join(shared)
        )
    if orphan:
        warnings.append(
            f"{len(orphan)} 条期望没有同名或同 Query 的实际输出，已标为「没有对应的实际输出」："
            + "，".join(orphan[:10]) + ("…" if len(orphan) > 10 else "")
        )
    matched_ids = set(used_by)
    unmatched_actual = [
        _public_side(item) for item in actual_items if item["sampleId"] not in matched_ids
    ]

    tiers = [pair.get("tier") for pair in pairs]
    categories = sorted({
        str(item.get("category") or "").strip()
        for item in expected_items if str(item.get("category") or "").strip()
    })
    return {
        "importRunId": import_run_id,
        "importName": import_name,
        "runId": run_id,
        "runName": run_name,
        "actualSource": "session" if run_id == _LIVE_RUN_ID else "batch",
        "summary": {
            "expected": len(expected_items),
            "actual": len(actual_items),
            "matched": tiers.count("matched") + tiers.count("no-fingerprint"),
            "none": tiers.count("none") + tiers.count("no-actual"),
        },
        "options": settings,
        "categories": categories,
        "pairs": pairs,
        "unmatchedActual": unmatched_actual,
        "warnings": warnings,
    }


def live_actual_items(actuals: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """校验并指纹化浏览器提交的真实输出（端到端／接口调试拿到的结果）。

    真实输出只存在前端会话里，因此由页面把 query、genui DSL 与可选尺寸提交上来；
    指纹与尺寸判定仍走本模块同一套逻辑，保证与批跑侧口径一致。
    """
    if not isinstance(actuals, list) or not actuals:
        raise ValueError("实际输出为空：请至少勾选一条端到端或接口调试记录")
    if len(actuals) > _LIVE_MAX_ITEMS:
        raise ValueError(f"单次最多对比 {_LIVE_MAX_ITEMS} 条调试记录，请减少勾选")
    items: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[str] = set()
    total_bytes = 0
    for raw in actuals:
        if not isinstance(raw, dict):
            raise ValueError("实际输出必须是对象")
        sample_id = str(raw.get("id") or "").strip()
        if not _ID_PATTERN.fullmatch(sample_id):
            raise ValueError(f"实际输出标识非法：{sample_id or '（空）'}")
        if sample_id.casefold() in seen:
            raise ValueError(f"实际输出标识重复：{sample_id}")
        seen.add(sample_id.casefold())
        genui = str(raw.get("genui") or "")
        if not genui.strip():
            raise ValueError(f"实际输出 {sample_id} 没有 genui DSL，无法参与对比")
        payload_bytes = len(genui.encode("utf-8"))
        if payload_bytes > _LIVE_MAX_GENUI_BYTES:
            raise ValueError(f"实际输出 {sample_id} 的 DSL 超过 2 MiB")
        total_bytes += payload_bytes
        if total_bytes > _LIVE_MAX_TOTAL_BYTES:
            raise ValueError("本次提交的 DSL 合计超过 8 MiB，请减少勾选")
        declared = str(raw.get("size") or "").strip()
        if declared and not normalize(declared):
            raise ValueError(f"实际输出 {sample_id} 声明了 {declared}；只有 2x2 与 2x4")
        verdict = judge(declared, genui, default_when_unknown="")
        if verdict["warning"]:
            warnings.append(f"实际样本 {sample_id}：{verdict['warning']}")
        items.append({
            "sampleId": sample_id,
            "title": str(raw.get("title") or "").strip() or sample_id,
            "query": str(raw.get("query") or "").strip(),
            "size": verdict["size"],
            "sizeSource": verdict["source"],
            "sizeDerived": verdict["derived"],
            "status": str(raw.get("status") or "").strip() or "success",
            "attempt": str(raw.get("attempt") or "").strip() or "调试记录",
            "genui": genui,
            "fingerprint": fingerprint(genui),
        })
    return items, warnings


def compare(
    reader: RunReader, import_run_id: str, run_id: str, options: Any = None,
) -> dict[str, Any]:
    """把期望批次与一次批跑运行或导入的实际输出批次自动配对；每个期望取缺失最少的实际样本。

    ``options`` 只承载筛选维度，与浏览器会话来源共用同一套判定规则。
    ``import_run_id`` 为空时不再要求挑批次，直接用全部已导入的期望。
    """
    if not _ID_PATTERN.fullmatch(run_id):
        raise KeyError(f"非法批次标识: {run_id}")
    chosen_id, chosen_name, expected_items, warnings = _expected_side(reader, import_run_id)
    actual_summary = reader.get_run(run_id)
    if import_purpose(actual_summary) == PURPOSE_EXPECT:
        raise ValueError(
            "右侧批次应是需要对比的批跑运行或导入的实际输出批次，而不是期望导入批次"
        )
    if import_purpose(actual_summary) == PURPOSE_ACTUAL:
        # 导入的实际批次没有 Query 时只能按样本 ID 配对，先提示口径，避免误以为漏配。
        warnings.append(
            f"实际来源是导入批次「{actual_summary.get('name') or run_id}」："
            "没有填 Query 的样本只按样本 ID 与期望配对"
        )
    actual_items, actual_warnings = _actual_items(reader, run_id, actual_summary)
    warnings.extend(actual_warnings)
    if import_run_id == run_id:
        warnings.append("左右选择了同一批次")
    return _assemble(
        chosen_id, chosen_name,
        run_id, actual_summary.get("name") or run_id,
        expected_items, actual_items, warnings, options,
    )


def compare_live(
    reader: RunReader,
    import_run_id: str,
    actuals: Any,
    run_name: str = "",
    options: Any = None,
) -> dict[str, Any]:
    """期望批次直接对比浏览器提交的真实输出；不要求先跑批，匹配规则与批跑侧一致。"""
    settings = normalize_options(options)
    chosen_id, chosen_name, expected_items, warnings = _expected_side(reader, import_run_id)
    actual_items, live_warnings = live_actual_items(actuals)
    warnings.extend(live_warnings)
    return _assemble(
        chosen_id, chosen_name,
        _LIVE_RUN_ID, (run_name or "").strip()[:80] or _LIVE_SOURCE_NAME,
        expected_items, actual_items, warnings, settings,
    )


def input_image_path(output_root, run_id: str, sample_id: str) -> tuple[str, str]:
    """返回导入样本截图的绝对路径与 MIME；仅服务 external-quality 批次的 input 图片。"""
    if not _ID_PATTERN.fullmatch(run_id) or not _ID_PATTERN.fullmatch(sample_id):
        raise KeyError(f"非法标识: {run_id or sample_id}")
    root = output_root.resolve()
    directory = (root / run_id / sample_id / "input").resolve()
    directory.relative_to(root)
    meta_path = directory / "input.json"
    if not meta_path.is_file():
        raise KeyError(sample_id)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("schemaVersion") != "external-quality-input-v1":
        raise KeyError(sample_id)
    name = str(meta.get("imageFile") or "")
    candidate = (directory / name).resolve()
    candidate.relative_to(directory)
    suffix = candidate.suffix.lower()
    if not candidate.is_file() or suffix not in _IMAGE_MEDIA:
        raise KeyError(sample_id)
    return str(candidate), _IMAGE_MEDIA[suffix]
