---
name: phone-widget-prompt-source
description: 供提示词维护者查阅的职责边界、装配顺序与迁移映射；本文件不进入模型上下文。
---

# Prompt 维护源

`prompt_source` 是 2×2 与 2×4 提示词的维护源。目录中的 README、迁移说明和各片段的 YAML frontmatter 仅供维护与构建使用，不进入模型上下文。

每个职责目录固定包含三份片段：

| 文件命名 | 只负责 |
|---|---|
| `<role>_common.md` | 两种尺寸含义相同、应只维护一次的规则 |
| `<role>_2x2.md` | 2×2 的能力、容量、路由与示例 |
| `<role>_2x4.md` | 2×4 的能力、容量、路由与示例 |

尺寸片段只能补充当前尺寸的能力，不能重新定义 Common 已声明的 Prop、绑定含义和事实规则。若语义触发条件相同但实现不同，触发条件写入 Common，具体组件、variant、槽位和 JSX 示例写入尺寸片段。

## 职责边界

| 目录 | 负责 | 不负责 |
|---|---|---|
| `core` | 输出协议、数据／Action 绑定、资源和生成边界 | 信息取舍、组件选择、布局路由 |
| `information-processing` | 理解 `userQuery`、划分信息分区、判断主次、保留与省略 | 组件、布局和 JSX Props |
| `components` | 单组件语义、真实 Props、绑定能力、容量和单组件示例 | 多组件组合与父布局路由 |
| `component-combinations` | 多组件何时构成一个表达单元、组合结构和组合示例 | 单组件合同与父布局定义 |
| `layouts` | `Card + Region` 接口、父布局、内容区 variant、固定槽和容量 | 业务字段取舍与组件内部 Props |
| `composition` | 信息、组件、组合与布局的联合选择顺序 | 重复定义组件或布局合同 |
| `fewshots` | 完整输入、分析、Plan 与 JSX 的端到端示例 | 新增合同或替代规则正文 |
| `repair` | 根据 findings 做最小修复与必要的语义迁移 | 首轮生成策略和新的重试机制 |

## 装配顺序

首轮生成按下列顺序装配 Common 与当前尺寸片段：

1. Core
2. Information Processing
3. Components
4. Component Combinations
5. Layouts
6. Composition
7. Fewshots（仅启用 `--few-shot` 时）

Repair 仅在修复轮次追加。每个片段的 YAML frontmatter 在装配时移除，最终 Prompt 只保留一份系统级说明。

## Common 判断标准

规则同时满足以下条件才进入 Common：

1. 两种尺寸下含义、Prop 和绑定方式相同。
2. 更新该规则时，两种尺寸都应同时生效。
3. 规则不依赖父布局名、Region 名、variant、固定槽或尺寸专属组件。

迁移前后的文件与职责对应关系见 [MIGRATION.md](./MIGRATION.md)。
