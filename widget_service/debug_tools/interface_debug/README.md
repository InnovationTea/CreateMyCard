# 接口调试（`@widget-debug/interface`）

这个子包把 `websocket_debugger` 分支原来的手工页面拆成可嵌入统一工作台的 React 组件，当前只覆盖正式的三个工具接口。调用在浏览器中直接建立 WebSocket，不经过调试后端代理：

- `getWidgetCapabilityOverview`
- `getDataCapabilitySchemas`
- `generateWidgetCardCompactDsl`

入口组件是 `InterfaceDebugger`，稳定属性如下：

```tsx
<InterfaceDebugger
  transportBase="ws://127.0.0.1:8855/api/v1/ws/tools"
  config={sharedConfig}
  onCallStart={({ operation, request }) => recordCall({ operation, request, status: 'pending' })}
  onCallFinish={(id, result) => updateCall(id, result)}
  onArtifact={(artifact) => renderer.open(artifact)}
/>
```

`transportBase` 可以是同源路径或完整 `ws://`/`wss://` 地址，组件会在其后追加接口名称；统一平台使用连接配置中的 `toolWsBaseUrl`。为兼容旧平台壳，还支持 `socketBasePath` 别名。组件不会启动、代理或管理 8855 工具服务，也不会调用来源分支的 `/ws/agent/chat` 智能体协议。

平台壳将 `agentWsUrl`（Main Agent）和 `toolWsBaseUrl`（三个微服务）分开配置。`bundleName`、协议版本、设备和分页字段从共享配置注入；会话 ID、交互 ID、设备时间等动态值在每次调用生成。独立使用该子包时可只传 `InterfaceDebugConfig` 的同名字段。

## 功能

- 三个接口 Tab，各自保存请求表单状态；通用设备/会话信封按共享配置构造。
- 一次调用监听 `start`、`partial`、`command`、`final`、`final_error` 帧，但调用记录只在 `final`/`final_error` 完成；`onCallStart` 收到实际发送的 request 包络，`onCallFinish` 收到最终帧、`finalStreamContent` 和归一化 response。中间帧不会写入平台左栏共享历史。
- `final.streamContent` 支持 JSON、JSONL fenced block、Python repr 以及 `data={...}` 旧消息包装；解析过程不使用 `eval`。
- 统一平台把 request/final output 发布到 `navigation-rail` 下半部，供接口调试、端到端和卡片渲染模块跨路由选中复用；解析结果以可展开树展示，字段可勾选并生成请求片段。
- 提供 `dataCapabilityIds`、`candidateDataBindings`、`candidateAssetIds`、`candidateEventCandidates` 和“选中内容”快速构建；构建结果可回填到业务参数 JSON。
- 解析到 artifact 后调用 `onArtifact`，供卡片渲染器显式接收；不会在浏览器中代理任意 `artifactUrl` 下载。

## 调用边界

- operation 只允许 `getWidgetCapabilityOverview`、`getDataCapabilitySchemas`、`generateWidgetCardCompactDsl`；地址末尾由组件追加固定 operation，不接受任意路径。
- HTTPS 页面只允许 `wss://`；相对路径按当前页面 host 转换为 `ws(s)://`。服务端必须允许当前页面 Origin，并由部署网络限制可访问的微服务地址。
- 浏览器等待 final 的默认总超时为 180 秒。收到 `final` 或 `final_error` 后关闭该次连接；连接错误、服务端关闭、非 JSON 和超时通过 `onCallFail` 报告。若该调用来自端到端 Agent，浏览器回传的结果还会由 Agent 工具桥校验调用 ID、operation 和大小。
- 不启动调试后端时，该组件仍可直接调用微服务；端到端 Agent 会话是独立链路。

## 与平台共享状态的最小适配

统一平台通过 `ToolCallRecord` 保存以下字段：`operation`、`source: "interface"`、`startedAt`、`finishedAt`、`request`、`finalFrame`、`finalStreamContent`、`response`、`callId`、`runId` 和 `error`。`response` 至少包含 `requestId`、`operation`、`status`、`errorCode`、`error`、`data`；不要把每个 WebSocket 中间帧复制到共享状态。

## 本地检查

```powershell
cd widget_service\debug_tools
npm install
npm --workspace @widget-debug/interface run typecheck
npm --workspace @widget-debug/interface run test
```

统一平台通过 `@widget-debug/interface` workspace 依赖导入该组件。
