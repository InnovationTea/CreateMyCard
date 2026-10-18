# 布局模板参考

本目录存放历史布局模板，供后续维护模板体系时参考版式结构和视觉组织方式。

这些模板只作为视觉和布局参考，不作为协议依据。若模板中的字段、尺寸、主题、事件、图片或组件属性与 `docs/云侧方案设计.md`、A2UI profile、能力注册表或校验器冲突，以方案文档和云侧校验结果为准。

## 目录

- `2x2/three-modules/`：2x2 三段式信息布局。
- `2x2/two-split-half/`：2x2 双区块分栏布局。
- `2x4/action-sidebar/`：2x4 内容区 + 操作区布局。
- `2x4/dual-action-panel/`：2x4 信息区 + 双操作面板布局。

每个模板目录包含：

- `template.dat`：历史 A2UI DSL 示例。
- `preview.png`：对应视觉预览图。

## 使用约束

- 在线链路仍由微服务生成最终 DSL、CardSpec、校验和 artifact。
- 离线 Skill 的正式模板路由仍以 `assets/templates/index.json` 为准，本目录不进入自动模板选择。
- 主 Agent 不应直接复制这些历史模板内容生成正式产物。
- 后续如需将这些历史模板纳入正式模板，应先规范化为 `assets/templates/` 下的 manifest、`template.genui.jsonl`、`cardspec.json`，并同步更新模板索引和校验规则。
