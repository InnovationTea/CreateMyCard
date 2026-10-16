# PR #522 当前优化与最新 main 融合

## 已核对来源

- PR：InnovationTea/CreateMyCard #522，head 为 leolya 的 codex/compact-semantic-layout-2x4-v1。
- PR 原 head：3bb02a2；当前单例优化从该提交延续，包含 Q057、Q058、Q059、Q061、Q065 的通用修复。
- 2026-10-14 获取的主仓 main：a376ba445295d42bac055b035951252f185628bf。
- GitHub 显示 CONFLICTING；旧 HEAD 模拟合并显示七个冲突文件，保存当前优化后实际合并共十个。
- 审查指出 ProgressCircle 的双环/四环：语义节点禁止几何，但展开层未注入必需尺寸。

## 执行顺序与保护边界

1. 精确提交当前单例优化并建立本地备份，排除 env、输出、Trace 与无内容差异的生成文件。
2. 将最新 main 合入当前 PR 的继承分支，按职责逐块解决冲突，不回退 main 的组件、模板、素材或修复能力。
3. 由公共 Runtime 在高阶组件展开前按语义模板的实际参考槽位给 ProgressCircle 注入尺寸；
   模型仍不得填几何。保留既有最小环径、标签、读数和容量检查，2×2 与旧输入行为不变。
4. 同步 Prompt/测试：保留示例的输入、字段、动作与配色，仅适配语义结构及主仓格式更新；
   不增加测试集答案，不新增批量模型调用。
5. 验证完整转换、绑定、布局与修复，区分主仓既有失败和新增回归。检查合并后代码与 main 的差异。
6. 快进推送到 PR 现有源分支，更新说明并再次读取 GitHub 合并状态；不直接合入主仓 main，
   不强推改写远端历史，不新建 PR，不代替审查者 Approve。

## 重点兼容

- 原始语义源与展开源不能混用；素材恢复、Artifact 保存、编辑和反馈须保留真实模型源。
- 主仓新增主题/组件行为、PNG 素材候选及排版规范不能被旧文档或构建产物回退。
- 单例结果是开发验证，不是稳定性或泛化统计；原失败与未闭环事项仍如实保留。

## 冲突裁决与补充兼容

- Core、组合、布局和阶段指令保留 2×4 Layout/Region/Group；2×2 保留主仓协议。
- 保留主仓 Plan 的素材分配、2×2 anchor 独立支撑事实条件和连续阶段消息历史。
- SecondaryBody 采用主仓新合同：单行 14fp/19vp、多行 12fp/16vp，不再生成 role；
  示例只调整结构与样式，十个输入、事实、路径、动作、素材和配色逐项与 main 核对。
- 保留 Q057 的标题加数量 Badge，以及当前 InfoBlock 文字规范、完整标签预算和覆盖修复。
- 素材还原同时使用“不展开语义源”和主仓“允许归档内部组件”入口；默认模型权限不变。
- 修复 JSX 标准输出误按 Compact 源保存的交叉回归；模板源沿用主仓专用解析入口。
- 语义双环、四环和四格内的直接 ProgressCircle 按模板槽位注入数值宽高；
  带图标标题、标题加 Badge、双行标题及可选底部按钮都参与预算，环径不足仍报错。
- 并未新增用户测试集答案、额外 few-shot、Case ID 路由或 DeepSeek 请求。

## 验证记录

- 相关链路第一组：571 passed、41 subtests passed。
- 跨入口补充回归：61 passed；双环/四环新增完整转换测试 9 项全部通过。
- 最终 widget_service/tests：2151 passed、19 failed、16 skipped、59 subtests passed。
- 独立 main a376ba4 对照：2049 passed、19 failed、16 skipped、59 subtests passed。
  两边失败测试集合完全相同，未新增失败。19 项集中于旧接口重试样例、Hero/低阶 Text 断言、
  编辑 Prompt、运行配置/能力清单和旧 ActionUnit 等，不能报告为全量通过；本 PR 不顺带修复它们。
- 十个 main 既有 2×4 few-shot：输入和业务字段对照通过，完整 Processor 全部通过。
- 渲染器：Badge 4 项、截断 20 项、双渲染 Runtime DOM 一致性 3 项，共 27 项通过。
- 修改 Python 文件 Ruff、差异空白检查、Renderer Runtime 同步检查通过。
- 未重新跑实际模型生成或全量视觉稳定性评测，不将单元测试数量替代效果改善结论。

## 备份与最新上游

- 优化快照提交 b4dea9c；本地备份 codex/backup-pr522-casewise-before-main-20261014。
- 重新核对时主仓增加 ca27f1f（仅耳机数据的蓝牙连接说明），继续合入，不回退素材与模板更新。
- 合入 ca27f1f 后能力说明、语义转换、素材、Badge、Prompt 与 Few-shot 定向回归：325 passed。
- 合并针对现有 PR 源分支，不直接写 InnovationTea/CreateMyCard 的 main。
