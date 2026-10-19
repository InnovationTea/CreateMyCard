# 最小闭合语义模板 Implementation Plan

**Goal:** 将 33 个布局/组合片段改为引用闭合、业务 Props 使用省略号的结构模板，测量 Token 变化。

**Architecture:** 仅修改 layouts/2x2.md、layouts/2x4.md、combinations/2x2.md 中的片段与对应说明。Core、Plan、完整 Few-shot、模型路由、Runtime、校验与修复预算保持不变；Group/Region 仍作为局部片段，其后代均在同块内定义。保留语义结构参数，其余 Props 用 `...` 占位，不提供具体业务填槽内容。

**Tech Stack:** Markdown Prompt Source、现有 Compact JSONL 解析与语义编译、pytest、统一 Renderer、DeepSeek 官方接口。

**用户追加范围：** 在 Core 的 JSONL 结构中补充组件 ID 与 children 的准确引用关系，区分组件引用和数据路径绑定；各布局文件明确省略号只作模板占位，不能出现在最终输出。其余 Core 合同保持不变。

## 步骤

1. 备份 cffe609，创建 codex/minimal-closed-templates-20261019；冻结原 36 条与新 12 条的已运行结果。
2. 修改前记录同一加载器、同一组装参数下两种尺寸的字符与 Token；无法使用官方 tokenizer 时明确采用统一估算器，不伪称账单 Token。
3. 添加失败回归测试：检查三个文件中所有 genui 块组件引用闭合、ID 唯一、单父且无孤立节点；完整父模板以 root 为根，局部片段以其首节点为根。
4. 保留最少组件定义、Layout/Region/Group 属性，以及组件必要的 variant/direction；业务 Props 统一写 `...`，不保留业务值、handler、素材和首帧数据。保持布局/变体、角色顺序与限制规则。
5. 模板测试仅在测试内移除 `...` 后检查 ID 唯一、单父、可达及引用闭合；另查模板不含业务填槽属性。不要求占位模板可执行，不修改 Runtime 解析器。运行既有完整 Few-shot 与提示词回归测试。
6. 新标签记录结构模板 Token，与原始基线及已备份的具体示例版本分开比较。
7. 用户指出具体填槽过细后已停止批跑：旧集只完成 Q053–Q064，后续 12 条未启动。该部分结果不用于评价本次结构模板；先交付修正格式，不自动恢复批跑。

## 不做

- 不改变布局准入、几何、缺失事实 warning 或 Drop 策略。
- 不把旧例子替换成测试集正确答案，不增加与测试输入相同的多字段组合。
- 不修改完整 Few-shot，不增加模型调用或检索阶段。
- 不自动推送 GitHub。

## 本次验证

- 33 个结构模板：业务 Props 均为 `...`，引用闭合、ID 唯一、单父、全部可达。
- 模板、提示词加载、完整 Few-shot 回归合计 338 项通过；Ruff 与 git diff --check 通过。
- 相对 cffe609 的同口径静态生成参考提示词：2x2 从 29425 增至 30013 Token（+588，约 2.0%）；2x4 从 29869 增至 30433（+564，约 1.9%）。均为 o200k_base 估算，不是 DeepSeek 账单 Token。
- Plan 内容及其增量 Token 不变。新模板未发起 API 批跑；已停止的具体填槽实验不作为其评测结果。
