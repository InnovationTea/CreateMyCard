"""
豆包（Doubao）视觉模型实现，兼容字节跳动火山引擎方舟OpenAI接口
"""
from typing import Dict, Any
import httpx
from .base import BaseAestheticsModel
from ..core.rubric import RUBRIC_DESCRIPTIONS, RUBRIC_SCORE_RULES, OCCLUSION_OVERLAP_CHECK, OCCLUSION_TYPES

class DoubaoAestheticsModel(BaseAestheticsModel):
    def build_prompt(self, image_data_url: str) -> str:
        """构建豆包视觉打分prompt，完全和原有aesthetic-v4的prompt一致，保证得分结果相同"""
        if self.output_mode == "score-only":
            return f"""
你是一个专业的UI视觉设计师，给这张界面截图打分，0-8分，只输出JSON格式的结果，不要任何其他内容：
{{"score": 你的打分结果}}
"""
        # 全量输出的prompt，和原有aesthetic-v4完全一致
        return f"""
你是一个专业的UI/UX视觉评审专家，你需要严格按照给定的6个维度给这张界面截图打分，输出JSON格式的结果。

评分维度和权重：
1. 视觉冲击/原创性 (30%): {RUBRIC_DESCRIPTIONS['visual_impact_originality']}
评分标准：{'; '.join(RUBRIC_SCORE_RULES['visual_impact_originality'])}

2. 构图/层级 (20%): {RUBRIC_DESCRIPTIONS['composition_hierarchy']}
评分标准：{'; '.join(RUBRIC_SCORE_RULES['composition_hierarchy'])}

3. 字体排版 (15%): {RUBRIC_DESCRIPTIONS['typography']}
评分标准：{'; '.join(RUBRIC_SCORE_RULES['typography'])}

4. 颜色/材质 (15%): {RUBRIC_DESCRIPTIONS['color_material']}
评分标准：{'; '.join(RUBRIC_SCORE_RULES['color_material'])}

5. 细节/完成度 (15%): {RUBRIC_DESCRIPTIONS['detail_finish']}
评分标准：{'; '.join(RUBRIC_SCORE_RULES['detail_finish'])}

6. 基础可用性 (5%): {RUBRIC_DESCRIPTIONS['basic_usability']}
评分标准：{'; '.join(RUBRIC_SCORE_RULES['basic_usability'])}

遮挡检测要求：
检查界面是否存在以下类型的遮挡问题：{', '.join(OCCLUSION_TYPES)}
如果有遮挡，列出检测到的类型、问题描述、受影响的维度、扣分值。

输出要求：
严格按照JSON格式输出，不要任何其他内容，JSON结构如下：
{{
  "score": 0-8分的最终加权总分,
  "axis_scores": {{
    "visual_impact_originality": 0-8分,
    "composition_hierarchy": 0-8分,
    "typography": 0-8分,
    "color_material": 0-8分,
    "detail_finish": 0-8分,
    "basic_usability": 0-8分
  }},
  "rationale": "100字以内的评分理由",
  "occlusion": {{
    "detected": true/false,
    "types": ["遮挡类型列表"],
    "findings": ["具体问题描述列表"],
    "affected_axes": ["受影响的维度id列表"],
    "score_impact": 扣分值（0-8）
  }}
}}
"""
    
    def call_api(self, prompt: str, image_data_url: str) -> Dict[str, Any]:
        """调用豆包视觉模型API，兼容OpenAI接口格式"""
        if not self.base_url.endswith("/"):
            base_url = f"{self.base_url}/"
        else:
            base_url = self.base_url
        
        # 拼接chat/completions端点，兼容已有路径
        if base_url.endswith("chat/completions"):
            endpoint = base_url
        elif base_url.endswith("/v3/") or base_url.endswith("/v1/"):
            endpoint = f"{base_url}chat/completions"
        else:
            endpoint = f"{base_url}v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_data_url
                            }
                        }
                    ]
                }
            ]
        }
        
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
