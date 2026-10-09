# Fusion 极简协议兼容说明

兼容目标为当前仓库 `design-compact-dsl-fusion` 的组件合同、Compact 转换器与版本化视觉 Recipe。浏览器直接导入
`widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/runtime/visual-recipes-v1.json`，不再固定到旧提交，也不复制第三套高阶组件样式。

## 支持内容

保持“极简 DSL → A2UI → 图模型 → React”链路，不引入模型调用。

- Compact 输入中的基础布局组件只有 Row、Column、Stack；内容组件包含 Text、Image、Divider 和已登记高阶组件，不直接接受 Progress、Button、List 或 Checkbox。
- CardHeader、旧版 TimelineUnit，以及 PillButton、CircleButton、EmphasizedData、InfoBlock、ProgressCircle、ProgressLine2、TableText、TextBlock、CardButton、ProgressCircleSingle、EventCard、DataDisplay、TopTextBottomValue、SummaryList 均在转换阶段展开为标准 A2UI 基础组件；其中 Progress 和 Button 只可能作为高阶组件的展开结果出现。
- 其中 13 个组件的几何、字号、间距和圆角直接来自共享 `visual-recipes-v1`；SummaryList 与云侧转换器保持同一份固定原生展开。
- 数据元组写入嵌套对象/数组，支持读取父数组、JSON Pointer 转义、父级替换、零值与 false。
- `{{ ... }}` 支持路径、字符串、数值、布尔值、算术、比较、逻辑、三元、size；动作参数递归绑定。表达式使用受限语法解析，拒绝任意函数、属性访问、非有限数值及过深嵌套。
- 任意组件和容器支持点击；保留 clickToIntent / clickToDeeplink 的名称及参数，触发时解析最新数据。嵌套动作阻止冒泡，容器支持键盘操作。
- 五套融球配色与叠层、ARGB 颜色、渐变、百分比尺寸、SVG 染色、PNG 原色、环形/线性进度。

浏览器仅显示动作调用及解析参数。原生 Intent、Deeplink 的实际执行仍需宿主接入；不表示已验证 HarmonyOS 原生行为或像素一致性。

融球预览将生成玻璃层的原生模糊参数 210 映射为 CSS blur(24px)，避免整张小卡片被平均成单色；导出的 A2UI 仍保留 210。圆角同时使用 overflow 和显式 clip-path，防止 Chromium 的模糊合成层露出方角。

## 原始示例与兼容差异

两组各 15 个，共 30 个 DSL 保存在 `platform/fixtures/fusion-examples.json`，可以直接从页面选择；旧动作入口已同步为 PillButton。另有高阶组件示例保存在 `platform/fixtures/high-level-component-examples.json`，共同覆盖全部 14 个高阶组件。

| 示例 | 处理 |
| --- | --- |
| 常规 2x2 / 2x4 | 150×150 / 300×150 预览 |
| 2x4-V02、2x4-V05 | 原始内容区宽 296，使用 320×160 兼容画布，页面提示原因 |
| 2x4-V13 | 引用的 project_fill.svg 不在分支资源库中，补充本地文件夹 SVG，页面明确提示 |

154 个上游资源与 1 个本地补充图标随项目提供。其他缺失图片显示可识别的占位提示。

## 验证

- 自动化测试覆盖全部 30 个原始示例、高阶组件示例、14 个组件覆盖检查、共享 Recipe 关键几何、非法合同、数据解析、动作参数、表达式安全和图模型更新。
- SDK 图模型 mock 回归通过，无在线模型调用。
- 浏览器逐一切换 30 个示例，检查文本、残留模板、错误、缺失素材和文本边界；截图检查时间线、融球与进度布局。
- TypeScript 检查、Next.js 生产构建通过。

```powershell
cd platform
npm test
npx tsc --noEmit --incremental false
npm run build
```

主要入口：`platform/lib/mini-renderer.ts`（转换与校验）、`platform/lib/compact-components.ts`（高阶组件语义展开与共享 Recipe 读取）、`genui-sdk/interactions/src/expression.ts`（表达式解析）。
