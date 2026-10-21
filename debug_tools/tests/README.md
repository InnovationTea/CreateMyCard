# Debug Tools 测试

调试工具测试统一放在本目录。`widget_service/tests/` 仅维护微服务自身的测试。
测试辅助文件与专用夹具同样随测试存放，业务源码和生产脚本不存放测试用例。

| 目录 | 用途 |
| --- | --- |
| `python/` | 批跑、数据集、后处理、截图、配置和 Trace 等后端及集成回归 |
| `frontend/platform/` | 调试平台页面、组件、状态与测试辅助文件 |
| `frontend/card_renderer/` | 卡片解析、渲染和运行时一致性 |
| `frontend/interface/` | 接口调试解析与传输 |
| `node/` | 桌面桥接逻辑单元测试 |
| `browser/` | 质量评估与离线画廊浏览器冒烟 |
| `fixtures/card_renderer/` | 渲染器专用输入样例 |

## Python

在仓库根目录安装开发依赖 `uv sync --group dev` 后运行：

```shell
python -m pytest debug_tools/tests/python -q
python -m pytest widget_service/tests -q
```

仓库根目录直接执行 `python -m pytest` 会收集两套测试；在 `widget_service/` 执行时只收集微服务测试。
跨云侧集成测试使用根目录配置提供的云侧导入路径，公共初始化固定同名 `core` 包的来源。
CI 使用独立任务执行两套 Python 测试。`test_test_layout.py` 防止微服务用例重新导入调试工具。

## 前端与 Node

先在 `debug_tools/` 安装依赖 `npm ci`。前端测试继续使用各工作区的配置，无需移动业务源码。
渲染一致性测试还需要在 `render/genui-sdk/` 安装依赖 `npm ci`。
在仓库根目录运行：

```shell
npm --prefix debug_tools test
npm --prefix debug_tools run typecheck
node --test debug_tools/tests/node/desktop_bridge.test.cjs
```

## 浏览器

以下命令在仓库根目录运行，需要本机 Edge，或使用环境变量
`WIDGET_DEBUG_GALLERY_BROWSER_EXECUTABLE` 指定 Chromium 浏览器可执行文件。
API 使用固定测试输入，不调用生产模型。

```shell
node debug_tools/tests/browser/web_quality.test.mjs
node debug_tools/tests/browser/quality_smoke.test.mjs
node debug_tools/tests/browser/quality_inputs.test.mjs
node debug_tools/tests/browser/check_postprocess_gallery.mjs <HTML路径> <输出目录> [浏览器路径]
```

最后一项需要已有离线画廊文件；测试输出应写入临时目录，不能提交运行产物。

## 历史夹具来源

`fixtures/component-recall.json` 保留原 16 个代表样本的组件召回真值，来自
`fd8ce689^` 的 `debug_tools/Datasets/request_dataset/evaluation/component-recall.json`。
该数据集已移除，文件只作为历史格式回归夹具，不代表当前批跑数据集的标注。
截图历史隔离用例从插件返回的产物路径读取截图，兼容现行导出命名。
