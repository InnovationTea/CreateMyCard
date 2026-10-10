# 调试平台 React 壳

`platform` 是 `debug_tools` 的统一 React/Vite 应用。它负责页面路由、连接配置、接口调用历史和模块间产物
传递；具体业务能力由 `end_to_end_debug/frontend`、`interface_debug/frontend` 和
`card_renderer/frontend` 提供。

## 页面路由

| 路由 | 页面 |
| --- | --- |
| `/debug/end-to-end` | 端到端调试 |
| `/debug/interface` | 接口调试 |
| `/debug/renderer` | 卡片渲染 |
| `/debug/batch` | 批量测试任务中心 |
| `/debug/settings` | 连接与公共请求配置 |

批跑详情、单样本 Trace、画廊捕获和插件看板使用独立子路由。未知路由会回到端到端调试页。

## 共享状态

平台 Context 统一维护：

- Main Agent 与微服务连接配置；
- 公共设备和版本参数；
- 当前微服务来源；
- 三个微服务接口的调用历史；
- 可传递给卡片渲染器的 artifact。

左侧“接口调用历史”只记录微服务调用的实际 request、`final`/`final_error` 和终态，不复制中间 WebSocket
帧。端到端 Agent 的普通事件保留在端到端页面内部。

浏览器配置保存到版本化的 `localStorage` 键 `ai-widget-debug-config:v1`。保存前会拒绝或清除地址中的用户
信息、hash 和常见凭据参数。API Key 不属于浏览器配置。

## 本地开发

先在一个终端启动 Python 后端：

```powershell
uv run debug_tools --mode full --host 127.0.0.1 --port 8888
```

再启动 Vite：

```powershell
cd debug_tools
npm install
npm run dev
```

打开 <http://127.0.0.1:5173/debug/>。Vite 将 Agent、健康检查、artifact 和批量测试 API 代理到
`127.0.0.1:8888`，但不会代理三个微服务 WebSocket；接口页面按浏览器配置直接连接微服务。

## 构建和检查

```powershell
cd debug_tools
npm run typecheck
npm test
npm run build
```

`npm run build` 只构建 `@widget-debug/platform`，但通过 workspace alias 打包三个前端业务模块，产物输出到
`debug_tools/dist/`。Python 的 `frontend` 和 `full` 模式均托管该目录，并为未知前端路由回退到
`dist/index.html`。

## 资源边界

卡片本地素材只通过 `/resources/` 和 `/background_assets/` 两个只读路由提供，服务端会校验路径必须位于
固定资源根内。外部图片由浏览器直接加载；平台不提供开放式图片代理。卡片点击动作只展示解析结果，不执行
Intent、Deeplink 或 URL 跳转。

统一启动与用户操作见 [`../README.md`](../README.md)，各业务模块的技术细节见相应子包 README。
