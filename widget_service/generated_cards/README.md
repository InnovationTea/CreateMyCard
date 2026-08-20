# DeepSeek 完整链路实验结果

本目录保留 2026-08-20 使用真实 DeepSeek 调用得到的可复查产物。每个成功样本的 `a2ui/<case-id>.a2ui` 是最终 A2UI；`artifacts/` 是服务生成的原始 artifact；`results.jsonl` 保留每一条请求、模型返回和链路结果。

## 目录说明

- `20260820-final-full-chain-deepseek/`：100 条测试集的完整运行。`summary.json` 记录 71/100 最终成功；其中 30 条模板直出，41 条由全量模型生成成功。该轮的路由后处理曾低估部分共享 capability 的模板命中，因此需要以其原始 `results.jsonl`、A2UI 与日志为准，不应再以早期问题分类报告作为最终归因。
- `20260820-problem-cases-rerun/`：对前一轮被归为问题的 49 条重新真实调用。它通过模板直出入口记录实际路由，确认其中 12 条为模板直出、7 条为全量生成成功，并保留 30 条未出卡的逐条说明。
  - `rejection_and_a2ui_validation_reasons.md` 是当前有效的 18 条前置拒绝与 12 条 DSL 校验失败归因。
  - `rerun_report.md`、`errors.jsonl` 及 `results.jsonl` 是原始运行记录。

根目录的两个 `.log` 分别对应上述两轮运行，保留完整服务日志以便逐条复核。`mock_obs/` 是与 `artifacts/` 内容相同的本地上传模拟副本，已不保留。

实验运行器是本地临时脚本，未纳入仓库；API key 未写入任何已提交文件。
