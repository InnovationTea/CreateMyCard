# 并列双信息块稳定性 Implementation Plan

**Goal:** 通过信息关系、组合选择和布局语义的一致描述，提高两个同级短信息单元采用双 InfoBlock 的稳定性，不加入测试答案。

**Architecture:** Common 维护关系与组合成立条件；单组件合同只约束一个实例；2x2 布局维护映射；Plan 复用组合条件而不复制选型表；Repair 只维护修复时的关系保真。不改 Runtime、校验、协议、预算或 Few-shot。

**Tech Stack:** Prompt Source Markdown、pytest、Ruff、官方 DeepSeek、现有两轮 Runner 和 build_gallery.mjs。

## 步骤与边界

1. 从 925d587 建立独立分支，冻结未改 Prompt，先对 Q009/Q010/Q015 各独立推理五次作为同配置对照。
2. 添加 Prompt 合同回归测试，验证规则归属、排除条件、Plan/Repair 关联和未改 Few-shot。
3. 更新方案文档，再按职责修改 Information/Common、Combinations/Common、Components/Common、Layouts/2x2、Plan、Repair。
4. 不以题号、字段路径、设备/天气/心率领域名做路由；不增加案例；不要求有动作、唯一核心或专用组件的卡片强用双信息块。
5. 2x2 stacked-info 明确可承载同主题两个同级指标，而非仅独立对象；不改变槽位尺寸、可用 Props、强制标题、素材分配与几何。
6. 运行相关 pytest、Ruff、diff 检查；修改后原三条各再独立推理五次，保留所有输出，不挑选结果。
7. 比较双 InfoBlock 使用率、输入要求绑定覆盖、生成/修复成功、布局/变体与标签；统一渲染全部结果并人工检查。

## 验证口径

- 官方 DeepSeek，关闭 thinking，开启 Few-shot，原有每轮五次质量修复、最多两轮；不改变 temperature。
- 每阶段五组、每组三例；无测试题示例进入 Prompt。不同重复间无历史对话复用。
- 组件一致率不等于质量，不牺牲完整事实、正确标签、合法槽位和必要动作。
- 五次只能提供小样本稳定性证据，不能保证所有后续生成相同，也不代表其它场景整体提升。

## 实际修改文件与职责

- `docs/云侧方案设计.md`：登记组合选型、同级布局与静态说明分工，不改 Runtime 行为。
- `prompt_source/combinations/common.md`：双信息块成立条件、优先级和专用表达/容量/动作排除条件。
- `prompt_source/components/common.md`：一个实例不能承载两个同级指标；静态说明与动态辅助值的不同填法。
- `prompt_source/components/2x2.md`：只维护图标额度，组合成立条件交回组合层，消除双对象旧措辞冲突。
- `prompt_source/layouts/2x2.md`：区分 standard 主辅与 stacked-info 同级；无标题双槽同样承载已成立组合。
- `prompt_source/plan.md`：组合映射到软组件推荐，不复制触发条件，不添加输出字段。
- `prompt_source/repair.md`：保留同级关系；主文本超宽先按组件合同恢复填槽分工，不冻结不适配组件。
- `widget_service/tests/test_peer_info_prompt_contract.py`：10 项文案归属、加载及 Few-shot 摘要回归。
- 本文件：计划、开发过程和验证边界。Information 原有同级规则足够明确，未重复修改；Few-shot 未改。

上述 prompt_source 均位于 `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/`。

## 重复生成结果

在同一批三条开发样本上，基线及三轮优化每版各独立生成五组，每组只含三例；共60次生成。
每版运行期间冻结全部 Prompt 摘要，配置与 TaskSpec 相同；没有按最佳结果替换失败结果。

| Case | 基线双InfoBlock最终稿 | 最终填槽版双InfoBlock最终稿 | 两版字段覆盖 |
|---|---:|---:|---:|
| Q009 | 5/5 | 5/5 | 均20/20 |
| Q010 | 5/5 | 5/5 | 均20/20 |
| Q015 | 1/5 | 5/5 | 均10/10 |

只澄清组合和命名时，Q015 初稿能达到5/5使用双信息块，但定义统一版在修复后只剩2/5：
模型把静态指标标签、读数、长单位同时塞入主行，超宽后改成表格或强调文本。
最终版补清单组件填槽和对应修复顺序，Q015 初稿及最终稿均5/5双信息块。
最终版15次均success，总计1次质量修复，未牺牲字段完整度。

- 363 项相关 pytest 通过；Ruff、git diff --check通过。
- Few-shot 两个源文件及所有内容摘要不变，未增加业务示例或测试题路由。
- 原 Runner、协议、Plan Schema、校验和预算均未改；没有用代码强制 InfoBlock。
- build_gallery.mjs 渲染全部60个最终稿，另保留15个 rejected 中间稿；浏览器检查60个最终稿可渲染、无脚本错误或失效图片。
- 静态生成参考 o200k_base：2x2 为30170，较命名版29658增512（约1.7%）；2x4 为30537，较30146增391（约1.3%）。非DeepSeek账单Token，未运行2x4推理。
- 本地完整对照及来源映射：`compact_dsl/output/1019-peer-infoblock-stability/`，不随代码提交上传。

这是开发样本上的小规模重复验证，不是未见样本的泛化证据；既不声称永远5/5，也不声称整体视觉已验证改善。
