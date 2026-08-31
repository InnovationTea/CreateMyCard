# Weather Provider Template

本目录是天气业务的 `card-provider-bundle/1` 资源。当前 Provider ID 为
`com.huawei.weather.cli`，通过 `ViewWeather` 读取 `/data/weather`，并声明 9 个
`WeatherOverview*` 业务模板。

## 文件职责

- `provider.json`：Provider、数据能力、数据根、Template 清单和分层规则入口。
- `layer-docs/first-layer.md`：天气字段和业务组件的首层规则。
- `layer-docs/second-layer.md`：二层 Template 与 Props 选择规则。
- `templates/weather-overview.cardtpl`：9 个天气模板的受信 CardTpl 源码。

天气数据 Schema 统一引用正式能力注册表，不在 Provider 目录保留历史 Schema 或独立样例副本。

Template 的主数据、次要数据和可选数据以 `provider.json#templates` 为准。`.cardtpl` 只能引用当前
Template 声明的数据路径；缺少任一主数据或次要数据时，该 Template 不进入候选。

Provider 资源、Search、CardTpl 和预览数据集的通用规则见：

- [Template 文档中心](../../../../docs/README.md)
- [Provider Template 契约](../../../../docs/provider-template-contract.md)
- [天气模板能力清单](../../../../docs/provider-template-capability-checklist.md#weatheroverview)

## 验证

在 `widget_service` 的父目录执行：

```bash
PYTHONPATH=widget_service/cloud widget_service/.venv312/bin/python -m pytest -q \
  widget_service/cloud/services/template_generation/tests
```

如需检查确定性预览，按
[Provider Template A2UI 预览数据集](../../../../docs/provider-template-preview-gallery.md)
生成全部模板样例。当前没有单独的 `validate_provider_bundle.py`；Provider Bundle 的严格加载和 CardTpl
编译由模块测试覆盖。
