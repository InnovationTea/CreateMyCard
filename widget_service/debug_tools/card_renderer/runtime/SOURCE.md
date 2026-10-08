# Render 运行时来源与同步说明

本文档记录 Debug Tools 卡片渲染器对仓库其它目录的文件级依赖、复制关系和本地适配。更新根目录
`render`、云侧视觉配置或素材后，应先按本文档判断影响范围，再同步代码并执行验证。除非特别说明，
下文路径均相对仓库根目录 `CreateMyCard/`。

## 依赖总览

| 类型 | 外部来源 | Debug Tools 使用位置 | 关系与更新触发条件 |
| --- | --- | --- | --- |
| Graph | `render/genui-sdk/graph/src/` | `widget_service/debug_tools/card_renderer/runtime/graph/src/` | 源码副本。节点、DataModel、surface 或 graph command 行为变化时同步。 |
| Parser | `render/genui-sdk/parser/src/` | `widget_service/debug_tools/card_renderer/runtime/parser/src/` | 源码副本。A2UI v0.9、JSONL、Compact command 或容错行为变化时同步。 |
| Components | `render/genui-sdk/components/src/` | `widget_service/debug_tools/card_renderer/runtime/components/src/` | 源码副本。基础组件、Extended 组件、样式转换或表单行为变化时同步；同步后必须重新应用下述图片代理差异。 |
| Interactions | `render/genui-sdk/interactions/src/` | `widget_service/debug_tools/card_renderer/runtime/interactions/src/` | 源码副本。表达式、路径绑定、事件上下文或 action dispatch 变化时同步。 |
| Renderer | `render/genui-sdk/renderer/src/` | `widget_service/debug_tools/card_renderer/runtime/renderer/src/` | 源码副本。registry、`renderTree`、动态子节点、循环或 TextInput 写回行为变化时同步。 |
| Mini DSL 编译 | `render/platform/lib/mini-renderer.ts` | `widget_service/debug_tools/card_renderer/frontend/src/runtime/mini-renderer.ts` | 源码副本并带本地诊断增强。Compact DSL 编译、高阶组件展开入口或 Design 处理顺序变化时同步。 |
| 高阶组件展开 | `render/platform/lib/compact-components.ts` | `widget_service/debug_tools/card_renderer/frontend/src/runtime/compact-components.ts` | 源码副本，仅调整视觉 Recipe 的相对导入路径。高阶组件清单、Recipe 参数映射或展开结构变化时同步。 |
| Design 样式 | `render/platform/lib/design-handle.ts` | `widget_service/debug_tools/card_renderer/frontend/src/runtime/design-handle.ts` | 当前为原样副本。Design token、渐变、背景素材或样式合并规则变化时同步。 |
| 视觉 Recipe | `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/runtime/visual-recipes-v1.json` | 由 `frontend/src/runtime/compact-components.ts` 直接导入 | 单一真实来源，不复制。Recipe 版本、组件参数或布局几何变化会立即影响构建，需同步适配展开逻辑和测试期望。 |
| 布局契约 | `widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/runtime/layout-contracts-v1.json` | 当前不被浏览器运行时直接导入 | 间接契约。更新后应检查生成 DSL 是否引入新布局字段，并评估 parser、components、renderer 是否需要同步；不要为它创建本地副本。 |
| 卡片素材 | `render/platform/public/resources/` | Python `/resources/...` 路由和 Vite 本地中间件直接读取 | 实时目录依赖，不复制。新增或替换素材会直接生效；目录迁移时必须同时修改 `debug_tools/static_site.py`、`debug_tools/platform/vite.config.ts` 和资源兼容测试。 |
| 背景素材 | `render/platform/public/background_assets/` | Python `/background_assets/...` 路由和 Vite 本地中间件直接读取 | 实时目录依赖，不复制。目录或命名规则变化时同步两套服务入口和测试。 |
| Concert One 字体 | `render/platform/public/fonts/ConcertOne-Regular.ttf` | `widget_service/debug_tools/card_renderer/frontend/src/assets/ConcertOne-Regular.ttf` | 二进制副本。源文件哈希变化时重新复制并执行 Vite build。HarmonyOS 字体不复制，继续使用系统字体回退。 |
| Render 示例 | `render/platform/src/example-dsl.ts` | `widget_service/debug_tools/card_renderer/frontend/tests/fixtures/example-dsl.ts` | 测试副本。示例协议或受支持组件变化时同步。 |
| Render 测试数据 | `render/platform/fixtures/high-level-component-examples.json`、`fusion-examples.json` | `widget_service/debug_tools/card_renderer/frontend/tests/fixtures/` | 测试副本。新增高阶组件、Fusion 样例或素材引用时同步。 |
| Render 测试逻辑 | `render/platform/tests/mini-renderer.test.ts`、`high-level-components.test.ts`、`fusion-compatibility.test.ts` | `frontend/tests/render-*.test.ts` | 适配后的测试副本。上游测试新增协议行为时同步相应用例，不以覆盖方式丢弃 Debug Tools 专属断言。 |

运行时包名仍使用 `@genui-sdk/graph`、`@genui-sdk/parser`、`@genui-sdk/components`、
`@genui-sdk/interactions` 和 `@genui-sdk/renderer`。这些包在
`widget_service/debug_tools/card_renderer/runtime/*/package.json` 中以 workspace 源码包形式暴露，
并由 `widget_service/debug_tools/package.json` 和 `package-lock.json` 管理；这里的 package manifest
是 Debug Tools 适配文件，不应直接用 `render/genui-sdk/*/package.json` 覆盖。

`widget_service/debug_tools/card_renderer/frontend/src/parser.ts`、`render.tsx` 和 `CardRenderer.tsx` 是
Debug Tools 自己的集成层，不是根 `render` 文件的副本：它们分别负责输入外壳解包与尺寸推断、graph
克隆与资源地址适配、编辑器和状态回调。上游 API 变化时应修改这些调用点，不能用上游页面组件覆盖。

## 必须保留的本地差异

同步外部源码时不能直接覆盖以下适配：

1. `runtime/components/src/extended/ExtendedMedia.tsx`
   - 根 `render` 会把外部 HTTP(S) 图片改写到 Next.js `/img-proxy`。
   - Debug Tools 不提供开放式代理，外部图片必须保持浏览器直读；`resources/...` 才改写为本地
     `/resources/...`，加载失败显示占位。
2. `frontend/src/runtime/compact-components.ts`
   - 视觉 Recipe 必须从云侧版本化文件直接导入。
   - 同步上游代码后只调整相对路径，禁止复制 `visual-recipes-v1.json` 到 Debug Tools。
3. `frontend/src/runtime/mini-renderer.ts`
   - Debug Tools 的 JSON 解析错误包含底层原因和最多 120 字符的输入片段，便于批跑与手工调试。
   - 上游解析流程变化时合并该诊断能力，不要退回只有行号的错误。
4. `runtime/*/package.json`
   - 这些文件是供 Debug Tools npm workspace 直接引用源码的极简 manifest，不是上游构建配置副本。

`frontend/src/runtime/design-handle.ts` 和 Concert One 字体当前与来源一致；如果同步后出现差异，应在本节
补充差异原因。生产目录 `widget_service/debug_tools/dist/` 只能通过构建生成，禁止从 `render` 手工复制。

## 同步流程

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
- 同步 `mini-renderer.ts`、`compact-components.ts`、`design-handle.ts` 后，逐项重新应用本地差异。
- 上游新增跨包 import 时，同时更新对应 `runtime/*/package.json` 和
  `card_renderer/frontend/package.json`；然后在 `widget_service/debug_tools/` 执行 `npm install` 更新锁文件。
- 上游删除或重命名文件时，不要机械覆盖或递归删除。先用 `rg` 确认 Debug Tools 没有额外引用，再删除
  明确废弃的本地副本。

从仓库根目录复制新增或修改文件时，可以按下列映射逐包执行；该操作不会删除本地文件，删除项仍需按
上一条规则单独确认：

```powershell
Copy-Item -Recurse -Force 'render/genui-sdk/graph/src/*' 'widget_service/debug_tools/card_renderer/runtime/graph/src/'
Copy-Item -Recurse -Force 'render/genui-sdk/parser/src/*' 'widget_service/debug_tools/card_renderer/runtime/parser/src/'
Copy-Item -Recurse -Force 'render/genui-sdk/components/src/*' 'widget_service/debug_tools/card_renderer/runtime/components/src/'
Copy-Item -Recurse -Force 'render/genui-sdk/interactions/src/*' 'widget_service/debug_tools/card_renderer/runtime/interactions/src/'
Copy-Item -Recurse -Force 'render/genui-sdk/renderer/src/*' 'widget_service/debug_tools/card_renderer/runtime/renderer/src/'
```

复制后应立即恢复本地差异，再查看 `git diff`；不要在恢复差异之前运行构建或提交。

### 3. 同步配置、素材与测试

- `visual-recipes-v1.json` 是直接依赖，文件内容不复制；若版本文件改名，需同时修改
  `compact-components.ts` 的 import、`VISUAL_RECIPE_VERSION` 和相关测试。
- `layout-contracts-v1.json` 更新时检查新增字段是否已经由 `compileMiniDsl` 和组件 registry 支持。
- `resources/` 与 `background_assets/` 是实时读取目录，只需同步引用和测试；目录根变化时必须保持
  frontend/full Python 服务与 Vite 开发服务一致，并继续拒绝 `..` 等目录穿越。
- Concert One 字体只有哈希变化时才重新复制。不要把根 `render` 的 HarmonyOS 字体目录迁入 Debug Tools。
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

在 `widget_service/debug_tools/` 运行：

```powershell
npm.cmd run typecheck
npm.cmd test -- --run
npm.cmd run build
```

在 `widget_service/` 运行 Python 路由回归：

```powershell
.venv\Scripts\ruff.exe check debug_tools/static_site.py debug_tools/end_to_end_debug/backend/server.py tests/test_debug_batch_testing.py
.venv\Scripts\python.exe -m pytest tests/test_debug_batch_testing.py -q
```

最后在仓库根目录执行：

```powershell
git diff --check
```

还需用浏览器至少检查一张基础组件卡、一张高阶组件卡、一张含本地图片的卡、一次点击动作和一次
TextInput/DataModel 编辑；检查桌面与窄屏布局，并确认控制台没有新增错误。同步提交或交付说明中应记录
上游 Git 版本、实际同步的映射项、保留的本地差异和验证结果，作为下一次同步的比较基线。
