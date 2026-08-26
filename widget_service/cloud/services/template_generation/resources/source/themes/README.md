# Theme Bundle

本目录按主题独立维护卡片样式。每个主题目录包含：

- `theme.json`：主题 ID、适用能力和场景、真实颜色值、`rootStyle`、主辅内容色、`actionStyle`；
- `first-layer.md`：仅在该主题成为候选时加载的首层选择规则。

`base/theme-base.json` 只保存所有主题共享的 UX Token、尺寸预算，以及“组件类型到颜色属性”的映射。
它不得保存某个具体主题的颜色、根样式或 Action 样式。根资源目录不再维护 `theme-profiles.json` 或
`advanced-component-ux-registry.json`。

主题字段直接使用 `#AARRGGBB` 等最终真实值，不使用 `text-on-accent` 一类语义占位符。编译阶段按以下
边界应用样式：

1. `rootStyle` 只合并到最终卡片根节点；主题显式值优先于 `themes/base` 的默认 UX Token。
2. `primaryColor` 只为普通内容组件缺失的颜色属性补值；`supportContentColor` 由 Provider 对辅助内容显式
   引用。非融球主题的两个字段取相同值。
3. `actionStyle` 只应用到受信 Action Template，控制 Action 根容器背景、尺寸、圆角和内部文本、图标颜色。
   Action 子树不再套用普通内容的 `primaryColor`。
4. `fusionBallStyle` 完整保存一套融球颜色及允许的 `businessIds`，只在业务、数据能力、`Full`/`Hero` 后缀
   均匹配的单业务 `2x2` 产物中生效；多业务、Compact 和 Wide 形态不应用融球包装。

CardTpl 和 TerseDSL-Nested-2 可以使用 `$theme('primaryColor')`、
`$theme('supportContentColor')`、`$theme('actionStyle.backgroundColor')` 和
`$theme('actionStyle.contentColor')`。解析器只接受 `themes/base/theme-base.json` 声明的路径，并在编译时
确定性替换为当前主题真实值；最终产物不能残留 `$theme`。Provider 负责显式区分主内容和辅助内容，服务端
不根据布局或文本特征猜测。

新增主题时需新建独立目录，并保证目录名与 `themeProfileId` 一致；`firstLayerRule.path` 必须是主题目录内的
相对 Markdown 路径。修改后需重建 CardPlan 清单并运行 Template Generation 测试。
