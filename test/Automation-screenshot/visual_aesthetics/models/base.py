"""
模型调用基类
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path
import httpx
import time
import os
from ..core.rubric import JudgeResult, extract_json_from_model_output, redact_secret
from automation.logger import get_logger
from automation.logger import get_logger

class BaseAestheticsModel(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.base_url = config.get("base_url", "")
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "doubao-seed-2-0-lite")
        self.timeout = config.get("timeout", 360)
        self.max_retries = config.get("max_retries", 3)
        self.max_tokens = config.get("max_tokens", 1200)
        self.temperature = config.get("temperature", 0.0)
        self.prompt_version = config.get("prompt_version", "aesthetic-v4")
        self.output_mode = config.get("output_mode", "full")  # full/score-only
        self._log = get_logger("aesthetics", sn="")
        self.logger = get_logger("aesthetics", sn="")
        
    @abstractmethod
    def build_prompt(self, image_data_url: str) -> str:
        """构建打分prompt"""
        pass
    
    @abstractmethod
    def call_api(self, prompt: str, image_data_url: str) -> Dict[str, Any]:
        """调用大模型API"""
        pass
    
    def judge(self, image_path: Path, qid: str = "", sn: str = "") -> JudgeResult:
        """对外统一打分入口"""
        self._log.info("[%s] stage=JUDGING image=%s", qid, image_path.name)
        self.logger.info("judge start: qid=%s image=%s", qid, image_path.name)
        from ..core.rubric import image_to_data_url, calculate_weighted_total, score_to_100, AxisScore, OcclusionResult
        
        start_time = time.perf_counter()
        try:
            if not self.base_url:
                raise ValueError("Aesthetics API base URL is required. Pass --aesthetics-base-url or set AESTHETICS_BASE_URL.")
            if not self.api_key:
                raise ValueError("Aesthetics API key is required. Pass --aesthetics-api-key or set AESTHETICS_API_KEY.")

            # 图片转base64
            image_data_url = image_to_data_url(image_path)
            
            # 构建prompt
            prompt = self.build_prompt(image_data_url)
            
            # 调用API，重试逻辑
            raw_response = None
            last_error = None
            for retry in range(self.max_retries + 1):
                try:
                    if retry > 0:
                        self.logger.warning("API retry %d/%d for qid=%s", retry, self.max_retries, qid)
                    raw_response = self.call_api(prompt, image_data_url)
                    break
                except Exception as e:
                    last_error = e
                    if retry < self.max_retries:
                        wait_time = 2 ** retry  # 指数退避
                        time.sleep(wait_time)
                        continue
            
            if raw_response is None:
                self._log.error("[%s] API all retries exhausted", qid)
                raise RuntimeError(f"API调用失败，重试{self.max_retries}次后仍失败: {str(last_error)}")
            
            # 解析响应
            message_content = self._extract_message_content(raw_response)
            result_json = extract_json_from_model_output(message_content)
            if not result_json:
                self._log.error("[%s] JSON parse failed: %s", qid, message_content[:200])
                raise RuntimeError(f"模型输出没有有效JSON结构: {message_content[:500]}")
            
            # 解析得分
            final_score = float(result_json.get("score", 0.0))
            rationale = result_json.get("rationale", "")
            
            # 解析维度得分
            axis_scores = []
            raw_axis = result_json.get("axis_scores", {})
            from ..core.rubric import RUBRIC_WEIGHTS, RUBRIC_DISPLAY_NAMES
            for axis_id, weight in RUBRIC_WEIGHTS.items():
                score = float(raw_axis.get(axis_id, final_score))
                score = max(0.0, min(8.0, score))
                weighted_score = round(score * weight, 2)
                axis_scores.append(AxisScore(
                    axis_id=axis_id,
                    axis_name=RUBRIC_DISPLAY_NAMES[axis_id],
                    score=score,
                    weight=weight,
                    weighted_score=weighted_score
                ))
            
            # 解析遮挡结果
            occlusion = OcclusionResult()
            if "occlusion" in result_json:
                occ_data = result_json["occlusion"]
                occlusion.detected = occ_data.get("detected", False)
                occlusion.types = occ_data.get("types", [])
                occlusion.findings = occ_data.get("findings", [])
                occlusion.affected_axes = occ_data.get("affected_axes", [])
                occlusion.score_impact = float(occ_data.get("score_impact", 0.0))
            
            # 计算最终得分
            final_score = calculate_weighted_total(axis_scores)
            final_score_100 = score_to_100(final_score)
            
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            
            # 提取 token 用量
            prompt_tokens = 0
            completion_tokens = 0
            usage = raw_response.get("usage", {})
            if usage:
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
            
            self._log.info("[%s] stage=JUDGE_DONE score=%.1f/100 elapsed=%dms tokens_in=%d tokens_out=%d", qid, final_score_100, elapsed_ms, prompt_tokens, completion_tokens)
            return JudgeResult(
                qid=qid,
                sn=sn,
                image_path=str(image_path.absolute()),
                final_score=final_score,
                final_score_100=final_score_100,
                axis_scores=axis_scores,
                occlusion=occlusion,
                rationale=rationale,
                model=self.model,
                prompt_version=self.prompt_version,
                elapsed_ms=elapsed_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                success=True
            )
            
        except Exception as e:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            self.logger.error("judge FAIL: qid=%s error=%s", qid, str(e)[:200])
            return JudgeResult(
                qid=qid,
                sn=sn,
                image_path=str(image_path.absolute()),
                final_score=0.0,
                final_score_100=0.0,
                axis_scores=[],
                occlusion=OcclusionResult(),
                rationale="",
                model=self.model,
                prompt_version=self.prompt_version,
                elapsed_ms=elapsed_ms,
                success=False,
                error_msg=str(e)
            )
    
    def _extract_message_content(self, raw_response: Dict[str, Any]) -> str:
        """从API响应里提取消息内容，默认OpenAI格式"""
        try:
            choices = raw_response.get("choices", [])
            if not choices:
                return ""
            message = choices[0].get("message", {})
            content = message.get("content", "")
            if isinstance(content, list):
                # 兼容多模态响应格式
                for item in content:
                    if item.get("type") == "text":
                        return item.get("text", "")
                return ""
            return str(content)
        except Exception as e:
            return str(raw_response)
