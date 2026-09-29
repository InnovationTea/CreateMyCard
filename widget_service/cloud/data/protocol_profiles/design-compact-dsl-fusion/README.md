# CompactDSL 融合提示词

本目录是正式单步链路唯一的提示词维护入口。协议身份仍是 `design-compact-dsl`，
其旧目录只保留 `protocol.json`；主提示词、编辑、修复、参数恢复和尺寸案例均不再从旧目录读取。

当前实现在最初等价拆分的基础上，已将 information 收敛为连续的语义合同；不接入 JSX，
也不增加独立 Plan 模型调用。最初迁移基线为
`Br_feature_fusion` / `81c64b843bf957e878a846bfdc498e09c7242b36`。

## 如何分工

| 维护文件（均在 prompt_source 下） | 边界 / 内容 | 配套检查 |
|---|---|---|
| `manifest.yaml` | 模块、适用尺寸、片段顺序、案例索引；不发模型 | 加载、来源完整性 |
| `core.md` | 输入/输出、绑定、数据、事件/资源、单位/字号/颜色、全局禁止和检查 | 协议与绑定测试 |
| `information/common.md` | 对象、事实关系、主次并列、去重取舍、动作归属 | 通用信息合同 |
| `information/2x2.md` | 小卡事实容量、双对象关系、日期去重 | 2x2 信息取舍 |
| `information/2x4.md` | 宽卡主辅/等权关系、多对象最小信息 | 2x4 信息取舍 |
| `components/common.md` | 基础组件、Compact 高阶组件与 CardHeader 合同 | 组件转换/校验 |
| `components/2x2.md` | 小卡图标限制、EventCard、PillButton、CircleButton 等尺寸适配 | 标题/图标/时间线 |
| `components/2x4.md` | 宽卡高阶组件、固定槽与背板透明度 | 色板与尺寸 |
| `combinations/common.md` | 多组件组合的共享语义、成立条件、角色数量与排除条件 | 组合语义边界 |
| `combinations/2x2.md` | 共享组合到十个 2x2 正式骨架的落地矩阵 | 小卡组合兼容性 |
| `combinations/2x4.md` | 共享组合到父布局、Sub-118/Sub-140 与固定槽的落地矩阵 | 宽卡组合兼容性 |
| `layouts/common.md` | 画布、预算、区域槽位、路由总则 | 一级高度、非负空间 |
| `layouts/2x2.md` | 十个正式语义布局；S1–S4 仅作为输入别名 | 小卡路由 |
| `layouts/2x4.md` | 四个正式顶层布局；W1–W10 仅作为输入别名 | 宽卡路由 |
| `composition.md` | 内部决策顺序、冲突优先级；未来 Plan 接入边界 | 模型消息合同 |
| `repair.md` | 反馈定位、共同根因、最小修复及子树重算 | 创建约束继承 |
| `edit.md` | 编辑包装与稳定性规则 | 原始 DSL 编辑 |
| `argument_repair.md` | 参数 JSON 结构恢复 | 不补造业务值 |
| `fewshots/2x2.md` | 小卡共用前言与 V00–V15 全部 16 个完整输入→输出案例 | 每例校验、转换，不丢失前置覆盖 |
| `fewshots/2x4.md` | 宽卡共用前言与 V00–V14 全部 15 个完整输入→输出案例 | 每例校验、转换，不丢失前置覆盖 |
| `fewshots/repair/` | 修复案例维护入口；本步不增加在线 few-shot | 先验证再启用 |

## 修改与加载

加载器为 `cloud/services/compact_prompt_loader.py`，仅依赖标准库，不依赖服务配置或模型客户端。
默认配置与协议注册表共用它；按源目录缓存完整提示词包，启动或首次使用时读取文件并校验。

```text
prompt_source → manifest 顺序 → 内存拼接与缓存 → 请求裁剪/示例选择 → 模型消息
```

`manifest.yaml` 使用 YAML 1.2 的 JSON 子集，由标准库解析，不新增部署依赖。
`prompts` 中每个数组的顺序是唯一拼接顺序，引用格式为 `文件#片段`。六个名称是内存中的提示词标识：
`create`、`edit`、`repair`、`argument_repair`、`fewshot_2x2`、`fewshot_2x4`。
每种尺寸的 Few-shot 只维护一个文档，前言使用 `preamble`；2x2 使用 `example-v00` 至
`example-v15`，2x4 使用 `example-v00` 至 `example-v14`。manifest 保留逐案例索引，加载器逐片段检查完整输入/输出，不按整文件放行。
只有 `<!-- prompt:片段 -->` 与对应结束标记之间的正文发给模型；维护说明、索引、边界表、
manifest 和标记本身不发。不要把要生效的规则写到标记外。
信息模块和组合公共模块使用连续合同：先完成信息语义分析，再判断多组件关系，最后按尺寸映射到正式
布局；组合不新增 Compact 组件或 Card/Region 等语义协议节点。其它模块仍可按需要拆分片段。

`sizes` 标明维护适用范围，而不是新增整文件运行时过滤。本期仍由 PromptBuilder 仅裁剪第九节的
尺寸/对象数骨架，并按原算法选择同尺寸案例；不基于新增字段重新选择布局。
修改规则时只编辑源模块，验证最终模型文本后发布并重启服务；没有中间文件或额外构建步骤。
部署应完整携带源目录；缺失、越界路径、重复/遗漏片段与损坏案例均明确报错。
外部配置使用 `@prompt:源目录#名称`。普通 `@file:` 仍读取原文，不能直接读取带维护说明的源模块。

## 与 Multi-step 的融合边界

吸收信息处理、单组件、组件组合、布局与编排分层的维护方式，并在 PR 416 的语义布局骨架内维护 Compact 高阶组件。
后续可以在 information/composition 中完善 Plan，或在 components 增加受控高阶组件；但必须同时
验证 Compact 编译/校验支持，不能仅把 JSX 名称和 Props 粘进提示词。

以下差异本次有意不搬运：JSX/dataIds、独立 submit_card_plan、四轮 next、160/320 画布、
格式化百分比自动转换为 Progress、冻结全部字段后禁止取舍。它们与当前 Compact 合同并不等价。
其它模块仍可能保留历史重复、覆盖和尺寸说明差异；information 已清除跨组件、视觉与布局职责的重复规则。

## 显示回归保障

六种模型文本继续由维护源确定性组装。高阶组件替换属于有意的协议演进，
不再要求与迁移前文本摘要完全一致；转换测试应证明高阶调用展开后保持对应 Few-shot 的布局与视觉属性。
案例另经 Compact 上下文校验和 A2UI 转换。这里不声称完成真实端侧截图验收或线上随机模型质量验收。
