# TextBlock 等高与协议一致性 Implementation Plan

> 在当前会话按步骤执行，不委派子代理，不更新远端 PR579。

**Goal:** 修复 TextBlock 展开 Row 使用协议外 stretch 导致最终交付失败的问题，保持原来的等高、等宽及字号间距。

**Architecture:** 修改视觉 Recipe 源中 TextBlock.root 的 alignItems 为 top；等高继续由各 item 的 height=matchParent 保证。所有尺寸、权重、最小尺寸、内部排版与标准枚举校验均保持原样。不修改模型输入、Few-shot、信息覆盖策略、主题及修复预算。

**Tech Stack:** JSON Recipe、Python pytest/Ruff、官方 Renderer、Playwright、官方 DeepSeek。

## 1. 保护和合同

- 基线8f5212a；备份codex/backup-before-textblock-protocol-fix-20261016。
- 独立分支codex/textblock-equal-height-protocol-fix-20261016。
- 先同步docs/云侧方案设计.md中的实现说明，不新增协议能力或放宽校验。

## 2. 红绿测试

- 新增test_textblock_protocol_geometry.py，覆盖2/3/4项的转换几何与标准协议枚举。
- 原stretch必须被相同标准校验拒绝；合法top及子项matchParent必须通过。
- 在后置主题执行后再次校验，并确认主题不改变前景几何。
- 官方Renderer测试补充父级合法top与item填满父高的断言。
- 只改视觉Recipe中的TextBlock.root.alignItems，不改任何其它几何参数。

## 3. 等高验证

- 重放Q054/Q055/Q069/Q070上一批的最后合法Compact源，不向模型提供答案。
- 官方build_gallery.mjs渲染，比较旧stretch与新top在同一槽高的子项边界、宽高、标签和值位置。
- 对2/3/4项、不同父槽高度补充浏览器测量，不能仅凭静态属性声称等高。

## 4. 在线验证门槛

- 原始四条使用官方DeepSeek、thinking关闭、Few-shot开启，原生最多两轮、每轮最多5次修复。
- 四条没有同类最终协议错误且预览等高确认后，才执行36条2×4全量。
- 原始输入不改，不回填模型产物；若出现其它错误，独立归因，不冒称本修复无效或全部成功。
- build_gallery.mjs生成独立Gallery，与上一批同口径统计成功率、字段覆盖、修复及完整耗时。
- 不推送、不更新PR579。

## 5. 检查与交付

执行相关pytest、Renderer测试、Ruff和git diff --check；保留已知V03高度失败，不在本次顺带更改。
报告逐文件用途、测试结果、四条验证和全量结果；保持原压缩Prompt及PR568策略不变。
