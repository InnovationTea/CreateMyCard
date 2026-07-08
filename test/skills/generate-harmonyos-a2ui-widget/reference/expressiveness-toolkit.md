# 表现力工具箱

使用这些技法，在不超出 HarmonyOS GenUI extended Catalog 的前提下创造视觉丰富度。

## 1. 线性渐变 Shell

用 `styles.linearGradient` 创建 root 背景和光晕层。

```json
"linearGradient":{"direction":"RightBottom","colors":[["#25272E",0],["#3037B8",0.72],["#5D49E8",1]]}
```

规则：

- 为场景选择颜色，不要从任何示例产物继承。
- 保持一个连贯色相系统和一个强调色家族。
- 夜晚/睡眠/专注/设备氛围使用暗色渐变；天气/生活方式使用更暖或更亮的渐变。

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

当不需要图标素材时，用 `Text` 承载紧凑字形/图标。

```json
{"id":"weatherIcon","component":"Text","content":{"path":"/weather/icon"},"styles":{"fontSize":38,"maxLines":1,"textAlign":"center"}}
```

字形图标用于简单符号标记。当字形承载语义时，添加 `accessibility.label`。

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
