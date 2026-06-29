# 表现力工具箱

使用这些技法，在不超出 HarmonyOS A2UI Form 子集的前提下创造视觉丰富度。

## 1. 线性渐变 Shell

用 `styles.linearGradient` 创建 root 背景和光晕层。

```json
"linearGradient":{"direction":"RightBottom","colors":[["#25272E",0],["#3037B8",0.72],["#5D49E8",1]]}
```

规则：

- 为场景选择颜色，不要从任何示例产物继承。
- 保持一个连贯色相系统和一个强调色家族。
- 常规信息卡背景保持干净整洁，避免大面积使用高亮、高饱和或高刺激颜色。
- 品牌色只能在合理范围内用于强调、图标、局部纹理或关键状态，不要直接铺满整张信息卡或密集正文。
- 夜晚/睡眠/专注/设备氛围使用暗色渐变；天气/生活方式使用更暖或更亮的渐变。
- 没有图片、模糊或沉浸式取色时，浅色模式默认背景使用 `#FFFFFF`，深色模式默认背景使用 `#2E3033`。
- 使用图片或用色丰富的沉浸式背景时，可从内容图中提取背景色；深浅模式可共用同一套内容色，不要随系统模式随意切换。
- 锁屏场景使用单色模式，通过透明度、模糊和层级区分元素，不使用色相区分。

## 颜色和文本层级

- 多彩色遵循 HarmonyOS 色彩语义，优先用于高亮文本、图标或核心提示。
- 文本层级使用 `font_primary`、`font_secondary`、`font_tertiary` 对应的主/次/弱语义色；如果只能使用 hex，按同等对比关系映射。
- 不要把高饱和多彩色直接用于整张卡片背景或整段文字。
- 灰色背景主要用于卡片中存在白色块重叠时，避免白色区域和卡片背景混在一起。
- 带透明通道的 PNG 资源保持透明，不要为了深色模式额外套底色；文字颜色跟随系统语义层级。

## 2. 半透明块

使用带 alpha 的 `backgroundColor` 和 `borderColor` 组织次要上下文。

```json
"styles":{"backgroundColor":"#24FFFFFF","borderWidth":1,"borderColor":"#3DFFFFFF","borderRadius":15}
```

规则：

- `2x2` 卡片最多 1 个主要半透明块。
- `2x4` 卡片最多 2 个主要半透明块。
- 块应支持层级，不要变成互相竞争的小卡片。

## 3. 文本字形图标

当不需要图标素材时，用 `Text` 承载紧凑字形/图标。若素材库存在与当前语义角色明确匹配的图标/图片，且卡片仍需要该语义视觉锚点，不要用文本字形替代素材库 `src`。

```json
{"id":"weatherIcon","component":"Text","content":{"path":"/weather/icon"},"styles":{"fontSize":38,"maxLines":1,"textAlign":"center"}}
```

字形图标用于简单符号标记。当字形承载语义时，旁边放置可见文本或让相邻文本明确说明其含义；不要生成未在组件目录声明的无障碍属性。

## 4. 用 Progress 做视觉锚点

睡眠、习惯、电量、完成度、训练和目标卡使用 `Progress`。

```json
{"id":"goalProgress","component":"Progress","value":{"path":"/goal/value"},"total":{"path":"/goal/total"},"styles":{"type":"ring","color":"#A77DFF","width":72,"height":72}}
```

进度组件应是主要焦点之一，不要成为很小的附带元素。

## 5. 强调分隔线

用 `Divider` 作为轻量结构元素。

```json
{"id":"accentLine","component":"Divider","styles":{"vertical":true,"strokeWidth":3,"color":"#73FFFFFF","height":28}}
```

它适合上下文卡片、分隔元数据与标题，或在不增加额外容器的情况下制造节奏。

## 6. 图片背景

对于有真实素材的产品/设备卡：

```json
{"id":"root","component":"Stack","children":["productImage","contentLayer"],"styles":{"width":160,"height":160,"clip":true}}
{"id":"productImage","component":"Image","src":{"path":"/asset/productImage"},"styles":{"width":"100%","height":"100%","objectFit":"cover"}}
```

规则：

- 只有素材真实时才使用。
- 通过遮罩块或位置保护文字对比。
- 不要用文字遮住重要产品细节。

## 反模式

- 在同一张 `2x2` 卡片里同时使用渐变 + 光晕 + 图片 + 多个块。
- 不能澄清场景的纯装饰。
- 多个无关强调色。
- 当有视觉数据时，用纯文本替代有意义的 `Progress` 或图片。
