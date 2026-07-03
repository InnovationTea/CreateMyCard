# 色彩 Token 系统

本文件校验颜色是否合法。视觉色板可以决定情绪和色族。非图片颜色优先回溯到 HarmonyOS 语义 token、`ohos_id_color_*`、`multi_color_*` 或 `multi_color_aux_*`；当具体场景需要更细腻的表面色、氛围渐变或高级感时，可以在官方 token 色族基础上声明少量场景拓展色。当前端侧不支持语义 token 渲染，最终 DSL 必须写映射或拓展后的 `#RRGGBB` 或 `#AARRGGBB` 色值；内部设计理由仍保留 token 名称、拓展来源和角色。

## 校验目标

写 DSL 前只需在内部确认：

- 每个非图片颜色都有来源：HarmonyOS 语义 token、`ohos_id_color_*`、`multi_color_*`、`multi_color_aux_*`，或符合本文规则的场景拓展色。
- DSL 中的颜色属性只输出映射后的 `#RRGGBB` 或 `#AARRGGBB`，不直接输出 token 名称、`ohos_id_color_*`、`multi_color_*` 或 `multi_color_aux_*` 字符串。
- 深浅模式使用同一 token 名，只切换官方 light/dark 值。
- 前景/背景配对符合本文规则。
- 渐变 stop 都来自官方来源或合规场景拓展色，且只使用线性渐变。
- 状态色只服务真实状态。
- 没有无法说明来源、场景和用途的颜色；如无法说明，改用可回溯 token 或删除该颜色。
- 背景颜色的**放置位置**不在本文范围：背景字段必须落在 `root.styles`（或 root 下真实背景组件），不得放 `createSurface`，见 [`../core-rules.md`](../core-rules.md) 与 [`../protocol/protocol.md`](../protocol/protocol.md)。

## 阻塞项

以下任一项失败都不能交付：

- 非图片颜色既无法回溯到官方 token、`ohos_id_color_*` 或官方多彩色来源，也无法用合规场景拓展色说明来源、场景和用途。
- DSL 颜色属性直接输出 token 名称、`ohos_id_color_*`、`multi_color_*` 或 `multi_color_aux_*`，而不是映射后的 hex。
- 深浅模式使用不同语义名，而不是同一 token 切换值。
- 普通背景上误用 `font_on_*`。
- 饱和/渐变背景上叠加第二个高饱和彩色前景。
- 状态色被用作整卡主题，且状态不是卡片主目的。
- 常规提醒或轻建议误用 `warning` / `alert`。
- 渐变 stop 含无场景依据的手调色、机械插值色、无来源 alpha 变体、径向装饰或 bokeh/orb。
- 同一卡片出现两个以上主场景色族。

## 来源优先级

1. 优先使用本表中的 token 名称和 light/dark 值，输出 DSL 时写入对应模式的 hex 值。
2. 如果输入或源规范给出 `ohos_id_color_*`，先映射到等价 token；无法映射时只在内部保留 `ohos_id_color_*` 作为来源名，并使用其官方 light/dark hex 值，不要把源 ID 直接写进 DSL。
3. 如果官方 token 无法表达具体场景的精致表面（如朝阳暖雾、雨天玻璃、薄荷运动、夜间睡眠、音乐氛围），可以创建场景拓展色；拓展色必须基于一个主色族或中性背景族，且只服务 root、重点面、半透明背板或渐变 stop。
4. 多彩色优先使用 `multi_color_01..11` 和 `multi_color_aux_01..11`；允许从它们派生低饱和、高明度、低对比的场景表面色，但不得派生第二个高饱和主色。
5. 状态色只用于真实状态；常规提示、建议、倒计时和轻提醒不自动使用 `warning` / `alert`。
6. 深浅模式必须使用同一 token 名或同一场景拓展色名，只切换对应 light/dark 值；若只产出单一 DSL，至少在内部记录 light 来源。

## 场景拓展色板

当官方 token 表不足以支撑场景质感时，可以在内部声明 `scenePalette`，最终 DSL 仍只写 hex。声明时必须满足：

- `scene`: 具体场景，而不是抽象风格词；例如 `weather.morning.cool`、`weather.morning.warm`、`fitness.mint`、`music.ambient`、`sleep.night`。
- `anchors`: 2-4 个物理或文化锚点；例如晨雾、薄云、奶油纸、跑道、薄荷饮、夜灯、唱片封套。
- `baseSources`: 使用的官方 token、`ohos_id_color_*`、`multi_color_*` 或 `multi_color_aux_*`；拓展色必须与这些来源保持同一主色族或中性表面关系。
- `derivedRoles`: 每个拓展色的用途，例如 `rootStart`、`rootEnd`、`softPanel`、`actionFill`、`dividerWash`；不要用 `prettyBlue`、`warm1` 这类无用途命名。
- `bounds`: 拓展色应低饱和、高明度、低对比；除主 CTA 外，不新增高饱和色。`2x2` 最多 2 个拓展色，`2x4` 最多 3 个拓展色。

拓展色适用范围：

- 允许：root 背景、重点面、弱背板、线性渐变 stop、轻分隔层。
- 谨慎：CTA 背景；只有品牌动作、确认动作、运动开始、导航等强动作可用实色。
- 禁止：正文色、状态语义色、错误/警告/成功判断色、多个互相无关的主题色。

推荐派生方向：

- 天气晨间：从 `background_primary/background_secondary` 加入低饱和冷蓝或暖米表面，形成轻柔空气感。
- 雨雪天气：从 `background_secondary/background_tertiary` 加入低饱和蓝灰表面，避免高饱和蓝。
- 运动健康：从 `multi_color_04` 或 `multi_color_aux_03/04` 派生薄荷浅表面，CTA 可用 `confirm` 或 `multi_color_04`。
- 音乐耳机：从 `brand`、`multi_color_06/07` 或中性背景派生轻氛围表面，避免同时使用多个高饱和娱乐色。
- 睡眠夜间：从 `background_tertiary`、`multi_color_01/06` 派生暗色或柔紫表面，文字使用 on-color 或中性前景。

场景拓展色仍需通过可读性和克制检查：如果去掉该颜色后卡片更清楚，或颜色只是装饰而不服务场景、层级或动作，则不要使用。

## 完整 Token 值

### 语义与文字

| Token | Light | Dark |
| --- | --- | --- |
| `brand` | `#ff0a59f7` | `#ff317af7` |
| `warning` | `#ffe84026` | `#ffd94838` |
| `alert` | `#ffed6f21` | `#ffdb6b42` |
| `confirm` | `#ff64bb5c` | `#ff5ba854` |
| `font_primary` | `#e5000000` | `#e5ffffff` |
| `font_secondary` | `#99000000` | `#99ffffff` |
| `font_tertiary` | `#66000000` | `#66ffffff` |
| `font_fourth` | `#33000000` | `#33ffffff` |
| `font_emphasize` | `#ff0a59f7` | `#ff317af7` |
| `font_on_primary` | `#ffffffff` | `#ffffffff` |
| `font_on_secondary` | `#99ffffff` | `#99ffffff` |
| `font_on_tertiary` | `#66ffffff` | `#66ffffff` |
| `font_on_fourth` | `#33ffffff` | `#33ffffff` |

### 图标

| Token | Light | Dark |
| --- | --- | --- |
| `icon_primary` | `#e5000000` | `#e5ffffff` |
| `icon_secondary` | `#99000000` | `#99ffffff` |
| `icon_tertiary` | `#66000000` | `#66ffffff` |
| `icon_fourth` | `#33000000` | `#33ffffff` |
| `icon_emphasize` | `#ff0a59f7` | `#ff317af7` |
| `icon_sub_emphasize` | `#660a59f7` | `#66317af7` |
| `icon_on_primary` | `#ffffffff` | `#ffffffff` |
| `icon_on_secondary` | `#99ffffff` | `#99ffffff` |
| `icon_on_tertiary` | `#66ffffff` | `#66ffffff` |
| `icon_on_fourth` | `#33ffffff` | `#33ffffff` |

### 背景与组件层

| Token | Light | Dark |
| --- | --- | --- |
| `background_primary` | `#ffffffff` | `#ffe5e5e5` |
| `background_secondary` | `#fff1f3f5` | `#ff191a1c` |
| `background_tertiary` | `#ffe5e5ea` | `#ff202224` |
| `background_fourth` | `#ffd1d1d6` | `#ff2e3033` |
| `background_emphasize` | `#ff0a59f7` | `#ff317af7` |
| `comp_foreground_primary` | `#ff000000` | `#ffe5e5e5` |
| `comp_background_primary` | `#ffffffff` | `#ff202224` |
| `comp_background_primary_contrary` | `#ffffffff` | `#ffe5e5e5` |
| `comp_background_gray` | `#fff1f3f5` | `#ffe5e5ea` |
| `comp_background_secondary` | `#19000000` | `#19ffffff` |
| `comp_background_tertiary` | `#0c000000` | `#0cffffff` |
| `comp_background_emphasize` | `#ff0a59f7` | `#ff317af7` |
| `comp_background_neutral` | `#ff000000` | `#ffffffff` |
| `comp_emphasize_secondary` | `#330a59f7` | `#33317af7` |
| `comp_emphasize_tertiary` | `#190a59f7` | `#19317af7` |
| `comp_divider` | `#33000000` | `#33ffffff` |
| `comp_common_contrary` | `#ffffffff` | `#ff000000` |
| `comp_background_focus` | `#fff1f3f5` | `#ff000000` |
| `comp_focused_primary` | `#e5000000` | `#e5ffffff` |
| `comp_focused_secondary` | `#99000000` | `#99ffffff` |
| `comp_focused_tertiary` | `#66000000` | `#66ffffff` |

### 交互态

| Token | Light | Dark |
| --- | --- | --- |
| `interactive_hover` | `#0c000000` | `#0cffffff` |
| `interactive_pressed` | `#19000000` | `#19ffffff` |
| `interactive_focus` | `#ff0a59f7` | `#ff317af7` |
| `interactive_active` | `#ff0a59f7` | `#ff317af7` |
| `interactive_select` | `#330a59f7` | `#33317af7` |
| `interactive_click` | `#19000000` | `#19ffffff` |

### 多彩色

| Token | Light | Dark |
| --- | --- | --- |
| `multi_color_01` | `#564af7` | `#5f58c7` |
| `multi_color_02` | `#46b1e3` | `#4796c4` |
| `multi_color_03` | `#61cfbe` | `#5aada0` |
| `multi_color_04` | `#64bb5c` | `#5ba854` |
| `multi_color_05` | `#a5d61d` | `#86ad53` |
| `multi_color_06` | `#ac49f5` | `#8c55c2` |
| `multi_color_07` | `#e64566` | `#d64966` |
| `multi_color_08` | `#0a59f7` | `#317af7` |
| `multi_color_09` | `#ed6f21` | `#db6b42` |
| `multi_color_10` | `#f9a01e` | `#e08c3a` |
| `multi_color_11` | `#f7ce00` | `#d1a738` |
| `multi_color_aux_01` | `#8981f7` | `#5550a6` |
| `multi_color_aux_02` | `#86c5e3` | `#467794` |
| `multi_color_aux_03` | `#92d6cc` | `#4c7a73` |
| `multi_color_aux_04` | `#92c48d` | `#5c8059` |
| `multi_color_aux_05` | `#bddb69` | `#6b8052` |
| `multi_color_aux_06` | `#c386f0` | `#634794` |
| `multi_color_aux_07` | `#e67c92` | `#a14a5c` |
| `multi_color_aux_08` | `#e87361` | `#9c554b` |
| `multi_color_aux_09` | `#ed955f` | `#9e644f` |
| `multi_color_aux_10` | `#f9bc64` | `#9e7349` |
| `multi_color_aux_11` | `#f5dc62` | `#997e39` |

## OhOS ID 映射入口

- `ohos_id_color_palette1..11` 映射到 `multi_color_01..11`。
- `ohos_id_color_palette_aux1..11` 映射到 `multi_color_aux_01..11`。
- `ohos_id_color_text_primary/secondary/tertiary` 映射到 `font_primary/secondary/tertiary`。
- `ohos_id_color_text_*_contrary` 映射到对应 `font_on_*`。
- `ohos_id_color_primary/secondary/tertiary/fourth` 映射到对应 `icon_*`。
- `ohos_id_color_background/sub_background` 映射到 `background_primary/background_secondary`。
- `ohos_id_color_warning`、`ohos_id_color_alert`、`ohos_id_color_connected` 映射到 `warning`、`alert`、`confirm`。
- `ohos_id_color_click_effect`、`ohos_id_color_hover`、`ohos_id_color_focused_*` 映射到 `interactive_*` 或 `comp_focused_*`。

若一个 `ohos_id_color_*` 没有明确映射，内部保留源 ID 并使用其官方 light/dark hex 值；不要发明替代 token 名，也不要把源 ID 直接写进 DSL。

## 前景/背景配对

普通背景：

- 使用 `font_primary/secondary/tertiary/fourth` 与 `icon_primary/secondary/tertiary/fourth`。
- 有意义的高亮可用 `font_emphasize` / `icon_emphasize`。
- 不使用 `font_on_*`、纯黑/纯白手写值或彩色前景堆叠。

品牌/高强调背景：

- 使用 `font_on_primary/secondary/tertiary`、`icon_on_primary/secondary/tertiary`。
- 不用 `font_emphasize`、`icon_emphasize`、黑色前景或低对比彩色前景。

饱和/渐变背景：

- 使用 on-color 或中性前景。
- 不把 `warning`、`alert`、`confirm`、`font_emphasize`、`multi_color_*` 直接作为饱和背景上的第二高饱和前景。
- 如果状态必须显示，把状态放入中性背板内。

中性背板：

- 使用 `comp_background_secondary` / `comp_background_tertiary` 承载弱分组、按钮磨砂层和轻提示。
- 使用 `comp_divider` 或组件透明层做边界，不手写自定义灰色。

## 渐变校验

- 每个 stop 必须是本表 token、`ohos_id_color_*`、`multi_color_*`、`multi_color_aux_*` 对应的确切 hex 值，或符合“场景拓展色板”规则的派生 hex。
- 只使用线性渐变。
- 场景适配：天气、睡眠、环境、音乐可用 `ambient-band`；时间、夜间、季节、事件、倒计时可用 `temporal-band`；运动、导航、清理、紧急动作可用 `action-fill`。若渐变不能解释场景或动作，不要为了装饰添加。
- 2 stop 优先；3 stop 仅用于时间、天气、夜间、舞台、倒计时等语义明确的带状渐变。
- 不使用无场景依据的手调色、机械插值色、`color-mix()`、滤镜、无来源 alpha 变体、径向装饰、orb 或 bokeh。
- 强渐变上的文本只用 on-color 或中性前景；状态色移入中性背板。

## 输出策略

- 设计说明里优先写 token 名和角色，例如 `root.bg = multi_color_06 -> multi_color_aux_06`；使用场景拓展色时，内部记录 `scene`、`anchors`、`baseSources`、`derivedRoles` 和最终 hex。
- 最终 DSL 一律写 token 映射或场景拓展后的 hex，同时在内部推理中保留 token 来源或拓展来源。
- 自定义角色名按用途命名，例如 `surface.default`、`text.primary`、`action.bg`；不要命名为 `blue1`、`prettyBg`。
- 同一张卡最多一个主场景色族；跨族只用于状态语义或明确品牌动作。
