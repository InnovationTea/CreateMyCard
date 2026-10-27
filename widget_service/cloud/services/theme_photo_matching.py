"""模板与融合共用的纯算法图片裁决；不读取用户原文、不调用模型。"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field

from services.content_business import VisibleBusinesses
from services.post_layout_theme_registry import load_theme_registry, registered_themes
from services.theme_texture_eligibility import texture_business_reason


@dataclass(frozen=True)
class PhotoScopeFacts:
    businesses: VisibleBusinesses
    body_flow: dict = field(default_factory=dict)
    texture_flow: dict = field(default_factory=dict)
    centered: bool = False
    bottom: bool = False
    holiday: bool = False


@dataclass(frozen=True)
class PhotoMatchFacts:
    size: str | None
    scopes: dict[str, PhotoScopeFacts] = field(default_factory=dict)
    top_content: dict = field(default_factory=dict)
    panel_count: int | None = None
    error: str | None = None
    subject_exclusion: str | None = None


def photo_content_reason(photo: dict, facts: PhotoMatchFacts) -> str | None:
    """硬条件逐项裁决；不同生成链路不能通过独立分数抵消不合格条件。"""
    if facts.error:
        return facts.error
    card = facts.scopes.get("card")
    if card is None:
        return "图片缺少定稿根节点"
    policy = photo.get("contentEligibility", {})
    kind = policy.get("kind")
    if kind == "holiday-countdown":
        if facts.size != "2x2" or not card.holiday:
            return "此图片仅用于2x2单业务节假日倒计时，每个展示对象均须属于节假日"
        return None
    if kind == "weather-panels":
        if facts.size != "2x4" or facts.panel_count not in {2, 4}:
            return "冰面图仅用于双大背板或四宫格，不用于主焦点布局"
        if "weather" not in card.businesses.data_businesses:
            return "冰面图要求至少一项实际可见天气业务"
        return None
    if kind != "uniform":
        return "图片缺少已登记准入配置"
    texture = photo.get("pool") == "texturePhotos"
    scope = card
    if facts.size == "2x4" and not texture:
        layout = policy.get("wideLayout", "left-main-dual")
        scope = facts.scopes.get(layout)
        if scope is None:
            return _wide_reason(layout)
    elif facts.size not in {"2x2", "2x4"}:
        return "图片只支持2x2和2x4"
    if texture:
        reason = texture_business_reason(photo, [], businesses=scope.businesses)
        if reason:
            return reason
    else:
        business = scope.businesses.single
        if "holiday" in policy.get("businesses", []):
            business = "holiday" if scope.holiday else None
        if business not in policy.get("businesses", []):
            return "图片业务与实际可见的单业务内容不匹配"
    flow = scope.texture_flow if texture else scope.body_flow
    lines = flow.get("lineCount")
    if type(lines) is not int or lines < 0:
        return "无法确认图片正文行数"
    rules = load_theme_registry().get("photoEligibility", {})
    limit_key = "wideMaxTextLines" if facts.size == "2x4" and not texture else "maxTextLines"
    limit = rules.get(limit_key, 0)
    maximum = min(limit, policy.get("maxTextLines", limit))
    if lines > maximum:
        return f"图片正文超过{maximum}行（不含顶部标题和按钮文案）"
    if not texture and facts.size == "2x2" and flow.get("leftAligned") is not True:
        return "2x2主体图片要求正文整体居左，不能居中或两端对齐"
    return _placement_reason(policy, scope, flow, facts.top_content)


def _wide_reason(layout: str) -> str:
    messages = {
        "main-focus": "2x4图片需要明确主焦点，不支持双大背板或无主次布局",
        "side-focus": "2x4图片需要左右主焦点加另一侧上下双槽，不支持上下或双大背板布局",
    }
    return messages.get(layout, "2x4图片需要左主焦点和右侧上下两个背板")


def _placement_reason(policy: dict, scope: PhotoScopeFacts, flow: dict, top: dict) -> str | None:
    placement = policy.get("placement")
    reason = None
    if placement in {"center", "not-center"}:
        if scope.centered != (placement == "center"):
            reason = "2x2全居中只用同心圆，其余布局只用菱形或斜纹"
    elif placement == "bottom":
        if not scope.bottom or flow.get("lineCount", 0) == 0:
            reason = "此图片要求主区正文整体居下，不能仅辅助内容贴底"
    elif placement in {"bottom-left", "not-bottom-left"}:
        bottom_left = scope.bottom and flow.get("leftAligned") is True
        if placement == "bottom-left" and not bottom_left:
            reason = "此会议图片要求左侧主区正文全部居左贴底"
        elif placement == "not-bottom-left" and bottom_left:
            reason = "居左贴底会议使用A19，不匹配会议室横图"
    elif placement == "top-left-empty-bottom":
        if flow.get("lineCount") == 0:
            reason = "蓝天白云需要1至2行正文"
        elif top.get("topOnly") is not True:
            reason = "蓝天白云要求正文居左居上且下方留空：" + str(top.get("reason"))
    return reason


def photo_reason(photo: dict, facts: PhotoMatchFacts) -> str | None:
    if photo.get("size") != facts.size:
        return "尺寸不匹配"
    if photo.get("pool") not in {"photos", "texturePhotos"}:
        return "图片不在当前主体图或抽象图集"
    if photo.get("contentEligibility", {}).get("kind") not in {
        "uniform", "holiday-countdown", "weather-panels",
    }:
        return "图片缺少统一准入配置"
    reason = photo_content_reason(photo, facts)
    if reason is None and photo.get("pool") != "texturePhotos":
        if photo.get("contentEligibility", {}).get("kind") != "weather-panels":
            reason = facts.subject_exclusion
    return reason


def eligible_photos(
    facts: PhotoMatchFacts, photos: list[dict] | None = None,
) -> tuple[list[dict], dict]:
    """只从公共登记图集发现候选；没有逐图模板白名单或第二份素材清单。"""
    candidates = []
    rejected = {}
    for photo in registered_themes() if photos is None else photos:
        if photo.get("pool") not in {"photos", "texturePhotos"}:
            continue
        reason = photo_reason(photo, facts)
        if reason:
            rejected[photo.get("id")] = reason
        else:
            candidates.append({**photo, "kind": "photo"})
    return candidates, rejected


def select_equivalent_photo(selected: str, candidates: list[dict]) -> tuple[str, dict]:
    """保持既有等概率分配；匹配准入不受模型返回的图片 ID 影响。"""
    photos = [item for item in candidates if item.get("kind") == "photo"]
    available = [item.get("id") for item in photos]
    audit = {}
    if available:
        choices = available
        audit = {"mode": "uniform", "eligible": available, "selected": selected}
        if all(item.get("pool") == "texturePhotos" for item in photos):
            families = []
            for item in photos:
                family = item.get("family")
                if family not in families:
                    families.append(family)
            families.sort()
            if len(families) > 1:
                family = secrets.choice(families)
                choices = [item.get("id") for item in photos if item.get("family") == family]
                audit.update(mode="uniform-family-and-shape", families=families, family=family)
        selected = secrets.choice(choices)
        audit["selected"] = selected
    return selected, audit
