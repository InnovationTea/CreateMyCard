# Design Token 到 A2UI 映射

## 1. 文档定位

本文档记录 Design Compact DSL 的 `design` 和语义颜色 token 如何由云侧转换器展开为
HarmonyOS A2UI Form NDJSON。

- 转换器：
  `widget_service/cloud/services/compact_dsl_a2ui_converter.py`
- 转换器测试：
  `widget_service/tests/test_compact_dsl_a2ui_converter.py`
- 上游参考快照：
  `a2ui-form-hmos-design-tokens(2).md`，接收日期为 2026-07-28
- A2UI catalog：
  `ohos.a2ui.extended.catalog.form`

本文档是**转换层实现契约**，不替代生成提示词。提示词由提示词维护方独立更新。

## 2. 转换边界

转换不调用模型，输入和输出均为 NDJSON。

输入组件行：

```json
["title","Text",{"content":"青浦天气","design":"subtitle-s"}]
```

输出固定为三条 A2UI 消息：

1. `createSurface`
2. `updateComponents`
3. `updateDataModel`

通用转换规则：

| Compact DSL | A2UI |
| --- | --- |
| `{"path":"/data/value"}` | `"{{ ${/data/value} }}"` |
| `Text.content` | 组件顶层 `content` |
| `Image.src` | 组件顶层 `src` |
| `Progress.value/total` | 组件顶层 `value/total` |
| `Button.label/enabled` | 组件顶层 `label/enabled` |
| `Checkbox.label/value/select` | 组件顶层同名字段 |
| `onClick` | 组件顶层 `onClick` |
| 其他可渲染属性 | `styles` |
| root 的 `width/height` | 强制转换为 `matchParent` |

实例显式传入的属性当前会覆盖 `design` 默认值，用于兼容已有 DSL。新增固定 design 时应在提示词、
转换器和测试中共同约束可覆盖属性。

## 3. Text

Text `design` 只展开字号和字重，颜色由实例的 `fontColor` 决定。

| Design | `fontSize` | `fontWeight` | 支持状态 |
| --- | ---: | ---: | --- |
| `display-l` | 56 | 300 | 完整支持 |
| `display-m` | 48 | 300 | 完整支持 |
| `display-s` | 36 | 700 | 完整支持 |
| `title-l` | 30 | 700 | 完整支持 |
| `title-m` | 24 | 700 | 完整支持 |
| `title-s` | 20 | 700 | 完整支持 |
| `subtitle-l` | 18 | 500 | 完整支持 |
| `subtitle-m` | 16 | 500 | 完整支持 |
| `subtitle-s` | 14 | 500 | 完整支持 |
| `body-l` | 16 | 500 | 完整支持 |
| `body-m` | 14 | 400 | 完整支持 |
| `body-s` | 12 | 400 | 完整支持 |
| `caption-l` | 12 | 500 | 完整支持 |
| `caption-m` | 10 | 500 | 完整支持 |

## 4. Button

### 4.1 `capsule`

| A2UI styles 字段 | 值 |
| --- | --- |
| `width` | `"matchParent"` |
| `height` | `36` |
| `borderRadius` | `20` |
| `padding` | `{"left":8,"top":0,"right":8,"bottom":0}` |
| `backgroundColor` | `#0C000000` |
| `fontColor` | `#FF0A59F7` |
| `fontSize` | `14` |
| `fontWeight` | `500` |
| `maxFontSize` | `14` |
| `minFontSize` | `12` |
| `maxLines` | `1` |
| `flexShrink` | `0` |

支持状态：完整支持。

### 4.2 `icon-round`

| A2UI styles 字段 | 值 |
| --- | --- |
| `width` | `36` |
| `height` | `36` |
| `borderRadius` | `18` |
| `padding` | `0` |
| `backgroundColor` | `#0C000000` |
| `flexShrink` | `0` |

支持状态：几何和背景完整支持。标准 A2UI Form Button 使用 `label`，不支持子节点。为兼容
PROMPT.md 允许的单个行内 `Image`，转换器会验证该子节点后将其移除，并保留 Button 的
`label`、`onClick` 和设计样式。该行为属于**降级支持**，图标不会出现在 A2UI 输出中。

兼容规则：

- Button 最多接受一个 `Image` 子节点，其他类型或多个子节点继续拒绝。
- 叶子组件误带的空 `children: []` 会被直接移除。
- 除 Button 的单个 `Image` 外，叶子组件的非空 `children` 继续拒绝。

已移除的旧别名：

- `default`
- `primary`
- `icon`
- `default-sm`
- `primary-sm`
- `icon-sm`

## 5. Progress

所有 Progress 必须提供 `value` 和 `total`。`ring` 不属于 design，直接使用 `type:"ring"`。

### 5.1 `linear-bar`

| A2UI styles 字段 | 值 |
| --- | --- |
| `type` | `"linear"` |
| `width` | `"matchParent"` |
| `height` | `8` |
| `borderRadius` | `4` |
| `backgroundColor` | `#19000000` |

支持状态：完整支持。前景 `color` 可由实例按主题或业务语义提供。

### 5.2 `segmented-bar`

标准 A2UI Form Progress 没有横向分段进度原语，当前降级为可渲染的线性进度：

| A2UI styles 字段 | 值 |
| --- | --- |
| `type` | `"linear"` |
| `width` | `"matchParent"` |
| `height` | `8` |
| `borderRadius` | `4` |
| `backgroundColor` | `#19000000` |

支持状态：**降级支持**。`value/total` 保留，但段间距和逐段强调无法等价表达。

### 5.3 `threshold-bar`

标准 A2UI Form Progress 只有单一前景填充，当前降级为安全色线性进度：

| A2UI styles 字段 | 值 |
| --- | --- |
| `type` | `"linear"` |
| `width` | `"matchParent"` |
| `height` | `20` |
| `borderRadius` | `10` |
| `backgroundColor` | `#6B7F91` |
| `color` | `#C8F000` |

Compact DSL 的 `threshold` 由转换层消费，不写入 A2UI `styles`，避免产生标准 Form catalog
不支持的字段。

支持状态：**降级支持**。当前不支持从安全色到警告色的双段填充。

已移除的旧 Progress design：

- `linear`
- `eclipse`

## 6. Divider

| Design | A2UI styles 映射 | 支持状态 |
| --- | --- | --- |
| `line` | `strokeWidth:1, vertical:false, color:#33000000` | 完整支持 |
| `bar` | `strokeWidth:8, vertical:false, color:#0C000000` | 完整支持 |

## 7. Checkbox

`design:"default"` 映射：

| A2UI styles 字段 | 值 |
| --- | --- |
| `width` | `20` |
| `height` | `20` |
| `borderRadius` | `10` |
| `selectedColor` | `#FF0A59F7` |
| `unSelectedColor` | `#66000000` |
| `mark.strokeColor` | `#FFFFFFFF` |
| `mark.size` | `20` |
| `mark.strokeWidth` | `2` |
| `shape` | `"circle"` |

支持状态：完整支持。

## 8. 语义颜色

转换器当前固定展开为上游参考快照的 Light 值。`theme="dark"` 参数仅保留接口兼容，
不会切换到 Dark 色值。

### 8.1 文本、图标和背景

| Token | A2UI hex |
| --- | --- |
| `font_primary` | `#E5000000` |
| `font_secondary` | `#99000000` |
| `font_tertiary` | `#66000000` |
| `font_emphasize` | `#FF0A59F7` |
| `font_on_primary` | `#FFFFFFFF` |
| `warning` | `#FFE84026` |
| `alert` | `#FFED6F21` |
| `confirm` | `#FF64BB5C` |
| `icon_primary` | `#E5000000` |
| `icon_secondary` | `#99000000` |
| `icon_tertiary` | `#66000000` |
| `icon_emphasize` | `#FF0A59F7` |
| `icon_on_primary` | `#FFFFFFFF` |
| `icon_on_tertiary` | `#66FFFFFF` |
| `background_primary` | `#FFFFFFFF` |
| `background_emphasize` | `#FF0A59F7` |
| `comp_background_list_card` | `#FFFFFFFF` |
| `comp_background_tertiary` | `#0C000000` |
| `comp_background_secondary` | `#19000000` |
| `comp_background_emphasize` | `#FF0A59F7` |
| `comp_background_primary_contrary` | `#FFFFFFFF` |
| `comp_divider` | `#33000000` |
| `container40` | `#66000000` |
| `primary50` | `#7F000000` |

### 8.2 多彩色

| Token | A2UI hex | Token | A2UI hex |
| --- | --- | --- | --- |
| `multi_color_01` | `#FF564AF7` | `multi_color_aux_01` | `#FF8981F7` |
| `multi_color_02` | `#FF46B1E3` | `multi_color_aux_02` | `#FF86C5E3` |
| `multi_color_03` | `#FF61CFBE` | `multi_color_aux_03` | `#FF92D6CC` |
| `multi_color_04` | `#FF64BB5C` | `multi_color_aux_04` | `#FF92C48D` |
| `multi_color_05` | `#FFA5D61D` | `multi_color_aux_05` | `#FFBDDB69` |
| `multi_color_06` | `#FFAC49F5` | `multi_color_aux_06` | `#FFC386F0` |
| `multi_color_07` | `#FFE64566` | `multi_color_aux_07` | `#FFE67C92` |
| `multi_color_08` | `#FFE84026` | `multi_color_aux_08` | `#FFE87361` |
| `multi_color_09` | `#FFED6F21` | `multi_color_aux_09` | `#FFED955F` |
| `multi_color_10` | `#FFF9A01E` | `multi_color_aux_10` | `#FFF9BC64` |
| `multi_color_11` | `#FFF7CE00` | `multi_color_aux_11` | `#FFF5DC62` |

### 8.3 蒙层

| Token | A2UI hex |
| --- | --- |
| `mask_primary` | `#CC000000` |
| `mask_secondary` | `#99000000` |
| `mask_tertiary` | `#66000000` |
| `mask_fourth` | `#33000000` |
| `mask_fifth` | `#19000000` |
| `mask_sixth` | `#0C000000` |

## 9. 支持状态定义

| 状态 | 定义 |
| --- | --- |
| 完整支持 | Compact DSL 语义可等价映射到标准 A2UI Form |
| 降级支持 | 输出可渲染，但标准 A2UI 缺少部分等价能力 |
| 不支持 | 转换器拒绝输入并返回 `CompactDslConversionError` |

## 10. 变更流程

以后新增或调整 design token 时，同一个 PR 必须完成：

1. 更新转换器映射。
2. 增加或更新转换器测试。
3. 更新本文档的当前映射。
4. 在下方 Change Log 追加一条记录。
5. 标明兼容性影响：新增、调整、废弃或降级。

提示词文件不由转换层 PR 自动修改。提示词维护方需要根据同一上游 token 版本单独同步。

## 11. Change Log

### v3 - 2026-07-28

- 兼容叶子组件多余的空 `children: []`，转换后不输出 `children`。
- Button 的单个 `Image` 子节点按标准 A2UI Form 能力降级移除。
- Button 的多个子节点、非 Image 子节点以及其他叶子组件的非空子节点仍为硬错误。

### v2 - 2026-07-28 - PR #13

- `display-s` 从 `38/300` 调整为 `36/700`。
- Button 仅保留 `capsule` 和 `icon-round`，并同步新几何定值。
- Progress 新增 `linear-bar`、`segmented-bar`、`threshold-bar`。
- Progress `total` 改为转换必填字段。
- Checkbox 新增 `design:"default"`。
- 补齐上游 Light 模式语义颜色。
- 明确 `segmented-bar` 和 `threshold-bar` 的标准 A2UI 降级行为。
- 转换后的 catalog 固定为 `ohos.a2ui.extended.catalog.form`。
