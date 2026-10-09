# 批跑后处理插件开发规范

插件位于 `debug_tools/postprocess_plugins/<pluginId>/`。每个目录包含 `plugin.json` 和 Python 入口；服务启动时
扫描清单，执行时才在独立子进程中加载脚本。插件只负责生产结构化数据和受限文件，调试平台依据清单自动
生成插件独立看板，不加载或执行插件提供的 HTML、JavaScript 或 React 代码。

## v2 清单

```json
{
  "apiVersion": "batch-postprocess-v2",
  "id": "my-plugin",
  "name": "我的插件",
  "version": "2.0.0",
  "entrypoint": "plugin.py",
  "dependence": ["prepare-data"],
  "timeoutSeconds": 300,
  "configSchema": {"type": "object", "properties": {}, "additionalProperties": false},
  "outputs": [
    {
      "key": "quality",
      "scope": "sample",
      "title": "质量明细",
      "dataType": "records",
      "renderer": "table",
      "required": true
    }
  ],
  "presentation": {
    "defaultView": "table",
    "sampleFields": [
      {"key": "score", "label": "得分", "type": "number", "sortable": true}
    ]
  }
}
```

`outputs` 是产物白名单。数据类型限于 `metrics`、`records`、`matrix`、`image`、`json`、`text`、`code`、
`diff`、`issues`、`file`、`link`；`renderer` 只能选择该类型允许的受控渲染提示。图表是 `records` 或
`matrix` 的显示方式，不能携带表达式、模板或前端代码。`presentation.defaultView` 仅支持 `table/gallery`；
`sampleFields` 声明样本索引读取的 `facts` 字段。

`id` 只能包含字母、数字、点、下划线和短横线，最长 80 个字符。`dependence` 是按声明顺序排列的插件
名称列表；宿主会自动补齐依赖、拒绝不存在或形成循环的依赖，并行运行彼此没有依赖关系的插件。插件的
`upstreamResults` 只包含其直接依赖结果，不包含用户同次勾选的其它独立插件。`configSchema` 使用 JSON Schema
2020-12，前后端均会校验。`entrypoint: "builtin"` 只供内置插件使用。

普通“开始后处理”只运行尚无执行历史的插件。依赖插件已有历史时，宿主将其最新规范化结果放入
`upstreamResults`，不会重复执行；只有用户点击该插件的“再次运行”时才创建新的执行记录。

## 函数与上下文

入口必须实现样本函数，可选实现数据集函数；可使用同步函数或 `async def`：

```python
def process_sample(context: dict[str, object]) -> dict[str, object]: ...

def process_dataset(context: dict[str, object]) -> dict[str, object]: ...
```

样本上下文包含 `apiVersion`、`scope`、`runId`、`sample`、只读的 `runDir/sampleDir/finalAttemptDir`、唯一
可写的 `outputDir`、已校验 `config` 和 `upstreamResults`。数据集上下文另含 `run` 与本插件的
`sampleResults`。宿主按批跑样本顺序执行样本函数，再执行一次数据集函数。

## v2 返回结果

```json
{
  "status": "success",
  "summary": "质量检查完成",
  "facts": {"score": 98.5, "labels": ["稳定", "完整"]},
  "artifacts": [
    {
      "key": "quality",
      "data": [{"item": "结构", "score": 100}]
    }
  ]
}
```

- `status` 只能为 `success`、`partial`、`failed` 或 `skipped`。
- `summary` 是一句纯文本摘要。
- `facts` 仅允许标量和字符串数组，用于索引、筛选与排序。
- `artifacts[].key` 必须存在于清单，作用域必须匹配；可内联 JSON，或以 `path` 引用当前
  `outputDir` 内真实存在的安全相对文件。必需产物在成功结果中不可缺失。
- 合法但暂无专用渲染器的数据会降级为只读 JSON；任何内容都不会作为 HTML 或脚本执行。

宿主统一校验 Schema、序列化和路径边界。样本异常、超时或无效结果会转为该样本的 `failed`，不会终止
其它样本或依赖图中的其它插件。新执行将摘要、数据集结果、逐样本结果与 `dashboard.json` 分开保存，避免详情接口
内联大产物。旧 `batch-postprocess-v1` 文件仍能通过只读适配器展示，但所有新执行只写 v2。

完整最小实现见 `example-metrics/`；覆盖全部受控数据类型和渲染方式的实现见
`complete-showcase/`；带独立评测标注、聚合指标和逐样本解释的实现见 `component-recall/`。
