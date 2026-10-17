# Render 运行时来源与同步说明

本文档记录 Debug Tools 卡片渲染器对仓库其它目录的文件级依赖、复制关系和本地适配。更新根目录
`render`、云侧视觉配置或素材后，应先按本文档判断影响范围，再同步代码并执行验证。除非特别说明，
下文路径均相对仓库根目录 `CreateMyCard/`。

## 依赖总览

| 类型 | 外部来源 | Debug Tools 使用位置 | 关系与更新触发条件 |
| --- | --- | --- | --- |
| Graph | `render/genui-sdk/graph/src/` | `debug_tools/card_renderer/runtime/graph/src/` | 由 `sync:renderer-runtime` 确定性同步。节点、DataModel、surface 或 graph command 行为变化时同步。 |
| Parser | `render/genui-sdk/parser/src/` | `debug_tools/card_renderer/runtime/parser/src/` | 由 `sync:renderer-runtime` 确定性同步。A2UI v0.9、JSONL、Compact command 或容错行为变化时同步。 |
| Components | `render/genui-sdk/components/src/` | `debug_tools/card_renderer/runtime/components/src/` | 由 `sync:renderer-runtime` 确定性同步；仅保留下述图片代理差异。 |
| Interactions | `render/genui-sdk/interactions/src/` | `debug_tools/card_renderer/runtime/interactions/src/` | 由 `sync:renderer-runtime` 确定性同步。表达式、路径绑定、事件上下文或 action dispatch 变化时同步。 |
| Renderer | `render/genui-sdk/renderer/src/` | `debug_tools/card_renderer/runtime/renderer/src/` | 由 `sync:renderer-runtime` 确定性同步。registry、`renderTree`、动态子节点、循环或 TextInput 写回行为变化时同步。 |
| 视觉 Recipe | `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/runtime/visual-recipes-v1.json` | 由云侧 Python 高阶组件模块读取 | 单一真实来源，不复制。Recipe 版本、组件参数或布局几何变化会立即影响构建，需同步适配展开逻辑和测试期望。 |
| 布局契约 | `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/runtime/layout-contracts-v1.json` | 当前不被浏览器运行时直接导入 | 间接契约。更新后应检查生成 DSL 是否引入新布局字段，并评估 parser、components、renderer 是否需要同步；不要为它创建本地副本。 |
| 卡片素材 | 根目录 `resources/`，按云侧素材清单同步到 `render/platform/public/resources/` | Python `/resources/...` 路由和 Vite 本地中间件直接读取共享目录 | 使用 `scripts/sync_assets.py --sync` 更新登记素材；运行时不复制到 dist。目录迁移时同步静态路由与 Vite 中间件。 |
| 背景素材 | `render/platform/public/background_assets/` | Python `/background_assets/...` 路由和 Vite 本地中间件直接读取 | 实时目录依赖，不复制。目录或命名规则变化时同步两套服务入口和测试。 |
| Concert One 字体 | `render/platform/public/fonts/ConcertOne-Regular.ttf` | `debug_tools/card_renderer/frontend/src/assets/ConcertOne-Regular.ttf` | 二进制副本。源文件哈希变化时重新复制并执行 Vite build。 |
| HarmonyOS 字体 | `render/platform/public/fonts/harmonyos/` | CSS `/fonts/harmonyos/` 引用、Python 资源路由和 Vite 本地中间件 | 实时目录依赖，不复制。字体目录变化时同步 `styles.css`、`debug_tools/static_site.py` 和两处 Vite 配置。 |

运行时包名仍使用 `@genui-sdk/graph`、`@genui-sdk/parser`、`@genui-sdk/components`、
`@genui-sdk/interactions` 和 `@genui-sdk/renderer`。这些包在
`debug_tools/card_renderer/runtime/*/package.json` 中以 workspace 源码包形式暴露，
并由 `debug_tools/package.json` 和 `package-lock.json` 管理；这里的 package manifest
是 Debug Tools 适配文件，不应直接用 `render/genui-sdk/*/package.json` 覆盖。

`debug_tools/card_renderer/frontend/src/parser.ts`、`render.tsx` 和 `CardRenderer.tsx` 是
Debug Tools 自己的集成层，不是根 `render` 文件的副本：它们分别负责输入外壳解包与尺寸推断、graph
克隆与资源地址适配、编辑器和状态回调。上游 API 变化时应修改这些调用点，不能用上游页面组件覆盖。

## 必须保留的本地差异

同步外部源码时不能直接覆盖以下适配：

1. `runtime/components/src/extended/ExtendedMedia.tsx`
   - 根 `render` 会把外部 HTTP(S) 图片改写到 Next.js `/img-proxy`。
   - Debug Tools 不提供开放式代理，外部图片必须保持浏览器直读；`resources/...` 才改写为本地
     `/resources/...`，加载失败显示占位。
2. Compact 转换不从根 `render/platform/lib/` 同步；由 `/debug/renderer/convert` 调用现有 Python 转换器。
   高阶组件、设计 token 和布局规则统一在云侧模块维护，不恢复前端编译副本。
3. 公共 `parseInput` 返回 Promise；调用方须等待转换并处理取消、失败和截图就绪状态。
4. `runtime/*/package.json`
   - 这些文件是供 Debug Tools npm workspace 直接引用源码的极简 manifest，不是上游构建配置副本。

Concert One 字体当前与来源一致；如果同步后出现差异，应在本节
补充差异原因。生产目录 `debug_tools/dist/` 只能通过构建生成，禁止从 `render` 手工复制。

## 同步流程

不要手工复制运行时源码。根 `render/genui-sdk` 更新后，在 `debug_tools/` 执行：

```powershell
npm run sync:renderer-runtime
```

该命令只同步五个包的 `src/`，会清理来源中已删除的陈旧文件，并在生成
`components/src/extended/ExtendedMedia.tsx` 时确定性应用“不使用 `/img-proxy`”的本地转换。普通测试通过
`pretest` 自动执行只读的 `check:renderer-runtime`；运行时发生未登记漂移时测试会在执行前失败。

### 1. 确认上游变化范围

使用 Git 比较目标更新前后的文件，至少检查：

```powershell
git diff --name-status <旧版本> <新版本> -- render/genui-sdk render/platform/lib render/platform/public
git diff --name-status <旧版本> <新版本> -- widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/runtime
```

如果外部更新尚未提交，则直接比较来源和本地副本。目录之间的预期差异应仅为“必须保留的本地差异”中
列出的文件；出现其它差异时先确认是新上游行为还是遗漏同步。

### 2. 按映射同步源码

- `graph`、`parser`、`components`、`interactions`、`renderer` 只同步各自的 `src/`。
- 不复制根 `render` 的 Next.js 页面、`llm-client`、Prompt、Skill、分析器、构建产物或整套 HarmonyOS 字体。
- 不同步根 `render/platform/lib/` 的 Compact 编译、高阶展开或 Design 样式副本。
- 上游新增跨包 import 时，同时更新对应 `runtime/*/package.json` 和
  `card_renderer/frontend/package.json`；然后在 `debug_tools/` 执行 `npm install` 更新锁文件。
- 上游删除或重命名文件时，`sync:renderer-runtime` 会删除非本地适配的陈旧副本；同步前先查看上游差异，
  确认删除属于运行时源码变更。

同步或只读检查分别使用：

```powershell
npm run sync:renderer-runtime
npm run check:renderer-runtime
```

脚本执行后仍应查看 `git diff`，确认同步范围和上游变更一致；不再需要手工恢复 `ExtendedMedia`。

### 3. 同步配置、素材与测试

- `visual-recipes-v1.json` 由 Python 转换器读取；云侧版本变化后运行 Python 转换回归和 Web 请求链路测试。
- `layout-contracts-v1.json` 更新时检查新增字段是否已经由 Python 转换器和组件 registry 支持。
- `resources/` 与 `background_assets/` 是实时读取目录，只需同步引用和测试；目录根变化时必须保持
  frontend/full Python 服务与 Vite 开发服务一致，并继续拒绝 `..` 等目录穿越。
- Concert One 字体只有哈希变化时才重新复制。HarmonyOS 字体通过受限静态路由复用，不把根 `render` 的字体目录迁入 Debug Tools。
- 同步上游测试和 fixture 时保留 Debug Tools 特有的 artifact 解包、尺寸、`assetBaseUrl`、`onArtifact`、
  `onAction`、TextInput/DataModel 和错误边界测试。

### 4. 检查对外兼容

同步后确认以下接口没有无意变化：

- `parseInput` 和 `RendererDocument`；
- `CardRendererProps`、`CardPreviewProps`、`RendererDocument` 的现有导入路径；
- `onArtifact`、`onAction`、`auto/2x2/2x4`、缩放和 artifact 选择行为；
- `/resources/...`、`/background_assets/...` 在 frontend/full/Vite 三种模式下的一致性；
- 点击动作只回传，不执行 Intent、Deeplink、URL 或 LLM 请求。

## 必须执行的验证

在 `debug_tools/` 运行：

```powershell
npm.cmd run typecheck
npm.cmd run check:renderer-runtime
npm.cmd test -- --run
npm.cmd run build
```

在仓库根目录运行 Python 路由回归：

```powershell
uv run ruff check debug_tools/static_site.py debug_tools/end_to_end_debug/backend/server.py widget_service/tests/test_debug_batch_testing.py
uv run pytest widget_service/tests/test_debug_batch_testing.py -q
```

最后在仓库根目录执行：

```powershell
git diff --check
```

还需用浏览器至少检查一张基础组件卡、一张高阶组件卡、一张含本地图片的卡、一次点击动作和一次
TextInput/DataModel 编辑；检查桌面与窄屏布局，并确认控制台没有新增错误。同步提交或交付说明中应记录
上游 Git 版本、实际同步的映射项、保留的本地差异和验证结果，作为下一次同步的比较基线。

## 云侧登记素材同步

云侧各能力快照 `asset_capabilities.json` 的 `src` 是同步范围，源文件位于仓库根目录 `resources/`。
在仓库根目录执行：

```powershell
.\.venv\Scripts\python.exe debug_tools/scripts/sync_assets.py --sync
.\.venv\Scripts\python.exe debug_tools/scripts/sync_assets.py --check
```

脚本按 src 去重，先确认源文件完整，再原样补齐或覆盖浏览器共享目录与真机工程
`debug_tools/a2ui_render/entry/src/main/resources/base/media/`，不修改素材路径或文件名大小写。
不删除清单外的应用图标等工程资源。`--check` 逐文件比较 SHA-256，缺失或内容不同返回非零。
当前清单为 141 张，两端各有 141 张登记素材，摘要与源文件一致。浏览器资源实时读取，无需复制到 dist；
真机须重新构建 HAP，资源变化会使设备构建缓存失效。
