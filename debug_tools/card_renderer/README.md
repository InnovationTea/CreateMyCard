# 卡片生成结果渲染器

这是调试平台的本地卡片预览子包，负责把生成链路输出的 JSONL/JSON 转成可交互的 Web 预览。输入编辑、artifact 解包、尺寸和缩放仍由本包管理；协议解析、UIGraph 和 React 组件绘制使用从仓库根目录 `render` 迁入的最小运行时。不承担 HarmonyOS 端侧校验、模型重试、截图或测评。

## 支持输入

- A2UI v0.9：`createSurface`、`updateComponents`、`updateDataModel` 对象行；
- Compact DSL：`[id, component, props, children]` 行和 DataModel 路径行；
- Design Compact DSL：在 Compact DSL 上增加 `design` token；
- JSONL、连续 JSON 值，以及包含 `genui`/`cardSpec`/`artifact` 字段的常见 artifact 外壳。

Compact DSL 和 Design Compact DSL 的基础组件、高阶组件、设计 token 和数据路径统一由现有 Python 转换器处理。
浏览器只解析 A2UI、维护 UIGraph 并绘制基础组件；不再维护 Compact 编译器或高阶组件展开副本。

所有渲染入口（自动渲染、手工渲染、批跑详情、DSL 画廊和截图页面）调用本地
`POST /debug/renderer/convert`，直接复用云侧 `compact_dsl_a2ui_converter.py`。
预览使用返回的实际尺寸；转换失败保留原输入并显示错误，不回退到浏览器转换。
普通渲染保留原始 DSL，“Python 转换并渲染”额外将编辑器内容更新为完整 A2UI。
选择“自动”时按 Compact 的组件宽度推断 2×2 或 2×4，也可以手工指定画布。
转换同时传递原产物或同次请求的客户端版本；裸 DSL 可在“客户端版本”输入框指定。
历史预览和截图保留各次执行的版本。缺失、非法或过低版本仍按 Python 门禁关闭融球，不能伪造高版本。
Compact 预览需要 Python 调试后端，frontend/full 模式均可用；两种 Vite 开发入口均代理转换接口。
已有 A2UI 或 Graph JSONL 在浏览器直接解析，不请求转换后端。

相对图片资源以 `/resources/` 为默认根目录，由 frontend/full 两种 Python 应用通过受目录约束的只读路由提供；Vite 开发服务提供等价本地中间件。浏览器字体通过 `/fonts/harmonyos/` 复用根 `render` 的 HarmonyOS Sans 与 HarmonyOS Sans SC 资源，保持字宽、字重和换行效果一致。外部图片由浏览器直接读取，失败时显示占位，不提供开放式服务端图片代理。点击动作只回传解析结果，不执行 Intent、Deeplink 或 URL 跳转。

## 导出

```tsx
import {
  CardRenderer,
  CardPreview,
  parseInput,
  type RendererDocument,
} from '@widget-debug/card-renderer';

<CardRenderer
  initialValue={artifact.genui}
  assetBaseUrl="/resources/"
  onArtifact={(document: RendererDocument) => store.publish(document)}
/>
```

`CardPreview` 接收已经解析的文档。`parseInput` 无 DOM 依赖，返回 `Promise<RendererDocument>`，
调用方必须 `await parseInput(source, { cardSize, appVersion, signal })`；`conversionUrl` 可覆盖默认接口地址。
宿主可用 `resolveAppVersion(artifact, request)` 提取原版本，并通过 `CardRenderer.appVersion` 传入。

迁入运行时位于 `card_renderer/runtime/`，来源和同步规则见其中的 `SOURCE.md`。根目录 `render` 保留为上游行为对照；同步运行时代码后必须重跑本包测试、平台回归和浏览器检查。

## 独立运行

```bash
npm install
npm run dev
npm run typecheck
npm run build
```

生产环境可将 `frontend/static` 的构建产物交给统一 FastAPI `/debug/` 静态入口；图片根目录通过 `assetBaseUrl` 配置，避免依赖迁移后的相对路径。

