# Weather Provider Template PoC

本目录是 `card-provider-bundle/1` 的最小可运行样例：

- `provider.json`：Provider、能力、数据 Schema 位置和模板入口；
- `schemas/`：上游没有可用 Schema 路径时的本地兜底示例；
- `templates/`：只含闭合声明式语法的 `.cardtpl`。

`dataSchema.path` 优先按云侧 `data` 根目录下的上游路径解析；上游文件不存在时，
再按 Bundle 内相对路径解析。`dataSchema.version` 标识 Schema 版本，
上游路径中必须包含该版本。
正式能力注册表仅被读取，不要求其他团队为 Provider Template 修改注册内容。

单字段使用 `Bind("city")`；同一行拼接多个 string binding 时使用受限的 TypeScript 风格
反引号语法，例如 `` `${condition}｜${airQuality}` ``。
`${...}` 内只能写本模板声明的 binding 名称。

从 `widget_service` 目录验证：

```bash
.venv/bin/python scripts/validate_provider_bundle.py \
  cloud/services/template_generation/resources/source/providers/weather
```

校验器只读取解析出的 Schema，检查 `.cardtpl` 使用的相对字段路径和类型。
请求运行时若缺少对应能力根或 TaskSpec 字段，只关闭该 Provider Template，
并继续使用正式能力和通用生成链路。

修改 `.cardtpl` 后必须同步更新 `provider.json` 中对应文件的 `sha256:` 摘要，再执行：

```bash
.venv/bin/python scripts/build_cardplan_bundle.py
PYTHONPATH=cloud .venv/bin/pytest -q tests/test_provider_template_bundle.py
```

`WeatherOverview@1` 已完成首轮 Python 影子对比并切换为默认生产路由。运行时只把 CardSpec
`writeResultTo` 下被模板声明的绑定叶子补回模型 TaskSpec；缺失、歧义或类型不符时仍在准入阶段关闭
该模板，保留正式能力和通用生成链路。
