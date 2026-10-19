"""按现有协议与生成契约判定卡片尺寸（2x2／2x4），不引入新尺寸。

依据：`docs/云侧方案设计.md` 与 `skills/harmony-card-design-generation/references/
design/layout-system.md` 只承认 2x2（150×150vp）与 2x4（300×150vp）两种尺寸，
请求 1x2／4x4 等一律不生成。Design Compact 布局名以 `S-` 前缀表示 2x2、`W-` 前缀
表示 2x4；`CardButton`、`TextBlock` 只能出现在 2x4。截图宽高比按同口径判定。

判定是确定性纯计算：声明值优先，缺省时使用判定值；声明与判定冲突时保留声明值并
把冲突交给上层告警，不静默纠正。
"""

from __future__ import annotations

import io
import re
from typing import Any

SIZES = ("2x2", "2x4")
_DEFAULT_SIZE = "2x2"

_LAYOUT_TOKEN = re.compile(r'"(?:layout|Layout)"\s*:\s*"(S|W)-([A-Za-z0-9-]*)"')
_TWO_WIDE_ONLY = ("CardButton", "TextBlock")
_ROOT_NUMERIC = re.compile(
    r'"id"\s*:\s*"root"[^{]*?"width"\s*:\s*(\d+(?:\.\d+)?)[^{}]*?"height"\s*:\s*'
    r"(\d+(?:\.\d+)?)",
    re.IGNORECASE | re.DOTALL,
)
_MIN_WIDE_WIDTH = 260.0
_MAX_SQUARE_EDGE = 200.0


def normalize(raw: Any) -> str:
    """把任意来源的尺寸归一为 2x2／2x4，无法确认返回空串。"""
    text = str(raw or "").strip().lower().replace(" ", "").replace("*", "x").replace("×", "x")
    if not text:
        return ""
    if text in {"2x2", "2*2"}:
        return "2x2"
    if text in {"2x4", "4x2", "2*4", "4*2"}:
        return "2x4"
    return ""


def _layout_evidence(text: str) -> tuple[str, str]:
    tokens = {match.group(1) for match in _LAYOUT_TOKEN.finditer(str(text or ""))}
    if tokens == {"S"}:
        return "2x2", "布局名以 S- 前缀（Design Compact 2x2 系列）"
    if tokens == {"W"}:
        return "2x4", "布局名以 W- 前缀（Design Compact 2x4 系列）"
    if len(tokens) > 1:
        return "", "同一份 DSL 同时出现 S- 与 W- 布局名，布局证据冲突"
    return "", ""


def _component_evidence(text: str) -> tuple[str, str]:
    for name in _TWO_WIDE_ONLY:
        if re.search(r'"component"\s*:\s*"' + re.escape(name) + r'"', str(text or "")):
            return "2x4", f"{name} 仅允许出现在 2x4"
    return "", ""


def _root_geometry(text: str) -> tuple[str, str]:
    match = _ROOT_NUMERIC.search(str(text or ""))
    if match is None:
        return "", ""
    width, height = float(match.group(1)), float(match.group(2))
    if width >= _MIN_WIDE_WIDTH:
        return "2x4", f"root 宽 {width:g}vp 属于 2x4 画布"
    if 0 < width <= _MAX_SQUARE_EDGE and 0 < height <= _MAX_SQUARE_EDGE:
        return "2x2", f"root 尺寸 {width:g}×{height:g}vp 属于 2x2 画布"
    return "", ""


def derive_from_genui(text: str) -> tuple[str, str]:
    """从 DSL／GenUI 文本判定尺寸；证据冲突或不足时返回空串并说明原因。"""
    candidates = []
    for probe in (_layout_evidence, _component_evidence, _root_geometry):
        size, reason = probe(text)
        if size:
            candidates.append((size, reason))
    distinct = {size for size, _ in candidates}
    if len(distinct) > 1:
        return "", "尺寸证据冲突：" + "；".join(f"{s}（{r}）" for s, r in candidates)
    if candidates:
        return candidates[0]
    if not str(text or "").strip():
        return "", "DSL 为空，无法判定尺寸"
    return "", "DSL 中没有可用的尺寸证据"


def derive_from_image(raw: bytes) -> tuple[str, str]:
    """按截图宽高比判定；方形视为 2x2，明显横版视为 2x4。"""
    try:
        from PIL import Image

        with Image.open(io.BytesIO(raw)) as picture:
            width, height = picture.size
    except Exception:  # noqa: BLE001 - 判定失败只是退回人工声明
        return "", "截图无法解析，跳过尺寸判定"
    if not width or not height:
        return "", "截图尺寸非法，跳过尺寸判定"
    ratio = width / height
    if ratio >= 1.5:
        return "2x4", f"截图宽高比 {ratio:.2f}，按 2x4 横版判定"
    if 0.75 <= ratio <= 1.33:
        return "2x2", f"截图宽高比 {ratio:.2f}，按 2x2 方版判定"
    return "", f"截图宽高比 {ratio:.2f} 不属于 2x2／2x4 的合理范围"


def judge(
    declared: Any,
    genui: str = "",
    image: bytes | None = None,
    default_when_unknown: str = _DEFAULT_SIZE,
) -> dict[str, Any]:
    """给出最终尺寸与其来源，声明值优先，冲突只记录不纠正。"""
    declared_size = normalize(declared)
    from_dsl, dsl_reason = derive_from_genui(genui)
    from_image, image_reason = (
        derive_from_image(image) if image else ("", "未提供截图，跳过截图判定")
    )
    evidence: list[str] = []
    if from_dsl:
        evidence.append(f"DSL：{from_dsl}（{dsl_reason}）")
    if from_image:
        evidence.append(f"截图：{from_image}（{image_reason}）")
    derived_candidates = {size for size in (from_dsl, from_image) if size}
    derived = derived_candidates.pop() if len(derived_candidates) == 1 else ""
    if len(derived_candidates) > 1:
        derived = ""
        evidence.append("DSL 判定与截图判定不一致")

    if declared_size:
        warning = ""
        if derived and derived != declared_size:
            warning = f"声明尺寸 {declared_size} 与判定结果 {derived} 不一致，已保留声明值"
        elif not derived and (from_dsl or from_image):
            warning = "尺寸证据冲突：" + "；".join(evidence)
        return {
            "size": declared_size, "source": "declared", "derived": derived,
            "declared": declared_size, "warning": warning, "evidence": evidence,
        }
    if derived:
        return {
            "size": derived, "source": "derived", "derived": derived, "declared": "",
            "warning": "", "evidence": evidence,
        }
    fallback = normalize(default_when_unknown)
    warning = "无法判定尺寸"
    if evidence:
        warning = "无法判定尺寸：" + "；".join(evidence)
    if fallback:
        warning += f"，按契约缺省取 {fallback}"
        return {
            "size": fallback, "source": "fallback", "derived": "", "declared": "",
            "warning": warning, "evidence": evidence,
        }
    return {
        "size": "", "source": "unknown", "derived": "", "declared": "",
        "warning": warning, "evidence": evidence,
    }
