# 设计启发式

只有在协议、绑定、尺寸预算、内容取舍和颜色合法性都已成立，但主显示组不突出、支撑组散落、表面层级缺失，或用户明确要求调整构图/表面时读取本文。构图和表面调整不得压缩受保护文本、CTA、日期、时间、状态、主指标或事件热区。

## 读取前提

- 一个服务对象或主问题、一个主色族；动作目标不超过当前尺寸或模板允许上限。
- `mustKeep` 完整显示，`shouldKeep` 不挤占主显示组、受保护文本或动作热区。
- `2x2` / `2x4` 尺寸和主要区域预算已经成立。
- 非图片颜色能回溯到 token、多彩色或合规场景拓展色。
- 动作能力和素材来源已经声明；不明点击或素材已经删除。

术语兜底：`manifest` 指选中模板目录内的 `manifest.json`；`metric/tile/status/badge` 是模板声明的并列小事实槽位，不按普通支撑条数折算。

## 职责边界

- 内容取舍和尺寸适配读 `../generation-contract.md`；模板和风格选择读 `../routing-and-style.md`。
- 宽高预算、安全区、字号、图标、按钮热区、进度几何：读 `layout-system.md`。
- token、hex、深浅色、渐变 stop、前景/背景、状态色：读 `color-token-system.md`。
- 素材路径、图片、图标来源：读 `asset-library.md`。

## 构图与表面

每张卡只选 1 个 `compositionPattern`，且它必须承载 `mustKeep` 主显示组、`shouldKeep` 支撑组、已声明动作或主媒体之一：

- `plain-card`：简单工具型信息，依靠字号、留白和中性表面建立层级。
- `single-panel`：会议、日历、票券、备忘、关怀、账单、物流等相关信息归拢成一个面板。
- `ambient-root`：天气、睡眠、音乐、环境状态等场景色放在 root。
- `dark-focus`：夜间、演出、睡眠、专注等暗色有语义价值的场景。
- `meter-dashboard`：一个仪表或进度主焦点，不是复杂仪表盘。
- `split-action`：内容区和动作区需要独立宽度预算，且动作能力完整。
- `media-card`：真实媒体或图片承载主对象，文本保持安全遮罩或独立背板。

每张卡最多选 1 个主 `surfaceStrategy`：`plain`、`tinted-surface`、`colored-root`、`split-surface`、`image-derived`、`dark-stage`、`soft-material`。表面变化必须绑定 `contentSurface`、`sceneAccent`、`actionMaterial` 或 `statusAccent` 中至少一个角色；`2x2` 最多一个主要表面变化，`2x4` 最多一个 root 变化加一个支撑背板。

值化反查：

- 主显示组必须是最大字号文本、最大图形、最靠前位置或唯一状态色之一；多个组件组成时都回答同一主问题。
- 支撑组只包含 `shouldKeep` 或必要 `mustKeep`；模板内 `metric/tile/status/badge` 按 manifest 独立计数，但不得重复 `primary`。
- 可点击动作区必须有已声明 `onClick` 和不小于 `24vp` 的点击视觉尺寸；文字动作标签优先 2-6 个中文字；动作区面积不得大于主信息区。
- 没有绑定 `mustKeep`、`shouldKeep`、主动作、状态或主媒体的装饰，删除。

## 可用表面技法

所有技法都必须在 HarmonyOS A2UI Form 子集内完成，不新增组件目录没有声明的属性。

### 线性渐变

```json
"linearGradient":{"direction":"RightBottom","colors":[["#ff202224",0],["#634794",1]]}
```

- 渐变语义和 stop 来源按 `color-token-system.md`；本文不创建颜色。
- 只使用线性渐变，不用 orb、bokeh、径向装饰或无来源 alpha 叠色。
- `2x2` 最多一个渐变面；`2x4` 最多一个 root 渐变加一个中性支撑背板，或中性 root 加一个渐变重点面。
- 文字超过 2 行、主按钮小于 `24vp` 点击视觉尺寸，或前景/背景配对失败时，回退为中性表面。

### 半透明块

```json
"styles":{"backgroundColor":"#19000000","borderWidth":1,"borderColor":"#33000000","borderRadius":14}
```

- 背板只用于归拢多个相关元素；单独按钮、单条状态或单个 icon 不套背板。
- `2x2` 最多 1 个主要半透明块；`2x4` 最多 2 个主要半透明块。
- 背板与其服务的按钮或文本共享左右边界，并保持 4-12vp 间距。

### 文本字形图标

```json
{"id":"weather_icon_text","component":"Text","content":"{{ ${/weather/icon} }}","styles":{"fontSize":32,"maxLines":1,"textAlign":"center"}}
```

- 仅当素材库没有匹配素材、且用户输入或 DataModel 已提供短符号字段时使用。
- 文本字形不能是 emoji；若素材库存在匹配语义素材且视觉是主识别对象，使用素材库声明的 `src`，不要用文本字形或自绘几何替代。
- 宿主协议没有可访问性属性时，用相邻可见文本承载语义，不输出协议外字段。

### 图片背景

- 只有图片是 `primaryObject`、`mustKeep` 主媒体，或用户明确提供票券/产品/照片/环境状态素材时才用图片。
- 图片路径必须来自用户当前提供或 `asset-library.md` 声明。
- 文本放在安全遮罩或独立面板上，不遮挡重要产品或媒体细节。
- 不使用网络图、内联/base64 SVG、占位图或相似路径猜测；只使用素材库声明的本地 SVG/PNG。

## 反模式

- 同一张 `2x2` 同时使用渐变、图片、多个半透明块和多个图表。
- 添加没有绑定 `mustKeep`、`shouldKeep`、状态、动作或主媒体的装饰。
- 同一卡片出现 2 个以上主场景色族、2 个以上最大字号文本或 2 个以上主视觉图形。
- 用视觉技法掩盖内容过载、字号过小、动作能力不明或颜色无来源。
- 将 `2x4` 做成 dashboard、导航 hub、按钮网格或营销卡。
- action、状态色或图表的字号、面积或饱和度高于主显示组，且它们不是 `mustKeep` 主显示组。

## 输出前检查

- 是否只有 1 个主显示组，且它是最大字号文本、最大图形、最靠前位置或唯一状态色之一？
- 支撑组是否只包含已入选 `shouldKeep` 字段？模板里的 `metric/tile/status/badge` 是否来自 manifest、互不重复且没有抢占主显示组？
- 可点击动作区是否有已声明 `onClick` 和不小于 `24vp` 的点击视觉尺寸？
- 渐变、背板、图片、图标是否各自绑定了 `contentSurface`、`sceneAccent`、`statusAccent`、主媒体或动作角色？
- 受保护文本是否完整，按钮是否贴近它服务的内容？
- 背板是否只包裹相关内容，没有空包或孤立包裹？
- 主色族是否只有 1 个，状态色是否只用于真实状态，图表色是否来自场景主色、状态色或中性 track？
- 没有角色绑定、超过色彩/表面预算或压缩受保护文本的效果是否已删除？
