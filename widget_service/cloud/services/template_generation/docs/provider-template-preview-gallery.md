# Provider Template A2UI 预览数据集

## 目标

该数据集用于逐个检查正式业务 Provider Template 的端侧显示效果。生成过程直接读取 Provider Bundle 与
`.cardtpl`，在本地可信展开器中生成标准 A2UI，不调用 LLM，也不经过在线微服务。

数据集覆盖 106 个业务模板，不包含 7 个布局模板和 2 个 Action 模板：

- HeroTitle：1 个，使用 2×2 卡片容器，模板内容高度 24vp。
- HeroContent：1 个，使用 2×2 卡片容器，模板内容高度 54vp。
- Support：18 个，使用 2×2 卡片容器，模板内容高度 68vp；原子预览省略可选内部事件。
- Compact：13 个，使用 2×2 卡片容器，模板内容高度 68vp。
- Hero：31 个，使用 2×2 卡片容器，模板内容高度 124vp。
- Full：31 个，使用 2×2 卡片容器，模板内容高度 136vp。
- WideHero：2 个，使用 4×2 卡片容器，模板内容高度 124vp。
- WideFull：9 个，使用 4×2 卡片容器，模板内容高度 136vp。

卡片容器统一保留 12vp 安全边距。Compact、Hero 和 WideHero 未占满的底部区域保持空白，用来检查原子模板
本身的占位效果；该预览不代表第一层最终组合，正式组合仍遵循对应后缀的 Action 与布局规则。

## 生成

在 `widget_service` 的父目录执行：

```bash
PYTHONPATH=widget_service/cloud widget_service/.venv312/bin/python \
  widget_service/cloud/services/template_generation/tools/generate_template_preview_dataset.py /tmp/template_gallery
```

输出目录包含：

- `manifest.json`：模板 ID、业务、Provider、能力、后缀、卡片尺寸、内容高度，以及主数据、次要数据和可选数据。
- `T001.json` 至 `T106.json`：每个模板独立的 A2UI 消息数组，固定包含 `createSurface`、
  `updateComponents` 和 `updateDataModel`。

Support 原子预览省略内部事件关联图标；必需素材仍分别使用耳机本体、耳机盒和心率对应图标，普通电量不借用图标。
单业务天气只允许匹配状态的图标；当前多云样例没有对应状态资源，省略图标，不使用温度计兜底。
18 个 Support 的业务根节点左右内边距均为 8vp，主文本 14vp/700、辅助文本 12vp/400，
独立右侧图标固定 24×24vp；外层预览容器仍保留 12vp 安全边距。
手机电量与耳机充电 Support 的环均在右侧并使用 40vp、环内图标 16vp；
手机电量图标可选，耳机充电盒图标必需。其他环形进度与环内图标尺寸保持各模板定义。
步数与平均心率的数值和单位合并为一个主文本，通过 `Expr` 保留数值类型及运行时绑定；
倒计时先展示剩余天数主文本，再展示可信标题辅助文本。
心率 Support 的两行 Text 直接放入内容 Column，不附加主行 Row 或辅助文本强制宽度；
两行保留单行省略与最小约束，右侧图标保持 24vp。
样例数据只用于视觉预览。绑定路径和类型来自正式 Provider 契约，素材路径必须能在目标 HAP 的
`resources/base/media` 中解析。

## 验证

```bash
PYTHONPATH=widget_service/cloud widget_service/.venv312/bin/pytest -q \
  widget_service/cloud/services/template_generation/tests/test_template_preview_dataset.py
```

测试会校验模板总数与后缀分布、三条 A2UI 消息、原子模板占位高度、数据层级互斥和端侧素材集合。
