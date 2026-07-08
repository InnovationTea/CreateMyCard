"""
对外统一审美打分入口
"""
from pathlib import Path
import json
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from .config import AestheticsConfig
from .models.doubao import DoubaoAestheticsModel
from .core.rubric import JudgeResult
from .utils.cache import AestheticsCache
from .reports.builder import ReportBuilder
from automation.logger import get_logger

class VisualAestheticsJudge:
    def __init__(self, config: AestheticsConfig):
        self.config = config
        self.model = DoubaoAestheticsModel(config.to_model_config())
        # 缓存默认关闭，避免旧缓存导致跳过API调用。需要开启时设置环境变量 AESTHETICS_ENABLE_CACHE=true
        self.cache = AestheticsCache(config.cache_dir) if config.enable_cache else None
        self._log = get_logger("aesthetics", sn="")
        self.logger = get_logger("aesthetics", sn="")
    
    def judge_image(self, image_path: Path, qid: str = "", sn: str = "", skip_cache: bool = False) -> JudgeResult:
        """
        单张图片打分
        :param image_path: 图片路径
        :param qid:  query ID
        :param sn:  设备SN
        :param skip_cache: 是否跳过缓存
        :return: 打分结果
        """
        image_path = Path(image_path).absolute()
        if not image_path.exists() or not image_path.is_file():
            return JudgeResult(
                qid=qid,
                sn=sn,
                image_path=str(image_path),
                final_score=0.0,
                final_score_100=0.0,
                axis_scores=[],
                occlusion=JudgeResult.__annotations__["occlusion"](),
                success=False,
                error_msg=f"图片不存在: {image_path}"
            )
        
        # 尝试读缓存
        if not skip_cache and self.cache:
            cached = self.cache.get(image_path, qid, sn)
            if cached:
                return cached
        
        # 调用模型打分
        result = self.model.judge(image_path, qid, sn)
        
        # 写入缓存
        if result.success and self.cache:
            self.cache.set(image_path, result)
        
        # 失败处理
        if not result.success and self.config.fail_fast:
            raise RuntimeError(f"打分失败: {result.error_msg}")
        
        return result
    
    def batch_judge(self, image_dir: Path, sn: str = "", output_jsonl_path: Optional[Path] = None) -> List[JudgeResult]:
        """
        批量给目录下所有png/jpg图片打分
        :param image_dir: 图片目录
        :param sn: 设备SN，用于关联结果
        :param output_jsonl_path: 结果输出jsonl路径，可选
        :return: 所有打分结果列表
        """
        image_dir = Path(image_dir).absolute()
        if not image_dir.exists() or not image_dir.is_dir():
            raise ValueError(f"图片目录不存在: {image_dir}")
        
        # 遍历所有图片
        image_files = []
        for ext in ["*.png", "*.jpg", "*.jpeg"]:
            image_files.extend(list(image_dir.glob(ext)))
        
        if not image_files:
            self.logger.warning("batch_judge: no images found in %s", image_dir)
            return []
        
        self.logger.info("batch_judge start: %d images, max_workers=%d", len(image_files), self.config.max_workers)
        # 并行打分
        results: List[JudgeResult] = []
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            future_to_image = {}
            for img in image_files:
                # 从文件名提取qid，格式：{SN}_q{xxx}.png或者直接q{xxx}.png
                qid = img.stem
                if sn and qid.startswith(f"{sn}_"):
                    qid = qid[len(f"{sn}_"):]
                future = executor.submit(self.judge_image, img, qid, sn)
                future_to_image[future] = img
            
            for future in as_completed(future_to_image):
                try:
                    result = future.result()
                    results.append(result)
                    status = "OK" if result.success else "FAIL"
                    self._log.info("batch_judge %s: qid=%s score=%.1f", status, result.qid, result.final_score_100)
                    self.logger.info("batch_judge %s: qid=%s score=%.1f", status, result.qid, result.final_score_100)
                except Exception as e:
                    img = future_to_image[future]
                    self.logger.error("batch_judge EXCEPTION: image=%s error=%s", img.name, str(e)[:200])
                    self._log.error("batch_judge EXCEPTION: image=%s error=%s", img.name, str(e)[:200])
                    results.append(JudgeResult(
                        qid=img.stem,
                        sn=sn,
                        image_path=str(img),
                        final_score=0.0,
                        final_score_100=0.0,
                        axis_scores=[],
                        occlusion=JudgeResult.__annotations__["occlusion"](),
                        success=False,
                        error_msg=str(e)
                    ))
        
        success_count = sum(1 for r in results if r.success)
        self.logger.info("batch_judge done: %d/%d success", success_count, len(results))
        total_prompt_tokens = sum(getattr(r, "prompt_tokens", 0) or 0 for r in results)
        total_completion_tokens = sum(getattr(r, "completion_tokens", 0) or 0 for r in results)
        avg_score = sum(r.final_score_100 for r in results if r.success) / success_count if success_count > 0 else 0
        self._log.info("=" * 60)
        self._log.info("BATCH JUDGE SUMMARY: total=%d success=%d fail=%d avg_score=%.1f tokens_in=%d tokens_out=%d", len(results), success_count, len(results) - success_count, avg_score, total_prompt_tokens, total_completion_tokens)
        self._log.info("=" * 60)
        
        # 输出jsonl
        if output_jsonl_path:
            self._write_results_jsonl(results, Path(output_jsonl_path))
        
        return results

    def judge_images(self, image_paths: List[Path], sn: str = "", output_jsonl_path: Optional[Path] = None) -> List[JudgeResult]:
        """
        Score an explicit list of images. Used by automation when original screenshots and cropped cards
        live in the same output directory.
        """
        results: List[JudgeResult] = []
        for image_path in image_paths:
            qid = Path(image_path).stem
            if qid.endswith("_card"):
                qid = qid[:-5]
            if sn and qid.startswith(f"{sn}_"):
                qid = qid[len(f"{sn}_"):]
            results.append(self.judge_image(Path(image_path), qid, sn))

        if output_jsonl_path:
            self._write_results_jsonl(results, Path(output_jsonl_path))
        return results

    def _write_results_jsonl(self, results: List[JudgeResult], output_jsonl_path: Path) -> None:
        output_jsonl_path = Path(output_jsonl_path).absolute()
        output_jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_jsonl_path, "w", encoding="utf-8") as f:
            for result in results:
                data = {
                    "qid": result.qid,
                    "sn": result.sn,
                    "image_path": result.image_path,
                    "final_score": result.final_score,
                    "final_score_100": result.final_score_100,
                    "axis_scores": [{k: v for k, v in ax.__dict__.items() if k not in ["__len__", "__getitem__"]} for ax in result.axis_scores],
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
                f.write(json.dumps(data, ensure_ascii=False) + "\n")
    
    def build_report(self, scores_jsonl_path: Path, output_html_path: Path, image_dir: Optional[Path] = None) -> None:
        """
        生成可视化HTML报告
        :param scores_jsonl_path: 打分结果jsonl路径
        :param output_html_path: 输出HTML路径
        :param image_dir: 图片所在目录，用于报告中引用图片，可选
        """
        builder = ReportBuilder()
        builder.build(scores_jsonl_path, output_html_path, image_dir)

