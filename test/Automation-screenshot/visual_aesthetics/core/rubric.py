"""
核心审美评分标准和维度定义
100%复用原有aesthetic-v4的评分逻辑，保证得分一致性
"""
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
import json
import re
import base64
import mimetypes
from pathlib import Path

# 评分常量
RUBRIC_VERSION = "aesthetic-static-v1"
AESTHETIC_PROFILE = "aesthetic-v4"
SCORE_MIN = 0.0
SCORE_MAX = 8.0
SCORE_PRECISION = 1

# 6个评分维度和权重（完全和原有一致）
RUBRIC_WEIGHTS = {
    "visual_impact_originality": 0.30,  # 视觉冲击/原创性 30%
    "composition_hierarchy": 0.20,      # 构图/层级 20%
    "typography": 0.15,                 # 字体排版 15%
    "color_material": 0.15,             # 颜色/材质 15%
    "detail_finish": 0.15,              # 细节/完成度 15%
    "basic_usability": 0.05             # 基础可用性 5%
}

# 维度显示名称
RUBRIC_DISPLAY_NAMES = {
    "visual_impact_originality": "视觉冲击/原创性",
    "composition_hierarchy": "构图/层级",
    "typography": "字体排版",
    "color_material": "颜色/材质",
    "detail_finish": "细节/完成度",
    "basic_usability": "基础可用性"
}

# 维度描述
RUBRIC_DESCRIPTIONS = {
    "visual_impact_originality": "评价页面是否有第一眼的视觉记忆点、明确的主题气质和非模板化表达。重点看是否存在强中心视觉、稳定氛围、原创构图、品牌化或话题化视觉表达语言，而不是只依赖常见渐变、圆角卡片、玻璃态、emoji、默认插图或普通组件堆砌。",
    "composition_hierarchy": "评价页面的信息组织、视觉重心、空间节奏和阅读路径。重点看首屏是否有清晰主次关系，核心内容是否被正确突出，导航、内容、操作区是否有稳定分组，而不是所有卡片、标签、颜色和按钮都在抢注意力。",
    "typography": "评价字体选择、字号层级、字重、行高、对齐和文本排版是否形成稳定系统。重点看标题、正文、标签、按钮、数字信息是否有清晰层级，字体是否匹配产品气质，文本是否可读且不拥挤。",
    "color_material": "评价配色、明暗关系、材质质感、光影、边框、阴影和背景处理是否统一且服务主题。重点看颜色是否有优先级，材质是否精致，是否避免廉价渐变、彩虹色堆砌、无意义玻璃态或默认灰白卡片。",
    "detail_finish": "评价整体完成度和细节处理。重点看图标风格统一度、圆角一致性、间距对齐、按钮状态区分、边距留白合理性。低完成度的表现是东拼西凑、元素对齐混乱、圆角大小不一、间距忽大忽小。",
    "basic_usability": "评价静态截图中的基础可读、可识别和可操作性。它不是产品功能评分，只用于防止明显不可读、遮挡、错位、核心结构失败的页面被视觉氛围抬高分。"
}

# 各维度评分标准
RUBRIC_SCORE_RULES = {
    "visual_impact_originality": [
        "0-2分：默认模板、课程demo、普通表单/卡片堆砌，几乎没有视觉记忆点",
        "2-4分：页面完整但常见，主要靠通用渐变、卡片、按钮、图标维持观感，原创性弱",
        "4-6分：有明确主题和一定视觉亮点，整体比模板更完整，但冲击感、原创资产或品牌化仍有限",
        "6-8分：有强中心视觉、稳定氛围、原创表达和高识别度，能明显区别于普通AI生成页面"
    ],
    "composition_hierarchy": [
        "0-2分：布局混乱、层级缺失、核心内容难以定位，或大面积空白/拥挤导致页面像未完成原型",
        "2-4分：基本能读，但主次关系弱，常见卡片网格或dashboard拼凑感明显",
        "4-6分：结构清晰，有较自然的阅读路径和视觉重心，但构图仍偏安全或缺少张力",
        "6-8分：构图成熟，首屏亮点强，内容分组、留白、比例和节奏共同服务主题表达"
    ],
    "typography": [
        "0-2分：系统默认字体痕迹强，字号/字重混乱，文本拥挤、错位、重叠或可读性差",
        "2-4分：字体基本可读，但层级普通，标题、正文、标签缺少精细排版规则",
        "4-6分：字体层级稳定，排版较干净，能支撑页面气质，但缺少更强的字体个性或细节控制",
        "6-8分：字体选择、尺寸、字重、行间距和对齐高度统一，明显增强品牌感和完成度"
    ],
    "color_material": [
        "0-2分：配色随意或极度默认，材质粗糙，颜色之间互相抢注意力或整体像未设计",
        "2-4分：有基础配色但比较常见，主要依赖默认白卡、普通阴影、弱渐变或单色调色块",
        "4-6分：颜色关系稳定，材质和光影有一定完成度，能配合主题但不够精细或独特",
        "6-8分：颜色系统成熟，材质、光影、背景和组件质感统一，形成强烈且克制的视觉氛围"
    ],
    "detail_finish": [
        "0-2分：细节完全缺失，图标/按钮/卡片风格不统一，大小、圆角、间距混乱，像半成品",
        "2-4分：基础元素完整，但细节普通，按钮、卡片、图表、图标和间距仍像快速拼凑",
        "4-6分：多数组件完成度较好，间距和局部样式稳定，但精致程度和资产质量仍有限",
        "6-8分：局部细节高度统一，组件、图标、图表、插图和状态都像完整产品设计系统的一部分"
    ],
    "basic_usability": [
        "0-2分：核心信息不可读，按钮/输入/导航被遮挡或错位，布局严重影响理解",
        "2-4分：基本能理解，但存在明显拥挤、溢出、低对比、遮挡或响应式问题",
        "4-6分：主要内容和操作清晰，只有局部小问题，不明显阻碍静态理解",
        "6-8分：信息清晰、控件可识别、结构稳定，桌面/移动截图中都没有明显基础可用性问题"
    ]
}

# 遮挡检测常量（完全和原有一致）
OCCLUSION_OVERLAP_CHECK = "always_on"
OCCLUSION_TYPES = [
    "text_text",      # 文字和文字重叠
    "text_graphic",   # 文字被图片/图标/图表遮挡
    "control_nav",    # 按钮/输入/导航遮挡核心内容
    "layer_zindex",   # 浮层/卡片/图层顺序问题导致核心内容遮挡
    "clipping_crop"   # 裁剪/溢出/截断导致核心内容不可读
]

# 边界分桶映射（和原有aesthetic-v4逻辑完全一致）
BOUNDARY_BUCKET_SCORES = {
    "[0,10)": 0.4,
    "[10,20)": 1.2,
    "[20,30)": 2.0,
    "[30,40)": 2.8,
    "[40,50)": 3.6,
    "[50,60)": 4.4,
    "[60,70)": 5.2,
    "[70,80)": 6.0,
    "[80,100]": 7.2
}

@dataclass
class AxisScore:
    """单维度得分"""
    axis_id: str
    axis_name: str
    score: float
    weight: float
    weighted_score: float
    description: str = ""

@dataclass
class OcclusionResult:
    """遮挡检测结果"""
    detected: bool = False
    types: List[str] = None
    findings: List[str] = None
    affected_axes: List[str] = None
    score_impact: float = 0.0

@dataclass
class JudgeResult:
    """完整打分结果"""
    qid: str
    sn: str
    image_path: str
    final_score: float
    final_score_100: float  # 0-100分制
    axis_scores: List[AxisScore]
    occlusion: OcclusionResult
    rationale: str = ""
    model: str = ""
    prompt_version: str = AESTHETIC_PROFILE
    elapsed_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    success: bool = True
    error_msg: str = ""

def calculate_weighted_total(axis_scores: List[AxisScore]) -> float:
    """计算加权总分（0-8分制）"""
    total = sum(ax.weighted_score for ax in axis_scores)
    return round(max(SCORE_MIN, min(SCORE_MAX, total)), SCORE_PRECISION)

def score_to_100(score_8: float) -> float:
    """0-8分转0-100分"""
    return round((score_8 / SCORE_MAX) * 100, 1)

def image_to_data_url(image_path: Path) -> str:
    """图片转base64 data url，用于报告嵌入"""
    mime = mimetypes.guess_type(image_path.name)[0] or "image/png"
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{encoded}"

def extract_json_from_model_output(text: str) -> Optional[Dict[str, Any]]:
    """从大模型输出里提取JSON结构，兼容各种格式和markdown包裹"""
    text = text.strip()
    # 移除markdown代码块包裹
    text = re.sub(r'^```(?:json|jsonl)?\s*', '', text, flags=re.I).strip()
    text = re.sub(r'\s*```$', '', text).strip()
    
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # 尝试找第一个{到最后一个}的内容
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end+1])
        except json.JSONDecodeError:
            pass
    
    # 尝试前缀解析
    try:
        decoded, _ = json.JSONDecoder().raw_decode(text)
        if isinstance(decoded, dict):
            return decoded
    except json.JSONDecodeError:
        pass
    
    return None

def redact_secret(text: str) -> str:
    """脱敏密钥，避免日志泄露"""
    text = re.sub(r'sk-[A-Za-z0-9_-]{8,}', 'sk-***REDACTED***', text)
    text = re.sub(r'ark-[A-Za-z0-9_-]{8,}', 'ark-***REDACTED***', text)
    return text
