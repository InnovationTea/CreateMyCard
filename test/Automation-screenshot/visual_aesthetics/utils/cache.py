"""
打分结果缓存工具
相同MD5的图片只会调用一次API，节省成本
"""
from pathlib import Path
import json
import hashlib
from typing import Optional, Dict, Any
from ..core.rubric import JudgeResult

class AestheticsCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_image_md5(self, image_path: Path) -> str:
        """计算图片MD5"""
        hasher = hashlib.md5()
        with open(image_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def get(self, image_path: Path, qid: str = "", sn: str = "") -> Optional[JudgeResult]:
        """获取缓存结果"""
        md5 = self._get_image_md5(image_path)
        cache_file = self.cache_dir / f"{md5}.json"
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # 反序列化为JudgeResult
            from ..core.rubric import AxisScore, OcclusionResult
            axis_scores = []
            for ax_data in data.get("axis_scores", []):
                axis_scores.append(AxisScore(**ax_data))
            
            occlusion = OcclusionResult(**data.get("occlusion", {}))
            
            result = JudgeResult(
                qid=qid,
                sn=sn,
                image_path=str(image_path.absolute()),
                final_score=data["final_score"],
                final_score_100=data["final_score_100"],
                axis_scores=axis_scores,
                occlusion=occlusion,
                rationale=data.get("rationale", ""),
                model=data.get("model", ""),
                prompt_version=data.get("prompt_version", ""),
                elapsed_ms=data.get("elapsed_ms", 0),
                success=data.get("success", True),
                error_msg=data.get("error_msg", "")
            )
            return result
        except Exception:
            return None
    
    def set(self, image_path: Path, result: JudgeResult) -> None:
        """写入缓存"""
        md5 = self._get_image_md5(image_path)
        cache_file = self.cache_dir / f"{md5}.json"
        
        # 序列化为JSON
        data = {
            "final_score": result.final_score,
            "final_score_100": result.final_score_100,
            "axis_scores": [ax.__dict__ for ax in result.axis_scores],
            "occlusion": {
                "detected": result.occlusion.detected,
                "types": result.occlusion.types,
                "findings": result.occlusion.findings,
                "affected_axes": result.occlusion.affected_axes,
                "score_impact": result.occlusion.score_impact
            },
            "rationale": result.rationale,
            "model": result.model,
            "prompt_version": result.prompt_version,
            "elapsed_ms": result.elapsed_ms,
            "success": result.success,
            "error_msg": result.error_msg
        }
        
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
