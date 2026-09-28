# Compact 模块化提示词

本目录是 Compact 生成链路唯一的提示词包，协议标识为 `design-compact-dsl`。

## 目录职责

- `prompt_source/`：唯一人工维护入口，按信息、组件、组合、布局、编排及修复等职责分工。
- `prompt_source/manifest.yaml`：模块、片段加载顺序、适用尺寸及 Few-shot 索引，不发送给模型。
- `generated/`：构建器从上述模块拼接出的运行文本；不人工修改，不独立维护规则。

服务加载 `generated/` 的创建、编辑、修复、参数恢复和尺寸 Few-shot 文本，再按请求裁剪
布局、选择示例并追加运行时约束。源文件中的维护说明、导航表和片段标记不发送给模型。
产物缺失时加载失败，不回退到其它提示词文件。协议定义单独位于相邻的
`design-compact-dsl/protocol.json`，不是另一条提示词链路。

## 模块分工

以下文件均位于 `prompt_source/`；尺寸专属规则和通用规则分开维护。

| 模块 | 职责 |
|---|---|
| `core.md` | 输入输出、绑定、数据、事件、素材及全局视觉参数 |
| `information/common.md` | 对象和事实归属、主次并列、去重取舍 |
| `information/2x2.md` | 小卡密度与容量、单业务多字段、日期去重 |
| `information/2x4.md` | 主辅与等权、数据块关系、W1 密度 |
| `components/common.md` | 基础组件及 ActionUnit、CardHeader 合同 |
| `components/2x2.md` | 小卡图标限制与 TimelineUnit |
| `components/2x4.md` | 宽卡组件限制与背板透明度 |
| `combinations/common.md` | 数值单位、并列指标、图文动作和 Progress 组合 |
| `combinations/2x2.md` | Hero 安全盒、成对状态、倒计时与融球组合 |
| `combinations/2x4.md` | 同行读数、主焦点居中与天气组合 |
| `layouts/common.md` | 画布、区域槽位、预算与路由总则 |
| `layouts/2x2.md` | S1–S4 骨架、区域预算与动作边界 |
| `layouts/2x4.md` | W1–W10 骨架、区域预算与动作边界 |
| `composition.md` | 内部决策顺序、冲突优先级和 Plan 集成边界 |
| `repair.md` | 反馈定位、根因、最小修复和子树重算 |
| `edit.md` | 编辑包装与未受影响区域的稳定性 |
| `argument_repair.md` | 参数 JSON 结构恢复，不补造业务值 |
| `fewshots/2x2.md`、`fewshots/2x4.md` | 各尺寸的完整输入输出示例 |
| `fewshots/repair/` | 经过校验后才能启用的修复示例 |

## 修改与构建

在 `widget_service` 目录执行：

```powershell
python scripts/build_compact_prompts.py
python scripts/build_compact_prompts.py --check
```

`manifest.yaml` 使用 YAML 1.2 的 JSON 子集，构建只依赖标准库。`products` 数组顺序决定
拼接顺序，引用形式为 `文件#片段`；一个模块可以提供多个片段。
只有 `<!-- prompt:片段 -->` 与结束标记之间的正文进入模型文本；需要生效的规则必须写在标记内。
Few-shot 每个尺寸维护一个文档，前言使用 `preamble`，示例使用 `example-v00` 至 `example-v14`。
`sizes` 表达维护归属，运行时按尺寸与对象数裁剪布局章节并选用同尺寸示例，不过滤整个模块文件。

修改规则时只编辑对应的源模块，再构建并审查产物差异。修改片段名称、章节结构或加载顺序时，
还须核对 manifest 和运行时章节裁剪。源与产物一起发布，服务不在请求期间构建；修改后需重启
服务以更新模块级提示词缓存，外部 `@file` 配置也应指向本目录的 `generated/`。
新增组件必须先实现 Compact 转换与校验支持，不能只在提示词中声明组件名和 Props。
正式 Few-shot 用于表达可复用的协议与布局规则；外部批跑用例、批次编号和实跑报告留在本地。
