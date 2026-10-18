# 2×4 Compact 语义布局 Implementation Plan

**Goal:** 模型只选择现有父布局、子布局和受控组合，Runtime 展开固定几何；兼容原有绑定、Plan、容量校验、修复、编辑与统一渲染。

**Architecture:** 在 Compact 行解析和转换的公共边界增加布局编译层。原始 Layout/Region/Group 与编译后的 Row/Column 分开保存；事实组件 ID、Props、事件及数据行保持不变。旧 DSL 和 2×2 继续可读，现有高阶 Recipe 和校验判定不放宽。

**Tech Stack:** Python、Compact JSONL、现有布局合同及 Recipe、PR #512 连续对话、统一 A2UI CardRenderer。

## 公开协议

- `Layout` 只作为 root：`layout` 使用四个现有 W 名称；背景属性沿用当前颜色合同。W-top-bottom 的 `variant` 为 continuous/bottom-details/equal，children 为可选标题、主体、明细。W-split-panels 为两个 Region。W-content-side-slots 为一个 Region 与上、下两个固定槽，支持 orientation=content-left/content-right。W-four-slots 按左上、右上、左下、右下提供四槽。
- `Region` 只用于左右父区或侧槽父布局的内容区。子布局使用语义名称，与原 Sub-118 A/B/C/D 和 Sub-140 A/B/C/D/F/G/H 一一映射；由父布局确定宽版/紧凑版，模型不填写宽高。
- `Group` 仅表达已有紧密主辅、标签与值、并列双内容；按已登记组合展开，不能用其容纳任意节点或伪造语义。固定槽的合法组合沿用原合同。
- 语义节点不接受 width/height/padding/itemMargin/layoutWeight/flexShrink/对齐等几何 Props；也不绑定数据、事件。业务组件语义、单位、文本、素材与动作合同不变。

## 文件与验证步骤

1. 更新总方案，新增 `services/compact_semantic_layout.py`、合成单元测试；语义节点字段与形状属于转换器公开组件契约，容量仍归现有 semantic/layout；不新增重复容量校验。
2. 转换器新增 raw/expanded 解析开关及 Layout/Region/Group 类型；转换、公开空间解析都走同一编译器。绑定修复、资源还原和编辑保留 raw 行，不把生成节点写回模型源。
3. 校验上下文与 source_locations 增加可证明的布局 provenance，标记 expanded，指向原 Layout/Region/Group；不假称模型写过生成属性。2×2 语义输入拒绝。
4. Processor 分别记录语义源和展开源，Plan 覆盖、原高阶组件展开、静态容量、Artifact 校验顺序不变。修复路由把语义形状错误送到布局修复，反馈不得修改固定展开参数。
5. 2×4 layout 与组合文档改为语义模板和容量表，保留原成立条件/组件槽位限制；core/shared 文档明确尺寸差异。转换现有十个 Few-shot，仅更改布局表达，不变输入、内容、数据、动作与配色，不新增测试样本答案。
6. 测试：四父布局、所有 Region 变体、标题可选、镜像、非法几何、空槽、引用、生成 ID 冲突、数据/动作不变、2×2 不变、Legacy 不变、编辑资源还原、容量错误与反馈定位；相关校验回归、Ruff、diff 检查。
7. 先将十个已有 Few-shot 全部通过现有 Processor，统一渲染并目视检查；再用原始 cardSpec24 的 32 条做一次串行推理，每请求最多十次修复，不接入上一实验的 Drop/Reset，保存原始输入/语义 DSL/展开 DSL/Plan/反馈/耗时，生成 Gallery。

## 维护与失败边界

- 固定几何从当前画布/布局合同读取；子布局的结构模板集中维护，不在 Prompt、校验器和渲染器复制展开器。
- 几何闭合不代表无限容量；超预算仍换密度或布局，Drop 继续按 PR #512 原有逻辑，不改业务兜底。
- 原始事实、动作、绑定路径、SVG 颜色规则均保留；不得用静态替换或自动删信息实现通过。
- 代码分支 `codex/compact-semantic-layout-2x4-v1`，基于 `2d43d55`。主仓及上次实验保留，不自动推送。
