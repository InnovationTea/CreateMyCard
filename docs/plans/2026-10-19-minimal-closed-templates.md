# 最小闭合语义模板 Implementation Plan

**Goal:** 将当前 33 个悬空布局/组合片段改为引用闭合、真实 Props 的最小代码模板，测量 Token 增长并完成 36+12 条宽卡实验。

**Architecture:** 仅修改 layouts/2x2.md、layouts/2x4.md、combinations/2x2.md 中的片段与对应说明。Core、Plan、完整 Few-shot、模型路由、Runtime、校验与修复预算保持不变；Group/Region 仍作为局部片段，但其后代均在同块内定义。使用既有组件/案例领域的短中性示例，不复制测试任务组合或测试答案。

**Tech Stack:** Markdown Prompt Source、现有 Compact JSONL 解析与语义编译、pytest、统一 Renderer、DeepSeek 官方接口。

## 步骤

1. 备份 cffe609，创建 codex/minimal-closed-templates-20261019；冻结原 36 条与新 12 条的已运行结果。
2. 修改前记录同一加载器、同一组装参数下两种尺寸的字符与 Token；无法使用官方 tokenizer 时明确采用统一估算器，不伪称账单 Token。
3. 添加失败回归测试：检查三个文件中所有 genui 块组件引用闭合、ID 唯一、单父且无孤立节点；完整父模板以 root 为根，局部片段以其首节点为根。
4. 逐块补齐最少组件定义和必要 Props；有动态绑定则同块初始化，有动作则给完整示例 handler，不使用伪类型占位符。保持原布局/变体、角色顺序与限制规则。
5. 用现有解析、编译和相关提示词测试验证；任何既有失败单列，不放宽校验。复查未扩大测试标签暴露程度。
6. 记录修改后 Token、增量和比例。以同一模型配置串行跑旧集 Q053–Q088 和新集 12 个 size=2x4 案例，每完整轮最多 5 次修复、最多 2 轮。
7. build_gallery.mjs 生成两份 Gallery；审计引用错误、最终状态、修复轮数、耗时及最终内容缺失/重复的 warning；与同日 cffe609 基线比较，不把单次波动宣称为稳定提升。

## 不做

- 不改变布局准入、几何、缺失事实 warning 或 Drop 策略。
- 不把旧例子替换成测试集正确答案，不增加与测试输入相同的多字段组合。
- 不修改完整 Few-shot，不增加模型调用或检索阶段。
- 不自动推送 GitHub。
