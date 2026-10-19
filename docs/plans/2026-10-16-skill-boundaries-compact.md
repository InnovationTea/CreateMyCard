# Skill 边界与提示词精简 Implementation Plan

> 本任务在当前会话按此计划逐项执行；不依赖未安装的 superpowers 执行工具，不开启子代理。

**Goal:** 在不改变DSL、语义布局能力、参数、固定规格、模型调用和校验算法的前提下，减少模型上下文中的重复与实现细节，并评估2×2/2×4质量。

**Architecture:** 保留prompt_source目录、manifest尺寸过滤和阶段加载。每项规则有唯一责任文件；总表只做选择索引，细则拥有Props/容量/示例/注意事项。描述、责任边界和迁移记录放在prompt标记外。Plan只定义工具字段和候选语义，Repair只定义按实际反馈修复及有界授权，不复制生成目录。

**Tech Stack:** Markdown片段、现有Python加载器与pytest、官方DeepSeek、原生接口重试、build_gallery.mjs。

---

## 1. 冻结输入与基线

- main `fd8ce68`；独立分支 `codex/skill-boundaries-compact-20261016`。
- 使用 `debug_tools/Datasets/20261016_request_baseline` 的52条2×2和36条2×4。
- 2×4复用同日同配置32条基线，补Q054/Q056/Q060/Q062；2×2新跑52条。
- 官方deepseek-flash、temperature0.7/top_p0.9、thinking关闭；每轮修复5次，原生最多两轮。
  外层每条只发一个请求；Few-shot开、筛选关、runtime prompt context关；其它策略保持main默认实验配置。

## 2. 责任划分

| 文件 | 唯一责任 | 不承担 |
|---|---|---|
| core.md | 输入/JSONL/绑定/事件/素材来源/全局色板 | 单组件选型、槽位几何实现、修复轮次 |
| information/common.md | 事实与对象、主辅并列、去重取舍、动作归属 | 组件名、字号、布局参数 |
| information/尺寸.md | 相应尺寸的信息密度考虑 | 字段删除配额 |
| components/common.md | 通用组件语义、Props、共同容量、单组件示例 | 父布局路由、重复组合和尺寸实现 |
| components/尺寸.md | 尺寸差异、尺寸专属组件 | 重讲通用语义与全局协议 |
| combinations/common.md | 多组件关系成立条件与排除条件 | 单组件Props、父布局模板 |
| combinations/尺寸.md | Group可用变体和组合映射 | 重复父布局表、旧Sub名映射 |
| layouts/common.md | 画布与容量检查 | Column/Row/权重操作、业务强路由 |
| layouts/尺寸.md | 父布局/Region、角色顺序、限定组件、容量及骨架模板 | 重复组件定义、业务few-shot |
| composition.md | 综合信息/组件/组合/布局的短决策与提交检查 | 复制其它Skill细则 |
| plan.md | 工具字段填写、原子事实、软候选、素材分配、可选composition | 再讲所有组件/颜色/几何 |
| repair.md | 反馈定位、修改范围、授权、修复顺序、提交 | 全量组件目录与重复协议 |
| fewshots/尺寸.md | 现有端到端输入输出 | 本轮不新增/改写测试相近案例 |

## 3. 实施与验证

1. 在模型片段外增加description/责任边界；保留文件路径与片段名，避免修改运行逻辑。
2. 精简Core；把2×2特有图标门禁放组件尺寸文件、2×2融球选择放尺寸信息片段。
3. 通用组件属性表保留全部当前生成可用字段和真实类型；移除仅历史兼容属性。
   完整单组件例子保留，不添加更贴近测试集的新业务内容。
4. 统一组件细则为选择条件、属性、容量、示例、注意事项；尺寸文件只写差异和专属组件。
5. 收敛组合、布局、Composition、Plan和Repair的重复条款；受控几何只保留选择所需的尺寸预算。
6. 对旧/新片段建立字段、布局名、变体、示例和必需规则核对；添加行为合同测试，不只检查旧原句。
7. 运行提示词加载、语义编译、Props、反馈、原生接口重试相关测试，Ruff和git diff --check。
8. 确认services、Runtime合同、renderer、数据、few-shot、模型配置未变。
9. 冻结新提示词后，完整串行跑52+36条，保存全部原生Trace，官方渲染后生成两个基线对照页。

## 4. 验收和限制

- 对比服务状态、原生轮数、累计修复/时延、两版Plan并集下的可见字段和Action、重复绑定、视觉问题及token。
- main修复后放宽非Action事实覆盖的既有行为不改；success不能充当完整性指标。
- 覆盖率不是人工真值；绑定齐全不等于文字可读；一次采样不能证明稳定等价。
- 不改生成产物、不挑选重跑、不引入测试答案。主仓保持不动，未经用户要求不推送。
