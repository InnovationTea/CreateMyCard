# Extended UI Schema (v0.9)

This document defines the **Extended.\*** component system and the **Common Styles** (`styles`) used by this skill.

It is a local copy of the previously bundled schema so this skill folder remains self-contained.

---

## AVAILABLE COMPONENTS:
**Extended.Text** — Body copy, labels, metrics. Renders as **plain text** (no border, no background).
Props: {
  id: string,
  component: "Extended.Text",
  content: string | { "path": string } /* DynamicString: literal or JSON Pointer — [`schema.md`](schema.md) § Dynamic values; Mode A structured JSON prefers `path` */,
  styles: {
    textOverflow: "ellipsis" | "clip" | "marquee" | "none",
    decoration: {
      type: "none" | "underline" | "overline" | "lineThrough",
      color: string,
      style: "solid" | "doubleE" | "dotted" | "dashed" | "wavy"
    }
    fontSize: number,
    fontWeight: "300" | "400" | "500" | "600" | "700",
    fontColor: string,
    textAlign: "start" | "center" | "end" | "justify",
    maxLines: number,
    wordBreak: "normal" | "breakAll" | "breakWord" | "hyphenation",
    maxFontSize: number,
    fontScaleMode: "followSystem" | "custom",
    minFontScale: number,
    maxFontScale: number
  }
}
- decoration: type，装饰线类型，字符串枚举值（"none":不使用文本装饰线，"underline":文字下划线修饰, "overline":文字上划线修饰, "lineThrough":穿过文本的修饰线），color:装饰线颜色，字符串类型（16进制），style：装饰线样式，字符串枚举值（"solid":单实线, "doubleE": 双实线, "dotted": 点线, "dashed": 虚线， "wavy": 波浪线）
- fontColor is text color hex (e.g., "#RRGGBB" or "#AARRGGBB")
- wordBreak: 文本断行规则，（"normal": 中文、日文和韩文文本可以在任意2个字符间断行,而Non-CJK文本只能在空白符处断行，"breakAll": 可在任意2个字符间断行,
"breakWord": 与breakAll相同，对于Non-CJK的文本可在任意2个字符间断行，一行文本中有断行破发点（如空白符）时，优先按破发点换行，保障单词优先完整显示。若整一行文本均无断行破发点，则在任意2个字符间断行。对于CJK文本，效果与normal一致。"hyphenation"：每行末尾单词尝试通过连字符“-”进行断行，若无法添加连字符“-”，则跟breakWord保持一致。）

**Extended.Button**
Props: {
  id: string,
  component: "Extended.Button",
  label: string | { "path": string } /* v0.9 DynamicString: literal or JSON Pointer binding — [`schema.md`](schema.md) § Dynamic values */,
  enabled: boolean,
  styles: {
    fontSize: number,
    fontWeight: 100 | 300 | 400 | 500 | 700 | 900,
    maxFontSize: number,
    fontScaleMode: "followSystem" | "custom",
    minFontScale: number,
    maxFontScale: number
  }
}
- 可与 **Common Styles** 合并使用（如 `width`、`borderRadius`、`padding`、`backgroundColor`）。**辅助链接型操作**（如「忘记密码」）若宿主对所有 `Button` 统一套主色实底，优先改用 **`Extended.Text` + `fontColor` + `decoration`**（见 skill 示例），避免与主 CTA 同权重。

**Extended.TextInput**
Props: {
  id: string,
  component: "Extended.TextInput",
  text: string | { "path": string } /* v0.9 DynamicString — [`schema.md`](schema.md) § Dynamic values */,
  placeholder: string,
  enabled: boolean,
  maxLength: number,
  type: "normal" | "email" | "password" | "number",
  styles: {
    placeholderColor: string,
    cancelButton: {
      "style": "constant" | "invisible" | "input",
      "fontColor": string,
      "fontSize": number
    }
    caretColor: string,
    selectedBackgroundColor: string,
    showUnderline: boolean,
    underlineColor: {
      "typing": string,
      "normal": string,
      "error": string,
      "disable": string
    },
    fontSize: number,
    fontWeight: 100 | 300 | 400 | 500 | 700 | 900,
    fontColor: string,
    textAlign: "start" | "center" | "end" | "justify",
    maxFontSize: number,
    wordBreak: "normal" | "breakAll" | "breakWord" | "hyphenation",
    maxLines: number,
    fontScaleMode: "followSystem" | "custom",
    minFontScale: number,
    maxFontScale: number
  }
}
- **GenUI A2UI skill（本仓生成约束）**：流式输出中 **`text` 仅允许** `{"path":"…"}`**；**不得** 用字符串字面量表示当前输入值；初值/空值用 **`updateDataModel`**。协议类型中的 `string` 保留给旧宿主。见 [`../../SKILL.md`](../../SKILL.md) **§0**、[`schema.md`](schema.md)（`path` / `updateDataModel`）。
- cancelButton: 设置右侧清除按钮样式，style: (constant:清除按钮常显样式, invisible: 清除按钮常隐样式, input: 清除按钮输入样式)
- caretColor：光标颜色
- selectedBackgroundColor: 文本选中底板颜色（默认 20% 不透明）
- wordBreak: 文本断行规则，（"normal": 中文、日文和韩文文本可以在任意2个字符间断行,而Non-CJK文本只能在空白符处断行，"breakAll": 可在任意2个字符间断行,
"breakWord": 与breakAll相同，对于Non-CJK的文本可在任意2个字符间断行，一行文本中有断行破发点（如空白符）时，优先按破发点换行，保障单词优先完整显示。若整一行文本均无断行破发点，则在任意2个字符间断行。对于CJK文本，效果与normal一致。"hyphenation"：每行末尾单词尝试通过连字符“-”进行断行，若无法添加连字符“-”，则跟breakWord保持一致。）

**Extended.Row**
Props: {
  id: string,
  component: "Extended.Row",
  children: string[],
  space: number,
  styles: {
    justifyContent: "start" | "center" | "end" | "spaceBetween" | "spaceAround" | "spaceEvenly",
    alignItems: "top" | "center" | "bottom"
  }
}

**Extended.Column**
Props: {
  id: string,
  component: "Extended.Column",
  children: string[],
  space: number,
  styles: {
    justifyContent: "start" | "center" | "end" | "spaceBetween" | "spaceAround" | "spaceEvenly",
    alignItems: "top" | "center" | "bottom"
  }
}

**Extended.List**
Props: {
  id: string,
  component: "Extended.List",
  children: string[],
  space: number,
  styles: {
    listDirection: "horizontal" | "vertical",
    scrollBar: "off" | "auto" | "on",
    nestedScroll: "scrollForward" | "scrollBackward"
  }
}

**Extended.Stack**
Props: {
  id: string,
  component: "Extended.Stack",
  children: string[],
  styles: {
    alignContent: "topStart" | "top" | "topEnd" | "start" | "center" | "end" | "bottomStart" | "bottom" | "bottomEnd"
  }
}

**Extended.Grid**
Props: {
  id: string,
  component: "Extended.Grid",
  children: string[],
  styles: {
    columnsTemplate: string,
    rowsTemplate: string,
    columnsGap: number,
    rowsGap: number
  }
}
- columnsTemplate: 列模板，字符串类型，格式为 "1fr 1fr 2fr"，表示列宽比例为 1:1:2
- rowsTemplate: 行模板，字符串类型，格式为 "1fr 1fr 2fr"，表示行高比例为 1:1:2
- columnsGap: 列间距，数值类型，单位为 px
- rowsGap: 行间距，数值类型，单位为 px

**Extended.GridRow**
Props: {
  id: string,
  component: "Extended.GridRow",
  children: string[],
  styles: {
  }
}

**Extended.Image**
Props: {
  id: string,
  component: "Extended.Image",
  src: string | { "path": string } /* DynamicString: literal or JSON Pointer — Mode A structured JSON prefers `path` */,
  styles: {
    aspectRatio: number,
    objectFit: "fill" | "contain" | "cover" | "auto" | "none" | "scaleDown"
    | "topStart" | "top" | "topEnd" | "start" | "center" | "end"
    | "bottomStart" | "bottom" | "bottomEnd" | "matrix"
  }
}
- aspectRatio: 指定当前组件的宽高比
- objectFit: 字符串枚举值
"fill"：不保持宽高比进行放大缩小，使得图片或视频充满显示边界，对齐方式为水平居中,
"contain"：保持宽高比进行缩小或者放大，使得图片或视频完全显示在显示边界内，对齐方式为水平居中,
"cover"：保持宽高比进行缩小或者放大，使得图片或视频两边都大于或等于显示边界，对齐方式为水平居中,
"auto"：图片或视频会根据其自身尺寸和组件的尺寸进行适当缩放，以在保持比例的同时填充视图，对齐方式为水平居中,
"none"：保持原有尺寸进行显示，对齐方式为水平居中,
"scaleDown"：保持宽高比进行显示，图片或视频缩小或者保持不变，对齐方式为水平居中,
"topStart"：图片或视频显示在组件的顶部起始端，且保持原有尺寸,
"top"：图片或视频显示在组件的顶部横向居中，且保持原有尺寸,
"topEnd"：图片或视频显示在组件的顶部尾端，且保持原有尺寸。,
"start"：图片或视频显示在组件的起始端纵向居中，且保持原有尺寸,
"center"：图片或视频显示在组件的横向和纵向居中，且保持原有尺寸,
"end"：图片或视频显示在组件的尾端纵向居中，且保持原有尺寸,
"bottomStart"：图片或视频显示在组件的底部起始端，且保持原有尺寸,
"bottom"：图片或视频显示在组件的底部横向居中，且保持原有尺寸,
"bottomEnd"：图片或视频显示在组件的底部尾端，且保持原有尺寸,
"matrix"：配合imageMatrix使用，使图像在Image组件自定义位置显示，且保持原有尺寸。不支持svg图源

**Extended.Divider**
Props: {
  id: string,
  component: "Extended.Divider",
  styles: {
    strokeWidth: number,
    vertical: boolean,
    color: string
  }
}

- vertical: 分割线方向，（false: 水平; true: 垂直）

**Extended.Toggle**
Props: {
  id: string,
  component: "Extended.Toggle",
  isOn: boolean,
  enabled: boolean,
  styles: {
    selectedColor: string,
    unSelectedColor: string,
    switchPointColor: string
  }
}

- unSelectedColor: 关闭（未选中）状态轨道背景色

**Extended.Progress**
Props: {
  id: string,
  component: "Extended.Progress",
  value: number,
  total: number,
  styles: {
    color: string,
    type: "linear" | "ring" | "eclipse" | "scaleRing" | "capsule"
  }
}

**Extended.Radio**
Props: {
  id: string,
  component: "Extended.Radio",
  value: string,
  checked: boolean,
  group: string,
  indicatorType: "tick" | "dot",
  styles: {
    checkedBackgroundColor: string,
    uncheckedBorderColor: string,
    indicatorColor: string
  }
}

**Extended.Checkbox**
Props: {
  id: string,
  component: "Extended.Checkbox",
  group: string,
  select: boolean,
  styles: {
    selectedColor: string,
    unselectedColor: string,
    mark: {
      "strokeColor": string,
      "size": number,
      "strokeWidth": number
    },
    shape: "circle" | "rounded_square"
  }
}

**Extended.CheckboxGroup**
Props: {
  id: string,
  component: "Extended.CheckboxGroup",
  group: string,
  selectAll: boolean,
  styles: {
    selectedColor: string,
    unselectedColor: string,
    mark: {
      "strokeColor": string,
      "size": number,
      "strokeWidth": number
    },
    checkboxShape: "circle" | "rounded_square"
  }
}

**Extended.If**
Props: {
  id: string,
  component: "Extended.If",
  condition: boolean,
  childrenIf: string[],
  childrenElse: string[],
  styles: {
  }
}

**Extended.Tabs**
Props: {
  id: string,
  component: "Extended.Tabs",
  barPosition: "start" | "end",
  children: string[],
  vertical: boolean,
  scrollable: boolean,
  tabIndex: number,
  styles: {
  }
}

- 通过页签进行内容视图切换的容器组件，每个页签对应一个内容视图
- barPosition: 页签栏位置，"start": vertical属性方法设置为true时，页签位于容器左侧；vertical属性方法设置为false时，页签位于容器顶部。"end": vertical属性方法设置为true时，页签位于容器右侧；vertical属性方法设置为false时，页签位于容器底部。
- children: 子组件类型必须是Extended.TabContent
- vertical: 是否为纵向Tab。默认值：false，横向Tabs，为true时纵向Tabs
- scrollable: 是否可通过滑动页面进行页面切换。默认值：false，不可滚动，为true时可滚动
- tabIndex: 当前选中的页签索引。默认值：0，第一个页签

**Extended.TabContent**
Props: {
  id: string,
  component: "Extended.TabContent",
  title: string,
  icon: string,
  selectedSrc: string,
  tabType: "capsule" | "underline",
  styles: {
    selectColor: string,
    unselectedColor: string,
    defaultBackgroundColor: string,
    selectBackgroundColor: string,
    defaultBorderColor: string,
    selectBorderColor: string,
    fontSize: number,
    fontWeight: 100 | 300 | 400 | 500 | 700 | 900,
    iconSize: number,
    space: number
  }
}

- selectColor: 当前选中tab的标题颜色
- unselectedColor: 默认的标题颜色
- defaultBackgroundColor: 默认的背景颜色
- selectBackgroundColor: 当前选中 tab 的背景颜色
- defaultBorderColor: 默认的边框颜色
- selectBorderColor: 当前选中 tab 的边框颜色
- fontSize: 标题字体大小
- fontWeight: 标题字体粗细
- iconSize: 图标大小
- space: 标题和图标之间的间距

**Extended.Select**
Props: {
  id: string,
  component: "Extended.Select",
  options: {
    value: string,
    icon: string,
    symbolIcon: {
      src: string,
      fontSize: number,
      fontWeight: 100 | 300 | 400 | 500 | 700 | 900,
      fontColor: string,
      renderingStrategy: "single" | "multipleColor" | "multipleOpacity",
      effectStrategy: "none" | "scale" | "hierarchical"
    }
  }[],
  selected: number,
  value: string,
  styles: {
    divider: {
      strokeWidth: number,
      startMargin: number,
      endMargin: number,
      color: string
    },
    font: {
      size: number,
      weight: 100 | 300 | 400 | 500 | 700 | 900,
      family: string,
      style: "normal" | "italic"
    },
    fontColor: string,
    selectedOptionBgColor: string,
    selectedOptionFont: {
      size: number,
      weight: 100 | 300 | 400 | 500 | 700 | 900,
      family: string,
      style: "normal" | "italic"
    },
    selectedOptionFontColor: string,
    optionBgColor: string,
    optionFont: {
      size: number,
      weight: 100 | 300 | 400 | 500 | 700 | 900,
      family: string,
      style: "normal" | "italic"
    },
    optionFontColor: string,
    space: number,
    arrowPosition: "start" | "end",
    menuAlign: {
      "alignType": "start" | "center" | "end",
      "offset": {
        "dx": number,
        "dy": number
      }
    },
    optionWidth: number,
    optionHeight: number,
    menuBackgroundColor: string,
  }
}

- renderingStrategy: 渲染策略，"single": 单色渲染，"multipleColor": 多色渲染，"multipleOpacity": 分层模式，
- effectStrategy: 动效策略，"none": 无动效，"scale": 整体缩放动效，"hierarchical": 层级动效

**Extended.Web**
Props: {
  id: string,
  component: "Extended.Web",
  url: string,
  styles: {
  }
}

- url: web组件的地址

**Extended.Navigation**
Props: {
  id: string,
  component: "Extended.Navigation",
  children: string[],
  currentIndex: number,
  title: string,
  styles: {
    backgroundColor: string
  }
}

导航组件，支持配置多卡片及卡片间跳转
- backgroundColor: 标题栏背景颜色

---

## Common Styles

backgroundImageSizeWithStyle: "cover" | "contain" | "auto" | "fill" | {
  width: number,
  height: number
}

flexShrink: number

width: "matchParent"

height: "matchParent"

constraintSize: {
  minWidth: number,
  maxWidth: number,
  minHeight: number,
  maxHeight: number
}

backgroundImage: string

backgroundPosition: string

backgroundRepeat: string

backgroundSize: string

Multi-layer note: comma-separated `backgroundImage` / `backgroundSize` / `backgroundPosition` requires **per-layer** CSS support. Hosts that only parse the **first** token can mis-render (e.g. photo shrinks to a corner). Prefer **single-layer** `url` + `backgroundImageSizeWithStyle` + optional `backgroundPosition` when targeting weaker clients.

margin: number | { top: number, bottom: number, left: number, right: number }

borderRadius: number | { topLeft: number, topRight: number, bottomRight: number, bottomLeft: number }

visibility: "visible" | "hidden" | "none"

clip: boolean

backgroundColor: string

borderWidth: number | string

borderColor: string

padding: number | { top: number, bottom: number, left: number, right: number }

layoutWeight: number

shadow: {
  offsetX?: number,
  offsetY?: number,
  radius: number,
  color?: string,
  fill?: boolean,
  type?: "color" | "blur" | "outerDefaultXS" | "outerDefaultSM" | "outerDefaultMD" | "outerDefaultLG" | "outerFloatingSM" | "outerFloatingMD"
}