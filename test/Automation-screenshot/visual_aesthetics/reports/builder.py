from typing import Optional
"""
可视化报告生成器
100%复用原有aesthetic-v4的报告样式，保证视觉一致
"""
from pathlib import Path
import json
from typing import List, Dict, Any
from ..core.rubric import RUBRIC_DISPLAY_NAMES, score_to_100

class ReportBuilder:
    def build(self, scores_jsonl_path: Path, output_html_path: Path, image_dir: Optional[Path] = None) -> None:
        """生成HTML报告"""
        # 读取打分结果
        results = []
        with open(scores_jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        
        if not results:
            self._build_empty_report(output_html_path)
            return
        
        # 计算统计数据
        total = len(results)
        success = sum(1 for r in results if r.get("success", False))
        avg_score = sum(r.get("final_score_100", 0) for r in results if r.get("success", False)) / success if success > 0 else 0
        min_score = min(r.get("final_score_100", 0) for r in results if r.get("success", False)) if success > 0 else 0
        max_score = max(r.get("final_score_100", 0) for r in results if r.get("success", False)) if success > 0 else 0
        occlusion_count = sum(1 for r in results if r.get("occlusion", {}).get("detected", False))
        
        # 生成报告内容
        html = self._build_html(results, {
            "total": total,
            "success": success,
            "failed": total - success,
            "avg_score": round(avg_score, 1),
            "min_score": round(min_score, 1),
            "max_score": round(max_score, 1),
            "occlusion_count": occlusion_count,
            "sn": results[0].get("sn", "")
        }, image_dir)
        
        # 写入文件
        output_html_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_html_path, "w", encoding="utf-8") as f:
            f.write(html)
    
    def _build_empty_report(self, output_html_path: Path) -> None:
        """生成空报告"""
        html = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UI审美打分报告</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif; }
        body { padding: 20px; background: #f5f7fa; color: #333; }
        .container { max-width: 1200px; margin: 0 auto; }
        .empty { text-align: center; padding: 100px 0; color: #999; font-size: 18px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="empty">暂无打分结果</div>
    </div>
</body>
</html>
        """
        with open(output_html_path, "w", encoding="utf-8") as f:
            f.write(html)
    
    def _build_html(self, results: List[Dict[str, Any]], stats: Dict[str, Any], image_dir: Optional[Path] = None) -> str:
        """生成完整HTML"""
        # 统计卡片样式
        stats_cards = f"""
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">{stats['total']}</div>
                <div class="stat-label">总截图数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{stats['success']}</div>
                <div class="stat-label">打分成功</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{stats['failed']}</div>
                <div class="stat-label">打分失败</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{stats['avg_score']}</div>
                <div class="stat-label">平均得分</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{stats['min_score']}</div>
                <div class="stat-label">最低得分</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{stats['max_score']}</div>
                <div class="stat-label">最高得分</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{stats['occlusion_count']}</div>
                <div class="stat-label">存在遮挡问题</div>
            </div>
        </div>
        """
        
        # 结果列表
        results_html = ""
        for idx, result in enumerate(results, 1):
            success = result.get("success", False)
            score = result.get("final_score_100", 0)
            qid = result.get("qid", f"未知_{idx}")
            
            # 得分颜色
            score_color = "#f5222d" if score < 60 else "#faad14" if score < 80 else "#52c41a"
            
            # 图片路径处理
            image_path = result.get("image_path", "")
            if image_dir and not Path(image_path).exists():
                image_path = str(Path(image_dir) / Path(image_path).name)
            
            if not success:
                item_html = f"""
                <div class="result-item failed">
                    <div class="result-header">
                        <span class="result-index">{idx}</span>
                        <span class="result-qid">{qid}</span>
                        <span class="result-score bad">失败</span>
                    </div>
                    <div class="result-error">错误信息: {result.get("error_msg", "未知错误")}</div>
                </div>
                """
            else:
                # 维度得分条
                axis_html = ""
                for ax in result.get("axis_scores", []):
                    ax_name = RUBRIC_DISPLAY_NAMES.get(ax.get("axis_id", ""), ax.get("axis_name", "未知维度"))
                    ax_score_100 = score_to_100(ax.get("score", 0))
                    ax_color = "#f5222d" if ax_score_100 < 60 else "#faad14" if ax_score_100 < 80 else "#52c41a"
                    axis_html += f"""
                    <div class="axis-item">
                        <div class="axis-name">{ax_name} ({ax.get("weight", 0)*100:.0f}%)</div>
                        <div class="axis-bar-wrap">
                            <div class="axis-bar" style="width: {ax_score_100}%; background: {ax_color};"></div>
                            <span class="axis-score">{ax_score_100:.0f}</span>
                        </div>
                    </div>
                    """
                
                # 遮挡问题
                occlusion_html = ""
                occlusion = result.get("occlusion", {})
                if occlusion.get("detected", False):
                    types = ", ".join(occlusion.get("types", []))
                    findings = "; ".join(occlusion.get("findings", []))
                    occlusion_html = f"""
                    <div class="occlusion-warning">
                        <strong>⚠️ 检测到遮挡问题</strong>
                        <div>类型: {types}</div>
                        <div>问题: {findings}</div>
                        <div>扣分影响: {occlusion.get("score_impact", 0):.1f}分</div>
                    </div>
                    """
                
                item_html = f"""
                <div class="result-item">
                    <div class="result-header">
                        <span class="result-index">{idx}</span>
                        <span class="result-qid">{qid}</span>
                        <span class="result-score" style="color: {score_color}; background: {score_color}15;">{score:.0f}分</span>
                    </div>
                    <div class="result-body">
                        <div class="result-image">
                            <img src="{image_path}" alt="截图" loading="lazy">
                        </div>
                        <div class="result-info">
                            <div class="rationale">评分理由: {result.get("rationale", "无")}</div>
                            <div class="axis-list">{axis_html}</div>
                            {occlusion_html}
                        </div>
                    </div>
                </div>
                """
            results_html += item_html
        
        # 完整HTML
        return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UI审美打分报告 {stats['sn'] and f'设备: {stats['sn']}' or ''}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif; }}
        body {{ padding: 20px; background: #f5f7fa; color: #333; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{ margin-bottom: 30px; }}
        .header h1 {{ font-size: 28px; font-weight: 600; margin-bottom: 10px; }}
        .header .subtitle {{ color: #666; font-size: 14px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; margin-bottom: 40px; }}
        .stat-card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); text-align: center; }}
        .stat-number {{ font-size: 28px; font-weight: 700; margin-bottom: 8px; color: #1890ff; }}
        .stat-label {{ font-size: 14px; color: #666; }}
        .result-item {{ background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); margin-bottom: 20px; overflow: hidden; }}
        .result-item.failed {{ border-left: 4px solid #f5222d; }}
        .result-header {{ padding: 16px 20px; border-bottom: 1px solid #f0f0f0; display: flex; align-items: center; gap: 16px; }}
        .result-index {{ width: 30px; height: 30px; background: #1890ff; color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 600; font-size: 14px; }}
        .result-qid {{ flex: 1; font-weight: 500; font-size: 16px; }}
        .result-score {{ font-weight: 700; font-size: 18px; padding: 4px 12px; border-radius: 4px; }}
        .result-score.bad {{ background: #fff1f0; color: #f5222d; }}
        .result-body {{ padding: 20px; display: grid; grid-template-columns: 360px 1fr; gap: 30px; align-items: start; }}
        .result-image img {{ width: 100%; border-radius: 4px; border: 1px solid #f0f0f0; max-height: 640px; object-fit: contain; background: #fafafa; }}
        .rationale {{ background: #f8f9fa; padding: 12px 16px; border-radius: 4px; margin-bottom: 20px; font-size: 14px; line-height: 1.6; }}
        .axis-list {{ display: flex; flex-direction: column; gap: 12px; }}
        .axis-item {{ display: flex; align-items: center; gap: 12px; }}
        .axis-name {{ width: 120px; font-size: 14px; color: #666; flex-shrink: 0; }}
        .axis-bar-wrap {{ flex: 1; height: 24px; background: #f0f0f0; border-radius: 12px; overflow: hidden; position: relative; }}
        .axis-bar {{ height: 100%; transition: width 0.3s; }}
        .axis-score {{ position: absolute; right: 8px; top: 50%; transform: translateY(-50%); font-size: 12px; font-weight: 600; color: #333; }}
        .occlusion-warning {{ margin-top: 20px; padding: 12px 16px; background: #fff7e6; border: 1px solid #ffd591; border-radius: 4px; font-size: 14px; line-height: 1.6; color: #d48806; }}
        .result-error {{ padding: 20px; color: #f5222d; font-size: 14px; }}
        @media (max-width: 1000px) {{
            .result-body {{ grid-template-columns: 1fr; }}
            .stats-grid {{ grid-template-columns: repeat(3, 1fr); }}
        }}
        @media (max-width: 600px) {{
            .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>UI审美打分报告 {stats['sn'] and f'设备: {stats['sn']}' or ''}</h1>
            <div class="subtitle">生成时间: {self._get_current_time()}</div>
        </div>
        {stats_cards}
        <div class="results-list">
            {results_html}
        </div>
    </div>
</body>
</html>
        """
    
    def _get_current_time(self) -> str:
        """获取当前时间字符串"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

