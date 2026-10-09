# 极简 DSL 渲染器

本地渲染工具：极简 DSL → A2UI v0.9 → UIGraph → React。不需要模型或 API Key。

源码来自 [a2ui_render](https://gitcode.com/GenUI_Union/a2ui_render/tree/main) 的 `2adfedbe` 提交。本目录可独立安装和启动，仅用于本地协议预览。以下命令从 CreateMyCard 仓库根目录执行。

## 启动

完整的首次安装、开发/生产启动和故障处理步骤见 [启动说明](启动说明.md)。

需要 Node.js 18+ 和 npm 9+。

```powershell
cd render/genui-sdk
npm ci
cd ../platform
npm ci
npm run dev
```

打开 http://127.0.0.1:3000 。输入 DSL 后点击“渲染预览”，或按 Ctrl / Cmd + Enter。
可以设置预览尺寸、查看转换后的 A2UI。默认示例是 160 × 160 的发布会倒计时卡片。

## 协议

每条组件元组：`[ID, 类型, 属性, 子节点ID数组（可省略）]`。
每条数据元组：`[JSON Pointer 路径, 值]`。
支持 JSONL、多行 JSON 元组、JSON 元组数组和单个代码围栏。

```jsonl
["root","Column",{"width":"matchParent","height":"matchParent","padding":12},["title","days"]]
["title","Text",{"content":{"path":"/data/title"}}]
["days","Text",{"content":"剩余 {{ ${/data/days} + \" 天\" }}"}]
["/data/title","产品发布会"]
["/data/days",18]
```

- 普通字符串保留为字面量；`{"path":"/data/title"}` 绑定数据。
- 支持对象、数组下标、零值、布尔值和嵌套参数绑定。缺失路径显示为空并提示。
- 完整 `{{ ... }}` 表达式支持路径、字符串拼接、算术、比较、逻辑、三元和 `size()`，保留数值/布尔类型；使用受限解析器，不执行 JavaScript。
- 组件定义无需父节点优先；数据可以放在组件之前或之后。缺少节点、重复 ID 和循环引用会明确报错。
- `CardHeader`、旧版 `TimelineUnit`，以及 Fusion 的 14 个组件都会在转换阶段展开为标准 A2UI 基础组件；Compact 输入不再直接接受 Progress、Button、List、Checkbox 或旧动作组件。
- 高阶组件样式直接读取云侧 `runtime/visual-recipes-v1.json`，不在浏览器中维护第三套硬编码样式。
- 点击事件在本地展示解析后的参数；原生 intent 和 URL 跳转需要宿主接入，不会发起 LLM 请求。
- 支持五套融球背景、ARGB 渐变、SVG 染色、透明 PNG、线性与环形进度。

示例选择器内置 CreateMyCard 的 `Br_feature_fusion` 分支全部 30 个原始 few-shot，另有覆盖全部组件的 Runtime 示例；兼容差异见 [验证说明](docs/fusion-compatibility.md)。导入指定版本的参考仓库：

```powershell
node render/scripts/import-fusion-reference.mjs .
```

## 验证与构建

```powershell
cd render/platform
npm test
npx tsc --noEmit
npm run build
npm start
```

运行生产构建前停止开发服务。已移除平台的 LLM 请求接口、模型配置、Markdown 混排、批量测试及旧版协议转换页面。
核心组件、图模型、协议解析和交互 SDK 保留供渲染器使用。
