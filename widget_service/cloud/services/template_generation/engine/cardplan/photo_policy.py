"""模板图片内容适配，配置与公共事实分析来自现有主题能力。"""

from dataclasses import dataclass, field

from services.post_layout_theme_registry import load_theme_registry


@dataclass(frozen=True)
class PhotoContentFacts:
    """模板定稿内容提取的事实，不包含猜测的宿主像素尺寸。"""

    size: str
    business: str | None
    line_count: int | None
    left_aligned: bool
    centered: bool
    bottom_left: bool
    wide_layout: bool = False
    top_content: dict = field(default_factory=dict)


def photo_facts_reason(photo: dict, facts: PhotoContentFacts) -> str | None:
    """读取共享配置，裁决模板正文事实；不改变后置主题规则。"""
    rules = load_theme_registry().get("photoEligibility", {})
    policy = photo.get("contentEligibility", {})
    lines = facts.line_count
    wide_subject = facts.size == "2x4" and photo.get("pool") == "photos"
    limit = rules.get("wideMaxTextLines" if wide_subject else "maxTextLines", 0)
    max_lines = min(limit, policy.get("maxTextLines", limit))
    placement = policy.get("placement")
    reason: str | None = None
    if facts.size == "2x4" and not facts.wide_layout:
        reason = "2x4图片需要左主焦点和右侧一个辅助背板或上下两个背板"
    elif facts.size not in {"2x2", "2x4"}:
        reason = "图片只支持2x2和2x4"
    elif (photo.get("pool") != "texturePhotos"
          and facts.business not in policy.get("businesses", [])):
        reason = "图片业务与实际可见的单业务内容不匹配"
    elif type(lines) is not int or lines < 0:
        reason = "无法确认图片正文行数"
    elif lines > max_lines:
        reason = f"图片正文超过{max_lines}行（不含顶部标题和按钮文案）"
    elif photo.get("pool") == "photos" and facts.size == "2x2" and not facts.left_aligned:
        reason = "2x2主体图片要求正文整体居左，不能居中或两端对齐"
    elif placement in {"center", "not-center"} and facts.centered != (placement == "center"):
        reason = "2x2全居中只用同心圆，其余布局只用菱形或斜纹"
    elif placement == "bottom" and not facts.bottom_left:
        reason = "此图片要求主区正文整体居下"
    elif placement == "bottom-left" and not facts.bottom_left:
        reason = "此会议图片要求左侧主区正文全部居左贴底"
    elif placement == "not-bottom-left" and facts.bottom_left:
        reason = "居左贴底会议使用A19，不匹配会议室横图"
    elif placement == "top-left-empty-bottom":
        if lines == 0:
            reason = "蓝天白云需要1至2行正文"
        elif facts.top_content.get("topOnly") is not True:
            reason = "蓝天白云要求正文居左居上且下方留空：" + str(facts.top_content.get("reason"))
    return reason
