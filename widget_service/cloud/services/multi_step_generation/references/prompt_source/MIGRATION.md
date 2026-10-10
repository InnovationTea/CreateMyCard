# Prompt Source 迁移映射

本文件仅供维护者查阅，不进入模型上下文。

## 文件重命名

| 原文件 | 新文件 |
|---|---|
| `<role>/common.md` | `<role>/<role>_common.md` |
| `<role>/2x2.md` | `<role>/<role>_2x2.md` |
| `<role>/2x4.md` | `<role>/<role>_2x4.md` |

## 内容职责迁移

| 原内容 | 新职责位置 |
|---|---|
| intent、主问题、次问题、字段表、冻结、HOW | `information-processing` 中改写为 `userQuery`、信息分区、组内关系、主要／辅助信息和内部信息清单 |
| 通用数据、Action、Boolean、资源绑定 | `core` |
| 具体组件可绑定的 Prop、数组绑定和组件触发条件 | `components` |
| 多组件共同表达一个语义单元的规则 | `component-combinations` |
| 父布局、内容区 variant、固定槽与 Action 槽 | `layouts` |
| 组件与布局如何联合选择 | `composition` |
| findings、重试轮次中的保持项与迁移 | `repair` |
| 完整业务卡片示例 | `fewshots` |

## 迁移范围

- 本文只记录 Prompt 来源与职责的迁移；Runner、工具 schema 和校验器的实时适配以代码与测试合同为准。
- 2×2 暂不增加端到端 few-shot。
- 150×150／300×150 规格、语义布局接口和最新组件能力继续有效。
