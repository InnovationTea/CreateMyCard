# 模板契约

## 文件闭环

每个正式模板目录必须包含：

- `manifest.json`：模板约束。
- `template.genui.jsonl`：默认组件树。
- `cardspec.json`：静态 CardSpec 骨架。

模板必须在 `assets/templates/index.json` 注册，并通过 `assets/templates/manifest.schema.json` 校验。

## manifest 字段

- `schemaVersion`：固定为 `template-v1`。
- `id`、`size`、`pattern`、`summary`：稳定标识和用途。
- `sourceProvenance`：只记录来源观察，不形成运行时依赖。
- `useWhen`、`avoidWhen`：路由提示；`avoidWhen` 命中时直接排除。
- `layout.canvas/root/safeArea/regions`：固定画布、root、安全区和 region 几何。
- `componentVariants`：region 可选组件树；默认变体必须与骨架一致。
- `slots`：内容路径、角色、region、必选性、字符上限和允许绑定。
- `defaultStyleProfile`、`allowedStyleProfiles`、`colorRoles`：风格约束。
- `allowedEdits`、`forbiddenEdits`、`deleteRules`：修改和删减规则。

## region 规则

每个 region 声明 `id`、`role`、`parent`、`width`、`height`、`required`、`maxChildren` 和 `allowedComponents`。region 外框不可变，内部变体的根组件必须属于允许组件，且不得突破宽高预算。

变体只解决同一职责的呈现差异：

- 动作 region：`Button`、`Row(Image + Text)`、静态支撑或删除。
- 身份 region：`Text` 或 `Row(Image + Text)`。
- 支撑 region：单行 Text、两行 Column 或同尺寸 metric/tile。
- 主视觉 region：只使用模板语义指定的 Text、Image 或 Progress，不跨类型自由替换。

## 槽位删除

只有 `required: false` 的槽位可以删除。删除后必须同步：

1. 从父组件 `children` 删除组件 ID。
2. 删除不再可达的组件。
3. 删除对应 DataModel 字段。
4. 删除只服务该槽位的数据绑定或事件。
5. 按 manifest 的替代尺寸重新分配相邻组件，不临场发明宽高。

## 新增模板

新增前确认它解决现有模板无法承载的布局关系。维护顺序固定为：更新 `方案设计.md`、添加模板目录、更新索引、运行全模板严格校验、补充路由和失败用例。
