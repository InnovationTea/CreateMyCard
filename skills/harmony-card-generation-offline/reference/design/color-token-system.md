# 色彩 Token 系统

本文件校验颜色是否合法。非图片颜色优先回溯到 HarmonyOS 语义 token、`ohos_id_color_*`、`multi_color_*` 或 `multi_color_aux_*`；当具体场景需要官方 token 表没有覆盖的 root 表面、重点面、半透明背板或线性渐变 stop 时，可以在官方 token 色族基础上声明少量场景拓展色。当前端侧不支持语义 token 渲染，最终 DSL 必须写映射或拓展后的 `#RRGGBB` 或 `#AARRGGBB` 色值；内部设计理由仍保留 token 名称、拓展来源和用途角色。

## 单文件兜底

- `scene vector`：场景字段组；颜色只取其中的场景目的、密度、主信息类型、时间性和表达调性，不改变内容取舍。
- `compositionPattern`：构图枚举，例如中性工具卡、内容背板、场景色 root、暗色焦点、仪表主焦点、动作分区或媒体卡。
- `surfaceStrategy`：表面策略，例如中性 root、低强度支撑背板、场景色 root、双表面分区、图片遮罩、暗色表面或柔和材质层。
- `sceneAccent/statusAccent/actionMaterial`：分别表示场景主色、真实状态色和动作材质；三者不能互相冒充。

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

## 配色决策流程

颜色选择先做场景判断，再做 token 映射；不要从“好看、清新、高级、科技感”这类抽象词直接挑色。

1. 从 `generation-workflow.md` 的 `scene vector`（场景字段组）取 `register`、`temporality`、`density`、`keyInfo` 和 `hierarchy`。
2. 命名 2-4 个具体锚点，例如天空层、雨玻璃、日历纸、跑道、票纸、电池环、包裹标签、药盒、收据纸、夜间舞台。
3. 选择一个 `compositionPattern`（构图枚举）和 `surfaceStrategy`（表面策略），再决定一个主场景色族；枚举定义见 `generation-workflow.md`。
4. 先分配角色：`cardSurface`、`contentSurface`、`sceneAccent`、`actionMaterial`、`statusAccent`、`textIcon`。
5. 将角色映射为本文件 token、多彩色或合规场景拓展色，并写入 DSL hex。
6. 检查深浅模式同名、前景/背景配对、状态色语义、渐变 stop 和 2x2/2x4 色彩预算。

色彩预算：

- `2x2`：最多一个场景色信号、一个状态/动作信号和中性文字；最多一个渐变面。
- `2x4`：最多一个场景色信号、一个中性支撑表面和一个状态/动作信号；可用一个 root 渐变加一个中性支撑背板，或中性 root 加一个渐变重点面。
- 同一卡片不要让每个内容块都有独立主题色。

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

1. 优先使用 `color-token-values.md` 中的 token 名称和 light/dark 值，输出 DSL 时写入对应模式的 hex 值。
2. 如果输入或源规范给出 `ohos_id_color_*`，先映射到等价 token；无法映射时只在内部保留 `ohos_id_color_*` 作为来源名，并使用其官方 light/dark hex 值，不要把源 ID 直接写进 DSL。
3. 如果官方 token 无法表达具体场景表面（如朝阳暖雾、雨天玻璃、薄荷运动、夜间睡眠、音乐封面），可以创建场景拓展色；拓展色必须基于一个主色族或中性背景族，且只服务 root、重点面、半透明背板或渐变 stop。
4. 多彩色优先使用 `multi_color_01..11` 和 `multi_color_aux_01..11`；允许从它们派生低饱和、高明度、低对比的场景表面色，但不得派生第二个高饱和主色。
5. 状态色只用于真实状态；常规提示、建议、倒计时和轻提醒不自动使用 `warning` / `alert`。
6. 深浅模式必须使用同一 token 名或同一场景拓展色名，只切换对应 light/dark 值；若只产出单一 DSL，至少在内部记录 light 来源。

## 官方多彩色语义

多彩色用于一个主场景色族、图表、徽标、小面积强调或同族辅助面，不是任意取色表。

- `multi_color_01`：紫蓝、夜间、科技或阶段感。
- `multi_color_02`：天空、天气、水、旅行冷感。
- `multi_color_03`：设备、薄荷、健康辅助；不默认用作 CTA。
- `multi_color_04`：确认、连接、安全、拨打等绿色动作。
- `multi_color_05`：成长、完成辅助、自然场景小面积。
- `multi_color_06`：夜间、睡眠、舞台紫。
- `multi_color_07`：演出、情绪、玫瑰色小面积强调。
- `multi_color_08`：品牌蓝或通用系统动作；不要当所有场景默认色。
- `multi_color_09`：物流、运动、警示邻近的橙红能量。
- `multi_color_10`：朝阳、行动、倒计时、庆祝。
- `multi_color_11`：便签、日光、高亮；大面积使用时必须保证深色前景可读。

`multi_color_aux_01..11` 只作为同族低强度支撑、渐变另一端、小面积图表或软表面。不要从辅助色再手调浅色、暗色或透明度。

## 场景主色启发

这些是内部起点，不是模板。用户给出更具体锚点时，以当前需求为准。

- 天气/环境：`ambient-root`（场景色 root）或 `split-action`（主内容 + 动作/状态分区）；晴天/多云可用 `multi_color_02`、`multi_color_aux_02` 或 `multi_color_10/11` 小面积日光；雨夜可用 `multi_color_01 -> multi_color_02`。普通出行建议不是 `warning`。
- 会议/日程：`plain-card`（中性工具卡）或 `single-panel`（一个内容背板）；中性表面为主，时间或入会动作可用 `brand` / `comp_background_emphasize`，不要把参会人和会议号做高饱和强调。
- 演出/票券/夜间活动：`dark-focus`（暗色有场景语义）、`single-panel`（票面背板）或 `split-action`（票面 + 动作）；可用 `multi_color_06/07/10`，票券状态用 `confirm` 只作状态。
- 运动/训练/倒计时：`meter-dashboard`（单一仪表/进度主焦点）或 `split-action`（指标 + 开始/继续动作）；可用 `multi_color_09/10`，完成/开始动作可用 `confirm` 或动作主色。
- 设备/电量/清理：`meter-dashboard`（电量/容量环或条为主）或 `plain-card`（中性状态卡）；teal 只放进仪表/小徽标，清理、连接、可用状态用 `confirm`。
- 亲情拨打/联系人：`split-action`（联系人 + 拨打动作）或 `single-panel`（联系人信息归组）；拨打动作可用 `confirm`，联系人信息使用中性表面或 `multi_color_aux_10/11` 小面积暖色。
- 物流/包裹：`single-panel`（包裹状态归组）；包裹/派送可用 `multi_color_09 -> multi_color_10`，取件码是中性背板里的高可读主信息。
- 备忘/便签：`plain-card`（纯文本提醒）或 `single-panel`（便签背板）；使用 `multi_color_aux_10/11` 做 1vp 边线、4-8vp 小标记或低强度背板，正文保持深色前景。
- 睡眠/专注/夜间：`dark-focus`（暗色主表面）或 `ambient-root`（夜间场景色 root）；使用 `multi_color_01/06` 或深色中性表面，状态不足用文字说明，不把 ring 或动作改成警告色。

## 按钮材质

- 默认按钮/胶囊使用中性或磨砂材质：`comp_background_secondary` / `comp_background_tertiary`，必要时加 `#ffffff19` 这类有来源的低 alpha 白色描边。
- 只有颜色本身表达含义时才用实色：品牌入会、确认/连接/拨打/清理、危险/破坏性操作或明确高能行动。
- 查看、打开、详情、进入类动作默认不是实色按钮。
- 实色按钮仍需要合规前景：品牌/强调背景用 `font_on_primary`，中性低强调动作使用普通前景。
- 不要因为“主动作”三个字就给按钮换成高饱和色；位置、尺寸和文案已经能表达主次。

## 场景拓展色板

当官方 token 表不足以支撑场景表面、重点面、背板或渐变 stop 时，可以在内部声明 `scenePalette`，最终 DSL 仍只写 hex。声明时必须满足：

- `scene`: 具体场景，而不是抽象风格词；例如 `weather.morning.cool`、`weather.morning.warm`、`fitness.mint`、`music.ambient`、`sleep.night`。
- `anchors`: 2-4 个物理或文化锚点；例如晨雾、薄云、奶油纸、跑道、薄荷饮、夜灯、唱片封套。
- `baseSources`: 使用的官方 token、`ohos_id_color_*`、`multi_color_*` 或 `multi_color_aux_*`；拓展色必须与这些来源保持同一主色族或中性表面关系。
- `derivedRoles`: 每个拓展色的用途，例如 `rootStart`、`rootEnd`、`softPanel`、`actionFill`、`dividerWash`；不要用 `prettyBlue`、`warm1` 这类无用途命名。
- `bounds`: 拓展色应低饱和、高明度、低对比；除主 CTA 外，不新增高饱和色。`2x2` 最多 2 个拓展色，`2x4` 最多 3 个拓展色。

拓展色适用范围：

- 允许：root 背景、重点面、低强度背板、线性渐变 stop、1vp 分隔层。
- 谨慎：CTA 背景；只有品牌动作、确认动作、运动开始、导航、拨打、入会、连接或清理等必要动作可用实色。
- 禁止：正文色、状态语义色、错误/警告/成功判断色、多个互相无关的主题色。

推荐派生方向：

- 天气晨间：从 `background_primary/background_secondary` 加入低饱和冷蓝或暖米表面，只用于 root 背景或低强度背板。
- 雨雪天气：从 `background_secondary/background_tertiary` 加入低饱和蓝灰表面，避免高饱和蓝。
- 运动健康：从 `multi_color_04` 或 `multi_color_aux_03/04` 派生薄荷浅表面，CTA 可用 `confirm` 或 `multi_color_04`。
- 音乐耳机：从 `brand`、`multi_color_06/07` 或中性背景派生 root/重点面表面，避免同时使用多个高饱和娱乐色。
- 睡眠夜间：从 `background_tertiary`、`multi_color_01/06` 派生暗色或柔紫表面，文字使用 on-color 或中性前景。

场景拓展色仍需通过角色和预算检查：每个拓展色必须绑定 `rootStart/rootEnd/softPanel/actionFill/dividerWash` 等用途；若没有对应用途、导致 `2x2` 超过 2 个拓展色、导致 `2x4` 超过 3 个拓展色，或破坏前景/背景配对，则删除该拓展色。

## Token 值映射

需要把 token、`ohos_id_color_*` 或多彩色转换为最终 DSL hex 时，读取 `color-token-values.md`。本文只维护颜色决策、合法性、角色和配对规则，不重复 token 数值表。

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

- 使用 `comp_background_secondary` / `comp_background_tertiary` 承载低强度分组、按钮磨砂层和辅助提示。
- 使用 `comp_divider` 或组件透明层做边界，不手写自定义灰色。

## 渐变校验

- 每个 stop 必须是 `color-token-values.md` 中 token、`ohos_id_color_*`、`multi_color_*`、`multi_color_aux_*` 对应的确切 hex 值，或符合“场景拓展色板”规则的派生 hex。
- 只使用线性渐变。
- 渐变角色只选一种：`ambient-band` 表达天气、睡眠、环境或音乐的 root/重点面；`temporal-band` 表达时间、夜间、季节、事件或倒计时；`action-fill` 表达运动、导航、清理或紧急动作。若渐变无法绑定这三类角色之一，则删除渐变。
- 2 stop 优先；3 stop 仅用于时间、天气、夜间、舞台、倒计时等语义明确的带状渐变。
- 不使用无场景依据的手调色、机械插值色、`color-mix()`、滤镜、无来源 alpha 变体、径向装饰、orb 或 bokeh。
- 饱和或高对比渐变上的文本只用 on-color 或中性前景；状态色移入中性背板。

## 输出策略

- 设计说明里优先写 token 名和角色，例如 `root.bg = multi_color_06 -> multi_color_aux_06`；使用场景拓展色时，内部记录 `scene`、`anchors`、`baseSources`、`derivedRoles` 和最终 hex。
- 最终 DSL 一律写 token 映射或场景拓展后的 hex，同时在内部推理中保留 token 来源或拓展来源。
- 自定义角色名按用途命名，例如 `surface.default`、`text.primary`、`action.bg`；不要命名为 `blue1`、`prettyBg`。
- 同一张卡最多一个主场景色族；跨族只用于状态语义或明确品牌动作。
