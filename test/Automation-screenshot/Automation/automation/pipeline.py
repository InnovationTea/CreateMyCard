from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .arkts import ArkTsRunner
from .config import AutomationConfig
from .hdc import HdcClient
from .queries import QueryCase, load_queries
from .xiaoyi import QueryResult, XiaoyiClient

@dataclass(frozen=True)
class RenderResult:
    qid: str
    dsl_path: Path
    screenshot_path: Path

class AutomationPipeline:
    def __init__(self, config: AutomationConfig, aesthetics_config = None):
        self.config = config
        self.hdc = HdcClient(config.hdc, sn=config.sn)
        self.xiaoyi = XiaoyiClient(config, self.hdc)
        self.arkts = ArkTsRunner(config, self.hdc)
        self.aesthetics_config = aesthetics_config
        
        # 初始化审美打分器
        self.aesthetics_judge = None
        if self.aesthetics_config and self.aesthetics_config.enable:
            # 动态导入，避免不需要打分的时候加载依赖
            import sys
            sys.path.insert(0, str(self.config.project_root))
            from visual_aesthetics.judge import VisualAestheticsJudge
            self.aesthetics_judge = VisualAestheticsJudge(self.aesthetics_config)

    def run_one(self, case: QueryCase) -> RenderResult:
        """运行单个query，从发送到渲染截图，开启打分的话自动打分"""
        query_result = self.xiaoyi.collect_dsl_for_query(case.qid, case.query)
        screenshot = self.arkts.render(case.qid, query_result.dsl_path)
        result = RenderResult(case.qid, query_result.dsl_path, screenshot)
        
        # 自动打分
        if self.aesthetics_judge:
            self.aesthetics_judge.judge_image(screenshot, case.qid, self.config.safe_sn or "")
        
        return result

    def run_batch(self, queries_path: Path | None = None) -> list[RenderResult]:
        """批量运行所有query，开启打分的话自动批量打分生成报告"""
        cases = load_queries(queries_path or self.config.queries_path)
        query_results: list[QueryResult] = []
        for case in cases:
            try:
                query_results.append(self.xiaoyi.collect_dsl_for_query(case.qid, case.query))
            except TimeoutError:
                continue

        render_results: list[RenderResult] = []
        for result in query_results:
            screenshot = self.arkts.render(result.qid, result.dsl_path)
            render_results.append(RenderResult(result.qid, result.dsl_path, screenshot))
        
        # 批量自动打分和生成报告
        if self.aesthetics_judge and render_results:
            self.aesthetics_judge.batch_judge(
                self.config.output_dir,
                sn=self.config.safe_sn or "",
                output_jsonl_path=self.config.scores_jsonl_path
            )
            self.aesthetics_judge.build_report(
                self.config.scores_jsonl_path,
                self.config.report_html_path,
                image_dir=self.config.output_dir
            )
        
        return render_results

