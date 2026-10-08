# 卡片生成结果渲染器

这是调试平台的本地卡片预览子包，负责把生成链路输出的 JSONL/JSON 转成可交互的 Web 预览。输入编辑、artifact 解包、尺寸和缩放仍由本包管理；协议解析、UIGraph 和 React 组件绘制使用从仓库根目录 `render` 迁入的最小运行时。不承担 HarmonyOS 端侧校验、模型重试、截图或测评。

## 支持输入

- A2UI v0.9：`createSurface`、`updateComponents`、`updateDataModel` 对象行；
- Compact DSL：`[id, component, props, children]` 行和 DataModel 路径行；
- Design Compact DSL：在 Compact DSL 上增加 `design` token；
- JSONL、连续 JSON 值，以及包含 `genui`/`cardSpec`/`artifact` 字段的常见 artifact 外壳。

解析器会处理 DataModel 路径、受限表达式、动态子节点、基础组件和 13 个高阶组件，并推断 2×2（160×160）和 2×4（320×160）画布尺寸。高阶组件直接读取云侧 `visual-recipes-v1.json`，不在浏览器维护副本。

相对图片资源以 `/resources/` 为默认根目录，由 frontend/full 两种 Python 应用通过受目录约束的只读路由提供；Vite 开发服务提供等价本地中间件。外部图片由浏览器直接读取，失败时显示占位，不提供开放式服务端图片代理。点击动作只回传解析结果，不执行 Intent、Deeplink 或 URL 跳转。

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

`CardPreview` 用于统一工作台已经有输入编辑器的场景；`parseInput` 是无 DOM 的纯函数，便于接口调试结果导入、单元测试和状态检查。

迁入运行时位于 `card_renderer/runtime/`，来源和同步规则见其中的 `SOURCE.md`。根目录 `render` 保留为上游行为对照；同步运行时代码后必须重跑本包测试、平台回归和浏览器检查。

## 独立运行

```bash
npm install
npm run dev
npm run typecheck
npm run build
```

生产环境可将 `frontend/static` 的构建产物交给统一 FastAPI `/debug/` 静态入口；图片根目录通过 `assetBaseUrl` 配置，避免依赖迁移后的相对路径。

