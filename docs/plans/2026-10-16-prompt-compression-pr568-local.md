# 压缩版融合 PR568 与 main 兼容 Implementation Plan

> 本任务在当前会话逐项执行，不调用未安装的 superpowers 工具，不开启子代理。

**Goal:** 在首版压缩 `a464537` 的职责结构上适配最新主仓、融合 PR568 实际策略，先本地验证及2×4全量回归，不更新远端PR579。

**Architecture:** 首版分支与备份保持冻结；在独立本地分支合并主仓 `f0ffcc3`、PR568 `b491ae3`。运行逻辑以两个上游版本为依据，不额外设计新策略；Prompt 按 Core/Plan/Repair 原职责融合，并保留 main 新主题阶段合同。

**Tech Stack:** Git、Python、pytest/Ruff、Markdown prompt_source、官方DeepSeek、原生两轮接口重试、build_gallery.mjs。

## 1. 保护与范围

- 原首版：`codex/skill-boundaries-compact-20261016`，`a464537`。
- 本地备份：`codex/backup-prompt-compression-before-pr568-20261016`。
- 本地整合：`codex/prompt-compression-pr568-local-20261016`。
- 不改原始测试输入、现有Few-shot业务答案，不混入后续骨架恢复及coverageChanges实验。
- 不推送、不更新PR579；用户审阅回归结果后再决定。

## 2. 合并最新主仓

涉及冲突文件：`prompt_source/core.md`、`test_compact_prompt_bundle.py`、`test_design_compact_few_shots.py`。
Core 保留压缩的协议组织，改为 main 当前的主题定稿阶段，不保留生成阶段旧的自行配色指令；
测试同时覆盖压缩边界与新阶段职责，不通过恢复整段旧提示词消除断言失败。
运行代码、配置、模板和其它无冲突文件沿用 main；不得覆盖 main 的协议或端侧适配更新。

## 3. 融合 PR568

主要运行文件：`api/schemas.py`、`models/generation.py`、`compact_dsl_interface_retry.py`、
`compact_high_level_components.py`、`compact_plan.py`、`compact_repair_strategy.py`、
`generation_pipeline.py`、`prompt_builder.py`、`widget_generation_service.py`。

- SecondaryBody 仅对预测自动换行的相关层级取消固定高度，保留其它合同。
- Plan数据事实恰好一次可见展示，进度图形驱动value不重复计作displayValue之外的新展示；
  composition不把同一数据事实分配给多个可见placement。
- 重复诊断保留组件/属性位置；先定向去重，再按原PR策略有界升级修复范围。
- 布局容量/结构失败后，接口重试传递内部capacity_recovery上下文，不扩展外部API。
- 第二轮重新Plan：压缩语义相容的补充内容，但不随意降级明确要求、核心事实或Action；
  特定恢复模式只允许should候选的受控删除，不另行修改修复预算。
- Core拥有唯一展示协议，Plan拥有placement语义，Repair拥有duplicateFacts执行说明；
  Runtime动态错误反馈仍由PR代码提供，不将条件分支全量复写进静态Skill。

## 4. 测试

1. 先运行变更涉及的Prompt加载、主题阶段、单组件转换、Plan、重复事实、Repair、接口重试测试，
   保留2×2/2×4参数化覆盖；发现冲突引起失败时做最小适配，不绕过真实业务断言。
2. 修改Python运行Ruff、测试与`git diff --check`；检查无合并标记。
3. 原Few-shot V03高度未闭合失败需要区分基线已有问题与本次合并回归；不修改测试样本隐藏它。
4. 比较融合版与最新main差异，确认没有覆盖新主题策略或引入其它实验。

## 5. 本轮在线回归

先沿用最近PR569的36条2×4任务。官方DeepSeek、关闭思考、Few-shot开启、runtime prompt context关闭，
原生最多两轮、每轮五次质量修复；新增主题阶段按main执行，不强行保持旧版调用次数。
输出独立目录，保留每条完整Trace及失败；用当前版本的build_gallery.mjs渲染，不替换失败最终稿。
核对新重复校验下的覆盖统计语义，区分“未展示”与“展示但重复”，不能把新规则导致的统计变化冒充字段消失。
与原首版两次及主仓已有结果比较成功/降级/失败、缺失/重复、修复次数、总时延与视觉问题。
离线长度重新统计，注明已经加入main新主题阶段，不能套用原46.1%的数值。

## 6. 交付

报告合并文件、测试通过/失败数量、完整36条结果、Gallery及策略触发情况；不声称单次采样证明稳定提升。
整合只在本地保存，不推送或更新PR579。
