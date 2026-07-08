# 间距和层级

GenUI extended 样式中，数字默认作为 vp；字符串可按文档使用 `vp`、`fp`、`%` 和 `px`。

## 间距尺度

使用一致的小卡片尺度：

| Token | 值 | 用途 |
| --- | --- | --- |
| `sp-2xs` | `2` | 极小内部文字/字形微调 |
| `sp-xs` | `4` | 图标到文字的间距 |
| `sp-sm` | `6` 或 `8` | 紧凑组间距 |
| `sp-md` | `10` 或 `12` | 普通行/区段内部间距 |
| `sp-lg` | `14` 或 `16` | root padding 或主要组间距 |
| `sp-xl` | `20` 或 `24` | 只用于更大的桌面卡片 shell |

规则：

- 区段间距必须大于区段内部间距。
- 在 160vp 高的卡片中，root padding 通常保持在 `10` 到 `16`。
- 不要在一张卡里发明许多任意间距。
- `itemMargin` 是 Row/Column 子节点间距的优先方式。

## 圆角系统

| 场景 | 圆角 |
| --- | --- |
| Root 卡片 shell | `20` 到 `24` |
| 内部半透明块 | `14` 到 `18` |
| 圆形/avatar/指标盘 | 宽高的一半 |
| 小图标块 | `5` 到 `8` |
| Pill/action bar | height / 2 |

规则：

- 外层圆角 >= 内层圆角。
- 使用圆角时，对 root 和图片容器启用裁剪。
- Button/pill 圆角应是最圆的形态。

## 阴影

GenUI extended 样式使用 `shadow` 对象：

```json
"shadow":{"radius":18,"color":"#22000000","offsetX":0,"offsetY":5,"fill":false,"type":"color","style":"outer"}
```

指导：

- Root shell 可以使用一个柔和阴影。
- 主要圆形/动作元素可以额外使用一个阴影。
- 避免每个内部块都有阴影。
- 深色卡可以使用带 alpha 的彩色光晕阴影；浅色卡应使用低 alpha 黑色。

## 颜色 Alpha

用 alpha hex 表示半透明：

- `#22FFFFFF` 用于轻微白色叠层。
- `#66FFFFFF` 用于可见边框/高光。
- `#22000000` 用于轻微深色阴影。

GenUI 文档允许 `#RRGGBB` 和 `#AARRGGBB`；alpha 前缀的 8 位 hex 对半透明叠层很有用。
