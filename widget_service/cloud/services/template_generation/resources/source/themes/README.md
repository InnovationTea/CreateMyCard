# Theme Bundle

本目录按主题独立维护卡片样式。每个主题目录包含：

- `theme.json`：主题 ID、适用能力和场景、真实颜色值、`rootStyle`、主辅内容色、`actionStyle`；
  布局专用主题还声明 `supportedLayoutIds` 和对应布局样式；
- `first-layer.md`：仅在该主题成为候选时加载的首层选择规则。

`base/theme-base.json` 只保存所有主题共享的 UX Token、尺寸预算，以及“组件类型到颜色属性”的映射。
它不得保存某个具体主题的颜色、根样式或 Action 样式。根资源目录不再维护 `theme-profiles.json` 或
`advanced-component-ux-registry.json`。

主题字段直接使用 `#AARRGGBB` 等最终真实值，不使用 `text-on-accent` 一类语义占位符。编译阶段按以下
边界应用样式：

1. `rootStyle` 只合并到最终卡片根节点；主题显式值优先于 `themes/base` 的默认 UX Token。
2. `primaryColor` 只为普通内容组件缺失的颜色属性补值；`supportContentColor` 由 Provider 对辅助内容显式
   引用。两个字段都保存最终真实颜色，可以不同，以表达主内容与辅助内容层级。
3. `actionStyle` 只保存受信 Action Template 的背景色和内容色。Action Template 节点已经显式声明的高度、
   圆角、字号和字重不得被 Theme 覆盖；Action 子树不再套用普通内容的 `primaryColor`。
4. `fusionBallStyle` 完整保存一套融球颜色及允许的 `businessIds`，只在业务、数据能力、`Full`、`Hero` 或
   `Compact` 后缀均匹配的单业务 `2x2` 产物中生效；Support、多业务和 Wide 形态不应用融球包装。
5. `supportContentStyle` 保存双 Support 内容块的背景色和圆角，只由 `TwoSupportLayout` 引用；业务
   Support 模板不各自声明容器底色。

CardTpl 和 Tersel 可以使用 `$theme('primaryColor')`、
`$theme('supportContentColor')`、`$theme('progressColor')`、`$theme('progressBackgroundColor')`、
`$theme('actionStyle.backgroundColor')` 和
`$theme('actionStyle.contentColor')`、`$theme('supportContentStyle.backgroundColor')` 和
`$theme('supportContentStyle.borderRadius')`。解析器只接受 `themes/base/theme-base.json` 声明的路径，并在编译时
确定性替换为当前主题真实值；最终产物不能残留 `$theme`。Provider 负责显式区分主内容和辅助内容，服务端
不根据布局或文本特征猜测。

新增主题时需新建独立目录，并保证目录名与 `themeProfileId` 一致；`firstLayerRule.path` 必须是主题目录内的
相对 Markdown 路径，`rootStyle.padding` 必须为 `12`。修改后需重建 CardPlan 清单并运行 Template
Generation 测试。

当前生产资源包含五套融球主题、九套业务非融球主题，以及一套 `TwoSupportLayout` 专用统一主题。
布局专用主题不进入第一层 LLM 主题候选。当前生产 Search 在 `2x2` 只接收单业务及零到两个 Action，
多业务会在进入第二层前显式拒绝；`2x2-two-support` 仅保留给兼容的 LLM 选择链路和原子预览，
由服务端在确定选出两个 Support 业务后按布局和能力切换。应用使用时长主题的固定颜色为：
白色底、10% 黑色到透明白色渐变、90% 黑色主内容、60% 黑色辅助内容、蓝色 Action 内容和 10% 蓝色
Action 背板。天气非融球主题使用 `#FFE5EDFE` 纯色背景，不配置渐变；主内容和 Action 内容为
`#FF1F4799`，辅助内容为 `#991F4799`，Action 背板为 `#330A59F7`。
睡眠非融球主题使用 `#FFEDE6FF` 纯色背景，不配置渐变；主内容、Action 文本和图标为 `#FF401F99`，
辅助内容和睡眠进度为 `#991F4799`，Action 背板为 `#33564AF7`。
运动非融球主题使用从 `#FFED6F21` 到 `#FFF9A01E` 的线性渐变背景；主内容为 `#FFFFFFFF`，辅助内容和
运动进度为 `#99FFFFFF`，Action 文本和图标为 `#FFED6F21`，Action 背板为 `#FFFFFFFF`。
耳机音乐非融球主题使用 `#FFF0FFE6` 纯色背景，不配置渐变；主内容、Action 文本和图标
为 `#FF52991F`，辅助内容和耳机电量环进度为 `#9952991F`，Action 背板为
`#3364BB5C`。当前耳机 Provider 不提供曲目、播放状态或播放进度数据。
日历信息与日程非融球主题使用 `#FFE5EDFE` 纯色背景，不配置渐变；主内容、Action 文本和图标为
`#FF1F4799`，辅助内容及进度颜色为 `#991F4799`，Action 背板为 `#331F4799`。当前 Calendar Provider
没有进度组件，`progressColor` 作为主题协议能力预留给后续显式引用。

手机电量普通主题保留 `battery-yellow` 兼容 ID，使用 `#FFFFF3E6` 米黄背景；主内容、Action 文本和进度为
`#FF1F8F99`，辅助内容为 `#991F8F99`，进度轨道和 Action 背板为 `#331F8F99`。
赛事倒计时非融球主题使用从 `#FFED6F21` 到 `#FFF9A01E` 的线性渐变背景；主内容为 `#FFFFFFFF`，
辅助内容及协议预留进度颜色为 `#99FFFFFF`，Action 文本和图标为 `#FFED6F21`，Action 背板为
`#FFFFFFFF`。当前 Countdown Provider 没有进度组件。
设备非融球主题使用 `#FFFFFFFF` 底色及 `#1AF9A01E` 到 `#00FFFFFF` 的线性渐变；主内容为
`#E6000000`，辅助内容和环内图标为 `#99000000`，环形进度为 `#FFF9A01E`，Action 文本和图标为
`#FF0A59F7`，Action 背板为 `#1A0A59F7`。
